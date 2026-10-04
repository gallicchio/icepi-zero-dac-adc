// sine.sv -- a sine wave out of the DAC by direct digital synthesis (DDS).
//
// A 32-bit "phase accumulator" adds a constant TW every clock.  Think of it as
// the angle of a phasor: 2^32 counts = one full turn.  Its top 8 bits pick
// one of 256 entries in a table of sin(), and that goes to the DAC.
//
//     output frequency  f = TW * 50 MHz / 2^32        (resolution 0.012 Hz)
//     so                TW = round(f / 50 MHz * 2^32)

module sine #(
    parameter logic [31:0] TW = 32'd85899346    // 1.000 000 MHz (calculation above)
) (
    input  logic       clk,                     // 50 MHz
    output logic [7:0] dac_d = 0,
    output logic       dac_clk
);
    // ---- the table: 256 samples of one cycle, from -127 to +127 ----------
    // Filled in when the design is compiled: Yosys runs this loop, not the FPGA.
    logic signed [7:0] sine_table [0:255];
    initial
        for (int i = 0; i < 256; i++)
            sine_table[i] = $rtoi($floor(127.0 * $sin(2 * 3.141592653589793 * i / 256) + 0.5));

    // ---- the phase accumulator -------------------------------------------
    logic [31:0] phase = 0;

    always_ff @(posedge clk) begin
        // ######################################################################
        // ##  KEY LINE 1: the phase advances by TW every clock.  It wraps
        // ##  around at 2^32 all by itself, exactly like an angle.
        // ######################################################################
        phase <= phase + TW;

        // ######################################################################
        // ##  KEY LINE 2: the top 8 bits of the phase pick a sample of sin()
        // ##  from the table.  "+ 128" turns -127..+127 into 1..255 for the DAC.
        // ######################################################################
        dac_d <= sine_table[phase[31:24]] + 128;
    end

    assign dac_clk = ~clk;                      // as in sawtooth.sv
endmodule
