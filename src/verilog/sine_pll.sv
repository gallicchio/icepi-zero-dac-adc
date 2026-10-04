// sine_pll.sv -- sine.sv with the DAC at 100 MS/s instead of 50, clocked by a PLL.
//
// Only three things change from sine.sv: the clock comes from pll100.sv, the DDS
// waits for the PLL to lock, and the tuning word is for 100 MHz:
//
//     f = TW * 100 MHz / 2^32,   so   TW = round(f / 100 MHz * 2^32)

module sine_pll #(
    parameter logic [31:0] TW = 32'd42949673    // 1.000 000 MHz at 100 MS/s
) (
    input  logic       clk,                     // 50 MHz
    output logic [7:0] dac_d,
    output logic       dac_clk
);
    // ##########################################################################
    // ##  KEY LINE: the PLL makes clk100 from the 50 MHz clk.  Everything
    // ##  below runs on clk100 instead of clk.
    // ##########################################################################
    logic clk100, locked;
    pll100 pll (.clk(clk), .clk100(clk100), .locked(locked));

    logic signed [7:0] sine_table [0:255];
    initial
        for (int i = 0; i < 256; i++)
            sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    logic [31:0] phase = 0;
    always_ff @(posedge clk100)
        if (locked) begin                       // wait until the PLL has settled
            phase <= phase + TW;
            dac_d <= sine_table[phase[31:24]] + 128;
        end

    assign dac_clk = ~clk100;                   // 5 ns after each data change
endmodule
