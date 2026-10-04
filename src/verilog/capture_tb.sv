// capture_tb.sv -- simulate capture.sv with no hardware at all.
//
// A fake ADC counts up by one on every rising edge of adc_clk, with the
// AD9280's 25 ns output delay, and the testbench plays the laptop: it sends "0"
// and checks that the samples coming back count up by one too.
//
//   make sim-capture
//   (or: iverilog -g2012 -o capture_tb.vvp capture_tb.sv capture.sv uart.sv && vvp capture_tb.vvp)
`timescale 1ns/1ps
module capture_tb;
    logic clk = 0;
    always #10 clk = ~clk;                          // 50 MHz: flip every 10 ns

    logic [7:0] adc = 0;
    logic       adc_clk, tx;
    logic       rx = 1;
    logic [4:0] led;
    always @(posedge adc_clk) adc <= #25 adc + 1;   // a ramp, 25 ns late like the real ADC

    // the design under test ("dut"), wired to the fake world
    capture dut (.clk(clk), .adc_d(adc), .adc_clk(adc_clk),
                 .uart_rx(rx), .uart_tx(tx), .led(led));

    // play the laptop: send one character at 1 Mbaud (1 us per bit)
    task automatic send(input logic [7:0] c);
        rx = 0; #1000;                                  // start bit
        for (int b = 0; b < 8; b++) begin rx = c[b]; #1000; end
        rx = 1; #1000;                                  // stop bit
    endtask

    // ...and listen: receive each byte the FPGA sends, and check it
    int n = 0, errors = 0;
    logic [7:0] c, prev;
    always @(negedge tx) begin                      // the start bit has begun
        #1500;                                      // to the middle of data bit 0
        for (int b = 0; b < 8; b++) begin c[b] = tx; #1000; end
        if (n < 8) $display("%t ns  sample %0d = %0d", $time / 1000, n, c);
        if (n > 0 && c != prev + 8'd1) errors = errors + 1;
        prev = c;
        n = n + 1;
    end

    initial begin
        #5000;
        send("0");                                  // capture at full rate
        #1_000_000;                                 // recording + the first ~30 bytes back
        $display("%0d samples received, %0d not one more than the one before", n, errors);
        $finish;
    end
endmodule
