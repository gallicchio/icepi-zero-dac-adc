`timescale 1ns/1ps
// Two Icepi stacks: A (role 0, X) and B (role 1, Y).  A's DAC reaches B's ADC through a tee and a cable: here the
// bench's measured transfer (gain 0.76, offset +30 codes), the edge spread over two samples, a three-sample delay, +/-1 code of noise.  Every DAC sample pair (A.x, B.y) goes to
// icepi_samples.txt with "F" at each of A's frames; render_icepi.py draws the XY picture, which is the seal only if
// B is in step with A.  B's own clock is 100 ppm fast, so its rate trim has work to do.  The period between bursts is
// set to 4 ms here (register 1F; the show's is 20 ms), so the test of every mode takes a fifth of the time.
module tb_icepi;
    reg clka = 0; always #10 clka = ~clka;                       // 50 MHz
    reg clkb = 0; always #9.999 clkb = ~clkb;                    // 100 ppm fast (at 1 ps resolution 9.9994 was always 9.999)
    localparam real BIT = 1000.0;
    reg uart_rx_a = 1, uart_rx_b = 1; wire uart_tx_a, uart_tx_b;
    wire [7:0] dac_a, dac_b; wire dac_clk_a, dac_clk_b, adc_clk_a, adc_clk_b; wire [4:0] led_a, led_b;
    reg [7:0] adc_in_b = 8'd128;
    top_icepi #(.ROLE(0)) A (.clk(clka), .led(led_a), .btn(1'b1), .uart_tx(uart_tx_a), .uart_rx(uart_rx_a), .adc_d(8'd128), .adc_clk(adc_clk_a), .dac_d(dac_a), .dac_clk(dac_clk_a));
    top_icepi #(.ROLE(1)) B (.clk(clkb), .led(led_b), .btn(1'b1), .uart_tx(uart_tx_b), .uart_rx(uart_rx_b), .adc_d(adc_in_b), .adc_clk(adc_clk_b), .dac_d(dac_b), .dac_clk(dac_clk_b));
    // the cable: A's DAC output (a new value every clka, held) sampled by B's ADC clock: the bench's measured transfer
    // (ADC = 0.76 DAC + 30), the module's edge spread over two samples with an overshoot, a pipeline of 3 samples
    reg [7:0] pipe0 = 128, pipe1 = 128, pipe2 = 128; integer noise, d0 = 128, d1 = 128, d2 = 128, v;
    always @(posedge adc_clk_b) begin
        noise = $random % 2;
        d2 = d1; d1 = d0; d0 = dac_a; v = (60 * d0 + 52 * d1 - 12 * d2) / 100;          // the edge over two samples, 12 % overshoot
        v = (76 * v) / 100 + 30 + noise; pipe0 <= v < 0 ? 0 : v > 255 ? 255 : v; pipe1 <= pipe0; pipe2 <= pipe1; adc_in_b <= pipe2;
    end
    // the UART to A (the sequencer lives there)
    real t_sent = 0;
    task send_byte(input [7:0] b); integer i; begin
        if ($realtime - t_sent < BIT) #(BIT - ($realtime - t_sent));
        uart_rx_a = 0; #(BIT); for (i = 0; i < 8; i = i + 1) begin uart_rx_a = b[i]; #(BIT); end
        uart_rx_a = 1; t_sent = $realtime;
    end endtask
    task wr(input [6:0] a, input [31:0] d); begin
        send_byte({1'b1, a}); send_byte(d[7:0]); send_byte(d[15:8]); send_byte(d[23:16]); send_byte(d[31:24]); #(BIT * 1.2);
    end endtask
    integer fo, rec = 0, nf = 0;
    reg [15:0] bad_q = 0; reg [15:0] good_q = 0;
    always @(posedge clkb) begin
        if (B.bad != bad_q) begin $display("  bad burst %0d at %0t: A mode %0d fin %0d fs %0d frames %0d, B fs %0d frames %0d, good %0d", B.bad, $time, A.mode, A.fin, A.fs, A.frames, B.fs, B.frames, B.good); bad_q = B.bad; end
        if (B.good != good_q) good_q = B.good;
    end
    always @(posedge clka) if (rec && A.tick) $fwrite(fo, "%0d %0d\n", dac_a, dac_b);
    always @(posedge clka) if (rec && A.frame_done) begin $fwrite(fo, "F\n"); nf = nf + 1; end
    // the mode mark, as A takes a new mode or finale: that is at the start of a period, after the last one's frames have
    // all reached the DACs (A waits for `drained` before its burst), so every sample after it belongs to the new one
    reg [3:0] mq = 4'hf; reg [4:0] fq = 5'h1f;
    always @(posedge clka) if (rec && (A.mode != mq || A.fin != fq)) begin $fwrite(fo, "M %0d %0d\n", A.mode, A.fin); mq <= A.mode; fq <= A.fin; end
    task frames(input integer n); integer k; begin for (k = 0; k < n; k = k + 1) @(posedge A.frame_done); end endtask
    task mode(input [3:0] m, input [4:0] f, input integer n); begin
        wr(7'h10, {f, 1'b0, m, 4'b0101}); wr(7'h11, 32'd1);
        wait (A.mode == m && (m != 3 || A.fin == f));         // A takes a new mode as its next period starts (the frames repeat between bursts)
        frames(n + 3);                                          // the mode mark is written as A switches (above)
    end endtask
    integer f, k, same, same_new; integer dxa, dxb, dya, dyb; real rate_ppm;
    initial begin
        fo = $fopen("icepi_samples.txt", "w");
        #20000;
        // the twins fast, to fill the rings, but with room between steps (a Lorenz step takes 14 clocks, Chua's 32): steps
        // back to back let B's trimmed tick (an interval of 1 or 3 clocks now and then) drop one, which the next burst, 4 ms
        // on, corrects; on the board a step comes every 623 (Lorenz) and 9766 (Chua) ticks
        wr(7'h1f, 32'd100000);                                  // a burst every 4 ms
        wr(7'h50, {4'd0, 12'd14, 16'd20});
        wr(7'h57, {4'd0, 12'd14, 16'd24}); wr(7'h58, 0);
        B.step_ticks = 16'd20; B.ring_every = 12'd14; B.step_ticks2 = 16'd24; B.ring_every2 = 12'd14;   // the same on B (it has no UART here)
        // then, after the frames below fill the rings, the hardware's regime: a step much longer than the twin's 14 clocks and
        // about one ring point a frame, where a replay out of step with A's would skip points
        wr(7'h14, 32'd60000000); wr(7'h15, 32'd85000000); wr(7'h17, 32'd160000000);
        wr(7'h10, 32'h015); wr(7'h11, 32'd1);
        frames(4);                                              // B locks on
        $display("after 4 frames: B good %0d bad %0d, lo %0d hi %0d, interval %0d clocks, rate %08x, B frames %0d, A frames %0d",
                 B.good, B.bad, B.lo, B.hi, B.interval, B.rate, B.frames, A.frames);
        rec = 1;
        mode(1, 0, 3); mode(2, 0, 3);
        for (f = 0; f < A.xrole.seq.NF; f = f + 1) mode(3, f, 2);
        rec = 0; $fclose(fo);
        A.step_ticks = 16'd2000; A.ring_every = 12'd8; B.step_ticks = 16'd2000; B.ring_every = 12'd8;
        A.step_ticks2 = 16'd2500; A.ring_every2 = 12'd6; B.step_ticks2 = 16'd2500; B.ring_every2 = 12'd6;
        wr(7'h10, {5'd0, 1'b0, 4'd3, 4'b0101}); wr(7'h11, 32'd1);              // the Lorenz finale: short frames
        @(posedge B.sy_valid);                                                 // B takes the new regime's step phase from a burst
        #30_000_000;                                                           // 30 ms: some 47 points of each ring
        same_new = 0; for (k = 1; k <= 40; k = k + 1) begin
            if (A.eng.ring_xy[A.wp - k[10:0]] == B.eng.ring_xy[A.wp - k[10:0]]) same_new = same_new + 1;
            if (A.eng.ring2_xy[A.wp2 - k[10:0]] == B.eng.ring2_xy[A.wp2 - k[10:0]]) same_new = same_new + 1;
        end
        $display("slow-point regime: of the 40 newest points of each ring, %0d of 80 identical on A and B (A wp %0d B wp %0d, A wp2 %0d B wp2 %0d)", same_new, A.wp, B.wp, A.wp2, B.wp2);
        $display("B good %0d bad %0d, rate %08x (nominal 80000000; B's clock is 100 ppm fast, so the trim heads for 7ffcb924), B frames %0d, A frames %0d", B.good, B.bad, B.rate, B.frames, A.frames);
        // the rings: B's must hold A's points in the same slots (B's twin is reloaded from A's at every burst)
        same = 0; for (k = 0; k < 2048; k = k + 1) begin
            dxa = A.eng.ring_xy[k][31:16]; dxb = B.eng.ring_xy[k][31:16]; dya = A.eng.ring_xy[k][15:0]; dyb = B.eng.ring_xy[k][15:0];
            if (dxa - dxb < 64 && dxb - dxa < 64 && dya - dyb < 64 && dyb - dya < 64) same = same + 1;
        end
        $display("rings: A wp %0d B wp %0d, slots that agree to 64/16384: %0d of 2048; A ring[wp-1] %09x B ring[wp-1] %09x", A.wp, B.wp, same, A.eng.ring_xy[A.wp - 11'd1], B.eng.ring_xy[B.wp - 11'd1]);
        rate_ppm = ($itor({1'b0, B.rate}) - 2147483648.0) / 2147483648.0 * 1e6;
        $display("B's rate trim %+.1f ppm (its clock is 100 ppm fast: -100 is right)", rate_ppm);
        $display("%0d frames recorded, %s", nf, (B.good > 10 && B.bad == 0 && same > 1900 && same_new == 80 && rate_ppm > -105.0 && rate_ppm < -95.0) ? "PASS" : "FAIL");
        $finish;
    end
    initial begin #250_000_000; $display("TIMEOUT: B good %0d bad %0d st %0d, A frames %0d", B.good, B.bad, B.yrole.srx.st, A.frames); $finish; end
endmodule
