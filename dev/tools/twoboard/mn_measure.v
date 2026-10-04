// measure the SNR that modem_noise.v delivers: a steady MARK tone plus its noise on
// the DAC (uart_rx tied high), and the tutorial's capture.v recording the ADC.
module mn_measure #(parameter integer NOISE = 0, parameter integer AMP = 100, parameter integer LOGWIN = 4) (
    input wire clk, output wire [7:0] dac_d, output wire dac_clk,
    input wire [7:0] adc_d, output wire adc_clk, input wire uart_rx, output wire uart_tx, output wire [4:0] led);
    modem_noise #(.NOISE(NOISE), .AMP(AMP), .LOGWIN(LOGWIN)) u_tx (.clk(clk), .uart_rx(1'b1), .uart_tx(), .dac_d(dac_d), .dac_clk(dac_clk),
                                       .adc_d(adc_d), .adc_clk(), .led());
    capture u_cap (.clk(clk), .adc_d(adc_d), .adc_clk(adc_clk), .uart_rx(uart_rx), .uart_tx(uart_tx), .led(led));
endmodule
