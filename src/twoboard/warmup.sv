// warmup.sv -- heat the FPGA with its own logic and watch the crystal move.
//
// The DAC plays a 1 MHz sine (sine.sv, from ../verilog), so another board's lock-in
// can follow this board's crystal.  A "heater" -- W flip-flops scrambling each other
// at 100 MHz -- burns power on command, and the ECP5's on-chip thermometer (the DTR
// primitive) reports the die temperature code.
//
// Serial port, 1,000,000 baud:  "H" heater on, "C" heater off.
// Every 2^23 clocks (0.168 s) the board sends "TT h\n": the DTR code in hex (bit 7 =
// valid, bits 5:0 = Lattice's temperature code) and the heater state.
// For safety the heater switches itself off if the code reaches 33 (70 C).
module warmup #(parameter W = 8192) (
    input  logic       clk,
    output logic [7:0] dac_d,
    output logic       dac_clk,
    input  logic       uart_rx,
    output logic       uart_tx,
    output logic [4:0] led
);
    sine #(.TW(32'd85899346)) u_sine (.clk(clk), .dac_d(dac_d), .dac_clk(dac_clk));   // 1 MHz

    // ---- 100 MHz for the heater -----------------------------------------------
    logic clk100, locked;
    pll100 u_pll (.clk(clk), .clk100(clk100), .locked(locked));

    // ---- the heater: a wide register that keeps scrambling itself ------------
    logic heat = 0;
    logic heat100a = 0, heat100 = 0;
    always_ff @(posedge clk100) begin heat100a <= heat; heat100 <= heat100a; end
    (* keep *) logic [W-1:0] h = 1;
    always_ff @(posedge clk100)
        // ######################################################################
        // ##  KEY LINE: the heater.  8192 flip-flops, most of them toggling
        // ##  100 million times a second.  Each toggle costs a little energy.
        // ######################################################################
        if (heat100) h <= {h[W-2:0], h[W-1]} ^ {h[W-3:0], h[W-1:W-2]} ^ ~(h >> 5);
    // reduce it to one bit so the tools cannot throw it away
    logic [63:0] fold = 0;
    logic sink = 0;
    always_ff @(posedge clk100) begin
        for (int k = 0; k < 64; k++) fold[k] <= ^h[k*(W/64) +: (W/64)];
        sink <= ^fold;
    end

    // ---- the thermometer ------------------------------------------------------
    logic [22:0] div = 0;
    always_ff @(posedge clk) div <= div + 1;
    logic [7:0] dtrout;
    DTR #(.DTR_TEMP(25)) u_dtr (.STARTPULSE(div[22:4] == 0), .DTROUT7(dtrout[7]), .DTROUT6(dtrout[6]),
        .DTROUT5(dtrout[5]), .DTROUT4(dtrout[4]), .DTROUT3(dtrout[3]), .DTROUT2(dtrout[2]),
        .DTROUT1(dtrout[1]), .DTROUT0(dtrout[0]));
    logic [7:0] code = 0;
    always_ff @(posedge clk) if (dtrout[7]) code <= dtrout;

    // ---- serial port ----------------------------------------------------------
    logic [7:0] rx;
    logic rxv, busy;
    uart_rx #(.CLKS_PER_BIT(50)) u_rx (.clk(clk), .rx(uart_rx), .data(rx), .valid(rxv));
    logic [2:0] idx = 7;
    logic st = 0;
    logic [7:0] d = 0;
    uart_tx #(.CLKS_PER_BIT(50)) u_tx (.clk(clk), .data(d), .start(st), .busy(busy), .tx(uart_tx));
    function automatic logic [7:0] hex(input logic [3:0] n); hex = n < 10 ? "0" + n : "A" + n - 10; endfunction
    always_ff @(posedge clk) begin
        if (rxv && rx == "H") heat <= 1;
        if ((rxv && rx == "C") || (code[7] && code[5:0] >= 6'd33)) heat <= 0;
        st <= 0;
        if (div == 23'h400000) idx <= 0;
        else if (idx < 5 && !busy && !st) begin
            d <= idx == 0 ? hex(code[7:4]) : idx == 1 ? hex(code[3:0]) : idx == 2 ? " " :
                 idx == 3 ? (heat ? "1" : "0") : "\n";
            st <= 1; idx <= idx + 1;
        end
    end
    assign led = {heat, sink, code[2:0]};
endmodule
