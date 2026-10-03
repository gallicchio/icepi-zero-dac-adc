# iCEBreaker: a much smaller open-source FPGA board

This is the little sibling to [README.md](README.md). Same open-source toolchain philosophy (Yosys, nextpnr, no vendor tools), completely different scale of chip: the iCEBreaker carries a Lattice **iCE40UP5K** (5,280 4-input LUTs, 128 KB of on-chip SPRAM, no SDRAM pins on the board at all) instead of an ECP5. It's not a Linux candidate -- it's the board for "how small can the whole open FPGA + RISC-V stack actually get."

The board plugged in right now identifies itself over USB as `1BitSquared iCEBreaker V1.0e` (confirmed via `udevadm info` on `/dev/ttyUSB0`), serial `ibP54Olo`.

## Hardware: which iCEBreaker is this, and which one does Mouser sell today?

Mouser carries this board under **two different manufacturer listings**, and they are not the same revision:

| Mouser listing | Manufacturer of record | Revision | Stock (checked 2026-08-27) |
|---|---|---|---|
| `CS-ICEBREAKER-01` | "Crowd Supply" | v1.0-series (the original campaign board) | **Non-Stocked, Call for Quote** -- not actually orderable |
| `ICEBREAKER-V1_1` | "1BitSquared" | v1.1a (current) | In stock, $79.95 |

So if you tried to reorder "the Crowd Supply one" off Mouser today, that exact listing isn't buyable -- you'd get the 1BitSquared `v1.1a` instead. The board already on your desk is `v1.0e`, one step before that split: an earlier point revision than either of the two Mouser SKUs above, most likely from the original Crowd Supply run before 1BitSquared took over direct sales.

**What actually changed from v1.0 to v1.1** (per 1BitSquared's own product page changelog):
* Micro USB → USB-C connector
* The breakaway "ears" (extra buttons/LEDs section) are now populated by default, with connectors included for even more ear boards
* RGB LED mounted by default
* **64 Mbit QSPI PSRAM mounted by default** -- an actual external RAM chip, new to v1.1
* Dedicated CRESET button added
* PMOD I/O signals length-matched (matters for fast/video signaling, not for anything in this doc)

**How different would this whole tutorial be on v1.1a?** Barely at all. The pins that matter here -- `clk12` (pin 35), the onboard button (pin 10), and the two onboard LEDs (pins 11/37) -- are unchanged across every revision; the Verilog, PCF, and `litex_boards` target below all work unmodified on either board -- same `iCE40UP5K-SG48` die, same `sys_clk_freq`/timing story, no revision-specific target file exists or is needed.

### Since you have v1.1 boards on order for teaching: what actually differs

Everything built in this document should run as-is on v1.1a. Two things are worth knowing before you put v1.1 boards in front of students, one likely upside and one real gap on this v1.0e unit:

* **Volatile SRAM loading may just work on v1.1, where it doesn't here.** The section below shows `iceprog -S` failing to bring `CDONE` high on this `v1.0e` board -- bitstream transfers fully, but the FPGA never finishes configuring, so every load in this doc went through flash instead. v1.1 added a *dedicated CRESET button*, which strongly suggests 1BitSquared revisited the CRESET/CDONE handling on that revision. If it works on v1.1, that changes the recommended classroom workflow: `--load` (SRAM, instant, zero flash wear, always boots blank on power-cycle -- no stale-bitstream confusion between students sharing boards) becomes the right default instead of `--flash`. **Worth testing on the first v1.1 board that arrives** before deciding which workflow to teach.
* **v1.1's onboard PSRAM (64 Mbit / 8 MB QSPI) is real extra memory v1.0e structurally does not have.** The stock `icebreaker` LiteX target (used below) doesn't wire it up -- it only uses the UP5K's built-in 128 KB SPRAM -- so nothing here needs it. But it's a genuine ceiling difference: a v1.0e board can never exceed ~128 KB total RAM no matter what you build, while v1.1 boards have a path to ~8 MB if a student project ever needs more heap or a framebuffer. Not exercised in this document, but worth knowing it's there if a class project runs into the 128 KB wall.

Cosmetic, not functional, for this doc: USB-C vs. micro-USB (bring the right cables for a classroom), and the RGB LED / populated breakaway ears being present out of the box on v1.1 rather than needing to be intact/unbroken (same as this v1.0e board, which still has its ears attached).

## Toolchain: what's different from the ECP5 flow, and what had to be installed

Same family of tools as the ECP5 half of this project, different backend:

```
Yosys (same for every board) -> nextpnr-ice40 (not nextpnr-ecp5) -> icepack -> iceprog / openFPGALoader
```

There's no Project Trellis equivalent to install for iCE40 -- `nextpnr-ice40` ships with a built-in chip database, so there's no separate "database" package the way ECP5 needs Trellis's `.bit` timing/routing data. Constraint files are `.pcf` (Physical Constraints File, `set_io <port> <pin>`), simpler than the ECP5 `.lpf` format and not comparable to Xilinx `.xdc`.

**Checked what was already on this machine before installing anything:**

* `yosys`, `nextpnr-ice40`, `nextpnr-ecp5`, `icepack`, `iceprog`, `icetime`, `icebox_explain`, `openFPGALoader` -- all already present in `oss-cad-suite` (the same suite already used for the ECP5 boards). **Nothing to install here.**
* `riscv64-unknown-elf-gcc` -- already at `/usr/bin/riscv64-unknown-elf-gcc` from prior LiteX/VexRiscv work.
* `litex`, `litex-boards` -- already installed, and `litex_boards/platforms/icebreaker.py` + `litex_boards/targets/icebreaker.py` already exist as real, maintained board files (more on this below).
* udev rules for `openFPGALoader` (`99-openfpgaloader.rules`) -- already installed to `/etc/udev/rules.d/`, and `jason` is already in the `plugdev`/`dialout` groups, so the board is accessible with no `sudo`.
* `openFPGALoader --scan-usb` confirms the board is seen: `0x0403:0x6010 FTDI2232 1BitSquared ibP54Olo iCEBreaker V1.0e`.

The only thing genuinely absent was `apio` (a higher-level wrapper some iCEBreaker tutorials use) -- not installed, because it would just be a thinner shell around the same `yosys`/`nextpnr-ice40`/`icepack` already in hand, and this project has consistently called those directly for the ECP5 boards too.

## A simple design: one button, two LEDs

The base board (independent of whether the breakaway "ears" with the extra 3 buttons/5 LEDs are still attached) always has: a 12 MHz oscillator (`clk12`, pin 35), one user button (pin 10, idle-high/active-low), and two LEDs -- red (pin 11) and green (pin 37), both active-low.

`button_led.v` (`/home/jason/openfpga/icebreaker-raw-verilog/button_led/button_led.v`):

```verilog
module button_led (
    input  wire clk12,    // 12 MHz onboard oscillator, pin 35
    input  wire btn_n,    // user button (SW1), pin 10 -- idle-high, actuated-low
    output wire led_r_n,  // onboard red LED (D11), pin 11 -- active-low
    output wire led_g_n   // onboard green LED (D37), pin 37 -- active-low
);
    // 2-stage synchronizer: the button is async to clk12.
    reg btn_s0 = 1'b1, btn_s1 = 1'b1;
    always @(posedge clk12) begin
        btn_s0 <= btn_n;
        btn_s1 <= btn_s0;
    end
    wire pressed = ~btn_s1;

    // Edge-detect so each press toggles state once, not a raw passthrough.
    reg pressed_d = 1'b0;
    always @(posedge clk12) pressed_d <= pressed;
    wire press_edge = pressed & ~pressed_d;

    reg red_state = 1'b0;
    always @(posedge clk12)
        if (press_edge) red_state <= ~red_state;

    // Free-running heartbeat, independent of the button -- proves the design
    // is alive even before you touch anything. ~1.4 Hz at 12 MHz.
    reg [22:0] heartbeat_ctr = 23'h0;
    always @(posedge clk12) heartbeat_ctr <= heartbeat_ctr + 1'b1;

    assign led_r_n = ~red_state;
    assign led_g_n = ~heartbeat_ctr[22];
endmodule
```

`icebreaker.pcf`:

```
set_io clk12 35
set_frequency clk12 12
set_io -pullup yes btn_n 10
set_io led_r_n 11
set_io led_g_n 37
```

Build (iCE40UP5K in the SG48 package, which is what's on this board):

```
yosys -p "synth_ice40 -top button_led -json button_led.json" button_led.v
nextpnr-ice40 --up5k --package sg48 --pcf icebreaker.pcf --json button_led.json --asc button_led.asc
icepack button_led.asc button_led.bin
```

Result: 27 LUT4s, 26 DFFs -- **0.5% of the chip's 5,280 LUTs.** Timing closes at 81.5 MHz against a 12 MHz requirement, so there's no speed concern at all at this size.

### Programming: SRAM (volatile) vs. flash

Tried the volatile-only path first, since that's what you asked for: `iceprog -S button_led.bin` drives the FPGA's configuration SPI pins directly, bypassing the flash chip entirely, so the design disappears on power-cycle. It transferred the full bitstream correctly but **`CDONE` never went high** -- on this specific `V1.0e` board, direct SRAM programming isn't completing (tried both default and slow-SPI `-s`, same result both times). This is the same board where the iCEstick has a documented SRAM-programming caveat for a similar reason (a shared SPI line that isn't broken out the way later revisions expect); it's plausible `v1.0e` has an equivalent wiring quirk that got fixed by `v1.1`.

Fell back to `openFPGALoader -b ice40_generic button_led.bin`, which writes through the board's Winbond `W25Q128` configuration flash (identified via JEDEC ID `0xEF4018`) instead. That completed normally -- erase, write, and `CDONE` confirmed high afterward. **So this landed in flash, not SRAM**, despite the preference for volatile -- it's the one thing in this doc that didn't go as asked, and it's a hardware limitation of this particular board rather than a tool choice. Practically: SPI NOR flash like this is rated for on the order of 100,000 erase cycles and is exactly what iCEBreaker's flash is for, so reflashing it during development isn't a real cost -- it's just not the "volatile only" behavior you asked for.

**Stop here and check the board:** the green LED should be blinking at roughly 1.4 Hz on its own, and each press of the button should toggle the red LED between on and off.

## How far can the UP5K go?

5,280 LUTs is about 1/8th the size of the smallest ECP5 this project uses (the Colorlight i9's 45F, ~44K LUTs) -- and there's no SDRAM pin on the board at all, on any revision. That rules out full Linux outright: no MMU-capable open soft core fits usefully in this LUT budget, and 128 KB of total on-chip RAM (all this board has) is far below what even the aggressively-trimmed Colorlight i9 Linux build in the main doc needed with 8 MB. But well short of Linux, there's real headroom:

**A LiteX + VexRiscv SoC fits, and it already exists -- built and flashed just now.** `litex_boards/targets/icebreaker.py` is a real, maintained target (not something built from scratch): it drops a VexRiscv onto the UP5K, using the chip's 128 KB `SPRAM` split 64/64 between `sram` and `main_ram`, with the BIOS living in the onboard SPI flash. No SDRAM controller anywhere in it, because there's nothing to control.

Two things had to change from the defaults to actually fit and close timing on this chip -- both real, board-specific findings, not guesses:

* **Default `--cpu-type=vexriscv` (the `standard` variant) does not fit**: first attempt came back `ICESTORM_LC: 5591/5280 105%` and nextpnr refused to place it. `--cpu-variant=lite` (drops the D-cache) was needed to get under budget.
* **Even then, the default `--sys-clk-freq` of 24 MHz doesn't close timing**: nextpnr reported `Max frequency for clock 'crg_clkout': 20.83 MHz (FAIL at 24.00 MHz)`. Dropping to `--sys-clk-freq 16e6` (16 MHz is the iCE40 PLL's minimum output -- 12 MHz straight passthrough isn't allowed) passed cleanly at 20.94-22.31 MHz achieved Fmax.

The build that actually worked, flashed and running right now (`ICESTORM_LC: 4648/5280`, 88% utilization):

```
python3 -m litex_boards.targets.icebreaker --cpu-variant=lite --sys-clk-freq 16e6 --build --flash
```

`--flash`, not `--load`, for the same reason as the plain Verilog demo above: `litex/build/lattice/programmer.py`'s `IceStormProgrammer.load_bitstream()` calls `iceprog -S` under the hood, which is the exact SRAM path that doesn't complete on this `v1.0e` board. `--flash` calls `iceprog -o <addr> <file>` instead (normal flash write, same path `openFPGALoader` used successfully earlier), and that went through cleanly -- BIOS at `0x40000`, gateware at `0x0`, `CDONE` confirmed high after each.

**Can it boot to the point of turning LEDs on/off from the BIOS? Yes** -- and not hypothetically. The target's `BaseSoC` sets `with_led_chaser = True` by default, which instantiates a `LedChaser` CSR peripheral, and LiteX's stock BIOS (`litex/soc/software/bios/cmds/cmd_bios.c:168-189`) already has a `leds` command gated on exactly that CSR existing:

```c
#ifdef CSR_LEDS_BASE
static void leds_handler(int nb_params, char **params) {
    ...
    leds_out_write(value);
}
define_command(leds, leds_handler, "Set LEDs value", SYSTEM_CMDS);
#endif
```

So after booting, `leds 1` / `leds 0` at the BIOS prompt directly drives the LEDs -- no custom firmware needed, it's already wired up in the LiteX BIOS that ships with this target.

**One behavior change from the plain-Verilog demo above, worth knowing before you go looking for it**: `BaseSoC`'s clock/reset generator wires the *same* onboard button (pin 10, `user_btn_n`) to the SoC's PLL/CPU reset (`pll.reset.eq(~rst_n)`), not to any user-visible GPIO. On this board, that button now reboots the BIOS when pressed -- it's not free for your own logic unless you edit the CRG or use one of the breakaway-ears buttons instead.

**Check it now:** connect a serial terminal to the FTDI's second channel at 115200 baud --

```
litex_term /dev/ttyUSB1
```

-- then press the button once (BIOS reset) to see the LiteX banner and boot log. At the `litex>` prompt, try `leds 1`, `leds 2`, `leds 0` and confirm the LEDs respond. `Ctrl+C` to exit `litex_term`.

**Confirmed working (2026-08-27):** talked to the console directly over `/dev/ttyUSB1` at 115200 baud (`stty -F /dev/ttyUSB1 115200 raw -echo`) without even needing a reset -- the BIOS was already sitting at its prompt:

```
litex>  leds 1
Setting LEDs to 0x1
litex>  leds 7
Setting LEDs to 0x7
litex> 
```

Real LiteX BIOS, real `leds` command, accepted and acknowledged. One environment gotcha hit along the way, worth knowing about if the console ever goes silent: after `iceprog`/`openFPGALoader` grab the FTDI chip in raw MPSSE mode to program it, both `/dev/ttyUSB0` and `/dev/ttyUSB1` can end up unbound from the kernel's `ftdi_sio` driver and disappear -- `lsusb` still sees the device, but the tty nodes are gone. Fixing that needs root (`/sys/bus/usb/drivers/ftdi_sio/bind` is `root`-only) or, far simpler, just unplug and replug the USB cable -- that's what actually resolved it here.

## Bare-metal C: a real computation, driven by the breakaway-ears buttons and LEDs

Two ways to run your own C on this LiteX SoC: bake it into the gateware's `rom` (replacing the BIOS -- a full rebuild+reflash for every code change), or compile it separately and load it over the UART into `main_ram` while the flashed BIOS is still running (`serialboot`, no reflashing at all). The second is the standard LiteX workflow -- it's what `litex_bare_metal_demo` (a console script that ships with `litex` itself) scaffolds by default, and it's dramatically faster to iterate on since nothing touches flash.

**One prerequisite first: give the CPU a button to read.** The stock `icebreaker.py` target wires the *only* base-board button to the SoC's reset line (`pll.reset.eq(~rst_n)`, from the CRG section above) -- there's no software-visible button register at all. Since the breakaway-ears are still attached, this is exactly the moment to use them: a five-line subclass adds the three pmod buttons as a plain `GPIOIn` CSR, the same pattern that already gives the LEDs their `leds` BIOS command.

`target/icebreaker_buttons.py`:

```python
from litex.soc.cores.gpio import GPIOIn
from litex.soc.integration.builder import Builder
from litex_boards.platforms import icebreaker
from litex_boards.targets.icebreaker import BaseSoC

class ButtonSoC(BaseSoC):
    def __init__(self, **kwargs):
        BaseSoC.__init__(self, **kwargs)
        self.buttons = GPIOIn(pads=self.platform.request_all("user_btn"))

# ...main() below is icebreaker.py's own main(), with ButtonSoC swapped in for BaseSoC.
```

Built and flashed with the same settings already proven above (`--cpu-variant=lite --sys-clk-freq 16e6`): fits at 4637/5280 LCs (87%), timing passes at 20-22 MHz achieved Fmax. One line of Python, and the stock BIOS immediately grows a free `buttons` command -- confirmed on real hardware, unpressed:

```
litex> buttons
Buttons value: 0x0
```

**The demo itself: search for prime numbers, controlled by the buttons, displayed on the LEDs.** This is deliberately not just GPIO wiring -- trial division needs a real multiply (`d*d`) and a real modulo (`n % d`) on every candidate, so it's exercising the CPU's ALU, not just a shift register. (Worth knowing: the `lite` VexRiscv variant used throughout this doc only drops the D-cache -- it keeps the full RV32IM hardware multiply/divide, per `GCC_FLAGS["lite"] = "-march=rv32i2p0_m"` in `litex/soc/cores/cpu/vexriscv/core.py`. So `d*d` and `n % d` below compile to real `mul`/`remu` instructions, not a software-emulated multiply.)

Added to the `litex_bare_metal_demo`-scaffolded `demo/main.c` (one static function plus one dispatch line -- the rest of that file is the unmodified stock scaffold: `help`, `reboot`, `led`, `donut`, `helloc`):

```c
#if defined(CSR_BUTTONS_BASE) && defined(CSR_LEDS_BASE)
static int is_prime(unsigned int n)
{
	if (n < 2)
		return 0;
	if (n % 2 == 0)
		return n == 2;
	for (unsigned int d = 3; d * d <= n; d += 2)
		if (n % d == 0)
			return 0;
	return 1;
}

static void primes_cmd(void)
{
	unsigned int n = 2, found = 0;

	printf("Hold button 0 to pause, button 1 to reset back to n=2. Ctrl-C the terminal to stop.\n");
	while (1) {
		uint32_t btn = buttons_in_read();
		if (btn & 0x2) { n = 2; found = 0; leds_out_write(0); busy_wait(200); continue; }
		if (btn & 0x1) { busy_wait(20); continue; }
		if (is_prime(n)) {
			found++;
			leds_out_write(n & 0x1f);  // low 5 bits of the prime, on the 5 LEDs
			printf("prime #%u: %u  (0x%02x on LEDs)\n", found, n, n & 0x1f);
			busy_wait(30);
		}
		n++;
	}
}
#endif
```

Button 1 held resets the search; button 0 held pauses it (holding whatever prime is currently lit); otherwise it keeps counting up, lighting the low 5 bits of each newly-found prime on the LEDs and printing it over UART. Built cleanly against the real `csr.h` from the `ButtonSoC` build above -- confirmed both `CSR_BUTTONS_BASE` is defined and the `primes` strings are actually present in the linked `demo.bin` (7,072 bytes), so the button-gated code really compiled in, not silently `#ifdef`'d away.

Load it the standard way -- from the `litex>` prompt already on screen from the BIOS section above, no reflash:

```
$ litex_term /dev/ttyUSB1 --kernel=demo.bin --kernel-adr=0x10010000 --serial-boot
```

**`--kernel-adr` is not optional here, and this is worth flagging because it's an easy silent mistake**: `litex_term`'s own default is `0x40000000` (correct for boards like the Arty where `main_ram` happens to sit there), but this SoC's `mem_list` output above already showed `MAIN_RAM 0x10010000` -- and the demo was linked against that exact address (`litex_bare_metal_demo`'s `--mem` defaults to `main_ram`, confirmed against this build's own `regions.ld`: `main_ram : ORIGIN = 0x10010000`). Leaving `--kernel-adr` at its default would upload to the wrong address on this board and run garbage. Always cross-check against this SoC's own `mem_list`, not a value copied from another board's tutorial.

Then type `serialboot` at the `litex>` prompt (or just reset the board -- either path reaches the same handshake). `litex_term` recognizes the SFL handshake automatically and uploads. **Actually ran this end-to-end just now** (piped through a pty so the transcript could be captured non-interactively):

```
serialboot
Booting from serial...
Press Q or ESC to abort boot completely.
sL5DdSMmkekro
[LITEX-TERM] Received firmware download request from the device.
[LITEX-TERM] Uploading demo.bin to 0x10010000 (7072 bytes)...
[LITEX-TERM] Upload calibration... (inter-frame: 0.00us, length: 251, window: 8)
[LITEX-TERM] Upload failed with length 251, window 8: device reported a serial frame error.
[LITEX-TERM] Retrying with length 64, window 1.
[LITEX-TERM] Upload complete (3.9KB/s).
[LITEX-TERM] Booting the device.
Executing booted program at 0x10010000

--============== Liftoff! ==============--

LiteX minimal demo app built Aug 27 2026 22:25:29

Available commands:
help               - Show this command
reboot             - Reboot CPU
led                - Led demo
donut              - Spinning Donut demo
helloc             - Hello C
primes             - Button-controlled prime search on the LEDs
litex-demo-app> primes
Hold button 0 to pause, button 1 to reset back to n=2. Ctrl-C the terminal to stop.
prime #1: 2  (0x02 on LEDs)
prime #2: 3  (0x03 on LEDs)
prime #3: 5  (0x05 on LEDs)
...
prime #145: 829  (0x1d on LEDs)
```

Worth knowing, not a real problem: the upload auto-negotiated down from its fastest calibrated transfer settings (`length: 251, window: 8`) after one frame error, retried slower, and completed fine at `length 64, window 1` -- normal over a real USB-serial cable rather than a lab bench, `litex_term` handles the retry on its own. 145 real primes found and correctly displayed in a few seconds with no buttons touched (search running unpaused) -- confirms the arithmetic, the LED write, and the UART trace are all actually working together, independent of anyone pressing anything.

**Try it and check the board**: run the `litex_term` command above (with `--kernel-adr=0x10010000`), type `serialboot` then `primes`, and watch the LEDs step through the low bits of 2, 3, 5, 7, 11, 13... Hold breakaway-ears button 0 to freeze it, button 1 to restart from 2.

### Is `/dev/ttyUSB0` always the programming channel and `ttyUSB1` always the UART?

Not reliably by number -- but the FT2232H's two channels are fixed in hardware, and there's a stable way to name them. The chip always exposes USB interface 0 (Channel A, wired on this board to the FPGA's CRESET/CDONE/SPI pins -- what `iceprog`/`openFPGALoader` talk to) and interface 1 (Channel B, wired to the FPGA fabric's UART pins -- the console). Interface 0 is *usually* claimed first and lands on the lower `ttyUSBn` number, which is why it's been `ttyUSB0`=programming/`ttyUSB1`=UART all through this session -- but that numbering is assigned by whichever channel's node the kernel happens to register first, not by anything the hardware guarantees. Plug in a second FTDI device, replug in a different order, or hit a probe-timing race, and the numbers can shift. This session already saw `ttyUSB0` vanish twice after `iceprog`/`openFPGALoader` ran, while `ttyUSB1` stayed put -- a preview of exactly this kind of instability.

The robust fix: use the `/dev/serial/by-id/` symlinks instead of raw `ttyUSBn`. They encode the actual USB interface number, so they can't shift with enumeration order:

```
$ ls /dev/serial/by-id/
usb-1BitSquared_iCEBreaker_V1.0e_ibP54Olo-if01-port0
```

`-if01-port0` = interface 1 = Channel B = UART, confirmed pointing at `ttyUSB1` on this machine right now. The equivalent `-if00-port0` (Channel A, programming) would appear the same way whenever that channel's tty node exists. `litex_term /dev/serial/by-id/usb-1BitSquared_iCEBreaker_V1.0e_ibP54Olo-if01-port0` is the version of the command that keeps working even if a replug flips which raw number gets assigned.

### In the BIOS, what `mem_test` actually exercises without corrupting anything

`mem_test <addr> [maxsize]` (in `litex/soc/software/bios/cmds/cmd_mem.c`, alongside `mem_read`/`mem_write`/`mem_copy`/`mem_speed`) is a real destructive write-then-verify test (`libbase/memtest.c`: writes `0xAAAAAAAA`/`0x55555555` bus patterns, then an LFSR data pattern, across the whole range, then reads it all back). It does not restore the original contents afterward -- running it over live code or the running BIOS's own stack will crash the board. **If `maxsize` is omitted it defaults to 2 MiB** (`MEMTEST_DATA_SIZE`), which is 32x bigger than this entire chip's RAM, so never call it bare.

Asked the running BIOS what its actual memory map is rather than assuming one:

```
litex> mem_list
Region   Origin     End        Size
PSRAM    0x10000000 0x1001ffff 0x20000
SRAM     0x10000000 0x1000ffff 0x10000
MAIN_RAM 0x10010000 0x1001ffff 0x10000
SPIFLASH 0x00000000 0x00ffffff 0x1000000
ROM      0x00040000 0x00047fff 0x8000
CSR      0xf0000000 0xf000ffff 0x10000
```

`SRAM` (`0x10000000`-`0x1000ffff`) is where the *running* BIOS keeps its own stack and data -- testing it while it's in use is the crash scenario above. `ROM` and `SPIFLASH` are the flash-mapped BIOS code itself, not writable RAM to test. `MAIN_RAM` (`0x10010000`-`0x1001ffff`, 64 KB) is the one region that's just idle scratch space while sitting at the BIOS prompt -- nothing else is using it. The safe command that still genuinely exercises real memory is to test exactly that region, no more:

```
litex> mem_test 0x10010000 0x10000
Memtest at 0x10010000 (64.0KiB)...
  Write: 0x10010000-0x10020000 64.0KiB
   Read: 0x10010000-0x10020000 64.0KiB
Memtest OK
```

Ran that on this board just now -- passed with 0 errors, and the BIOS was still fully responsive afterward (`leds 0` worked immediately after). That's the pattern for any board/build: run `mem_list` first, then bound `mem_test` to exactly the `MAIN_RAM` row's origin and size, never to `SRAM`/`ROM`/`SPIFLASH`, and never without an explicit `maxsize`.

**Can a "bare" RISC-V core plus baremetal C go directly in the fabric, no SDRAM?** Yes, and this is really the same architecture as the LiteX target above with the SoC-generator scaffolding removed -- a CPU, a block of on-chip memory for both instructions and data, and flash for persistent storage, all as raw HDL:

* **PicoRV32** (Yosys/nextpnr's own reference core) -- roughly 1,000-1,250 LUTs for a minimal configuration, meant to be paired with exactly this pattern (on-chip block RAM + memory-mapped SPI flash for XIP). Comfortably fits alongside the on-chip SPRAM.
* **SERV** -- a bit-serial RISC-V core (already present locally at `pythondata-cpu-serv`), around 200-250 LUTs, the smallest real RISC-V implementation available for exactly this class of chip. Trades speed for size -- one bit of each operation per clock -- but is a real RV32I core running real compiled C.

Either would use `riscv64-unknown-elf-gcc` (already installed) to compile baremetal C, link it into UP5K's on-chip RAM (SPRAM and/or the 30 EBR blocks, ~15 KB more), and load the whole thing -- CPU and program both -- as one `nextpnr-ice40`-placed bitstream. That's a separate build from today's blinky, not attempted in this pass, but every piece needed for it (RISC-V GCC, the iCE40 backend, and a documented small-core target to crib from) is already on this machine.

## Course comparison: Icepi Zero vs. iCEBreaker v1.1 vs. UPduino v3.1

Three open-toolchain boards, three very different price points and teaching trade-offs. Current pricing/stock, checked 2026-08-27:

| | **Icepi Zero** | **iCEBreaker v1.1a** | **UPduino v3.1** |
|---|---|---|---|
| FPGA | Lattice ECP5-25F | Lattice iCE40UP5K | Lattice iCE40UP5K (same die as iCEBreaker) |
| Logic | ~24K LUTs | 5.3K LUTs | 5.3K LUTs |
| RAM | 32 MiB SDRAM @ 166 MHz | 128 KB on-chip SPRAM + 64 Mbit (8 MB) QSPI PSRAM | 128 KB on-chip SPRAM (1 Mb) + 120 Kb DPRAM |
| Flash | 16 MB QSPI | (config flash, size not load-bearing here) | 4 MB SPI |
| Video | GPDI (mini-HDMI) | none | none |
| Onboard I/O | none dedicated -- 40-pin RPi GPIO header instead | 1 button + 2 LEDs on the base board, **+3 buttons/5 LEDs on the breakaway ears** (used throughout this doc), 3 PMOD connectors | 1 RGB LED, **no buttons at all** -- 32 raw GPIO on bare 0.1" headers |
| Form factor | Raspberry Pi Zero-shaped board | PMOD dev board | Bare breadboard-pluggable module, no enclosure |
| USB | 3x USB-C | 1x USB-C (FTDI FT2232H: JTAG/config + UART) | 1x USB (FTDI FT232H programmer) |
| Price | $69 | $79.95 | $36 (Tindie) / $36 (tinyvision.ai, **sold out** there right now) |
| Stock (2026-08-27) | Mouser: 76 in stock, ships immediately | Mouser: in stock | **Not on Mouser at all.** Tindie: "only 7 left." tinyvision.ai's own store: sold out. |

The procurement column matters as much as the spec column for a class order: Icepi Zero and iCEBreaker are both ordinary Mouser line items (POs, tax exemption, predictable lead time -- the way a university department actually buys 20 of something). UPduino, despite being the cheapest board by far, currently has to be sourced through a maker marketplace with 7 units left in one listing -- fine for a personal order, a real risk for outfitting a whole section on a semester timeline.

### What's an interesting junior-level physics electronics lab project on each?

**Icepi Zero** (the SDRAM + video unlocks a different category of project, not just a bigger version of the others):
* A from-scratch VGA/GPDI timing generator -- build horizontal/vertical sync and porches by hand in Verilog, then verify the actual pixel clock and sync pulse widths on a real oscilloscope. Directly ties raster-scan timing to the kind of period/frequency measurement a physics lab already teaches.
* A real logic analyzer or mini oscilloscope built in fabric (LiteScope is already installed and proven in this environment -- `litescope_prbs_demo`) -- capture real analog-adjacent signals from a class experiment (a photogate, a piezo pickup) at native sample rates the tiny iCE40 boards can't buffer.
* Embedded Linux + Python driving a custom hardware peripheral end-to-end -- this document's own confirmed working RAM-rootfs boot on this exact board -- as a capstone: students write the HDL peripheral, the Wishbone/CSR glue, and the Python that reads it, all on one board.
* PRBS/LFSR-based pseudorandom sequence generation at a scale (32 MiB, 24K LUTs) large enough to do real autocorrelation/spread-spectrum measurement, not just a toy-sized shift register.

**iCEBreaker v1.1** (explicitly designed for teaching, and this document's own worked examples are already lab-ready):
* Everything already built and verified in this document: a debounced button/LED state machine, a LiteX+VexRiscv SoC that boots to an interactive BIOS, and bare-metal C doing real integer arithmetic (the prime-search demo) driven by real buttons -- a natural three-week progression from raw HDL, to a full SoC, to software on a soft CPU.
* Build a UART transmitter/receiver from scratch against the onboard FTDI's UART channel -- a genuine "design a communication protocol" lab (start/stop bits, baud generation, framing errors -- the same framing-error/retry behavior this document's own serial upload hit is a real example to show).
* An ADC PMOD (several exist off-the-shelf) digitizing a real analog signal from another station in the lab (thermocouple, photodiode, strain gauge) -- sampling and quantization made concrete instead of abstract.
* The PRBS31 LiteX peripheral this document is heading toward next -- pseudorandom bit sequences are a real topic (spread-spectrum, jitter/BER testing) at a scale (128 KB) that still comfortably fits a one-lab-period build.

**UPduino v3.1** (same silicon as the iCEBreaker, so all of the above HDL/LiteX/bare-metal content ports over directly -- the pedagogical trade-off is entirely about the bare board, not the FPGA):
* No onboard buttons or LEDs beyond one RGB LED is a feature here, not a gap, for a *physics electronics* lab specifically: students build their own pushbutton circuit on a breadboard (pull-up resistor, RC debounce network) and their own LED-plus-current-limiting-resistor circuit, wire them to bare GPIO pins, and can put a scope probe directly on the mechanical bounce they coded around in HDL -- exactly the discrete-circuit intuition the "batteries included" boards let students skip past.
* 32 raw 0.1" GPIO pins with no PMOD connector in the way makes it the easiest of the three to wire an improvised sensor circuit directly with jumper wires -- a photogate-timer or speed-of-sound piezo-timing experiment where the FPGA is just the fast, precise clock/counter behind a circuit the students built themselves.
* Cheap enough (at $36, roughly half the iCEBreaker) to plausibly go one-board-per-student rather than shared lab stations, if procurement timing allows sourcing enough of them.

### What does the more expensive hardware actually unlock?

Not "more of the same, faster" -- three qualitatively different things become possible that don't fit on either iCE40 board at all, no matter how the code is optimized:

1. **Real embedded Linux and Python running on the board itself.** This requires an MMU-capable soft core plus enough RAM to be worth it -- 128 KB (iCEBreaker/UPduino) is a hard ceiling no amount of clever coding gets around, while Icepi Zero's 32 MiB is exactly what this whole project already proved sufficient for. This is the single biggest step-change: "compile HDL, flash, done" becomes "SSH in and run a Python script."
2. **Video output as a lab instrument in its own right.** Building a real VGA/GPDI signal from scratch and displaying it on an actual monitor is a fundamentally different (and more physics-relevant, in terms of timing/frequency measurement) exercise than blinking LEDs -- and neither iCE40 board has the connector or the pixel-clock-scale resources to attempt it.
3. **Larger, more parallel DSP designs.** 24K LUTs vs. 5.3K is not a small gap -- wider/deeper FFTs, several filter channels running in parallel, or a full MMU-capable soft core (VexRiscv-SMP) all need headroom the UP5K simply doesn't have, independent of how efficiently the design is written.

For a junior-level course that's mostly digital logic, state machines, and "my first soft CPU," the iCE40 boards are not a compromise -- they're arguably the *better* teaching tool (cheaper, and on the UPduino, more breadboard-honest about the underlying circuits). The Icepi Zero's price premium buys a genuinely different kind of project, not a faster version of the same one.
