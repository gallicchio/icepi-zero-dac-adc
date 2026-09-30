// lockin_core.v -- Tutorial 4's lock-in, with the serial port replaced by
// registers.  The reference is the function generator's own phase, so
// whatever frequency the function generator is set to is what we detect.
//
// A `start` pulse sums 2^n_log2 products (n_log2 up to 24: 0.67 s):
//     x_sum = sum (adc - 128) * sin(phase)      y_sum = sum (adc - 128) * cos(phase)
// with sin and cos from a table of +-127.  The CPU divides by 2^n_log2.

module lockin_core (
    input  wire        clk,
    input  wire [7:0]  sample,
    input  wire        sample_valid,
    input  wire [31:0] phase,           // from funcgen_core
    input  wire        start,
    input  wire [4:0]  n_log2,
    output reg         busy = 0,
    output reg         done = 0,
    output reg  signed [47:0] x_sum = 0,
    output reg  signed [47:0] y_sum = 0
);
    reg signed [7:0] sine_table [0:255];
    integer i;
    initial
        for (i = 0; i < 256; i = i + 1)
            sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    // the same 3-step assembly line as lockin.v
    reg               v1 = 0, v2 = 0;
    reg signed [8:0]  s = 0;
    reg signed [7:0]  ref_sin = 0, ref_cos = 0;
    reg signed [16:0] p_sin = 0, p_cos = 0;
    reg signed [47:0] acc_x = 0, acc_y = 0;
    reg [24:0]        count = 0;

    always @(posedge clk) begin
        v1      <= sample_valid;
        s       <= $signed({1'b0, sample}) - 9'sd128;
        ref_sin <= sine_table[phase[31:24]];
        ref_cos <= sine_table[phase[31:24] + 8'd64];
        v2      <= v1;
        p_sin   <= s * ref_sin;
        p_cos   <= s * ref_cos;

        if (start) begin
            acc_x <= 0;
            acc_y <= 0;
            count <= 0;
            busy  <= 1;
            done  <= 0;
        end else if (busy && v2) begin
            acc_x <= acc_x + p_sin;
            acc_y <= acc_y + p_cos;
            count <= count + 1;
            if (count == (25'd1 << n_log2) - 1) begin
                x_sum <= acc_x + p_sin;
                y_sum <= acc_y + p_cos;
                busy  <= 0;
                done  <= 1;
            end
        end
    end
endmodule
