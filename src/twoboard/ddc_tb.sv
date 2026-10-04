// ddc_tb.sv -- simulate ddc.sv with no hardware at all.
//
// The testbench plays the laptop (real serial bytes in on uart_rx at 1 Mbaud, and the
// I/Q frames decoded back off uart_tx) and the analog world: the ADC hears a 20-code
// sine at exactly the NCO's frequency, so every I/Q frame should be the same, with
// |I + jQ| = 2^10 x 20 x 127/2 >>> 1 = 650,240 at d = 10.  Meanwhile the transmitter
// plays a two-symbol message, 2000 clocks a symbol, and the DAC is watched for a phase
// jump at the tone switch and for silence once the FIFO is empty.  d = 10 is faster
// than the UART can carry, so every other frame should be dropped; at d = 11 none.
//
//   iverilog -g2012 -o ddc_tb.vvp ddc_tb.sv ddc.sv ../verilog/uart.sv && vvp ddc_tb.vvp
`timescale 1ns/1ps
module ddc_tb;
    logic clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    logic [7:0] dac, adc = 128;
    logic       dac_clk, adc_clk, tx;
    logic       rx = 1;
    logic [4:0] led;

    ddc dut (.clk(clk), .uart_rx(rx), .uart_tx(tx), .dac_d(dac), .dac_clk(dac_clk),
             .adc_d(adc), .adc_clk(adc_clk), .led(led));

    // the tones: 6.78 MHz and 6.78 MHz + 25e6/2^22 = 5.96 Hz, as the laptop would send them
    localparam logic [31:0] W0  = 32'h22b6_ae7d;    // 6.78e6 / 50e6 x 2^32
    localparam logic [31:0] W1  = W0 + 32'd512;     // + 5.96 Hz is + 2^9 at the DAC
    localparam logic [31:0] RXW = 32'h456d_5cfb;    // 6.78e6 / 25e6 x 2^32
    localparam integer      SYM = 2000;             // clocks per symbol (2^23 on the board)
    localparam real         A_ADC = 20.0;           // the tone at the ADC, in codes
    localparam real         EXPECT = 650240.0;      // 2^10 x 20 x 127/2 >>> 1
    localparam integer      MAX_STEP = 85;          // 2 x 100 x sin(pi x 6.78/50) = 82.6, +rounding

    // ---- the analog world: a sine at the NCO's own frequency into the ADC ------------
    // The AD9280 puts a new code out 25 ns after each rising edge of its clock.
    // +df=HZ puts the tone that far above the NCO instead: the I/Q then rotate at df.
    real ph = 0, df = 0;
    initial void'($value$plusargs("df=%f", df));
    always @(posedge adc_clk) begin
        adc <= #25 8'(128 + $rtoi($floor(A_ADC * $sin(ph) + 0.5)));
        ph = ph + 6.283185307179586 * (RXW / 4294967296.0 + df / 25.0e6);
    end

    // ---- the laptop: send bytes at 1 Mbaud (1 us a bit) ---------------------------------
    task automatic send(input logic [7:0] c);
        rx = 0; #1000;                                  // start bit
        for (int b = 0; b < 8; b++) begin rx = c[b]; #1000; end
        rx = 1; #1000;                                  // stop bit
    endtask
    task automatic send32(input logic [31:0] w);        // big-endian
        send(w[31:24]); send(w[23:16]); send(w[15:8]); send(w[7:0]);
    endtask

    // ...and listen: bytes off uart_tx, gathered into 7-byte frames from each 0xA5
    logic [7:0]         c, fb [0:6];
    logic signed [23:0] fi, fq;
    int                 nb = 0, n_bytes = 0, n_frames = 0, framing_errors = 0;
    int                 good = 0, bad = 0, checked = 0;
    real                mag, ang, ang_prev = 0;
    always @(negedge tx) begin                          // a start bit has begun
        #1500;                                          // the middle of data bit 0
        for (int b = 0; b < 8; b++) begin c[b] = tx; #1000; end
        if (tx !== 1) framing_errors++;
        n_bytes++;
        if (nb == 0) begin
            if (c == 8'ha5) begin fb[0] = c; nb = 1; end
        end else begin
            fb[nb] = c;
            nb++;
            if (nb == 7) begin
                nb = 0;
                n_frames++;
                fi  = {fb[1], fb[2], fb[3]};
                fq  = {fb[4], fb[5], fb[6]};
                mag = $sqrt(1.0 * fi * fi + 1.0 * fq * fq);
                ang = $atan2(1.0 * fq, 1.0 * fi) * 180.0 / 3.141592653589793;
                $display("%7t us  frame %2d: I = %8d  Q = %8d  |z| = %9.1f (%+.2f%% of %0d)  angle %7.2f deg  dropped so far %0d",
                         $time / 1000, n_frames, fi, fq, mag, 100.0 * (mag / EXPECT - 1), $rtoi(EXPECT), ang, dut.dropped);
                // from the second frame on, check the size, and (with the tone on the
                // NCO) that the angle stands still
                if (n_frames >= 2) begin
                    checked++;
                    if (mag > EXPECT * 0.97 && mag < EXPECT * 1.03 &&
                        (df != 0 || $abs(ang - ang_prev) < 2.0)) good++;
                    else bad++;
                end
                ang_prev = ang;
            end
        end
    end

    // ---- watch the transmitter --------------------------------------------------------
    logic [7:0]  dac_prev   = 128;
    logic [31:0] phase_prev = 0, word_prev = 0;
    logic        on_1 = 0, on_2 = 0;                    // was the DAC playing a tone, 1 and 2 clocks ago
    int          max_step = 0, on_clocks = 0, bad_phase_steps = 0, step_now;
    longint      t_word [0:3];                          // clock of each tuning-word change
    int          n_word = 0;
    always @(posedge clk) begin
        // the biggest sample-to-sample step while a tone is playing (the drop to 128 at
        // the end of a message is meant to be a jump)
        step_now = (dac > dac_prev) ? dac - dac_prev : dac_prev - dac;
        if (on_1 && on_2 && step_now > max_step) max_step = step_now;
        dac_prev = dac;
        on_2 = on_1; on_1 = dut.on2;
        // the phase may only ever advance by a tuning word in use, or not at all
        if (!(dut.tx_phase - phase_prev == 0 || dut.tx_phase - phase_prev == W0 ||
              dut.tx_phase - phase_prev == W1))
            bad_phase_steps++;
        phase_prev = dut.tx_phase;
        if (dut.tx_on) on_clocks++;
        if (dut.tx_word != word_prev) begin
            $display("%7t us  tuning word %08x -> %08x", $time / 1000, word_prev, dut.tx_word);
            if (n_word < 4) t_word[n_word] = $time / 20;
            n_word++;
        end
        word_prev = dut.tx_word;
    end

    // ---- the script -------------------------------------------------------------------
    int silent_bad, tone_codes, dropped_at, frames_at, msg_clocks, errors = 0;
    initial begin
        #2000;
        send("W"); send(8'd0); send32(W0);
        send("W"); send(8'd1); send32(W1);
        send("A"); send(8'd100);
        send("T"); send32(SYM);
        send("R"); send32(RXW);
        send("D"); send(8'd10);
        send("S"); send(8'd1);
        $display("%7t us  settings sent", $time / 1000);
        #60_000;                                        // a few frames (41 us each at d = 10)

        // the message: tone 0 then tone 1, SYM clocks each, then silence
        send("M"); send(8'd2); send(8'd0); send(8'd1);
        $display("%7t us  message sent: 2 symbols of %0d clocks", $time / 1000, SYM);
        wait (dut.tx_on == 1);
        wait (dut.tx_on == 0);
        msg_clocks = on_clocks;
        repeat (6) @(posedge clk);                      // the DAC pipeline
        silent_bad = 0;
        repeat (1000) begin @(posedge clk); if (dac != 128) silent_bad++; end
        $display("%7t us  after the FIFO emptied: %0d of 1000 DAC samples not 128", $time / 1000, silent_bad);
        if (silent_bad != 0) errors++;

        // a continuous tone, then off
        send("C"); send(8'd1);
        #20_000;
        if (!dut.tx_on || !led[0]) begin $display("FAIL: 'C' 1 did not start a tone"); errors++; end
        tone_codes = 0;
        repeat (200) begin @(posedge clk); if (dac != 128) tone_codes++; end
        $display("%7t us  'C' 1: tx_on = %0d, led[0] = %0d, %0d of 200 DAC samples not 128", $time / 1000, dut.tx_on, led[0], tone_codes);
        send("C"); send(8'hff);
        #2000;
        silent_bad = 0;
        repeat (200) begin @(posedge clk); if (dac != 128) silent_bad++; end
        $display("%7t us  'C' 0xFF: tx_on = %0d, %0d of 200 DAC samples not 128", $time / 1000, dut.tx_on, silent_bad);
        if (silent_bad != 0 || dut.tx_on) errors++;

        // d = 11: every frame fits in the UART, so none should be dropped
        send("D"); send(8'd11);
        #200_000;                                       // 2 frames: let the change settle
        dropped_at = dut.dropped; frames_at = n_frames;
        #(6 * 4096 * 20);                               // 6 more frames at d = 11
        $display("%7t us  d = 11: %0d frames, %0d dropped", $time / 1000, n_frames - frames_at, dut.dropped - dropped_at);
        if (dut.dropped - dropped_at != 0 || n_frames - frames_at < 5) errors++;
        send("S"); send(8'd0);
        #100_000;

        // the verdict
        $display("");
        $display("transmitter: the message's tone was on for %0d clocks (expect %0d)", msg_clocks, 2 * SYM);
        if (msg_clocks != 2 * SYM) errors++;
        if (n_word >= 3)
            $display("             tone switch after %0d clocks, silence after %0d more (expect %0d, %0d)",
                     t_word[1] - t_word[0], t_word[2] - t_word[1], SYM, SYM);
        if (n_word < 3 || t_word[1] - t_word[0] != SYM || t_word[2] - t_word[1] != SYM) errors++;
        $display("             phase steps that were not a tuning word: %0d; largest DAC step %0d codes (limit %0d)",
                 bad_phase_steps, max_step, MAX_STEP);
        if (bad_phase_steps != 0 || max_step > MAX_STEP) errors++;
        $display("receiver:    %0d bytes, %0d frames, %0d framing errors; %0d of %0d checked frames within 3%% of %0d%0s; %0d dropped at d = 10",
                 n_bytes, n_frames, framing_errors, good, checked, $rtoi(EXPECT),
                 df == 0 ? " and 2 deg of the last" : "", dropped_at);
        if (bad != 0 || framing_errors != 0 || checked < 5 || dropped_at == 0) errors++;
        if (errors == 0) $display("PASS");
        else             $display("FAIL: %0d checks failed", errors);
        $finish;
    end
endmodule
