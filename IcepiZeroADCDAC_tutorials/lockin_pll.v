// lockin_pll.v -- lockin.v with the DAC at 100 MS/s instead of 50.
//
// Everything runs on a 100 MHz clock from pll100.v.  The ADC still samples at
// 25 MS/s (now 100 MHz / 4), and the serial port still runs at 1,000,000 baud
// (now 100 clocks per bit), so lockin.py talks to it unchanged -- except that
// the tuning word is now  TW = f / 100 MHz * 2^32:  set  lockin.F_CLK = 100e6.
//
// See lockin.v for how it works; `diff lockin.v lockin_pll.v` shows the changes.

module lockin_pll #(
    parameter N_LOG2 = 20               // average 2^20 samples = 42 ms at 25 MS/s
) (
    input  wire       clk,         // 50 MHz, to the PLL
    input  wire [7:0] adc_d,
    output wire       adc_clk,
    output reg  [7:0] dac_d,
    output wire       dac_clk,
    input  wire       uart_rx,
    output wire       uart_tx,
    output wire [4:0] led
);
    wire clk100, locked;                 // every block below runs on clk100
    pll100 pll (.clk(clk), .clk100(clk100), .locked(locked));
    // ---- sine table, as in sine.v -------------------------------------------
    reg signed [7:0] sine_table [0:255];
    integer i;
    initial
        for (i = 0; i < 256; i = i + 1)
            sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    // ---- the stimulus: DDS -> DAC at 100 MS/s, as in sine_pll.v ---------------
    reg [31:0] tw = 32'h028f5c29;       // 1 MHz until told otherwise
    reg [31:0] phase = 0;
    initial dac_d = 128;
    always @(posedge clk100) begin
        phase <= phase + tw;
        dac_d <= sine_table[phase[31:24]] + 128;
    end
    assign dac_clk = ~clk100;

    // ---- the ADC at 25 MS/s: adc_clk is 20 ns high, 20 ns low, as before ----
    reg       adc_clk_r = 0;
    reg       new_sample = 0;
    reg [7:0] sample = 128;
    reg [7:0] sample_phase = 0;         // the stimulus phase when it was taken
    reg       adc_div = 0;               // toggles every clock: adc_clk_r every other
    always @(posedge clk100) begin
        adc_div    <= ~adc_div;
        if (adc_div) adc_clk_r <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_div && adc_clk_r == 0) begin
            sample       <= adc_d;
            sample_phase <= phase[31:24];
            new_sample   <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- multiply and accumulate: a 3-step assembly line --------------------
    // Each step takes one clock; v1 and v2 say "the step before me had data".
    reg               v1 = 0, v2 = 0;
    reg signed [8:0]  s = 0;            // sample - 128:  -128 .. +127
    reg signed [7:0]  ref_sin = 0, ref_cos = 0;
    reg signed [16:0] p_sin = 0, p_cos = 0;
    reg signed [N_LOG2+16:0] acc_x = 0, acc_y = 0;
    reg [N_LOG2-1:0]  count = 0;
    reg               done = 0;         // high for one clock: X and Y are ready
    reg signed [31:0] X = 0, Y = 0;
    reg               restart = 0;      // set by the serial command below

    always @(posedge clk100) begin
        // step 1: look up the reference, remove the ADC's mid-scale offset
        v1 <= new_sample;
        s       <= $signed({1'b0, sample}) - 9'sd128;
        ref_sin <= sine_table[sample_phase];
        ref_cos <= sine_table[sample_phase + 8'd64];     // 64/256 of a turn = 90 degrees
        // step 2: multiply (the FPGA has hardware multipliers for this)
        v2 <= v1;
        p_sin <= s * ref_sin;
        p_cos <= s * ref_cos;
        // step 3: add up 2^N_LOG2 products, then report and start again
        done <= 0;
        if (restart) begin
            acc_x <= 0;
            acc_y <= 0;
            count <= 0;
        end else if (v2) begin
            if (count == {N_LOG2{1'b1}}) begin            // the last one
                X <= (acc_x + p_sin) >>> (N_LOG2 - 16);   // sum / 2^N_LOG2 * 65536
                Y <= (acc_y + p_cos) >>> (N_LOG2 - 16);
                done  <= 1;
                acc_x <= 0;
                acc_y <= 0;
            end else begin
                acc_x <= acc_x + p_sin;
                acc_y <= acc_y + p_cos;
            end
            count <= count + 1;
        end
    end

    // ---- serial port ---------------------------------------------------------
    wire [7:0] rx_data;
    wire       rx_valid;
    reg  [7:0] tx_data = 0;
    reg        tx_start = 0;
    wire       tx_busy;
    uart_rx #(.CLKS_PER_BIT(100)) rx (.clk(clk100), .rx(uart_rx),
                                     .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(100)) tx (.clk(clk100), .data(tx_data), .start(tx_start),
                                     .busy(tx_busy), .tx(uart_tx));

    // Commands: hex digits shift into `entry`; Enter makes it the new TW.
    reg [31:0] entry = 0;
    wire is_digit  = rx_data >= "0" && rx_data <= "9";
    wire is_letter = rx_data >= "a" && rx_data <= "f";
    wire [3:0] nibble = is_digit ? rx_data - "0" : rx_data - "a" + 10;
    always @(posedge clk100) begin
        restart <= 0;
        if (rx_valid) begin
            if (is_digit || is_letter)
                entry <= {entry[27:0], nibble};
            else if (rx_data == "\n" || rx_data == "\r") begin
                tw      <= entry;
                restart <= 1;
            end
        end
    end

    // Results: print TW, X and Y as 8 hex digits each, then a newline.
    reg [95:0] line = 0;                // the three numbers, next digit at the top
    reg [1:0]  word = 3;                // 0..2 = printing that number, 3 = idle
    reg [3:0]  digit = 0;               // 0..7 = a hex digit, 8 = the separator
    wire [3:0] top = line[95:92];
    always @(posedge clk100) begin
        tx_start <= 0;
        if (done && word == 3) begin
            line  <= {tw, X, Y};
            word  <= 0;
            digit <= 0;
        end else if (word != 3 && !tx_busy && !tx_start) begin
            tx_start <= 1;
            if (digit == 8) begin
                tx_data <= (word == 2) ? "\n" : " ";
                word    <= word + 1;
                digit   <= 0;
            end else begin
                tx_data <= (top < 10) ? "0" + top : "a" + top - 10;
                line    <= line << 4;
                digit   <= digit + 1;
            end
        end
    end

    // ---- LEDs ------------------------------------------------------------------
    reg results_led = 0;
    reg [23:0] clip_timer = 0;          // stays lit ~0.3 s after the ADC clips
    always @(posedge clk100) begin
        if (done) results_led <= ~results_led;
        if (new_sample && (sample == 0 || sample == 255)) clip_timer <= ~0;
        else if (clip_timer != 0) clip_timer <= clip_timer - 1;
    end
    assign led = {clip_timer != 0, 3'b000, results_led};
endmodule
