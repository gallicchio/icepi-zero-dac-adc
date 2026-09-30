// sine_pll.v -- sine.v with the DAC at 100 MS/s instead of 50, clocked by a PLL.
//
// Only three things change from sine.v: the clock comes from pll100.v, the DDS
// waits for the PLL to lock, and the tuning word is for 100 MHz:
//
//     f = TW * 100 MHz / 2^32,   so   TW = round(f / 100 MHz * 2^32)

module sine_pll #(
    parameter [31:0] TW = 32'd42949673      // 1.000 000 MHz at 100 MS/s
) (
    input  wire       clk,                  // 50 MHz
    output reg  [7:0] dac_d,
    output wire       dac_clk
);
    wire clk100, locked;
    pll100 pll (.clk(clk), .clk100(clk100), .locked(locked));

    reg signed [7:0] sine_table [0:255];
    integer i;
    initial
        for (i = 0; i < 256; i = i + 1)
            sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 256) + 0.5));

    reg [31:0] phase = 0;
    always @(posedge clk100)
        if (locked) begin                          // wait until the PLL has settled
            phase <= phase + TW;
            dac_d <= sine_table[phase[31:24]] + 128;
        end

    assign dac_clk = ~clk100;                      // 5 ns after each data change
endmodule
