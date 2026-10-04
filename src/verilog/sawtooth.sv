// sawtooth.sv -- a counter wired to the DAC is a ramp generator.
//
// Every 20 ns the 8-bit count goes up by one and the DAC turns it into a
// voltage.  After 255 it wraps to 0, so the output is a sawtooth that repeats
// every 256 x 20 ns = 5.12 us (195.3 kHz).

module sawtooth (
    input  logic       clk,         // 50 MHz
    output logic [7:0] dac_d = 0,   // DAC data; dac_d[7] is the most significant bit (MSB)
    output logic       dac_clk      // the DAC grabs dac_d on the RISING edge of this
);
    always_ff @(posedge clk)
        // ######################################################################
        // ##  KEY LINE: the DAC's number goes up by one every clock (20 ns).
        // ##  8 bits wrap from 255 back to 0 by themselves: that's the sawtooth.
        // ######################################################################
        dac_d <= dac_d + 1;

    // dac_d changes just after each rising edge of clk.  Inverting clk puts
    // the DAC's rising edge halfway between those changes, 10 ns after one
    // and 10 ns before the next -- when the data is steady.
    assign dac_clk = ~clk;
endmodule
