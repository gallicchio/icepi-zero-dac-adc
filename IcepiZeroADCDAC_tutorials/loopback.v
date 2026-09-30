// loopback.v -- the DAC talks to the ADC: record your own signal coming back.
//
// Wire the DAC output to the ADC input with a cable.  As in capture.v, the PC
// sends one character and gets back 16384 ADC samples (25 MS/s) as raw bytes at
// 1,000,000 baud.  Meanwhile the DAC plays a pattern locked to the sample
// counter n, so we know exactly which sample each DAC change happened at:
//
//   "s"  square wave: low for n = 0..511, high for n = 512..1023, repeating
//   "t"  the same square wave, but every DAC change happens 20 ns (half a
//        sample) later -- interleave "s" and "t" for 50 MS/s "equivalent time"
//   "r"  a staircase: DAC code k for n = 64k .. 64k+63, k = 0..255
//   "p"  pseudo-random: HI or LO for each sample, from a 10-bit LFSR (an
//        m-sequence, period 1023), restarted from the same seed at n = 0
//
// The recording always starts at n = 0, so sample i of the record is n = i.

module loopback (
    input  wire       clk,         // 50 MHz
    input  wire [7:0] adc_d,
    output wire       adc_clk,
    output reg  [7:0] dac_d,
    output wire       dac_clk,
    input  wire       uart_rx,
    output wire       uart_tx,
    output wire [4:0] led
);
    localparam N = 16384;
    localparam LO = 8'd32, HI = 8'd224;     // the square wave: about -2.97 V and +2.93 V

    // ---- the ADC, as in capture.v, plus a sample counter n --------------------
    reg        adc_clk_r = 0;
    reg        new_sample = 0;
    reg [7:0]  sample = 0;
    reg [13:0] n = 0;
    always @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            sample     <= adc_d;
            n          <= n + 1;           // n and sample change together
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- the pseudo-random sequence: x^10 + x^7 + 1, one step per sample -------
    localparam [9:0] SEED = 10'h001;
    reg [9:0] lfsr = SEED;
    always @(posedge clk)
        if (adc_clk_r == 0)                // same edge as n
            lfsr <= (n == 14'h3fff) ? SEED : {lfsr[8:0], lfsr[9] ^ lfsr[6]};

    // ---- the DAC: a pattern computed from n ------------------------------------
    reg [1:0]  mode = 0;                   // 0 = "s", 1 = "t", 2 = "r", 3 = "p"
    reg [13:0] n_late = 0;                 // n, one clock (20 ns) later
    always @(posedge clk) n_late <= n;
    wire [13:0] m = (mode == 1) ? n_late : n;
    initial dac_d = LO;
    always @(posedge clk)
        dac_d <= (mode == 2) ? m[13:6] :
                 (mode == 3) ? (lfsr[9] ? HI : LO) :
                               (m[9] ? HI : LO);
    assign dac_clk = ~clk;

    // ---- the serial port ---------------------------------------------------------
    wire [7:0] rx_data;
    wire       rx_valid;
    reg  [7:0] tx_data = 0;
    reg        tx_start = 0;
    wire       tx_busy;
    uart_rx #(.CLKS_PER_BIT(50)) rx (.clk(clk), .rx(uart_rx),
                                     .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) tx (.clk(clk), .data(tx_data), .start(tx_start),
                                     .busy(tx_busy), .tx(uart_tx));

    // ---- record 16384 samples, starting at n = 0, then send them ---------------
    reg [7:0]  mem [0:N-1];
    reg [13:0] addr = 0;
    localparam IDLE = 0, WAIT = 1, RECORD = 2, SEND = 3;
    reg [1:0]  state = IDLE;
    reg [21:0] settle = 0;                 // let the new pattern run a while first

    always @(posedge clk) begin
        tx_start <= 0;
        case (state)
            IDLE:
                if (rx_valid && (rx_data == "s" || rx_data == "t" ||
                                 rx_data == "r" || rx_data == "p")) begin
                    mode   <= (rx_data == "s") ? 0 : (rx_data == "t") ? 1 :
                              (rx_data == "r") ? 2 : 3;
                    settle <= ~0;                    // 84 ms
                    state  <= WAIT;
                end
            WAIT:                                    // settle, then wait for n = 0
                if (settle != 0)
                    settle <= settle - 1;
                else if (new_sample && n == 0) begin
                    mem[0] <= sample;
                    addr   <= 1;
                    state  <= RECORD;
                end
            RECORD:
                if (new_sample) begin
                    mem[addr] <= sample;             // sample i was taken with n = i
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
