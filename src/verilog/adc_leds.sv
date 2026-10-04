// adc_leds.sv -- the ADC's reading on the five LEDs: the world's slowest voltmeter.
//
// The ADC is clocked at 25 MHz and its top five bits go straight to the LEDs:
// -5 V lights none, 0 V lights 01111, +5 V lights all five.  One LED step is
// 8 ADC codes, about 0.32 V.
//
// So that there is something to look at without a function generator, the DAC
// plays a very slow ramp (the counter of counter.sv, wired to the DAC): connect
// the DAC output to the ADC input with a cable and the LEDs count up for 5.4 s,
// then drop back.

module adc_leds (
    input  logic       clk,         // 50 MHz
    input  logic [7:0] adc_d,       // the ADC's 8 data pins (adc_d[7] is the MSB)
    output logic       adc_clk,     // the ADC's clock: it takes a sample on each rising edge
    output logic [7:0] dac_d,
    output logic       dac_clk,
    output logic [4:0] led
);
    // ---- the ADC: a 25 MHz clock, and a register to catch each sample ------
    logic       adc_clk_r = 0;
    logic [7:0] sample    = 0;

    always_ff @(posedge clk) begin
        // ######################################################################
        // ##  KEY LINE 1: flip the ADC's clock on every 50 MHz clock edge.
        // ##  20 ns high, 20 ns low: a 25 MHz clock, 25 million samples a second.
        // ######################################################################
        adc_clk_r <= ~adc_clk_r;

        // ######################################################################
        // ##  KEY LINE 2: catch the ADC's output just before its clock rises
        // ##  again.  That is when the data pins have been steady the longest.
        // ######################################################################
        if (adc_clk_r == 1'b0)          // adc_clk is low now, and rises at this same edge:
            sample <= adc_d;            // read the pins just before it does
    end
    assign adc_clk = adc_clk_r;

    assign led = sample[7:3];           // the top five bits of the reading

    // ---- the DAC: a slow ramp, so a cable from DAC to ADC makes the LEDs count
    logic [27:0] count = 0;
    always_ff @(posedge clk)
        count <= count + 1;
    assign dac_d   = count[27:20];      // one DAC step every 2^20 clocks (21 ms)
    assign dac_clk = ~clk;              // as in sawtooth.sv
endmodule
