// sine.v -- Tutorial 2b: a sine wave out of the DAC by direct digital synthesis.
//
// A 32-bit "phase accumulator" adds a constant TW every clock.  Think of it as
// the angle of a phasor: 2^32 counts = one full turn.  Its top 8 bits pick
// one of 256 entries in a table of sin(), and that goes to the DAC.
//
//     output frequency  f = TW * 50 MHz / 2^32        (resolution 0.012 Hz)
//     so                TW = round(f / 50 MHz * 2^32)

module sine #(
    parameter [31:0] TW = 32'd85899346      // 1.000 000 MHz
) (
    input  wire       clk,                  // 50 MHz
    output reg  [7:0] dac_d,
    output wire       dac_clk
);
    // ---- the table: 256 samples of one cycle, from -127 to +127 ----------
    // Filled in when the design is compiled: yosys runs this loop, not the FPGA.
    reg signed [7:0] sine_table [0:255];
    integer i;
    initial
        for (i = 0; i < 256; i = i + 1)
            sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    // ---- the phase accumulator -------------------------------------------
    reg [31:0] phase = 0;

    always @(posedge clk) begin
        phase <= phase + TW;                       // wraps around at 2^32, like an angle
        dac_d <= sine_table[phase[31:24]] + 128;   // -127..+127  ->  1..255
    end

    assign dac_clk = ~clk;                         // as in sawtooth.v
endmodule
