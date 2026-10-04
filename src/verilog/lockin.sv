// lockin.sv -- a lock-in amplifier.
//
// The DAC plays a sine wave at frequency f (the "stimulus"); call it cos(wt).
// Whatever comes back into the ADC is multiplied by the stimulus itself, and
// separately by the stimulus a quarter turn on, cos(wt + 90 deg) = -sin(wt), and
// each product is averaged over 2^20 samples (42 ms):
//
//     X = < adc * cos(wt) >        Y = < adc * -sin(wt) >
//
// If the ADC sees  a*cos(wt + phi)  then  X = (a*127/2) cos(phi)  and
// Y = (a*127/2) sin(phi); together,  X + jY = < adc * e^(-jwt) > = (a*127/2) e^(j phi):
// the amplitude and phase of the response at f, with everything at other
// frequencies (noise, harmonics, hum) averaged away.
//
// Serial port, 1,000,000 baud:
//   laptop -> FPGA:  the tuning word TW as hex digits, then Enter, e.g. "051eb852\n"
//                sets f = TW * 50 MHz / 2^32 (= 1.000000 MHz here) and restarts
//                the average.  lockin.py does the arithmetic for you.
//   FPGA -> laptop:  one line per average, three 32-bit hex numbers:
//                "TTTTTTTT XXXXXXXX YYYYYYYY"  -- the TW it used, then X and Y
//                in units of 1/65536 of a code^2, two's complement.
//
// LEDs: the rightmost (led[0]) toggles with each result; the leftmost (led[4])
// lights when the ADC clips (reads 0 or 255).

module lockin #(
    parameter N_LOG2 = 20           // average 2^20 samples = 42 ms at 25 MS/s
) (
    input  logic       clk,         // 50 MHz
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic       uart_rx,
    output logic       uart_tx,
    output logic [4:0] led
);
    // ---- sine table, as in sine.sv -------------------------------------------
    // One cycle of the stimulus.  Which point of the cycle is t = 0 is ours to
    // choose, so call what the DAC plays cos(wt): then the entry 64 further on,
    // a quarter of the way round the table, is cos(wt + 90 deg) = -sin(wt).
    logic signed [7:0] sine_table [0:255];
    initial
        for (int i = 0; i < 256; i++)
            sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    // ---- the stimulus: DDS -> DAC at 50 MS/s, as in sine.sv --------------------
    logic [31:0] tw    = 32'h051eb852;  // 1 MHz until told otherwise
    logic [31:0] phase = 0;
    always_ff @(posedge clk) begin
        phase <= phase + tw;
        dac_d <= sine_table[phase[31:24]] + 128;
    end
    assign dac_clk = ~clk;

    // ---- the ADC at 25 MS/s, as in capture.sv ---------------------------------
    logic       adc_clk_r    = 0;
    logic       new_sample   = 0;
    logic [7:0] sample       = 128;
    logic [7:0] sample_phase = 0;   // the stimulus phase when it was taken
    always_ff @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            sample       <= adc_d;
            // ##################################################################
            // ##  KEY LINE: remember the stimulus phase at the moment of each
            // ##  sample.  The reference below is computed from this phase.
            // ##################################################################
            sample_phase <= phase[31:24];
            new_sample   <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- multiply and accumulate: a 3-step assembly line --------------------
    // Each step takes one clock; v1 and v2 say "the step before me had data".
    logic                     v1 = 0, v2 = 0;
    logic signed [8:0]        s = 0;            // sample - 128:  -128 .. +127
    logic signed [7:0]        ref_x = 0, ref_y = 0;
    logic signed [16:0]       p_x = 0, p_y = 0;
    logic signed [N_LOG2+16:0] acc_x = 0, acc_y = 0;
    logic [N_LOG2-1:0]        count = 0;
    logic                     done = 0;         // high for one clock: X and Y are ready
    logic signed [31:0]       X = 0, Y = 0;
    logic                     restart = 0;      // set by the serial command below

    always_ff @(posedge clk) begin
        // step 1: look up the reference, remove the ADC's mid-scale offset
        v1      <= new_sample;
        s       <= $signed({1'b0, sample}) - 9'sd128;
        ref_x <= sine_table[sample_phase];            // cos(wt): the stimulus itself
        ref_y <= sine_table[sample_phase + 8'd64];    // a quarter turn on: -sin(wt)
        // step 2: multiply (the FPGA has hardware multipliers for this)
        v2 <= v1;
        // ######################################################################
        // ##  KEY LINE 1: multiply the signal by both references, cos and -sin.
        // ######################################################################
        p_x <= s * ref_x;
        p_y <= s * ref_y;
        // step 3: add up 2^N_LOG2 products, then report and start again
        done <= 0;
        if (restart) begin
            acc_x <= 0;
            acc_y <= 0;
            count <= 0;
        end else if (v2) begin
            if (count == {N_LOG2{1'b1}}) begin              // the last one
                // ##############################################################
                // ##  KEY LINE 3: the average is the sum / 2^N_LOG2.  Keep 16
                // ##  bits after the binary point: sum / 2^N_LOG2 * 65536.
                // ##############################################################
                X <= (acc_x + p_x) >>> (N_LOG2 - 16);
                Y <= (acc_y + p_y) >>> (N_LOG2 - 16);
                done  <= 1;
                acc_x <= 0;
                acc_y <= 0;
            end else begin
                // ##############################################################
                // ##  KEY LINE 2: add up the products.  Anything not at the
                // ##  stimulus frequency averages towards zero.
                // ##############################################################
                acc_x <= acc_x + p_x;
                acc_y <= acc_y + p_y;
            end
            count <= count + 1;
        end
    end

    // ---- serial port ---------------------------------------------------------
    logic [7:0] rx_data;
    logic       rx_valid;
    logic [7:0] tx_data  = 0;
    logic       tx_start = 0;
    logic       tx_busy;
    uart_rx #(.CLKS_PER_BIT(50)) rx (.clk(clk), .rx(uart_rx),
                                     .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) tx (.clk(clk), .data(tx_data), .start(tx_start),
                                     .busy(tx_busy), .tx(uart_tx));

    // Commands: hex digits shift into `entry`; Enter makes it the new TW.
    logic [31:0] entry = 0;
    logic        is_digit, is_letter;
    logic [3:0]  nibble;
    assign is_digit  = rx_data >= "0" && rx_data <= "9";
    assign is_letter = rx_data >= "a" && rx_data <= "f";
    assign nibble    = is_digit ? rx_data - "0" : rx_data - "a" + 10;
    always_ff @(posedge clk) begin
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
    logic [95:0] line  = 0;         // the three numbers, next digit at the top
    logic [1:0]  word  = 3;         // 0..2 = printing that number, 3 = idle
    logic [3:0]  digit = 0;         // 0..7 = a hex digit, 8 = the separator
    logic [3:0]  top;
    assign top = line[95:92];
    always_ff @(posedge clk) begin
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
    logic        results_led = 0;
    logic [23:0] clip_timer  = 0;   // stays lit ~0.3 s after the ADC clips
    always_ff @(posedge clk) begin
        if (done) results_led <= ~results_led;
        if (new_sample && (sample == 0 || sample == 255)) clip_timer <= '1;
        else if (clip_timer != 0) clip_timer <= clip_timer - 1;
    end
    assign led = {clip_timer != 0, 3'b000, results_led};
endmodule
