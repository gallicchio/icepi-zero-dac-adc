// The digital twin of an analog Lorenz circuit (the AI UNLEASHES CHAOS board): Lorenz in fixed point, one Euler step per `step`.
//
//   dx/dt = s (y - x)                 [+ g (xa - x) in mode 1]
//   dy/dt = r xe - y - xe z           [+ g (xa - x) in mode 0]
//   dz/dt = xe y - b z
//   dr/dt = -gamma (y - ya) xe        (the adaptive law that makes r follow the analog board's knob)
//   xe = x, or the measured xa in mode 2 (Pecora-Carroll x-drive)
//
// Numbers are Q14.24 in W = 38 bits (range +/-8192, resolution 6e-8); dt = 2^-DTS time units (a shift);
// every product is floored (>>> F), then the sums are exact, so a model in Python integers can follow it bit for bit
// (one did, against a testbench, when it was written; neither is in this directory).
// The ADC codes (offset binary, 12 bits) become units through k_adc: xa = (code - 2048) * k_adc.
// One 38x38 multiplier, one product per cycle, 14 cycles per step (3.5 M steps/s at 50 MHz, i.e. a
// time unit as short as 1.2 ms; the analog board's fastest is 2.2 ms).
module lorenz #(parameter W = 38, F = 24, DTS = 12) (
    input  wire                 clk,
    input  wire                 rst,
    input  wire                 step,          // start a step (ignored while busy)
    output reg                  busy = 1'b0,
    input  wire [11:0]          code_a,        // ADC A: the board's x
    input  wire [11:0]          code_b,        // ADC B: the board's y
    input  wire                 couple,        // coupling and adaptation on
    input  wire [1:0]           mode,          // 0: g in dy, 1: g in dx, 2: x-drive
    input  wire signed [W-1:0]  s, b, g, gamma, k_adc,
    input  wire signed [W-1:0]  r_min, r_max,
    input  wire                 load,          // load x,y,z,r from the *_in ports
    input  wire signed [W-1:0]  x_in, y_in, z_in, r_in,
    output reg  signed [W-1:0]  x = 0,
    output reg  signed [W-1:0]  y = 0,
    output reg  signed [W-1:0]  z = 0,
    output reg  signed [W-1:0]  r = 0,
    output reg  signed [W-1:0]  xa = 0,        // the measured state, in units (for the error display)
    output reg  signed [W-1:0]  ya = 0
);
    reg [3:0] cyc = 0;
    reg signed [W-1:0] A = 0, B = 0;           // multiplier operands (registered)
    reg signed [2*W-1:0] P = 0;                // the product (registered)
    wire signed [W+1:0] Pf = P >>> F;          // floored, the top bits dropped (exact when the value fits)
    reg signed [W+1:0] dx = 0, dy = 0, dz = 0, t = 0;
    reg [11:0] ca = 0, cb = 0; reg cpl = 0; reg [1:0] md = 0;
    wire signed [W-1:0] xe = (md == 2'd2) ? xa : x;
    wire signed [W+1:0] rn = $signed({{2{r[W-1]}}, r}) - (($signed({{2{Pf[W+1]}}, Pf})) >>> DTS);
    wire signed [W-1:0] rc = (rn < $signed({{2{r_min[W-1]}}, r_min})) ? r_min :
                             (rn > $signed({{2{r_max[W-1]}}, r_max})) ? r_max : rn[W-1:0];

    always @(posedge clk) begin
        if (rst) begin
            busy <= 0; cyc <= 0; x <= 0; y <= 0; z <= 0; r <= 0; xa <= 0; ya <= 0;
        end else begin
            if (load) begin x <= x_in; y <= y_in; z <= z_in; r <= r_in; end
            if (!busy) begin
                if (step) begin busy <= 1; cyc <= 0; ca <= code_a; cb <= code_b; cpl <= couple; md <= mode; end
            end else begin
                cyc <= cyc + 1;
                P <= A * B;
                // issue: the operands for the multiply whose product lands two cycles later
                case (cyc)
                    4'd0:  begin A <= $signed({{(W-12-F){1'b0}}, ca, {F{1'b0}}}) - $signed({{(W-12-F){1'b0}}, 12'd2048, {F{1'b0}}}); B <= k_adc; end
                    4'd1:  begin A <= $signed({{(W-12-F){1'b0}}, cb, {F{1'b0}}}) - $signed({{(W-12-F){1'b0}}, 12'd2048, {F{1'b0}}}); B <= k_adc; end
                    4'd2:  begin A <= s;        B <= y - x; end
                    4'd3:  begin A <= r;        B <= xe;    end
                    4'd4:  begin A <= xe;       B <= z;     end
                    4'd5:  begin A <= g;        B <= xa - x; end
                    4'd6:  begin A <= xe;       B <= y;     end
                    4'd7:  begin A <= b;        B <= z;     end
                    4'd8:  begin A <= y - ya;   B <= xe;    end
                    4'd11: begin A <= gamma;    B <= t[W-1:0]; end   // t landed at the end of cycle 10
                    default: ;
                endcase
                // commit: the product issued at cyc-2
                case (cyc)
                    4'd2:  xa <= Pf[W-1:0];
                    4'd3:  ya <= Pf[W-1:0];
                    4'd4:  dx <= Pf;
                    4'd5:  dy <= Pf - $signed({{2{y[W-1]}}, y});
                    4'd6:  dy <= dy - Pf;
                    4'd7:  begin if (cpl && md == 2'd0) dy <= dy + Pf; if (cpl && md == 2'd1) dx <= dx + Pf; end
                    4'd8:  dz <= Pf;
                    4'd9:  dz <= dz - Pf;
                    4'd10: t <= Pf;
                    4'd13: begin
                        if (cpl) r <= rc;
                        x <= x + (dx >>> DTS); y <= y + (dy >>> DTS); z <= z + (dz >>> DTS);
                        busy <= 0;
                    end
                    default: ;
                endcase
            end
        end
    end
endmodule
