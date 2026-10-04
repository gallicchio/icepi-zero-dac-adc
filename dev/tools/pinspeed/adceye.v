// ADC "eye" experiment.  One 125 MHz PLL domain:
//   DAC   62.5 MS/s, DDS sine (1024-entry table), data changes 8 ns before each rising dac_clk
//   ADC   clocked by a second PLL output (31.25 or 25 MHz) with a static phase shift
//   pins  adc_d sampled on EVERY 125 MHz edge (8 ns apart) into 32 kB of block RAM
// Any byte received over the UART (1 Mbaud) starts a capture; the 32768 raw bytes come back.
module adceye #(parameter [31:0] TW = 32'd0, parameter integer NRAW = 32768) (
    input wire clk, output reg [7:0] dac_d = 0, output reg dac_clk = 0,
    input wire [7:0] adc_d, output wire adc_clk,
    input wire uart_rx, output wire uart_tx, output wire [4:0] led);
    wire c125, cadc, locked;
    pll2 pll (.clkin(clk), .c125(c125), .cadc(cadc), .locked(locked));
    assign adc_clk = cadc;
    // DAC at 62.5 MS/s
    reg signed [7:0] sine_table [0:1023];
    integer i;
    initial for (i = 0; i < 1024; i = i + 1)
        sine_table[i] = $rtoi($floor(127.0 * $sin(6.283185307179586 * i / 1024) + 0.5));
    reg [31:0] phase = 0;
    reg [7:0] next = 128;
    always @(posedge c125) if (locked) begin
        dac_clk <= ~dac_clk;
        if (dac_clk) begin                     // falling edge of dac_clk: new code
            phase <= phase + TW;
            dac_d <= next;
        end else
            next <= sine_table[phase[31:22]] + 128;
    end
    // raw capture of the ADC pins on every 125 MHz edge
    reg [7:0] pin1 = 0, pin2 = 0;
    always @(posedge c125) begin pin1 <= adc_d; pin2 <= pin1; end
    reg [7:0] mem [0:NRAW-1];
    reg [15:0] wa = 0, ra = 0;
    reg [7:0] rd = 0, rd2 = 0;
    reg [1:0] mode = 0, st = 0;              // mode: 0 idle, 1 capturing, 2 sending
    wire [7:0] rx; wire rxv, busy; reg start = 0;
    uart_rx #(.CLKS_PER_BIT(125)) urx (.clk(c125), .rx(uart_rx), .data(rx), .valid(rxv));
    uart_tx #(.CLKS_PER_BIT(125)) utx (.clk(c125), .data(rd2), .start(start), .busy(busy), .tx(uart_tx));
    always @(posedge c125) begin
        start <= 0;
        rd  <= mem[ra];
        rd2 <= rd;
        if (mode == 1) mem[wa] <= pin2;
        case (mode)
            0: if (rxv) begin mode <= 1; wa <= 0; end
            1: begin
                   wa <= wa + 1;
                   if (wa == NRAW - 1) begin mode <= 2; ra <= 0; st <= 0; end
               end
            2: case (st)
                   0: st <= 3;                       // two clocks of read latency
                   3: st <= 1;
                   1: if (!busy && !start) begin start <= 1; st <= 2; end
                   2: if (!busy && !start) begin
                          if (ra == NRAW - 1) mode <= 0;
                          else begin ra <= ra + 1; st <= 0; end
                      end
               endcase
        endcase
    end
    assign led = {mode, 2'b0, locked};
endmodule
