# The XY show: two Icepi Zeros draw in 3D on an oscilloscope

The code of [5.08 A 3D show on an oscilloscope](../../tutorial/5_08_xy_show.md): the page explains how it works.  In short:

```console
cd src/xyshow
make            # build/x.bit and build/y.bit (the OSS CAD Suite of 1.00; a few minutes each)
make flash      # X into the board with the lower FT231X serial number, Y into the other
```

Cable each board's DAC to the other board's ADC, as in [5.00](../../tutorial/5_00_two_boards.md#500-two-boards-on-one-laptop), with an SMA tee
at each ADC to take the DAC to the scope too: board X's DAC to the scope's X input (channel 1), board Y's to channel 2,
and the scope in XY mode at about 0.8 V a division.

| file | what |
|---|---|
| `make_show.py` | the show: its constants (the finales and their order, the times, the speeds) and the program that writes the tables in `rtl/` from them; `--movie` renders a preview of what the boards will draw |
| `flash.py` | loads `build/x.bit` and `build/y.bit` into the two boards, the same way round every time (`make flash`, `make load`) |
| `rtl/top_icepi.v` | the top: `ROLE` 0 is the X board (the sequencer, and the burst on its DAC), 1 the Y board (it decodes the burst and follows) |
| `rtl/vec3d.v` | the vector engine: the scene memory, the transform, perspective, culling, the FIFO and the line generator |
| `rtl/matrix_unit.v` | the animator: 32 phases and a small microprogrammed computer that writes the 16 matrices |
| `rtl/show_seq.v` | the sequencer: the modes and their times, the finales, the spinner's ramp |
| `rtl/sync_link.v` | the burst that keeps the Y board in step: `sync_tx` on the X board, `sync_rx` on the Y board |
| `rtl/lorenz.v`, `rtl/chua.v` | two chaotic circuits computed live in fixed point: Lorenz's equations by Euler steps with one multiplier, Chua's circuit by Runge-Kutta with shifts and adds only |
| `rtl/regbus.v`, `rtl/uart.v` | the register bus over the USB serial port (1 Mbaud) |
| `rtl/*.hex`, `rtl/*.vh` | the tables, written by `make_show.py`: the scene (`scene_xy.hex`, `scene_z.hex`), the perspective and sine tables, the animator's program and constants, the parameters and the finales' table |
| `host/` | the Python behind the tables: the scene (`scene.py`, `gen_scene.py`), the finales' objects (`objects.py`, `proposals.py`), the animator's program and its bit-exact model (`gen_matrix_prog.py`), a check of it against the float models (`check_prog.py`), and `show.py`, which talks to the boards |
| `sim/tb_icepi.v`, `sim/render_icepi.py` | both boards simulated through a modelled cable (`make sim`) |

`host/seal.json` is Harvey Mudd College's seal, traced into strokes, and the spinner's cap carries the College's
wordmark in stroke letters: both belong to the College and are not covered by this repository's licence.  The
molecules are PubChem's (public domain) and the coastline Natural Earth's (public domain).
