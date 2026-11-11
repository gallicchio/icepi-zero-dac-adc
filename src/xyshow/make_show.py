#!/usr/bin/env python3
"""The XY show on two Icepi Zeros (the tutorial's 5.08), from one file: the constants below are the show.

    python3 make_show.py            the tables the gateware is built from, into rtl/: the scene (scene_xy.hex,
                                    scene_z.hex), the perspective and sine tables, the animator's program and its
                                    constants, the show's times and rates (show_params.vh) and its finales
                                    (show_finales.vh); then `make` builds the bitstreams
    python3 make_show.py --movie    the tables, and a preview: renders/show_movie.mp4 (the show as it runs, until every
                                    finale has been once), renders/show_finales.mp4 (the seal once, then the finales
                                    back to back) and renders/finales_sheet.png (three moments of each)
    python3 make_show.py --quick    the tables, and a short preview (the seal and the first four finales, 10 frames a second)

The sequence: the seal with its globe a 3D wireframe, upright and facing as the engraved one (64 W), still for a
second, then turning once about its axis; the seal turned over about an in-plane axis (the lettering reads backwards
half way) while the globe keeps turning; then FINALES_PER_SEAL finales from FINALES, one after another; then the seal
again, and the next finales.  The movie runs the gateware's own animator program bit for bit (host/gen_matrix_prog.py's
run()) and draws the beam's path with a phosphor, so it shows what the boards will draw; its brightness is the beam's
dwell, as on a scope.  The tables need numpy; the movies numpy, scipy, Pillow and ffmpeg.

This show was first written for another board, an ECP5 with two 14-bit DACs on one chip, and moved to the Icepi pair
while that board was being made; this copy is kept to the pair (an 8-bit DAC on each board, kept in step by a burst on
the X board's DAC: rtl/sync_link.v).
"""
import os, sys, math, json, time, subprocess, argparse
import numpy as np

# ============================== the constants to play with ==============================
T_GLOBE = 5.0           # s: mode 1, the seal with the 3D globe, still and then turning (the show starts here).  The seal as traced
                        # with its engraved globe (mode 0) was dropped 2026-11-09 (Jason: the change from the engraving to the
                        # wireframe was jarring) and its globe taken out of the scene memory
GLOBE_HOLD_S = 1.0      # s: mode 1 starts with the 3D globe still, upright and facing as the engraved one (Jason, 2026-11-09); 0 = it
                        # turns at once
GLOBE_TURNS = 1.0       # turns of the globe in the rest of T_GLOBE, so mode 2 starts with it facing as the seal's (it keeps turning
                        # at that rate afterwards)
T_FLIP = 7.5            # s: mode 2, the seal turns over about an in-plane axis, the globe still turning
FLIP_TURNS = 1.0        # turns of the seal during T_FLIP (half way it is seen from the back)
FLIP_AXIS_DEG = 25.0    # the axis' angle from vertical, in the seal's plane, at power-up
FLIP_AXIS_DEG_PER_S = 8.0   # the axis drifts round at this rate, so each cycle's turn is a little different
# The finales (mode 3), in this order, FINALES_PER_SEAL of them between the seal's turns: (kind, seconds).  The kinds are
# those of KINDS (up to 32 in the list); KINDS also has finales that are not in it, ready to add: "lorenz" (the
# Lorenz attractor's tail, from its twin), "em" (an electromagnetic wave), "knot", "lsd", "boom" (a sonic boom).
# Repeat one to show it more often, delete what you do not want.  The scene memory holds 8192 vertices: the seal and
# its 3D globe take 2888, each object its share (`python3 make_show.py` prints the layout).
FINALES = [
    ("chua",       5.0), ("spinner",    7.6), ("gears",      6.0),
    ("ligo",       7.0), ("caffeine",   5.0), ("governor",   6.5),
    ("dish",       9.0), ("top",        6.0), ("kaleido",    6.7),
    ("arm",        7.0), ("pcb",        7.0), ("sats",       7.0),
    ("pwave",     12.0), ("scope",      6.0), ("generator",  7.0),
    ("dna",        5.0), ("drone",      7.0), ("pol",        7.0),
    ("sagnac",     7.0), ("tek",        7.0), ("replicate",  6.0),
    ("transcribe", 6.5), ("translate",  6.5),
]
FINALES_PER_SEAL = 4    # finales between two of the seal's turns (modes 1 and 2); 3 until 2026-11-11
LORENZ_VIEW_TURNS_PER_S = (0.06, 0.085, 0.11)   # the view's three angles' rates while in the Lorenz finale (incommensurate: the axis wanders)
LORENZ_TIME_UNITS_PER_S = 9.8   # the twin's speed: the analog board's "nice!" setting (an integrator time constant of 102 ms: 1/0.102 time units
                                # a second; one orbit of the attractor is about 0.7 time units, so some 14 a second)
RING_EVERY = 56         # a tail point every this many steps of 2^-12 time units: 2048 points = 28 time units (2.9 s of trajectory)
TAIL_HOLD_US = 20.0     # the beam stays this long on a tail's newest point every frame: the bright head that shows the motion
CHUA_TIME_UNITS_PER_S = 2.5; RING_EVERY2 = 14   # Chua's circuit (the second twin): its speed, and a tail point every this many steps of 2^-10
CHUA_SCALE = (0.63 / 2.5, 0.63 / 0.45, 0.63 / 4.0)   # the double scroll's x, y, z ranges to the screen
LORENZ_SCALE = 0.63     # the tail's size on the screen (with perspective its near parts reach 0.9)
TUMBLE_TURNS_PER_S = (0.05, 0.07, 0.10)   # the molecules' and the knot's tumble: three Euler rates (faster smears on the phosphor)
DNA_TURNS_PER_S = 0.45; DNA_NOD_DEG = 16.0; DNA_NOD_PER_S = 0.25        # DNA spins on its axis and nods (a sine of that amplitude at that rate)
GEAR_SUN_TURNS_PER_S = 0.3     # the sun's rate (the carrier and planets follow the tooth counts); flat (a nod of the train looked like a squash)
ARM_VIEW_TURNS_PER_S = 0.07; ARM_VIEW_TILT_DEG = -24.0; ARM_WAVE_PER_S = 0.3   # the arm is seen from a slowly turning viewpoint (the kaleidocycle too); its joints wave at this rate
ARM_OFF = (0.0, -0.60)          # where the arm's base sits on the screen (centred: the viewpoint goes all the way round)
ARM_JOINTS = [(0.0, 0.18, "sin"), (0.06, 0.07, "cos"), (0.20, 0.08, "sin2"), (0.03, 0.06, "cos2"), (0.0, 0.25, "sin")]   # per joint: rest angle, amplitude (turns), which wave
PHYS_VIEW_SWING_DEG = 35.0; PHYS_VIEW_SWINGS_PER_S = 0.08; PHYS_VIEW_TILT_DEG = -20.0   # the EM wave, the lens, the dish and the satellites: the viewpoint
                                                                                      # swings this far either side of the side view, and back, at this rate
EM_CYCLES_PER_S = 0.5           # the EM wave's wt: the pattern moves a wavelength in 2 s
WAVEFRONT_PER_S = 0.33          # the lens's and the dish's wavefronts: each crosses the picture in 1/this seconds
SAT_TURNS_PER_S = (0.28, 0.24, 0.20)   # the three satellites' orbits per second
DRONE_SWEEPS_PER_S = 0.09; PROP_TURNS_PER_S = 2.5   # the drone's sweep through the beam (a sine), its propellers' spin
SLOW_PER_S = 0.15               # the phase sl: the oscilloscope in an oscilloscope swings once per 1/this seconds (host/proposals.py
                                # TEK); transcription's and translation's walk along the strand; the kaleidocycle's drive (a turn:
                                # flat, inside out and back to flat)
PCB_STEP_PER_S = 0.9            # the circuit board's charge moves a bead's spacing this often a second
PWAVE_CYCLE_S = 24.0            # the pendulum wave's cycle: in it the longest pendulum swings 16 times, the shortest 27; the same phase,
                                # from zero, times the dish's message
P_VIEW = 5.0            # the perspective's eye distance (scene units; the seal is 2 wide); larger = flatter, 5 keeps the turning seal on the screen
MOVIE_SCALE = 1.0       # the movie draws the scene at full size (the boards draw it at ICEPI_SCREEN_SCALE)
ICEPI_SCREEN_SCALE = 0.934 # the Icepi pair draws in this much of its DAC's range: applied to the perspective table, so the scene, the
                        # animator's lengths and the rings all shrink.  The X board's drawing is moved up ICEPI_X_OFFSET, so it spans
                        # codes 16..255 and its lowest point still reads 8 ADC codes above the burst's gap (code 0) on the Y board's
                        # ADC (thr_gap); the Y board's spans 9..248 (nothing reads its DAC)
ICEPI_X_OFFSET = 120    # 12-bit engine codes (7.5 DAC codes) added to the X board's drawing, into show_params.vh's X_OFFSET
ICEPI_ADC_LINKS = ((0.759, 30.0), (0.788, 25.5))   # ADC code = gain x DAC code + offset through the tee, each board's DAC into the other's
                        # ADC, measured on the bench 2026-11-08 (5.00 measured 0.78 x + 27 on other modules: the threshold has room)
MOVIE_CYCLES = None     # finales in show_movie.mp4 (the seal every FINALES_PER_SEAL); None: each once; show_finales.mp4 has the seal once, then every finale
MOVIE_FPS = 30
MOVIE_WIDTH = 640       # pixels; the height follows the seal's aspect (0.8)
PHOSPHOR_TAU_S = 0.08   # the movie's persistence.  The Tektronix 2235 (and surely the 2212) have P31 phosphor, which decays in tens
                        # of microseconds, so what the eye keeps (50-100 ms) is the persistence on the scope: 0.08 models that
ICEPI_STEP_SHIFT = 3    # sub-step size: 2^(lead1 - shift) sub-steps a segment of 4096 codes: 8-16 codes of the engine's 12 bits,
                        # a half to one of the 8-bit DAC's codes
ICEPI_DWELL_FULL = 1    # the dwell at full speed: a new sub-step every sample (it was 2 with sub-steps twice the size: lines drawn
                        # as beads one to two codes apart)
MIN_SUBSTEPS = 8        # a drawn segment takes at least this many sub-steps (a power of 2), so at least 8 samples: more than the
                        # engine's 6 a vertex, so it runs ahead, the FIFO fills, and the globe's hidden half (a few hundred vertices,
                        # 70 us) is worked through while the beam draws what is queued.  1 = the length alone (the beam then waited on
                        # a vertex a third of the time and was parked below the screen 13-20 % of it, each park a streak and a dot)
ICEPI_SYNC_PERIOD_S = 0.02    # the Icepi pair's burst period: one burst and the animator (so the motion is updated 50 times a second), then
                        # as many frames back to back as fit.  Each burst parks the beam and brings it back to the first point, a
                        # streak and an overshoot (Jason, 2026-11-09: those are worse than a little shear; it was 4 ms, and a
                        # park every frame before that).  A register on the X board (1F) for trying others
ICEPI_RING_SKIP = 64    # the Icepi pair draws a ring from the period's burst's write pointer on, less this many of the oldest points, which
                        # the twins overwrite during the period (Lorenz about 15 in 20 ms, Chua 4); so both boards draw the same tail all
                        # period (the tail moves 50 times a second)
ICEPI_TX_DELAY = 9      # ticks added to the X board's wait after its burst (its animator's time is added by the gateware): measured
                        # on the bench 2026-11-08 from the strokes' jumps on both channels: 8 -> +32 ns, 9 -> -8 ns, 10 -> -52 ns (simulation said 7)
# ==========================================================================================

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "host"))
import scene, objects, gen_scene, gen_matrix_prog as gmp
RTL = os.path.join(HERE, "rtl")             # the gateware and its tables
RENDERS = os.path.join(HERE, "renders")     # not in git: the movies and the sheet
Q = 1 << 14
PH = gmp.PH
# what each kind of finale draws (ranges of the scene memory, or the ring), which phases it advances, which program section it runs
KINDS = {
    "lorenz":   dict(obj=None,       sec="lorenz", ph=["la", "lb", "lc"], ranges=["ring"]),
    "chua":     dict(obj=None,       sec="lorenz", ph=["la", "lb", "lc"], ranges=["ring2"]),
    "caffeine": dict(obj="caffeine", sec="tumble", ph=["ta", "tb", "tc"]),
    "lsd":      dict(obj="lsd",      sec="tumble", ph=["ta", "tb", "tc"]),
    "knot":     dict(obj="knot",     sec="tumble", ph=["ta", "tb", "tc"]),
    "dna":      dict(obj="dna",      sec="dna",    ph=["ds", "dn"]),
    "gears":    dict(obj="gears",    sec="gears",  ph=["gs", "gc", "gp"]),
    "arm":      dict(obj="arm",      sec="arm",    ph=["av", "aw"]),
    "em":       dict(obj="em",       sec="em",     ph=["pv", "em"]),
    "scope":    dict(obj="scope",    sec="scope",  ph=["pv", "u0", "u1", "u2", "u3", "u4"]),
    "pol":      dict(obj="pol",      sec="pol",    ph=["pv", "em"]),
    "sagnac":   dict(obj="sagnac",   sec="sagnac", ph=["pv", "u0", "u1", "u2"]),
    "drone":    dict(obj="drone",    sec="drone",  ph=["pv", "dr", "ps"]),
    "replicate": dict(obj="replicate", sec="replicate", ph=["pv", "u0", "u1", "u2", "u3"]),
    "transcribe": dict(obj="transcribe", sec="transcribe", ph=["pv", "sl", "em", "u0", "u1", "u2"], zero=["sl"]),
    "translate": dict(obj="translate", sec="translate", ph=["pv", "sl", "u0", "u1", "u2", "u3"], zero=["sl"]),
    "dish":     dict(obj="dish",     sec="dish",   ph=["pv", "pw"], zero=["pw"]),
    "sats":     dict(obj="sats",     sec="sats",   ph=["pv", "o1", "o2", "o3"], ranges=["globe3d", "sats"]),
    "ligo":     dict(obj="ligo",     sec="ligo",   ph=["pv", "em"]),
    "pcb":      dict(obj="pcb",      sec="pcb",    ph=["pv", "pc"]),
    "spinner":  dict(obj="spinner",  sec="spinner", ph=["sp"], zero=["sp"], ramp=True),
    "top":      dict(obj="top",      sec="top",    ph=["em", "gs", "ds"]),
    "pwave":    dict(obj="pwave",    sec="pwave",  ph=["pv", "pw"], zero=["pw"]),
    "generator": dict(obj="generator", sec="generator", ph=["pv", "em"]),
    "governor": dict(obj="governor", sec="governor", ph=["pv", "em"]),
    "boom":     dict(obj="boom",     sec="boom",   ph=["pv", "u0", "u1", "u2", "u3", "u4"], zero=["pv"]),
    "tek":      dict(obj="tek",      sec="tek",    ph=["sl"], zero=["sl"]),       # the swing from rest at each showing
    "kaleido":  dict(obj="kaleido",  sec="kaleido", ph=["sl", "av"], zero=["sl"]),   # flat (as printed) at each showing
}
EN_ALWAYS = (1 << PH["a"]) | (1 << PH["s"]); EN_FLIP = EN_ALWAYS | (1 << PH["b"])
def kind_ranges(kind): k = KINDS[kind]; return k.get("ranges") or [k["obj"]]
def kind_en(kind): return sum(1 << PH[p] for p in KINDS[kind]["ph"])
def kind_zero(kind): return sum(1 << PH[p] for p in KINDS[kind].get("zero", []))          # phases put to zero when the finale starts
def finale_ranges(f): return kind_ranges(FINALES[f][0])
def finale_en(f): return kind_en(FINALES[f][0])
def finale_zero(f): return kind_zero(FINALES[f][0])
def ramp():
    """the spinner's ramp (show_seq.v): T0, T1 ms; UP, DN per ms (2^32 a turn a ms)"""
    import proposals
    return proposals.Spinner.ramp()
def ramp_step(w, i, r):
    """the ramp's rate after millisecond i of the finale, from its rate w in it (the gateware's arithmetic)"""
    return 0 if i < r["T0"] else w + r["UP"] if i < r["T0"] + r["T1"] else (w - r["DN"] if w > r["DN"] else 0)

def turns_per_ms(turns_per_s): return int(round(turns_per_s / 1000 * 2 ** 32)) & 0xffffffff
def turns(t): return int(round(t * 2 ** 32)) & 0xffffffff
def rates():
    """The 32 phases' rates (per millisecond, 2^32 = a turn) and their values at power-up (a free phase: 0 and 0)."""
    w = [0] * 32; p0 = [0] * 32
    w[PH["a"]] = turns_per_ms(FLIP_AXIS_DEG_PER_S / 360); p0[PH["a"]] = turns(FLIP_AXIS_DEG / 360)
    w[PH["b"]] = turns_per_ms(FLIP_TURNS / T_FLIP); w[PH["s"]] = turns_per_ms(GLOBE_TURNS / (T_GLOBE - GLOBE_HOLD_S))
    for i, n in enumerate(("la", "lb", "lc")): w[PH[n]] = turns_per_ms(LORENZ_VIEW_TURNS_PER_S[i])
    for i, n in enumerate(("ta", "tb", "tc")): w[PH[n]] = turns_per_ms(TUMBLE_TURNS_PER_S[i])
    w[PH["ds"]] = turns_per_ms(DNA_TURNS_PER_S); w[PH["dn"]] = turns_per_ms(DNA_NOD_PER_S)
    g = objects.gear_constants()
    w[PH["gs"]] = turns_per_ms(GEAR_SUN_TURNS_PER_S); w[PH["gc"]] = turns_per_ms(GEAR_SUN_TURNS_PER_S * g["carrier_ratio"])
    w[PH["gp"]] = turns_per_ms(GEAR_SUN_TURNS_PER_S * g["planet_ratio"])
    w[PH["av"]] = turns_per_ms(ARM_VIEW_TURNS_PER_S); w[PH["aw"]] = turns_per_ms(ARM_WAVE_PER_S)
    w[PH["pv"]] = turns_per_ms(PHYS_VIEW_SWINGS_PER_S); w[PH["em"]] = turns_per_ms(EM_CYCLES_PER_S)
    nf = objects.SCOPE["n_fronts"]                      # the five staggered sawtooths (the telescope, the boom, ...)
    for i in range(nf): w[PH["u%d" % i]] = turns_per_ms(WAVEFRONT_PER_S); p0[PH["u%d" % i]] = turns(i / nf)
    for i in range(3): w[PH["o%d" % (i + 1)]] = turns_per_ms(SAT_TURNS_PER_S[i]); p0[PH["o%d" % (i + 1)]] = turns(i / 3)
    w[PH["dr"]] = turns_per_ms(DRONE_SWEEPS_PER_S); w[PH["ps"]] = turns_per_ms(PROP_TURNS_PER_S); w[PH["sl"]] = turns_per_ms(SLOW_PER_S)
    w[PH["pc"]] = turns_per_ms(PCB_STEP_PER_S); w[PH["pw"]] = turns_per_ms(1.0 / PWAVE_CYCLE_S)          # sp: 0, its rate is the ramp's
    import proposals
    assert proposals.TEK["swing_per_s"] == SLOW_PER_S, "the oscilloscope's swing (proposals.TEK) is on sl: SLOW_PER_S"
    assert proposals.KAL["ev_per_s"] == SLOW_PER_S and proposals.KAL["spin_per_s"] == ARM_VIEW_TURNS_PER_S, \
        "the kaleidocycle (proposals.KAL) turns on sl (SLOW_PER_S) and its view on av (ARM_VIEW_TURNS_PER_S)"
    return w, p0
def anim_consts(seal_scale):
    return dict(seal_scale=seal_scale, dna_nod=DNA_NOD_DEG / 360, arm_view_tilt=ARM_VIEW_TILT_DEG / 360,
                arm_off=ARM_OFF, arm_joints=ARM_JOINTS, phys_view_tilt=PHYS_VIEW_TILT_DEG / 360, phys_view_swing=PHYS_VIEW_SWING_DEG / 360,
                dish_per_s=1.0 / PWAVE_CYCLE_S)

def thr_gap():
    """The Y board's gap threshold in ADC codes: half way between the gap (DAC code 0) and the lowest the drawing goes
    (the screen's edge at ICEPI_SCREEN_SCALE), as the worse of the two measured links sees them."""
    low_code = (2048 - int(round(2047 * ICEPI_SCREEN_SCALE)) + ICEPI_X_OFFSET + 8) >> 4    # the X board's lowest code (12 bits rounded to 8)
    assert (2048 + int(round(2047 * ICEPI_SCREEN_SCALE)) + ICEPI_X_OFFSET + 8) >> 4 <= 255, "the X board's drawing passes code 255"
    gap = max(o for g, o in ICEPI_ADC_LINKS); drawing = min(g * low_code + o for g, o in ICEPI_ADC_LINKS)
    assert drawing - gap >= 8, ("the drawing comes within %.1f ADC codes of the gap: shrink ICEPI_SCREEN_SCALE" % (drawing - gap))
    return int(round((gap + drawing) / 2))

def write_params(write=True):
    """The parameters for show_params.vh, and the file (not with write=False: the movie needs only the values)."""
    clk = 50e6
    step_period = int(round(25e6 / (4096 * LORENZ_TIME_UNITS_PER_S)))     # 25 MS/s ticks per twin step
    kx = int(round(LORENZ_SCALE * Q / 25)); ky = int(round(LORENZ_SCALE * Q / 30)); kz = kx
    step_period2 = int(round(25e6 / (1024 * CHUA_TIME_UNITS_PER_S)))
    kx2, ky2, kz2 = (int(round(c * Q)) for c in CHUA_SCALE)
    w, p0 = rates(); rp = ramp()
    p = {
        "T_MODE1_MS": int(T_GLOBE * 1000), "T_MODE2_MS": int(T_FLIP * 1000), "GLOBE_HOLD_MS": int(round(GLOBE_HOLD_S * 1000)),
        "DWELL_FULL": ICEPI_DWELL_FULL, "SYNC_TICKS": int(round(ICEPI_SYNC_PERIOD_S * 25e6)),
        "STEP_SHIFT": ICEPI_STEP_SHIFT, "MIN_K": MIN_SUBSTEPS.bit_length() - 1,
        "W_AXIS": w[PH["a"]], "W_FLIP": w[PH["b"]], "W_SPIN": w[PH["s"]], "AXIS0": p0[PH["a"]],
        "W_LA": w[PH["la"]], "W_LB": w[PH["lb"]], "W_LC": w[PH["lc"]],
        "STEP_PERIOD": step_period, "RING_EVERY": RING_EVERY, "KX": kx, "KY": ky, "KZ": kz, "TX_DELAY": ICEPI_TX_DELAY & 0xffff,
        "THR_GAP": thr_gap(), "RING_SKIP": ICEPI_RING_SKIP, "X_OFFSET": ICEPI_X_OFFSET,
        "STEP_PERIOD2": step_period2, "RING_EVERY2": RING_EVERY2, "KX2": kx2, "KY2": ky2, "KZ2": kz2, "TAIL_HOLD": int(round(TAIL_HOLD_US * 25)),
        "PER_SEAL": FINALES_PER_SEAL, "RAMP_T0": rp["T0"], "RAMP_T1": rp["T1"], "RAMP_UP": rp["UP"], "RAMP_DN": rp["DN"],
    }
    assert MIN_SUBSTEPS & (MIN_SUBSTEPS - 1) == 0 and 1 <= MIN_SUBSTEPS <= 256, "MIN_SUBSTEPS: a power of 2"
    widths = {"RING_SKIP": 12, "X_OFFSET": 12, "GLOBE_HOLD_MS": 16, "DWELL_FULL": 16, "STEP_SHIFT": 4, "MIN_K": 4, "STEP_PERIOD": 16, "RING_EVERY": 12, "KX": 16, "KY": 16, "KZ": 16, "TX_DELAY": 16, "THR_GAP": 8,
              "STEP_PERIOD2": 16, "RING_EVERY2": 12, "KX2": 16, "KY2": 16, "KZ2": 16, "TAIL_HOLD": 16, "PER_SEAL": 5, "RAMP_T0": 16, "RAMP_T1": 16}
    if not write: return p
    with open(os.path.join(RTL, "show_params.vh"), "w") as f:
        f.write("// generated by make_show.py from its constants: the show's times, rates and speeds (icepi)\n")
        for k, v in p.items(): f.write("localparam [%d:0] %s = %d'd%d;\n" % (widths.get(k, 32) - 1, k, widths.get(k, 32), v))
        f.write("// the 32 phases' rates per millisecond (phases 0, 1 and 3-6 are taken from registers whose defaults are above; a free phase's is 0)\n")
        f.write("// and their values at power-up\n")
        f.write("localparam [1023:0] W_PH_FIXED = {%s};\n" % ", ".join("32'd%d" % w[k] for k in range(31, -1, -1)))
        f.write("localparam [1023:0] PH0_ALL = {%s};\n" % ", ".join("32'd%d" % p0[k] for k in range(31, -1, -1)))
    return p

def write_finales(layout, sections):
    """show_finales.vh: the finales' table for show_seq.v / show_ranges.v."""
    with open(os.path.join(RTL, "show_finales.vh"), "w") as f:
        f.write("// generated by make_show.py from FINALES: per finale its time, its ranges, its phases, its program section\n")
        f.write("localparam [4:0] NF = 5'd%d;\nlocalparam [31:0] EN_ALWAYS = 32'h%08x, EN_FLIP = 32'h%08x, ZERO_GLOBE = 32'h%08x;\n" % (len(FINALES), EN_ALWAYS, EN_FLIP, 1 << PH["s"]))
        f.write("function [15:0] fin_dur(input [4:0] f); begin case (f)\n")
        for i, (kind, t) in enumerate(FINALES): f.write("    5'd%d: fin_dur = 16'd%d;\n" % (i, int(t * 1000)))
        f.write("    default: fin_dur = 16'd5000; endcase end endfunction\n")
        f.write("function [27:0] fin_range(input [4:0] f, input [1:0] r); begin fin_range = 28'd0; case ({f, r})\n")
        for i in range(len(FINALES)):
            for r, name in enumerate(finale_ranges(i)):
                nr = 2048 - ICEPI_RING_SKIP
                if name == "ring": f.write("    7'd%d: fin_range = {2'd1, 13'd%d, 13'd0};\n" % (4 * i + r, nr))
                elif name == "ring2": f.write("    7'd%d: fin_range = {2'd2, 13'd%d, 13'd0};\n" % (4 * i + r, nr))
                else: f.write("    7'd%d: fin_range = {2'd0, L_%s_COUNT, L_%s_START};\n" % (4 * i + r, name.upper(), name.upper()))
        f.write("    default: fin_range = 28'd0; endcase end endfunction\n")
        f.write("function [31:0] fin_zero(input [4:0] f); begin case (f)\n")
        for i in range(len(FINALES)): f.write("    5'd%d: fin_zero = 32'h%08x;\n" % (i, finale_zero(i)))
        f.write("    default: fin_zero = 32'd0; endcase end endfunction\n")
        f.write("function [31:0] fin_en(input [4:0] f); begin case (f)\n")
        for i in range(len(FINALES)): f.write("    5'd%d: fin_en = 32'h%08x;\n" % (i, finale_en(i)))
        f.write("    default: fin_en = 32'd0; endcase end endfunction\n")
        f.write("function [11:0] fin_pc(input [4:0] f); begin case (f)\n")
        for i, (kind, t) in enumerate(FINALES): f.write("    5'd%d: fin_pc = PC_%s;\n" % (i, KINDS[kind]["sec"].upper()))
        f.write("    default: fin_pc = PC_SEAL; endcase end endfunction\n")
        f.write("function fin_ramp(input [4:0] f); begin case (f)\n")              # the spinner's ramp on phase 15 (show_seq.v)
        for i, (kind, t) in enumerate(FINALES):
            if KINDS[kind].get("ramp"): f.write("    5'd%d: fin_ramp = 1'b1;\n" % i)
        f.write("    default: fin_ramp = 1'b0; endcase end endfunction\n")

def ramp_phase(n_ms):
    """the spinner's phase n_ms into its finale"""
    import proposals
    r = ramp(); return proposals.Spinner.ramp_sum(r["T0"], r["T1"], r["UP"], r["DN"], int(n_ms)) & 0xffffffff
def _object_views(fins, samples=8):
    """Per finale object, its points' screen positions at `samples` moments spread over its finale (the animator's own
    matrices from the finale's phases at their rates): what gen_scene.order_strokes measures its jumps with."""
    P = gmp.build(anim_consts(1.0)); v0 = gmp.regs_init(P); w, p0 = rates(); views = {}
    def proj(pts, R, t):
        q = np.asarray(pts, float) @ R.T + t; sc = P_VIEW / (P_VIEW + q[:, 2]); return q[:, :2] * sc[:, None]
    for kind, secs in fins:
        o = KINDS[kind]["obj"]
        if not o or o in views: continue
        en = kind_en(kind) | EN_ALWAYS; z = kind_zero(kind); mats = []
        for k in range(samples):
            ms = secs * 1000.0 * k / samples
            ph = [((0 if z >> i & 1 else p0[i]) + (int(w[i] * ms) if en >> i & 1 else 0)) & 0xffffffff for i in range(32)]
            if KINDS[kind].get("ramp"): ph[PH["sp"]] = ramp_phase(ms)
            v = list(v0); gmp.load_phases(v, ph); gmp.run(v, P.prog, P.sections["seal"]); gmp.run(v, P.prog, P.sections[KINDS[kind]["sec"]])
            mats.append(gmp.matrices(v))
        views[o] = (lambda mats: lambda pts, g: np.stack([proj(pts, *m[g]) for m in mats], 1))(mats)
    return views

_ORDERS = None
def scene_orders(fins=None):
    """Every scene's strokes in drawing order (gen_scene.order_strokes), the finale objects' measured on the screen as they
    move; computed once a process (with other finales' when asked for), used by the scene memory and the movie's model alike."""
    global _ORDERS
    fins = FINALES if fins is None else fins
    if _ORDERS is not None and any(KINDS[k]["obj"] and KINDS[k]["obj"] not in _ORDERS for k, t in fins):
        views = _object_views(fins)
        for kind, secs in fins:
            obj = KINDS[kind]["obj"]
            if obj and obj not in _ORDERS: _ORDERS[obj] = gen_scene.order_strokes(objects.OBJECTS[obj](), views.get(obj))
    if _ORDERS is None:
        body = scene.split_seal(scene.load_seal()); globe, limb = scene.globe_scene()
        o = {"body": gen_scene.order_strokes([(p, 0) for p in body + [limb]]), "globe3d": gen_scene.order_strokes([(p, 1) for p in globe])}
        views = _object_views(fins)
        for kind, secs in fins:
            obj = KINDS[kind]["obj"]
            if obj and obj not in o: o[obj] = gen_scene.order_strokes(objects.OBJECTS[obj](), views.get(obj))
        _ORDERS = o
    return _ORDERS

def gen_tables():
    """The scene, the perspective and sine tables, the layout, the animator's program, the parameters and the finales'
    table, into rtl/."""
    assert len(FINALES) <= 32
    fins = [KINDS[k]["obj"] for k, t in FINALES]
    layout = gen_scene.write_scene(RTL, ICEPI_SCREEN_SCALE, P_VIEW, fins, scene_orders())
    P = gmp.build(anim_consts(1.0)); lens = gmp.write_all(P, [RTL], os.path.join(HERE, "host"), names={KINDS[k]["sec"] for k, t in FINALES})
    pp = write_params(); write_finales(layout, P.sections)
    json.dump([dict(kind=k, seconds=t) for k, t in FINALES], open(os.path.join(HERE, "host", "finales.json"), "w"), indent=1)
    print("tables written into rtl/; the program has %d instructions of %d, the longest section %d; %d constants"
          % (sum(lens.values()), gmp.PROG_MAX, max(lens.values()), P.nk))
    print("scene memory:", ", ".join("%s %d" % (k, n) for k, (s, n) in layout.items()))
    return pp

# ---------------- the movie: the show's timeline as the gateware runs it, drawn with a phosphor ----------------
def lead1(d): return d.bit_length() - 1 if d > 0 else 0

def substeps(path2d, step_shift, min_k=None):
    """The line generator's sub-steps for a frame: (N, 3) x, y in -1..1 and beam, 2^(lead1(d) - shift) a drawn segment, at
    least MIN_SUBSTEPS; a jump one."""
    if min_k is None: min_k = MIN_SUBSTEPS.bit_length() - 1
    out = []
    for pl, on in path2d:
        p = np.clip(np.round(np.asarray(pl) * 2047 + 2048), 0, 4095).astype(int)
        if len(p) == 0: continue
        prev = p[0]
        out.append(np.array([[p[0, 0], p[0, 1], 0]]))
        for q in p[1:]:
            d = int(max(abs(q[0] - prev[0]), abs(q[1] - prev[1])))
            k = max(min_k, lead1(d) - step_shift) if on else 0
            n = 1 << k
            f = np.arange(1, n + 1) / n
            seg = prev + f[:, None] * (q - prev)
            out.append(np.column_stack([seg, np.full(n, 1 if on else 0)]))
            prev = q
    a = np.vstack(out)
    return np.column_stack([(a[:, 0] - 2048) / 2047.0, (a[:, 1] - 2048) / 2047.0, a[:, 2]])

class Show:
    """A mirror of the sequencer, the animator (its microprogram run bit for bit) and the twin, advanced in movie frames."""
    def __init__(self, params, seal_scale, step_shift, dwell_full, compact=False, fins=None, seal=True):
        self.p = params; self.scale = seal_scale; self.step_shift = step_shift; self.dwell_full = dwell_full
        self.compact = compact                                 # the seal once, then the finales one after another (the movie for looking at them)
        self.fins = FINALES if fins is None else fins          # another list of finales, and with seal=False no seal
        self.P = gmp.build(anim_consts(seal_scale)); self.v0 = gmp.regs_init(self.P)
        self.w, self.ph = rates(); self.ph = list(self.ph)
        O = scene_orders(self.fins); sc = lambda pg: [(p * seal_scale, g) for p, g in pg]     # in the scene memory's order
        self.scenes = {"body": (sc(O["body"]), set()), "globe3d": (sc(O["globe3d"]), {1})}       # (strokes, the groups culled)
        for kind, t in self.fins:
            o = KINDS[kind]["obj"]
            if o and o not in self.scenes: self.scenes[o] = (sc(O[o]), objects.CULL.get(o, set()))
        # the sequencer's dwell (dwell_seq) and the engine's (dwell, taken at the start of a frame): full speed throughout now
        self.t = 0.0; self.mode = 1; self.fin = 0; self.t_in = 0.0; self.dwell = self.dwell_seq = dwell_full; self.ms_acc = 0.0
        self.nseen = 0                                        # finales shown since the seal (show_seq.v's cnt)
        self.rp = ramp(); self.rw = 0; self.rtm = 0           # the spinner's ramp: its rate and its milliseconds
        if not seal: self.mode = 3; self.enter()
        self.durs = [T_GLOBE, T_FLIP]                         # modes 1 and 2; the show starts in mode 1 and comes back to it
        self.v = np.array([-5.0, -7.0, 20.0]); self.ring = []; self.steps = 0; self.dt = 2 ** -12           # the twin and its ring
        self.v2 = np.array([0.1, 0.0, 0.0]); self.ring2 = []; self.steps2 = 0; self.dt2 = 2 ** -10            # Chua's, and its
        self.hold = int(round(TAIL_HOLD_US * 25))
    def dur(self): return self.durs[self.mode - 1] if self.mode < 3 else self.fins[self.fin][1]
    def kind(self): return self.fins[self.fin][0]
    def enter(self):
        """entering a mode, or a finale: the phases that start from zero, the ramp from rest"""
        if self.mode in (1, 2): self.ph[PH["b"]] = 0
        if self.mode == 1: self.ph[PH["s"]] = 0                  # the globe starts facing as the seal's own does
        if self.mode == 3:
            for k in range(32):
                if kind_zero(self.kind()) >> k & 1: self.ph[k] = 0
        self.rw = 0; self.rtm = 0
    def _f(self, v):
        x, y, z = v; return np.array([10 * (y - x), 28 * x - y - x * z, x * y - 8 / 3 * z])
    def _f2(self, v):
        """Chua with the gateware's shift-add constants: alpha 15.625, beta 28, m1 -23/32, (m0 - m1)/2 -7/32"""
        x, y, z = v; fx = -23 / 32 * x - 7 / 32 * (abs(x + 1) - abs(x - 1))
        return np.array([15.625 * (y - x - fx), x - y + z, -28 * y])
    def advance(self, dt):
        # the mode clock
        self.t += dt; self.t_in += dt
        if self.t_in >= self.dur():
            self.t_in -= self.dur()
            if self.mode == 3:                                   # the next finale; the seal after every FINALES_PER_SEAL of them
                self.fin = (self.fin + 1) % len(self.fins)
                if self.compact or self.nseen + 1 < FINALES_PER_SEAL: self.nseen += 1
                else: self.mode = 1; self.nseen = 0
            else:
                self.mode += 1
                if self.mode == 3: self.nseen = 0
            self.enter()
        # the phases, by whole milliseconds; the spinner's ramp a millisecond at a time, as show_seq.v steps it
        en = EN_ALWAYS if self.mode == 1 else EN_FLIP if self.mode == 2 else kind_en(self.kind()) | EN_ALWAYS
        self.ms_acc += dt * 1000; n = int(self.ms_acc); self.ms_acc -= n
        for k in range(32):
            if en >> k & 1: self.ph[k] = (self.ph[k] + n * self.w[k]) & 0xffffffff
        if self.mode == 3 and KINDS[self.kind()].get("ramp"):
            for _ in range(n):
                self.ph[PH["sp"]] = (self.ph[PH["sp"]] + self.rw) & 0xffffffff; self.rw = ramp_step(self.rw, self.rtm, self.rp); self.rtm += 1
        if self.mode == 1 and self.t_in < GLOBE_HOLD_S: self.ph[PH["s"]] = 0     # held still at first
        # the twin, always
        n = int(round(LORENZ_TIME_UNITS_PER_S * dt / self.dt))
        for _ in range(n):
            k1 = self._f(self.v); k2 = self._f(self.v + self.dt / 2 * k1); k3 = self._f(self.v + self.dt / 2 * k2); k4 = self._f(self.v + self.dt * k3)
            self.v = self.v + self.dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4); self.steps += 1
            if self.steps % RING_EVERY == 0:
                self.ring.append(np.array([self.v[0] / 25, self.v[1] / 30, (self.v[2] - 25) / 25]) * LORENZ_SCALE)
                if len(self.ring) > 2048: self.ring.pop(0)
        n = int(round(CHUA_TIME_UNITS_PER_S * dt / self.dt2))
        for _ in range(n):
            k1 = self._f2(self.v2); k2 = self._f2(self.v2 + self.dt2 / 2 * k1); k3 = self._f2(self.v2 + self.dt2 / 2 * k2); k4 = self._f2(self.v2 + self.dt2 * k3)
            self.v2 = self.v2 + self.dt2 / 6 * (k1 + 2 * k2 + 2 * k3 + k4); self.steps2 += 1
            if self.steps2 % RING_EVERY2 == 0:
                self.ring2.append(self.v2 * np.array(CHUA_SCALE))
                if len(self.ring2) > 2048: self.ring2.pop(0)
    def matrices(self):
        v = list(self.v0); gmp.load_phases(v, self.ph); gmp.run(v, self.P.prog, self.P.sections["seal"])
        if self.mode == 3: gmp.run(v, self.P.prog, self.P.sections[KINDS[self.kind()]["sec"]])
        return gmp.matrices(v)
    def ranges(self):
        if self.mode in (1, 2): return ["body", "globe3d"]
        return kind_ranges(self.kind())
    def frame_path(self):
        """The beam's sub-steps for the current frame, as the engine would make them."""
        mats = self.matrices(); segs = []
        for name in self.ranges():
            if name in ("ring", "ring2"):
                ring = self.ring if name == "ring" else self.ring2
                polys, cull = ([(np.array(ring), 2)] if len(ring) > 1 else [], set())
            else: polys, cull = self.scenes[name]
            for pl, g in polys:
                R, t = mats[g]
                q = pl @ R.T + t
                vis = np.ones(len(q), bool) if g not in cull else (q[:, 2] - t[2]) >= 0
                s = P_VIEW / (P_VIEW + q[:, 2]); xy = np.stack([q[:, 0] * s, q[:, 1] * s], -1)
                start = None                                # hidden vertices break the stroke and are not visited, nor is a visible
                for i in range(len(q) + 1):                 # one between hidden ones (vec3d sends a jump only before a drawn segment)
                    on = i < len(q) and vis[i]
                    if on and start is None: start = i
                    elif not on and start is not None:
                        if i - start >= 2: segs.append((xy[start:i], True))
                        start = None
                if name in ("ring", "ring2"): segs.append((np.repeat(xy[-1:], self.hold, axis=0), True))   # the hold on the tail's head
        return substeps(segs, self.step_shift) if segs else np.zeros((0, 3))

def caption(show):
    names = {1: "the seal, its 3D globe still, then turning", 2: "the seal turns over, the globe still turning"}
    what = names[show.mode] if show.mode < 3 else "finale %d of %d: %s" % (show.fin + 1, len(show.fins), show.kind())
    return "t = %5.1f s   mode %d: %s   dwell %d" % (show.t, show.mode, what, show.dwell)

def render_movie(params, cycles, fps, compact=False):
    """show_movie.mp4: the show as the scope shows it, until `cycles` finales have been (the seal after every
    FINALES_PER_SEAL); with compact, show_finales.mp4: the seal once, then every finale back to back, and
    finales_sheet.png with three moments of each."""
    from PIL import Image, ImageDraw
    from scipy.ndimage import gaussian_filter
    W = MOVIE_WIDTH; H = int(W * 0.8); W += W % 2; H += H % 2
    show = Show(params, MOVIE_SCALE, ICEPI_STEP_SHIFT, ICEPI_DWELL_FULL, compact)
    fins = show.fins
    if compact: total = sum(show.durs) + sum(t for _, t in fins)
    else: total = sum(show.durs) * -(-cycles // FINALES_PER_SEAL) + sum(fins[i % len(fins)][1] for i in range(cycles))
    n_frames = int(total * fps); dt = 1.0 / fps
    img = np.zeros((H, W)); decay = math.exp(-dt / PHOSPHOR_TAU_S)
    cursor = 0.0
    # the brightness normalisation: a full-speed frame of the seal, steady state
    show0 = Show(params, MOVIE_SCALE, ICEPI_STEP_SHIFT, ICEPI_DWELL_FULL)
    p0 = show0.frame_path(); ref = np.zeros((H, W))
    ix = np.clip(((p0[:, 0] + 1) / 2 * (W - 1)).astype(int), 0, W - 1); iy = np.clip(((0.8 - p0[:, 1]) / 1.6 * (H - 1)).astype(int), 0, H - 1)
    np.add.at(ref, (iy, ix), np.where(p0[:, 2] > 0, 1.0, 0.1) * dt / len(p0)); ref = gaussian_filter(ref, 1.0) / (1 - decay)
    norm = np.percentile(ref[ref > 0], 99.0)
    mp4 = os.path.join(RENDERS, "show_finales.mp4" if compact else "show_movie.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
    t0 = time.time()
    sheet = {}                                                 # (finale, k): the frame at 0.25, 0.55, 0.85 of the finale's time
    for fi in range(n_frames):
        path = show.frame_path()
        n_sub = 25e6 / show.dwell * dt
        img *= decay
        if len(path):
            w_each = show.dwell / 25e6                         # seconds of beam per sub-step
            if n_sub >= len(path):
                reps = n_sub / len(path); sel = path; w = np.where(sel[:, 2] > 0, 1.0, 0.1) * w_each * reps
                show.dwell = show.dwell_seq                    # whole frames this movie frame: each starts with the sequencer's dwell
            else:
                n = int(n_sub); c = int(cursor) % len(path)
                idx = (c + np.arange(n)) % len(path); sel = path[idx]; w = np.where(sel[:, 2] > 0, 1.0, 0.1) * w_each
                if cursor + n_sub >= len(path): show.dwell = show.dwell_seq   # a frame ended: the next starts at the new dwell
                cursor = (cursor + n_sub) % len(path)
            ix = np.clip(((sel[:, 0] + 1) / 2 * (W - 1)).astype(int), 0, W - 1); iy = np.clip(((0.8 - sel[:, 1]) / 1.6 * (H - 1)).astype(int), 0, H - 1)
            dep = np.zeros((H, W)); np.add.at(dep, (iy, ix), w); img += gaussian_filter(dep, 1.0)
        v = np.clip(img / norm, 0, 1) ** 0.5
        rgb = np.zeros((H, W, 3)); rgb[..., 1] = v; rgb[..., 0] = 0.55 * v ** 2; rgb[..., 2] = 0.25 * v ** 2
        frame = Image.fromarray((rgb * 255).astype(np.uint8))
        if show.mode == 3 and compact:
            for k, frac in enumerate((0.25, 0.55, 0.85)):
                if (show.fin, k) not in sheet and show.t_in >= frac * show.dur(): sheet[(show.fin, k)] = frame.copy()
        ImageDraw.Draw(frame).text((6, H - 14), caption(show), fill=(200, 200, 200))
        ff.stdin.write(frame.tobytes())
        show.advance(dt)
        if fi % (fps * 10) == 0: print("  movie: %5.1f of %.1f s rendered (%.0f s elapsed)" % (fi / fps, total, time.time() - t0), flush=True)
    ff.stdin.close(); ff.wait()
    # the finales' sheet: three moments of each
    nf = max((f for f, k in sheet), default=-1) + 1
    if nf:
        cols = 3; rows = nf
        tile = (W // 2, H // 2); S = Image.new("RGB", (cols * tile[0], rows * tile[1]))
        for (f, k), im in sheet.items(): S.paste(im.resize(tile), (k * tile[0], f * tile[1]))
        d = ImageDraw.Draw(S)
        for f in range(nf): d.text((4, f * tile[1] + 4), "%d: %s" % (f, fins[f][0]), fill=(220, 220, 220))
        S.save(os.path.join(RENDERS, "finales_sheet.png"))
    print("wrote", mp4, "(%d frames, %.0f s)" % (n_frames, time.time() - t0))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--movie", action="store_true", help="and the two movies and the sheet, in renders/")
    ap.add_argument("--quick", action="store_true", help="and a short movie: the seal and the first FINALES_PER_SEAL finales at 10 frames a second")
    a = ap.parse_args()
    params = gen_tables()
    if a.movie or a.quick:
        os.makedirs(RENDERS, exist_ok=True)
        if a.quick: render_movie(params, FINALES_PER_SEAL, 10)
        else:
            render_movie(params, MOVIE_CYCLES or len(FINALES), MOVIE_FPS)
            render_movie(params, MOVIE_CYCLES or len(FINALES), MOVIE_FPS, compact=True)
