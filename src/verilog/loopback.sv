// loopback.sv -- the DAC talks to the ADC: record your own signal coming back.
//
// Wire the DAC output to the ADC input with a cable.  As in capture.sv, the laptop
// sends one character and gets back 16384 ADC samples (25 MS/s) as raw bytes at
// 1,000,000 baud.  Meanwhile the DAC plays a pattern locked to the sample
// counter n, so we know exactly which sample each DAC change happened at:
//
//   "s"  square wave: low for n = 0..511, high for n = 512..1023, repeating
//   "t"  the same square wave, but every DAC change happens 20 ns (half a
//        sample) later -- interleave "s" and "t" for 50 MS/s "equivalent time"
//   "r"  a staircase: DAC code k for n = 64k .. 64k+63, k = 0..255
//   "p"  pseudo-random: HI or LO for each sample, from a 10-bit LFSR (an
//        m-sequence, period 1023), restarted from the same seed at n = 0.
//        It's G1, the register in every GPS satellite (x^10 + x^3 + 1, from all ones)
//
// The recording always starts at n = 0, so sample i of the record is n = i.

module loopback (
    input  logic       clk,         // 50 MHz
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [7:0] dac_d = 32,  // = LO, below
    output logic       dac_clk,
    input  logic       uart_rx,
    output logic       uart_tx,
    output logic [4:0] led
);
    localparam N = 16384;
    localparam logic [7:0] LO = 8'd32, HI = 8'd224;    // the square wave: about -2.97 V and +2.93 V

    // ---- the ADC, as in capture.sv, plus a sample counter n --------------------
    logic        adc_clk_r  = 0;
    logic        new_sample = 0;
    logic [7:0]  sample     = 0;
    logic [13:0] n          = 0;    // 14 bits: counts 0..16383 and wraps
    always_ff @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            sample     <= adc_d;
            n          <= n + 1;    // n and sample change together
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- the pseudo-random sequence: x^10 + x^3 + 1, one step per sample ---------
    // GPS's G1: shift left, feed stage 3 xor stage 10 back into stage 1, and
    // play stage 10 (stage k is lfsr[k-1]).  Like GPS, start from all ones.
    localparam logic [9:0] SEED = 10'h3ff;
    logic [9:0] lfsr = SEED;
    always_ff @(posedge clk)
        if (adc_clk_r == 0)                         // same edge as n
            lfsr <= (n == 14'h3fff) ? SEED : {lfsr[8:0], lfsr[9] ^ lfsr[2]};

    // ---- the DAC: a pattern computed from n ------------------------------------
    logic [1:0]  mode   = 0;                        // 0 = "s", 1 = "t", 2 = "r", 3 = "p"
    logic [13:0] n_late = 0;                        // n, one clock (20 ns) later
    always_ff @(posedge clk) n_late <= n;
    logic [13:0] m;
    assign m = (mode == 1) ? n_late : n;
    always_ff @(posedge clk)
        // ######################################################################
        // ##  KEY LINE: the DAC's value is a function of the sample number n,
        // ##  so every change happens at a known sample of the recording.
        // ######################################################################
        dac_d <= (mode == 2) ? m[13:6] :                // staircase: n / 64
                 (mode == 3) ? (lfsr[9] ? HI : LO) :    // pseudo-random
                               (m[9] ? HI : LO);        // square: bit 9 of n flips every 512
    assign dac_clk = ~clk;

    // ---- the serial port ---------------------------------------------------------
    logic [7:0] rx_data;
    logic       rx_valid;
    logic [7:0] tx_data  = 0;
    logic       tx_start = 0;
    logic       tx_busy;
    uart_rx #(.CLKS_PER_BIT(50)) rx (.clk(clk), .rx(uart_rx),
                                     .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) tx (.clk(clk), .data(tx_data), .start(tx_start),
                                     .busy(tx_busy), .tx(uart_tx));

    // ---- record 16384 samples, starting at n = 0, then send them ---------------
    logic [7:0]  mem [0:N-1];
    logic [13:0] addr = 0;
    typedef enum logic [1:0] {IDLE, WAIT, RECORD, SEND} state_t;
    state_t      state  = IDLE;
    logic [21:0] settle = 0;                        // let the new pattern run a while first

    always_ff @(posedge clk) begin
        tx_start <= 0;
        case (state)
            IDLE:
                if (rx_valid && (rx_data == "s" || rx_data == "t" ||
                                 rx_data == "r" || rx_data == "p")) begin
                    mode   <= (rx_data == "s") ? 0 : (rx_data == "t") ? 1 :
                              (rx_data == "r") ? 2 : 3;
                    settle <= '1;                   // all ones: 2^22 clocks = 84 ms
                    state  <= WAIT;
                end
            WAIT:                                   // settle, then wait for n = 0
                if (settle != 0)
                    settle <= settle - 1;
                else if (new_sample && n == 0) begin
                    mem[0] <= sample;
                    addr   <= 1;
                    state  <= RECORD;
                end
            RECORD:
                if (new_sample) begin
                    mem[addr] <= sample;            // sample i was taken with n = i
                    addr <= addr + 1;
                    if (addr == N - 1)
                        state <= SEND;
                end
            SEND:
                if (!tx_busy && !tx_start) begin
                    tx_data  <= mem[addr];
                    tx_start <= 1;
                    addr     <= addr + 1;
                    if (addr == N - 1)
                        state <= IDLE;
                end
        endcase
    end

    assign led = {sample[7:5], state == SEND, state == RECORD};
endmodule
