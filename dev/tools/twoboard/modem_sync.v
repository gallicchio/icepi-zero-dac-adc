// modem_sync.v -- the textbook receiver of 10.6 (instructor's version): the transmitter
// (and noise) of modem_noise.v, and a receiver that knows the baud rate.
//
// Receive: sliding sums of each tone over NINT = 216 samples (216 holds whole cycles of
// both tones), and a BIT CLOCK that counts SPB + FRAC/256 samples a bit.  At the end of
// each bit it decides, D = Em - Es >= 0, and sends that bit on to the PC: the PC gets a
// clean copy of the line, one bit late.  (The PC's "115 200 baud" is really 3 MHz / 26 =
// 115 385 baud on the FT231X, 216.67 samples a bit.  0.16% is nothing to a UART, which
// starts afresh every byte, but to a free-running bit clock it is a third of a sample
// every bit.)
// Clock recovery (an early-late gate): DELTA samples before and after each decision,
// |D| is noted.  If the decision is late, the window already holds part of the next bit
// when that differs, so |D| after is smaller than |D| before; and the other way round.
// After V more votes one way than the other, the next bit is made a sample longer or
// shorter.  Without transitions (idle, or long runs) the votes are a random walk; with no
// noise at all they tie, a tie counts as "early", and the clock drifts a sample every 8
// bits.  That does no harm: the bits sent on are then a shifted copy, which the PC's UART
// times afresh, and only the SNR suffers.  (No noise, 30 ms between single bytes: 197 of
// 200 came through.)  Measured with tools/twoboard/fsk_sync_run.py.
module modem_sync #(parameter integer NOISE = 0, parameter integer AMP = 25,
                    parameter integer NINT = 216, parameter integer SPB = 216,
                    parameter integer FRAC = 171,                 // 0.67 * 256
                    parameter integer DELTA = 40, parameter integer V = 8) (
    input  wire       clk,          // 50 MHz
    input  wire       uart_rx,      // from the PC
    output reg        uart_tx = 1,  // to the PC
    output reg  [7:0] dac_d = 128,
    output wire       dac_clk,
    input  wire [7:0] adc_d,
    output wire       adc_clk,
    output wire [4:0] led
);
    // ---- transmitter and noise, as in modem_noise.v ------------------------------
    reg rx1 = 1, rx2 = 1;
    always @(posedge clk) begin rx1 <= uart_rx; rx2 <= rx1; end
    reg [31:0] phase = 0;
    localparam [31:0] TW_MARK = 32'h2000_0000, TW_SPACE = 32'h1000_0000;
    reg signed [7:0] sine_table [0:255];
    integer i;
    initial for (i = 0; i < 256; i = i + 1)
        sine_table[i] = $rtoi($floor(AMP * $sin(6.283185307179586 * i / 256) + 0.5));
    reg  [31:0] r = 32'h2545_f491;
    wire [31:0] r1 = r ^ (r << 13), r2 = r1 ^ (r1 >> 17), r3 = r2 ^ (r2 << 5);
    reg signed [10:0] gsum = 0;
    reg signed [19:0] scaled = 0;
    reg signed [9:0]  tone = 0;
    always @(posedge clk) begin
        r      <= r3;
        gsum   <= $signed({3'b0, r[7:0]}) + $signed({3'b0, r[15:8]}) + $signed({3'b0, r[23:16]})
                + $signed({3'b0, r[31:24]}) - 11'sd510;
        scaled <= gsum * NOISE;
        phase  <= phase + (rx2 ? TW_MARK : TW_SPACE);
        tone   <= sine_table[phase[31:24]];
    end
    wire signed [11:0] v = 12'sd128 + tone + (scaled >>> 8);
    always @(posedge clk) dac_d <= (v < 0) ? 8'd0 : (v > 255) ? 8'd255 : v[7:0];
    assign dac_clk = ~clk;

    // ---- the ADC at 25 MS/s ------------------------------------------------------
    reg adc_clk_r = 0, new_sample = 0;
    reg signed [8:0] x = 0;
    always @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            x <= $signed({1'b0, adc_d}) - 9'sd128;
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- mixers and NINT-sample sliding sums --------------------------------------
    reg [2:0] n = 0;
    reg signed [17:0] pmi, pmq, psi, psq;
    wire signed [17:0] xc = (x * 181) >>> 8;
    always @(posedge clk) if (new_sample) begin
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
    reg signed [17:0] dmi [0:NINT-1], dmq [0:NINT-1], dsi [0:NINT-1], dsq [0:NINT-1];
    reg signed [25:0] smi = 0, smq = 0, ssi = 0, ssq = 0;
    reg [7:0] k = 0;
    reg step = 0, step2 = 0, tick = 0;
    always @(posedge clk) begin
        step <= new_sample;
        if (step) begin
            smi <= smi + pmi - dmi[k]; dmi[k] <= pmi;
            smq <= smq + pmq - dmq[k]; dmq[k] <= pmq;
            ssi <= ssi + psi - dsi[k]; dsi[k] <= psi;
            ssq <= ssq + psq - dsq[k]; dsq[k] <= psq;
            k <= (k == NINT - 1) ? 0 : k + 1;
        end
    end
    // energies: registered squares, then D = Em - Es and |D|
    reg [51:0] em = 0, es = 0;
    reg signed [52:0] d = 0;
    always @(posedge clk) begin
        step2 <= step;
        tick  <= step2;                           // one per sample, after em, es are fresh
        em <= smi * smi + smq * smq;
        es <= ssi * ssi + ssq * ssq;
        d  <= $signed({1'b0, em}) - $signed({1'b0, es});
    end
    wire [52:0] dabs = d[52] ? -d : d;
    localparam [52:0] QUIET = (AMP * NINT / 8) * (AMP * NINT / 8);

    // ---- the bit clock and the early-late gate -------------------------------------
    reg signed [9:0] c = 0;                       // sample within the bit; decide at len-1
    reg [7:0] frac = 0;
    reg [9:0] len = SPB;                          // this bit's length: SPB or SPB + 1
    wire [8:0] fnext = frac + FRAC;
    reg [52:0] early = 0;
    reg signed [7:0] vote = 0;
    reg signed [1:0] adjust = 0;                  // +1: next bit a sample longer, -1: shorter
    always @(posedge clk) if (tick) begin
        c <= c + 1;
        if (c == len - 1 - DELTA) early <= dabs;
        if (c == len - 1) begin
            uart_tx <= (d >= 0) || (em + es < QUIET);   // the bit just ended, sent on
            c <= (adjust == 1) ? -1 : (adjust == -1) ? 1 : 0;
            adjust <= 0;
            frac <= fnext[7:0];
            len  <= SPB + fnext[8];               // a carry makes the next bit a sample longer
        end
        if (c == DELTA - 1) begin                 // DELTA after the last decision
            if (dabs > early) begin               // later is better: we decide early
                if (vote == V - 1) begin vote <= 0; adjust <= 1; end else vote <= vote + 1;
            end else begin
                if (vote == -V + 1) begin vote <= 0; adjust <= -1; end else vote <= vote - 1;
            end
        end
    end
    assign led = {~uart_tx, ~rx2, adjust == 1, adjust == -1, 1'b0};
endmodule
