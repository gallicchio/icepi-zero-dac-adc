// filter_tb.sv -- simulate filter.sv with no hardware at all.
//
// The testbench plays the laptop (bytes at 1 Mbaud on uart_rx; the capture's bytes read
// back off uart_tx) and watches the DAC once per ADC sample.  The fake ADC is a ramp.
//   1. A 5-tap FIR loaded over the UART and the impulse source: the DAC must play the taps.
//   2. A one-pole, a_1 = -0.9 and b_0 = 0.1, and the step source: the DAC must follow the
//      integer arithmetic of filter.sv exactly (the model is a few lines below) and the
//      ideal RC, 64 - 128 x 0.9^(n+1), within one code.
//   3. b_0 = 3.9999 with the step: the output saturates at 0 and 255; 'O' 1 shows the input.
//   4. The tone and the noise sources, through 'O' 1: the right amplitudes.
//   5. 'C': the bytes come back, starting at the stimulus period's start, from the re-seeded
//      noise generator, and in capture.sv's format (1 byte per sample).
//
//   make sim-filter
`timescale 1ns/1ps
module filter_tb;
    logic clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    logic [7:0] dac, adc = 128;
    logic       dac_clk, adc_clk, tx;
    logic       rx = 1;
    logic [4:0] led;
    always @(posedge adc_clk) adc <= #25 adc + 1;   // a ramp, 25 ns late like the real ADC

    filter dut (.clk(clk), .uart_rx(rx), .uart_tx(tx), .dac_d(dac), .dac_clk(dac_clk),
                .adc_d(adc), .adc_clk(adc_clk), .led(led));

    // ---- the laptop: bytes at 1 Mbaud (1 us a bit) --------------------------------------
    task automatic send(input logic [7:0] c);
        rx = 0; #1000;
        for (int b = 0; b < 8; b++) begin rx = c[b]; #1000; end
        rx = 1; #1000;
    endtask
    task automatic coef(input logic [7:0] which, input int k, input int v);   // 'B' or 'A'
        send(which); send(8'(k)); send(8'(v >>> 8)); send(8'(v));
    endtask
    task automatic clear_taps();
        for (int k = 0; k < 16; k++) coef("B", k, 0);
        for (int k = 1; k <= 4; k++) coef("A", k, 0);
    endtask

    // ...and listen: every byte off uart_tx
    logic [7:0] cap [0:16383];
    int         ncap = 0;
    logic [7:0] c;
    always @(negedge tx) begin
        #1500;
        for (int b = 0; b < 8; b++) begin c[b] = tx; #1000; end
        if (ncap < 16384) cap[ncap] = c;
        ncap++;
    end

    // ---- the DAC, once per sample ----------------------------------------------------------
    int dlog [0:1023];
    task automatic wait_cnt(input int value);     // until the sample whose cnt is `value` arrives
        do @(posedge clk); while (!(dut.new_sample && dut.cnt == 15'(value)));
    endtask
    task automatic log_dac(input int n);          // the next n samples' DAC codes
        for (int i = 0; i < n; i++) begin
            do @(posedge clk); while (!dut.new_sample);
            dlog[i] = dac;
        end
    endtask
    function automatic int first_change(input int n, input int idle);
        for (int i = 0; i < n; i++) if (dlog[i] != idle) return i;
        return -1;
    endfunction

    // ---- the integer model of filter.sv, for the one-pole: w is y in Q10.8 -------------
    function automatic longint sat18(input longint v);
        return (v > 131071) ? 131071 : (v < -131072) ? -131072 : v;
    endfunction
    function automatic int to_dac(input longint w);       // rounded, clipped, + 128
        longint y = (w + 128) >>> 8;
        return (y > 127) ? 255 : (y < -128) ? 0 : int'(y) + 128;
    endfunction

    // ---- the script -------------------------------------------------------------------------
    localparam int LAT = 4;                       // 3 samples of filter + the DAC register, as logged
    int errors = 0, i0, n, lo, hi, distinct, errs;
    int taps [0:4] = '{3, -5, 7, 11, -2};
    longint w;
    int model [0:63];
    real ideal;
    int seen [0:255];
    initial begin
        #5000;
        // ---- 1. the 5-tap FIR and the impulse ----
        clear_taps();
        for (int k = 0; k < 5; k++) coef("B", k, taps[k] * 128);     // x 128: an impulse of 64 gives the tap
        send("S"); send(8'd1);
        send("O"); send(8'd0);
        wait_cnt(16'h3fff);                       // the impulse is the next sample
        log_dac(16);
        i0 = first_change(16, 128);
        $write("1. impulse through [3 -5 7 11 -2]: DAC - 128 =");
        for (int i = 0; i < 16; i++) $write(" %0d", dlog[i] - 128);
        $display("   (first change at sample %0d)", i0);
        errs = 0;
        if (i0 != LAT) errs++;
        for (int i = 0; i < 16; i++)
            if (dlog[i] - 128 != ((i >= LAT && i < LAT + 5) ? taps[i - LAT] : 0)) errs++;
        if (errs == 0) $display("   ok: the taps, 3 samples after the impulse");
        else           $display("   FAIL: %0d mismatches", errs);
        errors += errs;

        // ---- 2. the one-pole and the step ----
        clear_taps();
        coef("B", 0, 819);                        // 0.1 x 8192
        coef("A", 1, -7373);                      // -0.9 x 8192
        send("S"); send(8'd2);
        wait_cnt(16'h7fff);                       // a whole half period at -64 comes next...
        wait_cnt(16'h3fff);                       // ...and then the rising edge
        log_dac(64);
        w = 0;
        repeat (16384) w = sat18((819 * (-64) * 256 - (-7373) * w) >>> 13);
        for (int i = 0; i < 64; i++) begin
            w = sat18((819 * 64 * 256 - (-7373) * w) >>> 13);
            model[i] = to_dac(w);                 // the DAC, 3 samples after input i
        end
        i0 = first_change(64, dlog[0]);
        $display("2. step -64 -> +64 through the one-pole a1 = -0.9, b0 = 0.1 (first change at sample %0d):", i0);
        $display("   n     DAC  model  ideal");
        errs = 0;
        for (int i = 0; i < 64; i++) begin
            ideal = (i < LAT) ? -64.0 : 64.0 - 128.0 * (0.9 ** (i - LAT + 1));
            n     = (i < LAT) ? 64 : model[i - LAT];          // the model's DAC code
            if (i < 12 || i % 8 == 0)
                $display("  %2d  %6d  %5d  %6.1f", i, dlog[i] - 128, n - 128, ideal);
            if (dlog[i] != n) errs++;
            if (dlog[i] - 128 > ideal + 1.0 || dlog[i] - 128 < ideal - 1.0) errs++;
        end
        if (errs == 0) $display("   ok: bit-exact with the integer model, within a code of the RC");
        else           $display("   FAIL: %0d mismatches", errs);
        errors += errs;

        // ---- 3. saturation ----
        clear_taps();
        coef("B", 0, 32767);                      // 3.9999
        send("S"); send(8'd2);
        wait_cnt(16'h3ff0);
        log_dac(32);                              // spans the rising edge
        lo = 255; hi = 0;
        for (int i = 0; i < 32; i++) begin if (dlog[i] < lo) lo = dlog[i]; if (dlog[i] > hi) hi = dlog[i]; end
        $display("3. b0 = 3.9999, step +-64: DAC from %0d to %0d, clip LED %0d", lo, hi, led[4]);
        if (lo != 0 || hi != 255 || !led[4]) errors++;
        send("O"); send(8'd1);
        wait_cnt(16'h3ff0);
        log_dac(32);
        lo = 255; hi = 0;
        for (int i = 0; i < 32; i++) begin if (dlog[i] < lo) lo = dlog[i]; if (dlog[i] > hi) hi = dlog[i]; end
        $display("   'O' 1, the input: DAC from %0d to %0d (expect 64 to 192)", lo, hi);
        if (lo != 64 || hi != 192) errors++;

        // ---- 4. the tone and the noise, through 'O' 1 ----
        send("F"); send(8'h0a); send(8'h3d); send(8'h70); send(8'ha4);   // 1 MHz
        send("S"); send(8'd4);
        #10000;
        log_dac(100);                             // four cycles
        lo = 255; hi = 0;
        for (int i = 0; i < 100; i++) begin if (dlog[i] < lo) lo = dlog[i]; if (dlog[i] > hi) hi = dlog[i]; end
        $display("4. tone at 1 MHz: DAC from %0d to %0d (expect 64 to 192)", lo, hi);
        if (lo > 66 || hi < 190) errors++;
        send("S"); send(8'd3);
        #10000;
        for (int i = 0; i < 256; i++) seen[i] = 0;
        log_dac(1000);
        lo = 255; hi = 0; distinct = 0;
        for (int i = 0; i < 1000; i++) begin
            if (dlog[i] < lo) lo = dlog[i];
            if (dlog[i] > hi) hi = dlog[i];
            if (!seen[dlog[i]]) begin seen[dlog[i]] = 1; distinct++; end
        end
        $display("   noise: DAC from %0d to %0d, %0d distinct values in 1000 samples (expect 96..159, > 30)", lo, hi, distinct);
        if (lo < 96 || hi > 159 || distinct < 30) errors++;

        // ---- 5. the capture ----
        send("S"); send(8'd1);
        send("O"); send(8'd0);
        ncap = 0;
        send("C");
        do @(posedge clk); while (!(dut.state == dut.RECORD && dut.new_sample && dut.addr == 0));
        $display("5. 'C': recording starts at cnt %0d with the noise generator at %08x (seed %08x); the ADC reads %0d",
                 dut.cnt, dut.r, dut.SEED, dut.x + 128);
        if (dut.cnt[13:0] != 0 || dut.r != dut.SEED) errors++;
        i0 = dut.x + 128;
        #(300 * 10_000 + 700_000);                // the recording, then 300 bytes at 10 us each
        errs = 0;
        for (int i = 1; i < ncap && i < 300; i++) if (cap[i] != 8'(cap[i-1] + 1)) errs++;
        $display("   %0d bytes so far (of 16384; the first %0d checked): first = %0d (the ADC read %0d), %0d not one more than the one before",
                 ncap, (ncap < 300) ? ncap : 300, cap[0], i0, errs);
        if (ncap < 250 || cap[0] != 8'(i0) || errs != 0 || dut.state != dut.SEND) errors++;

        $display("");
        if (errors == 0) $display("PASS");
        else             $display("FAIL: %0d checks failed", errors);
        $finish;
    end
endmodule
