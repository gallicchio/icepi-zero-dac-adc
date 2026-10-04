// sigma_delta_tb.sv -- simulate sigma_delta.sv with no hardware at all.
//
// The testbench plays the laptop (bytes in on uart_rx at 1 Mbaud, frames decoded off
// uart_tx) and the cable: the ADC hears the DAC's own output, one sample late.  A 1 kHz
// sine of 64 codes is sent in each of the four modes, and for each the DAC stream is
// checked for what it may contain (0 or 255 only in the 1-bit modes; 128 +- 65 in the
// 8-bit ones), for changing only every other clock (held x2), and -- the point -- for
// encoding the sine: a lock-in at 1 kHz over 3 whole cycles reads the stream's
// amplitude (64.0 expected) and its third harmonic (small, 1-bit second order included).
// The CIC's frames at d = 10 (24,414 a second) are read back and lock-in'd the same way:
// 64 codes x 2^16 = 4,194,304 expected, less the sinc^3 droop of 0.8 %.  Then mode 0
// and mode 3 at 1.5 codes: plain rounding of a sine that small is a staircase of four
// codes and its lock-in reads wrong; the noise-shaped one reads 1.50.
//
//   iverilog -g2012 -o sigma_delta_tb.vvp sigma_delta_tb.sv sigma_delta.sv ../verilog/uart.sv && vvp sigma_delta_tb.vvp
`timescale 1ns/1ps
module sigma_delta_tb;
    logic clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    logic [7:0] dac, adc = 128;
    logic       dac_clk, adc_clk, tx;
    logic       rx = 1;
    logic [4:0] led;
    sigma_delta dut (.clk(clk), .uart_rx(rx), .uart_tx(tx), .dac_d(dac), .dac_clk(dac_clk),
                     .adc_d(adc), .adc_clk(adc_clk), .led(led));

    localparam real         F_SINE = 1000.0;                 // Hz
    localparam logic [31:0] FWORD  = 32'd171_799;            // 1000 / 25e6 x 2^32
    localparam integer      D      = 10;                     // 2^10: 24,414 frames a second
    localparam integer      CYCLES = 3;                      // whole cycles per test: 3 ms
    localparam integer      CLKS   = CYCLES * 50_000;        // 50 MHz clocks in 3 ms

    // ---- the cable: the ADC hears the DAC, 25 ns after its own clock edge --------------
    always @(posedge adc_clk) adc <= #25 dac;

    // ---- the laptop's bytes -----------------------------------------------------------------
    task automatic send(input logic [7:0] c);
        rx = 0; #1000;
        for (int b = 0; b < 8; b++) begin rx = c[b]; #1000; end
        rx = 1; #1000;
    endtask
    task automatic send32(input logic [31:0] w);
        send(w[31:24]); send(w[23:16]); send(w[15:8]); send(w[7:0]);
    endtask
    task automatic send16(input logic [15:0] w);
        send(w[15:8]); send(w[7:0]);
    endtask

    // ---- the frames back: 0xA5 then 24 bits ------------------------------------------------
    logic [7:0]         c, fb [0:3];
    logic signed [23:0] fv;
    int                 nb = 0, n_frames = 0, framing_errors = 0;
    real                fi = 0, fq = 0;             // the lock-in on the frames
    real                ft = 0;                     // time of the frame, in seconds
    logic               count_frames = 0;
    always @(negedge tx) begin
        #1500;
        for (int b = 0; b < 8; b++) begin c[b] = tx; #1000; end
        if (tx !== 1) framing_errors++;
        if (nb == 0) begin
            if (c == 8'ha5) begin fb[0] = c; nb = 1; end
        end else begin
            fb[nb] = c;
            nb++;
            if (nb == 4) begin
                nb = 0;
                fv = {fb[1], fb[2], fb[3]};
                if (count_frames) begin
                    n_frames++;
                    ft = $time * 1e-9;
                    fi += fv * $cos(6.283185307179586 * F_SINE * ft);
                    fq += fv * $sin(6.283185307179586 * F_SINE * ft);
                end
            end
        end
    end

    // ---- watching the DAC: the lock-in, the allowed codes, and the hold --------------------
    real    si, sq, s3i, s3q, th;                   // the lock-in sums at f and 3f
    int     n_dac, bad_code, odd_changes;
    logic [7:0] dac_prev;
    logic   watching = 0;
    integer onebit;                                 // 1 = only codes 0 and 255 allowed
    always @(posedge clk) begin
        if (watching) begin
            th = 6.283185307179586 * F_SINE * $time * 1e-9;
            si  += (dac - 127.5) * $cos(th);     sq  += (dac - 127.5) * $sin(th);
            s3i += (dac - 127.5) * $cos(3 * th); s3q += (dac - 127.5) * $sin(3 * th);
            n_dac++;
            if (onebit ? (dac != 0 && dac != 255) : (dac < 128 - 66 || dac > 128 + 66)) bad_code++;
            if (dac != dac_prev && dut.tick == 1) odd_changes++;   // dac_d moves on the tick only: a change
                                                                   // made when tick was 1 shows at the next edge
        end
        dac_prev <= dac;
    end

    // ---- one test: a mode and an amplitude, 3 cycles, the verdict --------------------------
    int  errors = 0;
    real a_dac, a3_dac, a_frame;
    task automatic run_mode(input int mode, input int amp256, input real want, input real tol_amp,
                            input real tol_h3, input int check_frames);
        send("M"); send(8'(mode));
        send("A"); send16(16'(amp256));
        #400_000;                                   // the DDS and the CIC settle (0.4 ms)
        si = 0; sq = 0; s3i = 0; s3q = 0; n_dac = 0; bad_code = 0; odd_changes = 0;
        fi = 0; fq = 0; n_frames = 0;
        onebit = (mode == 1 || mode == 2);
        @(posedge clk); watching = 1; count_frames = 1;
        repeat (CLKS) @(posedge clk);
        watching = 0; count_frames = 0;
        a_dac   = 2.0 * $sqrt(si * si + sq * sq) / n_dac;
        a3_dac  = 2.0 * $sqrt(s3i * s3i + s3q * s3q) / n_dac;
        a_frame = 2.0 * $sqrt(fi * fi + fq * fq) / (n_frames > 0 ? n_frames : 1) / 65536.0;
        $display("mode %0d, %6.2f codes: DAC stream amplitude %7.3f (3rd harmonic %6.3f), %0d bad codes, %0d off-tick changes;  %0d frames, amplitude %7.3f codes, %0d dropped",
                 mode, amp256 / 256.0, a_dac, a3_dac, bad_code, odd_changes, n_frames, a_frame, dut.dropped);
        if (bad_code != 0 || odd_changes != 0) errors++;
        if (a_dac < want - tol_amp || a_dac > want + tol_amp) begin
            $display("  FAIL: expected the stream's amplitude %0.2f +- %0.2f", want, tol_amp); errors++;
        end
        if (a3_dac > tol_h3) begin
            $display("  FAIL: third harmonic above %0.2f", tol_h3); errors++;
        end
        if (check_frames) begin
            if (n_frames < CYCLES * 25_000 / (1 << D) - 2) begin
                $display("  FAIL: too few frames (expect about %0d)", CYCLES * 25_000 / (1 << D)); errors++;
            end
            if (a_frame < want * 0.97 || a_frame > want * 1.03) begin
                $display("  FAIL: the frames' amplitude is not %0.2f within 3%%", want); errors++;
            end
        end
    endtask

    initial begin
        #2000;
        send("F"); send32(FWORD);
        send("D"); send(8'(D));
        send("S"); send(8'd1);
        $display("1 kHz, d = %0d: %0d frames a second; each test 3 cycles = %0d clocks", D, 25_000_000 >> D, CLKS);
        //        mode  amp      expect  +-    3rd   frames?
        run_mode(0,    64 * 256, 64.0,   0.5,  0.5,  1);     // 8-bit plain
        run_mode(1,    64 * 256, 64.0,   0.5,  3.0,  1);     // 1-bit first order: tones allowed
        run_mode(2,    64 * 256, 64.0,   0.5,  0.5,  1);     // 1-bit second order
        run_mode(3,    64 * 256, 64.0,   0.5,  0.5,  1);     // 8-bit noise-shaped
        run_mode(3,    384,      1.5,    0.1,  0.1,  0);     // 1.5 codes, shaped: reads 1.50
        run_mode(0,    384,      1.5,    0.6,  1.0,  0);     // 1.5 codes, plain: a staircase (printed, loose)
        if (framing_errors != 0) begin $display("FAIL: %0d framing errors", framing_errors); errors++; end
        if (errors == 0) $display("PASS");
        else             $display("FAIL: %0d checks failed", errors);
        $finish;
    end
endmodule
