// capture.v -- Tutorial 3: record 16384 ADC samples into memory, then send
// them to the PC over the serial port.
//
// The PC sends one character, the hex digit D ("0".."9" or "a".."f", meaning
// 0..15).  The FPGA then keeps every 2^D-th sample
// of the 25 MS/s ADC stream -- a sample rate of 25 MHz / 2^D -- until its
// memory is full, and sends the 16384 samples back as 16384 raw bytes at
// 1,000,000 baud (about 0.16 s).  capture.py does the PC side.
//
// LEDs, USB connectors down: the left three show the ADC's top 3 bits (MSB on
// the left), then led[1] = sending, and the rightmost, led[0] = recording.

module capture (
    input  wire       clk,         // 50 MHz
    input  wire [7:0] adc_d,
    output wire       adc_clk,
    input  wire       uart_rx,
    output wire       uart_tx,
    output wire [4:0] led
);
    localparam N = 16384;

    // ---- the ADC: clock it at 25 MHz and grab each sample ------------------
    // The AD9280 needs 14.7 ns high and 14.7 ns low, so 25 MHz (20 + 20 ns) is
    // as fast as a 50 MHz clock allows.  A sample appears on adc_d about 25 ns
    // after the ADC's rising clock edge, so we read it just before the NEXT
    // rising edge, 40 ns later, when it has been steady for ~15 ns.
    reg       adc_clk_r = 0;
    reg       new_sample = 0;      // high for one clk when `sample` is new
    reg [7:0] sample = 0;

    always @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin  // adc_clk is about to rise
            sample     <= adc_d;
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- the serial port ---------------------------------------------------
    wire [7:0] rx_data;
    wire       rx_valid;
    reg  [7:0] tx_data = 0;
    reg        tx_start = 0;
    wire       tx_busy;

    uart_rx #(.CLKS_PER_BIT(50)) rx (.clk(clk), .rx(uart_rx),
                                     .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) tx (.clk(clk), .data(tx_data), .start(tx_start),
                                     .busy(tx_busy), .tx(uart_tx));

    // ---- memory: 16384 bytes of block RAM ----------------------------------
    reg [7:0]  mem [0:N-1];
    reg [13:0] addr = 0;

    // ---- what we're doing now ----------------------------------------------
    localparam IDLE = 0, RECORD = 1, SEND = 2;
    reg [1:0]  state = IDLE;
    reg [3:0]  D = 0;              // keep 1 sample in 2^D
    reg [15:0] skip = 0;           // samples still to skip before keeping one

    always @(posedge clk) begin
        tx_start <= 0;
        case (state)
            IDLE:
                // Only a hex digit starts a capture.  Anything else is ignored --
                // including the junk byte the FT231X can produce when the PC
                // opens the port.
                if (rx_valid && ((rx_data >= "0" && rx_data <= "9") ||
                                 (rx_data >= "a" && rx_data <= "f"))) begin
                    D     <= (rx_data <= "9") ? rx_data - "0" : rx_data - "a" + 10;
                    skip  <= 0;
                    addr  <= 0;
                    state <= RECORD;
                end
            RECORD:
                if (new_sample) begin
                    if (skip == 0) begin
                        mem[addr] <= sample;
                        addr  <= addr + 1;
                        skip  <= (16'd1 << D) - 1;
                        if (addr == N - 1)     // that was the last one
                            state <= SEND;     // (addr wraps back to 0)
                    end else
                        skip <= skip - 1;
                end
            SEND:
                if (!tx_busy && !tx_start) begin
                    tx_data  <= mem[addr];
                    tx_start <= 1;
                    addr     <= addr + 1;
                    if (addr == N - 1)
                        state <= IDLE;
                end
        endcase
    end

    assign led = {sample[7:5], state == SEND, state == RECORD};
endmodule
