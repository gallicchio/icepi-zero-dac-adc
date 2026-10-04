"""7.06: the measurements.  Step responses at several gains, the gain sweep that finds the
critical gain and the oscillation period (twice the loop delay), and the disturbance
rejection: the controller fighting the M2k's W1, and the sensitivity function |S(f)|.

    python3 fig_control_measured.py --sim                         # control_model.py's loop; all three figures
    python3 fig_control_measured.py PORT --mode 0                 # the loopback bench: steps and sweep
    python3 fig_control_measured.py PORT --mode 1 --m2k           # the M2k bench: steps, sweep and rejection
    python3 fig_control_measured.py PORT --mode 1 --what sweep    # one of steps, sweep, reject
    python3 fig_control_measured.py --replot [--mode 1]           # from the saved data

Writes dev/data/dsp_control_<steps|sweep|reject>[_m<mode>].npz and
tutorial/img/dsp_control_<steps|sweep|reject>[_m<mode>].png (mode 0's files have no suffix:
they are the page's main ones).  'reject' needs a W1 into ADC IN, so modes 1 and 2 only.

What each run does, in the three modes:
  steps   mode 0: Kp 0.4, 0.8, 1.1 (P) and 0.6 with Ki 0.03 (PI); a 20-code step.
          mode 1: the lag K = 4 with 5 extra samples of delay (a 7-sample round trip, like
                  the real loop): Kp 1, 2, 3.5, and 2 with Ki 0.05; a 40-code step.
          mode 2: the 100 kHz resonator, Q 25.7: Kp 0.5 and 1.2, and PID 0.5 / 0.005 / 16:
                  the D term is the damping the plant lacks.
  sweep   Kp from low to past the critical gain, P only; the hum's amplitude and frequency
          at each, and the record where it sings.
  reject  mode 1 or 2 with Kp 2 (0.5 in mode 2), Ki 0.05 (0.005), Kd 0 (16): a 5 kHz square
          wave from W1, loop open and closed; then sines at 20 frequencies: |S(f)|.
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.join(HERE, "..", "..", "..")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(TOP, "src", "dsp"))
from plotstyle import plt, C1, C2, C3, INK, INK2, MUTED   # noqa: E402
import control                                            # noqa: E402
import control_model as cm                                # noqa: E402

TS = cm.TS
PRE = control.PRE


def data_path(name, mode):
    return os.path.join(TOP, "dev", "data", "dsp_control_%s%s.npz" % (name, "" if mode == 0 else "_m%d" % mode))


def img_path(name, mode):
    return os.path.join(TOP, "tutorial", "img", "dsp_control_%s%s.png" % (name, "" if mode == 0 else "_m%d" % mode))


def base_config(mode):
    if mode == 0:
        return control.Config(mode=0, step=20, nstep=12)
    if mode == 1:
        return control.Config(mode=1, klag=4, ldelay=5, step=40, nstep=12)
    return control.Config(mode=2, f0=100e3, qshift=10, step=40, nstep=13)


GAINS = {0: [(0.4, 0, 0), (0.8, 0, 0), (1.1, 0, 0), (0.6, 0.03, 0)],
         1: [(1.0, 0, 0), (2.0, 0, 0), (3.5, 0, 0), (2.0, 0.05, 0)],
         2: [(0.5, 0, 0), (1.2, 0, 0), (0.5, 0.005, 16)]}
SWEEPS = {0: np.arange(0.3, 1.61, 0.1), 1: np.arange(1.0, 6.01, 0.5), 2: np.arange(0.25, 2.51, 0.25)}
REJECT = {1: (2.0, 0.05, 0.0), 2: (0.5, 0.005, 16.0)}


# ---- the runs ---------------------------------------------------------------------------------
def run_steps(dev, mode):
    cfg = base_config(mode)
    recs = [control.step_response(dev, cfg.copy(kp=kp, ki=ki, kd=kd)) for kp, ki, kd in GAINS[mode]]
    for r in recs:
        print("  Kp %g Ki %g Kd %g:" % (r["kp"], r["ki"], r["kd"]), end=" ")
        control.print_metrics(r)
    out = dict(mode=mode, source=dev.source, kp=[r["kp"] for r in recs], ki=[r["ki"] for r in recs],
               kd=[r["kd"] for r in recs], t=recs[0]["t"], sp=np.array([r["sp"] for r in recs]),
               pv=np.array([r["pv"] for r in recs]), u=np.array([r["u"] for r in recs]),
               e=np.array([r["e"] for r in recs]), describe=cfg.describe(), nstep=cfg.nstep, decim=cfg.decim)
    for key in ("rise", "overshoot", "settle", "error"):
        out[key] = np.array([r.get(key, np.nan) for r in recs])
    return out


def run_sweep(dev, mode):
    cfg = base_config(mode)
    r = control.gain_sweep(dev, cfg, SWEEPS[mode])
    control.print_sweep(r)
    s = cfg.settings()
    r["kp_theory"], r["f_theory"] = cm.critical_gain(s, cm.Cable() if mode == 0 else None)
    r["ldelay"], r["klag"] = cfg.ldelay, cfg.klag
    return r


def run_reject(dev, mode, w1):
    kp, ki, kd = REJECT[mode]
    cfg = base_config(mode).copy(kp=kp, ki=ki, kd=kd, stepping=False)
    d = control.disturbance_demo(dev, w1, cfg, 5e3, 1.0)
    freqs = np.logspace(np.log10(2e3), np.log10(3e6), 20)
    b = control.sensitivity_sweep(dev, w1, cfg, freqs, 0.5)
    out = dict(mode=mode, source=dev.source, describe=cfg.describe(), f_dist=d["f"], t=d["t"],
               x=d["closed"]["x"], meas_closed=d["closed"]["meas"], meas_open=d["open"]["meas"],
               u_closed=d["closed"]["u"], u_open=d["open"]["u"], rejection_db=d["rejection_db"],
               t_m2k=d["closed"]["t_m2k"], v_m2k_closed=d["closed"]["v_m2k"], v_m2k_open=d["open"]["v_m2k"],
               f=b["f"], S=b["S"], f_model=b["f_model"], S_model=b["S_model"])
    return out


# ---- the figures ----------------------------------------------------------------------------------
def fig_steps(d):
    mode = int(d["mode"])
    t = (d["t"] - PRE * TS * 2**int(d["decim"])) * 1e6
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0), gridspec_kw=dict(width_ratios=[1.2, 1]))
    cols = [C1, C3, C2, INK2]
    span = {0: 4.0, 1: 4.0, 2: 60.0}[mode]
    for k in range(len(d["kp"])):
        lbl = "Kp = %g" % d["kp"][k] + (", Ki = %g" % d["ki"][k] if d["ki"][k] else "") + (", Kd = %g" % d["kd"][k] if d["kd"][k] else "")
        ax[0].plot(t, d["pv"][k], color=cols[k % 4], lw=1.2, label=lbl)
        ax[1].plot(t, d["u"][k], color=cols[k % 4], lw=1.0, label=lbl)
    ax[0].step(t, d["sp"][0], where="post", color=MUTED, lw=0.9, ls="--")
    ax[0].set_xlim(-0.1 * span, span)
    ax[1].set_xlim(-0.1 * span, span)
    ax[0].set_xlabel("time after the setpoint step (µs)")
    ax[1].set_xlabel("time after the setpoint step (µs)")
    ax[0].set_ylabel("the measurement (ADC codes)" if mode == 0 else "the plant's output y (codes)")
    ax[1].set_ylabel("u, the controller's output (DAC codes)")
    ax[0].set_title({0: "the real loop through the cable: 280 ns around",
                     1: "the lag (τ = 0.64 µs) with a 7-sample round trip",
                     2: "the 100 kHz resonator, Q = 26: D is its damping"}[mode])
    ax[1].set_title("what the DAC did")
    ax[0].legend(loc="lower right", fontsize=8)
    fig.text(0.995, 0.005, str(d["source"]), ha="right", va="bottom", size=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(img_path("steps", mode), dpi=130)
    plt.close(fig)
    print("wrote", img_path("steps", mode))


def fig_sweep(d):
    mode = int(d["mode"])
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0), gridspec_kw=dict(width_ratios=[1, 1.2]))
    kps, tail, f_ring = d["kps"], d["tail"], d["f_ring"]
    ax[0].plot(kps, tail, "o-", color=C1, label="the hum's amplitude (codes rms)")
    ax[0].set_xlabel("Kp")
    ax[0].set_ylabel("ringing left at the end of the record (codes rms)", color=C1)
    ax2 = ax[0].twinx()
    hum = tail >= 1.0                                   # only where there is a hum to time
    ax2.plot(kps[hum], f_ring[hum] / 1e6, "s", color=C2, ms=4, label="its frequency")
    ax2.set_ylabel("ringing frequency (MHz)", color=C2)
    ax2.grid(False)
    f_top = np.nanmax(f_ring[hum]) / 1e6 if hum.any() else 1.0
    ax2.set_ylim(0, 1.6 * f_top)
    ax2.ticklabel_format(useOffset=False)
    ax[0].set_ylim(0, max(tail.max(), 1.0) * 1.25)
    if "kp_crit" in d:
        ax[0].axvline(float(d["kp_crit"]), color=INK, lw=0.9, ls="--")
        ax[0].text(float(d["kp_crit"]), ax[0].get_ylim()[1] * 0.97, "critical: Kp = %.2f " % float(d["kp_crit"]), size=8, va="top", ha="right", color=INK)
    if "kp_theory" in d and np.isfinite(float(d["kp_theory"])):
        ax[0].axvline(float(d["kp_theory"]), color=MUTED, lw=0.9, ls=":")
        ax[0].text(float(d["kp_theory"]), ax[0].get_ylim()[1] * 0.88, "model: %.2f " % float(d["kp_theory"]), size=8, va="top", ha="right", color=MUTED)
    ax[0].set_title({0: "raise Kp until the cable loop sings", 1: "the lag with a 7-sample round trip", 2: "the resonator"}[mode])
    h1, l1 = ax[0].get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax[0].legend(h1 + h2, l1 + l2, loc="center left", fontsize=8)
    if "e_unstable" in d:
        e = d["e_unstable"]
        dt = TS * 2**int(d["decim"])
        t = (np.arange(len(e)) - PRE) * dt * 1e6
        ax[1].plot(t, e, color=C2, lw=0.9)
        per = float(d["period"])
        n_show = int(min(len(e) - PRE, 8 * per / dt))
        ax[1].set_xlim(-0.05 * n_show * dt * 1e6, n_show * dt * 1e6)
        k0 = PRE + int(n_show * 0.45)
        seg = e[k0:k0 + int(2 * per / dt) + 1]
        i0 = k0 + int(np.argmax(seg))
        i1 = i0 + int(round(per / dt))
        y = e[i0] * 1.08 + 8
        ax[1].annotate("", (t[i1], y), (t[i0], y), arrowprops=dict(arrowstyle="<|-|>", color=INK, lw=1.0))
        ax[1].text(0.5 * (t[i0] + t[i1]), y + 3, "period %.1f samples = %.0f ns" % (per / TS, per * 1e9) +
                   ("\n= 2τ/(2k+1): τ = %.0f, %.0f or %.0f ns; the hum below\ncritical gain says which (280 ns)" % (per / 2 * 1e9, 3 * per / 2 * 1e9, 5 * per / 2 * 1e9) if mode == 0 else ""),
                   ha="center", va="bottom", size=8, color=INK)
        shown = e[:PRE + n_show]
        ax[1].set_ylim(shown.min() - 10, shown.max() * 1.1 + 40)
        ax[1].set_title("Kp = %.2f: it sings at %.3f MHz" % (float(d["kp_unstable"]), float(d["f_osc"]) / 1e6))
        ax[1].set_xlabel("time after the setpoint step (µs)")
        ax[1].set_ylabel("e (codes)")
    fig.text(0.995, 0.005, str(d["source"]), ha="right", va="bottom", size=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(img_path("sweep", mode), dpi=130)
    plt.close(fig)
    print("wrote", img_path("sweep", mode))


def fig_reject(d):
    mode = int(d["mode"])
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0), gridspec_kw=dict(width_ratios=[1.1, 1]))
    t = d["t"] * 1e3
    n = int(min(len(t), 3.0 / float(d["f_dist"]) / (t[1] - t[0]) * 1e3))     # three periods
    ax[0].plot(t[:n], d["meas_open"][:n], color=C2, lw=0.9, label="loop open: the disturbance, as the ADC sees it")
    ax[0].plot(t[:n], d["meas_closed"][:n], color=C1, lw=0.9, label="loop closed: what is left of it (%.0f dB)" % float(d["rejection_db"]))
    ax[0].plot(t[:n], d["u_closed"][:n], color=C3, lw=0.8, alpha=0.8, label="u: the DAC pushing back")
    ax[0].set_xlabel("time (ms)")
    ax[0].set_ylabel("codes")
    ax[0].set_title("a %.0f kHz square wave from W1 into ADC IN" % (float(d["f_dist"]) / 1e3))
    ax[0].legend(loc="upper right", fontsize=7.5)
    S, f = d["S"], d["f"]
    ax[1].semilogx(d["f_model"], 20 * np.log10(np.abs(d["S_model"])), color=INK2, lw=1.0, label="model: |1 / (1 + C H)|")
    ax[1].semilogx(f, 20 * np.log10(np.abs(S)), "o", color=C1, ms=5, label="|S| measured")
    ax[1].axhline(0, color=MUTED, lw=0.8)
    ax[1].fill_between(d["f_model"], 20 * np.log10(np.abs(d["S_model"])), 0,
                       where=np.abs(d["S_model"]) > 1, color=C2, alpha=0.2, lw=0)
    k = np.argmax(np.abs(S) >= 1) if np.any(np.abs(S) >= 1) else None
    if k:
        ax[1].annotate("rejected below\nthe loop bandwidth", xy=(f[k] / 10, -24), ha="center", va="top", size=8, color=INK2)
        ax[1].annotate("the waterbed:\namplified above it", xy=(f[k] * 1.6, 20 * np.log10(np.abs(S).max()) + 1),
                       ha="center", va="bottom", size=8, color=C2)
    ax[1].set_xlabel("frequency of the disturbance (Hz)")
    ax[1].set_ylabel("|S| (dB): how much of it gets through")
    ax[1].set_title("the sensitivity function")
    ax[1].legend(loc="lower right", fontsize=8)
    ax[1].grid(True, which="both")
    ax[1].set_ylim(min(-45, 20 * np.log10(np.abs(S).min()) - 3), max(8, 20 * np.log10(np.abs(S).max()) + 10))
    fig.text(0.995, 0.005, str(d["source"]), ha="right", va="bottom", size=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(img_path("reject", mode), dpi=130)
    plt.close(fig)
    print("wrote", img_path("reject", mode))


# ---- main ----------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", nargs="?", help="the board's serial port")
    ap.add_argument("--sim", action="store_true", help="control_model.py's loop instead of a board")
    ap.add_argument("--replot", action="store_true", help="redraw from the saved data")
    ap.add_argument("--mode", type=int, default=None, help="0 cable, 1 lag, 2 resonator (default: all in --sim, else 0)")
    ap.add_argument("--what", default=None, help="steps,sweep,reject (default: all that the bench allows)")
    ap.add_argument("--m2k", action="store_true", help="an M2k's W1 is on ADC IN: run 'reject' on the board")
    a = ap.parse_args()
    if not (a.sim or a.replot or a.port):
        ap.error("give the board's port, or --sim, or --replot")
    modes = [a.mode] if a.mode is not None else ([0, 1, 2] if (a.sim or a.replot) else [0])
    for mode in modes:
        what = a.what.split(",") if a.what else ["steps", "sweep"] + (["reject"] if mode and (a.sim or a.m2k or a.replot) else [])
        if a.replot:
            for name in what:
                p = data_path(name, mode)
                if not os.path.exists(p):
                    print("no", p)
                    continue
                d = dict(np.load(p, allow_pickle=True))
                {"steps": fig_steps, "sweep": fig_sweep, "reject": fig_reject}[name](d)
            continue
        dev = control.Sim() if a.sim else control.Board(a.port)
        for name in what:
            print("== mode %d: %s" % (mode, name))
            if name == "steps":
                d = run_steps(dev, mode)
            elif name == "sweep":
                d = run_sweep(dev, mode)
            elif name == "reject":
                if mode == 0:
                    print("'reject' needs W1 into ADC IN: modes 1 and 2 only")
                    continue
                w1 = control.open_w1(argparse.Namespace(sim=a.sim), dev)
                d = run_reject(dev, mode, w1)
                w1.close()
            else:
                raise SystemExit("what is %r?" % name)
            np.savez(data_path(name, mode), **d)
            print("saved", data_path(name, mode))
            {"steps": fig_steps, "sweep": fig_sweep, "reject": fig_reject}[name](d)
        dev.close()


if __name__ == "__main__":
    main()
