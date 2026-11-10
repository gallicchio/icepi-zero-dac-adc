// The register bus over the UART.  One command byte: bit 7 = write, bits 6:0 = register address.
//   write: the command byte, then 4 data bytes, least significant first; no reply
//   read:  the command byte; the board answers 4 bytes, least significant first
//   read of 0x7F: the board streams `dump_len` 32-bit words of the capture memory, address 0 up
// A write left unfinished for ~40 ms (2^20 cycles at 25 MHz) is dropped, so a lost byte cannot wedge
// the bus; five 0x00 bytes (reads of register 0, the ID) resynchronise it from any state.  Incoming bytes
// queue in a 64-byte FIFO, so commands may follow a read without waiting for its reply (within 64 bytes).
`default_nettype none

module regbus (
    input  wire        clk,
    // uart
    input  wire [7:0]  rx_data,
    input  wire        rx_valid,
    output reg  [7:0]  tx_data = 0,
    output reg         tx_start = 0,
    input  wire        tx_busy,
    // registers (one cycle: addr/wdata/we valid together; rdata must be valid the cycle after addr)
    output reg  [6:0]  addr = 0,
    output reg  [31:0] wdata = 0,
    output reg         we = 0,
    input  wire [31:0] rdata,
    // the capture memory: dump_addr out, dump_data valid two cycles later
    input  wire [15:0] dump_len,
    output reg  [15:0] dump_addr = 0,
    input  wire [31:0] dump_data,
    output reg         active = 0          // a command is in progress (for an activity LED)
);
    // Bytes from the PC wait in a 64-byte FIFO while a reply is going out, so a command sent on the heels of
    // a read is not lost (the PC need not wait for the reply before sending the next command).
    reg [7:0]  fifo [0:63];
    reg [5:0]  wp = 0, rp = 0;
    wire       f_empty = wp == rp;
    always @(posedge clk) if (rx_valid) begin fifo[wp] <= rx_data; wp <= wp + 1'b1; end
    wire [7:0] f_data = fifo[rp];
    reg        f_take;                        // consume the head this cycle
    always @(posedge clk) if (f_take) rp <= rp + 1'b1;

    localparam IDLE = 0, WDATA = 1, RD_WAIT = 2, RD_SEND = 3, DUMP_ADDR = 4, DUMP_WAIT1 = 5, DUMP_WAIT2 = 6, DUMP_SEND = 7;
    reg [2:0]  state = IDLE;
    reg [1:0]  byten = 0;
    reg [31:0] sh = 0;
    reg [15:0] dcount = 0;
    reg [19:0] tmo = 0;

    always @(*) f_take = !f_empty && (state == IDLE || state == WDATA);
    always @(posedge clk) begin
        we <= 1'b0;
        tx_start <= 1'b0;
        active <= state != IDLE || !f_empty;
        if (state == WDATA) begin
            tmo <= tmo + 1'b1;
            if (&tmo) state <= IDLE;
        end else tmo <= 0;
        case (state)
        IDLE: if (f_take) begin
            addr <= f_data[6:0];
            byten <= 0;
            if (f_data[7]) state <= WDATA;
            else if (f_data[6:0] == 7'h7f) begin dump_addr <= 0; dcount <= 0; state <= dump_len == 0 ? IDLE : DUMP_ADDR; end
            else state <= RD_WAIT;
        end
        WDATA: if (f_take) begin
            sh <= {f_data, sh[31:8]};
            byten <= byten + 1'b1;
            if (byten == 3) begin wdata <= {f_data, sh[31:8]}; we <= 1'b1; state <= IDLE; end
        end
        RD_WAIT: begin sh <= rdata; byten <= 0; state <= RD_SEND; end
        RD_SEND: if (!tx_busy && !tx_start) begin
            tx_data <= sh[7:0]; tx_start <= 1'b1; sh <= {8'h00, sh[31:8]};
            byten <= byten + 1'b1;
            if (byten == 3) state <= IDLE;
        end
        DUMP_ADDR:  state <= DUMP_WAIT1;
        DUMP_WAIT1: state <= DUMP_WAIT2;
        DUMP_WAIT2: begin sh <= dump_data; byten <= 0; state <= DUMP_SEND; end
        DUMP_SEND: if (!tx_busy && !tx_start) begin
            tx_data <= sh[7:0]; tx_start <= 1'b1; sh <= {8'h00, sh[31:8]};
            byten <= byten + 1'b1;
            if (byten == 3) begin
                dcount <= dcount + 1'b1;
                dump_addr <= dump_addr + 1'b1;
                state <= (dcount + 1'b1 == dump_len) ? IDLE : DUMP_ADDR;
            end
        end
        default: state <= IDLE;
        endcase
    end
endmodule
`default_nettype wire
