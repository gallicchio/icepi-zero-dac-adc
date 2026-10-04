// control_gl_tb.sv -- control.sv, or the netlist Yosys made of it, driven through its pins
// only by the exact bytes control.py sends, so that what the laptop does can be replayed
// against the RTL and against the synthesized gates and the two compared line for line.
//
// The script (control.py --dump-bytes FILE) has one token per line:
//   b HH   send this byte, back to back with the one before
//   g      a gap between two writes (as the USB has): 100 samples; prints the DAC word
//   w N    wait N samples, then print the DAC word
//   c      a capture's reply is due: wait for 4 x 2^LOGN bytes, print a few of its words
// The ADC reads 127 throughout (W1 at 0 V: x = -1), as on the M2k bench.
//
//   RTL:   iverilog -g2012 -o control_gl_rtl.vvp control_gl_tb.sv control.sv ../verilog/uart.sv
//          vvp -n control_gl_rtl.vvp +script=control_script.txt
//   gates: yosys -q -p "read_verilog -sv control.sv ../verilog/uart.sv; chparam -set LOGN 7 control;
//                       synth_ecp5 -top control; write_verilog -noattr control_gl.v"
//          iverilog -g2012 -DGATES -o control_gl_gates.vvp control_gl_tb.sv control_gl.v \
//                   $(yosys-config --datdir)/ecp5/cells_sim.v mult18x18d_sim.v
//          vvp -n control_gl_gates.vvp +script=control_script.txt
//   (make sim-control-gl does both and diffs the two logs)
`timescale 1ns/1ps
module control_gl_tb;
    localparam integer LOGN = 7;
    logic clk = 0;
    always #10 clk = ~clk;

    logic [7:0] dac, adc = 127;
    logic       dac_clk, adc_clk, tx;
    logic       rx = 1;
    logic [4:0] led;
`ifdef GATES
    control dut (.clk(clk), .uart_rx(rx), .uart_tx(tx), .dac_d(dac), .dac_clk(dac_clk),
                 .adc_d(adc), .adc_clk(adc_clk), .led(led));
`else
    control #(.LOGN(LOGN), .LOGPRE(6)) dut (.clk(clk), .uart_rx(rx), .uart_tx(tx), .dac_d(dac),
                                            .dac_clk(dac_clk), .adc_d(adc), .adc_clk(adc_clk), .led(led));
`endif

    // samples, counted from the pins
    int nsamp = 0;
    always @(posedge adc_clk) nsamp = nsamp + 1;

    task automatic send(input logic [7:0] c);
        rx = 0; #1000;
        for (int b = 0; b < 8; b++) begin rx = c[b]; #1000; end
        rx = 1; #1000;
    endtask
    task automatic wait_samples(input int n);
        repeat (n) @(posedge adc_clk);
    endtask

    logic [7:0] rxbuf [0:4095];
    int         nrx = 0;
    logic [7:0] c;
    always @(negedge tx) begin
        #1500;
        for (int b = 0; b < 8; b++) begin c[b] = tx; #1000; end
        rxbuf[nrx] = c;
        nrx = nrx + 1;
    end

    // the script, one token per line, read with $fscanf into plain vectors (Icarus's
    // string type trips over a case on strings)
    logic [8*256-1:0] script = "control_script.txt";
    logic [8*8-1:0]  tok;
    int    f, code, v, k, nwords;
    logic signed [15:0] wa, wb;
    initial begin
        void'($value$plusargs("script=%s", script));
        f = $fopen(script, "r");
        if (f == 0) begin $display("cannot open the script"); $finish; end
        #2000;
        while (!$feof(f)) begin
            code = $fscanf(f, "%s", tok);
            if (code != 1) break;
            if (tok == "b") begin
                code = $fscanf(f, "%h", v);
                send(v[7:0]);
            end else if (tok == "g") begin
                wait_samples(100);
                $display("sample %6d: DAC = %3d", nsamp, dac);
            end else if (tok == "w") begin
                code = $fscanf(f, "%d", v);
                wait_samples(v);
                $display("sample %6d: DAC = %3d", nsamp, dac);
            end else if (tok == "c") begin
                nwords = 1 << LOGN;
                wait (nrx >= 4 * nwords);
                $display("capture: %0d bytes.  words 0, 62, 63, 64, 65, 70, 100, %0d:", nrx, nwords - 1);
                for (int i = 0; i < 8; i++) begin
                    k = (i == 0) ? 0 : (i == 1) ? 62 : (i == 2) ? 63 : (i == 3) ? 64 : (i == 4) ? 65 :
                        (i == 5) ? 70 : (i == 6) ? 100 : nwords - 1;
                    wa = {rxbuf[4 * k], rxbuf[4 * k + 1]};
                    wb = {rxbuf[4 * k + 2], rxbuf[4 * k + 3]};
                    $display("   [%3d] A = %6d  B = %6d", k, wa, wb);
                end
                nrx = 0;
            end else if (tok == "s") begin              // a status frame is due: 32 bytes
                wait (nrx >= 32);
                $write("status:");
                for (int i = 0; i < 32; i++) $write(" %02x", rxbuf[i]);
                $display("");
                nrx = 0;
            end
        end
        $fclose(f);
        $display("end of script at sample %0d: DAC = %0d", nsamp, dac);
        $finish;
    end
endmodule
