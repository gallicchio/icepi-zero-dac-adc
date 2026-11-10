// The show's sequencer and its per-mode tables, for top_icepi.v (the X board runs both;
// the Y board gets the mode, the finale and the dwell from the burst and uses show_ranges alone).
//
// show_seq: the mode (1 the seal with the 3D globe, still and then turning, 2 the seal turning over, 3 a finale; any
// other the host's, not in the show), each for its time (modes 1 and 2 from the host registers, defaulting to
// show_params.vh; a finale's from show_finales.vh), the finale index advancing
// each time: 1, 2, then PER_SEAL finales one after another (2026-11-09, Jason: the seal after every three), 1, ...  The
// show starts in mode 1 at power-up.  BTN0 (`next`) goes on now; `hold` stops the
// clock.  With `auto` off the host's mode and finale are taken.  The dwell is DWELL_FULL unless the host writes one.
// Mode 1 starts with the globe's spin held at zero for GLOBE_HOLD_MS (`zero` kept on for it): the 3D globe comes in
// still, upright and facing as the seal's engraved globe does, and then turns.  (Until 2026-11-09 the show began with
// the seal as traced, its globe the engraving, in a mode 0: the change to the wireframe looked jarring, Jason's call,
// so it went, and the engraved globe with it.)
module show_seq (
    input  wire        clk,
    input  wire        ms,              // a millisecond
    input  wire        auto,
    input  wire        hold,
    input  wire        next,
    input  wire [3:0]  mode_h,
    input  wire [4:0]  fin_h,
    input  wire [15:0] dur1, dur2,
    input  wire        dwell_ws, input wire [15:0] dwell_h,
    output reg  [3:0]  mode = 4'd1,
    output reg  [4:0]  fin = 5'd0,
    output reg  [15:0] dwell,
    output reg         mode_enter = 1'b0,
    output reg  [31:0] zero = 32'd0,     // one clock on entering a mode or a finale: the phases that start from zero
    output reg  [31:0] ramp_w = 32'd0    // the spinner's phase rate (phase 15, a turn = 2^32 a millisecond): see below
);
    `include "scene_layout.vh"
    `include "matrix_prog.vh"
    `include "show_params.vh"
    `include "show_finales.vh"
    initial dwell = DWELL_FULL;
    reg [31:0] ms_in = 0; reg [3:0] mode_q = 4'd15; reg [4:0] fin_q = 5'd31;
    reg [2:0] cnt = 3'd0;               // the finales shown since the seal: PER_SEAL of them, then the seal again
    wire [15:0] dur = (mode == 1) ? dur1 : (mode == 2) ? dur2 : fin_dur(fin);
    reg [15:0] spin_hold = 16'd0;       // ms left of the globe's still start in mode 1
    wire [4:0] fin_next = (fin + 1 >= NF) ? 5'd0 : fin + 1;
    wire entering = (mode != mode_q) || (mode == 4'd3 && fin != fin_q);
    // the spinner's ramp: from the finale's start, each millisecond the phase goes on by ramp_w (in matrix_unit) and then
    // ramp_w is 0 for RAMP_T0 ms, grows by RAMP_UP for RAMP_T1 ms (the flick) and falls by RAMP_DN to 0 (it coasts to a stop)
    reg [15:0] rtm = 16'd0;
    always @(posedge clk) begin
        mode_enter <= 0; zero <= 32'd0;
        if (!auto) begin mode <= mode_h; fin <= fin_h; ms_in <= 0; cnt <= 3'd0; end
        else if (next || (ms && !hold && ms_in + 1 >= {16'b0, dur})) begin
            ms_in <= 0;
            if (mode == 4'd3) begin fin <= fin_next; if (cnt + 1 < PER_SEAL) cnt <= cnt + 1; else begin mode <= 1; cnt <= 3'd0; end end
            else if (mode >= 4'd4 || mode == 4'd0) begin mode <= 1; cnt <= 3'd0; end
            else begin mode <= mode + 1; cnt <= 3'd0; end
        end
        else if (ms && !hold) ms_in <= ms_in + 1;
        // entering a mode or a finale, the phases that start from zero: the seal's turn in modes 1 and 2, and in mode 1 the
        // globe's spin too, so it always starts facing as the seal's engraved globe does, and stays there for GLOBE_HOLD_MS;
        // a finale's own (its walker, its message, its pendulums let go together)
        if (entering) begin mode_q <= mode; fin_q <= fin; mode_enter <= 1;
                            zero <= (mode == 1) ? (EN_FLIP & ~EN_ALWAYS) | ZERO_GLOBE : (mode == 2) ? EN_FLIP & ~EN_ALWAYS : (mode == 3) ? fin_zero(fin) : 32'd0;
                            spin_hold <= (mode == 1) ? GLOBE_HOLD_MS : 16'd0; rtm <= 16'd0; ramp_w <= 32'd0; end
        else begin
            if (spin_hold != 0) begin zero <= ZERO_GLOBE; if (ms && !hold) spin_hold <= spin_hold - 1; end
            if (ms && !hold && mode == 4'd3 && fin_ramp(fin)) begin
                if (rtm != 16'hffff) rtm <= rtm + 1;
                ramp_w <= (rtm < RAMP_T0) ? 32'd0 : (rtm < RAMP_T0 + RAMP_T1) ? ramp_w + RAMP_UP : (ramp_w > RAMP_DN) ? ramp_w - RAMP_DN : 32'd0;
            end
        end
        // the dwell: DWELL_FULL, or the host's (it lasts until the next change of mode)
        if (dwell_ws) dwell <= (dwell_h == 0) ? 16'd1 : dwell_h;
        else if (mode_enter) dwell <= DWELL_FULL;
    end
endmodule

// show_ranges: what a mode draws (up to three ranges of the scene memory or the ring), which phases advance, and
// where the animator's program starts.  The finales' table is show_finales.vh (written by make_show.py from its
// FINALES list), over the scene layout (scene_layout.vh) and the program's sections (matrix_prog.vh).
module show_ranges (
    input  wire [3:0]  mode,
    input  wire [4:0]  fin,
    input  wire [10:0] wp, wp2,         // the rings' write pointers: the tails' oldest points
    input  wire [31:0] rh0, rh1, rh2,   // the host's ranges for its modes (0, 4-15): {src[1:0], 1'b0, count[12:0], 3'b0, start[12:0]}
    output reg  [5:0]  r_src,
    output reg  [38:0] r_start, r_count,
    output reg  [31:0] en,
    output reg  [11:0] pc0
);
    `include "scene_layout.vh"
    `include "matrix_prog.vh"
    `include "show_params.vh"
    `include "show_finales.vh"
    reg [27:0] fr0, fr1, fr2;
    function [12:0] rstart(input [27:0] fr); begin rstart = fr[27] ? {2'b0, wp2} : fr[26] ? {2'b0, wp} : fr[12:0]; end endfunction
    always @(*) begin
        r_src = 6'd0; r_start = 39'd0; r_count = 39'd0; en = EN_ALWAYS; pc0 = PC_SEAL;
        fr0 = fin_range(fin, 2'd0); fr1 = fin_range(fin, 2'd1); fr2 = fin_range(fin, 2'd2);
        case (mode)
            4'd1: begin r_start[12:0] = L_BODY_START; r_count[12:0] = L_BODY_COUNT; r_start[25:13] = L_GLOBE3D_START; r_count[25:13] = L_GLOBE3D_COUNT; end
            4'd2: begin r_start[12:0] = L_BODY_START; r_count[12:0] = L_BODY_COUNT; r_start[25:13] = L_GLOBE3D_START; r_count[25:13] = L_GLOBE3D_COUNT; en = EN_FLIP; end
            4'd3: begin
                r_src = {fr2[27:26], fr1[27:26], fr0[27:26]}; r_count = {fr2[25:13], fr1[25:13], fr0[25:13]};
                r_start = {rstart(fr2), rstart(fr1), rstart(fr0)};
                en = fin_en(fin) | EN_ALWAYS; pc0 = fin_pc(fin);
            end
            default: begin
                r_src = {rh2[31:30], rh1[31:30], rh0[31:30]};
                r_start = {rh2[12:0], rh1[12:0], rh0[12:0]}; r_count = {rh2[28:16], rh1[28:16], rh0[28:16]};
                en = 32'hffffffff;
            end
        endcase
    end
endmodule
