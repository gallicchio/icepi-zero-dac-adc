// The scope show on two Icepi Zero + AD9280/AD9708 stacks (the tutorial's 5.08): the same vector engine, animator,
// sequencer and twins in both boards, one DAC each.  ROLE 0 is
// the X board: it runs the sequencer and starts every period with a burst on its DAC (sync_tx) carrying its state.
// ROLE 1 is the Y board: its ADC sees the X board's DAC through a tee; it decodes the burst (sync_rx), loads the
// state, runs the animator, draws the same frames, and trims its sample rate so the frames stay in step (the burst
// carries the X board's free-running tick count; the Y board compares its advance with its own).  The X board, which
// ran its animator before the burst, waits for as long as that took (plus TX_DELAY, a calibration) before drawing,
// so both first points land together.  Then both draw the period's n frames back to back (n is in the burst): the
// engines run identically, so they stay together, and the beam goes from each frame's last point to the next's first
// as between strokes, parked only for the burst (Jason, 2026-11-09: the park and return at every frame made a vertical
// streak, and the return's overshoot a row of dots above the first point; shear from a long period is the lesser evil).
//
// Cables: A.DAC -> tee -> scope X and B.ADC; B.DAC -> tee -> scope Y (and A.ADC, unused).  The X board's drawing is
// moved up X_OFFSET (to8x), to codes 16..255, so its lowest point stays clear of the burst's gap (code 0) on the Y
// board's ADC; the Y board's spans codes 9..248 (make_show.py's ICEPI_SCREEN_SCALE).
//
// The register bus (regbus.v, 1 Mbaud over the FT231X; host/show.py uses it): 7-bit addresses, 32-bit data.
//   00 ID 0xEC5B5E4C | ROLE  01 BUILD_ID  02 SCRATCH  04 STATUS {frames[31:16], finale[15:11], mode[10:7], 0, btn[1], 1}
//   05 LEDS (W: [8] manual, [4:0] the LEDs)  06 FPS (frames in the last second)
//   10 CTRL [0] run [1] auto (the show's sequence) [2] animate [7:4] mode (when not auto) [8] hold [13:9] finale (when not auto)
//   11 DWELL (W; until the next change of mode)  14 WA (the seal's axis angle rate) 15 WB (its turn rate) 17 WS (the globe's
//      spin), all 2^32 = a turn, per millisecond  1B 1C 1D WLA WLB WLC (the tumble of the twins' tails, Chua's and Lorenz's; the other rates are fixed)
//   18 {T_MODE1_MS[31:16], 0}  1E {0, T_MODE2_MS[15:0]}
//   20 21 22 RANGE0..2 for the host's modes (0, 4-15): {src[31:30] (0 the scene memory, else a twin's ring), 0, count[28:16], 0, start[12:0]}
//   30 MAT (W: {addr[25:16], data[15:0]} into the animator's registers; see host/gen_matrix_prog.py)
//   40 VMEM_ADDR (W, auto-increments on 42)  41 VMEM_XY_LO (W: xy[31:0])  42 VMEM_XY_HI_Z (W: {group[3:2] in [21:20], xy[35:32] in [19:16], z[15:0]}, commits)
//   50 TWIN (Lorenz) {ring_every[27:16], step_ticks[15:0]}  52 LOAD (W)  53 54 55 KX KY KZ  56 OFF_Z
//   57 TWIN2 (Chua) {ring_every2[27:16], step_ticks2[15:0]}  58 LOAD2 (W)  59 5A 5B KX2 KY2 KZ2  5C HOLD (samples on a tail's last point)
// and for the two boards' link and the bench:
//   08 SYNC {bad[31:16], good[15:0]}  09 LEVELS {interval[31:16] (low half), hi[15:8], lo[7:0]}  0A TRIM (the Y board's rate, 2^31 nominal)
//   19 TX_DELAY (signed ticks added to the X board's wait after its burst; show_params.vh's TX_DELAY; trim it on the scope)  1A THR_GAP (the gap threshold in ADC codes; show_params.vh's THR_GAP, from the measured DAC -> ADC transfer)
//   1F SYNC_TICKS (the X board: the period between bursts in ticks of 40 ns; show_params.vh's SYNC_TICKS)  12 {min_k[7:4], step_shift[3:0]}
//   0B ADC {max[15:8], min[7:0]} of this board's own ADC over the last millisecond (what it sees of the other board's DAC)
//   0C DAC_FORCE [8] on, [7:0] the code: the DAC holds that code instead of the show (for checking the cables)
//   0D RING_WRITES {ring 2's writes[15:0], ring 1's[15:0]} since power-up  0E RING1 {wp[26:16], every[11:0]}  0F RING2 the same
//   03 TWIN_DIFF (Y board) at the last burst, its Lorenz twin's x minus the burst's, Q14.24 >> 8  07 the same for the Chua twin
module top_icepi #(parameter ROLE = 0, BUILD_ID = 32'h20261108, UART_DIV = 50) (
    input  wire       clk,              // 50 MHz
    output wire [4:0] led,
    input  wire       btn,
    output wire       uart_tx,
    input  wire       uart_rx,
    input  wire [7:0] adc_d,
    output wire       adc_clk,
    output reg  [7:0] dac_d = 8'd128,
    output wire       dac_clk
);
    `include "scene_layout.vh"
    `include "show_params.vh"
    localparam W = 920;                  // the burst's payload
    // the engine's 12-bit codes to the 8-bit DAC, rounded: code k covers 16k - 8 .. 16k + 7, so the screen's centre line (2048,
    // where the upright globe's equator lies) is in the middle of code 128, not on the edge between 127 and 128
    function [7:0] to8(input [11:0] v); reg [12:0] r; begin r = {1'b0, v} + 13'd8; to8 = r[12] ? 8'd255 : r[11:4]; end endfunction
    // the X board's: the same, X_OFFSET higher (show_params.vh), so the drawing uses codes 16..255
    function [7:0] to8x(input [11:0] v); reg [13:0] r; begin r = {2'b0, v} + {2'b0, X_OFFSET} + 14'd8; to8x = (r[13:12] != 2'b0) ? 8'd255 : r[11:4]; end endfunction
    // ---- the register bus ----
    wire [7:0] rx_data, tx_data; wire rx_valid, tx_start, tx_busy;
    uart_rx #(.DIV(UART_DIV)) urx (.clk(clk), .rx(uart_rx), .data(rx_data), .valid(rx_valid));
    uart_tx #(.DIV(UART_DIV)) utx (.clk(clk), .data(tx_data), .start(tx_start), .busy(tx_busy), .tx(uart_tx));
    wire [6:0] addr; wire [31:0] wdata; wire we; reg [31:0] rdata; wire bus_active;
    regbus bus (.clk(clk), .rx_data(rx_data), .rx_valid(rx_valid), .tx_data(tx_data), .tx_start(tx_start), .tx_busy(tx_busy),
                .addr(addr), .wdata(wdata), .we(we), .rdata(rdata), .dump_len(16'd0), .dump_addr(), .dump_data(32'd0), .active(bus_active));
    reg [31:0] scratch = 0; reg [8:0] leds_r = 0;
    reg [13:0] ctrl = 14'b00000_0_0000_0111; reg [15:0] dwell_h = DWELL_FULL; reg dwell_hw = 0; reg [3:0] step_shift = STEP_SHIFT, min_k = MIN_K; reg [31:0] sync_ticks = SYNC_TICKS;
    reg [31:0] wa = W_AXIS, wb = W_FLIP, ws = W_SPIN, wla = W_LA, wlb = W_LB, wlc = W_LC;
    reg [31:0] dur01 = {T_MODE1_MS[15:0], 16'd0}, dur23 = {16'd0, T_MODE2_MS[15:0]};
    reg [31:0] range_h [0:2]; initial begin range_h[0] = 0; range_h[1] = 0; range_h[2] = 0; end
    reg [25:0] mat_w = 0; reg mat_we = 0; reg [12:0] vaddr_h = 0; reg [35:0] vxy_h = 0; reg [17:0] vz_h = 0; reg vmem_we = 0;
    reg [15:0] step_ticks = STEP_PERIOD; reg [11:0] ring_every = RING_EVERY; reg signed [31:0] off_z = 25 << 24; reg load_w = 0;
    reg [15:0] kx = KX, ky = KY, kz = KZ; reg signed [15:0] tx_delay = TX_DELAY; reg [7:0] thr_gap = THR_GAP; reg [8:0] dac_force = 9'd0;
    reg [7:0] adc_max = 0, adc_min = 0, mx_acc = 8'd0, mn_acc = 8'd255; reg [15:0] adc_ms = 0;
    reg [15:0] step_ticks2 = STEP_PERIOD2; reg [11:0] ring_every2 = RING_EVERY2; reg load2_w = 0; reg [15:0] kx2 = KX2, ky2 = KY2, kz2 = KZ2; reg [15:0] hold_h = TAIL_HOLD;
    wire [15:0] frames, fps; wire [15:0] good, bad; wire [7:0] lo, hi; wire [31:0] interval; wire [31:0] trim;
    wire [3:0] mode; wire [4:0] fin; wire [15:0] dwell, dwell_eng;
    reg btn_q = 0; always @(posedge clk) btn_q <= ~btn;
    always @(posedge clk) begin
        dwell_hw <= 0; mat_we <= 0; vmem_we <= 0; load_w <= 0; load2_w <= 0;
        if (we) case (addr)
            7'h02: scratch <= wdata;  7'h05: leds_r <= wdata[8:0];  7'h10: ctrl <= wdata[13:0];
            7'h11: begin dwell_h <= wdata[15:0]; dwell_hw <= 1; end  7'h12: begin step_shift <= wdata[3:0]; min_k <= wdata[7:4]; end  7'h1f: sync_ticks <= wdata;
            7'h14: wa <= wdata; 7'h15: wb <= wdata; 7'h17: ws <= wdata;  7'h18: dur01 <= wdata;  7'h1e: dur23 <= wdata;
            7'h1b: wla <= wdata; 7'h1c: wlb <= wdata; 7'h1d: wlc <= wdata;
            7'h19: tx_delay <= wdata[15:0];  7'h1a: thr_gap <= wdata[7:0];  7'h0c: dac_force <= wdata[8:0];
            7'h20: range_h[0] <= wdata; 7'h21: range_h[1] <= wdata; 7'h22: range_h[2] <= wdata;
            7'h30: begin mat_w <= wdata[25:0]; mat_we <= 1; end
            7'h40: vaddr_h <= wdata[12:0];  7'h41: vxy_h[31:0] <= wdata;  7'h42: begin vxy_h[35:32] <= wdata[19:16]; vz_h <= {wdata[21:20], wdata[15:0]}; vmem_we <= 1; end
            7'h50: begin step_ticks <= wdata[15:0]; ring_every <= wdata[27:16]; end  7'h52: load_w <= 1;
            7'h53: kx <= wdata[15:0]; 7'h54: ky <= wdata[15:0]; 7'h55: kz <= wdata[15:0]; 7'h56: off_z <= wdata;
            7'h57: begin step_ticks2 <= wdata[15:0]; ring_every2 <= wdata[27:16]; end  7'h58: load2_w <= 1;
            7'h59: kx2 <= wdata[15:0]; 7'h5a: ky2 <= wdata[15:0]; 7'h5b: kz2 <= wdata[15:0]; 7'h5c: hold_h <= wdata[15:0];
            default: ;
        endcase
        if (vmem_we) vaddr_h <= vaddr_h + 1;
    end
    reg [11:0] every = 0, every2 = 0; reg [10:0] wp = 0, wp2 = 0; reg [15:0] nw1 = 0, nw2 = 0;   // the rings' state (the writer below), for the host too
    reg [31:0] twin_diff1 = 0, twin_diff2 = 0;                                                   // the Y board's twins against the burst (debug)
    always @(*) case (addr)
        7'h00: rdata = 32'hEC5B5E4C | ROLE;  7'h01: rdata = BUILD_ID;  7'h02: rdata = scratch;
        7'h04: rdata = {frames, fin, mode, 5'b0, btn_q, 1'b1};  7'h05: rdata = {23'b0, leds_r};  7'h06: rdata = {16'b0, fps};
        7'h08: rdata = {bad, good};  7'h09: rdata = {interval[15:0], hi, lo};  7'h0a: rdata = trim;  7'h0b: rdata = {16'b0, adc_max, adc_min};  7'h0c: rdata = {23'b0, dac_force};
        7'h03: rdata = twin_diff1;  7'h07: rdata = twin_diff2;  7'h0d: rdata = {nw2, nw1};  7'h0e: rdata = {5'b0, wp, 4'b0, every};  7'h0f: rdata = {5'b0, wp2, 4'b0, every2};
        7'h10: rdata = {18'b0, ctrl};  7'h11: rdata = {16'b0, dwell_h};  7'h12: rdata = {24'b0, min_k, step_shift};  7'h1f: rdata = sync_ticks;
        7'h14: rdata = wa;  7'h15: rdata = wb;  7'h17: rdata = ws;  7'h18: rdata = dur01;  7'h1e: rdata = dur23;  7'h19: rdata = {{16{tx_delay[15]}}, tx_delay};
        7'h1b: rdata = wla;  7'h1c: rdata = wlb;  7'h1d: rdata = wlc;
        7'h20: rdata = range_h[0];  7'h21: rdata = range_h[1];  7'h22: rdata = range_h[2];
        7'h50: rdata = {4'b0, ring_every, step_ticks};  7'h57: rdata = {4'b0, ring_every2, step_ticks2};  7'h5c: rdata = {16'b0, hold_h};
        default: rdata = 32'd0;
    endcase

    // ---- the sample tick: one in two clocks, the Y board's trimmed by the loop below ----
    reg [31:0] acc = 0; reg tick = 0; reg [31:0] rate = 32'h8000_0000;
    always @(posedge clk) begin {tick, acc} <= {1'b0, acc} + {1'b0, rate}; end
    assign trim = rate;
    // ---- the ADC, as capture.sv: 25 MHz, the sample grabbed as its clock is about to rise ----
    reg adc_clk_r = 0, sample = 0; reg [7:0] adc = 0;
    always @(posedge clk) begin adc_clk_r <= ~adc_clk_r; sample <= 0; if (!adc_clk_r) begin adc <= adc_d; sample <= 1; end end
    assign adc_clk = adc_clk_r;
    assign dac_clk = ~clk;
    // the ADC's range over each millisecond, for the host (register 0B)
    always @(posedge clk) begin
        if (adc_ms == 16'd49_999) begin adc_ms <= 0; adc_max <= mx_acc; adc_min <= mn_acc; mx_acc <= 8'd0; mn_acc <= 8'd255; end
        else begin adc_ms <= adc_ms + 1; if (sample) begin if (adc > mx_acc) mx_acc <= adc; if (adc < mn_acc) mn_acc <= adc; end end
    end

    // ---- the twin, free-running, and its ring ----
    wire mat_ws = mat_we, vmem_ws = vmem_we, load_s = load_w, dwell_ws = dwell_hw;      // one clock domain here
    reg [15:0] stepc = 0; reg step = 0; wire busy;
    // the step clocks: the Y board takes the X board's phase from each burst (ld_steps), so its twins replay the X board's
    // steps at the same times relative to the capture and write the same ring points before its next reload
    reg ld_steps = 1'b0; reg [15:0] ld_stepc = 0, ld_stepc2 = 0;
    always @(posedge clk) begin step <= 0; if (ld_steps) stepc <= ld_stepc; else if (tick) begin if (stepc >= step_ticks - 1) begin stepc <= 0; step <= 1; end else stepc <= stepc + 1; end end
    // the twin's starting point, loaded once after power-up (its state starts at 0, a fixed point of the Lorenz equations)
    reg [7:0] por_c = 8'd0; reg por_load = 1'b0;
    always @(posedge clk) begin por_load <= (por_c == 8'd200); if (por_c != 8'hff) por_c <= por_c + 1; end
    wire signed [37:0] x_t, y_t, z_t, r_t, xa_t, ya_t;
    reg ld_twin = 0; reg signed [37:0] ldx = 0, ldy = 0, ldz = 0;
    lorenz twin (.clk(clk), .rst(1'b0), .step(step && !ld_twin), .busy(busy), .code_a(12'd2048), .code_b(12'd2048), .couple(1'b0), .mode(2'd0),
                 .s(38'sd167772160), .b(38'sd44739243), .g(38'sd0), .gamma(38'sd0), .k_adc(38'sd245760), .r_min(38'sd268435456), .r_max(38'sd738197504),
                 .load(ld_twin | load_s | por_load), .x_in(ld_twin ? ldx : -38'sd83886080), .y_in(ld_twin ? ldy : -38'sd117440512), .z_in(ld_twin ? ldz : 38'sd335544320), .r_in(38'sd469762048),
                 .x(x_t), .y(y_t), .z(z_t), .r(r_t), .xa(xa_t), .ya(ya_t));
    // the rings' state: the Y board takes the X board's at each burst, so both write the same points into the same slots
    reg ring_load = 1'b0; reg [11:0] ld_every = 0, ld_every2 = 0; reg [10:0] ld_wp = 0, ld_wp2 = 0;
    // ---- the second twin, Chua's circuit, and its ring ----
    reg [15:0] stepc2 = 0; reg step2 = 0; wire busy2;
    always @(posedge clk) begin step2 <= 0; if (ld_steps) stepc2 <= ld_stepc2; else if (tick) begin if (stepc2 >= step_ticks2 - 1) begin stepc2 <= 0; step2 <= 1; end else stepc2 <= stepc2 + 1; end end
    wire signed [37:0] x2_t, y2_t, z2_t; reg ld_twin2 = 0; reg signed [37:0] ldx2 = 0, ldy2 = 0, ldz2 = 0;
    chua twin2 (.clk(clk), .step(step2 && !ld_twin2), .load(ld_twin2 | load2_w), .x_in(ld_twin2 ? ldx2 : 38'sd1677722), .y_in(ld_twin2 ? ldy2 : 38'sd0), .z_in(ld_twin2 ? ldz2 : 38'sd0), .busy(busy2), .x(x2_t), .y(y2_t), .z(z2_t));
    // ---- the rings' writer, shared by both twins: every ring_every steps a twin's state is scaled (one multiplier, the
    // three products one after the other) and written to its ring; a point due while the other twin's is being written waits ----
    reg busy_q = 0; wire stepped = busy_q && !busy; always @(posedge clk) busy_q <= busy;
    reg busy2_q = 0; wire stepped2 = busy2_q && !busy2; always @(posedge clk) busy2_q <= busy2;
    reg signed [37:0] zc = 0; reg [2:0] rp = 0, rp2 = 0; reg rw = 0, rw2 = 0;
    reg [35:0] rxy = 0, rxy2 = 0; reg [17:0] rz = 0, rz2 = 0; reg due1 = 0, due2 = 0; reg [2:0] wst = 0; reg wsel = 0;
    reg signed [37:0] ma = 0; reg signed [16:0] mk = 0; reg signed [54:0] mp = 0;
    always @(posedge clk) begin
        rw <= 0; rw2 <= 0; zc <= z_t - {{6{off_z[31]}}, off_z};
        rp <= {rp[1:0], stepped}; rp2 <= {rp2[1:0], stepped2};
        if (ring_load) begin every <= ld_every; every2 <= ld_every2; end
        else begin
        if (rp[2]) begin if (every + 1 >= ring_every) begin every <= 0; due1 <= 1; end else every <= every + 1; end
        if (rp2[2]) begin if (every2 + 1 >= ring_every2) begin every2 <= 0; due2 <= 1; end else every2 <= every2 + 1; end
        end
        mp <= ma * mk;
        case (wst)
            0: if (due1) begin wsel <= 0; due1 <= 0; ma <= x_t; mk <= {1'b0, kx}; wst <= 1; end
               else if (due2) begin wsel <= 1; due2 <= 0; ma <= x2_t; mk <= {1'b0, kx2}; wst <= 1; end
            1: begin ma <= wsel ? y2_t : y_t; mk <= wsel ? {1'b0, ky2} : {1'b0, ky}; wst <= 2; end
            2: begin ma <= wsel ? z2_t : zc; mk <= wsel ? {1'b0, kz2} : {1'b0, kz}; wst <= 3; if (wsel) rxy2[31:16] <= mp[39:24]; else rxy[31:16] <= mp[39:24]; end
            3: begin wst <= 4; if (wsel) rxy2[15:0] <= mp[39:24]; else rxy[15:0] <= mp[39:24]; end
            4: begin
                   wst <= 0;
                   if (wsel) begin rz2 <= {2'b00, mp[39:24]}; rxy2[35:32] <= {1'b1, 2'd2, 1'b0}; rw2 <= 1; wp2 <= wp2 + 1; nw2 <= nw2 + 1; end
                   else begin rz <= {2'b00, mp[39:24]}; rxy[35:32] <= {1'b1, 2'd2, 1'b0}; rw <= 1; wp <= wp + 1; nw1 <= nw1 + 1; end
               end
            default: wst <= 0;
        endcase
        if (ring_load) begin wp <= ld_wp; wp2 <= ld_wp2; end
    end

    // ---- the ranges, the enables and the program start per mode; the animator; the engine ----
    wire [5:0] r_src; wire [38:0] r_start, r_count; wire [31:0] en; wire [11:0] pc0; wire [31:0] ramp_w;
    // the rings are drawn, all period, from the write pointers the period's burst carried (the same on both boards), less
    // the RING_SKIP oldest slots, where the twins write during the period: the Y board's twin replays the X board's a burst
    // (148 us) late, so with the live pointer a frame could start a point further on one board than the other, frames of
    // other lengths, and the boards apart for the rest of the period
    reg [10:0] wp_p = 0, wp2_p = 0;
    show_ranges rng (.mode(mode), .fin(fin), .wp(wp_p + RING_SKIP[10:0]), .wp2(wp2_p + RING_SKIP[10:0]), .rh0(range_h[0]), .rh1(range_h[1]), .rh2(range_h[2]),
                     .r_src(r_src), .r_start(r_start), .r_count(r_count), .en(en), .pc0(pc0));
    reg eng_run = 0; wire eng_tick; wire [11:0] vx, vy; wire vbeam, frame_done, fifo_empty, drained;
    wire anim_done, anim_busy; wire [15:0] anim_cycles; wire [1023:0] ph; wire [9:0] maddr; wire [15:0] mdata;
    reg anim_start = 0, anim_load = 0, ms = 0; wire [31:0] zero; reg [15:0] ms_c = 0; reg [1023:0] lph = 1024'd0;
    wire [1023:0] w_all = {W_PH_FIXED[1023:512], ramp_w, W_PH_FIXED[479:224], wlc, wlb, wla, ws, W_PH_FIXED[95:64], wb, wa};   // phases 0, 1, 3-6 from the registers, 15 the spinner's ramp (the X board's), the rest fixed
    // the X board's phases held still from its animator's start until the burst has taken them (fs 1 to 3, under 0.2 ms; a
    // millisecond tick or a zeroing in that time is applied just after): the animator reads them over its first 224 clocks
    // and the burst took them after the run, so a tick in between gave the Y board a globe a millisecond on, other
    // vertices hidden, frames of another length, and with the frames back to back the boards apart for the rest of the
    // period (a rectangle of spots on the scope, as the globe began to turn)
    reg [3:0] fs = 0; wire ph_freeze = (ROLE == 0) && (fs >= 4'd1) && (fs <= 4'd3);
    reg tick_due = 1'b0; reg [31:0] zero_due = 32'd0;
    always @(posedge clk) begin
        if (ph_freeze) begin if (ms) tick_due <= 1'b1; zero_due <= zero_due | zero; end
        else begin tick_due <= 1'b0; zero_due <= 32'd0; end
    end
    wire tick_ph = (ROLE == 0) && !ph_freeze && (ms || tick_due); wire [31:0] zero_ph = ph_freeze ? 32'd0 : (zero | zero_due);
    matrix_unit #(.PH0(PH0_ALL)) anim (.clk(clk), .start(anim_start), .tick(tick_ph), .en(en), .w(w_all),
                      .zero(zero_ph), .load(anim_load), .lph(lph),
                      .hw(mat_ws), .haddr(mat_w[25:16]), .hdata(mat_w[15:0]), .pc0(pc0), .done(anim_done), .busy(anim_busy), .cycles(anim_cycles), .ph_o(ph),
                      .maddr(maddr), .mdata(mdata));
    reg eng_abort = 0;
    reg [15:0] nrep = 16'd1, nf = 0;     // the period's frames, and this one's number (from 1)
    // the period's frames alternate forwards and backwards (the even ones backwards, on both boards), so each starts where
    // the last ended
    vec3d eng (.clk(clk), .upd(eng_tick), .run(eng_run), .rev(~nf[0]), .abort(eng_abort), .r_src(r_src), .r_start(r_start), .r_count(r_count), .maddr(maddr), .mdata(mdata),
               .step_shift(step_shift), .min_k(min_k), .dwell(dwell_eng), .hold_n(hold_h), .vw(vmem_ws), .vaddr(vaddr_h - 13'd1), .vxy(vxy_h), .vz(vz_h),
               .rw(rw), .raddr(wp), .rxy(rxy), .rz(rz), .rw2(rw2), .raddr2(wp2), .rxy2(rxy2), .rz2(rz2),
               .x(vx), .y(vy), .beam(vbeam), .frame_done(frame_done), .frames(frames), .fifo_empty(fifo_empty), .drained(drained));

    // ---- the frame sequence, per role ----
    reg [15:0] dly = 0;
    // a period: the burst, then n frames back to back (the next started as the engine finishes the last, while the FIFO
    // still holds its end), then the next burst.  The burst and the animator take about 200 us
    reg [31:0] ft = 0; reg [15:0] frame_no = 0; reg sec = 0; reg [15:0] sec_c = 0;
    reg sync_start = 0; wire sync_active, sync_done; wire [7:0] sync_level; wire [W-1:0] sy_payload; wire sy_valid, sy_in_burst;
    reg [15:0] fcount = 0, fps_r = 0; assign fps = fps_r;
    reg btn_s = 0, btn_s2 = 0; always @(posedge clk) begin btn_s <= btn_q; btn_s2 <= btn_s; end
    wire next = btn_s && !btn_s2;
    always @(posedge clk) begin
        ms <= 0; sec <= 0;
        if (ms_c == 16'd49_999) begin ms_c <= 0; ms <= 1; if (sec_c == 16'd999) begin sec_c <= 0; sec <= 1; end else sec_c <= sec_c + 1; end else ms_c <= ms_c + 1;
        if (sec) begin fps_r <= fcount; fcount <= 0; end else if (frame_done) fcount <= fcount + 1;
    end
    generate if (ROLE == 0) begin : xrole
        // the X board: the sequencer, then per period: the animator, the burst, the wait, the frame and its repeats
        wire mode_enter; wire [3:0] mode_s; wire [4:0] fin_s;
        show_seq seq (.clk(clk), .ms(ms), .auto(ctrl[1]), .hold(ctrl[8]), .next(next), .mode_h(ctrl[7:4]), .fin_h(ctrl[13:9]),
                      .dur1(dur01[31:16]), .dur2(dur23[15:0]), .dwell_ws(dwell_ws), .dwell_h(dwell_h),
                      .mode(mode_s), .fin(fin_s), .dwell(dwell), .mode_enter(mode_enter), .zero(zero), .ramp_w(ramp_w));
        // the mode and finale for a whole period, taken as it starts: the animator's section, the burst and the ranges agree
        // (a change between the animator and the burst gave a period of one finale's matrices on another's vertices)
        reg [3:0] mode_p = 4'd0; reg [4:0] fin_p = 5'd0; assign mode = mode_p; assign fin = fin_p;
        wire signed [16:0] wait_ticks = $signed({2'b00, anim_cycles[15:1]}) + {tx_delay[15], tx_delay};
        reg [15:0] dwell_fr = DWELL_FULL;                 // the period's dwell: a change (the host's) waits for the next period
        assign dwell_eng = dwell_fr;
        // n for the next period: the frames of the last period's length (f: between its last two frames' ends, or its one
        // frame's start to drained) that fit in sync_ticks, by a 16-step divider while the animator runs; 1 after a change of
        // mode or finale, whose frames are of another length
        reg [31:0] f_last = 0, t_done = 0; reg chg = 1'b1; reg dv_start = 0, dv_busy = 0; reg [3:0] dv_i = 0; reg [47:0] dv_rem = 0, dv_sub = 0; reg [15:0] n_q = 0;
        always @(posedge clk) begin
            if (dv_start) begin dv_rem <= {16'b0, sync_ticks}; dv_sub <= {1'b0, f_last, 15'b0}; n_q <= 0; dv_i <= 4'd15; dv_busy <= (f_last != 0); end
            else if (dv_busy) begin
                if (dv_rem >= dv_sub) begin dv_rem <= dv_rem - dv_sub; n_q[dv_i] <= 1'b1; end
                dv_sub <= dv_sub >> 1;
                if (dv_i == 0) dv_busy <= 0; else dv_i <= dv_i - 1;
            end
        end
        always @(posedge clk) begin
            anim_start <= 0; sync_start <= 0; eng_run <= 0; dv_start <= 0;
            if (tick) ft <= ft + 1;
            if (sync_start) begin wp_p <= wp; wp2_p <= wp2; end                  // as the burst takes them
            case (fs)
                0: if (ctrl[0]) begin
                       chg <= (mode_s != mode_p) || (fin_s != fin_p); mode_p <= mode_s; fin_p <= fin_s;
                       anim_start <= ctrl[2]; fs <= ctrl[2] ? 4'd1 : 4'd2;
                   end
                1: if (anim_done) fs <= 2;
                2: if (!dv_busy && !dv_start) begin
                       sync_start <= 1; fs <= 3; dwell_fr <= dwell;
                       nrep <= (chg || n_q == 0) ? 16'd1 : (n_q > 16'd4095) ? 16'd4095 : n_q;
                   end
                3: if (sync_done) begin dly <= 0; fs <= 4; end
                4: if (tick) begin if ($signed({1'b0, dly}) + 17'sd1 >= wait_ticks) fs <= 5; else dly <= dly + 1; end
                5: begin eng_run <= 1; ft <= 0; t_done <= 0; nf <= 16'd1; fs <= 6; end   // the period's first frame, a one-clock start
                6: if (frame_done) begin
                       frame_no <= frame_no + 1; t_done <= ft;
                       if (nf != 1) f_last <= ft - t_done;
                       if (nf < nrep) begin eng_run <= 1; nf <= nf + 1; end              // the next at once: the FIFO holds this one's end
                       else fs <= 7;
                   end
                7: if (drained) begin if (nrep == 1) f_last <= ft; dv_start <= 1; fs <= 0; end   // all on the scope (and parked): the next period
                default: fs <= 0;
            endcase
        end
        wire [511:0] ph16; genvar k;
        for (k = 0; k < 32; k = k + 1) begin : p16 assign ph16[16*k +: 16] = ph[32*k + 16 +: 16]; end
        reg [31:0] tcount = 0; always @(posedge clk) if (tick) tcount <= tcount + 1;      // free-running: the Y board differences it
        // the step counters as the Y board should take them: a step under way (or just issued) is sent as due now, since the
        // twin state sent is the one before it
        wire [15:0] stepc_cap = (busy || step) ? step_ticks - 16'd1 : stepc, stepc2_cap = (busy2 || step2) ? step_ticks2 - 16'd1 : stepc2;
        wire [W-1:0] payload = {4'b1010, nrep, frame_no, mode, fin, dwell_fr, tcount, every, wp, every2, wp2, 1'b0, stepc_cap, stepc2_cap, ph16, x_t, y_t, z_t, x2_t, y2_t, z2_t, 8'd0};
        sync_tx #(.W(W)) stx (.clk(clk), .tick(tick), .start(sync_start), .payload(payload), .active(sync_active), .level(sync_level), .done(sync_done));
        assign eng_tick = tick && !sync_active;
        always @(posedge clk) dac_d <= dac_force[8] ? dac_force[7:0] : sync_active ? sync_level : to8x(vx);
        assign sy_valid = 0; assign sy_payload = 0; assign sy_in_burst = 0; assign good = 0; assign bad = 0; assign lo = 0; assign hi = 0; assign interval = 0;
    end else begin : yrole
        // the Y board: wait for a burst, load its state, run the animator, draw the frame; trim the tick rate
        sync_rx #(.W(W)) srx (.clk(clk), .sample(sample), .adc(adc), .thr_gap(thr_gap), .payload(sy_payload), .valid(sy_valid), .in_burst(sy_in_burst),
                     .lo(lo), .hi(hi), .interval(interval), .bad(bad), .good(good));
        reg [3:0] mode_y = 0; reg [4:0] fin_y = 0; reg [15:0] dwell_y = DWELL_FULL;
        assign mode = mode_y; assign fin = fin_y; assign dwell = dwell_y; assign dwell_eng = dwell_y; assign zero = 32'd0; assign ramp_w = 32'd0;
        reg [31:0] tcount_y = 0, x_prev = 0, y_prev = 0, nlat = 0; reg signed [31:0] err = 0; reg have_prev = 0, upd_rate = 0, upd2 = 0, upd3 = 0; reg [4:0] sh = 0;
        reg signed [31:0] err_acc = 0, err_app = 0; reg [31:0] n_acc = 0;
        function [4:0] lead1(input [31:0] v); integer i; begin lead1 = 0; for (i = 0; i < 32; i = i + 1) if (v[i]) lead1 = i; end endfunction
        wire [31:0] err_abs = err[31] ? -err : err;
        always @(posedge clk) begin ring_load <= sy_valid; ld_steps <= sy_valid; end
        genvar k;
        for (k = 0; k < 32; k = k + 1) begin : p16 always @(posedge clk) if (sy_valid) lph[32*k +: 32] <= {sy_payload[236 + 16*k +: 16], 16'd0}; end
        always @(posedge clk) begin
            anim_start <= 0; anim_load <= 0; ld_twin <= 0; ld_twin2 <= 0; eng_run <= 0; upd_rate <= 0; eng_abort <= 0; upd2 <= 0; upd3 <= 0;
            if (tick) tcount_y <= tcount_y + 1;
            // every burst restarts the frame, whatever this board was doing (a frame of its own that ran long is dropped)
            if (sy_valid) begin
                mode_y <= sy_payload[883:880]; fin_y <= sy_payload[879:875]; dwell_y <= sy_payload[874:859]; nrep <= sy_payload[915:900];
                wp_p <= sy_payload[814:804]; wp2_p <= sy_payload[791:781];
                ld_every <= sy_payload[826:815]; ld_wp <= sy_payload[814:804]; ld_every2 <= sy_payload[803:792]; ld_wp2 <= sy_payload[791:781];
                ld_stepc <= sy_payload[779:764]; ld_stepc2 <= sy_payload[763:748];
                ldx <= sy_payload[235:198]; ldy <= sy_payload[197:160]; ldz <= sy_payload[159:122];
                ldx2 <= sy_payload[121:84]; ldy2 <= sy_payload[83:46]; ldz2 <= sy_payload[45:8];
                twin_diff1 <= ($signed(x_t) - $signed(sy_payload[235:198])) >>> 8; twin_diff2 <= ($signed(x2_t) - $signed(sy_payload[121:84])) >>> 8;
                anim_load <= 1; ld_twin <= 1; ld_twin2 <= 1; frame_no <= sy_payload[899:884]; eng_abort <= (fs != 0); fs <= 1;
            end else case (fs)
                0: ;
                1: begin anim_start <= 1; fs <= 2; end
                2: if (anim_done) begin eng_run <= 1; nf <= 16'd1; fs <= 3; end         // the period's first frame, a one-clock start
                3: if (frame_done) begin
                       if (nf < nrep) begin eng_run <= 1; nf <= nf + 1; end              // the X board's n frames, back to back
                       else fs <= 4;
                   end
                4: if (drained) fs <= 0;                                                // parked until the next burst
                default: fs <= 0;
            endcase
            // the trim: the burst carries the X board's free-running tick count; between two bursts its advance minus ours is
            // the error.  Free-running counts, not ones reset at each burst, so the differences telescope: over a window only
            // its two ends are quantized (a counter reset each frame lost or kept a tick depending on the clocks' phase, a bias
            // of up to a tick a frame).  The rate moves by a part of sum(err) / sum(N), so the loop behaves the same for 0.25 ms
            // frames and 2 s ones; a frame's difference over 1000 ppm (a missed or a false burst) is left out; +/-1 % at most
            if (sy_valid) begin
                err <= $signed(sy_payload[858:827] - x_prev) - $signed(tcount_y - y_prev); nlat <= tcount_y - y_prev;
                x_prev <= sy_payload[858:827]; y_prev <= tcount_y; upd_rate <= have_prev; have_prev <= 1;
            end
            // the frames' differences and lengths are summed until 2^18 ticks (10 ms) have passed, so a tick of measurement is
            // 4 ppm whatever the frame length (one 0.25 ms frame alone would make it 160 ppm); each correction is a quarter
            // to a half of the summed fractional difference (2^30 err / 2^lead1(N))
            if (upd_rate && {err_abs, 10'b0} < {10'b0, nlat}) begin err_acc <= err_acc + err; n_acc <= n_acc + nlat; upd2 <= 1; end
            if (upd2 && n_acc[31:18] != 14'd0) begin sh <= 5'd30 - lead1(n_acc); err_app <= err_acc; err_acc <= 0; n_acc <= 0; upd3 <= 1; end
            if (upd3) rate <= rate + (err_app <<< sh);
            if (rate > 32'h8147_AE14) rate <= 32'h8147_AE14; else if (rate < 32'h7EB8_51EC) rate <= 32'h7EB8_51EC;
        end
        assign eng_tick = tick;
        // during the X board's burst the beam is parked at the bottom (code 0, just below the drawing's codes 9..248), so
        // the burst's streak lies along the bottom edge of the picture; the engine parks it there between frames too
        always @(posedge clk) dac_d <= dac_force[8] ? dac_force[7:0] : sy_in_burst ? 8'd0 : to8(vy);
        assign sync_active = 0; assign sync_done = 0; assign sync_level = 0;
    end endgenerate
    assign led = leds_r[8] ? leds_r[4:0] : {vbeam, (ROLE == 1) ? sy_in_burst : sync_active, mode[2:0]};
endmodule
