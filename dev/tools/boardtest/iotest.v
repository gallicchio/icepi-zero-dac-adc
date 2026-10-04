// iotest.v -- board test: every 10 ms, send "B<C4><C5><SD_DET>\n" at 1 Mbaud.
//
// Each of the three is '1' or '0' as read (buttons: 0 = pressed).  LEDs 0 and 1
// light while C4 / C5 are pressed.  Read it with
//     python3 -c "import serial; s=serial.Serial('/dev/ttyUSB0',1000000); [print(s.readline()) for _ in range(500)]"
// Build: see the Makefile in this folder.
module iotest (input wire clk, input wire btn, input wire btn4, input wire sd_det,
               input wire uart_rx, output wire uart_tx, output wire [1:0] led);
    reg [18:0] tick = 0;
    reg [2:0]  idx = 7;
    reg        start = 0;
    reg [7:0]  data = 0;
    wire       busy;
    uart_tx tx0 (.clk(clk), .data(data), .start(start), .busy(busy), .tx(uart_tx));
    always @(posedge clk) begin
        tick  <= tick + 1;
        start <= 0;
        if (tick == 0) idx <= 0;
        else if (idx < 5 && !busy && !start) begin
            case (idx)
                0: data <= "B";
                1: data <= btn4   ? "1" : "0";
                2: data <= btn    ? "1" : "0";
                3: data <= sd_det ? "1" : "0";
                4: data <= "\n";
            endcase
            start <= 1;
            idx   <= idx + 1;
        end
    end
    assign led = {~btn, ~btn4};
endmodule
