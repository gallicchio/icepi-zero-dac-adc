// The animator.  32 phases (2^32 = a turn), each advancing by its rate at every `tick` (a millisecond) when its bit
// of `en` is set, so the animation runs in real time whatever the frame rate; `zero` puts the phases in its mask at zero (the
// seal's turn when it is to be seen normally, a finale's walker at the finale's start); `load` sets all 32 (the Y board, from the burst).  At every `start` (a frame)
// the hardware writes the sine, cosine and turn value of every phase into a file of 1024 Q2.14 registers (a block
// RAM, regs_init.hex: the constants and the identity matrices), then runs the microprogram (matrix_prog.hex, 4096 x 36 in another, from
// host/gen_matrix_prog.py, which documents the register map and the instruction set) from `pc0` to END: the
// seal's section, or a finale's.  The matrices for the vector engine are registers 512 + 16 g (group g: R
// row-major, then t); the engine reads them through the RAM's second port (`maddr` / `mdata`).  The host may write
// any register (`hw`).  `done` pulses when the matrices are fresh; `cycles` is the clocks the run took (the X board's
// wait, so the Y board, which runs the same program after the burst, draws in step).
module matrix_unit #(parameter [1023:0] PH0 = 1024'd0) (
    input  wire          clk,
    input  wire          start,
    input  wire          tick,
    input  wire [31:0]   en,
    input  wire [1023:0] w,              // the 32 rates
    input  wire [31:0]   zero,           // one clock: these phases to zero (the seal seen normally; a finale's walker at its start)
    input  wire          load,
    input  wire [1023:0] lph,
    input  wire          hw, input wire [9:0] haddr, input wire signed [15:0] hdata,
    input  wire [11:0]   pc0,
    output reg           done = 1'b0,
    output reg           busy = 1'b0,
    output reg  [15:0]   cycles = 16'd0,
    output wire [1023:0] ph_o,
    input  wire [9:0]    maddr,
    output wire [15:0]   mdata
);
    // ---- the phases ----
    reg [1023:0] ph = PH0;
    wire [31:0] pha [0:31];
    genvar k;
    generate for (k = 0; k < 32; k = k + 1) begin : phs
        always @(posedge clk)
            if (load) ph[32*k +: 32] <= lph[32*k +: 32];
            else if (zero[k]) ph[32*k +: 32] <= 32'd0;
            else if (tick && en[k]) ph[32*k +: 32] <= ph[32*k +: 32] + w[32*k +: 32];
        assign pha[k] = ph[32*k +: 32];
    end endgenerate
    assign ph_o = ph;
    // ---- the memories: the registers (two ports), the program, the sine table ----
    (* no_rw_check *) reg [17:0] v [0:1023]; initial $readmemh("regs_init.hex", v);
    reg [9:0] aaddr = 0; reg awe = 0; reg [17:0] awd = 0, ard = 0, brd = 0;
    always @(posedge clk) begin if (awe) v[aaddr] <= awd; ard <= v[aaddr]; end
    always @(posedge clk) brd <= v[maddr];
    assign mdata = brd[15:0];
    reg [35:0] prog [0:4095]; initial $readmemh("matrix_prog.hex", prog);
    reg [11:0] pc = 0; reg [35:0] ins = 0; always @(posedge clk) ins <= prog[pc];
    reg [15:0] sine [0:1023]; initial $readmemh("sincos.hex", sine);
    reg [9:0] lidx = 0; reg [15:0] lrd = 0; always @(posedge clk) lrd <= sine[lidx];
    // ---- the sequence ----
    reg [3:0] st = 0; reg [5:0] lut_i = 0; reg [4:0] pv_i = 0;
    reg signed [15:0] oa = 0, ob = 0, vd = 0, wval = 0; reg signed [31:0] prod = 0; reg [2:0] op_q = 0; reg [9:0] dst_q = 0, b_q = 0;
    wire [2:0] op = ins[32:30]; wire [9:0] i_dst = ins[29:20], i_a = ins[19:10], i_b = ins[9:0];
    function signed [15:0] sat(input signed [17:0] x); begin sat = x > 18'sd32767 ? 16'sd32767 : x < -18'sd32768 ? -16'sd32768 : x[15:0]; end endfunction
    always @(posedge clk) begin
        done <= 0; awe <= 0;
        if (busy) cycles <= cycles + 1;
        case (st)
            0: begin
                   if (start) begin busy <= 1; cycles <= 0; lut_i <= 0; st <= 1; end
                   else if (hw) begin aaddr <= haddr; awd <= {2'b00, hdata}; awe <= 1; end
               end
            // the 64 table reads: sin and cos of the 32 phases, into v[160 + 2k], v[161 + 2k]
            1: begin lidx <= pha[lut_i[5:1]][31:22] + (lut_i[0] ? 10'd256 : 10'd0); st <= 2; end
            2: st <= 3;
            3: begin
                   aaddr <= 10'd160 + {4'b0, lut_i}; awd <= {2'b00, lrd}; awe <= 1;
                   if (lut_i == 6'd63) begin pv_i <= 0; st <= 12; end else begin lut_i <= lut_i + 1; st <= 1; end
               end
            // the 32 turn values, into v[224 + k]
            12: begin
                   aaddr <= 10'd224 + {5'b0, pv_i}; awd <= {4'b0, pha[pv_i][31:18]}; awe <= 1;
                   if (pv_i == 5'd31) begin pc <= pc0; st <= 4; end else pv_i <= pv_i + 1;
               end
            // the program: a wait for the fetch, then seven clocks an instruction (the operands a, b and the
            // destination's old value read one after the other, the product, the sum saturated, the write)
            4: st <= 5;
            5: begin
                   if (op == 3'd0) begin busy <= 0; done <= 1; st <= 0; end
                   else begin aaddr <= i_a; b_q <= i_b; dst_q <= i_dst; op_q <= op; pc <= pc + 1; st <= 6; end
               end
            6: begin aaddr <= b_q; st <= 7; end
            7: begin oa <= ard[15:0]; aaddr <= dst_q; st <= 8; end
            8: begin ob <= ard[15:0]; lidx <= oa[13:4] + (op_q == 3'd5 ? 10'd256 : 10'd0); st <= 9; end
            9: begin vd <= ard[15:0]; prod <= oa * ob; st <= 10; end
            10: begin
                   case (op_q)
                       3'd1: wval <= sat(prod >>> 14);
                       3'd2: wval <= sat($signed({{2{vd[15]}}, vd}) + (prod >>> 14));
                       3'd3: wval <= sat($signed({{2{vd[15]}}, vd}) - (prod >>> 14));
                       default: wval <= lrd;                                   // SIN, COS
                   endcase
                   st <= 11;
               end
            11: begin aaddr <= dst_q; awd <= {2'b00, wval}; awe <= 1; st <= 5; end
            default: st <= 0;
        endcase
    end
endmodule
