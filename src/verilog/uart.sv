// uart.sv -- a serial port ("UART"): 8 data bits, no parity, 1 stop bit (8N1).
//
// On the wire, an idle line sits at 1.  A byte is a 0 "start bit", the 8 data
// bits least-significant first, and a 1 "stop bit", each lasting one bit time.
// At 1,000,000 baud a bit time is 1 us = 50 clocks of the 50 MHz clock.
//
// Used by adc_stream.sv, capture.sv, loopback.sv and lockin.sv.  The FT231X
// chip on the Icepi Zero turns these wires into a serial port on the laptop.

module uart_tx #(
    parameter CLKS_PER_BIT = 50
) (
    input  logic       clk,
    input  logic [7:0] data,
    input  logic       start,     // high for one clock: send `data`
    output logic       busy,      // high while a byte is going out
    output logic       tx
);
    logic [9:0]  frame = 10'b1111111111;  // {stop, data[7:0], start}; bit 0 is on the wire
    logic [3:0]  bits  = 0;               // bits left to send
    logic [15:0] timer = 0;               // counts the clocks of one bit

    assign tx   = frame[0];
    assign busy = (bits != 0);

    always_ff @(posedge clk)
        if (!busy) begin
            if (start) begin
                // ##############################################################
                // ##  KEY LINE: load the whole 10-bit frame at once:
                // ##  stop bit (1), the 8 data bits, start bit (0).
                // ##############################################################
                frame <= {1'b1, data, 1'b0};
                bits  <= 10;
                timer <= 0;
            end
        end else if (timer == CLKS_PER_BIT - 1) begin
            timer <= 0;
            // ##################################################################
            // ##  KEY LINE: one bit time is up: shift the next bit onto the
            // ##  wire.  Ones shift in from the top, so the line ends idle.
            // ##################################################################
            frame <= {1'b1, frame[9:1]};
            bits  <= bits - 1;
        end else
            timer <= timer + 1;
endmodule


module uart_rx #(
    parameter CLKS_PER_BIT = 50
) (
    input  logic       clk,
    input  logic       rx,
    output logic [7:0] data  = 0,
    output logic       valid = 0      // high for one clock when `data` is new
);
    // rx comes from another chip with its own clock, so it can change at any
    // instant.  Two flip-flops in a row give it time to settle to a clean 0/1.
    logic rx1 = 1, rx2 = 1;
    always_ff @(posedge clk) begin
        rx1 <= rx;
        rx2 <= rx1;
    end

    logic [3:0]  count = 0;           // 0 = idle; 1..8 = next data bit; 9 = stop bit
    logic [15:0] timer = 0;
    logic [7:0]  shift = 0;

    always_ff @(posedge clk) begin
        valid <= 0;
        if (count == 0) begin
            if (!rx2) begin                          // the start bit has begun
                count <= 1;
                timer <= CLKS_PER_BIT * 3 / 2;       // wait 1.5 bits: the middle of data bit 0
            end
        end else if (timer != 0)
            timer <= timer - 1;
        else if (count <= 8) begin
            // ##################################################################
            // ##  KEY LINE: in the middle of each data bit, read the line and
            // ##  shift it in.  The LSB arrives first, so shift in from the top.
            // ##################################################################
            shift <= {rx2, shift[7:1]};
            count <= count + 1;
            timer <= CLKS_PER_BIT - 1;
        end else begin                               // the middle of the stop bit
            data  <= shift;
            valid <= 1;
            count <= 0;
        end
    end
endmodule
