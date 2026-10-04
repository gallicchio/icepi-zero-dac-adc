// capture.sv -- record 2^14 = 16384 ADC samples into memory at up to 25 MS/s,
// then send them to the laptop over the serial port.
//
// The laptop sends one character, the hex digit D ("0".."9" or "a".."f", meaning
// 0..15).  The FPGA then keeps every 2^D-th sample of the 25 MS/s ADC stream
// -- a sample rate of 25 MHz / 2^D -- until its memory is full, and sends the
// 16384 samples back as 16384 raw bytes at 1,000,000 baud (about 0.16 s).
// capture.py does the laptop side.
//
// LEDs (with the USB connectors facing down):
//   the left three LEDs show the ADC's top 3 bits (MSB on the left), then
//   led[1] = sending, and
//   led[0] = recording, on the right

module capture (
    input  logic       clk,         // 50 MHz
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    input  logic       uart_rx,
    output logic       uart_tx,
    output logic [4:0] led
);
    localparam N = 16384;

    // ---- the ADC: clock it at 25 MHz and grab each sample (as in adc_leds.sv)
    logic       adc_clk_r  = 0;
    logic       new_sample = 0;     // high for one clk when `sample` is new
    logic [7:0] sample     = 0;

    always_ff @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin   // adc_clk is about to rise
            sample     <= adc_d;
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- the serial port, both directions (see uart.sv) ---------------------
    logic [7:0] rx_data;
    logic       rx_valid;
    logic [7:0] tx_data  = 0;
    logic       tx_start = 0;
    logic       tx_busy;

    uart_rx #(.CLKS_PER_BIT(50)) rx (.clk(clk), .rx(uart_rx),
                                     .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) tx (.clk(clk), .data(tx_data), .start(tx_start),
                                     .busy(tx_busy), .tx(uart_tx));

    // ---- memory: 16384 bytes, which Yosys puts in the FPGA's block RAM -------
    logic [7:0]  mem [0:N-1];
    logic [13:0] addr = 0;          // 14 bits: counts 0..16383, then wraps to 0

    // ---- what we're doing now: the state machine's three states --------------
    typedef enum logic [1:0] {IDLE, RECORD, SEND} state_t;
    state_t      state = IDLE;
    logic [3:0]  D     = 0;         // keep 1 sample in 2^D
    logic [15:0] skip  = 0;         // samples still to skip before keeping one

    always_ff @(posedge clk) begin
        tx_start <= 0;
        case (state)
            IDLE:
                // Only a hex digit starts a capture.  Anything else is ignored --
                // including the junk byte the FT231X can produce when the laptop
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
                        // ######################################################
                        // ##  KEY LINE: store the sample, move to the next address.
                        // ######################################################
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
                    // ##########################################################
                    // ##  KEY LINE: the UART is free: send the next stored byte.
                    // ##########################################################
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
