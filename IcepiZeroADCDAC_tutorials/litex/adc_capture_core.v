// adc_capture_core.v -- record 16384 ADC samples into a buffer the CPU can read.
//
// Tutorial 3's capture.v without the serial port: a `start` pulse records
// 16384 samples (keeping 1 in 2^decimation), optionally waiting first for the
// signal to cross `trig_level` going upward.  The buffer is 4096 32-bit words,
// four samples per word, first sample in the lowest byte -- so on the
// (little-endian) CPU it simply reads as an array of 16384 bytes.

module adc_capture_core (
    input  wire        clk,
    input  wire [7:0]  sample,
    input  wire        sample_valid,
    // control, from the CPU's registers
    input  wire        start,          // pulse: begin a new capture
    input  wire [3:0]  decimation,     // keep 1 sample in 2^decimation
    input  wire        trig_enable,    // wait for an upward crossing first
    input  wire [7:0]  trig_level,
    output wire        busy,
    output reg         done = 0,       // a complete capture is in the buffer
    // the CPU's read port into the buffer
    input  wire [11:0] rd_addr,
    output reg  [31:0] rd_data = 0
);
    reg [31:0] mem [0:4095];
    always @(posedge clk)
        rd_data <= mem[rd_addr];

    localparam IDLE = 0, ARMED = 1, RECORD = 2;
    reg [1:0]  state = IDLE;
    reg [15:0] skip = 0;
    reg [7:0]  last = 0;               // previous kept sample, for the trigger
    reg [13:0] n = 0;                  // samples recorded so far
    reg [23:0] pack = 0;               // the first three samples of a word

    assign busy = (state != IDLE);

    // "keep" is high for the samples that survive decimation
    wire keep = sample_valid && (skip == 0);
    always @(posedge clk)
        if (start || state == IDLE)
            skip <= 0;
        else if (sample_valid)
            skip <= (skip == 0) ? (16'd1 << decimation) - 1 : skip - 1;

    always @(posedge clk) begin
        if (start) begin
            done  <= 0;
            n     <= 0;
            last  <= 8'hff;            // forget the old signal: no crossing yet
            state <= trig_enable ? ARMED : RECORD;
        end else case (state)
            ARMED:
                if (keep) begin
                    last <= sample;
                    if (last < trig_level && sample >= trig_level)
                        state <= RECORD;
                end
            RECORD:
                if (keep) begin
                    // shift the sample in; every 4th completes a 32-bit word
                    if (n[1:0] == 3)
                        mem[n[13:2]] <= {sample, pack};
                    pack <= {sample, pack[23:8]};
                    n <= n + 1;
                    if (n == 16383) begin
                        state <= IDLE;
                        done  <= 1;
                    end
                end
        endcase
    end
endmodule
