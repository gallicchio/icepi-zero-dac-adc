#!/usr/bin/env python3
"""The show's two boards from the laptop.  Not needed for the show, which runs by itself from the flash; this looks
inside it, over each board's USB serial port (1 Mbaud) and the register bus of rtl/regbus.v: a command byte (bit 7 =
write, bits 6:0 the register), then four data bytes, least significant first; a read is answered with four bytes.

    python3 host/show.py                  both boards: which is X and which Y, the build, the mode, the finale, frames a second
    python3 host/show.py sync             the Y board: bursts received good and bad, the levels its ADC sees, its rate trim
    python3 host/show.py mode 1           hold the X board in mode 1 (the seal and its globe) or 2 (the seal turning over)
    python3 host/show.py finale 12        hold the 13th finale (they count from 0, in make_show.py's FINALES order)
    python3 host/show.py auto             back to the show
    python3 host/show.py dither 0         both boards' DACs rounded to 8 bits: the stairs on nearly level lines; `dither 1`
                                          puts back the sub-code dither (the default at power-up)
    python3 host/show.py draw "HELLO"     your own drawing: stroke letters into both boards' free scene memory, shown in
                                          mode 4 and turning over as the seal does (auto ends it)

The registers are listed at the top of rtl/top_icepi.v.  Commands that hold a mode go to the X board, which runs the
sequencer; the Y board follows it through the burst.  A drawing goes to both boards, since each draws its own
scene memory.
"""
import json, os, struct, sys, time
import serial
from serial.tools import list_ports

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
Q = 1 << 14
ID = 0xEC5B5E4C                              # register 0: this, with bit 0 the board's role (0 X, 1 Y)


class Board:
    def __init__(self, port):
        self.port = port
        self.s = serial.Serial(port, 1_000_000, timeout=1.0)
        self.s.reset_input_buffer()
        self.s.write(bytes(5)); time.sleep(0.01); self.s.reset_input_buffer()   # five reads of register 0 resynchronise the bus
    def wr(self, a, d): self.s.write(bytes([0x80 | a]) + struct.pack("<I", d & 0xFFFFFFFF))
    def rd(self, a):
        self.s.write(bytes([a & 0x7F])); r = self.s.read(4)
        if len(r) != 4: raise IOError("%s: no answer (is the show's bitstream loaded?)" % self.port)
        return struct.unpack("<I", r)[0]
    def role(self): return "Y" if self.rd(0) & 1 else "X"
    def status(self):
        s = self.rd(4)
        return dict(role=self.role(), build="%08x" % self.rd(1), mode=(s >> 7) & 15, finale=(s >> 11) & 31, frames_per_s=self.rd(6))


def boards():
    """{'X': Board, 'Y': Board}, found by the FT231X (0403:6015) and the role each answers with"""
    out = {}
    for p in sorted(list_ports.comports(), key=lambda p: p.serial_number or ""):
        if (p.vid, p.pid) != (0x0403, 0x6015): continue
        b = Board(p.device)
        try:
            if b.rd(0) & ~1 == ID: out[b.role()] = b
        except IOError:
            pass
    if not out: sys.exit("no board answers with the show's ID: are the bitstreams loaded (make flash)?")
    return out


def q14(v): return int(max(-32768, min(32767, round(v * Q)))) & 0xFFFF


def draw(B, polylines, group=0):
    """Upload polylines ((x, y) in -1..1) into the free region of both boards' scene memory and show them in mode 4.
    Group 0's matrix is the seal's (the animator's seal section runs in mode 4), so the drawing turns over as it does."""
    free_start, free_n = json.load(open(os.path.join(HERE, "scene_layout_icepi.json")))["free"]
    ents = []
    for pl in polylines:
        for i, (x, y) in enumerate(pl):
            ents.append((((1 if i else 0) << 35) | ((group & 3) << 33) | (q14(x) << 16) | q14(y), (group >> 2) & 3))
    if len(ents) > free_n: sys.exit("%d vertices; %d are free" % (len(ents), free_n))
    for b in B.values():
        b.wr(0x40, free_start)
        for xy, g32 in ents: b.wr(0x41, xy & 0xFFFFFFFF); b.wr(0x42, (g32 << 20) | ((xy >> 32) << 16))     # z = 0
        b.wr(0x20, (len(ents) << 16) | free_start); b.wr(0x21, 0); b.wr(0x22, 0)    # range 0: {count, start}; ranges 1, 2 empty
    B["X"].wr(0x10, 0x005 | (4 << 4))                                            # run, animate, mode 4, not auto
    return len(ents)


if __name__ == "__main__":
    a = sys.argv[1:]; B = boards()
    if not a:
        for r in sorted(B): print(r, B[r].port, B[r].status())
    elif a[0] == "sync":
        y = B.get("Y") or sys.exit("no Y board")
        s, l, t = y.rd(8), y.rd(9), y.rd(0xA)
        print("bursts good %d, bad %d; the ADC sees the gap at %d and a 1 at %d; rate trim %+.1f ppm"
              % (s & 0xFFFF, s >> 16, l & 0xFF, (l >> 8) & 0xFF, (t - 2 ** 31) / 2 ** 31 * 1e6))
    elif a[0] == "mode": B["X"].wr(0x10, 0x005 | (int(a[1]) << 4)); print(B["X"].status())
    elif a[0] == "finale": B["X"].wr(0x10, 0x005 | (3 << 4) | ((int(a[1]) & 31) << 9)); print(B["X"].status())
    elif a[0] == "auto": B["X"].wr(0x10, 0x007); print(B["X"].status())
    elif a[0] == "dither":                                                       # register 13; each board dithers its own DAC
        for r in sorted(B): B[r].wr(0x13, int(a[1]) & 1); print(r, "dither", B[r].rd(0x13))
    elif a[0] == "draw":
        import vector
        print(draw(B, vector.centred_text(" ".join(a[1:]), size=0.5)), "vertices drawn; `python3 host/show.py auto` to go back")
    else: sys.exit(__doc__)
