// filter_core_tb.sv -- filter_core.sv in Icarus Verilog (no hardware):
//     iverilog -g2012 -o filter_core_tb.vvp filter_core_tb.sv filter_core.sv && vvp -n filter_core_tb.vvp
// Drives the sample stream as adda_io does (one sample every two clocks) and checks:
//   1. an impulse through b = [1 2 3 4 5] x 1024: the DAC plays 64 b_k / 8192 = 8, 16, .. 40
//   2. a step through the one-pole y += (x - y) / 4 (b0 = 2048, a1 = -6144): each sample
//      within one code of a floating-point model
//   3. b0 = 8192 (a wire), ADC source: the DAC plays the input 3 samples later; out = 1 too
//   4. enable low: DAC at 128, running 0; high: running after 3 samples
//   5. b0 = 32767 (4.0): a 64 impulse clips to 255, and `clipped` says so
`timescale 1ns/1ps
module filter_core_tb;
    logic clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    // the sample stream, as adda_io makes it
    logic [7:0] adc = 128, sample = 128;
    logic       sample_valid = 0, adc_clk_r = 0;
    always_ff @(posedge clk) begin
        adc_clk_r    <= ~adc_clk_r;
        sample_valid <= 0;
        if (adc_clk_r == 0) begin sample <= adc; sample_valid <= 1; end
    end

    logic [255:0] b_all = 0;
    logic [63:0]  a_all = 0;
    logic [2:0]   src = 0;
    logic         out_in = 0, enable = 0, running, clipped;
    logic [31:0]  tone_word = 32'h0a3d_70a4;
    logic [7:0]   dac;
    filter_core dut (.clk(clk), .sample(sample), .sample_valid(sample_valid),
                     .b_all(b_all), .a_all(a_all), .src(src), .out_in(out_in),
                     .tone_word(tone_word), .enable(enable),
                     .running(running), .clipped(clipped), .dac_value(dac));

    task set_b(input integer k, input integer v); b_all[16*k +: 16] = 16'(v); endtask
    task set_a(input integer k, input integer v); a_all[16*(k-1) +: 16] = 16'(v); endtask
    task clear_coefs; b_all = 0; a_all = 0; endtask

    // one DAC value per sample, taken on the clock the next sample arrives
    integer dlog [0:40000], ilog [0:40000], nlog;
    task log_samples(input integer n);
        nlog = 0;
        repeat (n) begin
            @(posedge clk); while (!sample_valid) @(posedge clk);
            dlog[nlog] = dac; ilog[nlog] = sample; nlog++;
        end
    endtask

    // the same, driving the ADC with a ramp: one process, so there is no race
    task drive_and_log(input integer n);
        nlog = 0;
        repeat (n) begin
            @(posedge clk); while (!sample_valid) @(posedge clk);
            dlog[nlog] = dac; ilog[nlog] = sample; nlog++;
            adc = 100 + nlog;                       // the next sample's value
        end
    endtask
    // by how many samples does the DAC lag the input?  0 = no match
    function integer delay_found();
        integer dd, j, match;
        delay_found = 0;
        for (dd = 1; dd < 8 && delay_found == 0; dd++) begin
            match = 1;
            for (j = 8; j < nlog; j++) if (dlog[j] != ilog[j - dd]) match = 0;
            if (match) delay_found = dd;
        end
    endfunction

    integer errors = 0, i, i0, d, ok, lo, hi;
    real    ym;
    initial begin
        // ---- 1. the impulse through a 5-tap FIR ----
        for (i = 0; i < 5; i++) set_b(i, 1024 * (i + 1));
        src = 1; enable = 1;
        wait (dut.cnt[13:0] == 14'h3ff0);           // just before the period's start
        log_samples(40);
        i0 = -1;
        for (i = 0; i < nlog - 5; i++) if (dlog[i] == 136 && i0 < 0) i0 = i;
        ok = (i0 >= 0);
        for (i = 0; i < 5 && ok; i++) ok = (dlog[i0 + i] == 128 + 8 * (i + 1));
        if (ok) ok = (dlog[i0 + 5] == 128 && dlog[i0 - 1] == 128);
        $display("1. impulse through [1 2 3 4 5] x 1024: DAC %0d %0d %0d %0d %0d %0d (expect 136 144 152 160 168 128): %s",
                 dlog[i0], dlog[i0+1], dlog[i0+2], dlog[i0+3], dlog[i0+4], dlog[i0+5], ok ? "ok" : "WRONG");
        if (!ok) errors++;

        // ---- 2. the step through the one-pole, K = 2 ----
        enable = 0; clear_coefs; set_b(0, 2048); set_a(1, -6144); src = 2;
        #100; enable = 1;
        wait (dut.cnt == 15'h3ff0);                 // the step rises at cnt 2^14
        log_samples(60);
        i0 = -1;
        for (i = 1; i < nlog; i++) if (dlog[i] != 64 && i0 < 0) i0 = i;     // first change from -64
        ok = (i0 > 0) && (dlog[i0 - 1] == 64);
        ym = -64.0;
        for (i = 0; i < 40 && ok; i++) begin
            ym = ym + (64.0 - ym) / 4.0;            // the model: y += (x - y) / 4
            d  = dlog[i0 + i] - 128 - $rtoi($floor(ym + 0.5));
            if (d > 1 || d < -1) begin
                ok = 0;
                $display("   sample %0d after the step: DAC %0d, model %f", i, dlog[i0 + i], ym + 128);
            end
        end
        $display("2. step through y += (x - y)/4: before %0d, then %0d %0d %0d %0d %0d ... (model 96 120 138 152 162), 40 samples within 1 code: %s",
                 dlog[i0-1], dlog[i0], dlog[i0+1], dlog[i0+2], dlog[i0+3], dlog[i0+4], ok ? "ok" : "WRONG");
        if (!ok) errors++;

        // ---- 3. a wire, from the ADC: the DAC is the input, a few samples later, and
        //         out = 1 (the input itself) has the same delay ----
        enable = 0; clear_coefs; set_b(0, 8192); src = 0; #100; enable = 1;
        drive_and_log(24);
        d  = delay_found();
        i0 = d;
        $display("3. b0 = 8192, ADC source: DAC = the input delayed %0d sample periods: %s", d, d > 0 ? "ok" : "WRONG");
        if (d <= 0) errors++;
        out_in = 1;
        drive_and_log(24);
        d = delay_found();
        $display("   out = 1 (the input): delayed %0d sample periods (expect the same, %0d): %s", d, i0, d == i0 ? "ok" : "WRONG");
        if (d != i0) errors++;
        out_in = 0; adc = 128;

        // ---- 4. enable ----
        enable = 0;
        log_samples(4);
        ok = (dlog[3] == 128) && !running;
        $display("4. enable 0: DAC %0d (expect 128), running %0d (expect 0): %s", dlog[3], running, ok ? "ok" : "WRONG");
        if (!ok) errors++;
        enable = 1;
        log_samples(2);
        ok = !running;
        log_samples(2);
        ok = ok && running;
        $display("   enable 1: running after 3 samples, not after 2: %s", ok ? "ok" : "WRONG");
        if (!ok) errors++;

        // ---- 5. clipping ----
        enable = 0; clear_coefs; set_b(0, 32767); src = 1; #100; enable = 1;
        ok = !clipped;
        wait (dut.cnt[13:0] == 14'h3ff0);
        log_samples(40);
        lo = 255; hi = 0;
        for (i = 0; i < nlog; i++) begin if (dlog[i] < lo) lo = dlog[i]; if (dlog[i] > hi) hi = dlog[i]; end
        ok = ok && (hi == 255) && clipped;
        $display("5. b0 = 32767 (4.0), the 64 impulse: DAC up to %0d (expect 255), clipped %0d (expect 1): %s", hi, clipped, ok ? "ok" : "WRONG");
        if (!ok) errors++;

        // ---- 6. filter.py's selftest numbers: the one-pole b0 = 819, a1 = -7373 on the step ----
        enable = 0; clear_coefs; set_b(0, 819); set_a(1, -7373); src = 2; #100; enable = 1;
        wait (dut.cnt == 15'h3ff0);
        log_samples(70);
        i0 = -1;
        for (i = 1; i < nlog; i++) if (dlog[i] != dlog[i-1] && i0 < 0) i0 = i;
        ok = (i0 > 0);
        begin : selftest
            integer want_k [0:13], want_y [0:13];
            want_k[0]=0; want_k[1]=1; want_k[2]=2; want_k[3]=3; want_k[4]=4; want_k[5]=5; want_k[6]=6;
            want_k[7]=7; want_k[8]=12; want_k[9]=20; want_k[10]=28; want_k[11]=36; want_k[12]=44; want_k[13]=52;
            want_y[0]=-51; want_y[1]=-40; want_y[2]=-29; want_y[3]=-20; want_y[4]=-12; want_y[5]=-4; want_y[6]=3;
            want_y[7]=9; want_y[8]=31; want_y[9]=50; want_y[10]=58; want_y[11]=61; want_y[12]=63; want_y[13]=64;
            for (i = 0; i < 14 && ok; i++)
                if (dlog[i0 + want_k[i]] != 128 + want_y[i]) begin
                    ok = 0;
                    $display("   sample %0d after the step: DAC %0d, filter.py says %0d", want_k[i], dlog[i0 + want_k[i]], 128 + want_y[i]);
                end
        end
        $display("6. the one-pole a1 = -0.9, b0 = 0.1 on the step: %0d %0d %0d %0d ... (filter.py's selftest: -51 -40 -29 -20 ...), 14 samples exact: %s",
                 dlog[i0] - 128, dlog[i0+1] - 128, dlog[i0+2] - 128, dlog[i0+3] - 128, ok ? "ok" : "WRONG");
        if (!ok) errors++;

        // ---- 7. a trace for filter.py's simulate(): the low-pass preset plus a Butterworth's
        //         feedback taps, on the noise, from a period's start: filter_core_trace.txt ----
        enable = 0; clear_coefs;
        set_b(0, -12); set_b(1, 8); set_b(2, 87); set_b(3, 289); set_b(4, 625); set_b(5, 1020); set_b(6, 1344);
        set_b(7, 1470); set_b(8, 1344); set_b(9, 1020); set_b(10, 625); set_b(11, 289); set_b(12, 87); set_b(13, 8); set_b(14, -12);
        set_a(1, -10709); set_a(2, 4029);
        src = 3;
        wait (dut.cnt[13:0] == 14'h3fff);           // the next sample re-seeds the noise...
        @(posedge clk); while (!sample_valid) @(posedge clk);
        enable = 1;                                 // ...and the filter starts, from a zero state,
        begin : trace                               // on noise_sequence()'s first value
            integer fd;
            fd = $fopen("filter_core_trace.txt", "w");
            repeat (3000) begin
                @(posedge clk); while (!sample_valid) @(posedge clk);
                $fwrite(fd, "%0d %0d\n", $signed(dut.u), dac);   // this sample's input; the DAC now
            end
            $fclose(fd);
        end
        $display("7. 3000 samples of the low-pass + Butterworth feedback on the noise written to filter_core_trace.txt");

        $display("");
        if (errors == 0) $display("PASS");
        else             $display("FAIL: %0d checks failed", errors);
        $finish;
    end
endmodule
