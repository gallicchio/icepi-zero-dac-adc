// lockin_core.sv -- lockin.sv's lock-in, with the serial port replaced by
// registers.  The reference is the function generator's own phase, so
// whatever frequency the function generator is set to is what we detect.
//
// A `start` pulse sums 2^n_log2 products (n_log2 up to 24: 0.67 s):
//     x_sum = sum (adc - 128) * cos(wt)      y_sum = sum (adc - 128) * -sin(wt)
// calling the stimulus cos(wt), as lockin.sv does, with both references from one
// table of +-127.  The CPU divides by 2^n_log2.

module lockin_core (
    input  logic        clk,
    input  logic [7:0]  sample,
    input  logic        sample_valid,
    input  logic [31:0] phase,          // from funcgen_core
    input  logic        start,
    input  logic [4:0]  n_log2,
    output logic        busy = 0,
    output logic        done = 0,
    output logic signed [47:0] x_sum = 0,
    output logic signed [47:0] y_sum = 0
);
    logic signed [7:0] sine_table [0:255];
    initial
        for (int i = 0; i < 256; i++)
            sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    // the same 3-step assembly line as lockin.sv
    logic               v1 = 0, v2 = 0;
    logic signed [8:0]  s = 0;
    logic signed [7:0]  ref_x = 0, ref_y = 0;
    logic signed [16:0] p_x = 0, p_y = 0;
    logic signed [47:0] acc_x = 0, acc_y = 0;
    logic [24:0]        count = 0;

    always_ff @(posedge clk) begin
        v1      <= sample_valid;
        s       <= $signed({1'b0, sample}) - 9'sd128;
        ref_x <= sine_table[phase[31:24]];            // cos(wt): the stimulus
        ref_y <= sine_table[phase[31:24] + 8'd64];    // a quarter turn on: -sin(wt)
        v2      <= v1;
        // ######################################################################
        // ##  KEY LINE 1: multiply the signal by both references, cos and -sin.
        // ######################################################################
        p_x   <= s * ref_x;
        p_y   <= s * ref_y;

        if (start) begin
            acc_x <= 0;
            acc_y <= 0;
            count <= 0;
            busy  <= 1;
            done  <= 0;
        end else if (busy && v2) begin
            // ##################################################################
            // ##  KEY LINE 2: add up the products; the CPU divides at the end.
            // ##################################################################
            acc_x <= acc_x + p_x;
            acc_y <= acc_y + p_y;
            count <= count + 1;
            if (count == (25'd1 << n_log2) - 1) begin
                x_sum <= acc_x + p_x;
                y_sum <= acc_y + p_y;
                busy  <= 0;
                done  <= 1;
            end
        end
    end
endmodule
