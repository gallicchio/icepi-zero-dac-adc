// lockin_tb.v -- simulate lockin.v with no hardware at all.
//
// The "analog world" here is a wire from the DAC pins back to the ADC pins,
// delayed by DELAY clocks and halved in amplitude.  So the lock-in should
// report an amplitude of 127/2 = 63.5 codes and a phase that is a pure delay.
//
//   iverilog -o lockin_tb.vvp lockin_tb.v lockin.v uart.v && vvp lockin_tb.vvp
`timescale 1ns/1ps
module lockin_tb;
    reg clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    wire [7:0] dac;
    wire       dac_clk, adc_clk, tx;
    reg        rx = 1;
    wire [4:0] led;

    // the fake analog path: delay the DAC codes, halve them around mid-scale
    localparam DELAY = 5;                            // clocks = 100 ns
    reg [7:0] pipe [0:DELAY];
    integer k;
    initial for (k = 0; k <= DELAY; k = k + 1) pipe[k] = 128;   // silence, not "x"
    always @(posedge clk) begin
        pipe[0] <= dac;
        for (k = 1; k <= DELAY; k = k + 1) pipe[k] <= pipe[k-1];
    end
    wire signed [8:0] centred = $signed({1'b0, pipe[DELAY]}) - 128;
    wire [7:0] adc = 128 + (centred >>> 1);

    // average 2^16 samples instead of 2^20, so the simulation is 16x shorter
    lockin #(.N_LOG2(16)) dut (.clk(clk), .adc_d(adc), .adc_clk(adc_clk),
        .dac_d(dac), .dac_clk(dac_clk), .uart_rx(rx), .uart_tx(tx), .led(led));

    // play the PC: send characters at 1 Mbaud (1 us per bit)
    task send(input [7:0] c);
        integer b;
        begin
            rx = 0; #1000;                                   // start bit
            for (b = 0; b < 8; b = b + 1) begin rx = c[b]; #1000; end
            rx = 1; #1000;                                   // stop bit
        end
    endtask

    // ...and listen: collect characters into a line and print it
    reg [8*40:1] line = 0;
    reg [7:0] c;
    integer b2;
    always @(negedge tx) begin
        #1500;                                               // middle of bit 0
        for (b2 = 0; b2 < 8; b2 = b2 + 1) begin c[b2] = tx; #1000; end
        if (c == "\n") begin
            $display("%t ns  FPGA says: %0s", $time / 1000, line);
            line = 0;
        end else
            line = {line[8*39:1], c};
    end

    initial begin
        #6_000_000;                                  // two results at 1 MHz (the default)
        send("0"); send("c"); send("c"); send("c");  // TW = 0ccccccd: 2.5 MHz
        send("c"); send("c"); send("c"); send("d"); send("\n");
        #6_000_000;
        $finish;
    end
endmodule
