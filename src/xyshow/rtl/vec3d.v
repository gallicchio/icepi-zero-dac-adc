// The vector engine: a scene of 3D vertices in block RAM, transformed by one of four matrices per frame,
// projected with perspective, the far side of the globe hidden, and drawn by a line generator that steps
// the DACs along each visible segment (a jump between strokes).  Runs on clk_s; the DACs take a sample at
// every `upd` (25 MS/s).  A frame may follow the last at once (`run` within a few clocks of `frame_done`): the FIFO
// keeps the line generator going across the boundary, and the beam goes from the last point to the next frame's first
// as from one stroke to the next.  With `rev` a frame is drawn backwards (the ranges, their vertices and every stroke in
// the opposite order), so drawn alternately it starts where the last one ended: no jump between frames (a jump of 2 V
// from the end of the globe to the U of MUDD rang 0.24 V above the U, every frame).  Frames with a ring are always
// drawn forwards (the hold is on the ring's newest point).
//
// Scene memory: 8192 entries {beam, group[1:0], cull, x[15:0], y[15:0]} + {group[3:2], z[15:0]}, Q2.14 (+/-2, the
// scope's full width is +/-1), initialised from scene_xy.hex / scene_z.hex, so that the board shows the seal with
// no PC; the ring (2048 entries) holds the Lorenz tail, written as the twin runs.  A frame is up to three
// ranges {src, start, count}, taken at `run`; `frame_done` pulses after the last.
// Matrices: group g's is {R00..R22 row-major, t0, t1, t2}, Q2.14 each (16 bits), read from the animator's register
// file (its second port, `maddr`/`mdata`, address 512 + 16 g + k) whenever a vertex's group differs from the last:
// a scene is laid out group by group, so this costs 14 clocks a few times a frame.
// The transform: q = R p + t; hidden = cull & (R p)_z < 0; s = P/(P + q_z) from persp.hex (codes per unit);
// X = 2048 + q_x s, Y = 2048 + q_y s, rounded and clipped to 12 bits.  6 clocks a hidden vertex, 10 a visible one (3 and 5
// samples: the next vertex is read while this one is transformed, and a hidden one is known as its z row is summed); a FIFO of FIFO_DEPTH (512, a block RAM) feeds the line generator, which spends 2^k sub-steps on a segment
// of d codes (k = lead1(d) - step_shift, so 2 to 4 codes a sub-step at step_shift 2, but at least 2^min_k sub-steps on
// a drawn one), 1 on a jump, and `dwell` DAC samples on each sub-step (1 at full speed; taken at `run`, so a frame is
// drawn at one speed).  With min_k 3 every drawn segment takes 8 samples or more, more than the engine's 5 a vertex,
// so the engine runs ahead and fills the FIFO, and a run of hidden vertices (the globe's far side: a few hundred, 70 us)
// is worked through while the generator draws what is queued: the beam keeps moving.  (With a 16-deep FIFO and 2 to 4
// samples on a short segment the beam waited on a vertex a third of the time and was parked 13 to 20 %.)  A ring
// range's last point (the tail's head) is held `hold_n` samples, so it is bright and the motion shows.  A hidden vertex
// (culled) is not sent to the line generator at all (the next visible one comes as a jump), so the far side of the
// globe costs no beam time; and a jump is sent only when a drawn segment follows it, so a visible vertex between hidden
// ones (the poles of the meridians behind an upright globe, exactly on its limb) is not visited at all.  After the last
// frame (the engine idle for IDLE_PARK clocks and everything drawn, `drained`) y is parked at 0, below the screen: the
// beam does not sit on the last point while the animator or the X board's burst runs, and the burst is drawn off the
// bottom of the screen.  It is parked too when the generator has waited STARVE_PARK samples for a segment in mid-frame
// (a run of hidden vertices longer than the FIFO holds); each park is a streak to the bottom and back, and the
// return's overshoot (0.4 to 0.6 V on the Icepi's DAC module) a dot above the point it returns to.
module vec3d #(parameter STARVE_PARK = 16, FIFO_DEPTH = 512, IDLE_PARK = 4) (
    input  wire         clk,
    input  wire         upd,
    input  wire         run,            // one clock: draw a frame (the engine idles after it)
    input  wire         rev,            // with run: draw it backwards (taken only when no range is a ring)
    input  wire         abort,          // one clock: drop the frame in progress, the FIFO and the segment in preparation
    input  wire [5:0]   r_src,          // per range, 2 bits: 0 the scene, 1 the ring, 2 the second ring
    input  wire [38:0]  r_start,        // 3 x 13 bits
    input  wire [38:0]  r_count,        // 3 x 13 bits (0: skipped)
    output reg  [9:0]   maddr = 10'd0,
    input  wire [15:0]  mdata,
    input  wire [3:0]   step_shift,
    input  wire [3:0]   min_k,          // a drawn segment takes at least 2^min_k sub-steps
    input  wire [15:0]  dwell,
    input  wire [15:0]  hold_n,         // DAC samples to stay on a ring range's last point (the tail's bright head)
    input  wire         vw,  input wire [12:0] vaddr, input wire [35:0] vxy, input wire [17:0] vz,
    input  wire         rw,  input wire [10:0] raddr, input wire [35:0] rxy, input wire [17:0] rz,
    input  wire         rw2, input wire [10:0] raddr2, input wire [35:0] rxy2, input wire [17:0] rz2,
    output wire [11:0]  x, y,
    output reg          beam = 1'b0,
    output reg          frame_done = 1'b0,
    output reg  [15:0]  frames = 16'd0,
    output wire         fifo_empty,
    output wire         drained         // the frame is on the scope: nothing left in the FIFO, the preparation or the generator
);
    // ---- memories ----
    reg [35:0] vmem_xy [0:8191]; reg [17:0] vmem_z [0:8191];
    reg [35:0] ring_xy [0:2047]; reg [17:0] ring_z [0:2047]; reg [35:0] ring2_xy [0:2047]; reg [17:0] ring2_z [0:2047];
    integer ii; initial begin $readmemh("scene_xy.hex", vmem_xy); $readmemh("scene_z.hex", vmem_z); for (ii = 0; ii < 2048; ii = ii + 1) begin ring_xy[ii] = 36'd0; ring_z[ii] = 18'd0; ring2_xy[ii] = 36'd0; ring2_z[ii] = 18'd0; end end
    reg [15:0] persp [0:511]; initial $readmemh("persp.hex", persp);
    reg [12:0] va = 0; reg [35:0] vrd_xy = 0, rrd_xy = 0, r2rd_xy = 0; reg [17:0] vrd_z = 0, rrd_z = 0, r2rd_z = 0;
    always @(posedge clk) begin
        if (vw) begin vmem_xy[vaddr] <= vxy; vmem_z[vaddr] <= vz; end
        vrd_xy <= vmem_xy[va]; vrd_z <= vmem_z[va];
        if (rw) begin ring_xy[raddr] <= rxy; ring_z[raddr] <= rz; end
        rrd_xy <= ring_xy[va[10:0]]; rrd_z <= ring_z[va[10:0]];
        if (rw2) begin ring2_xy[raddr2] <= rxy2; ring2_z[raddr2] <= rz2; end
        r2rd_xy <= ring2_xy[va[10:0]]; r2rd_z <= ring2_z[va[10:0]];
    end
    // ---- the transform ----
    reg [3:0] st = 0; reg [1:0] rng = 0; reg [12:0] idx = 0, cnt = 0, start = 0; reg [1:0] src = 0; reg first = 1; reg hold_now = 0;
    reg [23:0] pend = 0; reg pend_v = 0;                                         // a jump, sent only when a drawn segment follows it
    reg frev = 0; reg prev_beam = 0;                                             // this frame backwards; the last vertex's beam bit (backwards, a segment's)
    wire last_v = frev ? (idx == 0) : (idx + 13'd1 == cnt); wire [12:0] idx_next = frev ? idx - 13'd1 : idx + 13'd1;
    wire last_r = frev ? (rng == 2'd0) : (rng == 2'd2); wire [1:0] rng_next = frev ? rng - 2'd1 : rng + 2'd1;
    reg [2:0] idle_n = 0;                                                        // clocks the engine has been idle with no `run`
    reg [5:0] q_src = 0; reg [38:0] q_start = 0, q_count = 0;                    // the frame's ranges, taken at `run`
    reg [15:0] dwell_f = 16'd1;                                                  // and its dwell
    wire [12:0] rs = q_start[13*rng +: 13]; wire [12:0] rc = q_count[13*rng +: 13]; wire [1:0] rsrc = q_src[2*rng +: 2];
    wire [35:0] exy = src[1] ? r2rd_xy : src[0] ? rrd_xy : vrd_xy; wire [17:0] ez = src[1] ? r2rd_z : src[0] ? rrd_z : vrd_z;
    reg ebeam = 0, ecull = 0; reg [3:0] egrp = 0; reg signed [15:0] px = 0, py = 0, pz = 0;
    wire [3:0] gnew = {ez[17:16], exy[34:33]};
    reg [191:0] m = 192'd0; reg [3:0] mgrp = 0, mk = 0; reg mvalid = 0;           // the current group's matrix, fetched on a change of group
    function signed [15:0] me(input [191:0] mm, input integer k); begin me = mm[16*k +: 16]; end endfunction
    reg signed [15:0] a0 = 0, a1 = 0, a2 = 0, b = 0;          // the three rows' operands and the shared column
    reg signed [33:0] acc0 = 0, acc1 = 0, acc2 = 0;
    wire signed [31:0] m0 = a0 * b, m1 = a1 * b, m2 = a2 * b;
    reg signed [16:0] qx = 0, qy = 0, qz = 0; reg hidden_q = 0;
    reg [8:0] pidx = 0; reg [15:0] sc = 0;
    wire signed [33:0] accz14 = acc2 >>> 14;
    function signed [15:0] clip16(input signed [17:0] v); begin clip16 = v > 18'sd32767 ? 16'sd32767 : v < -18'sd32768 ? -16'sd32768 : v[15:0]; end endfunction
    wire signed [33:0] prx = $signed(qx) * $signed({1'b0, sc}), pry = $signed(qy) * $signed({1'b0, sc});
    reg signed [33:0] prxq = 0, pryq = 0;
    // rounded to the nearest code, not floored: the equator of the upright globe lies on the centre line, and the matrices'
    // rounding put its vertices a speck above or below it as the globe turned, so the floor gave 2047 or 2048, which the Icepi
    // pair's 8-bit DACs took as codes 127 or 128: the equator jumped a code up and down (Jason, 2026-11-09)
    wire signed [19:0] cx = 20'sd2048 + ((prxq + 34'sd8192) >>> 14), cy = 20'sd2048 + ((pryq + 34'sd8192) >>> 14);
    function [11:0] clip12(input signed [19:0] v); begin clip12 = v < 0 ? 12'd0 : v > 20'sd4095 ? 12'd4095 : v[11:0]; end endfunction
    // the FIFO to the line generator, in a block RAM: written by the engine, read one clock after its address settles
    // (`head`); an entry is taken only when the count a clock ago says it was there, so `head` has caught up with it
    localparam FA = $clog2(FIFO_DEPTH);
    reg [25:0] fifo [0:FIFO_DEPTH-1]; reg [FA-1:0] fw = 0, fr = 0; reg [FA:0] fn = 0, fn_q = 0; reg [25:0] head = 0;
    wire fifo_full = (fn == FIFO_DEPTH); assign fifo_empty = (fn == 0);
    wire fifo_room = (fn < FIFO_DEPTH - 2);                                  // room for two entries (a jump and its segment)
    reg push = 0; reg [25:0] pdata = 0; wire pop;
    always @(posedge clk) begin
        if (push && !fifo_full && !abort) fifo[fw] <= pdata;
        head <= fifo[fr];
    end
    always @(posedge clk) begin
        if (abort) begin fw <= 0; fr <= 0; fn <= 0; fn_q <= 0; end
        else begin
            if (push && !fifo_full) fw <= fw + 1;
            if (pop) fr <= fr + 1;
            fn <= fn + ((push && !fifo_full) ? 1'b1 : 1'b0) - (pop ? 1'b1 : 1'b0);
            fn_q <= fn;
        end
    end
    localparam S_IDLE = 0, S_RANGE = 1, S_FETCH = 2, S_WAIT = 3, S_LOAD = 4, S_M0 = 5, S_M1 = 6, S_M2 = 7, S_M3 = 12, S_NORM = 8, S_PERSP = 9, S_PROJ = 10, S_MULT = 13, S_EMIT = 11, S_MF = 14;
    reg signed [31:0] m0q = 0, m1q = 0, m2q = 0;
    wire signed [33:0] z_sum = acc2 + m2q;                       // the z row's sum, as S_NORM completes it: the cull's sign
    always @(posedge clk) begin
        push <= 0; frame_done <= 0;
        if (st == S_IDLE && !run) begin if (idle_n != IDLE_PARK) idle_n <= idle_n + 1; end else idle_n <= 0;
        if (abort) begin st <= S_IDLE; rng <= 0; mvalid <= 0; pend_v <= 0; hold_now <= 0; hidden_q <= 0; end
        else case (st)
            S_IDLE:  if (run) begin
                frev <= rev && (r_src == 6'd0); rng <= (rev && r_src == 6'd0) ? 2'd2 : 2'd0;
                mvalid <= 0; q_src <= r_src; q_start <= r_start; q_count <= r_count; dwell_f <= (dwell == 0) ? 16'd1 : dwell; st <= S_RANGE;
            end
            S_RANGE: begin
                if (rc == 0) begin
                    if (last_r) begin frame_done <= 1; frames <= frames + 1; rng <= 0; st <= S_IDLE; end
                    else rng <= rng_next;
                end else begin idx <= frev ? rc - 13'd1 : 13'd0; cnt <= rc; start <= rs; src <= rsrc; first <= 1; st <= S_FETCH; end
            end
            S_FETCH: begin va <= start + idx; st <= S_WAIT; end
            S_WAIT:  st <= S_LOAD;                                           // the RAMs answer
            S_LOAD:  begin
                ebeam <= (frev ? prev_beam : exy[35]) && !first; prev_beam <= exy[35]; egrp <= gnew; ecull <= exy[32]; px <= exy[31:16]; py <= exy[15:0]; pz <= ez[15:0];
                first <= 0; mk <= 0; st <= (mvalid && gnew == mgrp) ? S_M0 : S_MF;
            end
            // the group's matrix: twelve reads through the animator's second port, each landing two clocks later
            S_MF: begin
                maddr <= {2'b10, egrp, mk};
                if (mk >= 4'd2) m[16*(mk - 4'd2) +: 16] <= mdata;
                if (mk == 4'd13) begin mvalid <= 1; mgrp <= egrp; st <= S_M0; end else mk <= mk + 1;
            end
            // the operands of column c are set in one state, their products registered in the next, accumulated in the one after
            S_M0: begin a0 <= me(m, 0); a1 <= me(m, 3); a2 <= me(m, 6); b <= px; va <= start + idx_next; st <= S_M1; end   // the next vertex read meanwhile
            S_M1: begin m0q <= m0; m1q <= m1; m2q <= m2; a0 <= me(m, 1); a1 <= me(m, 4); a2 <= me(m, 7); b <= py; st <= S_M2; end
            S_M2: begin acc0 <= m0q; acc1 <= m1q; acc2 <= m2q; m0q <= m0; m1q <= m1; m2q <= m2; a0 <= me(m, 2); a1 <= me(m, 5); a2 <= me(m, 8); b <= pz; st <= S_M3; end
            S_M3: begin acc0 <= acc0 + m0q; acc1 <= acc1 + m1q; acc2 <= acc2 + m2q; m0q <= m0; m1q <= m1; m2q <= m2; st <= S_NORM; end
            S_NORM: begin
                acc0 <= acc0 + m0q; acc1 <= acc1 + m1q; acc2 <= acc2 + m2q;
                if (ecull && z_sum[33]) begin                                // hidden: not drawn, not sent; the next visible point jumps
                    hidden_q <= 1;
                    if (!last_v) begin idx <= idx_next; st <= S_LOAD; end   // read at S_M0
                    else if (!last_r) begin rng <= rng_next; st <= S_RANGE; end
                    else begin frame_done <= 1; frames <= frames + 1; rng <= 0; st <= S_IDLE; end
                end else st <= S_PERSP;
            end
            S_PERSP: begin
                qx <= clip16((acc0 >>> 14) + me(m, 9)); qy <= clip16((acc1 >>> 14) + me(m, 10)); qz <= clip16((acc2 >>> 14) + me(m, 11));
                st <= S_PROJ;
            end
            S_PROJ: begin sc <= persp[(qz[15:0] + 16'd32768) >> 7]; st <= S_MULT; end    // the table's read lands next cycle
            S_MULT: begin prxq <= prx; pryq <= pry; st <= S_EMIT; end                        // the products, registered
            S_EMIT: if (fifo_room) begin
                if (!(ebeam && !hidden_q) && !hold_now) begin
                    // a jump: kept, and replaced by the next jump if no drawn segment comes first (the beam would only
                    // visit the point and leave it); a frame's trailing jump is replaced by the next frame's first
                    pend <= {clip12(cx), clip12(cy)}; pend_v <= 1; hidden_q <= 0;
                    if (!last_v) begin idx <= idx_next; st <= S_LOAD; end
                    else if (!last_r) begin rng <= rng_next; st <= S_RANGE; end
                    else begin frame_done <= 1; frames <= frames + 1; rng <= 0; st <= S_IDLE; end
                end else if (pend_v) begin
                    pdata <= {2'b00, pend}; push <= 1; pend_v <= 0;                      // the jump first, this segment next clock
                end else begin
                    pdata <= {hold_now, ebeam && !hidden_q, clip12(cx), clip12(cy)}; push <= 1; hidden_q <= 0;
                    if (idx + 1 == cnt && src != 2'd0 && !hold_now) hold_now <= 1;      // a ring's last point once more, with the hold
                    else begin
                        hold_now <= 0;
                        if (!last_v) begin idx <= idx_next; st <= S_LOAD; end
                        else if (!last_r) begin rng <= rng_next; st <= S_RANGE; end
                        else begin frame_done <= 1; frames <= frames + 1; rng <= 0; st <= S_IDLE; end
                    end
                end
            end
            default: st <= S_IDLE;
        endcase
    end
    // ---- the line generator ----
    // The next segment is prepared while the current one draws (three register stages: the difference,
    // its magnitude's leading one, the increments), from the current segment's exact end point, which
    // the position snaps to when a segment completes.  Codes are Q12.8 in flight.
    reg signed [20:0] lx = 21'd2048 << 8, ly = 21'd2048 << 8;
    reg [11:0] tx = 12'd2048, ty = 12'd2048;                      // the current segment's target (exact)
    reg signed [20:0] ix = 0, iy = 0; reg [11:0] sub = 0; reg [15:0] dc = 0; reg busy = 0;
    reg vis = 0;                                                  // drawing: from a frame's first segment until it has drained
    reg [5:0] starve = 0;                                         // samples the generator has waited for a segment
    assign x = lx[19:8]; assign y = vis ? ly[19:8] : 12'd0;      // parked below the screen between frames
    // preparation: stage 1 takes the FIFO head and the current target
    reg p1v = 0, p2v = 0, p3v = 0; reg p1on = 0, p2on = 0, p3on = 0; reg p1h = 0, p2h = 0, p3h = 0; reg holding = 0;
    reg [11:0] p1x = 0, p1y = 0, p2x = 0, p2y = 0, p3x = 0, p3y = 0;
    reg signed [13:0] p1dx = 0, p1dy = 0, p2dx = 0, p2dy = 0; reg [12:0] p1ax = 0, p1ay = 0; reg [12:0] p2d = 0; reg [3:0] p2l = 0, p3k = 0;
    reg signed [20:0] p3ix = 0, p3iy = 0;
    function [3:0] lead1(input [12:0] v); integer i; begin lead1 = 0; for (i = 0; i < 13; i = i + 1) if (v[i]) lead1 = i; end endfunction
    wire take = !p1v && (fn_q != 0) && !(p2v || p3v);            // one segment in preparation at a time (so takes are 3+ clocks apart)
    assign pop = take;
    wire [3:0] p2kr = (lead1(p2d) > step_shift) ? lead1(p2d) - step_shift : 4'd0;
    wire [3:0] p2k = p2on ? ((p2kr < min_k) ? min_k : p2kr) : 4'd0;
    reg busy_done = 0;
    wire load = busy_done;                                        // the generator takes the prepared segment
    always @(posedge clk) begin
        if (abort) begin p1v <= 0; p2v <= 0; p3v <= 0; end
        else begin
        // stage 1: the difference from the last target to the next (both exact)
        if (take) begin
            p1v <= 1; p1on <= head[24]; p1h <= head[25]; p1x <= head[23:12]; p1y <= head[11:0];
            p1dx <= $signed({2'b0, head[23:12]}) - $signed({2'b0, tx}); p1dy <= $signed({2'b0, head[11:0]}) - $signed({2'b0, ty});
        end else if (p1v && !p2v) p1v <= 0;
        // stage 2: the magnitude and its leading one
        if (p1v && !p2v) begin
            p2v <= 1; p2on <= p1on; p2h <= p1h; p2x <= p1x; p2y <= p1y; p2dx <= p1dx; p2dy <= p1dy;
            p1ax <= p1dx[13] ? -p1dx : p1dx; p1ay <= p1dy[13] ? -p1dy : p1dy;
        end else if (p2v && !p3v) p2v <= 0;
        if (p2v && !p3v) begin
            p3v <= 1; p3on <= p2on; p3h <= p2h; p3x <= p2x; p3y <= p2y; p3k <= p2k;
            p3ix <= $signed({p2dx, 8'b0}) >>> p2k; p3iy <= $signed({p2dy, 8'b0}) >>> p2k;
        end else if (p3v && load) p3v <= 0;
        end
    end
    always @(*) p2d = (p1ax > p1ay) ? p1ax : p1ay;
    assign drained = (st == S_IDLE) && fifo_empty && !p1v && !p2v && !p3v && !busy;
    // the draw
    always @(posedge clk) begin
        busy_done <= 0;
        if (abort) begin busy <= 0; vis <= 0; end
        else if (upd) begin
            if (!busy) begin
                if (!p3v) begin
                    if (starve != 6'd63) starve <= starve + 1;
                    if ((st == S_IDLE && idle_n == IDLE_PARK && fifo_empty && !p1v && !p2v) || starve + 1 >= STARVE_PARK) vis <= 0;   // drawn and no frame follows, or starved: park
                end
                if (p3v) begin
                    vis <= 1; starve <= 0;
                    ix <= p3ix; iy <= p3iy; beam <= p3on; tx <= p3x; ty <= p3y;
                    lx <= lx + p3ix; ly <= ly + p3iy;
                    sub <= p3h ? 12'd1 : (12'd1 << p3k) - 12'd1; dc <= 0; busy <= (p3k != 0) || p3h; holding <= p3h; busy_done <= 1;
                    if (p3k == 0) begin lx <= {1'b0, p3x, 8'b0}; ly <= {1'b0, p3y, 8'b0}; end
                end
            end else begin
                if (dc + 1 >= (holding ? hold_n : dwell_f)) begin
                    dc <= 0;
                    if (sub == 1) begin busy <= 0; lx <= {1'b0, tx, 8'b0}; ly <= {1'b0, ty, 8'b0}; end   // snap to the exact end
                    else begin lx <= lx + ix; ly <= ly + iy; end
                    sub <= sub - 1;
                end else dc <= dc + 1;
            end
        end
    end
endmodule
