// UART, 8N1, for the FT2232H's channel B.  DIV = clock cycles per bit (25 MHz / 1 Mbaud = 25).
// The receiver samples the middle of every bit after a 2-flop synchroniser; the transmitter is a
// plain shift register.  Both are clocked by the TCXO directly, so the PC can talk to the board
// even if the PLL never locks.
`default_nettype none

module uart_rx #(parameter DIV = 25) (
    input  wire       clk,
    input  wire       rx,
    output reg  [7:0] data  = 0,
    output reg        valid = 0          // one-cycle pulse: `data` holds a new byte
);
    reg [1:0] sync = 2'b11;
    always @(posedge clk) sync <= {sync[0], rx};
    wire r = sync[1];

    localparam CW = $clog2(DIV) + 1;
    reg        busy = 0;
    reg [CW-1:0] cnt = 0;
    reg [3:0]  bitn = 0;
    reg [7:0]  sh = 0;
    always @(posedge clk) begin
        valid <= 1'b0;
        if (!busy) begin
            if (!r) begin                        // start bit: wait half a bit, then sample every DIV
                busy <= 1'b1; cnt <= DIV / 2; bitn <= 0;
            end
        end else if (cnt != 0) begin
            cnt <= cnt - 1'b1;
        end else begin
            cnt <= DIV - 1;
            if (bitn == 0) begin
                if (r) busy <= 1'b0;             // a glitch, not a start bit
                bitn <= 1;
            end else if (bitn <= 8) begin
                sh <= {r, sh[7:1]};
                bitn <= bitn + 1'b1;
            end else begin                       // stop bit
                busy <= 1'b0;
                if (r) begin data <= sh; valid <= 1'b1; end
            end
        end
    end
endmodule

module uart_tx #(parameter DIV = 25) (
    input  wire       clk,
    input  wire [7:0] data,
    input  wire       start,             // one-cycle pulse; ignored while busy
    output wire       busy,
    output reg        tx = 1'b1
);
    localparam CW = $clog2(DIV) + 1;
    reg [CW-1:0] cnt = 0;
    reg [3:0]  bitn = 0;                 // 0 idle; 1 start; 2-9 data; 10 stop
    reg [8:0]  sh = 9'h1ff;
    assign busy = bitn != 0;
    always @(posedge clk) begin
        if (bitn == 0) begin
            tx <= 1'b1;
            if (start) begin sh <= {data, 1'b0}; bitn <= 1; cnt <= DIV - 1; tx <= 1'b0; end
        end else if (cnt != 0) begin
            cnt <= cnt - 1'b1;
        end else begin
            cnt <= DIV - 1;
            if (bitn == 10) bitn <= 0;
            else begin
                tx <= bitn == 9 ? 1'b1 : sh[1];  // after the start bit come data[0..7], then the stop bit
                sh <= {1'b1, sh[8:1]};
                bitn <= bitn + 1'b1;
            end
        end
    end
endmodule
`default_nettype wire
