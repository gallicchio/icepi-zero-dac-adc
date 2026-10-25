// awgcap_slow_tb.sv -- simulate awgcap_slow.sv with no hardware at all.
//
// The testbench plays the laptop (serial bytes at 1 Mbaud) and a cable from the DAC
// to the ADC.  The waveform is a ramp, wave[i] = i mod 256, put straight into the RAM
// (sending 16384 bytes would take 164 ms of simulated time).  With k = 2 the DAC
// steps every 4 clocks and each recorded value is the mean of 4 ADC samples, which
// span two DAC samples: so the record should climb by 2 codes = 512 per value, start
// within a code of 0 (it is lined up with the loop), and wrap where the ramp does.
//
//   make sim-awgcap_slow
`timescale 1ns/1ps
module awgcap_slow_tb;
    logic clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    logic [7:0] dac, adc = 128;
    logic       dac_clk, adc_clk, tx;
    logic       rx = 1;
    logic [4:0] led;

    awgcap_slow dut (.clk(clk), .dac_d(dac), .dac_clk(dac_clk), .adc_d(adc),
                     .adc_clk(adc_clk), .uart_rx(rx), .uart_tx(tx), .led(led));

    // the cable: the AD9280 puts out the code it sampled 25 ns after its clock's edge
    always @(posedge adc_clk) adc <= #25 dac;

    initial for (int i = 0; i < 16384; i++) dut.wave[i] = 8'(i);

    task automatic send(input logic [7:0] c);          // 1 Mbaud: 1 us a bit
        rx = 0; #1000;
        for (int b = 0; b < 8; b++) begin rx = c[b]; #1000; end
        rx = 1; #1000;
    endtask

    // the laptop listens: bytes off uart_tx, two to a value, high byte first
    localparam int CHECK = 300;                         // values to check
    logic [7:0] c, hi_byte;
    int nbytes = 0, nvals = 0, bad = 0, v, expect_v;
    always @(negedge tx) begin
        #1500;                                          // the middle of data bit 0
        for (int b = 0; b < 8; b++) begin c[b] = tx; #1000; end
        if (nbytes % 2 == 0) hi_byte = c;
        else begin
            v = {hi_byte, c};
            // value n covers DAC samples 2n and 2n+1, each seen by two ADC samples
            expect_v = 256 * ((2 * nvals) % 256) + 256;
            if (nvals < 6 || nvals % 50 == 0 || nvals == 127 || nvals == 128)
                $display("value %4d = %5d  (%6.2f codes; a ramp would give about %6.2f)",
                         nvals, v, v / 256.0, expect_v / 256.0);
            // allow one code either way for the pipeline, except where the ramp wraps
            if ((nvals % 128) != 127 && (v < expect_v - 300 || v > expect_v + 300)) bad++;
            nvals++;
            if (nvals == CHECK) begin
                $display("%0d values checked, %0d out of place: %s", CHECK, bad,
                         bad == 0 ? "PASS" : "FAIL");
                $finish;
            end
        end
        nbytes++;
    end

    initial begin
        #2000;
        send("K"); send(8'd2);                          // one DAC sample every 4 clocks
        #5000;
        if (dut.k != 2) begin $display("FAIL: k = %0d after K 2", dut.k); $finish; end
        send("C");
        #300_000_000;
        $display("FAIL: timed out with %0d values", nvals);
        $finish;
    end
endmodule
