// Minimal 8N1 UART TX bit-banger, no LiteX, no CPU, no BIOS.
// Drives the same physical pin (J17) as colorlight_i5.py's "serial" tx,
// through the same DAPLink CDC-ACM bridge, to isolate whether the
// <DAPLink:Overflow> failure is link/probe-level or LiteX/BIOS-specific.
//
// BURST_LIMIT = 0   -> transmit forever, back-to-back, no idle gaps.
// BURST_LIMIT = N>0 -> transmit exactly N bytes, then go idle (tx=1) and
//                      light the onboard LED solid so completion is visible
//                      even without a serial capture running.
// PATTERN = 0 -> monotone 0x55 ('U')
// PATTERN = 1 -> cycling printable ASCII 0x20-0x7E (closer to real banner text)

module uart_stress_test #(
    parameter integer CLK_FREQ    = 25_000_000,
    parameter integer BAUD_RATE   = 115200,
    parameter integer BURST_LIMIT = 600,
    parameter integer PATTERN     = 1
) (
    input  wire clk,
    output reg  tx  = 1'b1,
    output reg  led = 1'b1   // active-low onboard LED (D2 @ L2)
);

    localparam integer BAUD_DIV = CLK_FREQ / BAUD_RATE;

    reg [$clog2(BAUD_DIV+1)-1:0] baud_cnt = 0;
    wire baud_tick = (baud_cnt == BAUD_DIV-1);
    always @(posedge clk)
        baud_cnt <= baud_tick ? 0 : baud_cnt + 1'b1;

    reg [7:0]  data_byte  = PATTERN ? 8'h20 : 8'h55;
    reg [3:0]  bit_idx    = 0;      // 0=start,1-8=data,9=stop
    reg [31:0] byte_count = 0;
    reg [7:0]  shift_reg  = 8'h55;

    wire burst_done = (BURST_LIMIT != 0) && (byte_count >= BURST_LIMIT);

    always @(posedge clk) begin
        if (burst_done) begin
            tx  <= 1'b1;
            led <= 1'b0;           // solid on: burst finished
        end else if (baud_tick) begin
            case (bit_idx)
                4'd0: begin tx <= 1'b0; shift_reg <= data_byte; end          // start bit
                4'd1,4'd2,4'd3,4'd4,4'd5,4'd6,4'd7,4'd8: begin
                    tx        <= shift_reg[0];
                    shift_reg <= {1'b0, shift_reg[7:1]};
                end
                4'd9: tx <= 1'b1;                                           // stop bit
            endcase

            if (bit_idx == 4'd9) begin
                bit_idx    <= 4'd0;
                byte_count <= byte_count + 1'b1;
                if (PATTERN)
                    data_byte <= (data_byte == 8'h7E) ? 8'h20 : data_byte + 1'b1;
            end else begin
                bit_idx <= bit_idx + 1'b1;
            end

            // blink slowly while running, only reached when BURST_LIMIT==0
            if (BURST_LIMIT == 0)
                led <= byte_count[19];
        end
    end

endmodule
