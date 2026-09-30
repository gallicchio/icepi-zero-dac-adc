// capture_tb.v -- simulate capture.v with no hardware at all.
//
// A fake ADC counts up by one on every rising edge of adc_clk, with the
// AD9280's 25 ns output delay, and the testbench plays the PC: it sends "0"
// and checks that the samples coming back count up by one too.
//
//   make sim-capture     (or: iverilog -o capture_tb.vvp capture_tb.v capture.v uart.v && vvp capture_tb.vvp)
`timescale 1ns/1ps
module capture_tb;
    reg clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    reg  [7:0] adc = 0;
    wire       adc_clk, tx;
    reg        rx = 1;
    wire [4:0] led;
    always @(posedge adc_clk) adc <= #25 adc + 1;   // a ramp, 25 ns late like the real ADC

    capture dut (.clk(clk), .adc_d(adc), .adc_clk(adc_clk),
                 .uart_rx(rx), .uart_tx(tx), .led(led));

    task send(input [7:0] c);                       // 1 Mbaud: 1 us per bit
        integer b;
        begin
            rx = 0; #1000;
            for (b = 0; b < 8; b = b + 1) begin rx = c[b]; #1000; end
            rx = 1; #1000;
        end
    endtask

    integer n = 0, errors = 0, b2;
    reg [7:0] c, prev;
    always @(negedge tx) begin                      // receive one byte
        #1500;
        for (b2 = 0; b2 < 8; b2 = b2 + 1) begin c[b2] = tx; #1000; end
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
