// adda_io.v -- the converter pins, and nothing else.
//
// The same clocking as the bare-Verilog tutorials: the DAC takes a new value
// every clock (50 MS/s) on the rising edge of the inverted clock, and the ADC
// is clocked at clk/2 = 25 MS/s and read just before each rising edge of its
// clock.  Every peripheral that wants the converters goes through here.

module adda_io (
    input  wire       clk,          // the SoC's 50 MHz system clock
    // the pins
    input  wire [7:0] adc_d,
    output wire       adc_clk,
    output reg  [7:0] dac_d = 128,
    output wire       dac_clk,
    // the peripherals' side
    input  wire [7:0] dac_value,    // what the DAC should output (0..255)
    output reg  [7:0] adc_sample = 128,
    output reg        adc_valid = 0 // high for one clock when adc_sample is new
);
    always @(posedge clk)
        dac_d <= dac_value;
    assign dac_clk = ~clk;

    reg adc_clk_r = 0;
    always @(posedge clk) begin
        adc_clk_r <= ~adc_clk_r;
        adc_valid <= 0;
        if (adc_clk_r == 0) begin
            adc_sample <= adc_d;
            adc_valid  <= 1;
        end
    end
    assign adc_clk = adc_clk_r;
endmodule
