// radio.sv -- 5.05's modem, made narrow enough for a radio link.  Text typed into this
// board's serial port leaves the DAC as one of two tones near 6.78 MHz, and the other
// board's receiver turns the tones back into text.
//
// Transmit: MARK = 6.7875 MHz for a 1, SPACE = 6.7725 MHz for a 0: 15 kHz apart, both
//           inside the 6.765-6.795 MHz ISM band.  A phase accumulator, as in modem.sv.
// Receive:  1.08's lock-in, once per tone: each ADC sample is multiplied by cos and -sin
//           of the tone, and each product goes through a "leaky" average with a time
//           constant of 2^LOGTAU samples (2^10 = 41 us).  Whichever tone has more energy,
//           I^2 + Q^2, sets the line to the laptop; too little of either reads as idle (1).
//           The narrow average is what lets it hear weak signals: it lets in noise from
//           about 6 kHz, against 780 kHz for modem.sv's 16-sample window.
// LEDs:     a signal-strength meter.  Each LED needs about 3 times the amplitude
//           (10 dB more) of the one to its right; the rightmost lights at half an ADC code.
//
// The modem never looks at the bits, so any baud rate up to about 9600 works (a bit
// must last a few time constants).
module radio #(
    parameter integer AMP = 100,    // the transmitted tone's amplitude, in DAC codes (max 127)
    parameter integer LOGTAU = 10   // the receiver's averaging time: 2^LOGTAU samples
) (
    input  logic       clk,         // 50 MHz
    input  logic       uart_rx,     // from the laptop
    output logic       uart_tx = 1, // to the laptop
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [4:0] led
);
    // tuning words: f / 50 MHz * 2^32 for the DAC, f / 25 MHz * 2^32 for the ADC's references
    localparam logic [31:0] TX_MARK = 32'h22c0_8312, TX_SPACE = 32'h22ac_d9e8;
    localparam logic [31:0] RX_MARK = 32'h4581_0625, RX_SPACE = 32'h4559_b3d0;

    logic signed [7:0] tx_table [0:255], ref_table [0:255];
    initial for (int i = 0; i < 256; i++) begin
        tx_table[i]  = $rtoi($floor(AMP * $sin(6.283185307179586 * i / 256) + 0.5));
        ref_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));
    end

    // ---- transmitter: as modem.sv, with this page's two tones --------------------------
    logic rx1 = 1, rx2 = 1;
    always_ff @(posedge clk) begin rx1 <= uart_rx; rx2 <= rx1; end
    logic [31:0] tx_phase = 0;
    always_ff @(posedge clk) begin
        // ######################################################################
        // ##  KEY LINE: the transmitter.  The laptop's line picks the tone.
        // ######################################################################
        tx_phase <= tx_phase + (rx2 ? TX_MARK : TX_SPACE);
        dac_d    <= tx_table[tx_phase[31:24]] + 128;
    end
    assign dac_clk = ~clk;

    // ---- the ADC at 25 MS/s, as in capture.sv -------------------------------------------
    logic adc_clk_r = 0, new_sample = 0;
    logic signed [8:0] x = 0;
    always_ff @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            x <= $signed({1'b0, adc_d}) - 9'sd128;
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- receiver: two lock-ins, with leaky averages ------------------------------------
    // Each tone's reference has its own phase accumulator, stepped once per ADC sample.
    // As in 1.08: the table at the phase is cos, a quarter turn on is -sin.
    logic [31:0] pm = 0, ps = 0;
    logic signed [16:0] p [0:3];                    // x * the four references
    logic step = 0;
    always_ff @(posedge clk) begin
        step <= new_sample;
        if (new_sample) begin
            pm   <= pm + RX_MARK;
            ps   <= ps + RX_SPACE;
            p[0] <= x * ref_table[pm[31:24]];               // mark, cos
            p[1] <= x * ref_table[pm[31:24] + 8'd64];       // mark, -sin
            p[2] <= x * ref_table[ps[31:24]];               // space, cos
            p[3] <= x * ref_table[ps[31:24] + 8'd64];       // space, -sin
        end
    end
    localparam integer W = 17 + LOGTAU + 1;
    logic signed [W-1:0] acc [0:3];
    initial for (int i = 0; i < 4; i++) acc[i] = 0;
    always_ff @(posedge clk)
        if (step)
            for (int i = 0; i < 4; i++)
                // ##############################################################
                // ##  KEY LINE: the leaky average.  Add the new product, and let
                // ##  1/2^LOGTAU of the total leak away.  acc / 2^LOGTAU is then
                // ##  an average over the last ~2^LOGTAU samples.
                // ##############################################################
                acc[i] <= acc[i] + p[i] - (acc[i] >>> LOGTAU);

    // energies: (I^2 + Q^2) of each tone, with I and Q the averages (acc / 2^LOGTAU)
    logic signed [16:0] avg [0:3];
    always_comb for (int i = 0; i < 4; i++) avg[i] = acc[i] >>> LOGTAU;
    logic [34:0] em = 0, es = 0, e = 0;
    always_ff @(posedge clk) begin
        em <= avg[0] * avg[0] + avg[1] * avg[1];
        es <= avg[2] * avg[2] + avg[3] * avg[3];
        e  <= em + es;
        // ######################################################################
        // ##  KEY LINE: the decision.  More MARK energy than SPACE: a 1.  Less
        // ##  than (half a code x 127/2)^2 of either: nothing there, so idle (1).
        // ######################################################################
        uart_tx <= (em >= es) || (em + es < 35'd1000);
    end

    // signal strength: a tone of A codes gives (A x 127/2)^2, so these thresholds are
    // amplitudes of 50, 15, 5, 1.5 and 0.5 codes
    assign led = {e >= 35'd10_000_000, e >= 35'd900_000, e >= 35'd100_000,
                  e >= 35'd9_000, e >= 35'd1_000};
endmodule
