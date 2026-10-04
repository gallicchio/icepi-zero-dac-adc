// qpsk_modem_tb.sv -- simulate qpsk_modem.sv with no hardware at all.
//
// The testbench plays the laptop (bytes in on uart_rx, bytes out of uart_tx) and the
// analog world (what the ADC sees), and writes down what the design does inside: every
// DAC code, every frame the transmitter sends, and the two loops' state at every symbol.
// qpsk_modem_check.py drives it.
//
//   python3 qpsk_modem_check.py          all the tests (this file, the model, the channel)
//   (or: iverilog -g2012 -o qpsk_modem_tb.vvp qpsk_modem_tb.sv qpsk_modem.sv ../verilog/uart.sv
//        && vvp -n qpsk_modem_tb.vvp +loop=1 +send=hello.txt +rx=got.txt)
//
// Options, after the .vvp file:
//   +clocks=N      run this many 50 MHz clocks (default 200000 = 4 ms)
//   +loop=1        the ADC sees the DAC through a cable: code = 0.776 x DAC + 27.5,
//                  11 clocks (220 ns) late, as measured in 1.07.  Otherwise:
//   +adc=FILE      ADC codes at 25 MS/s, one per line (decimal); 128 after the end
//   +send=FILE     bytes to send to the design, one per line (hex), from clock +send_t0
//                  (default 2000), one every +send_period clocks (default 0: back to
//                  back, 10 bit times apart); +send_sweep=1 makes it 10 bits + 1 clock, so
//                  that successive bytes land at every phase of the 256-clock frame
//   +bit_clocks=N  the laptop's bit time, in clocks (default 50 = 1,000,000 baud; 434 is
//                  115,200), for sending and for reading what comes back
//   +rx=FILE       write each byte received from uart_tx: "hex clock"
//   +dac=FILE      write every DAC code (one per clock, decimal)
//   +frames=FILE   write each frame the transmitter sends: "hex clock"
//   +sym=FILE      write the receiver's state at each symbol (see `sym` below)
// The summary line at the end counts the bytes sent and received, the bytes that
// arrived in the very clock a frame was loading (the hand-off that could race), the most
// bytes the output FIFO ever held, and how many clocks apart the bytes left.
// Compile with -P qpsk_modem_tb.FIFO_BITS=1 to shrink the design's FIFO to 2 bytes.
`timescale 1ns/1ps
module qpsk_modem_tb;
    parameter integer FIFO_BITS = 5;
    logic clk = 0;
    always #10 clk = ~clk;                          // 50 MHz

    logic [7:0] dac, adc = 128;
    logic       dac_clk, adc_clk, tx;
    logic       rx = 1;
    logic [4:0] led;

    qpsk_modem #(.FIFO_BITS(FIFO_BITS)) dut (.clk(clk), .uart_rx(rx), .uart_tx(tx), .dac_d(dac), .dac_clk(dac_clk),
                                            .adc_d(adc), .adc_clk(adc_clk), .led(led));

    // ---- options ----------------------------------------------------------------
    string adc_file, send_file, rx_file, dac_file, frames_file, sym_file;
    int    clocks = 200000, loop = 0, send_t0 = 2000, send_period = 0, send_sweep = 0, bit_clocks = 50;
    int    f_rx = 0, f_dac = 0, f_frames = 0, f_sym = 0;
    initial begin
        void'($value$plusargs("clocks=%d", clocks));
        void'($value$plusargs("loop=%d", loop));
        void'($value$plusargs("send_t0=%d", send_t0));
        void'($value$plusargs("send_period=%d", send_period));
        void'($value$plusargs("send_sweep=%d", send_sweep));
        void'($value$plusargs("bit_clocks=%d", bit_clocks));
        if ($value$plusargs("rx=%s", rx_file))         f_rx     = $fopen(rx_file, "w");
        if ($value$plusargs("dac=%s", dac_file))       f_dac    = $fopen(dac_file, "w");
        if ($value$plusargs("frames=%s", frames_file)) f_frames = $fopen(frames_file, "w");
        if ($value$plusargs("sym=%s", sym_file))       f_sym    = $fopen(sym_file, "w");
        if (send_period == 0) send_period = 10 * bit_clocks;
        if (send_sweep)       send_period = 10 * bit_clocks + 1;
    end

    // ---- the analog world --------------------------------------------------------
    // Either a cable from the DAC (delayed, scaled, offset, as the real one), or a
    // file of ADC codes.  The AD9280 puts a new code out 25 ns after each rising
    // edge of its clock; the design reads it at the next rising edge.
    localparam DELAY = 11;
    logic [7:0] pipe [0:DELAY];
    initial for (int k = 0; k <= DELAY; k++) pipe[k] = 128;
    always @(posedge clk) begin
        pipe[0] <= dac;
        for (int k = 1; k <= DELAY; k++) pipe[k] <= pipe[k-1];
    end
    logic [7:0] codes [0:(1 << 20) - 1];
    int         n_codes = 0, idx = 0, fd, v;
    initial begin
        if ($value$plusargs("adc=%s", adc_file)) begin
            fd = $fopen(adc_file, "r");
            while ($fscanf(fd, "%d\n", v) == 1) codes[n_codes++] = v;
            $fclose(fd);
        end
    end
    always @(posedge adc_clk) begin
        if (loop) adc <= #25 (776 * pipe[DELAY] + 28000) / 1000;         // round(0.776 x + 27.5)
        else      adc <= #25 (idx < n_codes) ? codes[idx] : 8'd128;
        idx++;
    end

    // ---- the laptop: send bytes from a file, one every send_period clocks -----------------
    logic [7:0] to_send [0:65535];
    int         n_send = 0, n_sent = 0;
    initial begin
        if ($value$plusargs("send=%s", send_file)) begin
            fd = $fopen(send_file, "r");
            while ($fscanf(fd, "%h\n", v) == 1) to_send[n_send++] = v;
            $fclose(fd);
        end
    end
    task automatic send(input logic [7:0] c);
        rx = 0; #(20 * bit_clocks);                     // start bit
        for (int b = 0; b < 8; b++) begin rx = c[b]; #(20 * bit_clocks); end
        rx = 1; #(20 * bit_clocks);                     // stop bit
    endtask
    initial begin
        #(20 * send_t0);
        for (int i = 0; i < n_send; i++) begin
            fork
                send(to_send[i]);
                #(20 * send_period);
            join
            n_sent++;
        end
    end

    // ...and listen: receive each byte, as uart_rx in uart.sv does, at the laptop's rate
    logic [7:0]  c;
    int          n_rx = 0, errors = 0;
    longint      t_start, t_last_start = -1, gap_min = 1 << 30, gap_max = 0;
    always @(negedge tx) begin                          // a start bit has begun
        t_start = $time / 20;
        if (t_last_start >= 0 && n_rx > 0) begin        // how far apart do bytes leave?
            if (t_start - t_last_start < gap_min) gap_min = t_start - t_last_start;
            if (t_start - t_last_start > gap_max) gap_max = t_start - t_last_start;
        end
        t_last_start = t_start;
        #(30 * bit_clocks);                             // to the middle of data bit 0
        for (int b = 0; b < 8; b++) begin c[b] = tx; #(20 * bit_clocks); end
        if (tx !== 1) errors++;                         // no stop bit?
        n_rx++;
        if (f_rx) $fwrite(f_rx, "%02x %0d\n", c, $time / 20);
    end

    // ---- what the design does inside ------------------------------------------------
    int n_sym = 0, n_frames = 0, n_coincide = 0, fifo_max = 0;
    always @(posedge clk) begin
        if (f_dac) $fwrite(f_dac, "%0d\n", dac);
        if (dut.frame_load) begin
            n_frames++;
            if (f_frames) $fwrite(f_frames, "%04x %0d\n", dut.fw_next, $time / 20);
        end
        if (dut.rx_valid && dut.frame_load) n_coincide++;        // the hand-off's tightest case
        if (int'(dut.wr - dut.rd) > fifo_max) fifo_max = int'(dut.wr - dut.rd);
        // ######################################################################
        // ##  KEY LINE: at each symbol, the loops' state: the symbol after the
        // ##  Costas loop, where the timing loop sampled it (mu), the symbol
        // ##  period and carrier frequency it has learnt, both detectors, the
        // ##  decision, and whether the frame sync is locked.
        // ######################################################################
        if (dut.sym_done) begin
            n_sym++;
            if (f_sym) $fwrite(f_sym, "%0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d\n",
                               dut.zr_i, dut.zr_q, dut.mu, dut.tau, dut.period, dut.e_g,
                               dut.phi, dut.freq, dut.e_c, dut.q_now, dut.locked, $time / 20);
        end
    end

    initial begin
        #(20 * clocks);
        $display("%0d clocks: %0d frames sent, %0d symbols received, locked = %0d; bytes: %0d sent, %0d received (%0d framing errors), %0d arrived as a frame loaded; the FIFO held at most %0d; bytes left %0d to %0d clocks apart",
                 clocks, n_frames, n_sym, dut.locked, n_sent, n_rx, errors, n_coincide, fifo_max, gap_min, gap_max);
        $finish;
    end
endmodule
