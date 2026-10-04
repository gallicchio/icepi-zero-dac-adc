// tick.v -- oscillator check: send a sequence byte every 2^22 clocks
// (83.886 ms at exactly 50 MHz).  measure_osc.py time-stamps them on the PC.
module tick (input wire clk, output wire uart_tx);
    reg [21:0] div = 0;
    reg [7:0]  seq = 0;
    reg        start = 0;
    wire       busy;
    uart_tx tx0 (.clk(clk), .data(seq), .start(start), .busy(busy), .tx(uart_tx));
    always @(posedge clk) begin
        div   <= div + 1;
        start <= (div == 0);
        if (start) seq <= seq + 1;
    end
endmodule
