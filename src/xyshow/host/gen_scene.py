#!/usr/bin/env python3
"""Writes what the vector engine's memories start with, so the board shows the seal with no PC attached:
  <rtl>/scene_xy.hex   8192 x 36 bits {beam, group[1:0], cull, x[15:0], y[15:0]}   (x, y Q2.14)
  <rtl>/scene_z.hex    8192 x 18 bits {group[3:2], z[15:0]}
  <rtl>/persp.hex      512 x 16: codes per unit = round(2047 * P / (P + z)) for z = -2 .. 2 (index = (z + 2) in Q2.14 >> 7)
  <rtl>/sincos.hex     1024 x 16: round(16383 * sin(2 pi i / 1024)) (cos = sin(i + 256))
  <rtl>/scene_layout.vh  the ranges (start, count) of the body, the 3D globe, every finale object, the free region
  host/scene_layout[_icepi].json  the same for the host
Vertices: each stroke's first vertex has beam 0 (the jump), the rest beam 1.  Each object's strokes are put in drawing
order first (order_strokes): with no blanking on the scope every jump between strokes is a streak, and in the order the
objects were made the jumps added up to as much as the drawing (the seal) or four times it (the telescope).
Called by make_show.py."""
import os, json, math, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import scene, objects
Q = 1 << 14
N = 8192
def q14(v, sc=1.0): return int(max(-32768, min(32767, round(v * sc * Q))))

def order_strokes(polys_groups, view=None):
    """The strokes in drawing order: each group's strokes together (a change of group costs the engine a matrix fetch),
    within a group each next stroke the one with an end nearest where the last ended (run backwards if its far end is
    the nearer), and when a group is done, the group with the nearest stroke end next; every stroke is tried as the first,
    both ways round, and the order with the least jump length kept.  A stroke that starts exactly where the last ended is
    joined to it, one jump fewer.  Distances: `view(points, group)` gives the points' screen positions at K moments of the
    object's motion, (M, K, 2), and a distance is the mean over them (the drone moves over the dish, the planets round
    the sun); without it, the object's own 3D coordinates (a group is rigid, so these are its screen distances, near
    enough).  (Until 2026-11-09 the groups came in the order the object was made, and each group's tour started at its
    first stroke.)  The make_show.py model draws from the same order."""
    strokes = [(np.asarray(pl, float), g) for pl, g in polys_groups if len(pl)]
    n = len(strokes)
    if n == 0: return []
    if view is None: view = lambda P, g: np.asarray(P, float)[:, None, :]
    ends = np.stack([view(np.array([pl[0], pl[-1]]), g) for pl, g in strokes])      # (n, 2 ends, K, D)
    grp = np.array([g for _, g in strokes])
    def tour(s, rev):
        used = np.zeros(n, bool); used[s] = True; order = [(s, rev)]; cur = ends[s, 0 if rev else 1]; g = grp[s]; cost = 0.0
        for _ in range(n - 1):
            cand = ~used & (grp == g)
            if not cand.any(): cand = ~used
            idx = np.flatnonzero(cand)
            d = np.linalg.norm(ends[idx] - cur, axis=-1).mean(-1)                      # (m, 2): to each candidate's start, end
            j, e = np.unravel_index(int(np.argmin(d)), d.shape); k = int(idx[j]); r = bool(e == 1)
            cost += float(d[j, e]); used[k] = True; order.append((k, r)); cur = ends[k, 0 if r else 1]; g = grp[k]
        return cost, order
    _, order = min((tour(s, r) for s in range(n) for r in (False, True)), key=lambda c: c[0])
    out = []
    for k, r in order:
        p, g = strokes[k]; p = p[::-1] if r else p
        if out and out[-1][1] == g and np.linalg.norm(p[0] - out[-1][0][-1]) < 1e-9: out[-1] = (np.vstack([out[-1][0], p[1:]]), g)
        else: out.append((p, g))
    return out

def write_scene(rtl, scale, p_view, objs, ordered=None):
    """objs: the finale objects' names (objects.OBJECTS); scale: the screen's, in the perspective table (the vertices are
    the same for both targets); ordered: {name: strokes in drawing order} (make_show.scene_orders()), else order_strokes
    without the motion.  Returns the layout {name: (start, count)}."""
    ents, layout = [], {}
    def add(name, polys_groups, cull):
        """cull: 0 or 1 for the whole object, or the set of its groups whose vertices carry the cull bit"""
        start = len(ents)
        for pl, g in (ordered[name] if ordered and name in ordered else order_strokes(polys_groups)):
            c = (1 if g in cull else 0) if isinstance(cull, (set, frozenset)) else cull
            for i, p in enumerate(pl):
                ents.append((1 if i else 0, g, c, q14(p[0]), q14(p[1]), q14(p[2])))
        layout[name] = (start, len(ents) - start)
    body = scene.split_seal(scene.load_seal()); globe, limb = scene.globe_scene()
    add("body", [(p, 0) for p in body + [limb]], 0); add("globe3d", [(p, 1) for p in globe], 1)
    for obj in dict.fromkeys(o for o in objs if o):
        add(obj, objects.OBJECTS[obj](), objects.CULL.get(obj, set()))
    assert len(ents) <= N, ("the scene memory holds %d vertices; this needs %d" % (N, len(ents)))
    layout["free"] = (len(ents), N - len(ents))
    pad = [(0, 0, 0, 0, 0, 0)] * (N - len(ents))
    with open(os.path.join(rtl, "scene_xy.hex"), "w") as f:
        for b, g, c, x, y, z in ents + pad: f.write("%09x\n" % ((b << 35) | ((g & 3) << 33) | (c << 32) | ((x & 0xffff) << 16) | (y & 0xffff)))
    with open(os.path.join(rtl, "scene_z.hex"), "w") as f:
        for b, g, c, x, y, z in ents + pad: f.write("%05x\n" % (((g >> 2) << 16) | (z & 0xffff)))
    with open(os.path.join(rtl, "persp.hex"), "w") as f:
        for i in range(512):
            z = (i * 128 - 32768) / Q
            f.write("%04x\n" % int(round(2047 * scale * p_view / (p_view + z))))
    with open(os.path.join(rtl, "sincos.hex"), "w") as f:
        for i in range(1024): f.write("%04x\n" % (int(round(16383 * math.sin(2 * math.pi * i / 1024))) & 0xffff))
    with open(os.path.join(rtl, "scene_layout.vh"), "w") as f:
        f.write("// generated by host/gen_scene.py: the scene memory's layout\n")
        for k, (s, n) in layout.items(): f.write("localparam [12:0] L_%s_START = 13'd%d, L_%s_COUNT = 13'd%d;\n" % (k.upper(), s, k.upper(), n))
        f.write("localparam signed [15:0] GLOBE_CX = 16'sd%d, GLOBE_CY = 16'sd%d, GLOBE_CZ = 16'sd0;\n" % (q14(scene.GLOBE_C[0]), q14(scene.GLOBE_C[1])))
        f.write("localparam signed [15:0] TILT_S = 16'sd%d, TILT_C = 16'sd%d;\n" % (q14(math.sin(scene.TILT)), q14(math.cos(scene.TILT))))
    json.dump({k: list(v) for k, v in layout.items()}, open(os.path.join(HERE, "scene_layout_icepi.json" if scale != 1.0 else "scene_layout.json"), "w"))
    return layout

if __name__ == "__main__":
    print("run through make_show.py, which supplies the finale list")
