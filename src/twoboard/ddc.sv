// ddc.sv -- the narrowband radio for an FT8-style weak-signal text link (6.11).  The
// laptop picks the tones and their timing; this board plays them, phase-continuous,
// and mixes what its ADC hears down to baseband and streams I/Q back to the laptop,
// whose Python does the decoding.
//
// Transmit: a DDS (phase accumulator + sine table, as modem.sv and radio.sv) whose
//           tuning word comes from a table of 8 that the laptop fills.  A 256-entry FIFO
//           of tone indices plays one entry per symbol period, counted in 50 MHz clocks.
//           The FT8-style symbol is 2^23 DAC clocks = 2^22 ADC samples = 167.77 ms, so
//           tones 25e6/2^22 = 5.96 Hz apart are orthogonal over a symbol (real FT8:
//           160 ms and 6.25 Hz; 79 symbols = 13.25 s).  Only the tuning word ever
//           changes, never the phase.  The carrier, 6.78 MHz, is inside the
//           6.765-6.795 MHz ISM band (5.07).
// Receive:  a digital down-converter (DDC): each ADC sample (25 MS/s) times cos and
//           -sin of an NCO at the laptop's frequency, as 1.08's lock-in, and the two
//           products summed over 2^d samples (a "boxcar") and dumped: one I/Q pair per
//           2^d samples, 3051.76 a second at d = 13, each a 7-byte frame on uart_tx:
//           0xA5, I (24-bit signed, big-endian), Q (likewise).  I = sum >>> (d - 9), so
//           a tone of A codes gives |I + jQ| = A x 2^9 x 127/2 = A x 32512 whatever d is.
//
// The laptop's protocol (1,000,000 baud, 8N1; multi-byte integers big-endian):
//   'W' idx word(4)   tone table entry idx (0..7) = f / 50e6 x 2^32 (the DAC's clock)
//   'A' amp           transmitted amplitude in DAC codes, 0..127; 0 = silent (DAC = 128)
//   'T' n(4)          symbol length in 50 MHz clocks (default 2^23 = 167.77 ms)
//   'M' count idx...  append count tone indices (0xFF = a silent symbol) to the FIFO;
//                     the first starts at once if the transmitter was idle
//   'C' idx           a continuous tone, for tuning antennas; 0xFF = off.  While it is
//                     on it replaces the FIFO's tone (the FIFO keeps its timing)
//   'R' word(4)       the receiver's NCO: f / 25e6 x 2^32 (the ADC's clock)
//   'D' d             decimation: one I/Q per 2^d ADC samples, 10..16 (default 13)
//                     ('R' and 'D' both restart the boxcar, so the next frame is clean)
//   'S' 0/1           I/Q streaming off/on (default off)
//   Unknown bytes are ignored; a command's argument bytes are taken in order.
//
// The UART carries 100,000 bytes a second, 14,285 frames: d >= 11 (12,207 frames/s)
// streams every one, d = 10 (24,414/s) can only send every other.  A frame that is
// ready while the one before is still going out is dropped whole, so the stream stays
// aligned; `dropped` counts them (visible in the simulation, not over the UART).
//
// LEDs:     led[0] = a tone is going out; led[4:1] = signal strength from the latest
//           |I| + |Q|, about 10 dB per LED: 1, 3, 10 and 30 codes of tone at the ADC.
//           ddc.py does the laptop side.
module ddc (
    input  logic       clk,         // 50 MHz
    input  logic       uart_rx,     // from the laptop
    output logic       uart_tx,     // to the laptop
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [4:0] led
);
    // ---- the serial port, both directions (uart.sv) -----------------------------------
    logic [7:0] rx_data, tx_data = 0;
    logic       rx_valid, tx_start = 0, tx_busy;
    uart_rx #(.CLKS_PER_BIT(50)) urx (.clk(clk), .rx(uart_rx), .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) utx (.clk(clk), .data(tx_data), .start(tx_start),
                                      .busy(tx_busy), .tx(uart_tx));

    // ---- the settings, as the laptop left them ----------------------------------------
    logic [31:0] tone_word [0:7];                   // 'W'; all 6.78 MHz until told otherwise
    initial for (int i = 0; i < 8; i++) tone_word[i] = 32'h22b6_ae7d;
    logic [6:0]  amp     = 7'd100;                  // 'A'
    logic [31:0] sym_len = 32'd8_388_608;           // 'T': 2^23 clocks = 167.77 ms
    logic [3:0]  cont    = 4'd8;                    // 'C': 0..7 = that tone, 8 = off
    logic [31:0] rx_word = 32'h456d_5cfb;           // 'R': 6.78 MHz
    logic [4:0]  d       = 5'd13;                   // 'D'
    logic        stream  = 0;                       // 'S'
    logic [7:0]  fifo [0:255];                      // 'M': tone indices, 0xFF = silence
    logic [8:0]  wr_ptr = 0, rd_ptr = 0;            // 9 bits: equal = empty, 256 apart = full

    // ---- the command parser: a command byte, then its arguments in order ---------------
    logic [7:0]  cmd  = 0;                          // the command being filled in; 0 = none
    logic [7:0]  left = 0;                          // argument bytes still to come
    logic [7:0]  idx  = 0;                          // 'W': which table entry
    logic [31:0] arg  = 0;                          // the argument bytes so far, newest lowest
    logic        restart = 0;                       // 'R' or 'D' done: start a fresh boxcar
    always_ff @(posedge clk) begin
      restart <= 0;
      if (rx_valid) begin
        if (cmd == 0)
            case (rx_data)
                "W": begin cmd <= "W"; left <= 5; end
                "A": begin cmd <= "A"; left <= 1; end
                "T": begin cmd <= "T"; left <= 4; end
                "M": begin cmd <= "M"; left <= 1; end
                "C": begin cmd <= "C"; left <= 1; end
                "R": begin cmd <= "R"; left <= 4; end
                "D": begin cmd <= "D"; left <= 1; end
                "S": begin cmd <= "S"; left <= 1; end
                default: ;                          // not a command: ignored
            endcase
        else begin
            arg  <= {arg[23:0], rx_data};
            left <= left - 1;
            if (left == 1) cmd <= 0;                // that was the last argument
            case (cmd)
                "W": if (left == 5) idx <= rx_data;
                     else if (left == 1) tone_word[idx[2:0]] <= {arg[23:0], rx_data};
                "A": amp <= rx_data[7] ? 7'd127 : rx_data[6:0];
                "T": if (left == 1) sym_len <= {arg[23:0], rx_data};
                "M": begin                          // the count; then that many entries ("m")
                         cmd  <= (rx_data == 0) ? 8'd0 : "m";
                         left <= rx_data;
                     end
                "m": if (wr_ptr - rd_ptr != 9'd256) begin      // not full
                         fifo[wr_ptr[7:0]] <= rx_data;
                         wr_ptr <= wr_ptr + 1;
                     end
                "C": cont <= (rx_data < 8) ? rx_data[3:0] : 4'd8;
                "R": if (left == 1) begin rx_word <= {arg[23:0], rx_data}; restart <= 1; end
                "D": if (rx_data >= 10 && rx_data <= 16) begin d <= rx_data[4:0]; restart <= 1; end
                "S": stream <= rx_data[0];
                default: ;
            endcase
        end
      end
    end

    // ---- transmitter: the symbol timer, the FIFO, and the DDS ---------------------------
    logic signed [8:0] sin_table [0:255];           // 128 x sin: amp x sin / 128 is amp codes
    initial for (int i = 0; i < 256; i++)
        sin_table[i] = $rtoi($floor(128.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    logic [31:0] sym_timer = 0;                     // clocks left in this symbol
    logic [31:0] seq_word  = 0;                     // the FIFO's tuning word; 0 = silence
    logic        seq_on    = 0;
    logic [7:0]  entry;                             // the FIFO's next entry
    assign entry = fifo[rd_ptr[7:0]];
    logic [31:0] tx_word = 0, tx_phase = 0;
    logic        tx_on   = 0;
    always_ff @(posedge clk) begin
        if (sym_timer != 0)
            sym_timer <= sym_timer - 1;
        else if (wr_ptr != rd_ptr) begin
            // ######################################################################
            // ##  KEY LINE: the symbol timer.  Exactly sym_len clocks after the last
            // ##  symbol began (or at once, if the FIFO was empty), take the next
            // ##  entry: its tuning word, or silence.
            // ######################################################################
            seq_word  <= (entry == 8'hff) ? 32'd0 : tone_word[entry[2:0]];
            seq_on    <= (entry != 8'hff);
            rd_ptr    <= rd_ptr + 1;
            sym_timer <= sym_len - 1;
        end else begin                              // the FIFO is empty: silence
            seq_word <= 0;
            seq_on   <= 0;
        end
        tx_word <= (cont != 8) ? tone_word[cont[2:0]] : seq_word;    // 'C' wins
        tx_on   <= (cont != 8) || seq_on;
        // ##########################################################################
        // ##  KEY LINE: phase-continuous.  The phase only ever adds the current
        // ##  tuning word; a new tone is a new step size, never a new phase.
        // ##########################################################################
        tx_phase <= tx_phase + tx_word;
    end

    // sine table, times the amplitude, to the DAC (three clocks of pipeline)
    logic signed [8:0]  sv   = 0;
    logic signed [16:0] prod = 0, rounded;
    logic               on1  = 0, on2 = 0;
    assign rounded = (prod + 17'sd64) >>> 7;        // -127..127
    always_ff @(posedge clk) begin
        sv    <= sin_table[tx_phase[31:24]];         on1 <= tx_on;
        prod  <= sv * $signed({1'b0, amp});          on2 <= on1;
        dac_d <= on2 ? 8'd128 + rounded[7:0] : 8'd128;
    end
    assign dac_clk = ~clk;

    // ---- the ADC at 25 MS/s, as in capture.sv -------------------------------------------
    logic adc_clk_r = 0, new_sample = 0;
    logic signed [8:0] x = 0;
    always_ff @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            x <= $signed({1'b0, adc_d}) - 9'sd128;
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- the DDC: an NCO, a mixer, and a boxcar that dumps every 2^d samples -----------
    // As in radio.sv: the table at the NCO's phase is "cos", a quarter turn on is "-sin".
    logic signed [7:0] ref_table [0:255];
    initial for (int i = 0; i < 256; i++)
        ref_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));
    logic [31:0]        rx_phase = 0;
    logic signed [16:0] p_x = 0, p_y = 0;           // |p| <= 128 x 127 < 2^14
    logic               step = 0;
    always_ff @(posedge clk) begin
        step <= new_sample;
        if (new_sample) begin
            rx_phase <= rx_phase + rx_word;
            // ######################################################################
            // ##  KEY LINE: the mixer.  Each sample times the NCO's cos and -sin.
            // ######################################################################
            p_x <= x * ref_table[rx_phase[31:24]];
            p_y <= x * ref_table[rx_phase[31:24] + 8'd64];
        end
    end
    logic signed [31:0] acc_x = 0, acc_y = 0;       // |acc| < 2^(d+14) <= 2^30
    logic signed [31:0] dump_x = 0, dump_y = 0;
    logic [15:0]        n = 0, last;                // samples so far; 2^d - 1
    logic               dump = 0;
    assign last = 16'((17'd1 << d) - 1);
    always_ff @(posedge clk) begin
        dump <= 0;
        if (restart) begin                          // a new NCO or d: throw the part-sum away
            acc_x <= 0;
            acc_y <= 0;
            n     <= 0;
        end else if (step) begin
            if ((n & last) == last) begin
                // ##################################################################
                // ##  KEY LINE: the boxcar.  Sum 2^d products, hand the sum over,
                // ##  and start again from zero.
                // ##################################################################
                dump_x <= acc_x + p_x;
                dump_y <= acc_y + p_y;
                acc_x  <= 0;
                acc_y  <= 0;
                n      <= 0;
                dump   <= 1;
            end else begin
                acc_x <= acc_x + p_x;
                acc_y <= acc_y + p_y;
                n     <= n + 1;
            end
        end
    end
    // scaled to 24 bits: sum >>> (d - 9), so the result does not depend on d
    logic [2:0]         sh;
    logic signed [23:0] iq_i = 0, iq_q = 0;
    logic               iq_new = 0;
    assign sh = 3'(d - 5'd9);
    always_ff @(posedge clk) begin
        iq_new <= dump;
        if (dump) begin
            iq_i <= 24'(dump_x >>> sh);
            iq_q <= 24'(dump_y >>> sh);
        end
    end

    // ---- the frames to the laptop: 0xA5, I, Q, one byte after another --------------------
    logic [55:0] frame   = 0;                       // the bytes still to go, next one on top
    logic [2:0]  nbytes  = 0;
    logic [15:0] dropped = 0;                       // frames that found the last one still going
    always_ff @(posedge clk) begin
        tx_start <= 0;
        if (iq_new && stream && nbytes == 0) begin
            frame  <= {8'ha5, iq_i, iq_q};
            nbytes <= 7;
        end else begin
            if (iq_new && stream)
                dropped <= dropped + 1;
            if (nbytes != 0 && !tx_busy && !tx_start) begin   // the UART is free: next byte
                tx_data  <= frame[55:48];
                tx_start <= 1;
                frame    <= {frame[47:0], 8'h00};
                nbytes   <= nbytes - 1;
            end
        end
    end

    // ---- LEDs: transmitting, and a signal-strength meter ----------------------------------
    // |I| + |Q| is between 32512 and 46000 per code of tone amplitude at the ADC, so the
    // thresholds below are tones of about 1, 3, 10 and 30 codes: 10 dB per LED.
    logic [23:0] abs_i, abs_q;
    logic [24:0] mag = 0;
    assign abs_i = iq_i[23] ? 24'(-iq_i) : 24'(iq_i);
    assign abs_q = iq_q[23] ? 24'(-iq_q) : 24'(iq_q);
    always_ff @(posedge clk) if (iq_new) mag <= abs_i + abs_q;
    assign led = {mag >= 25'd1_000_000, mag >= 25'd320_000, mag >= 25'd100_000,
                  mag >= 25'd32_000, tx_on && (amp != 0)};
endmodule
