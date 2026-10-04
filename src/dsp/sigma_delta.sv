// sigma_delta.sv -- trading speed for bits, in gateware (7.05).  A 16-bit sine from a
// DDS is re-quantized for the 8-bit DAC at 25 MS/s, four ways, each level held for two
// DAC clocks (so that the shaped noise stays below the ADC's 12.5 MHz); and the ADC's
// side is a three-stage CIC decimator that streams 24-bit samples to the laptop, so
// that the recovered waveform can be watched live (sigma_delta_live.py --monitor).
//
// Transmit: phase accumulator + a 16-bit quarter-wave sine table (4096 entries, block
//           RAM) + the amplitude, giving x in 1/65536 of a DAC code; then, once per
//           modulator sample (every other clock):
//             mode 0  8-bit plain:  dac = 128 + round(x)
//             mode 1  1-bit, 1st order:  v = x - e;  dac = v >= 0 ? 255 : 0;  e = y - v
//             mode 2  1-bit, 2nd order:  v = x - 2 e1 + e2;  likewise;  e2 = e1, e1 = y - v
//             mode 3  8-bit, 1st order:  v = x - e;  dac = 128 + round(v);  e = round(v) - v
//           (y = +-127.5 codes for the 1-bit modes).  Error feedback: y = x + (1 - z^-1)^n e.
// Receive:  x = adc - 128 into three integrators at 25 MS/s; every 2^d samples the sum
//           goes through three differentiators (a CIC, Hogenauer 1981: sinc^3, the
//           right order for a 2nd-order modulator) and out as a 24-bit sample, scaled
//           by 2^(16 - 3d) so that +-128 codes is +-2^23 whatever d is.  Each sample is
//           a 4-byte frame on uart_tx: 0xA5, then the 24 bits big-endian.
//
// The laptop's protocol (1,000,000 baud, 8N1; multi-byte integers big-endian):
//   'F' word(4)   the DDS tuning word: f / 25e6 x 2^32 (one step per modulator sample)
//   'A' amp(2)    amplitude in 1/256 DAC code, 0..32767 (= 0..127.996 codes)
//   'M' mode      0..3 as above (default 2); changing it clears the error state
//   'D' d         decimation 2^d, d = 8..16 (default 10: 24,414 samples a second)
//   'S' 0/1       streaming off/on (default off)
//   Unknown bytes are ignored.  The UART carries 25,000 frames a second: d >= 10 streams
//   every sample; at d = 9 every other one is dropped whole (`dropped` counts them).
//
// LEDs: led[0] = streaming; led[4:1] = the decimated signal's size, about 10 dB per LED.
module sigma_delta (
    input  logic       clk,         // 50 MHz
    input  logic       uart_rx,
    output logic       uart_tx,
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [4:0] led
);
    // ---- the serial port (uart.sv) -----------------------------------------------------
    logic [7:0] rx_data, tx_data = 0;
    logic       rx_valid, tx_start = 0, tx_busy;
    uart_rx #(.CLKS_PER_BIT(50)) urx (.clk(clk), .rx(uart_rx), .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) utx (.clk(clk), .data(tx_data), .start(tx_start),
                                      .busy(tx_busy), .tx(uart_tx));

    // ---- the settings ----------------------------------------------------------------
    logic [31:0] fword  = 32'd1_572_864;            // 'F': 9155.27 Hz (3 cycles per 327.68 us)
    logic [14:0] amp    = 15'd16384;                // 'A': 64 codes
    logic [1:0]  mode   = 2'd2;                     // 'M'
    logic [4:0]  d      = 5'd10;                    // 'D'
    logic        stream = 0;                        // 'S'
    logic [7:0]  cmd  = 0, left = 0;
    logic [31:0] arg  = 0;
    logic        restart = 0;                       // a new mode or d: clear the states
    always_ff @(posedge clk) begin
        restart <= 0;
        if (rx_valid) begin
            if (cmd == 0)
                case (rx_data)
                    "F": begin cmd <= "F"; left <= 4; end
                    "A": begin cmd <= "A"; left <= 2; end
                    "M": begin cmd <= "M"; left <= 1; end
                    "D": begin cmd <= "D"; left <= 1; end
                    "S": begin cmd <= "S"; left <= 1; end
                    default: ;
                endcase
            else begin
                arg  <= {arg[23:0], rx_data};
                left <= left - 1;
                if (left == 1) cmd <= 0;
                case (cmd)
                    "F": if (left == 1) fword <= {arg[23:0], rx_data};
                    "A": if (left == 1) amp <= {arg[6:0], rx_data};
                    "M": begin mode <= rx_data[1:0]; restart <= 1; end
                    "D": if (rx_data >= 8 && rx_data <= 16) begin d <= rx_data[4:0]; restart <= 1; end
                    "S": stream <= rx_data[0];
                    default: ;
                endcase
            end
        end
    end

    // ---- the modulator's clock: every other cycle --------------------------------------
    logic tick = 0;
    always_ff @(posedge clk) tick <= ~tick;

    // ---- the DDS: a 16-bit sine, from a quarter wave in block RAM ------------------------
    logic signed [15:0] quarter [0:4095];           // sin of (i + 1/2) / 4096 quarter turns
    initial for (int i = 0; i < 4096; i++)
        quarter[i] = $rtoi($floor(32767.0 * $sin(1.5707963267948966 * (i + 0.5) / 4096) + 0.5));
    logic [31:0]        phase = 0;
    logic [11:0]        qa = 0;
    logic               neg1 = 0, neg2 = 0;
    logic signed [15:0] qv = 0, sv = 0;             // the sine, +-32767
    always_ff @(posedge clk) begin
        if (tick) phase <= phase + fword;
        qa   <= phase[30] ? ~phase[29:18] : phase[29:18];   // 2nd and 4th quarters run backwards
        neg1 <= phase[31];                                   // 3rd and 4th are negative
        qv   <= quarter[qa];
        neg2 <= neg1;
        sv   <= neg2 ? -qv : qv;
    end
    logic signed [31:0] prod = 0;                   // sine x amplitude
    logic signed [31:0] x;                          // the sample, in 1/65536 of a DAC code
    always_ff @(posedge clk) prod <= sv * $signed({1'b0, amp});
    assign x = prod >>> 7;                          // (2^15 x 2^8 = 2^23 per code) -> 2^16 per code

    // ---- the modulator: round, or feed the error back and then round ----------------------
    localparam signed [31:0] HALF = 32'sd8_355_840; // 127.5 codes
    logic signed [31:0] e1 = 0, e2 = 0;             // the last two rounding errors
    logic signed [31:0] v, r;                       // the value to round; rounded to a code
    logic signed [8:0]  q;                          // -128..127
    logic               one;
    always_comb begin
        case (mode)
            2'd0:    v = x;
            2'd2:    v = x - (e1 <<< 1) + e2;
            default: v = x - e1;
        endcase
        r   = (v + 32'sd32768) >>> 16;
        q   = (r > 127) ? 9'sd127 : (r < -128) ? -9'sd128 : 9'(r);
        one = (v >= 0);
    end
    always_ff @(posedge clk) begin
        if (restart) begin
            e1 <= 0;
            e2 <= 0;
        end else if (tick) begin
            // ##########################################################################
            // ##  KEY LINE: the error of this rounding is kept, to be subtracted before
            // ##  the next one: y = x + (1 - z^-1) e, and the noise moves up in frequency.
            // ##########################################################################
            case (mode)
                2'd0: dac_d <= 8'(128 + q);
                2'd3: begin dac_d <= 8'(128 + q);          e1 <= (32'(q) <<< 16) - v; end
                2'd1: begin dac_d <= one ? 8'd255 : 8'd0;  e1 <= (one ? HALF : -HALF) - v; end
                2'd2: begin dac_d <= one ? 8'd255 : 8'd0;  e1 <= (one ? HALF : -HALF) - v; e2 <= e1; end
            endcase
        end
    end
    assign dac_clk = ~clk;

    // ---- the ADC at 25 MS/s, as in capture.sv -------------------------------------------
    logic adc_clk_r = 0, new_sample = 0;
    logic signed [8:0] xa = 0;
    always_ff @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            xa <= $signed({1'b0, adc_d}) - 9'sd128;
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- the CIC: three integrators at 25 MS/s, three combs at 25 MS/s / 2^d --------------
    // 8 bits in, times 2^(3d) <= 2^48 of gain: 56 bits, and the integrators may wrap.
    logic signed [55:0] i1 = 0, i2 = 0, i3 = 0;
    logic signed [55:0] c1 = 0, c2 = 0, c3 = 0, m1 = 0, m2 = 0, m3 = 0;
    logic [15:0]        cnt = 0, last;
    logic               dump = 0, v1 = 0, v2 = 0, v3 = 0, out_new = 0;
    logic signed [23:0] out = 0;
    assign last = 16'((17'd1 << d) - 1);
    always_ff @(posedge clk) begin
        dump <= 0;
        if (restart) begin
            i1 <= 0; i2 <= 0; i3 <= 0; m1 <= 0; m2 <= 0; m3 <= 0; cnt <= 0;
        end else if (new_sample) begin
            // ##########################################################################
            // ##  KEY LINE: a boxcar of boxcars of boxcars.  Integrate three times at
            // ##  the fast rate; differentiate three times at the slow one (below).
            // ##########################################################################
            i1 <= i1 + 56'(xa);
            i2 <= i2 + i1;
            i3 <= i3 + i2;
            if ((cnt & last) == last) begin
                cnt  <= 0;
                dump <= 1;
            end else
                cnt <= cnt + 1;
        end
        v1 <= dump;  v2 <= v1;  v3 <= v2;  out_new <= v3;
        if (dump) begin c1 <= i3 - m1; m1 <= i3; end
        if (v1)   begin c2 <= c1 - m2; m2 <= c1; end
        if (v2)   begin c3 <= c2 - m3; m3 <= c2; end
        if (v3)   out <= 24'(c3 >>> (3 * d - 16));
    end

    // ---- the frames to the laptop: 0xA5 then 3 bytes ----------------------------------------
    logic [31:0] frame   = 0;
    logic [2:0]  nbytes  = 0;
    logic [15:0] dropped = 0;
    always_ff @(posedge clk) begin
        tx_start <= 0;
        if (out_new && stream && nbytes == 0) begin
            frame  <= {8'ha5, out};
            nbytes <= 4;
        end else begin
            if (out_new && stream)
                dropped <= dropped + 1;
            if (nbytes != 0 && !tx_busy && !tx_start) begin
                tx_data  <= frame[31:24];
                tx_start <= 1;
                frame    <= {frame[23:0], 8'h00};
                nbytes   <= nbytes - 1;
            end
        end
    end

    // ---- LEDs ---------------------------------------------------------------------------
    logic [23:0] mag = 0;                           // |out|: 2^16 per ADC code
    always_ff @(posedge clk) if (out_new) mag <= out[23] ? 24'(-out) : 24'(out);
    assign led = {mag >= 24'd2_000_000, mag >= 24'd650_000, mag >= 24'd200_000,
                  mag >= 24'd65_000, stream};       // 1, 3, 10 and 30 codes
endmodule
