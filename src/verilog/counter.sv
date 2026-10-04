// counter.sv -- a binary counter on the five white LEDs.
//
// The 50 MHz oscillator ticks a 28-bit register up by one every 20 ns.
// Bit n of a counter is a square wave at 50 MHz / 2^(n+1), so we show the top five
// bits (23..27) -- bit 23 changes every 0.17 s, slow enough to watch.

module counter (
    input  logic       clk,         // 50 MHz, from the crystal oscillator
    output logic [4:0] led          // 1 = LED on
);
    logic [27:0] count = 0;         // 28 flip-flops; "= 0" is their value right after the FPGA loads

    always_ff @(posedge clk)        // on every rising edge of the clock...
        // ######################################################################
        // ##  KEY LINE: add one, every 20 ns.  That's the whole circuit.
        // ######################################################################
        count <= count + 1;

    assign led = count[27:23];      // wires from five of the flip-flops to the five LED pins
endmodule
