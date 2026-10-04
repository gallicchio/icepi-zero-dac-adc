# How the tutorial was made

Nothing here is needed to follow the tutorial. It's the record of how the
tutorial's numbers and figures were measured, and the tools for checking new
boards.

| | |
| --- | --- |
| [`CLAUDE_CODE_CHAT.md`](CLAUDE_CODE_CHAT.md) | the log of the Claude Code sessions that designed, tested and wrote the tutorial: each prompt, and what was done about it |
| [`tools/`](tools/) | the instructor's scripts: `fig_*.py` made the figures (most can redraw from the saved data with `--replot`), `anim_leds.py` the LED animations of [1.01](../tutorial/1_01_led_counter.md#101-a-counter-on-the-leds) and [1.04](../tutorial/1_04_adc_on_the_leds.md#104-the-adc-on-the-leds) (a KiCad render plus Verilator simulations), `fig_stack.py` the views of the stack from above, `fig_openers.py` the pages' opening diagrams, `m2k.py` drives an ADALM2000, `serialboot.py`, `console.py` and `linux_shell.py` drive the board from a script; `sync_md.py` keeps the code on the tutorial's pages identical to the files in `src/` and writes the navigation, `check_tutorial.py` checks everything else, and `wiki_links.py` links concepts to Wikipedia where a page first mentions them |
| [`tools/boardtest/`](tools/boardtest/) | for a new Icepi Zero: test designs for its buttons, SD-card detect and oscillator, and scripts that provision SD cards on several boards at once |
| [`tools/pinspeed/`](tools/pinspeed/) | how fast the DAC and ADC pins really go (the Details in [1.01](../tutorial/1_01_led_counter.md#101-a-counter-on-the-leds) and [1.04](../tutorial/1_04_adc_on_the_leds.md#104-the-adc-on-the-leds)) |
| [`tools/comms/`](tools/comms/) | the figure scripts of Chapter 6; each takes `--sim`, a port, two ports or `--replot` (`link.py`) |
| [`tools/dsp/`](tools/dsp/) | the figure scripts of Chapter 7: `--sim`, a port, `--m2k PORT` (the ADALM2000 as generator and scope) or `--replot` (`link.py`); `fig_fixed_scope.py` draws the scope traces of 7.01's fixed filters |
| [`tools/twoboard/`](tools/twoboard/) | the figure scripts and extra measurements of Chapter 5 |
| [`data/`](data/) | the raw measurements behind the figures, as NumPy files |

After changing anything, run `make sync` and then `make check` from the top of
the repository: the first copies files from `src/` into the tutorial's pages
and rewrites the navigation, the second checks the code, every link, anchor
and picture, and that every section named in the text is a link. Whoever
edits the tutorial, a person or a program, should leave `make check` with no
errors.
