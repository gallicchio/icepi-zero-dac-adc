# uart_stress_test

Raw-Verilog UART TX stress test for isolating `<DAPLink:Overflow>` failures
(see the "DAPLink:Overflow" sections of `../../openfpga.md` for the full
investigation and results across machines). No LiteX, no CPU, no BIOS --
just a bit-banger driving the same physical pin (`J17`) that
`litex_boards/platforms/colorlight_i5.py`'s `"serial"` resource uses for
`tx`, through the same DAPLink probe, so its reliability can be compared
directly against a full LiteX SoC boot on the same hardware.

## Files

* `uart_stress_test.v` -- parameterized 8N1 UART transmitter (`BAUD_RATE`,
  `BURST_LIMIT` -- 0 for continuous, N for a one-shot N-byte burst --
  `PATTERN` -- 0 monotone `0x55`, 1 cycling printable ASCII). Onboard LED
  (`L2`) lights solid when a bounded burst completes, or blinks slowly
  while a continuous stream runs.
* `colorlight_i9_uart_stress.lpf` -- pin constraints: `clk`->P3 (25MHz
  osc), `tx`->J17, `led`->L2. Board: Colorlight i9 v7.2 (ECP5 LFE5U-45F).
* `build.sh <baud> <burst_limit> <pattern> <out_name> [--load]` -- builds
  via the plain yosys/nextpnr-ecp5/ecppack flow. **Bakes parameter values
  into a per-build copy of the source via `sed`** rather than using yosys
  `chparam` -- an earlier version used `chparam -set BAUD_RATE ...` and it
  silently failed to re-elaborate the `BAUD_DIV` `localparam` derived from
  it, producing a bitstream that transmitted at ~8x the intended baud.
  Don't go back to `chparam` for this without re-verifying that.
* `capture_serial.py <port> <baud> <seconds> <pattern> [expect_bytes]` --
  opens the port (asserting DTR/RTS, since this DAPLink gates output on
  DTR), reads for a fixed window, reports byte count, flags
  `<DAPLink:Overflow>` and its offset, and checks the payload for internal
  consistency (each byte = previous + 1, mod the pattern range) rather
  than absolute alignment -- capture start has no fixed phase relative to
  a free-running continuous stream.
* `capture_raw.py <port> <baud> <seconds>` -- dumps raw bytes to stdout,
  for inspecting a real LiteX BIOS boot banner instead of the synthetic
  pattern above.

## Reliability finding: use 9600 baud, not 115200

**At 115200 baud this design overflows `<DAPLink:Overflow>` roughly 90% of
the time** (9 of 10 attempts, across two different USB ports on one
desktop host) -- despite being the simplest possible design (no CPU, no
LiteX, no SDRAM). **At 9600 baud, 15 of 16 attempts came through clean**
(~94%), a ~15x reduction in failure rate. This is a real, large
improvement and the recommended baud for teaching/demoing this example on
this board/probe/host combination -- but **it is a strong mitigation, not
a guarantee**: the one 9600-baud failure that did occur landed at almost
the identical byte offset (494) as the typical 115200 failures, despite
taking roughly 12x longer in wall-clock time to reach that point. That's a
loose thread against the "pure real-time USB-draining" theory (which
would predict the failure point tracking wall-clock time, not byte count,
as baud drops) -- worth investigating further before assuming the
mechanism is fully understood. Don't promise a class this will never
fail; promise it will rarely fail instead of usually failing.

## Typical usage

```bash
./build.sh 9600 0 1 cont_9600             # continuous ASCII-cycling stream, recommended baud
openFPGALoader -b colorlight-i9 cont_9600.bit
python3 capture_serial.py /dev/ttyACM0 9600 15 1

# 115200 is the tutorial's nominal default but overflows far more often (see above):
./build.sh 115200 0 1 cont_115200
openFPGALoader -b colorlight-i9 cont_115200.bit
python3 capture_serial.py /dev/ttyACM0 115200 8 1
```

For the actual LiteX regression case, build the stock target separately
and use `capture_raw.py` to watch the boot banner:

```bash
python3 -m litex_boards.targets.colorlight_i5 --board=i9 --revision=7.2 --build
openFPGALoader -b colorlight-i9 build/colorlight_i5/gateware/colorlight_i5.bit
python3 capture_raw.py /dev/ttyACM0 115200 12 > boot.log
```

## Hazard, confirmed on two separate host machines

**Never hold the serial (CDC) port open while a JTAG operation
(`--detect`, `--load`, `-f`, or a plain flash) runs on the same DAPLink
probe, and vice versa.** Doing so (or even just having a JTAG operation
get interrupted, e.g. by a shell timeout, while a capture script nearby
still has the port open) has reliably corrupted the probe's HID/JTAG
interface: `openFPGALoader --detect` starts failing with `JTAG init
failed`, and the corresponding `/dev/hidraw*` node disappears entirely
while `lsusb` still shows the same device at the same bus/path -- no full
USB re-enumeration happens. The only fix found so far, on either machine,
is a **physical USB replug**. Fully close one tool before opening the
other, every time.
