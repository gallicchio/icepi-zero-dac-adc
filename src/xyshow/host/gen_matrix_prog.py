#!/usr/bin/env python3
"""The animator's microprogram, its register file's initial contents, and a bit-exact reference model.

The matrix unit (rtl/matrix_unit.v) holds 1024 registers of Q2.14 (16 bits, +/-1.9999) in a block RAM and
one multiplier; the program (up to 4096 instructions) is in another.  An instruction is {op[2:0], dst[9:0], a[9:0], b[9:0]}: 1 MUL dst = (a b) >> 14; 2 MAC dst += (a b) >> 14;
3 MSB dst -= (a b) >> 14; 4 SIN dst = sin(a) and 5 COS dst = cos(a), a in turns (its bits [13:4] index the 1024-entry
table, so whole turns are dropped); 0 END.  Products are floored, sums saturated, so run() below is the gateware bit for bit.

Registers:  0-159 and 768-1023 constants (0 ZERO 1 ONE 2 NEG1 3 TILT_S 4 TILT_C (the satellites' Earth's tilt) 5 GCX 6 GCY
7 GCZ, the rest named below) | 160 + 2k, 161 + 2k: the sine and cosine of phase k (k < 32), 224 + k: phase k as turns in
[0, 1), both written by the hardware at every start | 256-511 working registers, each section's own (a section reads
no other's) | 512 + 16 g: group g's matrix, R row-major then t (12 used of 16).
The engine reads group g's matrix there; the host may write any register.

The program is in sections, one per animation, each ending in END; the sequencer gives the start address (PC_* in
matrix_prog.vh): the seal's section in modes 1, 2 and 4, a finale's in mode 3.  build() makes every section (the
finales in FINALES and the others in KINDS); select() keeps the seal's and the show's, end to end, for the
gateware (4096 instructions at most); the movie's model runs the whole program, the same instructions on the same
registers.  A section writes R and t of every
group it draws.  Phases (32, a turn = 2^32): a b s (the seal's axis, turn, the globe's spin) la lb lc (the
Lorenz view) ta tb tc (a tumble) ds dn (DNA's spin and nod) gs gc gp (the gears' sun, carrier, planet spin)
av aw (the arm's view and wave) pv em (the physics view, the EM wave's wt) u0-u4 (wavefronts and light dashes, a sawtooth each)
o1 o2 o3 (the satellites) dr ps (the drone's sweep and its propellers' spin) sl (a slow sawtooth: the dish's message; in the
transcription and translation, the polymerase and the ribosome) pc (the circuit board's charge) sp (the spinner: its rate ramps, show_seq.v) pw (the
pendulum wave: a turn in 24 s, the twelve pendulums at 16-27 times it).
Writes matrix_prog.hex (4096 x 36), regs_init.hex (1024 x 18), matrix_prog.vh (the sections' addresses), matrix_prog.json."""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import objects, scene
Q = 1 << 14
NPH = 32
PH = dict(a=0, b=1, pc=2, s=3, la=4, lb=5, lc=6, ta=7, tb=8, tc=9, ds=10, dn=11, gs=12, gc=13, gp=14, sp=15, av=16, aw=17, pv=18, em=19,
          u0=20, u1=21, u2=22, u3=23, u4=24, pw=25, o1=26, o2=27, o3=28, dr=29, ps=30, sl=31)
SIN_BASE, PHV_BASE, WORK_BASE, MAT_BASE, K2_BASE = 160, 224, 256, 512, 768
PROG_MAX = 4096
END, MUL, MAC, MSB, SIN, COS = 0, 1, 2, 3, 4, 5
SINE = [int(round(16383 * math.sin(2 * math.pi * i / 1024))) for i in range(1024)]
def q14(x):
    v = int(round(x * Q)); assert -32768 <= v <= 32767, ("constant out of Q2.14", x); return v
def S(ph): return SIN_BASE + 2 * PH[ph]
def C(ph): return SIN_BASE + 2 * PH[ph] + 1
def PV(ph): return PHV_BASE + PH[ph]
def R(g): return [MAT_BASE + 16 * g + j for j in range(9)]
def T(g): return [MAT_BASE + 16 * g + 9 + j for j in range(3)]

class Program:
    def __init__(self, consts):
        self.k = {}; self.kv = {}; self.nk = 0; self.nw = WORK_BASE; self.prog = []; self.sections = {}; self.sec = None; self.written = set()
        for name, val in (("ZERO", 0), ("ONE", 1.0), ("NEG1", -1.0), ("TS", math.sin(scene.TILT)), ("TC", math.cos(scene.TILT)),
                          ("GCX", scene.GLOBE_C[0] * consts["seal_scale"]), ("GCY", scene.GLOBE_C[1] * consts["seal_scale"]), ("GCZ", 0.0)):
            self.K(name, val)
    def K(self, name, val):
        """A constant's register (allocated on first use)."""
        if name not in self.k:
            r = self.nk if self.nk < SIN_BASE else K2_BASE + self.nk - SIN_BASE
            assert r < 1024, "too many constants"; self.k[name] = r; self.kv[name] = q14(val); self.nk += 1
        return self.k[name]
    def KV(self, val):
        """a constant's register by its value (shared by every use of the same value)"""
        return self.k["ZERO"] if val == 0 else self.k["ONE"] if val == 1 else self.k["NEG1"] if val == -1 else self.K("v%.12g" % val, val)
    def W(self, n=1):
        """n fresh working registers."""
        r = list(range(self.nw, self.nw + n)); self.nw += n; assert self.nw <= MAT_BASE; return r if n > 1 else r[0]
    def op(self, o, d, a, b=0): self.prog.append((o, d, a, b)); self.written.add(d)
    def MUL(self, d, a, b): self.op(MUL, d, a, b)
    def MAC(self, d, a, b): self.op(MAC, d, a, b)
    def MSB(self, d, a, b): self.op(MSB, d, a, b)
    def SIN(self, d, a): self.op(SIN, d, a)
    def COS(self, d, a): self.op(COS, d, a)
    def begin(self, name, groups): self.sections[name] = len(self.prog); self.sec = (name, groups); self.written = set(); self.nw = WORK_BASE
    def end(self, keep=()):
        """END; first every element of the section's groups' matrices that it did not write is zeroed (a group's
        translation is often 0; another section may have moved it)."""
        for g in self.sec[1]:
            for r in R(g) + T(g):
                if r not in self.written and r not in keep: self.MUL(r, self.K("ZERO", 0), self.K("ZERO", 0))
        self.op(END, 0, 0, 0)
    # ---- the matrix helpers (dst must not alias src) ----
    def euler(self, dst, s1, c1, s2, c2, s3, c3):
        """dst = Rz(1) Ry(2) Rx(3)"""
        t0, t1 = self.W(2); K = self.k
        self.MUL(t0, c1, s2); self.MUL(t1, s1, s2)
        self.MUL(dst[0], c1, c2)
        self.MUL(dst[1], t0, s3); self.MSB(dst[1], s1, c3)
        self.MUL(dst[2], t0, c3); self.MAC(dst[2], s1, s3)
        self.MUL(dst[3], s1, c2)
        self.MUL(dst[4], t1, s3); self.MAC(dst[4], c1, c3)
        self.MUL(dst[5], t1, c3); self.MSB(dst[5], c1, s3)
        self.MUL(dst[6], K["NEG1"], s2)
        self.MUL(dst[7], c2, s3)
        self.MUL(dst[8], c2, c3)
    def rx_ry(self, dst, sa, ca, sb, cb):
        """dst = Rx(a) Ry(b) = [[cb, 0, sb], [sa sb, ca, -sa cb], [-ca sb, sa, ca cb]]"""
        K = self.k
        self.MUL(dst[0], K["ONE"], cb); self.MUL(dst[1], K["ONE"], K["ZERO"]); self.MUL(dst[2], K["ONE"], sb)
        self.MUL(dst[3], sa, sb); self.MUL(dst[4], K["ONE"], ca); self.MUL(dst[5], K["NEG1"], sa); self.MUL(dst[5], dst[5], cb)
        self.MUL(dst[6], K["NEG1"], ca); self.MUL(dst[6], dst[6], sb); self.MUL(dst[7], K["ONE"], sa); self.MUL(dst[8], ca, cb)
    def matmul(self, dst, A, B):
        for i in range(3):
            for j in range(3):
                self.MUL(dst[3 * i + j], A[3 * i], B[j]); self.MAC(dst[3 * i + j], A[3 * i + 1], B[3 + j]); self.MAC(dst[3 * i + j], A[3 * i + 2], B[6 + j])
    def post_z(self, dst, M, s, c):
        """dst = M Rz: col0 = M0 c + M1 s, col1 = M1 c - M0 s, col2 = M2"""
        for i in range(3):
            self.MUL(dst[3 * i], M[3 * i], c); self.MAC(dst[3 * i], M[3 * i + 1], s)
            self.MUL(dst[3 * i + 1], M[3 * i + 1], c); self.MSB(dst[3 * i + 1], M[3 * i], s)
            self.MUL(dst[3 * i + 2], self.k["ONE"], M[3 * i + 2])
    def post_y(self, dst, M, s, c):
        """dst = M Ry: col0 = M0 c - M2 s, col1 = M1, col2 = M0 s + M2 c"""
        for i in range(3):
            self.MUL(dst[3 * i], M[3 * i], c); self.MSB(dst[3 * i], M[3 * i + 2], s)
            self.MUL(dst[3 * i + 1], self.k["ONE"], M[3 * i + 1])
            self.MUL(dst[3 * i + 2], M[3 * i], s); self.MAC(dst[3 * i + 2], M[3 * i + 2], c)
    def post_x(self, dst, M, s, c):
        """dst = M Rx: col0 = M0, col1 = M1 c + M2 s, col2 = M2 c - M1 s"""
        for i in range(3):
            self.MUL(dst[3 * i], self.k["ONE"], M[3 * i])
            self.MUL(dst[3 * i + 1], M[3 * i + 1], c); self.MAC(dst[3 * i + 1], M[3 * i + 2], s)
            self.MUL(dst[3 * i + 2], M[3 * i + 2], c); self.MSB(dst[3 * i + 2], M[3 * i + 1], s)
    def scale(self, dst, M, s):
        for j in range(9): self.MUL(dst[j], M[j], s)
    def copy(self, dst, src):
        for d, s in zip(dst, src): self.MUL(d, self.k["ONE"], s)
    def col_times(self, dst, M, col, x, add=False):
        """dst (3) = (+=) M's column col times the register x"""
        for i in range(3): (self.MAC if add else self.MUL)(dst[i], M[3 * i + col], x)
    def angle(self, off, amp, src, neg=False):
        """a fresh register = off + amp * src (turns), then its sine and cosine registers"""
        th, s, c = self.W(3); K = self.k
        self.MUL(th, K["ONE"], off); (self.MSB if neg else self.MAC)(th, amp, src); self.SIN(s, th); self.COS(c, th)
        return s, c

def build(consts):
    """The whole program.  consts: seal_scale, dna_nod, arm_view_tilt, arm_off, arm_joints, phys_view_tilt, phys_view_swing (see make_show.py)."""
    P = Program(consts); K = P.K; k = P.k
    # ---- the seal: group 0 = Rz(a) Ry(b) Rz(-a) (a turn by b about an in-plane axis at angle a), group 1 = R0 Rx(tilt) Ry(s)
    # at the globe's centre (tilt 0: R0 Ry(s), upright) ----
    P.begin("seal", [0, 1])
    M = P.W(9); sa, ca, sb, cb = S("a"), C("a"), S("b"), C("b")          # M = Rz(a) Ry(b) = [[ca cb, -sa, ca sb], [sa cb, ca, sa sb], [-sb, 0, cb]]
    P.MUL(M[0], ca, cb); P.MUL(M[1], k["NEG1"], sa); P.MUL(M[2], ca, sb)
    P.MUL(M[3], sa, cb); P.MUL(M[4], k["ONE"], ca); P.MUL(M[5], sa, sb)
    P.MUL(M[6], k["NEG1"], sb); P.MUL(M[7], k["ZERO"], k["ZERO"]); P.MUL(M[8], k["ONE"], cb)
    R0 = R(0)
    for i in range(3):
        P.MUL(R0[3 * i], M[3 * i], C("a")); P.MSB(R0[3 * i], M[3 * i + 1], S("a"))
        P.MUL(R0[3 * i + 1], M[3 * i], S("a")); P.MAC(R0[3 * i + 1], M[3 * i + 1], C("a"))
        P.MUL(R0[3 * i + 2], k["ONE"], M[3 * i + 2])
    if scene.SEAL_GLOBE_TILT:
        Tm = P.W(9); P.rx_ry(Tm, K("GTS", math.sin(scene.SEAL_GLOBE_TILT)), K("GTC", math.cos(scene.SEAL_GLOBE_TILT)), S("s"), C("s"))
        P.matmul(R(1), R0, Tm)
    else: P.post_y(R(1), R0, S("s"), C("s"))
    gc = [k["GCX"], k["GCY"], k["GCZ"]]
    for i in range(3):
        P.MUL(T(1)[i], k["ONE"], T(0)[i])
        for j in range(3): P.MAC(T(1)[i], R0[3 * i + j], gc[j])
    P.end(keep=T(0))                                           # t0 stays the host's (0 unless written)
    # ---- the Lorenz view: group 2 ----
    P.begin("lorenz", [2]); P.euler(R(2), S("la"), C("la"), S("lb"), C("lb"), S("lc"), C("lc")); P.end()
    # ---- a tumble: group 4 ----
    P.begin("tumble", [4]); P.euler(R(4), S("ta"), C("ta"), S("tb"), C("tb"), S("tc"), C("tc")); P.end()
    # ---- DNA: group 5 spins on its axis and nods ----
    P.begin("dna", [5])
    s, c = P.angle(k["ZERO"], K("DNA_NOD", consts["dna_nod"]), S("dn")); P.rx_ry(R(5), s, c, S("ds"), C("ds")); P.end()
    # ---- the gears, flat: the sun turns, the planets go round (the carrier) and spin, the ring gear (10) stays ----
    P.begin("gears", [6, 7, 8, 9, 10])
    gcst = objects.gear_constants()
    V = [k["ONE"], k["ZERO"], k["ZERO"], k["ZERO"], k["ONE"], k["ZERO"], k["ZERO"], k["ZERO"], k["ONE"]]   # the identity, as constants
    P.copy(R(10), V)
    P.post_z(R(6), V, S("gs"), C("gs"))
    for i in range(3):
        if i: K("K3_%d" % i, i / 3)
        ap, sp, cp, ac, sc, cc, xk, yk = P.W(8)
        P.MUL(ap, k["ONE"], PV("gp")); P.MUL(ac, k["ONE"], PV("gc"))
        if i: P.MAC(ap, k["ONE"], k["K3_%d" % i]); P.MAC(ac, k["ONE"], k["K3_%d" % i])
        P.SIN(sp, ap); P.COS(cp, ap); P.SIN(sc, ac); P.COS(cc, ac)
        P.post_z(R(7 + i), V, sp, cp)
        P.MUL(xk, K("GEAR_RC", gcst["carrier_r"]), cc); P.MUL(yk, k["GEAR_RC"], sc)
        P.col_times(T(7 + i), V, 0, xk); P.col_times(T(7 + i), V, 1, yk, add=True)
    P.end()
    # ---- the arm: a view turning about y; five joints on the wave phase ----
    P.begin("arm", [11, 12, 13, 14, 15])
    A = objects.ARM; V = R(11)
    P.rx_ry(V, K("ARM_VTS", math.sin(2 * math.pi * consts["arm_view_tilt"])), K("ARM_VTC", math.cos(2 * math.pi * consts["arm_view_tilt"])), S("av"), C("av"))
    P.MUL(T(11)[0], k["ONE"], K("ARM_OX", consts["arm_off"][0])); P.MUL(T(11)[1], k["ONE"], K("ARM_OY", consts["arm_off"][1]))
    s1, c1 = S("aw"), C("aw"); s2, c2 = P.W(2)
    P.MUL(s2, s1, c1); P.MAC(s2, s1, c1); P.MUL(c2, c1, c1); P.MSB(c2, s1, s1)           # the double angle
    src = {"sin": s1, "cos": c1, "sin2": s2, "cos2": c2}
    J = []
    for n, (off, amp, which) in enumerate(consts["arm_joints"]):
        J.append(P.angle(K("ARM_J%dO" % n, off), K("ARM_J%dA" % n, abs(amp)), src[which], neg=amp < 0))
    P.post_y(R(12), V, *J[0]); P.copy(T(12), T(11))
    P.post_z(R(13), R(12), *J[1]); P.copy(T(13), T(12)); P.col_times(T(13), R(12), 1, K("ARM_BH", A["base_h"]), add=True)
    P.post_z(R(14), R(13), *J[2]); P.copy(T(14), T(13)); P.col_times(T(14), R(13), 0, K("ARM_L1", A["l1"]), add=True)
    tmp = P.W(9); P.post_z(tmp, R(14), *J[3]); P.post_x(R(15), tmp, *J[4]); P.copy(T(15), T(14)); P.col_times(T(15), R(14), 0, K("ARM_L2", A["l2"]), add=True)
    P.end()
    # ---- the physics view, shared: Rx(tilt) Ry(swing sin(pv)), a viewpoint that swings about the side view and comes back ----
    def phys_view(dst):
        s, c = P.angle(k["ZERO"], K("PHYS_SWING", consts["phys_view_swing"]), S("pv"))
        P.rx_ry(dst, K("PHYS_VTS", math.sin(2 * math.pi * consts["phys_view_tilt"])), K("PHYS_VTC", math.cos(2 * math.pi * consts["phys_view_tilt"])), s, c)
    # ---- the EM wave: E (group 5) y = sin(kx - wt) from the stored (x, cos kx, sin kx), B (group 6) the same into z ----
    P.begin("em", [4, 5, 6])
    V = R(4); phys_view(V); ns = P.W(); P.MUL(ns, k["NEG1"], S("em"))
    for i in range(3):
        P.MUL(R(5)[3 * i], k["ONE"], V[3 * i]); P.MUL(R(5)[3 * i + 1], V[3 * i + 1], C("em")); P.MUL(R(5)[3 * i + 2], V[3 * i + 1], ns)
        P.MUL(R(6)[3 * i], k["ONE"], V[3 * i]); P.MUL(R(6)[3 * i + 1], V[3 * i + 2], C("em")); P.MUL(R(6)[3 * i + 2], V[3 * i + 2], ns)
    P.end()
    # ---- the telescope: the light's dashes slide in along x (groups 5-9), then slide to the focus (10-14, scaled about it) ----
    sc = objects.scope_constants(); nf = objects.SCOPE["n_fronts"]
    P.begin("scope", [4] + list(range(5, 5 + nf)) + list(range(10, 10 + nf)))
    V = R(4); phys_view(V)
    for n in range(nf):
        u = PV("u%d" % n); xk, sk = P.W(2)
        P.MUL(xk, k["ONE"], K("SCOPE_X0", sc["x_out0"])); P.MAC(xk, K("SCOPE_L", sc["l_out"]), u)
        P.copy(R(5 + n), V); P.col_times(T(5 + n), V, 0, xk)
        P.MUL(sk, k["ONE"], k["ONE"]); P.MSB(sk, k["ONE"], u)
        P.scale(R(10 + n), V, sk); P.col_times(T(10 + n), V, 0, K("SCOPE_XF", sc["x_focus"]))
    P.end()
    # ---- the dish: its message, HMC in Morse, one packet a group (5-14), each drawn only in flight (objects.dish) ----
    dc = objects.dish_constants(consts["dish_per_s"]); els = dc["elements"]; nv = int(math.ceil(dc["v"] / 1.9))
    P.begin("dish", [4] + list(range(5, 5 + len(els))))
    V = R(4); phys_view(V); u = PV("pw")                     # the pendulum wave's phase, put to zero at the finale's start
    for n, el in enumerate(els):
        g = 5 + n; a, b, px = P.W(3)
        P.MUL(a, k["ONE"], u); P.MSB(a, k["ONE"], P.KV(el["d"]))                                  # u - d
        P.MUL(b, k["ONE"], P.KV(el["d"] + dc["w"])); P.MSB(b, k["ONE"], u)                        # d + w - u
        P.MUL(R(g)[8], a, b)                                                                      # >= 0 only in flight: the cull
        P.MUL(px, k["ONE"], P.KV(dc["x_rim"]))
        for _ in range(nv): P.MAC(px, a, P.KV(dc["v"] / nv))                                    # x_rim + v a, v over 2 in parts
        for j_ in (0, 1, 3, 4): P.MUL(R(g)[j_], k["ONE"], V[j_])                                   # x, y as V; z only the cull's
        P.col_times(T(g), V, 0, px)
    P.end()
    # ---- polarization: the wave vertical (5), circular after the quarter-wave plate (6) ----
    P.begin("pol", [4, 5, 6])
    V = R(4); phys_view(V); ns = P.W(); P.MUL(ns, k["NEG1"], S("em")); c = C("em")
    for i in range(3):
        P.MUL(R(5)[3 * i], k["ONE"], V[3 * i]); P.MUL(R(5)[3 * i + 1], V[3 * i + 1], ns); P.MUL(R(5)[3 * i + 2], V[3 * i + 1], c)
        P.MUL(R(6)[3 * i], k["ONE"], V[3 * i])
        P.MUL(R(6)[3 * i + 1], V[3 * i + 1], ns); P.MAC(R(6)[3 * i + 1], V[3 * i + 2], c)
        P.MUL(R(6)[3 * i + 2], V[3 * i + 1], c); P.MAC(R(6)[3 * i + 2], V[3 * i + 2], S("em"))
    P.end()
    # ---- a dash sliding from A to B as a sawtooth phase goes round: R = V, t = V (A + u (B - A)) ----
    def slide(g, V, A, B, u, tag):
        px, py = P.W(2)
        P.MUL(px, k["ONE"], K("%s_AX" % tag, A[0])); P.MAC(px, K("%s_DX" % tag, B[0] - A[0]), u)
        P.MUL(py, k["ONE"], K("%s_AY" % tag, A[1])); P.MAC(py, K("%s_DY" % tag, B[1] - A[1]), u)
        P.copy(R(g), V); P.col_times(T(g), V, 0, px); P.col_times(T(g), V, 1, py, add=True)
    # ---- the Sagnac source: the pump's dashes (5), the loop's both ways (6-11), the pairs' (12, 13) ----
    legs = objects.sagnac_legs()
    P.begin("sagnac", [4] + sorted(legs))
    V = R(4); phys_view(V)
    for g, (A, B, pair) in legs.items(): slide(g, V, A, B, PV("u0" if g == 5 else "u1" if g < 12 else "u2"), "SG%d" % g)
    P.end()
    # ---- the drone: the body (5) on an arc over the dish, its angle a sine of the sweep phase; the propellers (6-11) spin ----
    dc = objects.drone_constants()
    P.begin("drone", [4, 5] + list(range(6, 12)))
    V = R(4); phys_view(V)
    sa, ca = P.angle(k["ZERO"], K("DR_SWEEP", dc["sweep"]), S("dr"))
    px, py = P.W(2); P.MUL(px, K("DR_R", dc["arc_r"]), sa); P.MUL(py, k["ONE"], K("DR_Y0", dc["y0"])); P.MAC(py, k["DR_R"], ca)
    P.copy(R(5), V); P.col_times(T(5), V, 0, px); P.col_times(T(5), V, 1, py, add=True)
    nps = P.W(); P.MUL(nps, k["NEG1"], S("ps"))
    for n, (ax, az) in enumerate(dc["arms"]):
        P.post_y(R(6 + n), V, S("ps") if n % 2 == 0 else nps, C("ps"))
        P.copy(T(6 + n), T(5)); P.col_times(T(6 + n), V, 0, K("DR_A%dX" % n, ax), add=True); P.col_times(T(6 + n), V, 2, K("DR_A%dZ" % n, az), add=True)
        P.col_times(T(6 + n), V, 1, K("DR_PY", dc["prop_y"]), add=True)
    P.end()
    # ---- replication: the fork (4) with four nucleotides (5-8) sliding in to the new strands ----
    paths = objects.replication_paths()
    P.begin("replicate", [4] + sorted(paths))
    V = R(4); phys_view(V)
    for n, (g, (A, B)) in enumerate(sorted(paths.items())): slide(g, V, A, B, PV("u%d" % n), "RP%d" % g)
    P.end()
    # ---- transcription and translation: a walker (5) along x at the slow phase, something it carries (6), three visitors (7-9) sliding in to it ----
    def walker(name, cst, carried):
        P.begin(name, [4, 5, 6, 7, 8, 9])
        V = R(4); phys_view(V); tag = name[:2].upper()
        px, py = P.W(2)
        P.MUL(px, k["ONE"], K(tag + "_P0", cst["p_start"])); P.MAC(px, K(tag + "_PL", cst["p_len"]), PV("sl")); P.MUL(py, k["ONE"], K(tag + "_PY", cst["p_y"]))
        P.copy(R(5), V); P.col_times(T(5), V, 0, px); P.col_times(T(5), V, 1, py, add=True)
        carried(V, px, py, tag)
        for n, (dx, dy) in enumerate(cst["offs"]):
            w, qx, qy = P.W(3); u = PV("u%d" % n)
            P.MUL(w, k["ONE"], k["ONE"]); P.MSB(w, k["ONE"], u)                                   # 1 - u: the visitor's distance left
            P.MUL(qx, k["ONE"], px); P.MAC(qx, K("%s_O%dX" % (tag, n), dx), w)
            P.MUL(qy, k["ONE"], py); P.MAC(qy, K("%s_O%dY" % (tag, n), dy), w)
            P.copy(R(7 + n), V); P.col_times(T(7 + n), V, 0, qx); P.col_times(T(7 + n), V, 1, qy, add=True)
        P.end()
    def rna_tail(V, px, py, tag):
        """the RNA out of the polymerase: a travelling wave along its own axis (the stored (s, cos ks, sin ks) with
        y' = sin(ks - wt)), the axis at a fixed angle in the picture's plane, its root at the polymerase's exit"""
        c_ = objects.TRANS; a = math.radians(c_["tail_angle_deg"])
        B = P.W(9); P.post_z(B, V, K("TR_TS", math.sin(a)), K("TR_TC", math.cos(a)))                # V Rz(angle)
        ns = P.W(); P.MUL(ns, k["NEG1"], S("em"))
        for i in range(3):
            P.MUL(R(6)[3 * i], k["ONE"], B[3 * i]); P.MUL(R(6)[3 * i + 1], B[3 * i + 1], ns); P.MUL(R(6)[3 * i + 2], B[3 * i + 1], C("em"))
        qx, qy = P.W(2); P.MUL(qx, k["ONE"], px); P.MAC(qx, k["ONE"], K("TR_EX", c_["tail_exit"][0])); P.MUL(qy, k["ONE"], py); P.MAC(qy, k["ONE"], K("TR_EY", c_["tail_exit"][1]))
        P.col_times(T(6), V, 0, qx); P.col_times(T(6), V, 1, qy, add=True)
    def peptide(V, px, py, tag):
        """the chain outside the ribosome rides up two beads a cycle of its phase (the pattern repeats every two beads)"""
        qy = P.W(); P.MUL(qy, k["ONE"], py); P.MAC(qy, K("TL_RISE", 2 * objects.TRL["pitch"]), PV("u3"))
        P.copy(R(6), V); P.col_times(T(6), V, 0, px); P.col_times(T(6), V, 1, qy, add=True)
    walker("transcribe", objects.TRANS, rna_tail); walker("translate", objects.TRL, peptide)
    # ---- the satellites: the Earth (the seal's globe, group 1, scaled up, spinning), the orbits (4), three satellites (5-7) ----
    P.begin("sats", [1, 4, 5, 6, 7])
    Tm = P.W(9); P.rx_ry(Tm, k["TS"], k["TC"], S("s"), C("s")); P.scale(R(1), Tm, K("EARTH", objects.EARTH_SCALE))
    V = R(4); phys_view(V)
    for n, sat in enumerate(objects.SATS):
        O = objects.orbit_matrix(sat); Ok = [K("O%d_%d" % (n, j), O.flat[j]) for j in range(9)]
        Mv = P.W(9); P.matmul(Mv, V, Ok)
        ph = "o%d" % (n + 1); P.post_z(R(5 + n), Mv, S(ph), C(ph))
        ax, ay = P.W(2); P.MUL(ax, K("SAT_A%d" % n, sat["a"]), C(ph)); P.MUL(ay, k["SAT_A%d" % n], S(ph))
        P.col_times(T(5 + n), Mv, 0, ax); P.col_times(T(5 + n), Mv, 1, ay, add=True)
    P.end()
    build_new(P, consts)
    return P

def build_new(P, consts):
    """The finales added 2026-11-09, from their models in proposals.py (whose mats(t), in floating point, these sections
    are checked against: check_prog.py)."""
    import proposals as PR
    k = P.k; K = P.KV; d2t = 1 / 360.0
    def view(dst, tilt, swing, off, src="pv"):
        """dst = Rx(tilt) Ry(off + swing sin(src)), degrees; constant when swing is 0"""
        if swing == 0:
            M = PR.rx(math.radians(tilt)) @ PR.ry(math.radians(off))
            for j in range(9): P.MUL(dst[j], k["ONE"], K(M.flat[j]))
            return
        s, c = P.angle(K(off * d2t), K(swing * d2t), S(src))
        P.rx_ry(dst, K(math.sin(math.radians(tilt))), K(math.cos(math.radians(tilt))), s, c)
    def kmat(M): return [K(x) for x in np.asarray(M, float).flat]
    def kvec_into(dst, v):
        for i in range(3):
            if v[i] != 0: P.MUL(dst[i], k["ONE"], K(v[i]))
    def double(s1, c1):
        """the sine and cosine of twice the angle"""
        s2, c2 = P.W(2); P.MUL(s2, s1, c1); P.MAC(s2, s1, c1); P.MUL(c2, c1, c1); P.MSB(c2, s1, s1); return s2, c2
    # ---- LIGO: the table seen tilted (4); the arms stretch and squeeze (5, 6), the ring of masses (7); light dashes (8-11) ----
    L = PR.LIGO; A = L["arm"]; cx, cy = L["c"]; rcx, rcy = L["ring_c"]
    P.begin("ligo", list(range(4, 12)))
    V = R(4); view(V, -38.0, 22.0, 0.0)
    h, p1, m1 = P.W(3); P.MUL(h, K(L["h"]), S("em"))
    P.MUL(p1, k["ONE"], k["ONE"]); P.MAC(p1, k["ONE"], h); P.MUL(m1, k["ONE"], k["ONE"]); P.MSB(m1, k["ONE"], h)
    for g, fx, fy in ((5, p1, None), (6, None, m1), (7, p1, m1)):
        for i in range(3):
            if fx is None: P.MUL(R(g)[3 * i], k["ONE"], V[3 * i])
            else: P.MUL(R(g)[3 * i], V[3 * i], fx)
            if fy is None: P.MUL(R(g)[3 * i + 1], k["ONE"], V[3 * i + 1])
            else: P.MUL(R(g)[3 * i + 1], V[3 * i + 1], fy)
            P.MUL(R(g)[3 * i + 2], k["ONE"], V[3 * i + 2])
    P.col_times(T(5), V, 0, K(cx)); P.col_times(T(5), V, 1, K(cy), add=True); P.copy(T(6), T(5))
    P.col_times(T(7), V, 0, K(rcx)); P.col_times(T(7), V, 1, K(rcy), add=True)
    u = PV("em")
    for g, along_x, back, side in ((8, True, False, 1), (9, True, True, -1), (10, False, False, 1), (11, False, True, -1)):
        xs, pa = P.W(2)
        if back: P.MUL(xs, k["ONE"], K(0.06 + 0.9 * A)); P.MSB(xs, K(0.9 * A), u)
        else: P.MUL(xs, k["ONE"], K(0.06)); P.MAC(xs, K(0.9 * A), u)
        P.MUL(pa, k["ONE"], K(cx if along_x else cy)); P.MAC(pa, xs, p1 if along_x else m1)
        P.copy(R(g), V)
        if along_x: P.col_times(T(g), V, 0, pa); P.col_times(T(g), V, 1, K(cy + 0.012 * side), add=True)
        else: P.col_times(T(g), V, 0, K(cx + 0.012 * side)); P.col_times(T(g), V, 1, pa, add=True)
    P.end()
    # ---- the circuit board: the board (4) and the charge, a group per direction of flow (5-12), sliding a bead's step ----
    KP = PR.PCB; P.begin("pcb", list(range(4, 13)))
    V = R(4); view(V, KP["tilt"], KP["swing"], 0.0)
    st, nst, dg, ndg = P.W(4); P.MUL(st, K(2 * KP["u"] * KP["scale"]), PV("pc")); P.MUL(nst, k["NEG1"], st)
    P.MUL(dg, st, K(math.sqrt(0.5))); P.MUL(ndg, k["NEG1"], dg)
    def comp(v): return None if abs(v) < 1e-9 else st if v > 0.99 else nst if v < -0.99 else dg if v > 0 else ndg
    for d in range(8):
        g = 5 + d; P.copy(R(g), V); dx, dy = PR._D8[d]; first = True
        for col, v in ((0, dx), (1, dy)):
            r = comp(v)
            if r is not None: P.col_times(T(g), V, col, r, add=not first); first = False
    P.end()
    # ---- the fidget spinner: the cap and logo still (4), the body (5) turned by the ramped phase ----
    P.begin("spinner", [4, 5])
    for j in (0, 4, 8): P.MUL(R(4)[j], k["ONE"], k["ONE"])
    sp, cp = S("sp"), C("sp"); R5 = R(5)
    P.MUL(R5[0], k["ONE"], cp); P.MUL(R5[1], k["ONE"], sp); P.MUL(R5[3], k["NEG1"], sp); P.MUL(R5[4], k["ONE"], cp); P.MUL(R5[8], k["ONE"], k["ONE"])
    P.end()
    # ---- the top: the floor (4); the top (5) = V Ry(precession) Rz(lean + nod) Ry(spin) about its tip ----
    TP = PR.TOP; P.begin("top", [4, 5])
    Vm = PR.rx(math.radians(-24.0)); Vk = kmat(Vm); tip = Vm @ np.array([TP["tip"][0], TP["tip"][1], 0.0])
    P.copy(R(4), Vk); kvec_into(T(4), tip); kvec_into(T(5), tip)
    M1 = P.W(9); P.post_y(M1, Vk, S("gs"), C("gs"))
    s2, c2 = double(S("ds"), C("ds"))
    sl_, cl_ = P.angle(K(TP["lean"] * d2t), K(TP["nod"] * d2t), s2)
    M2 = P.W(9); P.post_z(M2, M1, sl_, cl_)
    ss, cs = double(S("em"), C("em")); P.post_y(R(5), M2, ss, cs)
    P.end()
    # ---- the pendulum wave: the bar (3), twelve pendulums (4-15) at 16-27 times the phase pw, by angle addition ----
    W_ = PR.PWAVE; P.begin("pwave", list(range(3, 16)))
    V = R(3); view(V, -22.0, 8.0, 19.0); P.col_times(T(3), V, 1, K(W_["top"]))
    c1, s1 = C("pw"), S("pw"); cc, ss = c1, s1; n = 1
    while n < W_["n0"]: ss, cc = double(ss, cc); n *= 2
    assert n == W_["n0"], "n0 a power of 2"
    cn = [cc]
    for _ in range(W_["n"] - 1):
        c2, s2 = P.W(2); P.MUL(c2, cc, c1); P.MSB(c2, ss, s1); P.MUL(s2, ss, c1); P.MAC(s2, cc, s1); cc, ss = c2, s2; cn.append(cc)
    for kk in range(W_["n"]):
        th, sk, ck = P.W(3); P.MUL(th, K(W_["amp"] * d2t), cn[kk]); P.SIN(sk, th); P.COS(ck, th)
        P.post_z(R(4 + kk), V, sk, ck); P.copy(T(4 + kk), T(3)); P.col_times(T(4 + kk), V, 2, K(PR.PWave.z(kk)), add=True)
    P.end()
    # ---- the AC generator: magnet and chart (4), the coil turning (5), its voltage as a travelling sine (6) ----
    G = PR.GEN; P.begin("generator", [4, 5, 6])
    V = R(4); view(V, -18.0, 22.0, 0.0); P.post_x(R(5), V, S("em"), C("em"))
    a1, a2 = P.W(2); P.MUL(a1, K(G["amp"]), S("em")); P.MUL(a2, K(-G["amp"]), C("em"))
    for i in range(3):
        P.MUL(R(6)[3 * i], k["ONE"], V[3 * i]); P.MUL(R(6)[3 * i + 1], V[3 * i + 1], a1); P.MUL(R(6)[3 * i + 2], V[3 * i + 1], a2)
    P.col_times(T(6), V, 0, K(G["x0"]))
    P.end()
    # ---- Watt's governor: the frame (4), the arms (5, 6), the links (7, 8), the sleeve (9), the lever (10) ----
    G = PR.GOV; P.begin("governor", list(range(4, 11)))
    Vm = PR.rx(math.radians(-14.0)); Vk = kmat(Vm); P.copy(R(4), Vk); lk = G["link"]
    sm, cm = double(S("pv"), C("pv"))                                          # the speed's rise and fall: twice pv
    th, ssp, csp = P.W(3); P.MUL(th, k["ONE"], PV("em")); P.MSB(th, K(G["mod"] * G["spin_per_s"] / G["mod_per_s"] / (2 * math.pi)), cm)
    P.SIN(ssp, th); P.COS(csp, th)
    sa, ca = P.angle(K(G["a0"] * d2t), K(G["a1"] * d2t), sm); nsa = P.W(); P.MUL(nsa, k["NEG1"], sa)
    Sm = P.W(9); P.post_y(Sm, Vk, ssp, csp)
    P.post_z(R(5), Sm, sa, ca); P.post_z(R(6), Sm, nsa, ca); P.copy(R(7), R(6)); P.copy(R(8), R(5))
    topw = Vm @ np.array([0, G["top"], 0.0]); kvec_into(T(5), topw); kvec_into(T(6), topw)
    P.copy(T(7), T(5)); P.col_times(T(7), R(5), 1, K(-lk), add=True); P.copy(T(8), T(6)); P.col_times(T(8), R(6), 1, K(-lk), add=True)
    P.copy(R(9), Sm); ysl = P.W(); P.MUL(ysl, k["ONE"], K(G["top"])); P.MSB(ysl, K(2 * lk), ca); P.col_times(T(9), Vk, 1, ysl)
    y0 = G["top"] - 2 * lk * math.cos(math.radians(G["a0"])) - G["tube"] + 0.02; Y = G["tube"] - 0.02 + y0; kh = 1 / (0.045 - 0.36) / 2
    dd, kk_, ty = P.W(3); P.MUL(dd, k["ONE"], ysl); P.MSB(dd, k["ONE"], K(Y)); P.MUL(kk_, dd, K(kh)); P.MAC(kk_, dd, K(kh))
    for i in range(3):
        P.MUL(R(10)[3 * i], k["ONE"], Vk[3 * i]); P.MAC(R(10)[3 * i], kk_, Vk[3 * i + 1])
        P.MUL(R(10)[3 * i + 1], k["ONE"], Vk[3 * i + 1]); P.MUL(R(10)[3 * i + 2], k["ONE"], Vk[3 * i + 2])
    P.MUL(ty, k["ONE"], K(y0)); P.MSB(ty, K(0.36), kk_); P.col_times(T(10), Vk, 1, ty)
    P.end()
    # ---- the sonic boom: the jet (4), five circles (5-9) on the staggered sawtooths, carried back by the Mach number ----
    B = PR.BOOM; P.begin("boom", list(range(4, 4 + 1 + B["n"])))
    for j in (0, 4, 8): P.MUL(R(4)[j], k["ONE"], k["ONE"])
    P.MUL(T(4)[0], k["ONE"], K(B["jet_x"]))
    Mr = P.W(); P.MUL(Mr, k["ONE"], K(B["m0"])); P.MSB(Mr, K(B["m1"]), C("pv"))
    for n in range(B["n"]):
        r, tx = P.W(2); P.MUL(r, K(B["r_max"]), PV("u%d" % n))
        for j in (0, 4, 8): P.MUL(R(5 + n)[j], k["ONE"], r)
        P.MUL(T(5 + n)[0], k["ONE"], K(B["jet_x"])); P.MSB(T(5 + n)[0], Mr, r)
    P.end()
    # ---- the oscilloscope in the oscilloscope: level 0 (4), each inner level (5-7) = the outer's R x the screen's frame
    # (scaled, flattened) x the view, at the outer's screen centre ----
    TK = PR.TEK; P.begin("tek", [4, 5, 6, 7])
    V = R(4); view(V, TK["view_tilt"], TK["swing"], TK["view_off"])
    ctr, e1, e2, sw, sh = PR.Tek.screen_frame(); sc = PR.Tek.nest_scale()
    Rk, Tk = V, None
    for lv in range(1, TK["levels"]):
        g = 4 + lv; A0, A1 = P.W(3), P.W(3)
        for i in range(3):
            for dst, e in ((A0, e1), (A1, e2)):
                first = True
                for j in range(3):
                    if abs(e[j]) > 1e-9: (P.MUL if first else P.MAC)(dst[i], Rk[3 * i + j], K(sc * e[j])); first = False
        for i in range(3):
            for j in range(3): P.MUL(R(g)[3 * i + j], A0[i], V[j]); P.MAC(R(g)[3 * i + j], A1[i], V[3 + j])
        first = Tk is None
        if not first: P.copy(T(g), Tk)
        for j in range(3):
            if abs(ctr[j]) > 1e-9: P.col_times(T(g), Rk, j, K(ctr[j]), add=not first); first = False
        Rk, Tk = R(g), T(g)
    P.end()

def select(P, names):
    """The program with only the seal's section and those named, end to end (each section is self-contained: no jumps),
    and their start addresses."""
    order = sorted(P.sections.items(), key=lambda kv: kv[1]); ends = [pc for n, pc in order[1:]] + [len(P.prog)]
    prog, secs = [], {}
    for (n, pc), e in zip(order, ends):
        if n == "seal" or n in names: secs[n] = len(prog); prog += P.prog[pc:e]
    assert len(prog) <= PROG_MAX, ("the program is %d instructions; the gateware holds %d" % (len(prog), PROG_MAX))
    return prog, secs

def regs_init(P):
    v = [0] * 1024
    for name, r in P.k.items(): v[r] = P.kv[name]
    for g in range(16): v[MAT_BASE + 16 * g] = v[MAT_BASE + 16 * g + 4] = v[MAT_BASE + 16 * g + 8] = Q          # every group the identity
    v[MAT_BASE + 16 + 9] = P.kv["GCX"]; v[MAT_BASE + 16 + 10] = P.kv["GCY"]                                   # the globe at its place
    return v

def run(v, prog, pc0):
    """The reference: v (1024 ints, Q2.14) modified in place as the gateware would, from pc0 to END."""
    def sat(x): return max(-32768, min(32767, x))
    pc = pc0
    while True:
        op, d, a, b = prog[pc]; pc += 1
        if op == END: return v
        if op == SIN: v[d] = SINE[(v[a] >> 4) & 1023]
        elif op == COS: v[d] = SINE[((v[a] >> 4) + 256) & 1023]
        else:
            p = (v[a] * v[b]) >> 14
            v[d] = sat(p) if op == MUL else sat(v[d] + p) if op == MAC else sat(v[d] - p)

def load_phases(v, phases):
    """What the hardware writes at every start: the sines, cosines and turn values of the 32 phases (32-bit each)."""
    for k_ in range(NPH):
        ph = int(phases[k_]) & 0xffffffff; i = ph >> 22
        v[SIN_BASE + 2 * k_] = SINE[i]; v[SIN_BASE + 2 * k_ + 1] = SINE[(i + 256) & 1023]; v[PHV_BASE + k_] = ph >> 18

def matrices(v):
    """{group: (R 3x3, t 3)} as floats from the register file."""
    out = {}
    for g in range(16):
        m = np.array(v[MAT_BASE + 16 * g: MAT_BASE + 16 * g + 12], float) / Q
        out[g] = (m[:9].reshape(3, 3), m[9:12])
    return out

def write_all(P, rtl_dirs, host_dir=HERE, names=None):
    """the gateware's files from the program with the seal's section and the named ones (all if None)"""
    prog0, secs = select(P, names if names is not None else set(P.sections))
    init = regs_init(P); prog = prog0 + [(0, 0, 0, 0)] * (PROG_MAX - len(prog0))
    for d in rtl_dirs:
        with open(os.path.join(d, "matrix_prog.hex"), "w") as f:
            for op, dst, a, b in prog: f.write("%09x\n" % ((op << 30) | (dst << 20) | (a << 10) | b))
        with open(os.path.join(d, "regs_init.hex"), "w") as f:
            for x in init: f.write("%05x\n" % (x & 0x3ffff))
        with open(os.path.join(d, "matrix_prog.vh"), "w") as f:
            f.write("// generated by host/gen_matrix_prog.py: the program's sections (start addresses) and length\n")
            for name, pc in secs.items(): f.write("localparam [11:0] PC_%s = 12'd%d;\n" % (name.upper(), pc))
            f.write("localparam [12:0] PROG_LEN = 13'd%d;\n" % len(prog0))
    order = sorted(secs.values()); lens = {n: (order + [len(prog0)])[order.index(pc) + 1] - pc for n, pc in secs.items()}
    json.dump({"sections": secs, "section_lengths": lens, "constants": {n: P.kv[n] / Q for n in P.k}, "n_instructions": len(prog0),
               "n_constants": P.nk}, open(os.path.join(host_dir, "matrix_prog.json"), "w"), indent=1)
    return lens

if __name__ == "__main__":
    print("run through make_show.py, which supplies the animation constants")
