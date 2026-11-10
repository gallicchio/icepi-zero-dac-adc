#!/usr/bin/env python3
"""The finales' objects: 3D polylines in their own frames (scene units: the screen is x -1..1, y -0.8..0.8), each with
the matrix group its vertices are transformed by.  The animator (host/gen_matrix_prog.py) writes a matrix per group
each frame, so an object moves as a whole, and a moving part is a group of its own.

Groups: 0 the seal  1 the globe (the Earth of the satellites too)  2 the Lorenz ring  3 free (it was the labels')
4-15 the finales', re-used by each finale: a tumbling object (the molecules, the knot) 4; DNA 5;
the gears: sun 6, planets 7 8 9, the ring gear and rim 10; the arm: base 11, links 12-15; the EM wave: axis 4,
E 5, B 6; the lens: lens, rays, axis 4, plane wavefronts 5-9, converging wavefronts 10-14; the dish: dish, feed,
stand 4, wavefronts 5-10; the satellites: orbits 4, satellites 5 6 7."""
import os, sys, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import scene
def circle(r, n=16, axis="z", c=(0, 0, 0)):
    t = np.linspace(0, 2 * np.pi, n + 1); a, b = r * np.cos(t), r * np.sin(t); z = np.zeros(n + 1)
    p = {"z": np.column_stack([a, b, z]), "x": np.column_stack([z, a, b]), "y": np.column_stack([b, z, a])}[axis]
    return p + np.array(c)
def seg(a, b): return np.array([a, b], float)
def box(x0, x1, y0, y1, z0, z1):
    a = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z0]]
    b = [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1], [x0, y0, z1]]
    return [np.array(a), np.array(b)] + [np.array([a[i], b[i]]) for i in range(4)]

# ---------------- molecules: PubChem 3D SDF files (public domain), bonds as lines, atoms as small rings ----------------
ATOM_R = {"H": 0.012, "C": 0.03, "N": 0.034, "O": 0.034, "S": 0.04, "P": 0.04}
TUMBLE_R = 0.66            # a tumbling object fits a sphere of this radius: it stays on the screen whichever way it turns
def molecule(sdf, group=4, ring_n=4):
    lines = open(sdf).read().splitlines()
    na, nb = int(lines[3][:3]), int(lines[3][3:6])
    atoms = [(np.array([float(l[0:10]), float(l[10:20]), float(l[20:30])]), l[31:34].strip()) for l in lines[4:4 + na]]
    bonds = [(int(l[:3]) - 1, int(l[3:6]) - 1) for l in lines[4 + na:4 + na + nb]]
    xyz = np.array([a[0] for a in atoms]); xyz -= xyz.mean(0)
    w, v = np.linalg.eigh(np.cov(xyz.T)); xyz = xyz @ v[:, ::-1]        # the long axes first
    xyz *= (TUMBLE_R - 0.04) / np.linalg.norm(xyz, axis=1).max()
    out = [(seg(xyz[i], xyz[j]), group) for i, j in bonds]
    th = np.linspace(0, 2 * np.pi, ring_n + 1)
    for p, (_, el) in zip(xyz, atoms):
        r = ATOM_R.get(el, 0.03)
        out.append((np.column_stack([p[0] + r * np.cos(th), p[1] + r * np.sin(th), np.full(ring_n + 1, p[2])]), group))
    return out
def caffeine(): return molecule(os.path.join(HERE, "caffeine.sdf"))
def lsd(): return molecule(os.path.join(HERE, "lsd.sdf"))

# ---------------- DNA: two backbones and the base pairs, the axis along y, B-DNA's proportions ----------------
def dna(turns=2.5, height=1.4, radius=0.26, per_turn=40, rungs_per_turn=10, group=5):
    n = int(turns * per_turn); t = np.linspace(0, turns * 2 * np.pi, n); y = np.linspace(-height / 2, height / 2, n)
    s1 = np.column_stack([radius * np.cos(t), y, radius * np.sin(t)])
    s2 = np.column_stack([radius * np.cos(t + 2.2), y, radius * np.sin(t + 2.2)])    # the minor groove: 126 degrees
    out = [(s1, group), (s2, group)]
    for k in range(int(turns * rungs_per_turn)):
        i = int(k * per_turn / rungs_per_turn)
        if i < n: out.append((seg(s1[i], s2[i]), group))
    return out

# ---------------- a trefoil knot ----------------
def trefoil(n=180, group=4):
    t = np.linspace(0, 2 * np.pi, n + 1)
    p = np.column_stack([np.sin(t) + 2 * np.sin(2 * t), np.cos(t) - 2 * np.cos(2 * t), -np.sin(3 * t)])
    return [(p / np.linalg.norm(p, axis=1).max() * (TUMBLE_R - 0.04), group)]

# ---------------- a planetary gear train in the xy plane: the ring gear fixed, the sun driven, the carrier free ----------------
GEARS = dict(zs=12, zp=9, zr=30, module=0.036)      # teeth: sun, planet, ring (zr = zs + 2 zp); pitch radius = module x teeth / 2
def gear(z, module, internal=False, hub=0.0, phase=0.0):
    """The outline: a tooth centred on every pitch angle (the first at `phase` turns), the gaps between."""
    rp = module * z / 2
    ra, rd = (rp + 0.9 * module, rp - 1.1 * module) if not internal else (rp - 0.9 * module, rp + 1.1 * module)
    pts = []
    for k in range(z):
        a = 2 * np.pi * (k / z + phase); w = 2 * np.pi / z
        for f, rr in ((-0.10, ra), (0.10, ra), (0.22, rd), (0.78, rd)):
            pts.append([rr * np.cos(a + f * w), rr * np.sin(a + f * w), 0])
    pts.append(pts[0]); out = [np.array(pts)]
    if hub > 0: out.append(circle(hub, 16))
    return out
def gear_constants():
    """The carrier's rate over the sun's, the planets' spin (absolute) over the sun's, the carrier radius, the planets' rest angles."""
    g = GEARS; zs, zp, zr = g["zs"], g["zp"], g["zr"]; cr = zs / (zs + zr)
    return dict(carrier_ratio=cr, planet_ratio=cr - zs / zp * (1 - cr), carrier_r=g["module"] * (zs + zp) / 2, rim_r=g["module"] * zr / 2 + 1.1 * g["module"] + 0.04)
def gears():
    g = GEARS; m = g["module"]; c = gear_constants()
    out = [(p, 6) for p in gear(g["zs"], m, hub=0.05)]
    # planet k sits at carrier angle k/3 with its own spin k/3 (a gap toward the sun, a tooth toward the ring); its outline is
    # stored unspun, the animator spins it, so all three are the same shape
    for k in range(3): out += [(p, 7 + k) for p in gear(g["zp"], m, hub=0.03)]
    out += [(p, 10) for p in gear(g["zr"], m, internal=True, phase=0.5 / g["zr"])]      # the ring: a gap at angle 0, facing planet 0's tooth
    out.append((circle(c["rim_r"], 48), 10))
    return out

# ---------------- a five-joint arm in the proportions of the LeRobot SO-100: base yaw, shoulder, elbow, wrist pitch, wrist roll with the gripper ----------------
ARM = dict(base_h=0.1125, l1=0.3875, l2=0.3375, l3=0.1125, grip=0.10, w=0.069)   # the largest that stays on the screen over a turn of the viewpoint, with the shoulder up    # the full reach stays within 0.85 of the base with perspective
def arm():
    A = ARM; w = A["w"]; out = []
    out += [(p, 11) for p in box(-0.14, 0.14, -0.03, 0.0, -0.14, 0.14)]                 # the base plate
    out.append((circle(0.11, 24, "y"), 11))
    out += [(p, 12) for p in box(-w, w, 0.0, A["base_h"], -w, w)]                      # the housing that yaws
    out += [(p, 13) for p in box(0.0, A["l1"], -w / 2, w / 2, -w / 2, w / 2)]          # the upper arm, along +x from the shoulder
    out += [(p, 14) for p in box(0.0, A["l2"], -w / 2.4, w / 2.4, -w / 2.4, w / 2.4)]  # the forearm
    out += [(p, 15) for p in box(0.0, A["l3"], -w / 3, w / 3, -w / 3, w / 3)]          # the wrist
    for s in (-1, 1): out += [(p, 15) for p in box(A["l3"], A["l3"] + A["grip"], -w / 6, w / 6, s * w / 3, s * (w / 3 - 0.02))]   # the fingers
    return out

# ---------------- a travelling electromagnetic wave: E and B as sinusoids with arrows, in quadrature planes ----------------
# The stored vertex of a wave point at x is (x, cos kx, sin kx): the animator's matrix for the E group makes y = sin kx cos wt -
# cos kx sin wt = sin(kx - wt) and z = 0, so the wave travels with no vertex changing; the B group the same into z.
EM = dict(half_len=0.72, amp=0.36, waves=2.0, n=96, arrows=16)      # within 0.85 of the centre with perspective, so the Icepi pair (scaled 0.9) never clips
def em_wave():
    e = EM; x = np.linspace(-e["half_len"], e["half_len"], e["n"]); k = 2 * np.pi * e["waves"] / (2 * e["half_len"])
    wave = np.column_stack([x, e["amp"] * np.cos(k * x), e["amp"] * np.sin(k * x)])
    out = [(seg([-e["half_len"], 0, 0], [e["half_len"], 0, 0]), 4), (wave, 5), (wave.copy(), 6)]
    for xi in np.linspace(-e["half_len"], e["half_len"], e["arrows"]):
        a = [xi, 0, 0]; b = [xi, e["amp"] * np.cos(k * xi), e["amp"] * np.sin(k * xi)]
        out.append((seg(a, b), 5)); out.append((seg(a, b), 6))
    return out

# ---------------- the refracting telescope as it stands at the table: the William Optics tube (the dew shield wider than
# the tube, the objective at the right), the red rack-and-pinion focuser with its knobs, the adapter, the optics cage
# behind it (four posts, the plates, a beam-splitter cube, a branch going up) and the camera at the far left, on the
# pier of the mount; light comes in from the right as dashes along parallel rays and converges through the tube and the
# cage to the focus in the camera ----------------
SCOPE = dict(x_obj=0.50, r_lens=0.10, r_tube=0.10, r_dew=0.125, x_dew=0.28, x_back=-0.12, r_foc=0.065, x_foc=-0.26, r_draw=0.05, x_draw=-0.36,
             cage=(-0.36, -0.60, 0.08), x_cam=(-0.62, -0.78), r_cam=0.07, x_focus=-0.70, x_in=0.85, dash=0.05, n_rays=6, r_rays=0.075, n_fronts=5)
def cyl(x0, x1, r, n=12, lines=6):
    out = [circle(r, n, "x", (x0, 0, 0)), circle(r, n, "x", (x1, 0, 0))]
    for a in np.linspace(0, 2 * np.pi, lines, endpoint=False): out.append(seg([x0, r * np.cos(a), r * np.sin(a)], [x1, r * np.cos(a), r * np.sin(a)]))
    return out
def telescope():
    T = SCOPE; out = []
    out += [(p, 4) for p in cyl(T["x_obj"], T["x_dew"], T["r_dew"], 12, 6)]                    # the dew shield
    out.append((circle(T["r_lens"], 12, "x", (T["x_obj"], 0, 0)), 4))                           # the objective
    out += [(p, 4) for p in cyl(T["x_dew"], T["x_back"], T["r_tube"], 12, 6)]                  # the tube
    for x in (0.2, 0.0): out.append((circle(T["r_tube"] + 0.012, 12, "x", (x, 0, 0)), 4))      # the tube rings
    out += [(p, 4) for p in cyl(T["x_back"], T["x_foc"], T["r_foc"], 12, 4)]                   # the focuser
    for sgn in (1, -1):                                                                        # its knobs
        out.append((circle(0.03, 10, "z", (T["x_foc"] + 0.06, 0, sgn * (T["r_foc"] + 0.025))), 4))
        out.append((seg([T["x_foc"] + 0.06, 0, sgn * T["r_foc"]], [T["x_foc"] + 0.06, 0, sgn * (T["r_foc"] + 0.025)]), 4))
    out += [(p, 4) for p in cyl(T["x_foc"], T["x_draw"], T["r_draw"], 10, 4)]                  # the adapter
    x0, x1, h = T["cage"]                                                                        # the cage: plates and posts
    for x in (x0, x1): out.append((np.array([[x, -h, -h], [x, h, -h], [x, h, h], [x, -h, h], [x, -h, -h]]), 4))
    for yy in (-h, h):
        for zz in (-h, h): out.append((seg([x0, yy, zz], [x1, yy, zz]), 4))
    xc = (x0 + x1) / 2
    out += [(p, 4) for p in box(xc - 0.03, xc + 0.03, -0.03, 0.03, -0.03, 0.03)]               # the beam-splitter cube
    out.append((seg([xc - 0.03, -0.03, 0.03], [xc + 0.03, 0.03, 0.03]), 4))
    yt = 0.26                                                                                    # the branch going up: posts and a plate
    for zz in (-h, h):
        for dx in (-h, h): out.append((seg([xc + dx, h, zz], [xc + dx, yt, zz]), 4))
    out.append((np.array([[xc - h, yt, -h], [xc + h, yt, -h], [xc + h, yt, h], [xc - h, yt, h], [xc - h, yt, -h]]), 4))
    out += [(p, 4) for p in cyl(xc - 0.02, xc + 0.02, 0.025, 8, 4)]                            # a mirror mount in the branch
    xa, xb = T["x_cam"]
    out += [(p, 4) for p in cyl(x1, xa, 0.03, 8, 4)]                                            # the camera's nose
    out += [(p, 4) for p in cyl(xa, xb, T["r_cam"], 12, 6)]                                     # the camera
    out += [(p, 4) for p in box(T["x_back"] - 0.02, T["x_back"] + 0.06, -0.6, -T["r_foc"] - 0.03, -0.04, 0.04)]   # the pier
    out += [(p, 4) for p in box(T["x_back"] - 0.06, T["x_back"] + 0.10, -T["r_foc"] - 0.03, -T["r_foc"], -0.06, 0.06)]   # the saddle
    out.append((circle(0.11, 12, "y", (T["x_back"] + 0.02, -0.6, 0)), 4))                       # the base
    # the light: on each of n_rays rays (a ring inside the objective) a dash; outside, group 5 + k slides in along x
    # (x = x_in + L u_k, L negative: toward the objective); inside, group 10 + k, stored about the focus, is scaled by
    # (1 - u_k): it slides to the focus
    F = np.array([T["x_focus"], 0, 0]); d = T["dash"]
    for k in range(T["n_fronts"]):
        for a in np.linspace(0, 2 * np.pi, T["n_rays"], endpoint=False):
            y, z = T["r_rays"] * np.cos(a), T["r_rays"] * np.sin(a)
            out.append((seg([-d / 2, y, z], [d / 2, y, z]), 5 + k))
            P = np.array([T["x_obj"], y, z]) - F; L = np.linalg.norm(P)
            out.append((seg(P, P * (1 - d / L)), 10 + k))
    return out
def scope_constants():
    T = SCOPE; d = T["dash"]
    return dict(x_out0=T["x_in"] - d / 2, l_out=(T["x_obj"] + d / 2) - (T["x_in"] - d / 2), x_focus=T["x_focus"])

# ---------------- polarization: one wave along x, vertical, through a quarter-wave plate in the middle (its axes at 45
# degrees), after which it is circular: a helix.  Two wave groups (5, 6), each stored as (x, cos kx, sin kx) like the EM
# wave; the animator's matrices make the first y = sin(kx - wt), the second y = sin(kx - wt), z = cos(kx - wt).  The axis
# and the plate are group 4. ----------------
POL = dict(half_len=0.85, amp=0.3, x_qwp=0.0, wavelength=0.5, n=50, arrows=8, r_plate=0.26)
def polarization():
    o = POL; k = 2 * np.pi / o["wavelength"]; out = [(seg([-o["half_len"], 0, 0], [o["half_len"], 0, 0]), 4)]
    x = o["x_qwp"]
    for f in (1.0, 0.8): out.append((circle(f * o["r_plate"], 20, "x", (x, 0, 0)), 4))                   # the plate, double-ringed
    d = 0.06 * math.sqrt(0.5)
    out.append((seg([x, -d, -d], [x, d, d]), 4)); out.append((seg([x, -d, d], [x, d, -d]), 4))             # its axes, at 45 degrees
    for g, (x0, x1) in enumerate(((-o["half_len"], x), (x, o["half_len"]))):
        xs = np.linspace(x0 + 0.01, x1 - 0.01, o["n"])
        out.append((np.column_stack([xs, o["amp"] * np.cos(k * xs), o["amp"] * np.sin(k * xs)]), 5 + g))
        for xi in np.linspace(x0 + 0.03, x1 - 0.03, o["arrows"]):
            out.append((seg([xi, 0, 0], [xi, o["amp"] * np.cos(k * xi), o["amp"] * np.sin(k * xi)]), 5 + g))
    return out

# ---------------- the Sagnac source of entangled photon pairs, as on the table: the pump laser at the right, a plate, a
# dichroic mirror, the polarizing beam splitter at the bottom of the loop, two mirrors and the crystal in the far leg,
# the pairs leaving down to two detectors with their fibre coils.  At the beam splitter light goes straight on or turns
# 90 degrees, so the loop is a right triangle with the splitter at its right angle (one leg along the pump's line, one up),
# the crystal in the hypotenuse.  The table is the xy plane (seen from above, tilted a little); the parts have a height.  Group 4 the parts and the beam lines; dashes travel the pump line (5), the loop
# both ways (6-8 and 9-11), and the two outputs as pairs of dashes (12, 13). ----------------
SAG = dict(pbs=(0.22, -0.18), m1=(-0.58, -0.18), m2=(0.22, 0.52), laser_x=0.66, plate_x=0.52, dichroic_x=0.44, det_y=-0.58, dash=0.05)
def _mirror_line(c, d_in, d_out, half=0.045):
    """a mirror at c turning direction d_in into d_out: a segment along the surface"""
    n = np.array(d_out, float) / np.linalg.norm(d_out) - np.array(d_in, float) / np.linalg.norm(d_in); n /= np.linalg.norm(n)
    t = np.array([-n[1], n[0]])
    return seg([c[0] - half * t[0], c[1] - half * t[1], 0], [c[0] + half * t[0], c[1] + half * t[1], 0])
def sagnac():
    S_ = SAG; px, py = S_["pbs"]; m1 = np.array(S_["m1"]); m2 = np.array(S_["m2"]); out = []
    out += [(p, 4) for p in box(S_["laser_x"], S_["laser_x"] + 0.16, py - 0.04, py + 0.04, -0.03, 0.03)]           # the laser
    out.append((seg([S_["plate_x"], py - 0.06, 0], [S_["plate_x"], py + 0.06, 0]), 4))                                 # a plate on the pump
    out.append((_mirror_line((S_["dichroic_x"], py), (-1, 0), (0, -1)), 4))                                             # the dichroic
    out += [(p, 4) for p in box(px - 0.04, px + 0.04, py - 0.04, py + 0.04, -0.03, 0.03)]                               # the PBS
    out.append((seg([px - 0.04, py - 0.04, 0.03], [px + 0.04, py + 0.04, 0.03]), 4))
    a1 = np.array([px - 0.04, py]); a2 = np.array([px, py + 0.04])                                                       # the loop's ports at the PBS: straight on, and 90 degrees up
    out.append((_mirror_line(m1, m1 - a1, m2 - m1), 4)); out.append((_mirror_line(m2, m2 - m1, a2 - m2), 4))             # the mirrors
    cm = (m1 + m2) / 2; dv = (m2 - m1) / np.linalg.norm(m2 - m1); nv = np.array([-dv[1], dv[0]])                           # the crystal, square to the far leg
    cr = [cm + 0.05 * dv + 0.02 * nv, cm - 0.05 * dv + 0.02 * nv, cm - 0.05 * dv - 0.02 * nv, cm + 0.05 * dv - 0.02 * nv, cm + 0.05 * dv + 0.02 * nv]
    for zz in (-0.02, 0.02): out.append((np.array([[c[0], c[1], zz] for c in cr]), 4))
    for c in cr[:4]: out.append((seg([c[0], c[1], -0.02], [c[0], c[1], 0.02]), 4))
    for cx in (px, S_["dichroic_x"]):                                                                                     # the detectors and their fibre coils
        out += [(p, 4) for p in box(cx - 0.06, cx + 0.06, S_["det_y"] - 0.1, S_["det_y"], -0.03, 0.03)]
        out.append((circle(0.045, 12, "z", (cx + 0.13, S_["det_y"] - 0.05, 0)), 4)); out.append((circle(0.038, 12, "z", (cx + 0.135, S_["det_y"] - 0.045, 0)), 4))
    lines = [((S_["laser_x"], py), (px + 0.04, py)), (tuple(a1), tuple(m1)), (tuple(m1), tuple(m2)), (tuple(m2), tuple(a2)),
             ((px, py - 0.04), (px, S_["det_y"])), ((S_["dichroic_x"], py), (S_["dichroic_x"], S_["det_y"]))]
    for a, b in lines: out.append((seg([a[0], a[1], 0], [b[0], b[1], 0]), 4))
    # the dashes: stored centred on the origin along each leg's direction; the animator slides them from A to B
    def dash(a, b, g, pair=False):
        d = (np.array(b) - np.array(a)); d = d / np.linalg.norm(d) * S_["dash"] / 2; n = np.array([-d[1], d[0]]) / np.linalg.norm(d) * 0.012
        if pair:
            out.append((seg([-d[0] + n[0], -d[1] + n[1], 0], [d[0] + n[0], d[1] + n[1], 0]), g)); out.append((seg([-d[0] - n[0], -d[1] - n[1], 0], [d[0] - n[0], d[1] - n[1], 0]), g))
        else: out.append((seg([-d[0], -d[1], 0], [d[0], d[1], 0]), g))
    for g, (a, b, pair) in sagnac_legs().items(): dash(a, b, g, pair)
    return out
def sagnac_legs():
    """{group: (A, B, pair)}: the dashes' legs, the animator moving each from A to B as its phase goes round"""
    S_ = SAG; px, py = S_["pbs"]; m1 = S_["m1"]; m2 = S_["m2"]; a1 = (px - 0.07, py); a2 = (px, py + 0.07)
    return {5: ((S_["laser_x"] - 0.03, py), (px + 0.07, py), False),
            6: (a2, m2, False), 7: (m2, m1, False), 8: (m1, a1, False),
            9: (a1, m1, False), 10: (m1, m2, False), 11: (m2, a2, False),
            12: ((px, py - 0.07), (px, S_["det_y"] + 0.03), True), 13: ((S_["dichroic_x"], py - 0.03), (S_["dichroic_x"], S_["det_y"] + 0.03), True)}

# ---------------- a hexacopter with a BicoLog antenna under it sweeping through the beam pattern of a radio astronomy
# dish on its cart (the mapping flights): the dish, cart and pattern are group 4; the drone's body and antenna group 5,
# its six propellers groups 6-11 (the animator spins them, alternate ways, and carries them with the body) ----------------
DRONE = dict(dish_c=(0.0, -0.38), dish_r=0.2, dish_focal=0.16, arc_r=0.82, sweep_deg=40.0, arm=0.17, hub=0.045, blade=0.09, lobe=0.6)
def drone_map():
    D = DRONE; cx, cy = D["dish_c"]; r, F = D["dish_r"], D["dish_focal"]; out = []
    th = np.linspace(0, 2 * np.pi, 17)
    for rr in (r, 0.55 * r): out.append((np.column_stack([cx + rr * np.cos(th), np.full(17, cy + rr * rr / (4 * F)), rr * np.sin(th)]), 4))   # the dish, pointing up
    for ang in np.linspace(0, np.pi, 3, endpoint=False):
        s_ = np.linspace(-r, r, 13); out.append((np.column_stack([cx + s_ * np.cos(ang), cy + s_ * s_ / (4 * F), s_ * np.sin(ang)]), 4))
    out.append((circle(0.02, 8, "y", (cx, cy + F, 0)), 4))                                                              # the feed
    for ang in np.linspace(0, 2 * np.pi, 3, endpoint=False): out.append((seg([cx + r * np.cos(ang), cy + r * r / (4 * F), r * np.sin(ang)], [cx, cy + F, 0]), 4))
    out.append((seg([cx, cy + F, 0], [cx, cy + F + 0.16, 0]), 4))                                                       # the Yagi on its mast
    for i, yy in enumerate(np.linspace(cy + F + 0.04, cy + F + 0.15, 4)): w = 0.05 - 0.008 * i; out.append((seg([cx - w, yy, 0], [cx + w, yy, 0]), 4))
    out += [(p, 4) for p in box(cx - 0.025, cx + 0.025, cy - 0.3, cy - 0.02, -0.025, 0.025)]                           # the mount column
    for ang in np.linspace(np.pi / 2, np.pi / 2 + 2 * np.pi, 3, endpoint=False):                                       # the tripod and its wheels
        wx, wz = 0.2 * np.cos(ang), 0.2 * np.sin(ang)
        out.append((seg([cx, cy - 0.2, 0], [cx + wx, cy - 0.36, wz]), 4)); out.append((circle(0.035, 10, "z", (cx + wx, cy - 0.36, wz)), 4))
    # the beam pattern: a main lobe and side lobes, a surface of revolution about the dish's axis: two profiles and rings
    def prof(t): return D["lobe"] * (np.cos(t) ** 8 + 0.22 * np.exp(-((np.abs(t) - np.radians(55)) / np.radians(10)) ** 2))
    t = np.linspace(-np.radians(80), np.radians(80), 41); rp = prof(t)
    for ang in (0.0, np.pi / 2): out.append((np.column_stack([cx + rp * np.sin(t) * np.cos(ang), cy + F + rp * np.cos(t), rp * np.sin(t) * np.sin(ang)]), 4))
    for tt in (np.radians(12), np.radians(24), np.radians(52)):
        rr = prof(tt); out.append((np.column_stack([cx + rr * np.sin(tt) * np.cos(th), np.full(17, cy + F + rr * np.cos(tt)), rr * np.sin(tt) * np.sin(th)]), 4))
    # the drone, level, in its own frame: the hub, six arms (three lines through it), and under it the BicoLog, horizontal
    # as on the drone that flies (Jason's photo, 2026-11-09): two cones, apex to apex, their axis along the sweep, on a
    # short mount (the motors, skids, payload box and plate are not drawn; the props mark the motors)
    h = D["hub"]; A = D["arm"]
    out.append((np.column_stack([h * np.cos(np.linspace(0, 2 * np.pi, 7)), np.zeros(7), h * np.sin(np.linspace(0, 2 * np.pi, 7))]), 5))
    for ang in np.linspace(0, np.pi, 3, endpoint=False): out.append((seg([-A * np.cos(ang), 0, -A * np.sin(ang)], [A * np.cos(ang), 0, A * np.sin(ang)]), 5))
    yc, xl, rb = -0.105, 0.095, 0.07                                                    # the axis's height, a cone's length, its radius
    out.append((seg([0, 0, 0], [0, yc, 0]), 5))
    for sx in (-1, 1):
        out.append((circle(rb, 6, "x", (sx * xl, yc, 0)), 5))
        for ang in np.linspace(0, 2 * np.pi, 3, endpoint=False): out.append((seg([sx * xl, yc + rb * np.cos(ang), rb * np.sin(ang)], [0, yc, 0]), 5))
    # the propellers: two blades through the centre, stored flat; the animator spins them about y at each arm's end
    b = D["blade"]
    for k in range(6): out.append((np.array([[-b, 0, 0], [-b * 0.3, 0, 0.01], [0, 0, 0], [b * 0.3, 0, -0.01], [b, 0, 0]]), 6 + k))
    return out
def drone_constants():
    D = DRONE
    return dict(arc_r=D["arc_r"], y0=D["dish_c"][1] + D["dish_focal"], sweep=D["sweep_deg"] / 360, arms=[(D["arm"] * np.cos(a), D["arm"] * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 6, endpoint=False)], prop_y=0.02)

# ---------------- a radio dish transmitting: a paraboloid, its feed, and, once a finale, HMC in Morse code leaving along
# its axis (2026-11-09, Jason: transmit less often, so the dish is seen alone; HMC in Morse).  Each dot and dash is a
# plane-wave packet seen edge on, a bar as tall as the beam and one or three Morse units long (groups 5-14).  It is
# drawn only in flight: its vertices are stored at z = 1 with the cull bit, and the animator writes R[2][2] = (u - d)(d
# + w - u), positive only while the packet is between the dish and the end of the beam (u a slow sawtooth from the
# finale's start, the pendulum wave's phase, a turn in 24 s; d when the packet leaves, w its flight).  The rest of R's third row is 0, so its depth is that of
# its centre and the cull sees R[2][2] alone. ----------------
DISH = dict(radius=0.36, focal=0.26, x_vertex=-0.52, msg_t0=1.0, speed=0.3, unit=0.04, travel=0.95, h=0.27, fill=0.8)   # speed: slow enough
                                                                                           # that the phosphor's trail (80 ms) is half a unit
MORSE = {"H": "....", "M": "--", "C": "-.-."}
def morse_elements(text="HMC"):
    """(start, length) in Morse units: a dot 1, a dash 3, 1 between them, 3 between letters"""
    out = []; u = 0
    for li, ch in enumerate(text):
        if li: u += 3                                                                   # 3 between letters
        for k, sym in enumerate(MORSE[ch]):
            if k: u += 1
            n = 1 if sym == "." else 3; out.append((u, n)); u += n
    return out
def dish_constants(per_s):
    """per Morse element: d (the sawtooth's value as its centre passes the rim) and the flight w, in the sawtooth's
    turns (per_s: the sawtooth's rate); x_rim; the speed in screen units per turn"""
    D = DISH; r, F, xv = D["radius"], D["focal"], D["x_vertex"]; x_rim = xv + r * r / (4 * F); tau = D["unit"] / D["speed"]
    els = [dict(d=per_s * (D["msg_t0"] + (st + n / 2) * tau), n=n) for st, n in morse_elements()]
    return dict(x_rim=x_rim, w=per_s * D["travel"] / D["speed"], v=D["speed"] / per_s, elements=els)
def dish():
    d = DISH; r, F, xv = d["radius"], d["focal"], d["x_vertex"]
    out = []
    for rr in (r, 0.5 * r): out.append((circle(rr, 32, "x", (xv + rr * rr / (4 * F), 0, 0)), 4))       # the rim and a ring
    for ang in np.linspace(0, np.pi, 4, endpoint=False):                                            # four ribs (parabolas)
        s = np.linspace(-r, r, 17); out.append((np.column_stack([xv + s * s / (4 * F), s * np.cos(ang), s * np.sin(ang)]), 4))
    feed = np.array([xv + F, 0, 0]); out.append((circle(0.025, 8, "x", feed), 4))                   # the feed
    for ang in np.linspace(0, 2 * np.pi, 3, endpoint=False):                                        # three struts from the rim
        out.append((seg([xv + r * r / (4 * F), r * np.cos(ang), r * np.sin(ang)], feed), 4))
    out.append((seg([xv, 0, 0], [xv - 0.1, -0.45, 0]), 4)); out.append((seg([xv - 0.1, -0.45, 0], [xv - 0.3, -0.45, 0]), 4)); out.append((seg([xv - 0.1, -0.45, 0], [xv + 0.1, -0.45, 0]), 4))  # the stand
    for k, (st, n) in enumerate(morse_elements()):                                                  # the packets, centred, at z = 1 (culled)
        a = (n - 1 + d["fill"]) * d["unit"] / 2; hh = d["h"]                                         # a gap wider than a unit between them
        out.append((np.array([[-a, -hh, 1], [a, -hh, 1], [a, hh, 1], [-a, hh, 1], [-a, -hh, 1]], float), 5 + k))
    return out

# ---------------- satellites round the Earth (the seal's globe, drawn large), each with a link beam to the ground ----------------
EARTH_SCALE = 1.9            # the globe's radius 0.305 x 1.9 = 0.58 (the matrices hold up to 1.9999)
SATS = [dict(a=0.70, inc=35.0, node=0.0), dict(a=0.76, inc=62.0, node=120.0), dict(a=0.80, inc=85.0, node=240.0)]   # radius, inclination, node (degrees)
def orbit_matrix(s):
    import scene
    return scene.rot_y(math.radians(s["node"])) @ scene.rot_x(math.radians(s["inc"]))
def satellites():
    out = []
    for k, s in enumerate(SATS):
        out.append((circle(s["a"], 48) @ orbit_matrix(s).T, 4))
    # a satellite in its own frame: it sits at +x on the orbit (the animator puts it there), -x points to the Earth
    for k, s in enumerate(SATS):
        g = 5 + k; sz = 0.025; beam = s["a"] - 0.305 * EARTH_SCALE
        out += [(p, g) for p in box(-sz, sz, -sz, sz, -sz, sz)]
        out.append((seg([0, 0, -sz], [0, 0, -0.11]), g)); out.append((seg([0, 0, sz], [0, 0, 0.11]), g))        # the solar panels' arms
        out += [(p, g) for p in box(-sz, sz, -0.012, 0.012, -0.11, -0.05)] + [(p, g) for p in box(-sz, sz, -0.012, 0.012, 0.05, 0.11)]
        for a in np.linspace(0, 2 * np.pi, 4, endpoint=False):                                       # the link beam, a cone to the ground
            out.append((seg([-sz, 0.5 * sz * np.cos(a), 0.5 * sz * np.sin(a)], [-beam, 0.03 * np.cos(a), 0.03 * np.sin(a)]), g))
    return out

# ---------------- the central dogma, three schematics.  Replication: the parent double helix opens at a fork (the
# helicase ring) into two template strands, single near the fork, each with its new strand (dashed) and rungs from the
# growing point on, nucleotides flying in to the growing points (groups 5-8, each on a straight path).  Transcription:
# the DNA helix with a polymerase (group 5) sliding along it; the RNA (group 6) comes out of it as a travelling wave
# (stored as (s, cos ks, sin ks) along its own axis, the animator's matrix making the wave run away from the
# polymerase), nucleotides (7-9) flying in to the polymerase.  Translation: the mRNA with its codons, a ribosome (large
# and small subunit, group 5) sliding along it, the peptide chain of beads from the docking site up through the large
# subunit (with the ribosome) and on out of its top (group 6, riding up two beads a cycle, seamlessly), tRNAs with their
# amino acids (7-9) arriving at the docking site. ----------------
def _helix(x0, x1, r, pitch, phase=0.0, n=None):
    n = n or max(8, int((x1 - x0) / pitch * 14)); x = np.linspace(x0, x1, n); k = 2 * np.pi / pitch
    return np.column_stack([x, r * np.cos(k * x + phase), r * np.sin(k * x + phase)])
def _dashed(pl, on=3, off=2):
    out = []; i = 0
    while i < len(pl) - 1:
        out.append(pl[i:i + on + 1]); i += on + off
    return [p for p in out if len(p) >= 2]
def _rungs(x0, x1, r, pitch, every, phase2=2.2):
    k = 2 * np.pi / pitch; out = []
    for x in np.arange(x0, x1, every): out.append(seg([x, r * np.cos(k * x), r * np.sin(k * x)], [x, r * np.cos(k * x + phase2), r * np.sin(k * x + phase2)]))
    return out
REPL = dict(fork=(-0.05, 0.0), r=0.11, pitch=0.42, angle_deg=24.0, parent_len=0.68, daughter_len=0.78, grow=0.36)
def replication():
    R_ = REPL; fx, fy = R_["fork"]; r, pt, L = R_["r"], R_["pitch"], R_["daughter_len"]; out = []
    x0 = fx - R_["parent_len"]
    out.append((_helix(x0, fx, r, pt), 4)); out.append((_helix(x0, fx, r, pt, 2.2), 4)); out += [(p, 4) for p in _rungs(x0, fx, r, pt, 0.06)]
    out.append((circle(0.06, 12, "x", (fx, fy, 0)), 4))                                                  # the helicase
    g0 = R_["grow"] * L
    for sgn in (1, -1):
        M = scene.rot_z(sgn * math.radians(R_["angle_deg"])); T_ = np.array([fx, fy, 0])
        out.append((_helix(0.0, L, r, pt) @ M.T + T_, 4))                                                 # the template strand, all the way
        out += [(p @ M.T + T_, 4) for p in _dashed(_helix(g0, L, r, pt, 2.2))]                           # the new strand, from the growing point on
        out += [(p @ M.T + T_, 4) for p in _rungs(g0, L, r, pt, 0.06)]
    for g in range(5, 9): out.append((seg([-0.025, 0, 0], [0.025, 0, 0]), g)); out.append((circle(0.014, 6, "z", (0.025, 0, 0)), g))   # the nucleotides
    return out
def replication_paths():
    """{group: (A, B)}: where each nucleotide starts and where it joins, at the new strand's growing point"""
    R_ = REPL; fx, fy = R_["fork"]; paths = {}; g = 5; L = R_["daughter_len"]
    for sgn in (1, -1):
        M = scene.rot_z(sgn * math.radians(R_["angle_deg"]))
        for f, off in ((R_["grow"], 0.42), (R_["grow"] + 0.05, 0.3)):
            B = M @ np.array([f * L, R_["r"] * 0.9, 0]) + np.array([fx, fy, 0])
            A = B + np.array([0.1, sgn * off, 0]); paths[g] = ((A[0], A[1]), (B[0], B[1])); g += 1
    return paths
TRANS = dict(r=0.09, pitch=0.3, x0=-0.72, x1=0.72, p_start=-0.42, p_len=0.84, p_y=0.0, offs=[(-0.2, 0.5), (0.05, 0.55), (0.3, 0.45)],
             tail_exit=(-0.08, 0.1), tail_angle_deg=140.0, tail_len=0.42, tail_amp=0.05, tail_wavelength=0.16)
def transcription():
    T_ = TRANS; r, pt = T_["r"], T_["pitch"]; out = []
    out.append((_helix(T_["x0"], T_["x1"], r, pt), 4)); out.append((_helix(T_["x0"], T_["x1"], r, pt, 2.2), 4)); out += [(p, 4) for p in _rungs(T_["x0"], T_["x1"], r, pt, 0.05)]
    th = np.linspace(0, 2 * np.pi, 21)
    out.append((np.column_stack([0.17 * np.cos(th), 0.13 * np.sin(th), np.zeros(21)]), 5))               # the polymerase, two ellipses
    out.append((np.column_stack([0.17 * np.cos(th), np.zeros(21), 0.13 * np.sin(th)]), 5))
    s_ = np.linspace(0.0, T_["tail_len"], 36); k = 2 * np.pi / T_["tail_wavelength"]                    # the RNA: a wave along its own axis
    out.append((np.column_stack([s_, T_["tail_amp"] * np.cos(k * s_), T_["tail_amp"] * np.sin(k * s_)]), 6))
    for g in range(7, 10): out.append((seg([-0.025, 0, 0], [0.025, 0, 0]), g)); out.append((circle(0.014, 6, "z", (0.025, 0, 0)), g))
    return out
TRL = dict(x0=-0.72, x1=0.72, p_start=-0.42, p_len=0.84, p_y=0.0, offs=[(0.25, 0.5), (0.4, 0.38), (0.32, 0.62)], dock_y=0.05, exit_y=0.25, pitch=0.05, chain_len=0.42)
def _beads(y0, y1, pitch, dock_y):
    """beads from y0 to y1 in a zigzag whose side depends on the bead's number from the docking site"""
    ys = np.arange(y0, y1 + 1e-6, pitch)
    return [np.array([0.0, y, 0.03 * (1 if int(round((y - dock_y) / pitch)) % 2 == 0 else -1)]) for y in ys]
def translation():
    T_ = TRL; out = []
    x = np.linspace(T_["x0"], T_["x1"], 60); out.append((np.column_stack([x, 0.03 * np.sin(12 * x), np.zeros(60)]), 4))        # the mRNA
    for xi in np.arange(T_["x0"] + 0.04, T_["x1"], 0.06): out.append((seg([xi, 0.03 * np.sin(12 * xi) - 0.025, 0], [xi, 0.03 * np.sin(12 * xi) + 0.025, 0]), 4))
    out.append((circle(0.03, 8, "z", (T_["x0"] - 0.03, 0, 0)), 4))                                        # the cap
    th = np.linspace(0, 2 * np.pi, 21)
    out.append((np.column_stack([0.2 * np.cos(th), 0.12 + 0.13 * np.sin(th), np.zeros(21)]), 5))        # the large subunit
    out.append((np.column_stack([0.16 * np.cos(th), -0.07 + 0.07 * np.sin(th), np.zeros(21)]), 5))      # the small subunit
    p, d = T_["pitch"], T_["dock_y"]
    fixed = _beads(d, T_["exit_y"], p, d)                                                                # the chain inside: docking site to the exit
    out.append((np.array(fixed), 5)); out += [(circle(0.018, 6, "z", c), 5) for c in fixed]
    moving = _beads(T_["exit_y"] - 2 * p, T_["exit_y"] + T_["chain_len"], p, d)                           # the chain outside: rides up two beads a cycle
    out.append((np.array(moving), 6)); out += [(circle(0.018, 6, "z", c), 6) for c in moving]
    for g in range(7, 10):                                                                               # a tRNA: an inverted L with its amino acid
        out.append((np.array([[0, -0.06, 0], [0, 0.03, 0], [-0.05, 0.03, 0]]), g)); out.append((seg([0, 0.03, 0], [0.05, 0.03, 0]), g)); out.append((circle(0.016, 6, "z", (0, 0.05, 0)), g))
    return out

def _model(name):
    def f():
        import proposals
        return proposals.PROPOSALS[name]["obj"]()
    f.__name__ = name; return f
CULL = {"dish": set(range(5, 15))}          # objects with groups whose vertices carry the cull bit
OBJECTS = {"caffeine": caffeine, "lsd": lsd, "dna": dna, "knot": trefoil, "gears": gears, "arm": arm,
           "em": em_wave, "pol": polarization, "sagnac": sagnac, "scope": telescope, "dish": dish, "sats": satellites, "drone": drone_map,
           "replicate": replication, "transcribe": transcription, "translate": translation}
for _n in ("ligo", "pcb", "spinner", "top", "pwave", "generator", "governor", "boom", "tek", "galton", "engine", "escape", "cartpole", "bridge"):
    OBJECTS[_n] = _model(_n)

if __name__ == "__main__":
    for k, f in OBJECTS.items():
        o = f(); print("%-9s %4d polylines %5d vertices, groups %s" % (k, len(o), sum(len(p) for p, g in o), sorted({g for p, g in o})))
