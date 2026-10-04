// funcgen_core.sv -- a DDS function generator: sine, square, triangle, sawtooth.
//
// The phase accumulator of sine.sv, with the waveform and amplitude now
// inputs, so a CPU can change them while it runs.  The phase is also an
// output: the lock-in uses it as its reference.
//
//   f = tw * f_clk / 2^32        amplitude: 255 = full scale (+-3.9 V)

module funcgen_core (
    input  logic        clk,
    input  logic [31:0] tw,             // tuning word: from a CPU register
    input  logic [7:0]  amplitude,      // 0..255: from a CPU register
    input  logic [1:0]  waveform,       // 0 sine, 1 square, 2 triangle, 3 sawtooth
    output logic [31:0] phase = 0,
    output logic [7:0]  dac_value = 128
);
    logic signed [7:0] sine_table [0:255];
    initial
        for (int i = 0; i < 256; i++)
            sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    // ##########################################################################
    // ##  KEY LINE: the same phase accumulator as sine.sv, but now `tw` is a
    // ##  wire from a register that the CPU writes.
    // ##########################################################################
    always_ff @(posedge clk)
        phase <= phase + tw;

    // step 1: the waveform, as a signed number -128..127
    logic [8:0] p;
    assign p = phase[31:23];                    // 9 bits of phase, for the triangle
    logic signed [7:0] w = 0;
    always_ff @(posedge clk)
        case (waveform)
            2'd0: w <= sine_table[phase[31:24]];
            2'd1: w <= phase[31] ? -8'sd127 : 8'sd127;
            2'd2: w <= (p < 256) ? p - 128 : 383 - p;   // up for half a cycle, then down
            2'd3: w <= phase[31:24] - 128;
        endcase

    // step 2: scale by amplitude/256.  step 3: back to offset binary for the DAC
    logic signed [16:0] scaled = 0;
    always_ff @(posedge clk) begin
        scaled    <= w * $signed({1'b0, amplitude});
        dac_value <= (scaled >>> 8) + 128;
    end
endmodule
