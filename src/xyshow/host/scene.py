#!/usr/bin/env python3
"""The 3D scene for the scope: the seal, a wireframe globe in its style from a real coastline, the Lorenz
tail; the tumbling rotation; a float reference of what the gateware's vector engine computes, and a phosphor
renderer for previews.  Coordinates: the seal spans x -1..1 (the scope's full width), y -0.63..0.63, z = 0.

Groups: 0 the seal body (tumbles), 1 the globe (tumbles with the seal and spins about its polar axis, upright as on
the seal, the far half hidden), 2 the Lorenz tail (tumbles), 3 static.  Vertices carry (beam, group, x, y, z)."""
import os, json, math, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GLOBE_C = np.array([0.09, 0.0, 0.0]); GLOBE_R = 0.305
GLOBE_FACE_LON = -64.0      # the 3D globe at rest (its spin phase 0, where mode 1 starts) faces this longitude, seen from the
                            # equator with the poles at the top and bottom: the seal's own globe.  Fitted to the seal's coastlines
                            # (the mean distance from the real coastlines, projected as the engine does, to the traced strokes and
                            # back): South and North America both fit best at 64 W; the engraving squeezes Africa in from the
                            # edge (alone it would fit at 44 W)
SEAL_GLOBE_TILT = 0.0       # the seal's globe's axis from vertical (radians): 0, upright as engraved, so mode 1's 3D globe comes
                            # in exactly where the seal's was and spins about the vertical
TILT = math.radians(23.4)   # the satellites' Earth's axial tilt

# ---------------- the seal ----------------
def load_seal():
    with open(os.path.join(HERE, "seal.json")) as f: return [np.array(p, float) for p in json.load(f)]

# The dividers.  The traced right leg was tangled with the globe's grid it crossed (and the left with the sun's
# rays), so both legs are redrawn from the left leg's measured edges (the dividers' outline is stroke 10 of
# seal.json), the right leg as the left's mirror image about the knob's vertical axis, so the two arms match;
# the knob stays as traced.  The traced strokes within a strip along either leg are cut away first (the legs lie
# over the sun and the globe).
AXIS_X = -0.252                                              # the knob's centre
LEFT_OUTER = (np.array([-0.296, 0.305]), np.array([-0.551, -0.299]))
LEFT_INNER = (np.array([-0.253, 0.299]), np.array([-0.537, -0.291]))
LEFT_TIP = np.array([-0.557, -0.322])
LEG_BAND = 0.028                                             # the cut's half-width (the leg is 0.020 at the top)
LEG_TOP_Y = 0.31                                             # above this is the knob, kept

def _mirror(p):
    q = np.array(p, float).copy(); q[..., 0] = 2 * AXIS_X - q[..., 0]; return q

def _in_band(p, left=True, w=LEG_BAND):
    a = (LEFT_OUTER[0] + LEFT_INNER[0]) / 2; b = LEFT_TIP
    if not left: a, b = _mirror(a), _mirror(b)
    d = b - a; t = np.clip((p - a) @ d / (d @ d), 0, 1)
    return (np.hypot(*(p - (a + t[:, None] * d)).T) < w) & (p[:, 1] < LEG_TOP_Y)

def dividers():
    """The two legs as outlines, the right the mirror of the left."""
    left = np.array([LEFT_OUTER[0], LEFT_OUTER[1], LEFT_TIP, LEFT_INNER[1], LEFT_INNER[0], LEFT_OUTER[0]])
    right = _mirror(left)
    return [np.column_stack([left, np.zeros(len(left))]), np.column_stack([right, np.zeros(len(right))])]

def split_seal(polys, c=GLOBE_C[:2], r=GLOBE_R):
    """The body's strokes: everything outside the globe's circle and the legs' bands, plus the redrawn legs.  The
    engraved globe's strokes (inside the circle) are dropped: the 3D globe takes its place."""
    body = []
    for pl in polys:
        inside = np.hypot(*(pl - c).T) < r
        cut = _in_band(pl, True) | _in_band(pl, False)
        cls = np.where(cut, 2, np.where(inside, 1, 0))                   # 0 body, 1 the engraved globe, 2 cut away
        start = 0
        for i in range(1, len(pl) + 1):
            if i == len(pl) or cls[i] != cls[start]:
                seg = pl[start:i]
                if len(seg) >= 2 and cls[start] == 0: body.append(np.column_stack([seg, np.zeros(len(seg))]))
                start = i
    return body + dividers()

# ---------------- the globe ----------------
def _ll2xyz(lon, lat):
    lo, la = np.radians(lon), np.radians(lat)
    return np.stack([np.cos(la) * np.sin(lo), np.sin(la), np.cos(la) * np.cos(lo)], -1)   # y up, z toward lon 0

def coastlines(path=None, min_vertices=6, tol_deg=1.5, max_total=1300):
    """Natural Earth 110 m coastline (public domain), simplified, as 3D polylines on the unit sphere."""
    path = path or os.path.join(HERE, "coast.json")
    with open(path) as f: lines = json.load(f)
    out = []
    for ln in lines:
        p = np.array(ln, float)
        if len(p) >= min_vertices: out.append(_ll2xyz(p[:, 0], p[:, 1]))
    return out

def grid(step=30.0, n=24):
    """Meridians and parallels every `step` degrees, like the seal's globe."""
    out = []
    for lon in np.arange(-180, 180, step):
        lat = np.linspace(-90, 90, n); out.append(_ll2xyz(np.full(n, lon), lat))
    for lat in np.arange(-60, 61, step):
        lon = np.linspace(-180, 180, 2 * n); out.append(_ll2xyz(lon, np.full(2 * n, lat)))
    return out

def globe_scene(r=GLOBE_R, c=GLOBE_C):
    """The globe's wireframe in its own frame (unit sphere scaled to r, centred at the origin): the grid and the
    coastlines; group 1.  The limb (a circle of radius r in the seal's plane at c) goes with the body, group 0."""
    R = rot_y(math.radians(-GLOBE_FACE_LON))                         # longitude GLOBE_FACE_LON to the front
    g = [p @ R.T * r for p in grid()] + [p @ R.T * r for p in coastlines()]
    t = np.linspace(0, 2 * np.pi, 97); limb = np.stack([c[0] + r * np.cos(t), c[1] + r * np.sin(t), np.zeros_like(t)], -1)
    return g, limb

# ---------------- Lorenz ----------------
def lorenz_tail(n=2048, dt=2 ** -12, every=14, r=28.0, warm=30.0):
    s, b = 10.0, 8 / 3; v = np.array([1.0, 1.0, 1.0])
    def f(v): return np.array([s * (v[1] - v[0]), r * v[0] - v[1] - v[0] * v[2], v[0] * v[1] - b * v[2]])
    for _ in range(int(warm / dt)): v = v + dt * f(v)
    pts = []
    for i in range(n * every):
        v = v + dt * f(v)
        if i % every == 0: pts.append(v.copy())
    p = np.array(pts)
    return np.stack([p[:, 0] / 25, p[:, 1] / 30, (p[:, 2] - 25) / 25], -1) * 0.9

# ---------------- the rotations ----------------
def rot_x(a): c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
def rot_y(a): c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def rot_z(a): c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
def tumble(t, wa=0.37, wb=0.53, wc=0.71):
    """Three Euler angles advancing at incommensurate rates: the apparent axis wanders, nothing looks like a
    squash about x or y.  t in seconds."""
    return rot_z(wa * t) @ rot_y(wb * t) @ rot_x(wc * t)
def globe_matrix(R0, spin, tilt=SEAL_GLOBE_TILT):
    return R0 @ rot_x(tilt) @ rot_y(spin)

# ---------------- the engine's reference: transform, project, cull, draw ----------------
P_VIEW = 3.0
def project(q):
    s = P_VIEW / (P_VIEW + q[:, 2])
    return np.stack([q[:, 0] * s, q[:, 1] * s], -1)

def frame_points(groups, step_codes=3.0):
    """groups: list of (polylines, R, t, cull).  Returns the beam path as an (N, 3) array of x, y, beam in -1..1,
    sampled every `step_codes` DAC codes along each visible segment, as the line generator would."""
    out = []
    for polys, R, t, cull in groups:
        for pl in polys:
            q = pl @ R.T + t
            vis = np.ones(len(q), bool) if not cull else (q[:, 2] - t[2]) >= 0
            xy = project(q)
            for i in range(1, len(q)):
                a, b = xy[i - 1], xy[i]
                on = vis[i - 1] and vis[i]
                n = max(1, int(np.ceil(np.hypot(*(b - a)) * 2047 / step_codes))) if on else 1
                f = np.linspace(0, 1, n + 1)[1:]
                seg = a + f[:, None] * (b - a)
                out.append(np.column_stack([seg, np.full(n, 1.0 if on else 0.0)]))
            if len(q): out.append(np.array([[xy[0, 0], xy[0, 1], 0.0]]))   # the jump to the next stroke's start
    return np.vstack(out) if out else np.zeros((0, 3))

def phosphor(path, n=560, aspect=0.8, blur=1.1, gamma=0.55, jump_weight=0.08):
    """Brightness by dwell: every sample adds light where the beam is; jumps add a little (an analog scope)."""
    from scipy.ndimage import gaussian_filter
    h = int(n * aspect)
    img = np.zeros((h, n))
    ix = np.clip(((path[:, 0] + 1) / 2 * (n - 1)).astype(int), 0, n - 1)
    iy = np.clip(((aspect - path[:, 1]) / (2 * aspect) * (h - 1)).astype(int), 0, h - 1)
    w = np.where(path[:, 2] > 0, 1.0, jump_weight)
    np.add.at(img, (iy, ix), w)
    img = gaussian_filter(img, blur)
    img = np.clip(img / (np.percentile(img[img > 0], 99.0) + 1e-9), 0, 1) ** gamma
    rgb = np.zeros(img.shape + (3,)); rgb[..., 1] = img; rgb[..., 0] = 0.55 * img ** 2; rgb[..., 2] = 0.25 * img ** 2
    return (rgb * 255).astype(np.uint8)

def to_gif(frames, path, fps=20):
    from PIL import Image
    ims = [Image.fromarray(f) for f in frames]
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=int(1000 / fps), loop=0)

if __name__ == "__main__":
    body = split_seal(load_seal())
    g, limb = globe_scene()
    print(f"seal body {len(body)} strokes / {sum(len(p) for p in body)} vertices; "
          f"3D globe {len(g)} / {sum(len(p) for p in g)}; limb {len(limb)}")
