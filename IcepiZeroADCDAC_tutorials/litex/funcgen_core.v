// funcgen_core.v -- a DDS function generator: sine, square, triangle, sawtooth.
//
// The phase accumulator of Tutorial 2, with the waveform and amplitude now
// inputs, so a CPU can change them while it runs.  The phase is also an
// output: the lock-in uses it as its reference.
//
//   f = tw * f_clk / 2^32        amplitude: 255 = full scale (+-3.9 V)

module funcgen_core (
    input  wire        clk,
    input  wire [31:0] tw,          // tuning word
    input  wire [7:0]  amplitude,   // 0..255
    input  wire [1:0]  waveform,    // 0 sine, 1 square, 2 triangle, 3 sawtooth
    output reg  [31:0] phase = 0,
    output reg  [7:0]  dac_value = 128
);
    reg signed [7:0] sine_table [0:255];
    integer i;
    initial
        for (i = 0; i < 256; i = i + 1)
            sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    always @(posedge clk)
        phase <= phase + tw;

    // step 1: the waveform, as a signed number -128..127
    wire [8:0] p = phase[31:23];                 // 9 bits of phase, for the triangle
    reg signed [7:0] w = 0;
    always @(posedge clk)
        case (waveform)
            2'd0: w <= sine_table[phase[31:24]];
            2'd1: w <= phase[31] ? -8'sd127 : 8'sd127;
            2'd2: w <= (p < 256) ? p - 128 : 383 - p;   // up for half a cycle, then down
            2'd3: w <= phase[31:24] - 128;
        endcase

    // step 2: scale by amplitude/256.  step 3: back to offset binary for the DAC
    reg signed [16:0] scaled = 0;
    always @(posedge clk) begin
        scaled    <= w * $signed({1'b0, amplitude});
        dac_value <= (scaled >>> 8) + 128;
    end
endmodule
