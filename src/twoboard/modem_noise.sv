// modem_noise.sv -- modem.sv with three knobs, for measuring error rate against noise:
//
//   NOISE   white noise added to the transmitted tone: about 0.577 * NOISE DAC codes rms
//   AMP     the tone's amplitude in DAC codes (modem.sv: 100)
//   LOGWIN  the receiver's window is 2^LOGWIN samples (modem.sv: 4, i.e. 16 samples)
//
// With the defaults (NOISE = 0, AMP = 100, LOGWIN = 4) it is modem.sv.  Everything else
// is as in modem.sv: MARK = 6.25 MHz for 1, SPACE = 3.125 MHz for 0; the ADC at 25 MS/s
// is mixed with both tones and summed over the window, and the stronger tone wins.
module modem_noise #(parameter integer NOISE = 0, parameter integer AMP = 100,
                     parameter integer LOGWIN = 4) (
    input  logic       clk,         // 50 MHz
    input  logic       uart_rx,     // from the laptop
    output logic       uart_tx = 1, // to the laptop
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [4:0] led
);
    localparam integer W = 1 << LOGWIN;                   // window, in samples
    // ---- transmitter: a phase accumulator whose step follows the laptop's line ----
    logic rx1 = 1, rx2 = 1;
    always_ff @(posedge clk) begin rx1 <= uart_rx; rx2 <= rx1; end
    logic [31:0] phase = 0;
    localparam logic [31:0] TW_MARK = 32'h2000_0000, TW_SPACE = 32'h1000_0000;   // 1/8 and 1/16 of 50 MHz
    logic signed [7:0] sine_table [0:255];
    initial for (int i = 0; i < 256; i++)
        sine_table[i] = $rtoi($floor(AMP * $sin(6.283185307179586 * i / 256) + 0.5));
    // ---- noise: the four bytes of a 32-bit xorshift generator, added up (a sum of
    //      four nearly independent bytes is nearly Gaussian); it repeats after 2^32 - 1
    //      clocks, 86 s
    logic [31:0] r = 32'h2545_f491;
    logic [31:0] r1, r2, r3;
    assign r1 = r ^ (r << 13);
    assign r2 = r1 ^ (r1 >> 17);
    assign r3 = r2 ^ (r2 << 5);
    logic signed [10:0] gsum = 0;                   // sum of four bytes, minus the mean
    logic signed [19:0] scaled = 0;
    logic signed [9:0]  tone = 0;
    always_ff @(posedge clk) begin
        // ######################################################################
        // ##  KEY LINE: one step of the xorshift random-number generator,
        // ##  32 new pseudo-random bits every clock.
        // ######################################################################
        r      <= r3;
        gsum   <= $signed({3'b0, r[7:0]}) + $signed({3'b0, r[15:8]}) + $signed({3'b0, r[23:16]})
                + $signed({3'b0, r[31:24]}) - 11'sd510;
        scaled <= gsum * NOISE;
        phase  <= phase + (rx2 ? TW_MARK : TW_SPACE);
        tone   <= sine_table[phase[31:24]];
    end
    // ##########################################################################
    // ##  KEY LINE: tone plus noise, clipped to what the DAC can do.
    // ##########################################################################
    logic signed [11:0] v;
    assign v = 12'sd128 + tone + (scaled >>> 8);
    always_ff @(posedge clk) dac_d <= (v < 0) ? 8'd0 : (v > 255) ? 8'd255 : v[7:0];   // clip
    assign dac_clk = ~clk;

    // ---- the ADC at 25 MS/s, as in capture.sv -----------------------------------
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

    // ---- receiver: mix with both tones, sum over the window ----------------------
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
    logic signed [17:0] dmi [0:W-1], dmq [0:W-1], dsi [0:W-1], dsq [0:W-1];
    logic signed [17+LOGWIN:0] smi = 0, smq = 0, ssi = 0, ssq = 0;
    logic [LOGWIN-1:0] k = 0;
    logic step = 0;
    always_ff @(posedge clk) begin
        step <= new_sample;
        if (step) begin
            smi <= smi + pmi - dmi[k]; dmi[k] <= pmi;
            smq <= smq + pmq - dmq[k]; dmq[k] <= pmq;
            ssi <= ssi + psi - dsi[k]; dsi[k] <= psi;
            ssq <= ssq + psq - dsq[k]; dsq[k] <= psq;
            k <= k + 1;
        end
    end
    // energies and the decision.  "No signal" is now less than a third of the amplitude
    // that a tone of AMP codes gives (modem.sv's 40000 is this for AMP = 100, LOGWIN = 4).
    localparam logic [63:0] QUIET = (AMP * W / 8) * (AMP * W / 8);
    logic [2*(18+LOGWIN)-1:0] em = 0, es = 0;
    always_ff @(posedge clk) begin
        em <= smi * smi + smq * smq;
        es <= ssi * ssi + ssq * ssq;
        uart_tx <= (em >= es) || (em + es < QUIET);
    end
    assign led = {~uart_tx, ~rx2, 3'b0};
endmodule
