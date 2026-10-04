// control.sv -- a PID controller in gateware, one update per ADC sample (25 MS/s), with the
// loop closed through the real world (DAC OUT -> whatever you wire -> ADC IN) or through a
// plant simulated inside the FPGA, with the ADC as a disturbance the controller must fight.
// The laptop sets the gains, steps the setpoint, and reads back a 16384-sample record.
// Section 7.06; control.py does the laptop side, control_model.py is the same loop in Python.
//
// The controller:  e = setpoint - measurement          (in ADC codes)
//                  u = Kp e + Ki sum(e) + Kd (e - e_prev)
//                  DAC = 128 + bias + u, saturated to 0..255.
// The integrator stops integrating while the DAC is pinned at a rail and the error would
// push it further ("conditional integration": the anti-windup every real controller has),
// and is clamped at +-131071 codes; it is held at zero while Ki is 0 or the loop is open,
// so turning the integrator on starts it clean.  The I term uses the sum as it was before
// this sample's error is added (one sample late: it is the slow term and does not mind).
//
// Three plants, 'M':
//   0  the real world.  DAC = 128 + bias + u leaves DAC OUT; whatever comes back at ADC IN
//      is the measurement.  A loopback cable is a pure delay (gain 0.776, 1.07); an RC is
//      a first-order plant (4.08); an LED and a photodiode (4.07) are a "noise eater".
//   1  a first-order lag inside the FPGA, y <= y + (u - y) / 2^K, time constant 2^K
//      samples; the measurement is y + (ADC - 128), so the M2k's W1 into ADC IN is a
//      disturbance.  The DAC plays u (controller output) or y (plant output), 'O'.
//   2  a resonator inside the FPGA: v <= v + w0^2 (u - y) - v / 2^Q ; y <= y + v (the
//      semi-implicit Euler step, so it stays stable at any Q), w0 = 2 pi f0 / fs, same
//      disturbance and output choice.  It is a mass on a spring, a laser cavity's piezo, a
//      qubit's readout resonator: anything that rings.
//   In modes 1 and 2 the plant's input can be delayed 'L' extra samples, to see what
//   latency does to the same plant.  The internal loop is 2 samples + L round trip.
//
// LATENCY, counted in clocks.  The ADC's word is registered at the clock edge where adc_clk
// rises (edge 0, as capture.sv).  Edge 1: e, and the three products into the multipliers'
// registers.  Edge 2: the sum, the bias, the saturation, and dac_d changes.  So the DAC word
// changes 2 clocks = 40 ns after the ADC word was registered (the word has been valid on the
// pins for about 15 ns when it is taken, so pin-to-pin it is 55 ns), and the DAC latches it
// 10 ns later on dac_clk = ~clk.  Around the real loop (1.07's table): 160 ns from the ADC
// sampling its input to the FPGA holding the word (3 pipeline cycles + 25 ns, read on the
// 4th edge), 40 ns here, 10 ns to the DAC latch, about 35 ns of analog (DAC output stage,
// cable, ADC front end), then up to 40 ns waiting for the ADC's next sampling edge:
// 280 ns = 7 samples, with the signal reaching the ADC only a few ns after the 6th edge, so
// a short cable may make it 6.  The oscillation period at the critical gain measures it.
//
// The laptop's protocol (1,000,000 baud, 8N1; two-byte values big-endian, signed):
//   'P' kp(2)   Kp in 1/1024ths                     (Q6.10: -32 .. +32)
//   'I' ki(2)   Ki in 1/65536ths per sample          (-0.5 .. +0.5 per sample)
//   'D' kd(2)   Kd in 1/256ths, per sample of difference   (Q8.8: -128 .. +128)
//               (Red Pitaya's PID scales its three gains differently too: the integrator
//               adds 25 million times a second, the differentiator sees 40 ns steps)
//   'S' sp(2)   setpoint, ADC codes relative to mid-scale (128); clipped to +-511
//   'J' j(2)    the step: with 'T' on the setpoint alternates S and S + J
//   'N' n       half-period of the step, 2^n samples (7..24; 2^12 = 164 us)
//   'T' 0/1     stepping off/on
//   'B' b       bias, signed: DAC = 128 + b + u (where the plant's operating point is)
//   'K' k       mode 1: time constant 2^k samples (0..15; 4 = 16 samples = 0.64 us)
//   'R' r(2)    mode 2: (2 pi f0 / fs)^2 x 2^20, unsigned (662 = 100 kHz, 65535 = 995 kHz)
//   'Q' q       mode 2: damping 1/2^q per sample (0..12): Q = 2 pi f0 / fs x 2^q
//   'M' m       plant: 0 real world, 1 lag, 2 resonator
//   'O' o       modes 1-2: the DAC plays 0 = 128 + b + u, 1 = 128 + y
//   'E' e       1 = loop closed; 0 = open: u = setpoint, straight to the DAC / the plant
//               (a step of the plant alone), integrator cleared
//   'L' l       modes 1-2: extra samples of delay before the plant (0..63)
//   'X' x       capture decimation: keep 1 sample in 2^x (0..15)
//   'V' v       capture signals: high nibble A, low nibble B: 0 adc - 128, 1 setpoint,
//               2 e, 3 u, 4 y (the plant's output)
//   'C'         capture 2^LOGN samples of (A, B): A then B, each 16-bit signed big-endian,
//               65536 bytes at LOGN = 14 (0.66 s).  With 'T' on the record begins 64 x 2^x
//               samples before a rising step of the setpoint, so the step is at sample 64.
//   '?'         read everything back: 32 bytes, 0xA5 then P I D S J R (2 bytes each), N T B
//               K Q M O E L X V (1 each, V = A << 4 | B), then the live x, e, u, y (2 each).
//               control.py prints it after every setting, so a mismatch shows at once.
//   Unknown bytes are ignored; a command's argument bytes are taken in order and must
//   arrive within 1.3 ms, or the command is forgotten.
//
// LEDs:  led[0] in lock (|e| <= 1 code: the brightness is the fraction of the time it is),
//        led[1] the DAC hit a rail in the last 84 ms, led[2] loop closed, led[3] recording
//        (or waiting for the step), led[4] sending.
module control #(
    parameter integer LOGN   = 14,          // samples in a capture: 2^14 = 16384
    parameter integer LOGPRE = 6            // samples before the step in a capture: 64
) (
    input  logic       clk,                 // 50 MHz
    input  logic       uart_rx,             // from the laptop
    output logic       uart_tx,             // to the laptop
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    output logic [4:0] led
);
    localparam integer N = 1 << LOGN;

    // ---- the serial port, both directions (uart.sv) -----------------------------------
    logic [7:0] rx_data, tx_data = 0;
    logic       rx_valid, tx_start = 0, tx_busy;
    uart_rx #(.CLKS_PER_BIT(50)) urx (.clk(clk), .rx(uart_rx), .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLKS_PER_BIT(50)) utx (.clk(clk), .data(tx_data), .start(tx_start),
                                      .busy(tx_busy), .tx(uart_tx));

    // ---- the settings, as the laptop left them ----------------------------------------
    logic signed [15:0] kp = 0, ki = 0, kd = 0;    // 'P' 'I' 'D'
    logic signed [15:0] sp_base = 0, jump = 0;     // 'S' 'J'
    logic        [4:0]  nstep   = 5'd12;           // 'N'
    logic               stepping = 0;              // 'T'
    logic signed [7:0]  bias    = 0;               // 'B'
    logic        [3:0]  klag    = 4'd4;            // 'K'
    logic        [15:0] rword   = 16'd662;         // 'R': 100 kHz
    logic        [3:0]  qshift  = 4'd10;           // 'Q': Q = 25.7 at 100 kHz
    logic        [1:0]  mode    = 0;               // 'M'
    logic               osel    = 0;               // 'O'
    logic               enable  = 0;               // 'E'
    logic        [5:0]  ldelay  = 0;               // 'L'
    logic        [3:0]  decim   = 0;               // 'X'
    logic        [2:0]  sel_a   = 3'd0, sel_b = 3'd3;   // 'V': adc and u
    logic               arm     = 0;               // 'C', for one clock
    logic               ask     = 0;               // '?', for one clock

    // ---- the command parser: a command byte, then its arguments in order ---------------
    // A command's argument bytes must follow within 1.3 ms (2^16 clocks); after that a
    // half-done command is forgotten, so the byte the FT231X can emit when the laptop opens
    // the port cannot swallow the first real command's bytes.
    logic [7:0]  cmd   = 0;                        // the command being filled in; 0 = none
    logic [7:0]  left  = 0;                        // argument bytes still to come
    logic [7:0]  arg0  = 0;                        // the first of two argument bytes
    logic [15:0] quiet = 0;                        // clocks since the last byte, saturating
    always_ff @(posedge clk) begin
        arm <= 0;
        ask <= 0;
        quiet <= rx_valid ? 16'd0 : (quiet == 16'hFFFF) ? quiet : quiet + 16'd1;
        if (!rx_valid && quiet == 16'hFFFE)
            cmd <= 0;
        else if (rx_valid) begin
            if (cmd == 0)
                case (rx_data)
                    "P", "I", "D", "S", "J", "R":
                        begin cmd <= rx_data; left <= 2; end
                    "N", "T", "B", "K", "Q", "M", "O", "E", "L", "X", "V":
                        begin cmd <= rx_data; left <= 1; end
                    "C": arm <= 1;
                    "?": ask <= 1;
                    default: ;                      // not a command: ignored
                endcase
            else begin
                left <= left - 1;
                if (left == 2)
                    arg0 <= rx_data;
                else begin                          // the last argument byte: act on it
                    cmd <= 0;
                    case (cmd)
                        "P": kp      <= {arg0, rx_data};
                        "I": ki      <= {arg0, rx_data};
                        "D": kd      <= {arg0, rx_data};
                        "S": sp_base <= {arg0, rx_data};
                        "J": jump    <= {arg0, rx_data};
                        "R": rword   <= {arg0, rx_data};
                        "N": nstep   <= (rx_data > 24) ? 5'd24 : (rx_data < 1) ? 5'd1 : rx_data[4:0];
                        "T": stepping <= rx_data[0];
                        "B": bias    <= rx_data;
                        "K": klag    <= rx_data[3:0];
                        "Q": qshift  <= (rx_data > 12) ? 4'd12 : rx_data[3:0];
                        "M": mode    <= (rx_data > 2) ? 2'd0 : rx_data[1:0];
                        "O": osel    <= rx_data[0];
                        "E": enable  <= rx_data[0];
                        "L": ldelay  <= rx_data[5:0];
                        "X": decim   <= rx_data[3:0];
                        "V": begin sel_a <= rx_data[6:4]; sel_b <= rx_data[2:0]; end
                        default: ;
                    endcase
                end
            end
        end
    end

    // ---- the ADC at 25 MS/s, as in capture.sv: edge 0 -------------------------------------
    // new_sample marks edge 1 (the clock after the word was registered), step marks edge 2.
    logic adc_clk_r = 0, new_sample = 0, step = 0;
    logic signed [8:0] x = 0;                       // ADC - 128
    always_ff @(posedge clk) begin
        adc_clk_r  <= ~adc_clk_r;
        new_sample <= 0;
        step       <= new_sample;
        if (adc_clk_r == 0) begin                   // adc_clk is about to rise: edge 0
            x <= $signed({1'b0, adc_d}) - 9'sd128;
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;

    // ---- the setpoint: S, or S + J in the second half of every 2^(N+1) samples ------------
    logic [25:0]        c = 0;                      // counts samples; bit N picks S or S + J
    logic [25:0]        c1;
    logic signed [16:0] sp_sum;
    logic signed [10:0] sp = 0;                     // this sample's setpoint, +-511
    assign c1 = c + 26'd1;
    assign sp_sum = 17'(sp_base) + ((stepping && c1[nstep]) ? 17'(jump) : 17'sd0);
    always_ff @(posedge clk)
        if (step) begin
            c  <= c1;
            sp <= (sp_sum > 17'sd511) ? 11'sd511 : (sp_sum < -17'sd511) ? -11'sd511 : 11'(sp_sum);
        end

    // ---- edge 1: the measurement, the error, and the three products ------------------------
    // The plant's wall, 2047 codes x 256, as two literals.  Not "-22'(YMAX)": Yosys drops
    // the minus sign of a negated size cast (Icarus does not), and the first build of this
    // design sat at the lower wall on the board while every simulation passed.
    localparam logic signed [21:0] YMAX = 22'sd524032;
    localparam logic signed [21:0] YMIN = -22'sd524032;
    logic signed [20:0] y_state   = 0;              // the plant's output, in codes x 256
    logic signed [31:0] vel_state = 0;              // its velocity, in codes/sample x 65536
    logic signed [12:0] y_int;                      // the plant's output in whole codes
    logic signed [13:0] meas;
    logic signed [14:0] e_c;
    assign y_int = (mode == 0) ? 13'sd0 : y_state[20:8];
    assign meas  = 14'(y_int) + 14'(x);
    // ##########################################################################
    // ##  KEY LINE: the error.  What you asked for, minus what you measured.
    // ##########################################################################
    assign e_c   = 15'(sp) - 15'(meas);

    logic signed [14:0] e_r = 0, e_prev = 0;
    logic signed [15:0] de_c;
    logic signed [17:0] integ = 0;                  // the running sum of e, +-131071
    logic signed [18:0] integ_sum;
    logic signed [30:0] pp = 0;                     // Kp e
    logic signed [31:0] pd = 0;                     // Kd (e - e_prev)
    logic signed [33:0] pi = 0;                     // Ki sum(e)
    logic               sat_hi = 0, sat_lo = 0;     // the DAC was pinned, last sample
    assign de_c      = 16'(e_c) - 16'(e_prev);
    assign integ_sum = 19'(integ) + 19'(e_c);
    always_ff @(posedge clk)
        if (new_sample) begin
            // ######################################################################
            // ##  KEY LINE: the three terms, each a multiply into a DSP block.
            // ######################################################################
            pp     <= kp * e_c;
            pd     <= kd * de_c;
            pi     <= ki * integ;
            e_r    <= e_c;
            e_prev <= e_c;
            if (!enable || ki == 16'sd0)            // no integrator: no sum to wake up later
                integ <= 0;
            else if (!((sat_hi && e_c > 0) || (sat_lo && e_c < 0)))      // anti-windup
                integ <= (integ_sum > 19'sd131071) ? 18'sd131071 :
                         (integ_sum < -19'sd131071) ? -18'sd131071 : 18'(integ_sum);
        end

    // ---- edge 2: the sum, the bias, the saturation: the DAC word -----------------------------
    logic signed [36:0] dsum;                       // 128 + bias + u, in 1/1024ths of a code
    logic signed [8:0]  base;                       // 128 + bias
    logic signed [26:0] dac_c;                      // 128 + bias + u, whole codes, unclipped
    logic        [7:0]  dac_sat, y_dac;
    logic signed [9:0]  u_out;                      // what actually went out, -255..255
    logic signed [13:0] y_plus;
    logic signed [8:0]  u = 0;
    assign base    = 9'sd128 + 9'(bias);
    // (Kp e is in 1/1024ths already; Ki sum(e) in 1/65536ths, so / 64; Kd de in 1/256ths, so x 4.
    //  Flooring Ki's term to 1/1024ths first changes nothing: floor((n + f) / 1024) = floor(n / 1024).)
    assign dsum    = 37'(pp) + 37'(pi >>> 6) + (37'(pd) <<< 2) + (37'(base) <<< 10);
    // ##########################################################################
    // ##  KEY LINE: the loop open or closed, then the rails.
    // ##########################################################################
    assign dac_c   = enable ? dsum[36:10] : 27'(sp) + 27'(base);
    assign dac_sat = (dac_c > 27'sd255) ? 8'd255 : (dac_c < 27'sd0) ? 8'd0 : dac_c[7:0];
    assign u_out   = 10'($signed({2'b0, dac_sat})) - 10'(base);
    assign y_plus  = 14'(y_int) + 14'sd128;
    assign y_dac   = (y_plus > 14'sd255) ? 8'd255 : (y_plus < 14'sd0) ? 8'd0 : y_plus[7:0];
    always_ff @(posedge clk)
        if (step) begin
            dac_d  <= (mode != 0 && osel) ? y_dac : dac_sat;
            u      <= u_out[8:0];
            sat_hi <= dac_c > 27'sd255;
            sat_lo <= dac_c < 27'sd0;
        end
    assign dac_clk = ~clk;

    // ---- the plant inside the FPGA (modes 1 and 2) ---------------------------------------
    // Its input is u from L + 1 samples ago: a shift register of 64 nine-bit values whose
    // entry 0 is the last sample's u, tapped at entry L.
    logic [64*9-1:0] uline = 0;
    always_ff @(posedge clk)
        if (step)
            uline <= {uline[63*9-1:0], u_out[8:0]};
    logic signed [8:0]  u_plant;
    logic signed [21:0] d_c;                        // (u - y) in codes x 256
    logic signed [17:0] d18;                        // the same, in codes x 32
    assign u_plant = uline[ldelay * 9 +: 9];
    assign d_c     = (22'(u_plant) <<< 8) - 22'(y_state);
    assign d18     = d_c[20:3];

    // edge 1: the pieces that only need last sample's state
    logic signed [21:0] lag_r  = 0;                 // mode 1: (u - y) / 2^K
    logic signed [34:0] prod   = 0;                 // mode 2: (u - y) w0^2, scaled
    logic signed [31:0] damp_r = 0;                 // mode 2: v / 2^Q
    always_ff @(posedge clk)
        if (new_sample) begin
            lag_r  <= d_c >>> klag;
            prod   <= d18 * $signed({1'b0, rword});
            damp_r <= vel_state >>> qshift;
        end

    // edge 2: the state update.  prod / 2^9 is w0^2 (u - y) in velocity units.
    logic signed [32:0] vel_new;
    logic signed [21:0] y_new;
    assign vel_new = 33'(vel_state) + 33'(prod >>> 9) - 33'(damp_r);
    assign y_new   = (mode == 1) ? 22'(y_state) + lag_r : 22'(y_state) + 22'(vel_new >>> 8);
    always_ff @(posedge clk)
        if (step) begin
            if (mode == 0 || mode == 3) begin
                y_state   <= 0;
                vel_state <= 0;
            end else if (y_new > YMAX) begin        // the wall: stop there
                y_state   <= YMAX[20:0];
                vel_state <= 0;
            end else if (y_new < YMIN) begin
                y_state   <= YMIN[20:0];
                vel_state <= 0;
            end else begin
                // ##################################################################
                // ##  KEY LINE: the plant.  A lag: y moves 1/2^K of the way to u.
                // ##  A resonator: the velocity feels the spring, then y moves.
                // ##################################################################
                y_state   <= y_new[20:0];
                vel_state <= (mode == 1) ? 32'sd0 : vel_new[31:0];
            end
        end

    // ---- the capture: 2^LOGN samples of two signals, then the dump (capture.sv) -------------
    logic [31:0]      mem [0:N-1];
    logic [LOGN-1:0]  addr = 0;
    logic [15:0]      skip = 0;
    logic [31:0]      rdata = 0;                    // the word read from mem (only that, so
                                                    // Yosys makes it the block RAM's own register)
    logic [31:0]      word = 0;                     // the bytes still to go, next one on top
    logic [2:0]       bi   = 0;
    logic [255:0]     sreg = 0;                     // the '?' frame, next byte on top
    logic [5:0]       sn   = 0;                     // its bytes still to go
    typedef enum logic [2:0] {IDLE, WAIT, RECORD, SEND, STAT} state_t;
    state_t state = IDLE;

    // the trigger: 2^LOGPRE x 2^X samples before bit N of the counter rises
    logic [25:0] trig, cmask;
    logic        at_trig;
    assign trig    = (26'd1 << nstep) - (26'(1 << LOGPRE) << decim);
    assign cmask   = (26'd2 << nstep) - 26'd1;
    assign at_trig = (c & cmask) == (trig & cmask);

    // the two signals, as 16-bit values, chosen by 'V'
    logic signed [15:0] val_a, val_b;
    always_comb begin
        case (sel_a)
            3'd0:    val_a = 16'(x);
            3'd1:    val_a = 16'(sp);
            3'd2:    val_a = 16'(e_r);
            3'd3:    val_a = 16'(u_out);
            3'd4:    val_a = 16'(y_int);
            default: val_a = 16'sd0;
        endcase
        case (sel_b)
            3'd0:    val_b = 16'(x);
            3'd1:    val_b = 16'(sp);
            3'd2:    val_b = 16'(e_r);
            3'd3:    val_b = 16'(u_out);
            3'd4:    val_b = 16'(y_int);
            default: val_b = 16'sd0;
        endcase
    end

    logic do_store;
    assign do_store = step && ((state == RECORD && skip == 0) || (state == WAIT && at_trig));
    always_ff @(posedge clk)
        if (do_store)
            // ##########################################################################
            // ##  KEY LINE: store this sample's pair; with 'T' on, the record starts
            // ##  64 samples before the setpoint steps.
            // ##########################################################################
            mem[addr] <= {val_a, val_b};

    always_ff @(posedge clk) begin
        tx_start <= 0;
        case (state)
            IDLE:
                if (arm) begin
                    addr  <= 0;
                    skip  <= 0;
                    bi    <= 0;
                    state <= state_t'(stepping ? WAIT : RECORD);
                end else if (ask) begin             // '?': every register, and the live signals
                    sreg  <= {8'hA5, kp, ki, kd, sp_base, jump, rword, 3'd0, nstep, 7'd0, stepping,
                              bias, 4'd0, klag, 4'd0, qshift, 6'd0, mode, 7'd0, osel, 7'd0, enable,
                              2'd0, ldelay, 4'd0, decim, 1'b0, sel_a, 1'b0, sel_b,
                              16'(x), 16'(e_r), 16'(u), 16'(y_int)};
                    sn    <= 6'd32;
                    state <= STAT;
                end
            WAIT:
                if (step && at_trig) begin          // sample 0 is being stored now
                    addr  <= 1;
                    skip  <= (16'd1 << decim) - 16'd1;
                    state <= RECORD;
                end
            RECORD:
                if (step) begin
                    if (skip == 0) begin
                        addr <= addr + 1;
                        skip <= (16'd1 << decim) - 16'd1;
                        if (addr == N - 1)          // that was the last one
                            state <= SEND;          // (addr wraps back to 0)
                    end else
                        skip <= skip - 1;
                end
            SEND:
                if (!tx_busy && !tx_start) begin
                    if (bi == 0)                    // fetch the word (one clock)...
                        bi <= 1;
                    else if (bi == 1) begin         // ...and take it (another)
                        word <= rdata;
                        bi   <= 2;
                    end else begin                  // send its 4 bytes, top first
                        tx_data  <= word[31:24];
                        word     <= {word[23:0], 8'h00};
                        tx_start <= 1;
                        if (bi == 5) begin
                            bi   <= 0;
                            addr <= addr + 1;
                            if (addr == N - 1)
                                state <= IDLE;
                        end else
                            bi <= bi + 1;
                    end
                end
            STAT:
                if (!tx_busy && !tx_start) begin
                    tx_data  <= sreg[255:248];
                    sreg     <= {sreg[247:0], 8'h00};
                    tx_start <= 1;
                    sn       <= sn - 1;
                    if (sn == 1)
                        state <= IDLE;
                end
            default: state <= IDLE;
        endcase
    end
    always_ff @(posedge clk)
        if (state == SEND && bi == 0)
            rdata <= mem[addr];

    // ---- LEDs ------------------------------------------------------------------------------
    logic [21:0] sat_stretch = 0;                   // 2^22 clocks = 84 ms
    always_ff @(posedge clk)
        if (step && (sat_hi || sat_lo))
            sat_stretch <= '1;
        else if (sat_stretch != 0)
            sat_stretch <= sat_stretch - 1;
    assign led = {state == SEND || state == STAT, state == RECORD || state == WAIT, enable, sat_stretch != 0,
                  enable && (e_r >= -15'sd1 && e_r <= 15'sd1)};
endmodule
