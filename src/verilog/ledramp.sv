// ledramp.sv -- a slow DC ramp on the DAC, and where it has got to on the five LEDs.
//
// For AMOD-P's tile p12: four LEDs (red, yellow, green, blue) behind 100 ohm, one at a time on its DIP switch.
// The DAC rises from 0 V to +3.9 V in 43 s, one DAC step (30.7 mV) every 0.34 s, drops back to 0 V and rises
// again.  The LEDs show the ramp's top five bits: led[4], the leftmost, is worth 1.97 V, then 0.98, 0.49, 0.25 and
// 0.12 V, so the voltage is the sum of the lit LEDs' weights (to within the 0.12 V of one LED step).
// The button nearest the USB connectors stops the ramp where it is; press it again and it goes on.

module ledramp (
    input  logic       clk,         // 50 MHz
    input  logic       btn,         // 0 while pressed
    output logic [7:0] dac_d,       // code 128 is 0 V (-0.02 V), 255 is +3.88 V: 1.02's V = 0.0307 x code - 3.95
    output logic       dac_clk,
    output logic [4:0] led          // led[4] (the MSB) is the leftmost; 1 = on
);
    // ---- the button starts and stops the ramp.  Its contacts bounce for a few milliseconds, so look at it only
    //      once every 2^20 clocks (21 ms): a press is a 1 at one look and a 0 at the next.  `last` starts at 0, so a
    //      press has to be a 1 first: the button's pull-up is inside the FPGA, and at the first clock after loading the
    //      pin can still read 0.  (Starting at 1 counted that as a press: the ramp stopped at 0 V before it began.)
    logic [19:0] tick = 0;
    logic        last = 0, running = 1;
    always_ff @(posedge clk) begin
        tick <= tick + 1;
        if (tick == 0) begin
            last <= btn;
            if (last && !btn)
                running <= !running;
        end
    end

    // ---- the ramp: a 31-bit counter whose top 7 bits are the DAC's steps above 0 V
    logic [30:0] t = 0;
    always_ff @(posedge clk)
        if (running)
            // ######################################################################
            // ##  KEY LINE: up by one every 20 ns.  The top 7 bits go up by one
            // ##  every 2^24 clocks (0.34 s): 0 to 127 in 43 s, then wrap to 0.
            // ######################################################################
            t <= t + 1;

    wire [6:0] v = t[30:24];        // 0 .. 127
    assign dac_d   = 8'd128 + v;    // 0 V .. +3.88 V
    assign led     = v[6:2];        // the top five bits: one LED step is 4 DAC steps, 0.12 V
    assign dac_clk = ~clk;          // as in sawtooth.sv
endmodule
