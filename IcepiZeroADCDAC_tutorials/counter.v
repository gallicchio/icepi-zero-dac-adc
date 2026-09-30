// counter.v -- Tutorial 1: a binary counter on the five white LEDs.
//
// The 50 MHz oscillator ticks a 28-bit register up by one every 20 ns.
// Bit n of a counter toggles at 50 MHz / 2^(n+1), so we show the top five
// bits (23..27) -- bit 23 changes every 0.17 s, slow enough to watch.

module counter (
    input  wire       clk,      // 50 MHz
    output wire [4:0] led       // 1 = LED on
);
    reg [27:0] count = 0;       // "= 0" is the value right after the FPGA loads

    always @(posedge clk)       // on every rising edge of the clock...
        count <= count + 1;     // ...add one.  That's the whole circuit.

    assign led = count[27:23];  // wires from five flip-flops to five pins
endmodule
