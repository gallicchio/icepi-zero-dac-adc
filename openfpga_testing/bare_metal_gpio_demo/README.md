# bare_metal_gpio_demo

Implements the "Bare-metal C on a LiteX SoC: stock GPIO peripherals for the
LED/button/switch PMODs" section of `../../openfpga.md`: a bare-metal
(non-Linux) VexRiscv SoC with the 8-LED PMOD (`pmodk`) and 4-button +
4-switch PMOD (`pmodl`) wired to LiteX's stock `GPIOOut`/`GPIOIn`, plus a
`gpio` console command that polls switches/buttons and drives the LEDs.

Builds and boots with **no PMODs physically attached** -- the switch/button
inputs are pulled up (`Misc("PULLMODE=UP")` in `gpio_pmods.py`) so they read
a safe idle value, and the LED outputs just drive pins that go nowhere.
`gpio_demo_cmd()` in `main.c.patched` prints every reading over serial for
exactly this reason (the tutorial's original version only drives LEDs
silently, which is unobservable with no PMODs and no scope attached).

## Files

* `gpio_pmods.py` -- the three new IO entries (`user_leds8`, `user_switches4`,
  `user_buttons4`), bit-order-corrected against the raw-Verilog GPIO demo's
  verified `.lpf` (Pins() token order *is* bit index, so this is where the
  LSB-first reordering has to happen -- see the comment block in the file).
* `colorlight_i9_gpio.py` -- standalone target script. Builds the stock
  `litex_boards.targets.colorlight_i5.BaseSoC` (board=i9, revision=7.2),
  then wires the GPIO extension/peripherals onto it exactly the way
  `colorlight_i5.py`'s own `main()` bolts on `_sdcard_pmod_io` after
  `BaseSoC.__init__` -- no subclassing or monkeypatching needed.
* `main.c.patched` -- the litex bare-metal demo's `main.c` with two commands
  added, both guarded by `#ifdef CSR_LEDS8_BASE`:
  * `gpio` (`gpio_demo_cmd`) -- **bounded to 20 iterations**, unlike the
    tutorial's `while(1)` version, so it finishes on its own when driven
    from a scripted serial capture instead of an interactive terminal.
    Change back to `while(1)` for interactive live-tracking use.
  * `ledtest` (`ledtest_cmd`) -- diagnostic added while debugging a real
    wiring issue (see below): holds all-off, all-on, low-nibble,
    high-nibble, bit-0-only, and bit-7-only for 4s each, on repeat, so
    polarity and per-bit LED control can be confirmed by eye without
    needing to interpret a single static pattern. **Loops forever with no
    exit command** -- deliberately, so there's no race against how long a
    human takes to go look at the board, but it also means `console_service()`
    never regains control once started: a queued command sent while it's
    running is silently dropped (it doesn't queue for after), and the only
    way back to the prompt is a fresh JTAG reflash + reupload, not `reboot`.
    If reusing this, consider adding a serial-input check inside the loop
    if you want it interruptible instead.
* `serial_boot.py` -- non-interactive SFL kernel upload (see "Flashing and
  running" below for why this exists alongside `litex_term`).
* `send_and_capture.py` -- opens the port, waits, sends one command line
  (e.g. `gpio`), and captures the response for a fixed window. Generic,
  not gpio-specific -- useful for driving the demo app's console from a
  script for any command.

## Rebuilding from scratch on a new machine

```bash
mkdir -p ~/openfpga/gpio_demo && cd ~/openfpga/gpio_demo
cp /path/to/this/dir/gpio_pmods.py /path/to/this/dir/colorlight_i9_gpio.py .

python3 colorlight_i9_gpio.py --build          # SoC gateware, ~45s
grep -iE "leds8|switches|buttons" build/colorlight_i5/csr.csv   # sanity check

litex_bare_metal_demo --build-path=build/colorlight_i5   # generates demo/
cp /path/to/this/dir/main.c.patched demo/main.c
make -C demo BUILD_DIR=$(pwd)/build/colorlight_i5   # NOTE: pass BUILD_DIR
                                                     # explicitly -- the
                                                     # Makefile's own
                                                     # default (../build/)
                                                     # only resolves if you
                                                     # cd into demo/ first
                                                     # AND the layout matches
```

## Flashing and running

`litex_term` requires a real TTY on stdin (it calls `termios.tcgetattr`) and
fails immediately with `termios.error: (25, 'Inappropriate ioctl for
device')` when driven from a non-interactive/scripted context (a backgrounded
shell, a tool call with no real stdin) -- the same class of problem this
whole investigation already hit with `picocom`. `serial_boot.py` is a
from-scratch reimplementation of just the SFL upload protocol litex_term
uses (same `sL5DdSMmkekro` magic handshake, same frame format, CRC16 table
verified to match litex_term's byte-for-byte), with no TTY dependency, for
exactly this situation. Interactively at a real terminal, plain `litex_term`
works fine and is simpler -- reach for `serial_boot.py` only when scripting.

```bash
openFPGALoader -b colorlight-i9 build/colorlight_i5/gateware/colorlight_i5.bit

# interactively:
litex_term /dev/ttyACM0 --kernel=demo/demo.bin
# at the litex-demo-app> prompt:
gpio

# or, non-interactively / scripted (close one before opening the other --
# see the JTAG/serial hazard note below):
python3 serial_boot.py /dev/ttyACM0 115200 demo/demo.bin 0x40000000 20
python3 send_and_capture.py /dev/ttyACM0 115200 gpio 1.0 10
```

**Confirmed working on real hardware with no PMODs attached (2026-08-23):**
all 20 `gpio` iterations read `switches=0xf buttons=0x0 -> leds8_out=0xf0
(readback=0xf0)` -- exactly the expected all-idle values (switches pulled
up and uninverted = reads "up"/1; buttons pulled up then inverted in
gateware = reads "not pressed"/0), confirming the CSR pipeline end-to-end
even with nothing physically attached.

**Confirmed working with real PMODs attached, same day, after finding and
fixing a real wiring issue.** First attempt with PMODs physically plugged
in showed `gpio` still reading the same all-idle `switches=0xf buttons=0x0`
regardless of actual switch position, and the LED pattern didn't look like
the expected half-on/half-off split -- i.e. the readings never changed at
all, not just in the wrong bit order. That ruled out a software bit-order
bug (a real bug there would still change *something* when a switch moved)
and pointed at the PMODs simply not being electrically connected to the
pins this design drives. Root cause, found by the user: **the PMODs were in
the wrong physical header** -- the board was oriented differently (upside
down, tighter space) than during the original raw-Verilog empirical
verification, and it wasn't obvious from that orientation which header was
actually P6. `ledtest`'s all-off/all-on toggle and moving single-LED phases
were the deciding evidence once eyes were actually on the right header: LEDs
toggled clearly and a single lit LED visibly moved position between the
bit-0-only and bit-7-only phases, confirming real, distinct per-bit
electrical control -- not just "some LED is stuck on."

After moving the PMODs to the correct header, `gpio` read `switches=0x9`
(binary `1001`) with two switches down -- confirmed by the user as exactly
the physical state they'd set (the two down switches are the middle two of
the four, per the LSB-first bit convention: `switches[3]`=leftmost,
`switches[0]`=rightmost). **Lesson for next time this board changes
orientation or gets moved to tighter quarters: don't assume "PMOD is
plugged into *a* connector" means "plugged into the *right* connector" --
verify against which physical header is actually P6 for the board's current
orientation before assuming a software bug.**
