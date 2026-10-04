// awgcap.sv -- an arbitrary waveform generator and a digitizer in one design.
//
// The DAC plays a 16384-sample waveform from block RAM, over and over, at
// 50 MS/s (one loop = 327.68 us).  The ADC records 16384 samples at 25 MS/s
// (655.36 us = exactly two loops), starting on the first sample of a loop, so
// every record has the same timing relative to this board's own waveform.
//
// Serial port, 1,000,000 baud:
//   "W" then 16384 bytes   load a new waveform (the DAC keeps playing as it loads)
//   "C"                    record, then send back the 16384 ADC samples
//
// Two boards running this, cross-connected, can send each other any signal.
// One board looped back records its own.
module awgcap (
    input  logic       clk,         // 50 MHz
    output logic [7:0] dac_d = 8'd128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    input  logic       uart_rx,
    output logic       uart_tx,
    output logic [4:0] led
);
    localparam N = 16384;

    // ---- the waveform: one sample per clock -----------------------------------
    logic [7:0]  wave [0:N-1];
    logic [13:0] play = 0;                  // which sample the DAC is playing
    initial for (int i = 0; i < N; i++) wave[i] = 8'd128;
    always_ff @(posedge clk) begin
        // ######################################################################
        // ##  KEY LINE: play the stored waveform, one sample per clock.  `play`
        // ##  wraps from 16383 to 0, so it loops forever.  Its zero is this
        // ##  board's "noon": the instant every record is lined up with.
        // ######################################################################
        play  <= play + 1;
        dac_d <= wave[play];
    end
    assign dac_clk = ~clk;                  // as in the earlier designs

    // ---- the ADC: 25 MS/s, as in capture.sv ------------------------------------
    logic adc_clk_r = 0, new_sample = 0;
    logic [7:0] sample = 0;
    always_ff @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            sample     <= adc_d;
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- serial port ----------------------------------------------------------
    logic [7:0] rx_data;
    logic       rx_valid, tx_busy;
    logic [7:0] tx_data = 0;
    logic       tx_start = 0;
    uart_rx #(.CLKS_PER_BIT(50)) urx (.clk(clk), .rx(uart_rx), .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) utx (.clk(clk), .data(tx_data), .start(tx_start), .busy(tx_busy), .tx(uart_tx));

    // ---- load, record, send ---------------------------------------------------
    logic [7:0]  rec [0:N-1];
    logic [13:0] addr = 0;
    logic [7:0]  rd = 0;
    typedef enum logic [2:0] {IDLE, LOAD, ARM, RECORD, SEND, SEND2} state_t;
    state_t state = IDLE;
    always_ff @(posedge clk) begin
        tx_start <= 0;
        rd <= rec[addr];
        case (state)
            IDLE:
                if (rx_valid && rx_data == "W") begin addr <= 0; state <= LOAD; end
                else if (rx_valid && rx_data == "C") state <= ARM;
            LOAD:
                if (rx_valid) begin
                    wave[addr] <= rx_data;
                    addr <= addr + 1;
                    if (addr == N - 1) state <= IDLE;
                end
            ARM:
                // ##############################################################
                // ##  KEY LINE: start recording on the first sample of a loop,
                // ##  so every record starts at the same instant of this
                // ##  board's own clock.
                // ##############################################################
                if (new_sample && play == 14'd1) begin
                    rec[0] <= sample; addr <= 1; state <= RECORD;
                end
            RECORD:
                if (new_sample) begin
                    rec[addr] <= sample;
                    addr <= addr + 1;
                    if (addr == N - 1) begin addr <= 0; state <= SEND; end
                end
            SEND:  state <= SEND2;          // one clock for the RAM read
            SEND2:
                if (!tx_busy && !tx_start) begin
                    tx_data <= rd; tx_start <= 1;
                    if (addr == N - 1) state <= IDLE;
                    else begin addr <= addr + 1; state <= SEND; end
                end
        endcase
    end
    assign led = {state, 2'b0};
endmodule
