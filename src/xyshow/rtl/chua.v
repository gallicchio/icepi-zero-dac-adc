// Chua's circuit, the second digital twin: x' = alpha (y - x - f(x)), y' = x - y + z, z' = -beta y, with the diode's
// f(x) = m1 x + (m0 - m1)/2 (|x + 1| - |x - 1|).  The classic double scroll has alpha 15.6, beta 28, m0 -8/7, m1 -5/7;
// here alpha = 15.625 (16 - 3/8), m1 = -23/32, (m0 - m1)/2 = -7/32, so every product is shifts and adds: no multiplier.
// State in Q14.24 (38 bits, like lorenz.v), Runge-Kutta 4 with dt = 2^-10 time units a `step` (dt/6 as 1/8 + 1/32 +
// 1/128 + 1/512: a 0.4 % time-scale error, nothing else).  The arithmetic is pipelined one or two 38-bit adders a
// clock (a derivative takes six clocks, a step 32), which closes timing at 50 MHz where a single-cycle derivative did
// not.  `load` sets the state (the Y board, from the burst).  `busy` falls when a step is done (the ring writer watches it).
module chua #(parameter signed [37:0] X0 = 38'sd1677722, Y0 = 38'sd0, Z0 = 38'sd0) (
    input  wire               clk,
    input  wire               step,
    input  wire               load,
    input  wire signed [37:0] x_in, y_in, z_in,
    output reg                busy = 1'b0,
    output reg  signed [37:0] x = X0,
    output reg  signed [37:0] y = Y0,
    output reg  signed [37:0] z = Z0
);
    localparam signed [37:0] ONE = 38'sd16777216;
    reg signed [37:0] sx = 0, sy = 0, sz = 0;                                   // the state the derivative is taken at
    reg signed [37:0] a1p = 0, a2p = 0, t1 = 0, t2 = 0, a1 = 0, a2 = 0, t = 0, d = 0, d2 = 0, w = 0, dx = 0, dy = 0, dz = 0;
    reg signed [37:0] k1x = 0, k1y = 0, k1z = 0, k2x = 0, k2y = 0, k2z = 0, k3x = 0, k3y = 0, k3z = 0, k4x = 0, k4y = 0, k4z = 0;
    reg signed [37:0] ksx = 0, ksy = 0, ksz = 0, s6x = 0, s6y = 0, s6z = 0;
    reg [3:0] st = 0; reg [1:0] ph = 0;
    function signed [37:0] sixth(input signed [37:0] v); begin sixth = (v >>> 3) + (v >>> 5) + (v >>> 7) + (v >>> 9); end endfunction
    always @(posedge clk) begin
        if (load) begin x <= x_in; y <= y_in; z <= z_in; st <= 0; busy <= 0; end
        else case (st)
            0: if (step) begin busy <= 1; sx <= x; sy <= y; sz <= z; ph <= 0; st <= 1; end
            // the derivative at (sx, sy, sz): f(x) = -(x/2 + x/8 + x/16 + x/32) - (d/4 - d/32), d = |x + 1| - |x - 1|
            1: begin a1p <= sx + ONE; a2p <= sx - ONE; t1 <= (sx >>> 1) + (sx >>> 3); t2 <= (sx >>> 4) + (sx >>> 5); st <= 2; end
            2: begin a1 <= a1p[37] ? -a1p : a1p; a2 <= a2p[37] ? -a2p : a2p; t <= t1 + t2; st <= 3; end
            3: begin d <= a1 - a2; st <= 4; end
            4: begin d2 <= (d >>> 2) - (d >>> 5); st <= 5; end
            5: begin w <= (sy - sx) + t + d2; dy <= sx - sy + sz; dz <= (sy <<< 2) - (sy <<< 5); st <= 6; end      // w = y - x - f(x)
            6: begin dx <= (w <<< 4) - (w >>> 2) - (w >>> 3); st <= 7; end                                         // alpha w
            // the four evaluations of Runge-Kutta 4
            7: begin
                   case (ph)
                       0: begin k1x <= dx; k1y <= dy; k1z <= dz; sx <= x + (dx >>> 11); sy <= y + (dy >>> 11); sz <= z + (dz >>> 11); end
                       1: begin k2x <= dx; k2y <= dy; k2z <= dz; sx <= x + (dx >>> 11); sy <= y + (dy >>> 11); sz <= z + (dz >>> 11); end
                       2: begin k3x <= dx; k3y <= dy; k3z <= dz; sx <= x + (dx >>> 10); sy <= y + (dy >>> 10); sz <= z + (dz >>> 10); end
                       3: begin k4x <= dx; k4y <= dy; k4z <= dz; end
                   endcase
                   ph <= ph + 1; st <= (ph == 3) ? 4'd8 : 4'd1;
               end
            8: begin ksx <= (k1x + k4x) + ((k2x + k3x) <<< 1); ksy <= (k1y + k4y) + ((k2y + k3y) <<< 1); ksz <= (k1z + k4z) + ((k2z + k3z) <<< 1); st <= 9; end
            9: begin s6x <= sixth(ksx); s6y <= sixth(ksy); s6z <= sixth(ksz); st <= 10; end
            10: begin x <= x + (s6x >>> 10); y <= y + (s6y >>> 10); z <= z + (s6z >>> 10); busy <= 0; st <= 0; end
            default: st <= 0;
        endcase
    end
endmodule
