// uart.v -- a serial port ("UART"): 8 data bits, no parity, 1 stop bit (8N1).
//
// On the wire, an idle line sits at 1.  A byte is a 0 "start bit", the 8 data
// bits least-significant first, and a 1 "stop bit", each lasting one bit time.
// At 1,000,000 baud a bit time is 1 us = 50 clocks of the 50 MHz clock.
//
// Used by capture.v and lockin.v.  The FT231X chip on the Icepi Zero turns
// these wires into /dev/ttyUSB0 on the PC.

module uart_tx #(
    parameter CLKS_PER_BIT = 50
) (
    input  wire       clk,
    input  wire [7:0] data,
    input  wire       start,     // high for one clock: send `data`
    output wire       busy,      // high while a byte is going out
    output wire       tx
);
    reg [9:0]  frame = 10'b1111111111;   // {stop, data[7:0], start}; bit 0 is on the wire
    reg [3:0]  bits  = 0;                // bits left to send
    reg [15:0] timer = 0;

    assign tx   = frame[0];
    assign busy = (bits != 0);

    always @(posedge clk)
        if (!busy) begin
            if (start) begin
                frame <= {1'b1, data, 1'b0};
                bits  <= 10;
                timer <= 0;
            end
        end else if (timer == CLKS_PER_BIT - 1) begin
            timer <= 0;
            frame <= {1'b1, frame[9:1]};  // shift the next bit onto the wire
            bits  <= bits - 1;
        end else
            timer <= timer + 1;
endmodule


module uart_rx #(
    parameter CLKS_PER_BIT = 50
) (
    input  wire       clk,
    input  wire       rx,
    output reg  [7:0] data  = 0,
    output reg        valid = 0      // high for one clock when `data` is new
);
    // rx comes from another chip with its own clock, so it can change at any
    // instant.  Two flip-flops in a row give it time to settle to a clean 0/1.
    reg rx1 = 1, rx2 = 1;
    always @(posedge clk) begin
        rx1 <= rx;
        rx2 <= rx1;
    end

    reg [3:0]  count = 0;            // 0 = idle; 1..8 = next data bit; 9 = stop bit
    reg [15:0] timer = 0;
    reg [7:0]  shift = 0;

    always @(posedge clk) begin
        valid <= 0;
        if (count == 0) begin
            if (!rx2) begin                          // start bit has begun
                count <= 1;
                timer <= CLKS_PER_BIT * 3 / 2;       // wait 1.5 bits: middle of data bit 0
            end
        end else if (timer != 0)
            timer <= timer - 1;
        else if (count <= 8) begin                   // middle of a data bit
            shift <= {rx2, shift[7:1]};              // LSB arrives first
            count <= count + 1;
            timer <= CLKS_PER_BIT - 1;
        end else begin                               // middle of the stop bit
            data  <= shift;
            valid <= 1;
            count <= 0;
        end
    end
endmodule
