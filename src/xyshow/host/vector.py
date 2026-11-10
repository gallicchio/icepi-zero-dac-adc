#!/usr/bin/env python3
"""Vector graphics for an oscilloscope in XY mode, drawn by the two DACs.

A display list is a sequence of (x, y, beam) points in DAC units (-1..1 on each axis); the gateware steps
through it at a fixed rate and the scope's phosphor (or its persistence) joins the dots.  This module turns
text, polylines and a spinning wireframe into display lists; the host uploads them over the UART (a list of
up to 4096 points fits the player's BRAM), so a new drawing is seconds away, no bitstream rebuild.
"""
import numpy as np

# A stroke font on a 4 x 6 grid (x 0..4, y 0..6, baseline y = 0): one or more polylines per glyph.
FONT = {
 'A': [[(0,0),(2,6),(4,0)],[(0.8,2.4),(3.2,2.4)]],
 'B': [[(0,0),(0,6),(3,6),(4,5),(4,3.8),(3,3),(0,3)],[(3,3),(4,2),(4,1),(3,0),(0,0)]],
 'C': [[(4,5),(3,6),(1,6),(0,5),(0,1),(1,0),(3,0),(4,1)]],
 'D': [[(0,0),(0,6),(2.5,6),(4,4.5),(4,1.5),(2.5,0),(0,0)]],
 'E': [[(4,0),(0,0),(0,6),(4,6)],[(0,3),(3,3)]],
 'F': [[(0,0),(0,6),(4,6)],[(0,3),(3,3)]],
 'G': [[(4,5),(3,6),(1,6),(0,5),(0,1),(1,0),(3,0),(4,1),(4,3),(2.5,3)]],
 'H': [[(0,0),(0,6)],[(4,0),(4,6)],[(0,3),(4,3)]],
 'I': [[(1,0),(3,0)],[(2,0),(2,6)],[(1,6),(3,6)]],
 'J': [[(0,1),(1,0),(3,0),(4,1),(4,6)]],
 'K': [[(0,0),(0,6)],[(4,6),(0,2.5)],[(1.5,3.6),(4,0)]],
 'L': [[(0,6),(0,0),(4,0)]],
 'M': [[(0,0),(0,6),(2,3),(4,6),(4,0)]],
 'N': [[(0,0),(0,6),(4,0),(4,6)]],
 'O': [[(1,0),(0,1),(0,5),(1,6),(3,6),(4,5),(4,1),(3,0),(1,0)]],
 'P': [[(0,0),(0,6),(3,6),(4,5),(4,4),(3,3),(0,3)]],
 'Q': [[(1,0),(0,1),(0,5),(1,6),(3,6),(4,5),(4,1),(3,0),(1,0)],[(2.5,1.5),(4,0)]],
 'R': [[(0,0),(0,6),(3,6),(4,5),(4,4),(3,3),(0,3)],[(2,3),(4,0)]],
 'S': [[(4,5),(3,6),(1,6),(0,5),(0,4),(1,3),(3,3),(4,2),(4,1),(3,0),(1,0),(0,1)]],
 'T': [[(0,6),(4,6)],[(2,6),(2,0)]],
 'U': [[(0,6),(0,1),(1,0),(3,0),(4,1),(4,6)]],
 'V': [[(0,6),(2,0),(4,6)]],
 'W': [[(0,6),(1,0),(2,4),(3,0),(4,6)]],
 'X': [[(0,0),(4,6)],[(0,6),(4,0)]],
 'Y': [[(0,6),(2,3),(4,6)],[(2,3),(2,0)]],
 'Z': [[(0,6),(4,6),(0,0),(4,0)]],
 '0': [[(1,0),(0,1),(0,5),(1,6),(3,6),(4,5),(4,1),(3,0),(1,0)],[(0,1),(4,5)]],
 '1': [[(1,5),(2,6),(2,0)],[(1,0),(3,0)]],
 '2': [[(0,5),(1,6),(3,6),(4,5),(4,4),(0,0),(4,0)]],
 '3': [[(0,6),(4,6),(2,3.5),(3,3.5),(4,2.5),(4,1),(3,0),(1,0),(0,1)]],
 '4': [[(3,0),(3,6),(0,2),(4,2)]],
 '5': [[(4,6),(0,6),(0,3.5),(3,3.5),(4,2.5),(4,1),(3,0),(1,0),(0,1)]],
 '6': [[(3,6),(1,6),(0,5),(0,1),(1,0),(3,0),(4,1),(4,2),(3,3),(0,3)]],
 '7': [[(0,6),(4,6),(1.5,0)]],
 '8': [[(1,3),(0,4),(0,5),(1,6),(3,6),(4,5),(4,4),(3,3),(1,3),(0,2),(0,1),(1,0),(3,0),(4,1),(4,2),(3,3)]],
 '9': [[(4,3),(1,3),(0,4),(0,5),(1,6),(3,6),(4,5),(4,1),(3,0),(1,0)]],
 '-': [[(0.5,3),(3.5,3)]], '.': [[(1.8,0),(2.2,0),(2.2,0.4),(1.8,0.4),(1.8,0)]], '=': [[(0.5,2),(3.5,2)],[(0.5,4),(3.5,4)]],
 '+': [[(0.5,3),(3.5,3)],[(2,1.5),(2,4.5)]], '!': [[(2,6),(2,2)],[(2,0.5),(2,0)]], '?': [[(0,5),(1,6),(3,6),(4,5),(4,4),(2,2.5),(2,1.5)],[(2,0.5),(2,0)]],
 ' ': [],
}

def text(s, x=-0.9, y=0.0, size=0.3, spacing=1.3):
    """Polylines for a string: `size` is the glyph height in DAC units (the axis is -1..1)."""
    k = size / 6.0
    out = []
    for i, ch in enumerate(s.upper()):
        for pl in FONT.get(ch, FONT['?']):
            out.append([(x + (i * 4 * spacing + px) * k, y + py * k) for px, py in pl])
    return out

def centred_text(s, y=0.0, size=0.3, spacing=1.3):
    w = (len(s) * 4 * spacing - (spacing - 1) * 4) * size / 6.0
    return text(s, x=-w / 2, y=y - size / 2, size=size, spacing=spacing)

def cube(angle, size=0.5, cx=0.0, cy=0.0):
    """A wireframe cube turned about two axes, projected with a little perspective."""
    v = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
    ca, sa, cb, sb = np.cos(angle), np.sin(angle), np.cos(0.7 * angle), np.sin(0.7 * angle)
    ry = np.array([[ca, 0, sa], [0, 1, 0], [-sa, 0, ca]]); rx = np.array([[1, 0, 0], [0, cb, -sb], [0, sb, cb]])
    p = v @ ry.T @ rx.T
    d = 1.0 / (3.5 - p[:, 2])
    pts = np.stack([cx + size * p[:, 0] * d * 3, cy + size * p[:, 1] * d * 3], 1)
    edges = [(a, b) for a in range(8) for b in range(a + 1, 8) if bin(a ^ b).count('1') == 1]
    return [[tuple(pts[a]), tuple(pts[b])] for a, b in edges]

def heart(n=200, size=0.8):
    t = np.linspace(0, 2 * np.pi, n)
    x = 16 * np.sin(t) ** 3; y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
    return [list(zip(size * x / 17, size * y / 17))]

def display_list(polylines, step=0.01, settle=2):
    """Polylines -> (N, 3) array of x, y, beam: points `step` apart along each stroke; the beam is off while
    the spot jumps between strokes and `settle` points are spent at the start of each (the DAC's 12 MHz
    and the cable make the jump take a few points at 1 M points/s)."""
    pts = []
    for pl in polylines:
        pl = np.asarray(pl, float)
        if len(pl) == 0: continue
        for _ in range(settle): pts.append((pl[0, 0], pl[0, 1], 0))
        for (x0, y0), (x1, y1) in zip(pl[:-1], pl[1:]):
            n = max(1, int(np.hypot(x1 - x0, y1 - y0) / step))
            for i in range(n + 1):
                f = i / n; pts.append((x0 + f * (x1 - x0), y0 + f * (y1 - y0), 1))
    return np.array(pts) if pts else np.zeros((0, 3))

def to_codes(dl):
    """-1..1 -> the player's 12-bit offset-binary codes (the DAC's top 12 bits) plus the beam bit."""
    c = np.clip(np.round(dl[:, :2] * 2047 + 2048), 0, 4095).astype(int)
    return c[:, 0], c[:, 1], dl[:, 2].astype(int)

if __name__ == "__main__":
    dl = display_list(centred_text("HMC", size=0.8) + cube(0.5, size=0.25, cx=0.7, cy=-0.7))
    print(len(dl), "points;", dl[:, 2].sum(), "lit")
