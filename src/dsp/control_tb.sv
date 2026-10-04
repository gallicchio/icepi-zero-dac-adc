// control_tb.sv -- simulate control.sv with no hardware at all.
//
// The testbench plays the laptop (commands in on uart_rx at 1 Mbaud, the capture's bytes
// decoded back off uart_tx) and the analog world (an ADC word that appears 25 ns after each
// rising edge of adc_clk, as the AD9280's does).  It runs the loop through:
//   A  mode 0, Kp = 1: the ADC word jumps and the DAC word answers; the clocks between
//      them are the gateware's latency (expect 40 ns edge to edge, 55 ns pin to pin);
//   B  mode 1 (lag, 16 samples), a PI loop stepping 0 -> 40 -> 0: it must settle;
//   C  anti-windup: a setpoint of 400 the plant can never reach pins the DAC at 255; the
//      integrator must stop, and when the setpoint returns the DAC must come off the rail
//      within a few samples, not after unwinding a huge sum;
//   D  a capture, 128 samples of (setpoint, y) with the step at sample 64, over the UART;
//   E  mode 2 (a 100 kHz resonator), open loop: the step rings, first peak near 5 us;
//   F  mode 2, closed with a small PI;  G  mode 1 again with 5 extra samples of delay.
// Every sample of all of it goes to control_tb_trace.txt, which
//   python3 control_model.py --check control_tb_trace.txt
// replays through the Python model and compares bit for bit (e, u, y, DAC).
//
//   make sim-control
//   (or: iverilog -g2012 -o control_tb.vvp control_tb.sv control.sv ../verilog/uart.sv && vvp control_tb.vvp)
`timescale 1ns/1ps
module control_tb;
    logic clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    logic [7:0] dac, adc = 128;
    logic       dac_clk, adc_clk, tx;
    logic       rx = 1;
    logic [4:0] led;

    // a short capture (128 samples: 64 before the step, 64 after) keeps the dump quick
    control #(.LOGN(7), .LOGPRE(6)) dut (.clk(clk), .uart_rx(rx), .uart_tx(tx), .dac_d(dac),
                                         .dac_clk(dac_clk), .adc_d(adc), .adc_clk(adc_clk), .led(led));

    // ---- the analog world: the ADC's word, 25 ns after each rising edge of its clock ------
    logic [7:0] adc_val = 128;
    always @(posedge adc_clk) adc <= #25 adc_val;

    // ---- the laptop: commands at 1 Mbaud (1 us a bit) ----------------------------------
    task automatic send(input logic [7:0] c);
        rx = 0; #1000;                              // start bit
        for (int b = 0; b < 8; b++) begin rx = c[b]; #1000; end
        rx = 1; #1000;                              // stop bit
    endtask
    task automatic cmd1(input logic [7:0] c, input logic [7:0] v);
        send(c); send(v);
    endtask
    task automatic cmd2(input logic [7:0] c, input logic signed [15:0] v);
        send(c); send(v[15:8]); send(v[7:0]);
    endtask
    task automatic wait_samples(input int n);
        repeat (n) @(posedge dut.step);
    endtask

    // ...and the bytes coming back
    logic [7:0] rxbuf [0:1023];
    int         nrx = 0;
    logic [7:0] c;
    always @(negedge tx) begin                      // a start bit has begun
        #1500;                                      // the middle of data bit 0
        for (int b = 0; b < 8; b++) begin c[b] = tx; #1000; end
        rxbuf[nrx] = c;
        nrx = nrx + 1;
    end

    // ---- the trace: every sample, with the settings as the two edges saw them -------------
    int f;
    int nsamp = 0;
    logic signed [15:0] kp1, ki1, kd1;
    logic [15:0] rword1;
    logic        en1, mode1a, mode1b;
    logic [3:0]  klag1, qshift1;
    logic [5:0]  ldelay1;
    logic [7:0]  dac_next;
    always @(posedge clk)
        if (dut.new_sample) begin                   // edge 1: what the products used
            kp1 = dut.kp; ki1 = dut.ki; kd1 = dut.kd; en1 = dut.enable;
            {mode1b, mode1a} = dut.mode; klag1 = dut.klag; rword1 = dut.rword;
            qshift1 = dut.qshift; ldelay1 = dut.ldelay;
        end
    always @(posedge clk)
        if (dut.step) begin                         // edge 2: the output and the state update
            dac_next = (dut.mode != 0 && dut.osel) ? dut.y_dac : dut.dac_sat;
            $fwrite(f, "%0d %0d %0d %0d %0d %0d %0d | %0d %0d %0d %0d %0d %0d %0d %0d %0d | %0d %0d %0d %0d\n",
                    nsamp, dut.sp, dut.x, dut.e_r, dut.u_out, dut.y_int, dac_next,
                    kp1, ki1, kd1, en1, {mode1b, mode1a}, klag1, rword1, qshift1, ldelay1,
                    dut.enable, dut.bias, dut.mode, dut.osel);
            nsamp = nsamp + 1;
        end

    // ---- timing marks for the latency measurement ----------------------------------------
    time t_pin = 0, t_x = 0, t_dac = 0;
    always @(adc)   t_pin = $time;
    always @(dut.x) t_x   = $time;
    always @(dac)   t_dac = $time;

    // ---- the run --------------------------------------------------------------------------
    int errors = 0;
    int k, i0, imax;
    logic signed [15:0] wa [0:127], wb [0:127];
    logic signed [12:0] ytrace [0:511];
    int ymax, iymax;

    // the '?' frame: 32 bytes, checked against the registers
    task automatic check_status(input logic signed [15:0] kp_e, input logic [1:0] mode_e,
                                input logic [3:0] klag_e, input logic [5:0] ldelay_e);
        nrx = 0;
        send("?");
        wait (nrx == 32);
        if (rxbuf[0] != 8'hA5 || $signed({rxbuf[1], rxbuf[2]}) != kp_e || rxbuf[18] != mode_e ||
            rxbuf[16] != klag_e || rxbuf[21] != ldelay_e) begin
            $display("?: bad frame: %02x kp %0d mode %0d klag %0d ldelay %0d", rxbuf[0],
                     $signed({rxbuf[1], rxbuf[2]}), rxbuf[18], rxbuf[16], rxbuf[21]);
            errors++;
        end else
            $display("?: 32 bytes: kp %0d ki %0d kd %0d S %0d J %0d N %0d T %0d mode %0d K %0d L %0d E %0d | x %0d e %0d u %0d y %0d",
                     $signed({rxbuf[1], rxbuf[2]}), $signed({rxbuf[3], rxbuf[4]}), $signed({rxbuf[5], rxbuf[6]}),
                     $signed({rxbuf[7], rxbuf[8]}), $signed({rxbuf[9], rxbuf[10]}), rxbuf[13], rxbuf[14], rxbuf[18],
                     rxbuf[16], rxbuf[21], rxbuf[20], $signed({rxbuf[24], rxbuf[25]}), $signed({rxbuf[26], rxbuf[27]}),
                     $signed({rxbuf[28], rxbuf[29]}), $signed({rxbuf[30], rxbuf[31]}));
    endtask

    initial begin
        f = $fopen("control_tb_trace.txt", "w");
        #2000;

        // ---- the junk byte: a lone "P" (as the FT231X might emit on opening), then 2 ms of
        //      silence; the parser must forget it, so the "P" 1024 below still lands
        send("P");
        #2_000_000;

        // ---- A: latency, mode 0, Kp = 1 ------------------------------------------------
        cmd2("P", 16'd1024); cmd2("I", 0); cmd2("D", 0); cmd2("S", 0);
        cmd1("M", 0); cmd1("E", 1);
        check_status(16'd1024, 2'd0, 4'd4, 6'd0);
        wait_samples(20);
        if (dac != 128) begin $display("A: DAC should rest at 128, is %0d", dac); errors++; end
        @(posedge dut.step); #5;
        adc_val = 138;                              // x = +10, so e = -10 and u = -10
        wait_samples(6);
        if (dac != 118) begin $display("A: DAC should answer 118, is %0d", dac); errors++; end
        $display("A: ADC word 128 -> 138 at the pins at %0t ns; registered at %0t ns; DAC word 128 -> %0d at %0t ns",
                 t_pin, t_x, dac, t_dac);
        $display("   latency: %0d ns = %0d clocks from the sampling edge to the DAC word; %0d ns pin to pin%s",
                 t_dac - t_x, (t_dac - t_x) / 20, t_dac - t_pin,
                 (t_dac - t_x == 40) ? "" : "   <-- expected 40");
        if (t_dac - t_x != 40) errors++;
        adc_val = 128;
        wait_samples(10);

        // ---- B: mode 1, PI, stepping 0 -> 40 -> 0 every 512 samples -----------------------
        cmd1("M", 1); cmd1("K", 4); cmd1("L", 0);
        cmd2("P", 16'd1024); cmd2("I", 16'd1311);       // Kp = 1.0, Ki = 0.02 per sample
        cmd2("J", 16'd40); cmd1("N", 9); cmd1("T", 1);
        check_status(16'd1024, 2'd1, 4'd4, 6'd0);
        @(posedge dut.sp[5]);                           // the setpoint just became 40
        wait_samples(400);
        $display("B: 400 samples after the step to 40: y = %0d, e = %0d, u = %0d", dut.y_int, dut.e_r, dut.u);
        if (dut.e_r > 2 || dut.e_r < -2) begin $display("B: should have settled (|e| <= 2)"); errors++; end
        @(negedge dut.sp[5]);
        wait_samples(400);
        $display("B: 400 samples after the step back to 0: y = %0d, e = %0d", dut.y_int, dut.e_r);
        if (dut.e_r > 2 || dut.e_r < -2) begin $display("B: should have settled (|e| <= 2)"); errors++; end

        // ---- C: anti-windup ----------------------------------------------------------------
        cmd1("T", 0); cmd2("S", 16'd400);               // unreachable: the plant tops out at 127
        wait_samples(600);
        $display("C: 600 samples at an unreachable setpoint: DAC = %0d, u = %0d, y = %0d, integrator = %0d",
                 dac, dut.u, dut.y_int, dut.integ);
        if (dac != 255) begin $display("C: the DAC should be pinned at 255"); errors++; end
        if (dut.integ > 10000) begin $display("C: the integrator wound up (%0d)", dut.integ); errors++; end
        cmd2("S", 0);
        wait_samples(4);
        $display("C: 4 samples after the setpoint returned: DAC = %0d, u = %0d, integrator = %0d", dac, dut.u, dut.integ);
        if (dut.u > 100) begin $display("C: the DAC should have left the rail at once"); errors++; end
        wait_samples(400);

        // ---- D: a capture of (setpoint, y), the step at sample 64 ---------------------------
        cmd1("T", 1); cmd1("V", 8'h14); cmd1("X", 0);
        nrx = 0;
        send("C");
        wait (nrx == 512);
        for (k = 0; k < 128; k++) begin
            wa[k] = {rxbuf[4 * k], rxbuf[4 * k + 1]};
            wb[k] = {rxbuf[4 * k + 2], rxbuf[4 * k + 3]};
        end
        $display("D: 512 bytes back.  setpoint at samples 62..65: %0d %0d %0d %0d;  y at 64, 70, 100, 127: %0d %0d %0d %0d",
                 wa[62], wa[63], wa[64], wa[65], wb[64], wb[70], wb[100], wb[127]);
        for (k = 0; k < 128; k++)
            if (wa[k] != ((k < 64) ? 0 : 40)) begin
                $display("D: the step is not at sample 64 (sample %0d reads %0d)", k, wa[k]); errors++; k = 128;
            end
        if (!(wb[70] > wb[64] && wb[127] >= 25 && wb[127] <= 35)) begin
            $display("D: y does not look like the lag's step response"); errors++;
        end

        // ---- E: the resonator, open loop ---------------------------------------------------
        // Q = 25.7 rings down over 2^10 samples, so give it 2^13 between steps: it starts
        // each step from rest, as the model's prediction (77 at sample 119) assumes.
        cmd1("E", 0); cmd1("M", 2); cmd2("R", 16'd662); cmd1("Q", 10); cmd1("N", 13);
        @(posedge dut.sp[5]);
        @(posedge dut.sp[5]);
        for (k = 0; k < 400; k++) begin @(posedge dut.step); ytrace[k] = dut.y_int; end
        ymax = -9999; iymax = 0;
        for (k = 0; k < 400; k++) if (ytrace[k] > ymax) begin ymax = ytrace[k]; iymax = k; end
        $display("E: 100 kHz resonator, open-loop step 0 -> 40: first peak y = %0d at sample %0d (%0.2f us)",
                 ymax, iymax, iymax * 0.04);
        if (iymax < 110 || iymax > 130 || ymax < 70 || ymax > 85) begin
            $display("E: expected the peak near sample 119 (half a period) at about 77 (Q = 25.7)"); errors++;
        end

        // ---- F: the resonator, closed with PID: the D term is the damping it lacks -----------
        cmd2("P", 16'd512); cmd2("I", 16'd328); cmd2("D", 16'd4096); cmd1("E", 1);   // 0.5, 0.005, 16
        @(posedge dut.sp[5]);
        wait_samples(1000);
        $display("F: resonator under PID (Kd = 16 damps it), 1000 samples after a step: y = %0d, e = %0d",
                 dut.y_int, dut.e_r);
        if (dut.e_r > 5 || dut.e_r < -5) begin $display("F: should have settled (|e| <= 5)"); errors++; end

        // ---- G: the lag with 5 extra samples of delay, P only, ringing -------------------------
        cmd1("M", 1); cmd1("L", 5); cmd2("P", 16'd2048); cmd2("I", 0); cmd1("N", 9);
        @(posedge dut.sp[5]);
        wait_samples(300);
        $display("G: lag + 5 samples of delay, Kp = 2: 300 samples after a step y = %0d (P only leaves an offset)", dut.y_int);
        wait_samples(300);

        $fclose(f);
        $display("%0d samples traced to control_tb_trace.txt; %0d error(s)", nsamp, errors);
        $finish;
    end
endmodule
