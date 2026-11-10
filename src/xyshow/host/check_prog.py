#!/usr/bin/env python3
"""The animator's sections for the finales added 2026-11-09 against their float models (proposals.py's mats(t), and
the dish's message here): the program run bit for bit (gen_matrix_prog.run) with the phases at their rates from a
start of 0 (the staggered sawtooths at their power-up offsets, the spinner's phase from its ramp), every group's R and
t compared at many moments.  Prints the largest difference per finale; fails over TOL.  The sine table's 1024 steps a
turn put up to 0.006 into a matrix element of a turning view, and the pendulum wave's angle addition multiplies its
phase's step by up to 27 (its swing is updated 43 times a second): 0.04 is that, and a section built wrong is off by
0.1 or more."""
import os, sys, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, ".."))
import make_show as ms, gen_matrix_prog as gmp, proposals as PR, objects
TOL = 0.04
def phases_at(t, kind):
    w, p0 = ms.rates(); ph = []
    for i in range(32):
        base = p0[i] if (ms.PH.get("u0", -1) <= i <= ms.PH.get("u4", -1)) else 0      # the sawtooths keep their stagger
        ph.append((base + int(round(w[i] * t * 1000))) & 0xffffffff)
    if ms.KINDS[kind].get("ramp"): ph[ms.PH["sp"]] = ms.ramp_phase(t * 1000)
    return ph
def dish_model(t):
    dc = objects.dish_constants(1.0 / ms.PWAVE_CYCLE_S); u = (t / ms.PWAVE_CYCLE_S) % 1.0
    V = PR.rx(math.radians(ms.PHYS_VIEW_TILT_DEG)) @ PR.ry(math.radians(ms.PHYS_VIEW_SWING_DEG) * math.sin(2 * math.pi * 0.08 * t))
    m = {4: (V, np.zeros(3))}
    for n, el in enumerate(dc["elements"]):
        a = u - el["d"]; R = np.zeros((3, 3)); R[:2, :2] = V[:2, :2]; R[2, 2] = a * (el["d"] + dc["w"] - u)
        m[5 + n] = (R, V @ np.array([dc["x_rim"] + dc["v"] * a, 0, 0]))
    return m
def check(kinds=("ligo", "pcb", "spinner", "top", "pwave", "generator", "governor", "boom", "tek", "dish"), n=60):
    P = gmp.build(ms.anim_consts(1.0)); v0 = gmp.regs_init(P); bad = False
    print("program: %d instructions in all sections, %d constants" % (len(P.prog), P.nk))
    for kind in kinds:
        secs = dict(ms.FINALES).get(kind, 7.0); worst = (0.0, None)
        model = dish_model if kind == "dish" else PR.PROPOSALS[kind]["mats"]
        for i in range(n):
            t = secs * (i + 0.37) / n
            v = list(v0); gmp.load_phases(v, phases_at(t, kind)); gmp.run(v, P.prog, P.sections["seal"]); gmp.run(v, P.prog, P.sections[ms.KINDS[kind]["sec"]])
            got = gmp.matrices(v)
            for g, (R, tt) in model(t).items():
                if kind == "dish" and g >= 5 and R[2, 2] < 0:                        # a packet not in flight: hidden, whatever its place
                    if got[g][0][2, 2] >= 0: worst = max(worst, (1.0, (t, g)))
                    continue
                e = max(np.abs(got[g][0] - R).max(), np.abs(got[g][1] - tt).max())
                if e > worst[0]: worst = (e, (t, g))
        ok = worst[0] < TOL; bad |= not ok
        print("%-10s %4d instructions  largest difference %.5f %s%s" % (kind, len(P.prog[P.sections[ms.KINDS[kind]["sec"]]:]) and
              (sorted(P.sections.values()) + [len(P.prog)])[sorted(P.sections.values()).index(P.sections[ms.KINDS[kind]["sec"]]) + 1] - P.sections[ms.KINDS[kind]["sec"]],
              worst[0], "" if ok else "  FAIL at t %.2f s, group %d" % worst[1], ""))
    return not bad
if __name__ == "__main__":
    sys.exit(0 if check(sys.argv[1:] or ("ligo", "pcb", "spinner", "top", "pwave", "generator", "governor", "boom", "tek", "dish")) else 1)
