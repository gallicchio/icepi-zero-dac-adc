# openfpga_testing

Standalone test code developed while debugging the Colorlight i9 /
DAPLink `<DAPLink:Overflow>` issue (see `../openfpga.md`), kept here so it
survives between machines instead of living only as scratch files under
`~/openfpga/` (which got wiped and recloned once already during that
investigation).

* `uart_stress_test/` -- raw-Verilog UART TX stress test + serial capture
  scripts, used to isolate whether overflow failures are link/probe-level
  or LiteX/BIOS-specific, and to compare reliability across host machines.
* `bare_metal_gpio_demo/` -- LiteX target script + bare-metal C for the
  "Bare-metal C on a LiteX SoC" GPIO tutorial section, buildable and
  bootable with no PMODs physically attached.
