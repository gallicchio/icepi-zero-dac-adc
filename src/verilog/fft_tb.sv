// fft_tb.sv -- simulate fft.sv with no hardware at all.
//
// A fake ADC plays a test signal from a file; the testbench plays the laptop:
// it sends the command, then decodes the 2048 bytes that come back on uart_tx.
// fft_check.py writes the test signals, runs this, and compares the answers
// with numpy's FFT of the very same samples.
//
//   make sim-fft            the built-in test: a sine at exactly frequency k = 100
//   python3 fft_check.py    all the tests
//   (or: iverilog -g2012 -o fft_tb.vvp fft_tb.sv fft.sv uart.sv && vvp fft_tb.vvp +in=...)
//
// Options, after the .vvp file (fft_check.py uses them all):
//   +in=FILE     ADC codes, one hex byte per line, at 25 MS/s (repeats at the end)
//   +cmd=TEXT    the characters to send (default "00": D = 0, A = 0)
//   +out=FILE    write the 2048 bytes received, one hex byte per line
//   +kept=FILE   write each sample the design kept: its code, and its line in +in
//   +ms=T        give up after T ms of simulated time (default 50)
`timescale 1ns/1ps
module fft_tb;
    logic clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    logic [7:0] adc = 128;
    logic       adc_clk, tx;
    logic       rx = 1;
    logic [4:0] led;

    fft dut (.clk(clk), .adc_d(adc), .adc_clk(adc_clk),
             .uart_rx(rx), .uart_tx(tx), .led(led));

    // ---- the test signal, and the fake ADC that plays it ------------------------
    logic [7:0] codes [0:(1 << 20) - 1];
    int         len = 0, idx = 0, adc_idx = 0, sample_idx = 0;
    string      in_file, out_file, kept_file, cmd = "00";
    int         fd, v, fo = 0, fk = 0, ms = 50;

    // ##########################################################################
    // ##  KEY LINES: on each rising edge of adc_clk, the next code of the test
    // ##  signal appears on the ADC's pins, 25 ns late like the real AD9280.
    // ##########################################################################
    always @(posedge adc_clk) begin
        adc     <= #25 codes[idx];
        adc_idx <= #25 idx;
        idx      = (idx + 1) % len;
    end

    // Write down every sample the design keeps (`keep` in fft.sv), and which
    // line of the test signal it was, so Python can FFT exactly the same ones.
    // (sample_idx follows the design's `sample <= adc_d`.)
    always @(posedge clk) begin
        if (dut.keep && fk)
            $fwrite(fk, "%02x %0d\n", dut.sample, sample_idx);
        if (dut.adc_clk_r == 0)
            sample_idx <= adc_idx;
    end

    // fft.sv promises Yosys (no_rw_check) never to read a RAM address in the
    // same clock as it's written, when the data read matters.  Check that.
    int collisions = 0;
    always @(posedge clk) begin
        if (dut.we && dut.waddr == dut.raddr && (dut.state == 2 || dut.state == 3))
            collisions++;                               // in FFT or POWER
        if (dut.acc_we && dut.acc_waddr == dut.k)
            collisions++;
    end

    // ---- play the laptop: send characters at 1 Mbaud (1 us per bit) -------------
    task automatic send(input logic [7:0] c);
        rx = 0; #1000;                                  // start bit
        for (int b = 0; b < 8; b++) begin rx = c[b]; #1000; end
        rx = 1; #1000;                                  // stop bit
    endtask

    // ...and listen: receive each byte, as uart_rx in uart.sv does
    logic [7:0]  c;
    logic [31:0] P [0:511];
    int          nbytes = 0, errors = 0;
    always @(negedge tx) begin                          // a start bit has begun
        #1500;                                          // to the middle of data bit 0
        for (int b = 0; b < 8; b++) begin c[b] = tx; #1000; end
        if (tx !== 1) errors++;                         // no stop bit?
        if (fo) $fwrite(fo, "%02x\n", c);
        P[nbytes / 4][8 * (nbytes % 4) +: 8] = c;       // least significant byte first
        nbytes++;
        if (nbytes == 2048) begin
            $display("%t ns  received 2048 bytes (%0d framing errors, %0d RAM collisions)",
                     $time / 1000, errors, collisions);
            if (!fo) report();
            $finish;
        end
    end

    // For the built-in test: print the five biggest P[k], in dB re full scale.
    task automatic report();
        int best;
        for (int r = 0; r < 5; r++) begin
            best = 0;
            for (int k = 1; k < 512; k++)
                if (P[k] > P[best]) best = k;
            $display("  P[%0d] = %0d  = %.2f dB re full scale", best, P[best],
                     10.0 * $log10(P[best] / 1073741824.0));
            P[best] = 0;
        end
        $display("expect P[100] near 2^30 * (100/128)^2 = 655360000 (-2.14 dB), and");
        $display("P[99], P[101] a quarter of that (-6 dB more): a Hann window's main lobe");
    endtask

    initial begin
        if ($value$plusargs("in=%s", in_file)) begin
            fd = $fopen(in_file, "r");
            if (fd == 0) begin $display("can't open %0s", in_file); $finish; end
            while ($fscanf(fd, "%h", v) == 1) begin codes[len] = v; len++; end
            $fclose(fd);
        end else                                        // 100 cycles in 1024 samples
            for (len = 0; len < 1024; len++)
                codes[len] = $rtoi($floor(128.0 + 100.0 * $sin(6.283185307179586 * 100 * len / 1024) + 0.5));
        void'($value$plusargs("cmd=%s", cmd));
        void'($value$plusargs("ms=%d", ms));
        if ($value$plusargs("out=%s", out_file))  fo = $fopen(out_file, "w");
        if ($value$plusargs("kept=%s", kept_file)) fk = $fopen(kept_file, "w");

        #5000;
        for (int i = 0; i < cmd.len(); i++)
            send(cmd[i]);
        #(ms * 1_000_000);
        $display("timeout: only %0d of 2048 bytes after %0d ms", nbytes, ms);
        $finish;
    end
endmodule
