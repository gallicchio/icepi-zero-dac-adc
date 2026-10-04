// am_radio_tb.sv -- simulate am_radio.sv with no hardware at all.
//
// The "analog world" is a cable from the DAC to the ADC: the ADC sees the
// DAC's codes DELAY clocks later, as code = 0.776 x DAC + 27.5 (as measured
// with a real cable).  The testbench plays the laptop: it decodes the bytes on
// uart_tx into envelope samples, prints some, and checks
//   1. the envelope's average, which is the carrier: 0.776 x 69.5 codes at
//      the ADC, times 473.1, / 2^2 (g = 2) = 6375;
//   2. the pitch of the melody's first note, E4 = 329.63 Hz, from the times
//      the envelope crosses its average going up;
//   3. after "m3" and "g3", the 1 kHz tone, at half the size (g = 3).
//
//   make sim-am_radio       (about 40 s: 45 ms of the radio's time)
//   (or: iverilog -g2012 -o am_radio_tb.vvp am_radio_tb.sv am_radio.sv uart.sv && vvp am_radio_tb.vvp)
//
// am_check.py tests much more, much longer, with Verilator.
`timescale 1ns/1ps
module am_radio_tb;
    logic clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    logic [7:0] dac, adc;
    logic       dac_clk, adc_clk, tx;
    logic       rx = 1;
    logic [4:0] led;

    am_radio dut (.clk(clk), .adc_d(adc), .adc_clk(adc_clk), .dac_d(dac), .dac_clk(dac_clk),
                  .uart_rx(rx), .uart_tx(tx), .led(led));

    // ##########################################################################
    // ##  KEY LINES: the fake analog world.  Delay the DAC's codes by DELAY
    // ##  clocks, and scale them as the real cable and ADC do.
    // ##########################################################################
    localparam DELAY = 10;                          // clocks = 200 ns
    logic [7:0] pipe [0:DELAY];
    initial for (int k = 0; k <= DELAY; k++) pipe[k] = 128;
    always @(posedge clk) begin
        pipe[0] <= dac;
        for (int k = 1; k <= DELAY; k++) pipe[k] <= pipe[k-1];
    end
    assign adc = (776 * pipe[DELAY] + 28000) / 1000;   // round(0.776 x DAC + 27.5)

    // ---- play the laptop: send characters at 1 Mbaud (1 us per bit) ------------
    task automatic send(input logic [7:0] c);
        rx = 0; #1000;                                  // start bit
        for (int b = 0; b < 8; b++) begin rx = c[b]; #1000; end
        rx = 1; #1000;                                  // stop bit
    endtask

    // ...and listen: each byte, as uart_rx in uart.sv does, then join the pairs:
    // a byte with its top bit 0 is a sample's low 7 bits, the next one (top bit 1)
    // its high 7 bits.  (A high byte with no low byte before it is skipped.)
    localparam MAX = 4000;
    int         env [0:MAX-1];                      // the envelope samples
    real        t_us [0:MAX-1];                     // ...and when each arrived
    int         n = 0, low = -1, errors = 0;
    logic [7:0] c;
    always @(negedge tx) begin                      // a start bit has begun
        #1500;                                      // to the middle of data bit 0
        for (int b = 0; b < 8; b++) begin c[b] = tx; #1000; end
        if (tx !== 1) errors++;                     // no stop bit?
        if (c[7] == 0)
            low = c[6:0];
        else if (low >= 0 && n < MAX) begin
            env[n]  = {c[6:0], 7'(low)};
            t_us[n] = $realtime / 1000.0;
            n++;
            low = -1;
        end
    end

    // The average of env[a..b-1], and the frequency of the wiggles around it:
    // from the first to the last upward crossing of the average (each crossing
    // time found by drawing a straight line between the samples either side).
    task automatic analyze(input int a, input int b, output real mean, output real freq);
        real first, last, t;
        int  ups;
        mean = 0;
        for (int i = a; i < b; i++) mean += env[i];
        mean /= (b - a);
        ups = 0;
        for (int i = a + 1; i < b; i++)
            if (env[i - 1] < mean && env[i] >= mean) begin
                t = t_us[i - 1] + 40.0 * (mean - env[i - 1]) / (env[i] - env[i - 1]);  // 40 us apart
                if (ups == 0) first = t;
                last = t;
                ups++;
            end
        freq = (ups > 1) ? (ups - 1) / (last - first) * 1e6 : 0;
    endtask

    real mean1, f1, mean2, f2;
    int  n1, ok;
    initial begin
        // Part 1: power-up: the melody at 1 MHz, received at 1 MHz, g = 2
        #25_000_000;                                // 25 ms
        n1 = n;
        $display("%0d envelope samples in 25 ms (expect 25 per ms; %0d framing errors)", n, errors);
        $display("   t (ms)   envelope   (one every 0.4 ms from 6 ms: the first note, E4)");
        for (int i = 150; i < 230; i += 10)
            $display("  %7.3f   %6d", t_us[i] / 1000, env[i]);
        analyze(150, n1, mean1, f1);                // from 6 ms: the filters have filled up
        $display("melody: average %.0f (expect about 6375), first note %.2f Hz (E4 = 329.63)",
                 mean1, f1);

        // Part 2: the 1 kHz tone, and g = 3
        send("m"); send("3"); send("\n");
        send("g"); send("3"); send("\n");
        #20_000_000;                                // 20 ms
        analyze(n1 + 175, n, mean2, f2);            // from 7 ms after the commands
        $display("tone:   average %.0f (expect about 3187), frequency %.2f Hz (expect 1000.00)",
                 mean2, f2);
        $display("LEDs %b (left four: signal strength; rightmost: a note is playing)", led);
        ok = errors == 0 && n > 1100 && mean1 > 6000 && mean1 < 6750 && f1 > 328 && f1 < 331.3
             && mean2 > 3000 && mean2 < 3375 && f2 > 995 && f2 < 1005;
        if (ok) $display("PASS"); else $display("FAIL");
        $finish;
    end
endmodule
