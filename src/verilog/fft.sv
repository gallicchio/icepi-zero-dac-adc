// fft.sv -- a spectrum analyzer: record 1024 ADC samples, Fourier transform
// them inside the FPGA, and send the power spectrum to the laptop.
//
// It is capture.sv (1.06) with a Fourier transform between "record" and "send".
// For each "frame" of N = 1024 samples the FPGA
//   1. records the samples, keeping 1 in 2^D of the 25 MS/s stream: a sample
//      rate fs = 25 MHz / 2^D.  There is no anti-alias filter, so a signal
//      above fs/2 shows up folded back to a frequency below fs/2.
//   2. subtracts 128 (so 0 V is about 0) and multiplies by a Hann window, a
//      bump that fades the frame in and out.  Without it, a sine that doesn't
//      fit a whole number of cycles into the frame leaks into every frequency.
//   3. computes X[k] = (1/N) sum_n x[n] w[n] exp(-2 pi i k n / N), with the
//      window w[n], using the FFT: 10 stages of 512 "butterflies".  X[k] is
//      the amplitude at the frequency k * fs / N.
//   4. adds |X[k]|^2, k = 0..511 (0 to fs/2), to a running sum in memory.
// After 2^A frames it sends the average and waits for the next command.
// One frame takes 1024 * 2^D / 25 MHz to record (41 us at D = 0), then 0.61 ms
// for the FFT (10 * 512 butterflies, 6 clocks each) and 41 us for step 4.
//
// Serial port, 1,000,000 baud:
//   laptop -> FPGA:  two hex digits, D then A ("0".."9", "a".."f"), e.g. "08":
//                    fs = 25 MHz / 2^D, average 2^A frames.  Other bytes are
//                    ignored, except "q" and "w", which turn the DAC's test
//                    signal off and on.
//   FPGA -> laptop:  P[0] .. P[511], 32-bit unsigned numbers, least significant
//                    byte first (2048 bytes, 20 ms).  P[k] is the average of
//                    |X[k]|^2, rounded down; anything too big for 32 bits is
//                    sent as 2^32 - 1.  A sine of amplitude 128 codes (full
//                    scale) exactly at frequency k gives P[k] = 2^30, so
//                    dB re full scale = 10 log10(P / 2^30).   (fft.py)
//
// Numbers: everything in the FFT is an 18-bit signed integer, -131072 ..
// 131071, the width of the FPGA's multipliers.  The window peaks at 1024, so
// |x w| <= 128 * 1024 = 131072.  Each stage computes (a + W b)/2 and
// (a - W b)/2, which are never bigger than the bigger of |a| and |b| (|W| = 1),
// so the numbers can't grow; ten halvings make the 1/N.  (A real part of
// +131072 wouldn't fit, but the first stage averages samples n and n + 512,
// whose window values add up to exactly 1024: after it, everything is at most
// 65536, half the range.)
//
// The DAC plays a test signal, a 781.25 kHz square wave, so that 1.07's cable from
// the DAC to the ADC gives the analyzer something to show: 32 whole periods per
// frame at D = 0, so its odd harmonics land exactly on k = 32, 96, 160, ...
// Send "q" to quiet it (the DAC sits at mid-scale, 0 V), so it can't leak into
// what you plug into the ADC, and "w" to bring it back.  (fft.py --quiet.)
//
// LEDs: the left three show the ADC's top 3 bits, then
//   led[1] = sending, and led[0] = recording or computing.

module fft #(
    parameter LOG2N = 10            // N = 2^10 = 1024 samples per frame
) (
    input  logic       clk,         // 50 MHz
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [7:0] dac_d,
    output logic       dac_clk,
    input  logic       uart_rx,
    output logic       uart_tx,
    output logic [4:0] led
);
    localparam N = 1 << LOG2N;

    // ---- the DAC's test signal: a square wave, 64 clocks per period ----------
    logic [5:0] dac_count = 0;
    logic       dac_on    = 1;      // "q" turns it off, "w" back on (see below)
    always_ff @(posedge clk)
        dac_count <= dac_count + 1;
    assign dac_d   = !dac_on ? 8'd128 :                  // mid-scale: 0 V
                     dac_count[5] ? 8'd224 : 8'd32;      // about +2.9 V and -2.9 V, as loopback.sv
    assign dac_clk = ~clk;

    // ---- the ADC: clock it at 25 MHz and grab each sample (as in capture.sv)
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
    always_ff @(posedge clk)
        if (rx_valid && rx_data == "q") dac_on <= 0;
        else if (rx_valid && rx_data == "w") dac_on <= 1;
    logic       is_hex;             // rx_data is "0".."9" or "a".."f"
    logic [3:0] hex;                // ...and its value
    assign is_hex = (rx_data >= "0" && rx_data <= "9") || (rx_data >= "a" && rx_data <= "f");
    assign hex    = (rx_data <= "9") ? rx_data - "0" : rx_data - "a" + 10;

    // ---- tables, computed by Yosys (like the sine table in lockin.sv) --------
    logic        [10:0] hann [0:N-1];            // the window: 0 .. 1024 .. 0
    logic signed [17:0] twiddle_re [0:N/2-1];    // exp(-2 pi i k / N), k = 0..N/2-1,
    logic signed [17:0] twiddle_im [0:N/2-1];    //   times 65536
    initial begin
        for (int i = 0; i < N; i++)
            hann[i] = $rtoi($floor(512.0 - 512.0 * $cos(6.283185307179586 * i / N) + 0.5));
        for (int i = 0; i < N/2; i++) begin
            twiddle_re[i] = $rtoi($floor( 65536.0 * $cos(6.283185307179586 * i / N) + 0.5));
            twiddle_im[i] = $rtoi($floor(-65536.0 * $sin(6.283185307179586 * i / N) + 0.5));
        end
    end

    // ---- memory, in block RAM -------------------------------------------------
    // The FFT works "in place" on N complex numbers: a butterfly reads two and
    // writes its two answers back in their places.  A RAM reads its read
    // address on every clock (the data is there on the next), and writes one
    // clock after the state machine sets `we`.  (* no_rw_check *) tells Yosys
    // that nothing reads an address in the clock it's written (fft_tb.sv
    // checks), so it needn't add logic for that case.
    (* no_rw_check *) logic signed [17:0] mem_re [0:N-1], mem_im [0:N-1];
    logic [LOG2N-1:0]   raddr, waddr = 0;
    logic signed [17:0] rd_re, rd_im, wr_re = 0, wr_im = 0;
    logic               we = 0;
    always_ff @(posedge clk) begin
        if (we) begin
            mem_re[waddr] <= wr_re;
            mem_im[waddr] <= wr_im;
        end
        rd_re <= mem_re[raddr];
        rd_im <= mem_im[raddr];
    end

    // The sums of |X[k]|^2.  |X|^2 < 2^33, so 2^15 frames add up to < 2^48.
    (* no_rw_check *) logic [47:0] acc [0:N/2-1];
    logic [LOG2N-2:0] k = 0, acc_waddr = 0;      // k: the frequency, 0 .. N/2-1
    logic [47:0]      acc_rd, acc_wr = 0;
    logic             acc_we = 0;
    always_ff @(posedge clk) begin
        if (acc_we)
            acc[acc_waddr] <= acc_wr;
        acc_rd <= acc[k];
    end

    // ---- the state machine's registers ------------------------------------------
    typedef enum logic [2:0] {IDLE, RECORD, FFT, POWER, SEND} state_t;
    state_t           state = IDLE;
    logic [3:0]       D = 0, A = 0;  // keep 1 sample in 2^D; average 2^A frames
    logic             got_D  = 0;    // the first digit (D) has arrived
    logic [15:0]      skip   = 0;    // samples still to skip before keeping one
    logic [14:0]      frame  = 0;    // which frame, 0 .. 2^A - 1
    logic [LOG2N-1:0] n      = 0;    // RECORD: which sample, 0 .. N-1
    logic [3:0]       stage  = 0;    // FFT: which stage, 0 .. LOG2N-1
    logic [LOG2N-2:0] j      = 0;    // FFT: which butterfly, 0 .. N/2-1
    logic [2:0]       step   = 0;    // the step within a butterfly, or a k
    logic [1:0]       byte_i = 0;    // SEND: which byte of P[k]

    // ---- recording ----------------------------------------------------------------
    logic              keep;         // a new sample, and the 1 in 2^D we keep
    logic signed [8:0] x;            // the sample - 128:  -128 .. +127
    assign keep = (state == RECORD) && new_sample && (skip == 0);
    assign x    = $signed({1'b0, sample}) - 9'sd128;

    // Sample n is stored at address "n with its 10 bits in reverse order".  The
    // FFT splits the samples into evens and odds, each of those into evens and
    // odds, and so on; bit-reversed order is the order that leaves them in.
    // Then each stage combines neighbouring blocks, and X[k] ends up at k.
    function automatic logic [LOG2N-1:0] bit_reverse(input logic [LOG2N-1:0] v);
        for (int i = 0; i < LOG2N; i++)
            bit_reverse[i] = v[LOG2N-1-i];
    endfunction

    // The window for sample n.  A block RAM's output comes too late in the
    // clock (5.6 ns) to go straight into a multiplier, so it's copied into a
    // register first.  That takes the 2 clocks there are between samples at
    // 25 MS/s, so as soon as a sample is kept, look up the next one's.
    logic [10:0] hann_rom, hann_n;
    always_ff @(posedge clk) begin
        hann_rom <= hann[keep ? n + 1'b1 : n];
        hann_n   <= hann_rom;
    end

    // ---- the butterfly ----------------------------------------------------------
    // Stage s makes 2^(s+1)-point transforms out of pairs of 2^s-point ones.
    // If a is frequency lo of the first (the "even" samples) and b frequency
    // lo of the second ("odd"), then a + W b and a - W b are frequencies lo and
    // lo + 2^s of the bigger one, with W = exp(-2 pi i lo / 2^(s+1)): entry
    // lo * 2^(9-s) of the table.  Butterfly j works on addresses
    //   ia = j with a 0 put in at bit s  (= 2j - lo, where lo = j's bits below s)
    //   ib = ia + 2^s.
    logic [LOG2N-1:0] half, ia, ib;
    logic [LOG2N-2:0] lo, w_k;
    assign half  = 1 << stage;
    assign lo    = j & (half - 1);
    assign ia    = 2 * j - lo;
    assign ib    = ia + half;
    assign w_k   = lo << (LOG2N - 1 - stage);
    assign raddr = (state == FFT) ? ((step == 0) ? ia : ib) : k;

    logic signed [17:0] w_re_rom, w_im_rom, w_re, w_im;     // W (times 65536), copied
    always_ff @(posedge clk) begin                           //   into a register too:
        w_re_rom <= twiddle_re[w_k];                         //   ready by step 2
        w_im_rom <= twiddle_im[w_k];
        w_re     <= w_re_rom;
        w_im     <= w_im_rom;
    end

    logic signed [17:0] a_re = 0, a_im = 0, b_re = 0, b_im = 0;
    logic signed [35:0] p1 = 0, p2 = 0, p3 = 0, p4 = 0;     // the four products
    logic signed [37:0] top_re, top_im, bot_re, bot_im;      // a + W b, a - W b, times 65536
    assign top_re = (a_re <<< 16) + (p1 - p2);               // (<<< 16 is times 65536)
    assign top_im = (a_im <<< 16) + (p3 + p4);
    assign bot_re = (a_re <<< 16) - (p1 - p2);
    assign bot_im = (a_im <<< 16) - (p3 + p4);

    // v / 2^17 (undo the 65536, and halve), rounded to the nearest integer; an
    // exact half goes to the even neighbour, so the roundings don't add up to a
    // bias.  The answer always fits in 18 bits (see "Numbers" at the top).
    function automatic logic signed [17:0] halve(input logic signed [37:0] v);
        logic signed [37:0] r;
        r = v + 38'sd65535 + v[17];
        halve = r >>> 17;
    endfunction

    // ---- the power spectrum ---------------------------------------------------
    logic [36:0] power = 0;          // |X[k]|^2
    logic [47:0] sum   = 0;          // acc[k], out of the RAM
    logic [47:0] avg;                // SEND: sum / 2^A ...
    logic [31:0] P;                  // ...in 32 bits
    assign avg = sum >> A;
    assign P   = (avg[47:32] != 0) ? 32'hFFFFFFFF : avg[31:0];

    // ---- what we're doing now ---------------------------------------------------
    always_ff @(posedge clk) begin
        we       <= 0;
        acc_we   <= 0;
        tx_start <= 0;
        case (state)
            IDLE:
                // Two hex digits, D then A.  Anything else is ignored -- including
                // the junk byte the FT231X can send when the laptop opens the port.
                if (rx_valid && is_hex) begin
                    if (!got_D) begin
                        D     <= hex;
                        got_D <= 1;
                    end else begin
                        A     <= hex;
                        got_D <= 0;
                        frame <= 0;
                        skip  <= 0;
                        state <= RECORD;
                    end
                end
            RECORD:
                if (keep) begin
                    // ##########################################################
                    // ##  KEY LINE: take off the offset, multiply by the window,
                    // ##  and store at the bit-reversed address.
                    // ##########################################################
                    we    <= 1;
                    waddr <= bit_reverse(n);
                    wr_re <= x * $signed({1'b0, hann_n});
                    wr_im <= 0;
                    n     <= n + 1;                  // (wraps to 0 after N-1)
                    skip  <= (16'd1 << D) - 1;
                    if (n == N - 1)                  // that was the last one
                        state <= FFT;
                end else if (new_sample)
                    skip <= skip - 1;
            FFT: begin
                // One butterfly every 6 clocks.  stage, j and step start at 0.
                step <= step + 1;
                case (step)
                    0: ;                                     // the RAM reads a (raddr = ia)
                    1: begin a_re <= rd_re; a_im <= rd_im; end   // ...and then b
                    2: begin b_re <= rd_re; b_im <= rd_im; end
                    3: begin
                        // ######################################################
                        // ##  KEY LINE: W b, a complex multiply: four real
                        // ##  multiplies, on four of the FPGA's multipliers.
                        // ######################################################
                        p1 <= b_re * w_re;
                        p2 <= b_im * w_im;
                        p3 <= b_re * w_im;
                        p4 <= b_im * w_re;
                    end
                    4: begin
                        // ######################################################
                        // ##  KEY LINE: the butterfly.  (a + W b)/2 goes where a
                        // ##  was, and (a - W b)/2 (next clock) where b was.
                        // ######################################################
                        we    <= 1;
                        waddr <= ia;
                        wr_re <= halve(top_re);
                        wr_im <= halve(top_im);
                    end
                    5: begin
                        we    <= 1;
                        waddr <= ib;
                        wr_re <= halve(bot_re);
                        wr_im <= halve(bot_im);
                        step  <= 0;
                        j     <= j + 1;                      // (wraps to 0 after N/2-1)
                        if (j == N/2 - 1) begin              // the stage's last butterfly
                            stage <= stage + 1;
                            if (stage == LOG2N - 1) begin    // ...and the last stage
                                stage <= 0;
                                state <= POWER;
                            end
                        end
                    end
                endcase
            end
            POWER: begin
                // For each k: read X[k] and its sum so far, add |X[k]|^2.
                step <= step + 1;
                case (step)
                    0: ;                                     // the RAMs read X[k], acc[k]
                    1: begin
                        a_re <= rd_re;
                        a_im <= rd_im;
                        sum  <= (frame == 0) ? 48'd0 : acc_rd;   // first frame: from 0
                    end
                    2: power <= a_re * a_re + a_im * a_im;
                    3: begin
                        // ######################################################
                        // ##  KEY LINE: add this frame's |X[k]|^2 to the sum.
                        // ######################################################
                        acc_we    <= 1;
                        acc_waddr <= k;
                        acc_wr    <= sum + power;
                        step      <= 0;
                        k         <= k + 1;                  // (wraps to 0 after N/2-1)
                        if (k == N/2 - 1) begin
                            if (frame == (16'd1 << A) - 1)   // that was the last frame
                                state <= SEND;
                            else begin                       // record another
                                frame <= frame + 1;
                                skip  <= 0;
                                state <= RECORD;
                            end
                        end
                    end
                endcase
            end
            SEND:
                // Send P[k] = acc[k] / 2^A as 4 bytes, low byte first.
                case (step)
                    0: step <= 1;                            // the RAM reads acc[k]
                    1: begin                                 // take it out of the RAM
                        sum  <= acc_rd;
                        step <= 2;
                    end
                    2: if (!tx_busy && !tx_start) begin
                        // ######################################################
                        // ##  KEY LINE: the UART is free: send the next byte.
                        // ######################################################
                        tx_data  <= P[8*byte_i +: 8];
                        tx_start <= 1;
                        byte_i   <= byte_i + 1;
                        if (byte_i == 3) begin               // P[k] is done
                            step <= 0;
                            k    <= k + 1;
                            if (k == N/2 - 1)
                                state <= IDLE;
                        end
                    end
                endcase
        endcase
    end

    assign led = {sample[7:5], state == SEND, state == RECORD || state == FFT || state == POWER};
endmodule
