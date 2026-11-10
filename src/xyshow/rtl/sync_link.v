// The two-board synchronisation through the signal: the X board (role 0) starts every frame with a burst on
// its DAC, a gap at code 0 and then its state as bits (SPB = 4 DAC samples a bit, low = code 0, high = code HI),
// and the Y board (role 1), whose ADC sees that DAC through a tee, decodes it, loads the same state, trims
// its sample rate from the burst-to-burst interval, and draws the same frame.  The drawings never go below
// code 13 (the scene is scaled to +/-0.9), so the gap is unmistakable.
//
// Payload (W = 920 bits), most significant bit first: preamble 4'b1010, the repeat interval rep_f[15:0] (ticks; 0 = one
// frame a burst), frame[15:0], mode[3:0], finale[4:0],
// dwell[15:0], the X board's free-running tick count [31:0], the rings' state (every[11:0], wp[10:0], every2, wp2, 1'b0),
// the twins' step counters (stepc[15:0], stepc2[15:0]), the 32 phases' top 16 bits (phase 0 lowest), x, y, z
// (38 each, the Lorenz twin), x, y, z (38 each, the Chua twin), checksum[7:0] = the sum of the 912 bits before it as 114
// bytes, mod 256.  Both ends keep the sum as the bytes go by (sync_tx adds each byte as it starts to send it
// and sends the sum last; sync_rx adds each byte as its last bit arrives), so no end-of-burst adder tree: the Y board's
// clock did not close with one.

module sync_tx #(parameter HI = 8'd40, GAP = 16, W = 920, SPB = 4) (
    input  wire         clk,
    input  wire         tick,           // the DAC's sub-step tick (25 MHz)
    input  wire         start,          // one clock: send a burst
    input  wire [W-1:0] payload,        // its low byte is replaced by the checksum
    output reg          active = 1'b0,
    output reg  [7:0]   level = 8'd0,
    output reg          done = 1'b0
);
    reg [W-1:0] sh = 0; reg [12:0] n = 0; reg [1:0] sc = 0; reg [7:0] acc = 0; reg [9:0] b = 0;
    always @(posedge clk) begin
        done <= 0;
        if (start && !active) begin active <= 1; sh <= payload; n <= 0; sc <= 0; level <= 8'd0; acc <= 0; b <= 0; end
        else if (active && tick) begin
            if (n < GAP) begin level <= 8'd0; n <= n + 1; end
            else if (n < GAP + SPB * W) begin
                if (sc == 0) begin                                            // a bit's first sample
                    if (b[2:0] == 3'd0 && b != W - 8) acc <= acc + sh[W-1 -: 8];  // a byte starts: into the sum
                    if (b == W - 8) begin sh[W-1 -: 8] <= acc; level <= acc[7] ? HI : 8'd0; end   // the last byte is the sum
                    else level <= sh[W-1] ? HI : 8'd0;
                end
                if (sc == SPB - 1) begin sh <= {sh[W-2:0], 1'b0}; b <= b + 1; sc <= 0; end else sc <= sc + 1;
                n <= n + 1;
            end else begin active <= 0; done <= 1; level <= 8'd0; end
        end
    end
endmodule

// The receiver: the gap (at least GAP - 4 samples below thr_gap), then the first sample above it is bit 0's start (the
// payload starts with a 1).  Bit k is decided SPB k + SAMPLE_AT samples after that: well inside the bit whatever the
// sampling phase, after the module's edge (about 20 ns) and its ringing (about 100 ns) have mostly settled.  The data
// threshold is half way between the gap's level and bit 0's.
module sync_rx #(parameter GAP = 16, W = 920, SPB = 4, SAMPLE_AT = 2) (
    input  wire         clk,
    input  wire         sample,         // one clock: `adc` is a new 25 MS/s sample
    input  wire [7:0]   adc,
    input  wire [7:0]   thr_gap,        // below this is the gap
    output reg  [W-1:0] payload = 0,
    output reg          valid = 1'b0,   // one clock: payload is fresh and its checksum agrees
    output reg          in_burst = 1'b0,
    output reg  [7:0]   lo = 8'd0,          // the levels seen (for the host)
    output reg  [7:0]   hi = 8'd0,
    output reg  [31:0]  interval = 0,   // clocks between the last two bursts
    output reg  [15:0]  bad = 16'd0,
    output reg  [15:0]  good = 16'd0
);
    reg [4:0] gapn = 0; reg [1:0] st = 0; reg [9:0] nb = 0; reg [1:0] sc = 0; reg first = 0; reg [7:0] thr = 0;
    reg [W-1:0] sh = 0; reg [31:0] clocks = 0; reg [7:0] acc = 0; wire bitv = (adc > thr);
    always @(posedge clk) begin
        valid <= 0; clocks <= clocks + 1;
        if (sample) case (st)
            0: begin                                              // looking for the gap, then the first high sample (bit 0 = 1)
                if (adc < thr_gap) begin if (gapn != 5'd31) gapn <= gapn + 1; lo <= adc; end else gapn <= 0;
                if (gapn >= GAP - 4 && adc >= thr_gap) begin
                    st <= 1; nb <= 0; sc <= 1; first <= 1; sh <= {{(W-1){1'b0}}, 1'b1}; in_burst <= 1; gapn <= 0; acc <= 0;
                    interval <= clocks; clocks <= 0;
                end
            end
            1: begin                                              // sc counts the samples of the current bit from its start
                if (sc == SAMPLE_AT) begin
                    if (first) begin first <= 0; hi <= adc; thr <= ({1'b0, adc} + {1'b0, lo}) >> 1; end   // bit 0, a 1: the high level
                    else if (nb != W - 1) begin
                        sh <= {sh[W-2:0], bitv}; nb <= nb + 1;
                        if (nb[2:0] == 3'd6 && nb != W - 2) acc <= acc + {sh[6:0], bitv};     // a byte's last bit: into the sum (not the checksum's)
                    end
                end
                if (nb == W - 1 && sc == SPB - 1) st <= 2;
                sc <= (sc == SPB - 1) ? 2'd0 : sc + 1;
            end
            2: begin
                in_burst <= 0; st <= 0;
                if (acc == sh[7:0] && sh[W-1:W-4] == 4'b1010) begin payload <= sh; valid <= 1; good <= good + 1; end
                else bad <= bad + 1;
            end
            default: st <= 0;
        endcase
    end
endmodule
