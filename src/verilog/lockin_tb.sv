// lockin_tb.sv -- simulate lockin.sv with no hardware at all.
//
// The "analog world" here is a wire from the DAC pins back to the ADC pins,
// delayed by DELAY clocks and halved in amplitude.  So the lock-in should
// report an amplitude of 127/2 = 63.5 codes and a phase that is a pure delay.
//
//   make sim-lockin
//   (or: iverilog -g2012 -o lockin_tb.vvp lockin_tb.sv lockin.sv uart.sv && vvp lockin_tb.vvp)
`timescale 1ns/1ps
module lockin_tb;
    logic clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    logic [7:0] dac;
    logic       dac_clk, adc_clk, tx;
    logic       rx = 1;
    logic [4:0] led;

    // ##########################################################################
    // ##  KEY LINES: the fake analog world.  Delay the DAC's codes by DELAY
    // ##  clocks, and halve them around mid-scale.  That is what the ADC sees.
    // ##########################################################################
    localparam DELAY = 5;                           // clocks = 100 ns
    logic [7:0] pipe [0:DELAY];
    initial for (int k = 0; k <= DELAY; k++) pipe[k] = 128;    // silence, not "x"
    always @(posedge clk) begin
        pipe[0] <= dac;
        for (int k = 1; k <= DELAY; k++) pipe[k] <= pipe[k-1];
    end
    logic signed [8:0] centred;
    logic        [7:0] adc;
    assign centred = $signed({1'b0, pipe[DELAY]}) - 128;
    assign adc     = 128 + (centred >>> 1);

    // average 2^16 samples instead of 2^20, so the simulation is 16x shorter
    lockin #(.N_LOG2(16)) dut (.clk(clk), .adc_d(adc), .adc_clk(adc_clk),
        .dac_d(dac), .dac_clk(dac_clk), .uart_rx(rx), .uart_tx(tx), .led(led));

    // play the laptop: send characters at 1 Mbaud (1 us per bit)
    task automatic send(input logic [7:0] c);
        rx = 0; #1000;                                  // start bit
        for (int b = 0; b < 8; b++) begin rx = c[b]; #1000; end
        rx = 1; #1000;                                  // stop bit
    endtask

    // ...and listen: collect characters into a line and print it
    logic [8*40:1] line = 0;
    logic [7:0]    c;
    always @(negedge tx) begin
        #1500;                                          // the middle of bit 0
        for (int b = 0; b < 8; b++) begin c[b] = tx; #1000; end
        if (c == "\n") begin
            $display("%t ns  FPGA says: %0s", $time / 1000, line);
            line = 0;
        end else
            line = {line[8*39:1], c};
    end

    initial begin
        #6_000_000;                                 // two results at 1 MHz (the default)
        send("0"); send("c"); send("c"); send("c"); // TW = 0ccccccd: 2.5 MHz
        send("c"); send("c"); send("c"); send("d"); send("\n");
        #6_000_000;
        $finish;
    end
endmodule
