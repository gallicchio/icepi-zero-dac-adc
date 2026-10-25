// awgcap_slow.sv -- awgcap.sv (6.00) with a slower clock: an arbitrary waveform
// generator and a digitizer for signals of tens of kilohertz instead of megahertz.
//
// The DAC plays a 16384-sample waveform from block RAM, over and over, one sample
// every 2^k clocks: 195,312.5 samples a second at the default k = 8, so one loop is
// 83.89 ms.  The ADC still samples at 25 MS/s, but what is recorded is the AVERAGE of
// 2^k of its samples: one value every 2^(k+1) clocks (97,656.25 a second at k = 8),
// 16384 of them (167.77 ms = exactly two loops), starting on the first sample of a
// loop.  The average is the anti-alias filter (a boxcar, 7.05), and it buys bits: each
// value is sent as 16 bits, the average in 1/256ths of an ADC code.
//
// Serial port, 1,000,000 baud:
//   "W" then 16384 bytes   load a new waveform (the DAC keeps playing as it loads)
//   "K" then one byte k    the rate: one DAC sample every 2^k clocks, k = 0..12
//                          (default 8).  k = 0 plays at 50 MS/s, as awgcap.sv does
//   "C"                    record, then send back the 16384 values, 2 bytes each,
//                          high byte first: 256 x (the mean ADC code), 0..65280
//
// awgcap_slow.py does the laptop side.
module awgcap_slow (
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

    // ---- the rate: one DAC sample every 2^k clocks ------------------------------
    logic [3:0]  k = 4'd8;
    logic [12:0] last;                      // 2^k - 1: the divider's last count
    assign last = 13'((14'd1 << k) - 1);

    // ---- the waveform: one sample every 2^k clocks -------------------------------
    logic [7:0]  wave [0:N-1];
    logic [13:0] play = 0;                  // which sample the DAC is playing
    logic [12:0] div  = 0;                  // clocks into this sample
    initial for (int i = 0; i < N; i++) wave[i] = 8'd128;
    always_ff @(posedge clk) begin
        // ######################################################################
        // ##  KEY LINE: as awgcap.sv, but the next sample only every 2^k clocks.
        // ##  play wraps from 16383 to 0, so the waveform loops forever, and its
        // ##  zero is the instant every record is lined up with.
        // ######################################################################
        if (div >= last) begin
            div   <= 0;
            play  <= play + 1;
            dac_d <= wave[14'(play + 1)];   // so the DAC shows wave[play] while play holds it
        end else
            div <= div + 1;
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

    // ---- load, record (averaging), send ------------------------------------------
    logic [15:0] rec [0:N-1];
    logic [13:0] addr = 0;
    logic [15:0] rd = 0;
    logic [19:0] acc = 0;                   // up to 2^12 samples of 255
    logic [11:0] cnt = 0;                   // samples in acc so far
    logic [19:0] sum;
    logic [27:0] scaled;
    logic        hi = 1;                    // sending the high byte next
    assign sum    = acc + sample;
    assign scaled = {sum, 8'd0} >> k;       // 256 x the mean: sum x 2^(8-k)
    typedef enum logic [2:0] {IDLE, LOAD, RATE, ARM, RECORD, SEND, SEND2} state_t;
    state_t state = IDLE;
    always_ff @(posedge clk) begin
        tx_start <= 0;
        rd <= rec[addr];
        case (state)
            IDLE:
                if (rx_valid && rx_data == "W") begin addr <= 0; state <= LOAD; end
                else if (rx_valid && rx_data == "K") state <= RATE;
                else if (rx_valid && rx_data == "C") state <= ARM;
            LOAD:
                if (rx_valid) begin
                    wave[addr] <= rx_data;
                    addr <= addr + 1;
                    if (addr == N - 1) state <= IDLE;
                end
            RATE:
                if (rx_valid) begin
                    k <= (rx_data > 12) ? 4'd12 : rx_data[3:0];
                    state <= IDLE;
                end
            ARM:
                // ##############################################################
                // ##  KEY LINE: start on the first clock of a loop, so every
                // ##  record starts at the same instant of the waveform.
                // ##############################################################
                if (play == 0 && div == 0) begin
                    acc <= 0; cnt <= 0; addr <= 0; state <= RECORD;
                end
            RECORD:
                if (new_sample) begin
                    // ##########################################################
                    // ##  KEY LINE: add up 2^k samples, store their mean (in
                    // ##  1/256ths of a code), and start the next sum from zero.
                    // ##########################################################
                    if (cnt == last[11:0]) begin
                        rec[addr] <= scaled[15:0];
                        acc <= 0;
                        cnt <= 0;
                        addr <= addr + 1;
                        if (addr == N - 1) begin addr <= 0; hi <= 1; state <= SEND; end
                    end else begin
                        acc <= sum;
                        cnt <= cnt + 1;
                    end
                end
            SEND:  state <= SEND2;          // one clock for the RAM read
            SEND2:
                if (!tx_busy && !tx_start) begin
                    tx_data <= hi ? rd[15:8] : rd[7:0];
                    tx_start <= 1;
                    hi <= ~hi;
                    if (hi) state <= SEND2;                 // the low byte of the same value
                    else if (addr == N - 1) state <= IDLE;
                    else begin addr <= addr + 1; state <= SEND; end
                end
        endcase
    end
    assign led = {state, 2'b0};
endmodule
