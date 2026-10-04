// adc_stream.sv -- stream ADC samples to the laptop: 50,000 samples a second, forever.
//
// The ADC runs at 25 MS/s, as in adc_leds.sv, far faster than the serial port
// can carry.  So every 1000 clocks (20 us) the latest sample goes out over the
// serial port as one raw byte: 50,000 bytes a second, half of what 1,000,000
// baud can carry.  stream.py reads and plots them.
//
// The DAC plays a sawtooth that repeats every 1.31 ms (763 Hz), so a cable from
// the DAC to the ADC gives you something to see without a function generator.

module adc_stream (
    input  logic       clk,         // 50 MHz
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [7:0] dac_d,
    output logic       dac_clk,
    output logic       uart_tx,     // to the laptop, through the FT231X USB chip
    output logic [4:0] led
);
    // ---- the ADC, exactly as in adc_leds.sv ----------------------------------
    logic       adc_clk_r = 0;
    logic [7:0] sample    = 0;
    always_ff @(posedge clk) begin
        adc_clk_r <= ~adc_clk_r;
        if (adc_clk_r == 1'b0)
            sample <= adc_d;
    end
    assign adc_clk = adc_clk_r;

    // ---- the serial port: only the transmitter is needed (see uart.sv) -------
    logic [7:0] tx_data  = 0;
    logic       tx_start = 0;
    logic       tx_busy;
    uart_tx #(.CLKS_PER_BIT(50)) tx (.clk(clk), .data(tx_data), .start(tx_start),
                                     .busy(tx_busy), .tx(uart_tx));

    // ---- every 1000 clocks, send the latest sample -----------------------------
    logic [9:0] tick = 0;           // counts 0, 1, ..., 999, 0, ...
    always_ff @(posedge clk) begin
        tx_start <= 1'b0;           // a one-clock pulse, unless set below
        if (tick == 999) begin
            tick <= 0;
            // ##################################################################
            // ##  KEY LINE: hand the latest sample to the UART and start it.
            // ##  A byte takes 500 clocks to send, so the UART is always free
            // ##  again long before the next one, 1000 clocks later.
            // ##################################################################
            tx_data  <= sample;
            tx_start <= 1'b1;
        end else
            tick <= tick + 1;
    end

    assign led = sample[7:3];       // as in adc_leds.sv

    // ---- the DAC: a sawtooth from a counter, slower than sawtooth.sv by 2^8 ---
    logic [15:0] count = 0;
    always_ff @(posedge clk)
        count <= count + 1;
    assign dac_d   = count[15:8];   // 256 steps of 256 clocks: 1.31 ms per ramp
    assign dac_clk = ~clk;
endmodule
