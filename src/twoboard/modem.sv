// modem.sv -- a frequency-shift-keying modem: text typed into this board's serial
// port travels down the cable as two tones and comes out of the other board's port.
//
// Transmit: the line from the laptop (uart_rx: 1 when idle) picks the DAC's tone,
//           MARK = 6.25 MHz for 1, SPACE = 3.125 MHz for 0, without phase jumps.
// Receive:  the ADC's samples (25 MS/s) are mixed with both tones and summed over a
//           16-sample (0.64 us) window -- 4 cycles of MARK, 2 of SPACE, so the two
//           detectors ignore each other's tone -- and whichever tone has more energy
//           sets the line back to the laptop (uart_tx).  No signal at all reads as idle (1).
//
// The modem never looks at the bits: it carries whatever baud rate the laptops use, up
// to what a 0.64 us window can resolve (about 2.5 Mbaud, measured).
module modem (
    input  logic       clk,         // 50 MHz
    input  logic       uart_rx,     // from the laptop
    output logic       uart_tx = 1, // to the laptop
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [4:0] led
);
    // ---- transmitter: a phase accumulator whose step follows the laptop's line ----
    logic rx1 = 1, rx2 = 1;
    always_ff @(posedge clk) begin rx1 <= uart_rx; rx2 <= rx1; end
    logic [31:0] phase = 0;
    localparam logic [31:0] TW_MARK = 32'h2000_0000, TW_SPACE = 32'h1000_0000;   // 1/8 and 1/16 of 50 MHz
    logic signed [7:0] sine_table [0:255];
    initial for (int i = 0; i < 256; i++)
        sine_table[i] = $rtoi($floor(100.0 * $sin(6.283185307179586 * i / 256) + 0.5));
    always_ff @(posedge clk) begin
        // ######################################################################
        // ##  KEY LINE: the transmitter.  The serial line picks the step size,
        // ##  and so the frequency.  The phase itself never jumps.
        // ######################################################################
        phase <= phase + (rx2 ? TW_MARK : TW_SPACE);
        dac_d <= sine_table[phase[31:24]] + 128;
    end
    assign dac_clk = ~clk;

    // ---- the ADC at 25 MS/s, as in capture.sv ------------------------------------
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

    // ---- receiver: mix with both tones, sum over 16 samples ----------------------
    // MARK  = fs/4: cos = 1,0,-1,0   sin = 0,1,0,-1
    // SPACE = fs/8: cos = 1,c,0,-c,-1,-c,0,c  with c = 181/256 = 0.707
    // The references are so simple that "multiplying" is just picking x, -x, 0 or c*x.
    logic [2:0] n = 0;
    logic signed [17:0] pmi, pmq, psi, psq;         // this sample times each reference
    logic signed [17:0] xc;
    assign xc = (x * 181) >>> 8;
    always_ff @(posedge clk) if (new_sample) begin
        n <= n + 1;
        case (n[1:0]) 0: begin pmi <= x;  pmq <= 0;  end
                      1: begin pmi <= 0;  pmq <= x;  end
                      2: begin pmi <= -x; pmq <= 0;  end
                      3: begin pmi <= 0;  pmq <= -x; end endcase
        case (n)      0: begin psi <= x;   psq <= 0;   end
                      1: begin psi <= xc;  psq <= xc;  end
                      2: begin psi <= 0;   psq <= x;   end
                      3: begin psi <= -xc; psq <= xc;  end
                      4: begin psi <= -x;  psq <= 0;   end
                      5: begin psi <= -xc; psq <= -xc; end
                      6: begin psi <= 0;   psq <= -x;  end
                      7: begin psi <= xc;  psq <= -xc; end endcase
    end
    // running sums over the last 16 products (a 16-deep delay line for each)
    logic signed [17:0] dmi [0:15], dmq [0:15], dsi [0:15], dsq [0:15];
    logic signed [21:0] smi = 0, smq = 0, ssi = 0, ssq = 0;
    logic [3:0] k = 0;
    logic step = 0;
    always_ff @(posedge clk) begin
        step <= new_sample;                         // one clock after the products update
        if (step) begin
            // ##################################################################
            // ##  KEY LINE: a running sum over the last 16 products: add the
            // ##  newest, subtract the one from 16 samples ago.
            // ##################################################################
            smi <= smi + pmi - dmi[k]; dmi[k] <= pmi;
            smq <= smq + pmq - dmq[k]; dmq[k] <= pmq;
            ssi <= ssi + psi - dsi[k]; dsi[k] <= psi;
            ssq <= ssq + psq - dsq[k]; dsq[k] <= psq;
            k <= k + 1;
        end
    end
    // energies and the decision
    logic [43:0] em = 0, es = 0;
    always_ff @(posedge clk) begin
        em <= smi * smi + smq * smq;
        es <= ssi * ssi + ssq * ssq;
        // ######################################################################
        // ##  KEY LINE: the decision.  More MARK energy than SPACE: a 1.
        // ######################################################################
        uart_tx <= (em >= es) || (em + es < 44'd40000);   // no signal: idle
    end
    assign led = {~uart_tx, ~rx2, 3'b0};
endmodule
