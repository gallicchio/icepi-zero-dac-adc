<!-- nav -->
[← 0.00 The hardware](0_00_the_hardware.md#000-the-hardware) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [1.00 Circuits from code →](1_00_circuits_from_code.md#100-circuits-from-code)

# 0.01 How to use this tutorial

<img src="img/stack_loopback.png" alt="Seen from above, USB connectors at the bottom: ADC IN is the left SMA, DAC OUT the right one, and the loopback cable joins them" width="400">

Every diagram of the board in this tutorial looks like this one: seen from
above, USB connectors at the bottom, **[ADC](https://en.wikipedia.org/wiki/Analog-to-digital_converter) IN on the left and [DAC](https://en.wikipedia.org/wiki/Digital-to-analog_converter) OUT on the
right**.

## Get the files

Everything you'll build is in this repository's [`src/`](../src/) folder. Get a
copy on your laptop, either with git:

```bash
git clone https://github.com/gallicchio/icepi-zero-dac-adc.git
cd icepi-zero-dac-adc
```

or with the green **Code → Download ZIP** button on the repository's GitHub
page. Each page tells you which folder to work in: Chapters 1 and 4 in
[`src/verilog/`](../src/verilog/), Chapter 2 in [`src/riscv/`](../src/riscv/),
Chapter 3 in [`src/linux/`](../src/linux/), Chapter 5 in
[`src/twoboard/`](../src/twoboard/) and Chapter 6 in
[`src/comms/`](../src/comms/).

## How the pages work

**Code.** Every source file is printed in full on the page that explains it,
so you can follow along on GitHub alone. The printed copy is kept identical
to the file in `src/` by a script ([`dev/tools/sync_md.py`](../dev/tools/sync_md.py)),
so what you read is what was tested. (`make check`, in the repository's top
folder, checks that, and that every link and picture on every page works.) Longer files that you don't need to read
line by line are folded away: click to open them.

**The lines that matter.** In the code, a banner like this marks where the
action is:

```systemverilog
        // ######################################################################
        // ##  KEY LINE: add one, every 20 ns.  That's the whole circuit.
        // ######################################################################
        count <= count + 1;
```

The rest of a file is usually plumbing: declaring wires, clocking the
converters, talking to the serial port. Short, quiet comments answer the
questions you might have on the way.

<details>
<summary><b>Detail:</b> boxes like this one hold background you can skip</summary>

Some paragraphs explain *why* a number is what it is, or what happened when
something was measured more carefully. They are folded away so that a first
pass through a page stays short. Come back to them when you're curious, or
when something doesn't work.

</details>

**Try this.** Most pages end with a few exercises. Some take five minutes and
some are small projects. They're where most of the learning happens.

## Where does this run?

By Chapter 3 there are five places a command can run, and the prompt at the
start of each line in a console block tells you which. Students mix these up
more than anything else in the tutorial, so:

| prompt | where | what it is |
| --- | --- | --- |
| `$` | your laptop | its shell, in the folder the page names; `python3 x.py` runs the laptop's Python with numpy |
| `litex>` | the board | the [BIOS](https://en.wikipedia.org/wiki/BIOS) of Chapter 2, through `litex_term` |
| `>` or a name like `adda>` | the board | a bare-metal C program's own prompt (Chapter 2) |
| `#` | the board | root's shell under Linux (Chapter 3); `micropython` there runs MicroPython *on the board* |
| `>>>` | the board | MicroPython's prompt, after you typed `micropython` at a `#` |
| `A#`, `B#`, `A$` | board A, board B, the laptop | with two boards (Chapter 5) |

Two Pythons talk to the board from the laptop, and both show a `$` prompt:
the scripts of Chapters 1, 4, 5 and 6 talk over the serial port, and
[2.06](2_06_registers_from_the_laptop.md#206-the-registers-from-the-laptop)'s talks through `litex_server`. Lines without a prompt
in a console block are what the program printed.

A block of commands with no prompt at all, like the `git clone` above, is
typed at the laptop's `$`. Everything in Chapter 1 runs on the laptop.

![What runs where: the laptop with the shell prompt dollar and the Python prompt, connected by USB to the board, whose prompt is litex> under the BIOS, adda> under the firmware, none under awgcap.sv, root's hash under Linux and the Python prompt under MicroPython, and to a second board whose Linux prompt is B hash; a coax joins the boards' DAC and ADC](img/comms_d_where.png)

## Talking to the board

The Icepi Zero's USB port is also a serial port, and its name depends on
your laptop:

| laptop | the board's serial port |
| --- | --- |
| Linux, and Windows with WSL ([1.00](1_00_circuits_from_code.md#100-circuits-from-code)) | `/dev/ttyUSB0` (or `ttyUSB1`, ... with several boards) |
| macOS | `/dev/cu.usbserial-` followed by the board's serial number, e.g. `/dev/cu.usbserial-DP051TLX` |

The Python scripts find the board by themselves. Other programs (`litex_term`,
`screen`) need the name; the commands here use `/dev/ttyUSB0`, so put in your
own. On a Mac, `ls /dev/cu.usbserial*` shows it.

## Numbers and units

*MS/s* is millions of samples per second. A *code* is the number on an
8-bit converter's pins, 0 to 255. "2<sup>20</sup>" is two to the twentieth
power, 1,048,576, and `0x51eb852` is [hexadecimal](https://en.wikipedia.org/wiki/Hexadecimal).

Sections are numbered by chapter, and the file names match, written with an
underscore so that they sort in order on GitHub:
[1.06](1_06_fast_capture.md#106-fast-captures), the seventh section of Chapter 1
(counting the opening page, [1.00](1_00_circuits_from_code.md#100-circuits-from-code)), is
[`1_06_fast_capture.md`](1_06_fast_capture.md#106-fast-captures). A
section named in the text is always a link to it.

<!-- nav -->
[← 0.00 The hardware](0_00_the_hardware.md#000-the-hardware) &emsp;&emsp;&emsp; **[Contents](../README.md#contents)** &emsp;&emsp;&emsp; [1.00 Circuits from code →](1_00_circuits_from_code.md#100-circuits-from-code)

<!-- author -->
<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>
