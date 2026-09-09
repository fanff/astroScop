"""Re-derive PI plant numbers and look for drivetrain PE vs loop hunt vs noise."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from asc_rates import (
    ASC_SIDEREAL_STEPS_PER_SEC,
    ASC_SIDEREAL_UI_SPEED,
    ASC_STEPS_PER_DEGREE,
    SKY_DEG_PER_SEC,
)
from guide_geom import (
    ASC_ARCSEC_PER_STEP,
    IMX477_PIXEL_PITCH_UM,
    PLATE_SCALE_ARCSEC_FACTOR,
    plate_scale_arcsec_per_px,
)
from guide_pid import KI, KP

SAVED = Path(__file__).resolve().parent.parent / "savedimgs"
OUT = SAVED / "guide_trace_plots"
FILES = [
    SAVED / "guide_trace_20260905T225553Z.csv",
    SAVED / "guide_trace_20260906T000032Z.csv",
]
KP_USED = KP
KI_USED = KI
MOTOR_FULLSTEPS = 200  # NEMA-typical; used only as a candidate marker
HW_MICROSTEPS = 8


def load(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    t = np.array([float(r["t"]) for r in rows])
    d = {
        "name": path.stem.replace("guide_trace_", ""),
        "t": t,
        "t_rel": t - t[0],
        "e_asc_arcsec": np.array([float(r["e_asc_arcsec"]) for r in rows]),
        "e_dec_arcsec": np.array([float(r["e_dec_arcsec"]) for r in rows]),
        "e_asc_px": np.array([float(r["e_asc_px"]) for r in rows]),
        "e_dec_px": np.array([float(r["e_dec_px"]) for r in rows]),
        "dAsc": np.array([float(r["dAsc"]) for r in rows]),
        "dDec": np.array([float(r["dDec"]) for r in rows]),
        "snr": np.array([float(r["snr"]) for r in rows]),
        "dec_deg": float(rows[0]["dec_deg"]),
        "focal_mm": float(rows[0]["focal_mm"]),
        "bin": int(rows[0]["bin"]),
        "stack_n": int(rows[0]["stack_n"]),
    }
    d["dt"] = float(np.median(np.diff(d["t_rel"])))
    d["r_px"] = np.hypot(d["e_asc_px"], d["e_dec_px"])
    return d


def moving_mean(y: np.ndarray, dt: float, win_s: float) -> np.ndarray:
    k = max(3, int(round(win_s / dt)))
    if k % 2 == 0:
        k += 1
    return np.convolve(y, np.ones(k) / k, mode="same")


def band_fft(t: np.ndarray, y: np.ndarray, fmin: float, fmax: float) -> dict:
    dt = float(np.median(np.diff(t)))
    z = y - y.mean()
    n = len(z)
    mag = np.abs(np.fft.rfft(z))
    xf = np.fft.rfftfreq(n, d=dt)
    band = (xf >= fmin) & (xf <= fmax)
    if not np.any(band):
        return {"f": float("nan"), "T": float("nan"), "mag": 0.0, "xf": xf, "amp": mag}
    i = int(np.argmax(np.where(band, mag, 0.0)))
    f = float(xf[i])
    # single-sided amplitude ~ 2/n * mag for a sinusoid
    amp = 2.0 * mag[i] / n
    return {"f": f, "T": (1.0 / f) if f > 0 else float("nan"), "mag": float(mag[i]), "amp": amp, "xf": xf, "spec": mag}


def window_peaks(t: np.ndarray, y: np.ndarray, win_s: float, fmin: float, fmax: float) -> list[dict]:
    t0, t1 = float(t[0]), float(t[-1])
    out = []
    start = t0
    while start + win_s * 0.8 <= t1:
        m = (t >= start) & (t < start + win_s)
        if m.sum() >= 64:
            pk = band_fft(t[m], y[m], fmin, fmax)
            pk["t0"] = start - t0
            pk["rms"] = float(y[m].std())
            out.append(pk)
        start += win_s / 2.0
    return out


def plant_numbers(dec_deg: float, f_mm: float, bin_: int) -> dict:
    s = plate_scale_arcsec_per_px(f_mm, bin_)
    cos_d = abs(math.cos(math.radians(dec_deg)))
    g_asc = (ASC_ARCSEC_PER_STEP * cos_d) / s  # px/s per STEP/s
    g_dec = ASC_ARCSEC_PER_STEP / s
    return {
        "plate_arcsec_px": s,
        "arcsec_per_step": ASC_ARCSEC_PER_STEP,
        "cos_d": cos_d,
        "G_asc": g_asc,
        "G_dec": g_dec,
    }


def closed_loop(G: float, kp: float = KP_USED, ki: float = KI_USED) -> dict:
    wn = math.sqrt(G * ki)
    zeta = kp / 2.0 * math.sqrt(G / ki) if ki > 0 else float("inf")
    wd = wn * math.sqrt(max(1.0 - zeta * zeta, 0.0))
    Td = (2.0 * math.pi / wd) if wd > 0 else float("nan")
    return {
        "wn": wn,
        "zeta": zeta,
        "Tn": 2.0 * math.pi / wn if wn else float("nan"),
        "Td": Td,
        "P_bw": G * kp,  # 1/s, first-order P-only
        "tau_P": 1.0 / (G * kp) if kp and G else float("nan"),
    }


def print_plant() -> None:
    s = plate_scale_arcsec_per_px(18.0, 2)
    print("=== constants ===")
    print(f"pixel pitch {IMX477_PIXEL_PITCH_UM} um  plate-scale factor {PLATE_SCALE_ARCSEC_FACTOR}")
    print(f"18 mm bin2 plate scale = {s:.4f} arcsec/px")
    print(f"ASC_STEPS_PER_DEGREE = {ASC_STEPS_PER_DEGREE:.4f}")
    print(f"ASC_ARCSEC_PER_STEP  = {ASC_ARCSEC_PER_STEP:.4f}  (sky HA)")
    print(f"sidereal cmd {ASC_SIDEREAL_UI_SPEED} STEP/s  sky {SKY_DEG_PER_SEC*3600:.4f} arcsec/s")
    print(f"Kp={KP_USED}  Ki={KI_USED}  (PI on e_*_px, output STEP/s)")
    print()
    for dec in (0.0, 15.0):
        p = plant_numbers(dec, 18.0, 2)
        cl_a = closed_loop(p["G_asc"])
        cl_d = closed_loop(p["G_dec"])
        print(f"--- dec={dec:.0f} deg  cos(dec)={p['cos_d']:.4f} ---")
        print(f"  G_asc={p['G_asc']:.5f} px/s per STEP/s   G_dec={p['G_dec']:.5f}")
        print(
            f"  ASC  zeta={cl_a['zeta']:.3f}  Tn={cl_a['Tn']:.1f}s ({cl_a['Tn']/60:.2f} min)  "
            f"Td={cl_a['Td']:.1f}s  P-only tau={cl_a['tau_P']:.1f}s"
        )
        print(
            f"  DEC  zeta={cl_d['zeta']:.3f}  Tn={cl_d['Tn']:.1f}s ({cl_d['Tn']/60:.2f} min)  "
            f"Td={cl_d['Td']:.1f}s  P-only tau={cl_d['tau_P']:.1f}s"
        )
        print(
            f"  at 4 px: P={KP_USED*4:.2f} STEP/s   dI/dt={KI_USED*4:.3f} STEP/s^2   "
            f"time-to-rail from 0 = {8.0/(KI_USED*4):.1f}s"
        )
        print()


def pi_split(d: dict) -> dict:
    p_asc = KP_USED * d["e_asc_px"]
    p_dec = KP_USED * d["e_dec_px"]
    i_asc = d["dAsc"] - p_asc
    i_dec = d["dDec"] - p_dec
    dead = d["r_px"] <= 0.5
    sat_a = np.abs(d["dAsc"]) >= 7.99
    sat_d = np.abs(d["dDec"]) >= 7.99
    return {
        "p_asc": p_asc,
        "p_dec": p_dec,
        "i_asc": i_asc,
        "i_dec": i_dec,
        "dead": dead,
        "sat_a": sat_a,
        "sat_d": sat_d,
    }


def motor_period_s(step_s: float) -> float:
    fs = abs(step_s) / HW_MICROSTEPS
    if fs <= 1e-6:
        return float("nan")
    return MOTOR_FULLSTEPS / fs


def analyze_one(d: dict) -> None:
    pi = pi_split(d)
    t = d["t_rel"]
    dt = d["dt"]
    print(f"=== {d['name']}  dec={d['dec_deg']:.0f} deg  stack={d['stack_n']}  dt={dt:.3f}s ===")
    print(
        f"  deadband {100*pi['dead'].mean():.1f}% of samples  "
        f"(hypot e_px <= 0.5)"
    )
    for axis, p, iest, dw in (
        ("ASC", pi["p_asc"], pi["i_asc"], d["dAsc"]),
        ("DEC", pi["p_dec"], pi["i_dec"], d["dDec"]),
    ):
        p_ac = p - p.mean()
        i_ac = iest - iest.mean()
        print(
            f"  {axis}  mean P={p.mean():+.3f}  mean Iest={iest.mean():+.3f}  mean trim={dw.mean():+.2f}  "
            f"AC RMS P={p_ac.std():.3f}  AC RMS I={i_ac.std():.3f}  "
            f"I/P (AC)={i_ac.std()/max(p_ac.std(), 1e-9):.1f}x"
        )

    for label, y in (("ASC", d["e_asc_arcsec"]), ("DEC", d["e_dec_arcsec"])):
        slow = moving_mean(y, dt, 180.0)
        res = y - slow
        mid = moving_mean(res, dt, 20.0)
        pe = moving_mean(res, dt, 25.0) - moving_mean(res, dt, 80.0)
        fast = res - moving_mean(res, dt, 20.0)
        print(
            f"  {label} arcsec RMS: raw={y.std():.1f}  "
            f">180s={(slow-slow.mean()).std():.1f}  "
            f"20-180s={mid.std():.1f}  "
            f"25-80s={pe.std():.1f}  "
            f"<20s={fast.std():.1f}"
        )

    fmin, fmax = 1.0 / 90.0, 1.0 / 25.0
    print("  sliding 5-min windows on 120s-highpassed data, peak in 25-90 s:")
    for label, y in (("ASC", d["e_asc_arcsec"]), ("DEC", d["e_dec_arcsec"]), ("dASC", d["dAsc"])):
        hp = y - moving_mean(y, dt, 120.0)
        peaks = window_peaks(t, hp, 300.0, fmin, fmax)
        ts = ", ".join(f"{p['T']:.1f}s@{p['t0']/60:.1f}min" for p in peaks)
        periods = [p["T"] for p in peaks if math.isfinite(p["T"])]
        amps = [p["amp"] for p in peaks]
        if periods:
            print(
                f"    {label:4s} T=[{ts}]  median={np.median(periods):.1f}s  "
                f"spread={np.std(periods):.1f}s  amp median={np.median(amps):.1f}"
            )

    m = (t >= 15 * 60) & (t <= 19 * 60)
    if m.sum() > 100:
        print("  late 15-19 min (after 120s highpass):")
        for label, y in (("ASC", d["e_asc_arcsec"]), ("DEC", d["e_dec_arcsec"])):
            hp = y - moving_mean(y, dt, 120.0)
            pk = band_fft(t[m], hp[m], 1 / 90.0, 1 / 25.0)
            print(
                f"    {label} peak T={pk['T']:.1f}s amp~{pk['amp']:.1f}  "
                f"RMS={hp[m].std():.1f} arcsec"
            )

    omega_cmd = ASC_SIDEREAL_UI_SPEED + d["dAsc"]
    t_mot = np.array([motor_period_s(w) for w in omega_cmd])
    print(
        f"  |w_asc| mean={np.abs(omega_cmd).mean():.2f} STEP/s  "
        f"200fs motor candidate T mean={np.nanmean(t_mot):.1f}s  "
        f"range {np.nanmin(t_mot):.1f}-{np.nanmax(t_mot):.1f}s"
    )
    print(
        "  worm candidates T=86164/N : "
        f"N=144 -> {86164/144:.0f}s  N=180 -> {86164/180:.0f}s  N=130 -> {86164/130:.0f}s"
    )
    print()


def plot_bands(ds: list[dict]) -> None:
    plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 160, "savefig.bbox": "tight"})
    fig, axes = plt.subplots(len(ds), 3, figsize=(14.5, 8.2), sharex=False)
    fig.suptitle(
        "Band split · slow PI hunt (>180 s) vs drivetrain band (15–120 s) vs fast (<15 s)",
        fontsize=12,
    )
    for row, d in enumerate(ds):
        tmin = d["t_rel"] / 60.0
        dt = d["dt"]
        for col, (key, title, color) in enumerate(
            [
                ("e_asc_arcsec", "ASC error", "#c0392b"),
                ("e_dec_arcsec", "DEC error", "#2980b9"),
            ]
        ):
            y = d[key]
            slow = moving_mean(y, dt, 180.0)
            res = y - slow
            mid = moving_mean(res, dt, 15.0)
            ax = axes[row, col]
            ax.plot(tmin, slow - np.mean(slow), color="0.25", lw=1.2, label=">180 s (hunt/drift)")
            ax.plot(tmin, mid, color=color, lw=0.8, label="15–180 s")
            ax.axhline(0, color="k", lw=0.4, alpha=0.4)
            ax.set_title(f"{d['name']}  {title}")
            ax.set_ylabel("arcsec")
            ax.legend(loc="upper right", fontsize=8)
            if row == len(ds) - 1:
                ax.set_xlabel("time (min)")

        # spectrum of high-passed ASC vs DEC (remove >180s)
        ax = axes[row, 2]
        for key, label, color in (
            ("e_asc_arcsec", "ASC err", "#c0392b"),
            ("e_dec_arcsec", "DEC err", "#2980b9"),
            ("dAsc", "dASC", "#e67e22"),
        ):
            y = d[key]
            hp = y - moving_mean(y, dt, 180.0)
            spec = band_fft(d["t_rel"], hp, 0.0, 2.0)
            xf, mag = spec["xf"], spec["spec"]
            n = len(hp)
            amp = 2.0 * mag / n
            m = (xf > 1 / 400.0) & (xf < 1 / 8.0)
            scale = 1.0 if key != "dAsc" else 20.0  # STEP/s vs arcsec overlay
            ax.plot(1.0 / xf[m], amp[m] * (scale if key == "dAsc" else 1.0), color=color, lw=1.1, label=label)
        ax.set_xscale("log")
        ax.set_xlim(10, 400)
        ax.axvspan(15, 120, color="0.85", zorder=0, label="PE search")
        ax.set_xlabel("period (s)")
        ax.set_ylabel("amp (arcsec; dASC×20)")
        ax.set_title(f"{d['name']}  residual spectrum")
        ax.legend(loc="upper right", fontsize=8)

    fig.tight_layout()
    fig.savefig(OUT / "band_split_pe.png")
    plt.close(fig)


def plot_asc_residual(ds: list[dict]) -> None:
    plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 160, "savefig.bbox": "tight"})
    fig, axes = plt.subplots(2, 1, figsize=(14, 7.2), sharex=False)
    fig.suptitle("ASC residual after removing 3-min trend — candidate gear PE", fontsize=12)
    for ax, d in zip(axes, ds):
        tmin = d["t_rel"] / 60.0
        dt = d["dt"]
        y = d["e_asc_arcsec"]
        res = y - moving_mean(y, dt, 180.0)
        ax.plot(tmin, res, color="#c0392b", lw=0.7, label="ASC residual")
        ax.plot(tmin, d["e_dec_arcsec"] - moving_mean(d["e_dec_arcsec"], dt, 180.0), color="#2980b9", lw=0.6, alpha=0.7, label="DEC residual")
        ax.axhline(0, color="k", lw=0.4, alpha=0.4)
        ax.set_ylabel("arcsec")
        ax.set_title(d["name"])
        ax.legend(loc="upper right")
        ax.set_xlabel("time (min)")
    fig.tight_layout()
    fig.savefig(OUT / "asc_residual_pe.png")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print_plant()
    ds = [load(p) for p in FILES]
    for d in ds:
        analyze_one(d)
    plot_bands(ds)
    plot_asc_residual(ds)
    print(f"wrote {OUT / 'band_split_pe.png'}")
    print(f"wrote {OUT / 'asc_residual_pe.png'}")


if __name__ == "__main__":
    main()
