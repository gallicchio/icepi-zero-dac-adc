// pll.sv -- a phase-locked loop in hardware: this board's oscillator follows the sine
// arriving at its ADC, updating 24 414 times a second.
//
// The oscillator is a DDS (tuning word tw).  The phase detector is a lock-in: ADC
// samples times sin and cos of the oscillator's phase, summed over 1024 samples
// (41 us), give I and Q; Q is proportional to the sine of the phase error.  A
// proportional-plus-integral loop filter turns Q into a correction of tw:
//
//     integ += Q >>> 17          tw = tw0 + (Q >>> 10) + integ
//
// For a full-scale input that is a loop bandwidth of about 50 Hz, damping 0.7.
// The DAC plays either the locked oscillator itself (command L) or, for testing on
// one board looped back, an independent test tone (command X).
//
// Serial port, 1,000,000 baud.  Laptop -> board, one line each:
//   "Fhhhhhhhh"   centre tuning word tw0 (also resets the integrator)
//   "Thhhhhhhh"   test-tone tuning word; "L" = DAC plays the oscillator, "X" = test tone
//   "O" / "C"     loop open (tw = tw0) / closed
// Board -> laptop, about 12 times a second: "tw I Q" as three 32-bit hex numbers.
module pll (
    input  logic       clk,
    output logic [7:0] dac_d = 128,
    output logic       dac_clk,
    input  logic [7:0] adc_d,
    output logic       adc_clk,
    input  logic       uart_rx,
    output logic       uart_tx,
    output logic [4:0] led
);
    logic signed [7:0] sine_table [0:255];
    initial for (int i = 0; i < 256; i++)
        sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    // ---- control registers (set over the serial port, below) --------------------
    logic [31:0] tw0 = 32'd85899346, tw_test = 32'd85899346;   // 1 MHz
    logic closed = 1, play_test = 0, cmd_reset = 0;

    // ---- the oscillator and the test tone -------------------------------------
    logic [31:0] tw = 32'd85899346, phase = 0, tphase = 0;
    always_ff @(posedge clk) begin
        phase  <= phase + tw;
        tphase <= tphase + tw_test;
        dac_d  <= (play_test ? sine_table[tphase[31:24]] : sine_table[phase[31:24]]) + 128;
    end
    assign dac_clk = ~clk;

    // ---- ADC at 25 MS/s, and the phase detector --------------------------------
    logic adc_clk_r = 0;
    logic signed [8:0] x = 0;
    logic [7:0] ph_at_sample = 0;
    logic new_sample = 0;
    always_ff @(posedge clk) begin
        adc_clk_r <= ~adc_clk_r;
        new_sample <= 0;
        if (adc_clk_r == 0) begin
            x <= $signed({1'b0, adc_d}) - 9'sd128;
            ph_at_sample <= phase[31:24];
            new_sample <= 1;
        end
    end
    assign adc_clk = adc_clk_r;
    logic signed [7:0] rs = 0, rc = 0;
    logic mult = 0;
    always_ff @(posedge clk) begin
        mult <= new_sample;
        if (new_sample) begin
            rs <= sine_table[ph_at_sample];
            rc <= sine_table[ph_at_sample + 8'd64];
        end
    end
    logic signed [31:0] acc_i = 0, acc_q = 0, I = 0, Q = 0;
    logic [9:0] n = 0;
    logic update = 0;
    always_ff @(posedge clk) begin
        update <= 0;
        if (mult) begin
            n <= n + 1;
            if (n == 10'd1023) begin
                // ##############################################################
                // ##  KEY LINE: the phase detector's answer, every 1024 samples.
                // ##  Q is (amplitude) x sin(phase error).
                // ##############################################################
                I <= acc_i + x * rs; Q <= acc_q + x * rc;
                acc_i <= 0; acc_q <= 0; update <= 1;
            end else begin
                acc_i <= acc_i + x * rs; acc_q <= acc_q + x * rc;
            end
        end
    end
    // ---- loop filter --------------------------------------------------------------
    // The correction is formed as a SIGNED value first.  Written inline as
    // tw0 + (Q >>> 10) + integ, SystemVerilog would treat the whole sum as unsigned
    // (tw0 is), turn >>> into a logical shift, and a negative Q into a huge positive kick.
    logic signed [31:0] integ = 0;
    logic signed [31:0] corr;
    assign corr = (Q >>> 10) + integ;
    logic upd2 = 0;
    always_ff @(posedge clk) begin
        upd2 <= update;
        // ######################################################################
        // ##  KEY LINES: the loop filter.  The integral collects the error so
        // ##  that, once locked, the oscillator sits at the right frequency with
        // ##  no error left; the proportional term steadies the loop.
        // ######################################################################
        if (update && closed) integ <= integ + (Q >>> 17);
        if (upd2) tw <= closed ? tw0 + corr : tw0;
        if (cmd_reset) integ <= 0;
    end

    // ---- serial port: commands in, reports out --------------------------------------
    logic [7:0] rx;
    logic rxv, busy;
    uart_rx #(.CLKS_PER_BIT(50)) u_rx (.clk(clk), .rx(uart_rx), .data(rx), .valid(rxv));
    logic [7:0] cmd = 0;
    logic [31:0] val = 0;
    function automatic logic [3:0] unhex(input logic [7:0] c);
        unhex = (c >= "a") ? c - "a" + 10 : (c >= "A") ? c - "A" + 10 : c - "0";
    endfunction
    always_ff @(posedge clk) begin
        cmd_reset <= 0;
        if (rxv) begin
            if (rx == "F" || rx == "T") begin cmd <= rx; val <= 0; end
            else if (rx == "L") play_test <= 0;
            else if (rx == "X") play_test <= 1;
            else if (rx == "O") closed <= 0;
            else if (rx == "C") closed <= 1;
            else if (rx == "\n" || rx == "\r") begin
                if (cmd == "F") begin tw0 <= val; cmd_reset <= 1; end
                if (cmd == "T") tw_test <= val;
                cmd <= 0;
            end else val <= {val[27:0], unhex(rx)};
        end
    end
    logic [21:0] tick = 0;
    logic [31:0] r_tw = 0, r_i = 0, r_q = 0;
    logic [4:0] idx = 31;
    logic st = 0;
    logic [7:0] d = 0;
    uart_tx #(.CLKS_PER_BIT(50)) u_tx (.clk(clk), .data(d), .start(st), .busy(busy), .tx(uart_tx));
    function automatic logic [7:0] hex(input logic [3:0] v); hex = v < 10 ? "0" + v : "a" + v - 10; endfunction
    logic [31:0] word;
    logic [4:0]  nib;
    assign word = (idx < 8) ? r_tw : (idx < 17) ? r_i : r_q;
    assign nib  = (idx < 8) ? 7 - idx : (idx < 17) ? 16 - idx : 25 - idx;
    always_ff @(posedge clk) begin
        tick <= tick + 1; st <= 0;
        if (tick == 0) begin r_tw <= tw; r_i <= I; r_q <= Q; idx <= 0; end
        else if (idx < 27 && !busy && !st) begin
            d <= (idx == 8 || idx == 17) ? " " : (idx == 26) ? "\n" : hex(word[nib*4 +: 4]);
            st <= 1; idx <= idx + 1;
        end
    end
    assign led = {closed, play_test, 3'b0};
endmodule
