#!/usr/bin/env python3
"""The finales proposed on 2026-11-09, and the oscilloscope in an oscilloscope added after, as float models.  Jason's
choice (prompt 84): LIGO, the circuit board, the fidget spinner, the top, the pendulum wave, the AC generator, Watt's
governor, the sonic boom and the oscilloscope are in the show (objects.OBJECTS draws their obj(); gen_matrix_prog.py's
build_new has their program sections, which check_prog.py holds to their mats(t)); the Galton board, the engine, the
escapement, CartPole and the bridge are models only (none is in the show; they have no program section).

Each proposal is what a finale is in host/objects.py and host/gen_matrix_prog.py, in floating point:
  obj()     the object: (polyline, group) pairs, one rigid group per moving part, groups 3-15 (3, the labels' group,
            is free now there are none; a finale draws nothing of the seal)
  mats(t)   {group: (R 3x3, t 3)} at t seconds into the finale: what its program section would write.  Only what the
            animator can compute: sines and cosines of phases, products, sums; every element within +/-2 (Q2.14)
  seconds   how long it runs
  needs     what the gateware would need beyond a program section and its vertices (an honest list for choosing)
A dot (an electron, a peg) is a stroke of two equal vertices: the line generator gives a zero-length segment its
least 8 samples, a bright point."""
import os, sys, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from objects import circle, seg, box
TAU = 2 * math.pi; I3 = np.eye(3); O3 = np.zeros(3)
def rx(a): c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
def ry(a): c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def rz(a): c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
def deg(a): return math.radians(a)
def view(t, tilt=-20.0, swing=35.0, per_s=0.08, off=0.0):
    """the physics finales' viewpoint: Rx(tilt) Ry(off + swing sin): it swings either side of a view and comes back"""
    return rx(deg(tilt)) @ ry(deg(off + swing * math.sin(TAU * per_s * t)))
def saw(t, per_s, k=0, n=1): return (t * per_s + k / n) % 1.0          # a sawtooth phase, the k-th of n staggered
def dot(p): return np.array([p, p], float)
def xy(pts, z=0.0): p = np.asarray(pts, float); return np.column_stack([p, np.full(len(p), z)])
def arc(r, a0, a1, n, c=(0, 0, 0)):
    a = np.radians(np.linspace(a0, a1, n + 1)); return np.column_stack([r * np.cos(a), r * np.sin(a), np.zeros(n + 1)]) + np.array(c)
def rect(x0, x1, y0, y1, z=0.0): return np.array([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z], [x0, y0, z]], float)
PROPOSALS = {}
def proposal(name, title, seconds, needs=""):
    def deco(cls):
        PROPOSALS[name] = dict(name=name, title=title, seconds=seconds, obj=cls.obj, mats=cls.mats, needs=needs); return cls
    return deco

# ---------------- 1. a four-stroke engine, a cutaway seen flat (as the gears are): the crank (5) turns, the
# connecting rod (6) follows it (a shear: its foot on the crank pin, its head on the cylinder's axis), the piston (7)
# slides; the two cams (10, 11) turn at half the crank's rate and push their valves (8, 9) open in turn; a spark (12)
# at the plug as compression ends.  Intake, compression, power, exhaust: two turns of the crank. ----------------
ENG = dict(cy=-0.47, r=0.13, L=0.42, bore=0.16, head=0.25, lift=0.055, cam_y=0.665, cam_r=0.045, vx=0.08, rev_per_s=0.8)
def _bump(x, n): return ((1 + math.cos(x)) / 2) ** n      # a smooth bump at x = 0 (n squarings in the program)
@proposal("engine", "four-stroke engine", 6.5, "1 new phase (the cams; the crank is twice it)")
class Engine:
    @staticmethod
    def obj():
        E = ENG; cy, r, L, b, h, vx = E["cy"], E["r"], E["L"], E["bore"], E["head"], E["vx"]; out = []
        a0 = math.degrees(math.asin(b / 0.22))                                   # the crankcase meets the cylinder's walls
        case = arc(0.22, 90 - a0, -270 + a0, 20, (0, cy, 0))
        out.append((np.vstack([[[b, h, 0]], case, [[-b, h, 0]]]), 4))            # the walls and the crankcase, one stroke
        for s in (-1, 1):                                                        # the head: the roof, the ports
            out.append((xy([(s * b, h), (s * (vx + 0.05), h)]), 4))
            out.append((xy([(s * (vx + 0.05), h), (s * 0.21, h + 0.10), (s * 0.38, h + 0.10)]), 4))
            out.append((xy([(s * (vx - 0.05), h), (s * (vx - 0.05), h + 0.14), (s * 0.12, h + 0.20), (s * 0.38, h + 0.20)]), 4))
        out.append((xy([(-(vx - 0.05), h), (-0.012, h), (-0.012, h + 0.09), (0.012, h + 0.09), (0.012, h), (vx - 0.05, h)]), 4))   # the roof and the plug
        out.append((xy([(0, h + 0.09), (0, h + 0.15)]), 4))
        out.append((circle(0.05, 12), 5)); out.append((circle(0.028, 8, c=(0, r, 0)), 5))                         # the crank: hub, pin
        cw = arc(0.115, 215, 325, 8); out.append((np.vstack([[[0.03, 0.04, 0]], cw[::-1], [[-0.03, 0.04, 0]]]), 5))  # its counterweight
        out.append((xy([(-0.03, 0.04), (-0.022, r), (0.022, r), (0.03, 0.04)]), 5))
        out.append((xy([(-0.024, 0.03), (-0.014, L - 0.02)]), 6)); out.append((xy([(0.024, 0.03), (0.014, L - 0.02)]), 6))   # the rod, from the pin up
        out.append((circle(0.038, 10), 6)); out.append((circle(0.022, 8, c=(0, L, 0)), 6))
        out.append((rect(-b + 0.008, b - 0.008, -0.07, 0.10), 7))                # the piston, its rings
        for y in (0.075, 0.05): out.append((xy([(-b + 0.008, y), (b - 0.008, y)]), 7))
        top = E["cam_y"] - E["cam_r"]
        for g, s in ((8, -1), (9, 1)):                                           # a valve: the head on its seat, the stem, the cap under the cam
            out.append((xy([(s * (vx - 0.05), h), (s * (vx + 0.05), h), (s * vx, h + 0.025), (s * (vx - 0.05), h)]), g))
            out.append((xy([(s * vx, h + 0.025), (s * vx, top)]), g)); out.append((xy([(s * vx - 0.025, top), (s * vx + 0.025, top)]), g))
        a = np.linspace(0, TAU, 17); rr = E["cam_r"] + E["lift"] * ((1 + np.cos(a)) / 2) ** 8      # a cam: the lobe along -y when the valve is fully open
        cam = np.column_stack([rr * np.sin(a), -rr * np.cos(a), np.zeros(17)])
        for g in (10, 11): out.append((cam.copy(), g)); out.append((circle(0.012, 4), g))
        for a in (0, 60, 120): c, s = 0.05 * math.cos(deg(a)), 0.05 * math.sin(deg(a)); out.append((xy([(-c, -s), (c, s)]), 12))   # the spark
        return out
    @staticmethod
    def mats(t):
        E = ENG; cy, r, L, vx = E["cy"], E["r"], E["L"], E["vx"]
        th = TAU * E["rev_per_s"] * t; ps = th / 2                               # the crank from top dead centre, the cams
        s, c = math.sin(th), math.cos(th); y = r * c + L - r * r * s * s / (2 * L)       # the piston's pin above the crank's centre
        shear = np.array([[1, -r / L * s, 0], [0, 1 - r * r * s * s / (2 * L * L), 0], [0, 0, 1]])
        m = {4: (I3, O3), 5: (rz(-th), np.array([0, cy, 0])), 6: (shear, np.array([r * s, cy + r * c, 0])), 7: (I3, np.array([0, cy + y, 0]))}
        for g, cam, sx, at in ((8, 10, -1, math.pi / 4), (9, 11, 1, 7 * math.pi / 4)):     # intake mid-way down the first stroke, exhaust up the fourth
            m[g] = (I3, np.array([0, -E["lift"] * _bump(ps - at, 8), 0]))
            m[cam] = (rz(-sx * (ps - at)), np.array([sx * vx, E["cam_y"], 0]))
        m[12] = (I3 * _bump(ps - math.pi, 64), np.array([0, E["head"] - 0.03, 0]))
        return m

# ---------------- 2. Watt's flyball governor: the shaft and all on it spin about the vertical; the two arms (5, 6)
# swing out as it speeds up, the lower links (7, 8) lift the sleeve (9), and the sleeve's lever (10) closes the
# throttle.  The spin's rate rises and falls (a phase plus a sine), the arms' angle with it. ----------------
GOV = dict(top=0.52, arm=0.52, link=0.26, ball=0.085, a0=38.0, a1=20.0, tube=0.35, spin_per_s=0.5, mod_per_s=0.16, mod=0.6)
@proposal("governor", "Watt's flyball governor", 6.5, "no new phase (the spin on em, 0.5/s; its rise and fall on twice pv)")
class Governor:
    @staticmethod
    def obj():
        G = GOV; out = []; top, arm, lk, b = G["top"], G["arm"], G["link"], G["ball"]
        out.append((xy([(0, -0.62), (0, top + 0.06)]), 4))                       # the shaft, its base, its bearing
        out += [(p, 4) for p in box(-0.2, 0.2, -0.68, -0.62, -0.14, 0.14)]
        out.append((circle(0.035, 8, "y", (0, top + 0.06, 0)), 4))
        out.append((xy([(-0.03, top), (0.03, top)]), 4))
        for g in (5, 6):                                                         # an arm, hanging along -y from the top pivot, its ball
            out.append((xy([(0, 0), (0, -arm + b)]), g))
            for ax in ("x", "y", "z"): out.append((circle(b, 10, ax, (0, -arm, 0)), g))
        for g in (7, 8): out.append((xy([(0, 0), (0, -lk)]), g))                 # a lower link, hanging from its pin on the arm
        tb = G["tube"]                                                           # the sleeve: a tube down the shaft, the lever's collar at its foot, below the balls
        for y in (0, -0.05, -tb + 0.04, -tb): out.append((circle(0.045, 8, "y", (0, y, 0)), 9))
        for a in (0, 180): out.append((xy([(0.045 * math.cos(deg(a)), 0), (0.045 * math.cos(deg(a)), -tb)]), 9))
        y0 = G["top"] - 2 * lk * math.cos(deg(G["a0"])) - tb + 0.02              # the lever's pivot: level with the collar at the mean speed
        out.append((xy([(0.045, 0), (0.62, 0)]), 10))                            # the lever: from the collar, over its pivot, to the throttle rod
        out.append((xy([(0.62, 0), (0.62, -0.27)]), 10)); out.append((rect(0.57, 0.67, -0.32, -0.27), 10))
        out.append((xy([(0.36, -0.62), (0.36, y0)]), 4)); out.append((circle(0.02, 6, c=(0.36, y0, 0)), 4))   # the lever's post
        out += [(p, 4) for p in box(0.52, 0.72, -0.68, -0.40, -0.07, 0.07)]      # the valve chest the rod goes into
        return out
    @staticmethod
    def angle(t):
        G = GOV; m = TAU * G["mod_per_s"] * t
        spin = TAU * G["spin_per_s"] * t - G["mod"] * G["spin_per_s"] / G["mod_per_s"] * math.cos(m)     # the rate: 1 + mod sin(m)
        return spin, deg(G["a0"] + G["a1"] * math.sin(m))
    @staticmethod
    def mats(t):
        G = GOV; V = view(t, -14.0, 0.0); spin, a = Governor.angle(t); S = V @ ry(spin); lk = G["link"]
        top = np.array([0, G["top"], 0]); m = {4: (V, O3)}
        ysl = G["top"] - 2 * lk * math.cos(a)                                    # the sleeve: a rhombus of the arms' upper parts and the links
        for g, gl, sgn in ((5, 7, 1), (6, 8, -1)):
            R = S @ rz(sgn * a); m[g] = (R, V @ top)
            m[gl] = (S @ rz(-sgn * a), V @ top + R @ np.array([0, -lk, 0]))
        m[9] = (S, V @ np.array([0, ysl, 0]))
        y0 = G["top"] - 2 * lk * math.cos(deg(G["a0"])) - G["tube"] + 0.02       # the lever, level at the mean; a shear about its pivot
        k = (ysl - G["tube"] + 0.02 - y0) / (0.045 - 0.36); Lv = np.array([[1, 0, 0], [k, 1, 0], [0, 0, 1]])
        m[10] = (V @ Lv, V @ np.array([0, y0 - k * 0.36, 0]))
        return m

# ---------------- 3. a sonic boom, seen from beside the jet (which stays put: the picture moves with it): the sound it
# makes spreads as circles (5-12) while the air carries their centres back; as the jet's speed climbs through Mach 1
# the circles pile up at its nose and then trail as a cone.  Each circle is a group, scaled by its age (a sawtooth,
# eight of them staggered) and moved back by the Mach number times as much. ----------------
BOOM = dict(jet_x=0.56, jet=1.7, r_max=0.46, n=5, per_s=0.33, m0=1.0, m1=0.62, m_per_s=0.08)      # the circles on u0-u4, the Mach number on pv (zeroed at the start)
@proposal("boom", "sonic boom", 7.0, "no new phase with five circles (the sawtooths u0-u4, the Mach number on pv); eight need three more")
class Boom:
    @staticmethod
    def obj():
        B = BOOM; out = []
        jet = [(0.0, 0.0), (-0.06, 0.012), (-0.10, 0.016), (-0.13, 0.05), (-0.145, 0.05), (-0.135, 0.012), (-0.15, 0.0),
               (-0.135, -0.012), (-0.10, -0.016), (-0.06, -0.012), (0.0, 0.0)]                      # the fuselage and the fin, the nose at the origin
        out.append((xy(jet) * B["jet"], 4)); out.append((xy([(-0.05, 0.0), (-0.105, -0.045), (-0.12, -0.045), (-0.095, 0.0)]) * B["jet"], 4))   # a wing
        for g in range(5, 5 + B["n"]): out.append((circle(1.0, 28), g))
        return out
    @staticmethod
    def mach(t): B = BOOM; return B["m0"] - B["m1"] * math.cos(TAU * B["m_per_s"] * t)
    @staticmethod
    def mats(t):
        B = BOOM; M = Boom.mach(t); m = {4: (I3, np.array([B["jet_x"], 0, 0]))}
        for k in range(B["n"]):
            r = B["r_max"] * saw(t, B["per_s"], k, B["n"])
            m[5 + k] = (I3 * r, np.array([B["jet_x"] - M * r, 0, 0]))
        return m

# ---------------- 4. LIGO: the laser, the beam splitter at the corner, two arms with a mirror at the end of each, the
# detector; a gravitational wave stretches one arm (5) as it squeezes the other (6), and a ring of free masses beside
# them (7) flexes the same way into an ellipse and back.  Light runs out and back along each arm as dashes (8-11),
# carried by the arm's stretch.  The table is the xy plane, seen tilted. ----------------
LIGO = dict(c=(-0.42, -0.42), arm=0.92, h=0.13, gw_per_s=0.5, ring_c=(0.2, 0.2), ring_r=0.27, n_mass=12, dash=0.07, light_per_s=0.5)
@proposal("ligo", "LIGO", 7.0, "no new phase at 0.5/s (the wave and the light on em, the view on pv)")
class Ligo:
    @staticmethod
    def obj():
        L = LIGO; cx, cy = L["c"]; A = L["arm"]; out = []
        out += [(p, 4) for p in box(cx - 0.40, cx - 0.24, cy - 0.04, cy + 0.04, -0.03, 0.03)]              # the laser
        out.append((xy([(cx - 0.24, cy), (cx, cy)]), 4))
        out.append((xy([(cx - 0.05, cy - 0.05), (cx + 0.05, cy + 0.05)]), 4))                             # the beam splitter
        out.append((xy([(cx, cy), (cx, cy - 0.20)]), 4)); out += [(p, 4) for p in box(cx - 0.05, cx + 0.05, cy - 0.30, cy - 0.20, -0.03, 0.03)]   # the detector
        # an arm in its own frame, from the splitter at the origin: the beam, the tube's two rings, the end mirror
        out.append((xy([(0, 0), (A, 0)]), 5)); out.append((xy([(0, 0), (0, A)]), 6))
        for f in (0.12, 1.0):
            out.append((circle(0.045, 10, "x", (f * A, 0, 0)), 5)); out.append((circle(0.045, 10, "y", (0, f * A, 0)), 6))
        out.append((xy([(A + 0.012, -0.05), (A + 0.012, 0.05)]), 5)); out.append((xy([(-0.05, A + 0.012), (0.05, A + 0.012)]), 6))
        rx_, ry_ = L["ring_c"]                                                                           # the free masses, about the ring's centre
        for a in np.linspace(0, TAU, L["n_mass"], endpoint=False):
            out.append((circle(0.022, 4, c=(L["ring_r"] * math.cos(a), L["ring_r"] * math.sin(a), 0)), 7))
        d = L["dash"] / 2
        for g in (8, 9): out.append((xy([(-d, 0), (d, 0)]), g))
        for g in (10, 11): out.append((xy([(0, -d), (0, d)]), g))
        return out
    @staticmethod
    def mats(t):
        L = LIGO; V = view(t, -38.0, 22.0, 0.08); h = L["h"] * math.sin(TAU * L["gw_per_s"] * t); c = np.array([L["c"][0], L["c"][1], 0])
        Sx = np.diag([1 + h, 1, 1]); Sy = np.diag([1, 1 - h, 1]); u = saw(t, L["light_per_s"]); A = L["arm"]
        m = {4: (V, O3), 5: (V @ Sx, V @ c), 6: (V @ Sy, V @ c),
             7: (V @ np.diag([1 + h, 1 - h, 1]), V @ np.array([L["ring_c"][0], L["ring_c"][1], 0]))}
        for g, s in ((8, u), (9, 1 - u)): m[g] = (V, V @ (c + np.array([(0.06 + 0.9 * s * A) * (1 + h), 0.012 * (1 if g == 8 else -1), 0])))
        for g, s in ((10, u), (11, 1 - u)): m[g] = (V, V @ (c + np.array([0.012 * (1 if g == 10 else -1), (0.06 + 0.9 * s * A) * (1 - h), 0])))
        return m

# ---------------- 5. a spinning top on a floor: it spins on its axis, the axis leans and goes round the vertical
# (precession) and nods as it goes (nutation).  One group: R = V Ry(precession) Rz(lean) Ry(spin), the tip fixed. ----------------
TOP = dict(tip=(0.0, -0.52), scale=1.25, lean=17.0, nod=6.0, spin_per_s=1.0, prec_per_s=0.3, nod_per_s=0.9)     # spin twice em, precession gs, nod twice ds
@proposal("top", "spinning top", 6.0, "no new phase with the rates nudged (spin twice em, precession gs, nod twice ds)")
class Top:
    @staticmethod
    def obj():
        T = TOP; k = T["scale"]; out = []
        prof = np.array([(0, 0), (0.05, 0.06), (0.28, 0.28), (0.30, 0.32), (0.28, 0.36), (0.07, 0.40), (0.03, 0.44), (0.03, 0.60), (0.055, 0.63), (0.0, 0.66)]) * k
        for a in (0, 90):                                                        # two outlines through the axis: four meridians
            c, s = math.cos(deg(a)), math.sin(deg(a)); full = np.vstack([prof * [1, 1], (prof * [-1, 1])[-2::-1]])
            out.append((np.column_stack([full[:, 0] * c, full[:, 1], full[:, 0] * s]), 5))
        for r, y, n in ((0.30, 0.32, 20), (0.07, 0.40, 8), (0.055, 0.63, 6)): out.append((circle(r * k, n, "y", (0, y * k, 0)), 5))
        out.append((np.column_stack([0.19 * k * np.cos(np.linspace(0, 4.2, 9)), np.linspace(0.20, 0.30, 9) * k, 0.19 * k * np.sin(np.linspace(0, 4.2, 9))]), 5))   # a stripe: the spin shows
        out.append((circle(0.52, 28, "y"), 4)); out.append((circle(0.012, 4, "y"), 4))                      # the floor
        for a in (0, 90): c, s = 0.52 * math.cos(deg(a)), 0.52 * math.sin(deg(a)); out.append((np.array([[-c, 0, -s], [-0.3 * c, 0, -0.3 * s]]), 4)); out.append((np.array([[0.3 * c, 0, 0.3 * s], [c, 0, s]]), 4))
        return out
    @staticmethod
    def mats(t):
        T = TOP; V = rx(deg(-24.0)); tip = V @ np.array([T["tip"][0], T["tip"][1], 0])
        lean = deg(T["lean"] + T["nod"] * math.sin(TAU * T["nod_per_s"] * t))
        return {4: (V, tip), 5: (V @ ry(TAU * T["prec_per_s"] * t) @ rz(lean) @ ry(TAU * T["spin_per_s"] * t), tip)}

# ---------------- 6. a pendulum wave: twelve pendulums on one bar, each a little shorter than the last, so that in
# CYCLE seconds the longest swings N0 times, the next N0 + 1, ...: let go together they drift out of step into
# travelling waves, then (half way, where the finale ends) two alternating sets, and would come back into line.  The lengths are a real pendulum's (as
# 1 / frequency^2).  Each pendulum a group (4-15), R = V Rz(its angle); the frame is group 3. ----------------
PWAVE = dict(n=12, n0=16, cycle=24.0, l0=1.0, top=0.56, dz=0.11, amp=13.0, bob=0.04)
@proposal("pwave", "pendulum wave", 12.0, "1 new phase if the program makes the twelve rates as multiples of it (~110 more instructions), else 12; 13 groups (3-15)")
class PWave:
    @staticmethod
    def length(k): W = PWAVE; return W["l0"] * (W["n0"] / (W["n0"] + k)) ** 2
    @staticmethod
    def z(k): W = PWAVE; return (k - (W["n"] - 1) / 2) * W["dz"]            # the longest in front
    @staticmethod
    def obj():
        W = PWAVE; out = []; z0, z1 = PWave.z(0) - 0.05, PWave.z(W["n"] - 1) + 0.05
        out.append((np.array([[0, 0.06, z0], [0, 0, z0], [0, 0, z1], [0, 0.06, z1]]), 3))     # the bar, hung by its ends
        for z in (z0, z1): out.append((np.array([[-0.05, 0.06, z], [0.05, 0.06, z]]), 3))
        for k in range(W["n"]):
            L = PWave.length(k); out.append((xy([(0, 0), (0, -L + W["bob"])]), 4 + k)); out.append((circle(W["bob"], 8, c=(0, -L, 0)), 4 + k))
        return out
    @staticmethod
    def mats(t):
        W = PWAVE; V = view(t, -22.0, 8.0, 0.08, 19.0); top = np.array([0, W["top"], 0]); m = {3: (V, V @ top)}
        for k in range(W["n"]):
            a = deg(W["amp"]) * math.cos(TAU * (W["n0"] + k) / W["cycle"] * t)
            m[4 + k] = (V @ rz(a), V @ (top + np.array([0, 0, PWave.z(k)])))
        return m

# ---------------- 7. a clock's escapement (Graham's dead beat): the anchor (6) rocks with the pendulum; each swing
# one of its two pallets lets a tooth of the escape wheel (5) by and the other catches the next, so the wheel goes
# round a tooth a swing (30 teeth: once a minute in a clock that beats seconds).  The pallets are a quarter turn
# apart round the wheel, 7 1/2 teeth, and the anchor's pivot where the lines to them are tangent to the wheel, so
# rocking dips one pallet straight in as it lifts the other straight out.  The wheel's angle is a smooth staircase of
# the pendulum's phase: it waits, a tooth against a pallet's face, and steps half a tooth as the swing passes centre. ----------------
ESC = dict(w=(0.0, -0.03), teeth=30, rt=0.30, rr=0.245, swing=8.0, per_s=0.8, pend=0.93, bob=0.075, face=0.6, gap=0.4, top=0.07, back=7.0)
@proposal("escape", "clock escapement", 7.0, "2 new phases (the pendulum, the wheel at 1/30 of it)")
class Escape:
    @staticmethod
    def obj():
        E = ESC; out = []; n = E["teeth"]; pts = []; rt = E["rt"]
        for j in range(n + 1):                                                   # the wheel about its centre, turning clockwise: a tip, then the root under it (the tips lean forward)
            a = deg(-360.0 * j / n); b = a + deg(1.5)
            pts.append([rt * math.cos(a), rt * math.sin(a), 0])
            if j < n: pts.append([E["rr"] * math.cos(b), E["rr"] * math.sin(b), 0])
        out.append((np.array(pts), 5)); out.append((circle(0.05, 10), 5)); out.append((circle(0.20, 24), 5))
        for a in np.linspace(0, TAU, 5, endpoint=False): out.append((xy([(0.05 * math.cos(a), 0.05 * math.sin(a)), (0.20 * math.cos(a), 0.20 * math.sin(a))]), 5))
        piv = np.array([0, rt * math.sqrt(2)]); dip = rt * math.sin(deg(E["swing"]))
        def pol(r, a): return np.array([r * math.cos(deg(a)), r * math.sin(deg(a))])
        def pallet(A, sgn):                                                      # a wedge, drawn where it is when fully in, then turned back to the anchor at rest: tip, face, back
            w = [pol(rt - dip, A + E["face"] - 0.3), pol(rt + E["top"], A + E["face"]), pol(rt + E["top"], A + E["face"] - E["back"])]
            c, s_ = math.cos(deg(-sgn * E["swing"])), math.sin(deg(-sgn * E["swing"])); return [np.array([[c, -s_], [s_, c]]) @ (p - piv) for p in w]
        Te, Fe, Be = pallet(135.0, 1); Tx, Fx, Bx = pallet(45.0, -1)             # the entry pallet is in when the anchor is at +swing, the exit at -swing
        out.append((xy([Te, Fe, (0, 0.04), Bx, Tx, Fx, (0, -0.035), Be, Te]), 6))  # the anchor about its pivot: one outline
        out.append((circle(0.02, 6), 6))
        out.append((xy([(0, -0.035), (0, -E["pend"] + E["bob"])]), 6)); out.append((circle(E["bob"], 16, c=(0, -E["pend"], 0)), 6))    # the pendulum
        out.append((circle(0.012, 4, c=(0, -E["pend"], 0)), 6))
        pv = (E["w"][0], E["w"][1] + piv[1])
        out.append((xy([(pv[0] - 0.035, pv[1] + 0.04), (pv[0] - 0.07, pv[1] + 0.11), (pv[0] + 0.07, pv[1] + 0.11), (pv[0] + 0.035, pv[1] + 0.04)]), 4))   # the pivot's bracket
        out.append((circle(0.015, 4, c=(E["w"][0], E["w"][1], 0)), 4))
        return out
    @staticmethod
    def mats(t):
        E = ESC; ph = E["per_s"] * t; y = 2 * TAU * (ph - 0.25)
        st = (y - 4 / 3 * math.sin(y) + math.sin(2 * y) / 6) / TAU                # the staircase: 1 a half swing, flat (to the fifth order) at each extreme
        tooth = 135.0 + E["face"] + E["gap"] - 180.0 / E["teeth"] * st            # a tooth's tip, against the entry pallet's face at st = 0
        w = np.array([E["w"][0], E["w"][1], 0]); pv = w + np.array([0, E["rt"] * math.sqrt(2), 0])
        return {4: (I3, O3), 5: (rz(deg(tooth)), w), 6: (rz(deg(E["swing"]) * math.sin(TAU * ph)), pv)}

# ---------------- 8. an AC generator: a coil (5) turned by a crank between the poles of a magnet, its two ends on
# slip rings; two brushes take the voltage off to a chart, where it leaves as a sine wave (6) in step with the coil:
# zero when the coil lies across the field, greatest as its sides cut straight through.  The wave is the EM finale's
# trick: its vertices are stored (x, cos kx, sin kx), and the matrix's second row (0, A sin, -A cos) makes A sin(angle - kx). ----------------
GEN = dict(xc=-0.50, a=0.20, b=0.19, rings=(-0.19, -0.12), ring_r=0.05, lead=0.03, pole=0.27, rev_per_s=0.5, x0=0.06, len=0.86, wl=0.43, amp=0.25)
@proposal("generator", "AC generator", 7.0, "no new phase at 0.5/s (the coil on em, the view on pv)")
class Generator:
    @staticmethod
    def obj():
        G = GEN; xc, a, b, (r1, r2), rr, ld = G["xc"], G["a"], G["b"], G["rings"], G["ring_r"], G["lead"]; out = []
        out.append((np.array([[r1, 0, rr], [r1, 0, ld], [xc + a, 0, ld], [xc + a, 0, b], [xc - a, 0, b], [xc - a, 0, -b], [xc + a, 0, -b], [xc + a, 0, -ld], [r2, 0, -ld], [r2, 0, -rr]]), 5))   # the coil, ring to ring
        i = 0.03; out.append((np.array([[xc + a - i, 0, b - i], [xc - a + i, 0, b - i], [xc - a + i, 0, -b + i], [xc + a - i, 0, -b + i], [xc + a - i, 0, b - i]]), 5))                        # a second turn
        for r in (r1, r2): out.append((circle(rr, 10, "x", (r, 0, 0)), 5))
        out.append((np.array([[xc - a, 0, 0], [-0.84, 0, 0], [-0.84, 0, 0.12], [-0.93, 0, 0.12]]), 5))                                                                                    # the shaft and its crank
        p, zf, zb, zo, yo = G["pole"], -0.19, 0.30, 0.42, 0.41                   # the magnet: a C, its poles above and below the coil, its back behind
        C = [(zf, p), (zf, yo), (zo, yo), (zo, -yo), (zf, -yo), (zf, -p), (zb, -p), (zb, p), (zf, p)]
        for x in (xc - 0.15, xc + 0.15): out.append((np.array([[x, y, z] for z, y in C]), 4))
        for z, y in C[:-1]: out.append((np.array([[xc - 0.15, y, z], [xc + 0.15, y, z]]), 4))
        x0, x1 = G["x0"], G["x0"] + G["len"]
        out.append((xy([(r1, -rr), (r1, -0.21), (x0, -0.21)]), 4)); out.append((xy([(r2, -rr), (r2, -0.13), (x0, -0.13)]), 4))                                                        # the brushes and their wires
        out.append((rect(x0, x1, -0.33, 0.33), 4)); out.append((xy([(x0, 0), (x1, 0)]), 4))                                                                                             # the chart
        k = TAU / G["wl"]; x = np.linspace(0, G["len"], 33); out.append((np.column_stack([x, np.cos(k * x), np.sin(k * x)]), 6))
        return out
    @staticmethod
    def mats(t):
        G = GEN; V = view(t, -18.0, 22.0, 0.08); th = TAU * G["rev_per_s"] * t; A = G["amp"]
        W = np.array([[1, 0, 0], [0, A * math.sin(th), -A * math.cos(th)], [0, 0, 0]])
        return {4: (V, O3), 5: (V @ rx(th), O3), 6: (V @ W, V @ np.array([G["x0"], 0, 0]))}

# ---------------- 9. CartPole, the first problem of every control and reinforcement-learning course: a cart on a
# track keeps a pole on end by driving under it.  The cart's path is two sines; the pole's lean is what a pole of
# this length must do above that path (small angles: L th'' = g th - x'', so each sine of x gives the sine
# -a w^2 / (g + L w^2) of the lean: the pole leans in toward the middle, and the cart is always chasing it).
# One unit is two metres (g = 4.9 units/s^2): a tall pole, slow enough to follow.  Cart (5), wheels (6, 7: they roll, turned by x / r), pole (8). ----------------
CART = dict(track=-0.56, wheel=0.055, w=0.30, h=0.13, wx=0.09, L=0.85, a=(0.32, 0.16), f=(0.30, 0.50), g=4.9)
@proposal("cartpole", "CartPole", 7.0, "no new phase (the cart's two sines on gs, 0.3/s, and em, 0.5/s)")
class CartPole:
    @staticmethod
    def obj():
        K = CART; y0 = K["track"]; r = K["wheel"]; out = []
        out.append((xy([(-0.9, y0 + 0.07), (-0.9, y0), (0.9, y0), (0.9, y0 + 0.07)]), 4))        # the track, its stops, a scale under it
        for x in np.arange(-0.8, 0.81, 0.2): out.append((xy([(x, y0), (x, y0 - (0.06 if abs(x) < 1e-9 else 0.03))]), 4))
        out.append((rect(-K["w"] / 2, K["w"] / 2, 0, K["h"]), 5)); out.append((circle(0.022, 6, c=(0, K["h"], 0)), 5))
        for g in (6, 7):
            out.append((circle(r, 10), g)); out.append((xy([(-r, 0), (r, 0)]), g)); out.append((xy([(0, -r), (0, r)]), g))
        out.append((xy([(-0.012, 0.022), (-0.012, K["L"]), (0.012, K["L"]), (0.012, 0.022)]), 8)); out.append((circle(0.04, 10, c=(0, K["L"] + 0.04, 0)), 8))
        return out
    @staticmethod
    def state(t):
        K = CART; x = th = 0.0
        for a, f in zip(K["a"], K["f"]):
            w = TAU * f; s = math.sin(w * t); x += a * s; th += -a * w * w / (K["g"] + K["L"] * w * w) * s
        return x, th
    @staticmethod
    def mats(t):
        K = CART; x, th = CartPole.state(t); r = K["wheel"]; yw = K["track"] + r
        return {4: (I3, O3), 5: (I3, np.array([x, yw, 0])), 6: (rz(-x / r), np.array([x - K["wx"], yw, 0])), 7: (rz(-x / r), np.array([x + K["wx"], yw, 0])),
                8: (rz(-th), np.array([x, yw + K["h"], 0]))}

# ---------------- 10. the Tacoma Narrows bridge, 7 November 1940: in a steady wind the deck of the main span began
# to twist, the two halves opposite ways about a still point at mid-span, five seconds a cycle, growing until it
# tore.  Each side (5 near, 6 far) is stored (x, y, mode) with mode = sin(2 pi x / span): the matrix's second row
# (0, 1, +/-A) lifts one side as it drops the other, deck edge, hangers and cable together.  The floor beams (7) are
# stored (x, -/+mode, -/+w) and scaled in y by A.  A = the twist's sine times a slow rise.  Towers, side spans: 4. ----------------
BRIDGE = dict(tower=0.55, end=0.96, w=0.11, deck=-0.12, top=0.42, sag=0.05, foot=-0.52, n=16, twist=0.085, per_s=0.24, grow_s=9.0)
@proposal("bridge", "Tacoma Narrows bridge", 8.0, "1 new phase (the twist's growth from zero; the twist on o2, the view on pv)")
class Bridge:
    @staticmethod
    def cable(x): B = BRIDGE; return B["deck"] + B["sag"] + (B["top"] - B["deck"] - B["sag"]) * (x / B["tower"]) ** 2
    @staticmethod
    def obj():
        B = BRIDGE; T, w, yd, n = B["tower"], B["w"], B["deck"], B["n"]; out = []
        for s in (-1, 1):
            x = s * T
            out.append((np.array([[x, B["foot"], -w], [x, B["top"], -w], [x, B["top"], w], [x, B["foot"], w]]), 4))               # a tower: two legs, the top strut
            out.append((np.array([[x, yd - 0.03, -w], [x, yd - 0.03, w]]), 4)); out.append((np.array([[x, 0.2, -w], [x, 0.2, w]]), 4))
            for z in (-w, w):                                                                                                 # a side span: deck edge, cable, two hangers
                e = s * B["end"]; out.append((np.array([[x, yd, z], [e, yd, z]]), 4)); out.append((np.array([[x, B["top"], z], [e, yd, z]]), 4))
                for f in (1 / 3, 2 / 3): xh = x + f * (e - x); out.append((np.array([[xh, yd, z], [xh, B["top"] + f * (yd - B["top"]), z]]), 4))
            out.append((np.array([[s * B["end"], yd, -w], [s * B["end"], yd, w]]), 4))
        xs = np.linspace(-T, T, n + 1); mode = np.sin(TAU * (xs + T) / (2 * T)); mode[0] = mode[-1] = mode[n // 2] = 0.0
        for g in (5, 6):
            out.append((np.column_stack([xs, np.full(n + 1, yd), mode]), g)); out.append((np.column_stack([xs, Bridge.cable(xs), mode]), g))
            for i in range(1, n, 2):
                if Bridge.cable(xs[i]) - yd > 0.06: out.append((np.array([[xs[i], yd, mode[i]], [xs[i], Bridge.cable(xs[i]), mode[i]]]), g))
        for i in range(1, n): out.append((np.array([[xs[i], mode[i], -w], [xs[i], -mode[i], w]]), 7))
        return out
    @staticmethod
    def mats(t):
        B = BRIDGE; V = view(t, -20.0, 16.0, 0.07, 22.0); w = B["w"]
        A = B["twist"] * math.sin(TAU * B["per_s"] * t) * math.sin(TAU * t / (4 * B["grow_s"]))
        side = lambda s: np.array([[1, 0, 0], [0, 1, s * A], [0, 0, 0]])
        return {4: (V, O3), 5: (V @ side(1), V @ np.array([0, 0, -w])), 6: (V @ side(-1), V @ np.array([0, 0, w])),
                7: (V @ np.diag([1, A, 1]), V @ np.array([0, B["deck"], 0]))}

# ---------------- 11. a Galton board: a ball falls through eight rows of pegs and goes left or right at each, a coin
# flip a row; the bin it ends in counts its rights.  It starts with enough balls down that the bell is plain (a fixed
# sample of N, binomial, with its honest scatter) and the heap and its bell curve (5) grow by the few that fall
# while it runs: one matrix, a scale in y about the floor.  Six balls (6-11) are on their way at any moment, each a
# translation; their paths are what the gateware has no source for yet (a coin a row: an LFSR and a hop). ----------------
GALTON = dict(rows=8, dx=0.115, dy=0.078, top=0.55, floor=-0.68, bar=0.52, balls=6, r=0.02, enter_s=0.3, hop_s=0.22, fall_s=0.4, rest_s=0.14, seed=1907, n=200, grow=(0.9, 1.0), hatch=0.042)
@proposal("galton", "Galton board", 8.0, "NEW GATEWARE: a random path for each of 6 balls (an LFSR's coin a row, a hop between pegs); no new phase (the heap's growth on sl)")
class Galton:
    @staticmethod
    def counts():
        G = GALTON; rng = np.random.default_rng(G["seed"]); return np.bincount(rng.binomial(G["rows"], 0.5, G["n"]), minlength=G["rows"] + 1)
    @staticmethod
    def heights(): c = Galton.counts(); return GALTON["bar"] * c / c.max()
    @staticmethod
    def obj():
        G = GALTON; n, dx, dy, top = G["rows"], G["dx"], G["dy"], G["top"]; out = []
        for r in range(n):
            for j in range(r + 1): out.append((dot([(j - r / 2) * dx, top - r * dy, 0]), 4))          # the pegs
        yw = top - n * dy + 0.02; xe = (n + 1) / 2 * dx
        for k in range(n + 2): x = (k - (n + 1) / 2) * dx; out.append((xy([(x, yw if 0 < k < n + 1 else yw + 0.05), (x, G["floor"])]), 4))   # the bins' walls
        out.append((xy([(-xe, G["floor"]), (xe, G["floor"])]), 4))
        for s in (-1, 1): out.append((xy([(s * 0.22, top + 0.24), (s * 0.035, top + 0.07), (s * 0.035, top + 0.045)]), 4)); out.append((xy([(s * 0.10, top + 0.045), (s * xe, yw + 0.05)]), 4))   # the hopper, the sides
        h = Galton.heights(); st = []
        for k in range(n + 1): x0 = (k - (n + 1) / 2) * dx; st += [(x0, h[k]), (x0 + dx, h[k])]
        out.append((xy([(-xe, 0)] + st + [(xe, 0)]), 5))                                                 # the heap: a staircase, each bin's filled with a zigzag
        for k in range(n + 1):
            x0 = (k - (n + 1) / 2) * dx + 0.014; m = int(h[k] / G["hatch"])
            if m >= 1: out.append((xy([(x0 + (i % 2) * (dx - 0.028), h[k] * i / m) for i in range(m + 1)]), 5))
        c = Galton.counts(); x = np.linspace(-xe, xe, 25); k = x / dx + n / 2; sg2 = n / 4
        out.append((np.column_stack([x, G["bar"] * G["n"] / c.max() * np.exp(-(k - n / 2) ** 2 / (2 * sg2)) / math.sqrt(TAU * sg2), np.zeros(25)]), 5))   # the bell it tends to
        for b in range(G["balls"]): out.append((circle(G["r"], 6), 6 + b))
        return out
    @staticmethod
    def ball(b, t, scale):
        G = GALTON; n, dx, dy, top = G["rows"], G["dx"], G["dy"], G["top"]; per = G["enter_s"] + n * G["hop_s"] + G["fall_s"] + G["rest_s"]
        tt = t + b * per / G["balls"] + 0.37 * b; cyc = int(tt // per); tau = tt % per
        bits = np.random.default_rng([G["seed"], b, cyc]).integers(0, 2, n); up = G["r"] + 0.014
        if tau < G["enter_s"]: s = tau / G["enter_s"]; return np.array([0, top + 0.2 - (0.2 - up) * s * s, 0])
        tau -= G["enter_s"]; r = int(tau // G["hop_s"])
        if r < n:                                                                # a hop off peg r: up a little, then down to the next row, half a peg left or right
            s = tau / G["hop_s"] - r; x0 = (bits[:r].sum() - r / 2) * dx; y0 = top - r * dy + up; v = 0.7 * dy
            return np.array([x0 + (bits[r] - 0.5) * dx * s, y0 + v * s - (dy + v) * s * s, 0])
        tau -= n * G["hop_s"]; k = bits.sum(); x = (k - n / 2) * dx; y0 = top - n * dy + up; y1 = G["floor"] + scale * Galton.heights()[k] + G["r"]
        s = min(tau / G["fall_s"], 1.0); return np.array([x, y0 - (y0 - y1) * s * s, 0])
    @staticmethod
    def mats(t):
        G = GALTON; sc = G["grow"][0] + (G["grow"][1] - G["grow"][0]) * min(t / PROPOSALS["galton"]["seconds"], 1.0)
        m = {4: (I3, O3), 5: (np.diag([1, sc, 1]), np.array([0, G["floor"], 0]))}
        for b in range(G["balls"]): m[6 + b] = (I3, Galton.ball(b, t, sc))
        return m

# ---------------- 12. a circuit board: a processor, a memory, four small parts and a connector, the traces between
# them at 45 degrees, and the charge moving in the traces as beads (a short bar across the trace: a point is lost
# in the trace's own light).  All the beads moving one way (of eight) are one group, and a group only slides one dot spacing along its direction on a sawtooth: at
# the wrap each dot is where the next one started.  So that a dot turns a corner exactly at the wrap, every corner
# of a trace is a whole number of spacings from its first; the ends need not be (a dot comes out of a part's body
# or goes on into one, half a spacing).  One unit: the pins' pitch; a dot every two. ----------------
PCB = dict(u=0.07, pin=0.035, via=0.016, bead=0.017, per_s=0.9, shift=0.05, scale=0.86, tilt=36.0, swing=13.0, sma_x=-0.87, edge=-0.94)
_D8 = [np.array(v, float) / np.linalg.norm(v) for v in ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))]
_E, _NE, _N, _NW, _W, _SW, _S, _SE = range(8)
def _pcb_traces():
    """(start, [(direction, units)...], flow, what it ends on): flow +1 start to end, -1 back"""
    T = []
    for y, f in ((0.105, 1), (0.035, -1), (-0.035, 1), (-0.105, -1)): T.append(((0.01, y), [(_E, 2), (_NE, 2), (_E, 3)], f, "chip"))       # the bus to the memory
    T += [((-0.305, 0.21), [(_N, 1), (_NW, 2), (_W, 2)], -1, "chip"), ((-0.235, 0.21), [(_N, 2), (_NW, 2), (_W, 3)], 1, "chip"),
          ((-0.165, 0.21), [(_N, 2), (_NE, 2), (_E, 4)], 1, "chip"), ((-0.095, 0.21), [(_N, 1), (_NE, 2), (_E, 3)], -1, "chip"),
          ((-0.305, -0.21), [(_S, 1), (_SW, 2), (_W, 2)], 1, "chip"), ((-0.235, -0.21), [(_S, 2), (_SW, 2), (_W, 3)], -1, "chip"),
          ((-0.165, -0.21), [(_S, 2), (_SE, 2), (_E, 7)], -1, "chip"), ((-0.095, -0.21), [(_S, 1), (_SE, 2), (_E, 6)], 1, "chip"),
          ((-0.41, 0.105), [(_W, 1), (_NW, 4), (_W, 2)], -1, "sma"), ((-0.41, 0.035), [(_W, 2), (_NW, 2), (_W, 2)], -1, "sma"),      # two SMAs in (the ADCs')
          ((-0.41, -0.035), [(_W, 2), (_SW, 2), (_W, 2)], 1, "sma"), ((-0.41, -0.105), [(_W, 1), (_SW, 4), (_W, 2)], 1, "sma"),      # and two out (the DACs')
          ((0.485, 0.449), [(_E, 4)], 1, "via"), ((0.485, 0.379), [(_E, 2)], -1, "via"), ((0.695, -0.379), [(_E, 2)], 1, "via"), ((0.695, -0.449), [(_E, 2)], -1, "via")]
    return T
def _pcb_path(start, segs):
    p = [np.array(start, float)]
    for d, n in segs: p.append(p[-1] + n * PCB["u"] * _D8[d])
    return p
def _pcb_dots(start, segs, flow):
    """the dots' homes and directions: every second unit along the flow, in step with the trace's corners"""
    if flow < 0: start = _pcb_path(start, segs)[-1]; segs = [((d + 4) % 8, n) for d, n in reversed(segs)]
    assert all(n % 2 == 0 for d, n in segs[1:-1]), "a corner off the dots' step"
    p = _pcb_path(start, segs); L = sum(n for d, n in segs); s = -(segs[0][1] % 2) if len(segs) > 1 else 0; out = []
    while s <= L - 1:
        acc = 0
        for i, (d, n) in enumerate(segs):
            if s < acc + n or i == len(segs) - 1: break
            acc += n
        out.append((p[i] + (s - acc) * PCB["u"] * _D8[d], d)); s += 2
    return out
@proposal("pcb", "circuit board", 8.0, "1 new phase (the beads' step, 0.9/s; or none on em at half the speed); the view on pv")
class Pcb:
    @staticmethod
    def obj():
        K = PCB; out = []; pin = K["pin"]; sh = np.array([K["shift"], 0.0])
        def add(pts, g=4): out.append((xy((np.asarray(pts, float) + sh) * K["scale"]), g))
        for start, segs, flow, end in _pcb_traces():
            p = _pcb_path(start, segs); line = [p[0] - pin * _D8[segs[0][0]]] + p                    # a pin of the part it leaves, the trace
            if end == "chip": line.append(p[-1] + pin * _D8[segs[-1][0]])
            elif end == "sma": line.append(np.array([K["sma_x"], p[-1][1]])); out += Pcb.sma(p[-1][1])
            else: out.append((circle(K["via"] * K["scale"], 5, c=np.append((p[-1] + sh) * K["scale"], 0)), 4))
            add(line)
            for q, d in _pcb_dots(start, segs, flow): w = K["bead"] * _D8[(d + 2) % 8]; add([q - w, q + w], 5 + d)
        R = lambda x0, x1, y0, y1: add([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
        R(-0.375, -0.025, -0.175, 0.175); out.append((circle(0.014 * K["scale"], 5, c=np.append((np.array([-0.335, 0.135]) + sh) * K["scale"], 0)), 4))   # the processor, its pin-1 mark
        R(0.494, 0.72, -0.056, 0.254)                                                                # the memory, its far pins
        for y in (-0.006, 0.064, 0.134, 0.204): add([(0.72, y), (0.72 + pin, y)])
        R(0.249, 0.45, 0.334, 0.494); R(0.459, 0.66, -0.494, -0.334)                                 # the small parts on the right
        for sy in (1, -1):                                                                           # ... and on the left, their far pins
            R(-0.745, -0.579, sy * 0.334, sy * 0.494)
            for y in (0.379, 0.449): add([(-0.745, sy * y), (-0.745 - pin, sy * y)])
        a, b, c = 0.94, 0.60, 0.05; add([(-a + c, -b), (a - c, -b), (a, -b + c), (a, b - c), (a - c, b), (-a + c, b), (-a, b - c), (-a, -b + c), (-a + c, -b)])   # the board
        return out
    @staticmethod
    def sma(y):
        """an edge-launch SMA on the board's left edge at height y: its flange on the board, the hex nut at the edge, the
        barrel out past it (the board's own coordinates, before the shift and scale)"""
        K = PCB; e = K["edge"]; sh = np.array([K["shift"], 0.0, 0.0]); k = K["scale"]; out = []
        def put(pts): out.append(((np.asarray(pts, float) + sh) * k, 4))
        put(xy([(K["sma_x"], y - 0.035), (e, y - 0.035), (e, y + 0.035), (K["sma_x"], y + 0.035), (K["sma_x"], y - 0.035)]))
        put(circle(0.036, 6, "x", (e - 0.012, y, 0)))
        put(circle(0.026, 8, "x", (e - 0.09, y, 0)))
        for dy in (-0.026, 0.026): put(xy([(e - 0.012, y + dy), (e - 0.09, y + dy)]))
        return out
    @staticmethod
    def mats(t):
        K = PCB; V = rx(deg(K["tilt"])) @ ry(deg(K["swing"]) * math.sin(TAU * 0.08 * t)); step = 2 * K["u"] * K["scale"] * saw(t, K["per_s"])
        m = {4: (V, O3)}
        for d in range(8): m[5 + d] = (V, V @ np.append(step * _D8[d], 0))
        return m

# ---------------- 13. the fidget spinner the college gives away: three lobes, a bearing in each, about a cap held
# between finger and thumb.  The cap (4) is still and carries the college's logo, the three stacked words, here in
# the show's stroke font, each row spread to the block's width and the rows' heights in the logo's proportions
# (36 : 48 : 32, the block 128 wide).  The body (5) is at rest, is flicked, blurs, and coasts down to rest a lobe up:
# its rate rises in a quarter second and falls in a straight line, so the angle is two parabolas. ----------------
SPIN = dict(d=0.50, lobe=0.24, c=0.58, cap=0.25, rings=((0.15, 14), (0.07, 8)), block=0.30, rest=0.5, flick=0.25, stop=6.5, turns=9 + 2 / 3)
@proposal("spinner", "HMC fidget spinner", 7.6, "NEW GATEWARE: a phase whose rate ramps (up in the flick, down to nothing); nothing else")
class Spinner:
    @staticmethod
    def logo():
        from vector import FONT
        S = SPIN; W = S["block"]; k = W / 128.0; rows = (("HARVEY", 36), ("MUDD", 48), ("COLLEGE", 32)); gaps = (8, 7); out = []
        y = (36 + 8 + 48 + 7 + 32) * k / 2
        for i, (word, h) in enumerate(rows):
            h *= k; y -= h; n = len(word); ux = W / (4 * n + 1.3 * (n - 1))                           # a glyph is 4 x 6; 1.3 between glyphs
            for j, ch in enumerate(word):
                x0 = -W / 2 + j * 5.3 * ux
                for pl in FONT[ch]: out.append(xy([(x0 + px * ux, y + py * h / 6) for px, py in pl]))
            if i < 2: y -= gaps[i] * k
        return out
    @staticmethod
    def outline():
        S = SPIN; d, c, R1 = S["d"], S["c"], S["lobe"]; Rf = math.sqrt(c * c + d * d - c * d) - R1; pts = []
        al = math.degrees(math.atan2(c * math.sin(deg(60)), c * math.cos(deg(60)) - d))               # from a lobe's centre to the fillet beside it
        be = math.degrees(math.atan2(d * math.sin(deg(60)), d * math.cos(deg(60)) - c))               # from a fillet's centre to the lobe beside it
        for k in range(3):
            a = 90.0 + 120.0 * k
            pts += [(d * math.cos(deg(a)) + R1 * math.cos(deg(a + x)), d * math.sin(deg(a)) + R1 * math.sin(deg(a + x))) for x in np.linspace(-al, al, 13)]
            b = a + 60.0
            pts += [(c * math.cos(deg(b)) + Rf * math.cos(deg(b + x)), c * math.sin(deg(b)) + Rf * math.sin(deg(b + x))) for x in np.linspace(360 - be, be, 6)[1:-1]]
        return xy(pts + [pts[0]])
    @staticmethod
    def obj():
        S = SPIN; out = [(Spinner.outline(), 5)]
        for k in range(3):
            a = deg(90.0 + 120.0 * k); c = (S["d"] * math.cos(a), S["d"] * math.sin(a), 0)
            for r, n in S["rings"]: out.append((circle(r, n, c=c), 5))
        out.append((circle(S["cap"], 24), 4)); out += [(pl, 4) for pl in Spinner.logo()]
        return out
    @staticmethod
    def ramp():
        """The gateware's ramp (show_seq.v): from the finale's start, each millisecond the phase goes on by the rate w (2^32
        a turn), and then w is 0 for T0 ms, grows by UP for T1 ms, and falls by DN until it is 0.  UP sets the top speed;
        DN is chosen so that it comes to rest after `turns` turns to the nearest part in 2^32 (a third of a turn on from
        where it started looks the same, a lobe up)."""
        S = SPIN; T0, T1, T2 = int(S["rest"] * 1000), int(S["flick"] * 1000), int((S["stop"] - S["rest"] - S["flick"]) * 1000)
        w0 = S["turns"] / ((S["flick"] + S["stop"] - S["rest"] - S["flick"]) / 2) / 1000 * 2 ** 32     # turns a ms at the top, x 2^32
        UP = int(round(w0 / T1)); wmax = UP * T1; target = int(round(S["turns"] * 2 ** 32))
        DN = max(1, int(round(wmax / T2)))
        best = min(range(max(1, DN - 400), DN + 400), key=lambda d: abs(Spinner.ramp_sum(T0, T1, UP, d) - target))
        return dict(T0=T0, T1=T1, UP=UP, DN=best)
    @staticmethod
    def ramp_sum(T0, T1, UP, DN, n_ms=None):
        """the phase (x 2^32, not wrapped) after n_ms milliseconds of the ramp (all of it if None), as the gateware adds it"""
        w = 0; ph = 0; i = 0
        while (n_ms is None and (i < T0 + T1 or w > 0)) or (n_ms is not None and i < n_ms):
            ph += w
            w = 0 if i < T0 else w + UP if i < T0 + T1 else (w - DN if w > DN else 0)
            i += 1
        return ph
    _cache = {}
    @staticmethod
    def turns(t):
        r = Spinner._cache.get("r") or Spinner._cache.setdefault("r", Spinner.ramp())
        return Spinner.ramp_sum(r["T0"], r["T1"], r["UP"], r["DN"], int(t * 1000)) / 2 ** 32
    @staticmethod
    def mats(t): return {4: (I3, O3), 5: (rz(-TAU * Spinner.turns(t)), O3)}

# ---------------- 14. an oscilloscope showing an oscilloscope: the Tektronix 2235 propped on its carrying handle (its
# hubs on the sides, the arms swung down under the front, the front raised), and on its screen an XY drawing of the
# same scope, whose screen shows a smaller one, and so on, four levels.  Each drawing is the scope as the viewer sees
# it, flattened onto the screen of the one around it: level k + 1 = level k's matrix x (the screen's frame, scaled,
# flattened) x the view, so every level turns as the outer one does.  The view swings slowly (pv).  Level 0 (group 4)
# is 3D with its knobs; the inner ones (5, 6, 7) lose detail as they shrink. ----------------
TEK = dict(w=1.0, h=0.42, d=0.8, tilt=11.0, bezel=(-0.495, -0.035, -0.2, 0.2), screen=(-0.47, -0.06, -0.175, 0.175), zf=-0.03,
           hub=(0.30, 0.0, 0.11), bar=(-0.13, 0.06), size=1.36, view_tilt=-15.0, view_off=-21.0, swing=11.0, levels=4, fill=0.94)
class Tek:
    @staticmethod
    def frame():
        """the body's tilt (front up) about its back-bottom edge, then centred: model -> drawn"""
        T = TEK; c, s_ = math.cos(deg(T["tilt"])), math.sin(deg(T["tilt"])); R = np.array([[1, 0, 0], [0, c, -s_], [0, s_, c]])
        pivot = np.array([0, -T["h"] / 2, T["d"]]); return R, pivot
    @staticmethod
    def raw(level):
        """the scope in its own frame (front face z = 0 facing -z, the body to +z), tilted; level 0 has every detail"""
        T = TEK; w, h, d = T["w"] / 2, T["h"] / 2, T["d"]; R, pv_ = Tek.frame(); out = []
        def put(pts): out.append((np.asarray(pts, float) - pv_) @ R.T + pv_)
        if level <= 2:
            for pl in box(-w, w, -h, h, 0.0, d): put(pl)
        else: put([[-w, -h, 0], [w, -h, 0], [w, h, 0], [-w, h, 0], [-w, -h, 0]])
        x0, x1, y0, y1 = T["bezel"]; zf = T["zf"]
        if level <= 1: put([[x0, y0, zf], [x1, y0, zf], [x1, y1, zf], [x0, y1, zf], [x0, y0, zf]])
        x0, x1, y0, y1 = T["screen"]; put([[x0, y0, zf], [x1, y0, zf], [x1, y1, zf], [x0, y1, zf], [x0, y0, zf]])
        if level == 0:                                                       # the knobs: VOLTS/DIV x 2, SEC/DIV, and the small ones above
            for x, y, r, n in ((0.06, -0.05, 0.055, 12), (0.22, -0.05, 0.055, 12), (0.39, -0.05, 0.06, 12),
                               (0.02, 0.12, 0.024, 6), (0.12, 0.12, 0.024, 6), (0.24, 0.12, 0.024, 6), (0.36, 0.12, 0.024, 6), (0.45, 0.12, 0.024, 6)):
                put(circle(r, n, "z", (x, y, zf)))
            for x in (0.06, 0.22): put(circle(0.022, 6, "z", (x, -0.16, zf)))           # the CH 1 and CH 2 inputs
        elif level == 1:
            for x, y, r in ((0.06, -0.05, 0.055), (0.22, -0.05, 0.055), (0.39, -0.05, 0.06)): put(circle(r, 6, "z", (x, y, zf)))
        # the handle: a hub on each side, the arms down and forward to the bar on the bench in front
        hz, hy, hr = T["hub"]; bz, by = T["bar"]
        Rt, pv2 = Tek.frame(); hub_w = lambda sx: ((np.array([sx * w, hy, hz]) - pv2) @ Rt.T + pv2)
        floor = (np.array([0, -h, d]))[1]                                      # the back-bottom edge stays on the bench
        for sx in (-1, 1):
            if level <= 1 and sx < 0: out.append(circle(hr, 12 if level == 0 else 8, "x", hub_w(sx)))      # the near hub (the far one is behind the body)
            hw_ = hub_w(sx); foot = np.array([sx * (w + 0.03), floor, bz])
            if level == 0:                                                     # an arm: a flat bar from the hub to the bench
                out.append(np.array([hw_ + [sx * 0.03, 0.03, -0.03], foot + [0, 0.05, 0.0], foot + [0, 0.0, 0.05], hw_ + [sx * 0.03, -0.03, 0.03]]))
            else: out.append(np.array([hw_ + [sx * 0.03, 0, 0], foot]))
        if level == 0:                                                         # the bar on the bench, its two edges
            out.append(np.array([[-(w + 0.03), floor + 0.05, bz], [w + 0.03, floor + 0.05, bz]])); out.append(np.array([[-(w + 0.03), floor, bz + 0.05], [w + 0.03, floor, bz + 0.05]]))
        elif level <= 2: out.append(np.array([[-(w + 0.03), floor, bz], [w + 0.03, floor, bz]]))
        return out
    @staticmethod
    def centre():
        pts = np.vstack(Tek.raw(0)); return (pts.max(0) + pts.min(0)) / 2
    @staticmethod
    def model(level):
        """centred and scaled to TEK['size']"""
        c = Tek.centre(); k = TEK["size"] / np.ptp(np.vstack(Tek.raw(0))[:, 0]); return [(pl - c) * k for pl in Tek.raw(level)]
    @staticmethod
    def screen_frame():
        """the screen's centre and its in-plane axes, in the model's (centred, scaled) frame"""
        T = TEK; R, pv_ = Tek.frame(); c = Tek.centre(); k = T["size"] / np.ptp(np.vstack(Tek.raw(0))[:, 0])
        x0, x1, y0, y1 = T["screen"]; ctr = (np.array([(x0 + x1) / 2, (y0 + y1) / 2, T["zf"]]) - pv_) @ R.T + pv_
        return (ctr - c) * k, R @ np.array([1.0, 0, 0]), R @ np.array([0, 1.0, 0]), (x1 - x0) * k, (y1 - y0) * k
    @staticmethod
    def nest_scale():
        """the largest the flattened scope fits the screen at, over the view's swing"""
        T = TEK; ctr, e1, e2, sw, sh = Tek.screen_frame(); pts = np.vstack(Tek.model(0)); best = 9.0
        for ph in np.linspace(0, 1, 49):
            V = rx(deg(T["view_tilt"])) @ ry(deg(T["view_off"] + T["swing"] * math.sin(TAU * ph))); q = pts @ V.T
            best = min(best, sw / np.ptp(q[:, 0]), sh / np.ptp(q[:, 1]))
        return best * T["fill"]
    @staticmethod
    def obj():
        out = []
        for lv in range(TEK["levels"]): out += [(pl, 4 + lv) for pl in Tek.model(lv)]
        return out
    @staticmethod
    def mats(t):
        T = TEK; V = rx(deg(T["view_tilt"])) @ ry(deg(T["view_off"] + T["swing"] * math.sin(TAU * 0.08 * t)))
        ctr, e1, e2, sw, sh = Tek.screen_frame(); s_ = Tek.nest_scale(); C = s_ * np.column_stack([e1, e2, np.zeros(3)])
        m = {4: (V, O3)}; R, tt = V, O3
        for lv in range(1, T["levels"]): tt = tt + R @ ctr; R = R @ C @ V; m[4 + lv] = (R, tt)
        return m
proposal("tek", "oscilloscope in an oscilloscope", 7.0, "no new phase (the view on pv); 4 groups")(Tek)
