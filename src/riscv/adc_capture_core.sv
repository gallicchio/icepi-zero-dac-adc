// adc_capture_core.sv -- record 16384 ADC samples into a buffer the CPU can read.
//
// capture.sv without the serial port: a `start` pulse records 16384 samples
// (keeping 1 in 2^decimation), optionally waiting first for the signal to
// cross `trig_level` going upward.  The buffer is 4096 32-bit words, four
// samples per word, first sample in the lowest byte -- so on the
// (little-endian) CPU it simply reads as an array of 16384 bytes.

module adc_capture_core (
    input  logic        clk,
    input  logic [7:0]  sample,
    input  logic        sample_valid,
    // control, from the CPU's registers
    input  logic        start,          // pulse: begin a new capture
    input  logic [3:0]  decimation,     // keep 1 sample in 2^decimation
    input  logic        trig_enable,    // wait for an upward crossing first
    input  logic [7:0]  trig_level,
    output logic        busy,
    output logic        done = 0,       // a complete capture is in the buffer
    // the CPU's read port into the buffer
    input  logic [11:0] rd_addr,
    output logic [31:0] rd_data = 0
);
    logic [31:0] mem [0:4095];
    // ##########################################################################
    // ##  KEY LINE: the CPU's side of the buffer.  Whatever address the CPU
    // ##  reads, the word stored there comes back one clock later.
    // ##########################################################################
    always_ff @(posedge clk)
        rd_data <= mem[rd_addr];

    typedef enum logic [1:0] {IDLE, ARMED, RECORD} state_t;
    state_t      state = IDLE;
    logic [15:0] skip  = 0;
    logic [7:0]  last  = 0;             // previous kept sample, for the trigger
    logic [13:0] n     = 0;             // samples recorded so far
    logic [23:0] pack  = 0;             // the first three samples of a word

    assign busy = (state != IDLE);

    // "keep" is high for the samples that survive decimation
    logic keep;
    assign keep = sample_valid && (skip == 0);
    always_ff @(posedge clk)
        if (start || state == IDLE)
            skip <= 0;
        else if (sample_valid)
            skip <= (skip == 0) ? (16'd1 << decimation) - 1 : skip - 1;

    always_ff @(posedge clk) begin
        if (start) begin
            done  <= 0;
            n     <= 0;
            last  <= 8'hff;             // forget the old signal: no crossing yet
            state <= trig_enable ? ARMED : RECORD;
        end else case (state)
            ARMED:
                if (keep) begin
                    last <= sample;
                    // ##########################################################
                    // ##  KEY LINE: the trigger.  Below the level last time,
                    // ##  at or above it now: start recording.
                    // ##########################################################
                    if (last < trig_level && sample >= trig_level)
                        state <= RECORD;
                end
            RECORD:
                if (keep) begin
                    // ##########################################################
                    // ##  KEY LINE: shift each sample in; every 4th completes
                    // ##  a 32-bit word, which goes into the buffer.
                    // ##########################################################
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
