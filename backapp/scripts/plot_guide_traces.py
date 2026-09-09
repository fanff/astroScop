"""Plot autoguide traces and extract hunting period / amplitude."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize

TRIM_MAX = 8.0
DEADBAND_PX = 0.5
KP = 0.80
KI = 0.008

HERE = Path(__file__).resolve().parent
SAVED = HERE.parent / "savedimgs"
OUT = SAVED / "guide_trace_plots"

FILES = [
    SAVED / "guide_trace_20260905T225553Z.csv",
    SAVED / "guide_trace_20260906T000032Z.csv",
]


def load(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    t = np.array([float(r["t"]) for r in rows], dtype=float)
    out = {
        "path": path,
        "name": path.stem.replace("guide_trace_", ""),
        "t": t,
        "t_rel": t - t[0],
        "t_iso0": rows[0]["t_iso"],
        "t_iso1": rows[-1]["t_iso"],
        "ok": np.array([int(r["ok"]) for r in rows], dtype=int),
        "e_asc_arcsec": np.array([float(r["e_asc_arcsec"]) for r in rows]),
        "e_dec_arcsec": np.array([float(r["e_dec_arcsec"]) for r in rows]),
        "e_asc_px": np.array([float(r["e_asc_px"]) for r in rows]),
        "e_dec_px": np.array([float(r["e_dec_px"]) for r in rows]),
        "dAsc": np.array([float(r["dAsc"]) for r in rows]),
        "dDec": np.array([float(r["dDec"]) for r in rows]),
        "snr": np.array([float(r["snr"]) for r in rows]),
        "n_gated": np.array([int(r["n_gated"]) for r in rows]),
        "bin": int(rows[0]["bin"]),
        "focal_mm": float(rows[0]["focal_mm"]),
        "dec_deg": float(rows[0]["dec_deg"]),
        "stack_n": int(rows[0]["stack_n"]),
    }
    dt = np.diff(out["t_rel"])
    out["dt_med"] = float(np.median(dt))
    out["hz"] = 1.0 / out["dt_med"]
    out["span_s"] = float(out["t_rel"][-1])
    out["r_arcsec"] = np.hypot(out["e_asc_arcsec"], out["e_dec_arcsec"])
    return out


def highpass(y: np.ndarray, dt: float, win_s: float = 180.0) -> np.ndarray:
    k = max(3, int(round(win_s / dt)))
    if k % 2 == 0:
        k += 1
    kernel = np.ones(k) / k
    slow = np.convolve(y, kernel, mode="same")
    return y - slow, slow


def osc_stats(t: np.ndarray, y: np.ndarray, win_s: float = 180.0) -> dict:
    dt = float(np.median(np.diff(t)))
    res, slow = highpass(y, dt, win_s)
    n = len(res)
    yf = np.fft.rfft(res - res.mean())
    xf = np.fft.rfftfreq(n, d=dt)
    mag = np.abs(yf)
    mag[0] = 0.0
    mask = xf > (1.0 / win_s)
    i = int(np.argmax(mag * mask))
    f = float(xf[i]) if mag[i] > 0 else 0.0
    z = res - res.mean()
    ac = np.correlate(z, z, mode="full")[n - 1 :]
    ac = ac / (ac[0] if ac[0] else 1.0)
    minlag = int(8.0 / dt)
    maxlag = int(min(240.0 / dt, n // 3))
    lag = minlag + int(np.argmax(ac[minlag:maxlag]))
    return {
        "res": res,
        "slow": slow,
        "fft_f": f,
        "fft_T": (1.0 / f) if f > 0 else float("nan"),
        "fft_xf": xf,
        "fft_mag": mag,
        "ac": ac,
        "ac_T": lag * dt,
        "rms": float(res.std()),
        "ptp": float(np.ptp(res)),
        "raw_rms": float(y.std()),
        "raw_ptp": float(np.ptp(y)),
        "raw_mean": float(y.mean()),
    }


def sat_frac(v: np.ndarray, lim: float = TRIM_MAX, eps: float = 0.01) -> float:
    return float(np.mean(np.abs(v) >= (lim - eps)))


def style():
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "#fafafa",
            "axes.grid": True,
            "grid.alpha": 0.35,
            "grid.linestyle": ":",
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "figure.dpi": 120,
            "savefig.dpi": 160,
            "savefig.bbox": "tight",
        }
    )


def plot_timeseries(d: dict, out_path: Path) -> None:
    tmin = d["t_rel"] / 60.0
    fig, axes = plt.subplots(5, 1, figsize=(14, 12.5), sharex=True)
    fig.suptitle(
        f"Autoguide trace {d['name']}\n"
        f"{d['t_iso0']} → {d['t_iso1']}  ·  {d['span_s']/60:.1f} min  ·  "
        f"{d['hz']:.2f} Hz  ·  f={d['focal_mm']:.0f} mm  bin={d['bin']}  "
        f"δ={d['dec_deg']:.0f}°  stack={d['stack_n']}  ·  "
        f"defaults Kp={KP} Ki={KI}",
        fontsize=12,
    )

    ax = axes[0]
    ax.plot(tmin, d["e_asc_arcsec"], color="#c0392b", lw=0.8, label="e_ASC")
    ax.plot(tmin, d["e_dec_arcsec"], color="#2980b9", lw=0.8, label="e_DEC")
    ax.axhline(0, color="k", lw=0.6, alpha=0.5)
    ax.set_ylabel("error (arcsec)")
    ax.legend(loc="upper right", ncol=2)
    ax.set_title("On-sky error")

    ax = axes[1]
    ax.plot(tmin, d["e_asc_px"], color="#c0392b", lw=0.8, label="e_ASC")
    ax.plot(tmin, d["e_dec_px"], color="#2980b9", lw=0.8, label="e_DEC")
    ax.axhline(DEADBAND_PX, color="0.4", ls="--", lw=0.8, label="deadband ±0.5 px")
    ax.axhline(-DEADBAND_PX, color="0.4", ls="--", lw=0.8)
    ax.axhline(0, color="k", lw=0.6, alpha=0.5)
    ax.set_ylabel("error (px)")
    ax.legend(loc="upper right", ncol=2)
    ax.set_title("Axis-pixel error (PI input)")

    ax = axes[2]
    ax.plot(tmin, d["dAsc"], color="#e67e22", lw=0.9, label="dASC")
    ax.plot(tmin, d["dDec"], color="#8e44ad", lw=0.9, label="dDEC")
    ax.axhline(TRIM_MAX, color="0.3", ls=":", lw=0.8)
    ax.axhline(-TRIM_MAX, color="0.3", ls=":", lw=0.8)
    ax.axhline(0, color="k", lw=0.6, alpha=0.5)
    ax.set_ylim(-TRIM_MAX - 0.4, TRIM_MAX + 0.4)
    ax.set_ylabel("trim (STEP/s)")
    sat_a = sat_frac(d["dAsc"]) * 100
    sat_d = sat_frac(d["dDec"]) * 100
    ax.set_title(f"PI output  ·  ASC sat {sat_a:.0f}%  DEC sat {sat_d:.0f}%")
    ax.legend(loc="upper right", ncol=2)

    ax = axes[3]
    ax.plot(tmin, d["r_arcsec"], color="#16a085", lw=0.8)
    ax.set_ylabel("radial (arcsec)")
    ax.set_title(
        f"Radial error  ·  RMS {d['r_arcsec'].std():.1f}\"  "
        f"mean {d['r_arcsec'].mean():.1f}\"  max {d['r_arcsec'].max():.1f}\""
    )

    ax = axes[4]
    ax.plot(tmin, d["snr"], color="#2c3e50", lw=0.8)
    ax.set_ylabel("SNR")
    ax.set_xlabel("time (min)")
    ax.set_title("Lock SNR")

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_xy(d: dict, out_path: Path) -> None:
    x = d["e_asc_arcsec"]
    y = d["e_dec_arcsec"]
    tmin = d["t_rel"] / 60.0
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.8))
    fig.suptitle(f"Sky-plane error path · {d['name']}", fontsize=12)

    ax = axes[0]
    pts = np.column_stack([x, y]).reshape(-1, 1, 2)
    segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
    lc = LineCollection(
        segs, cmap="viridis", norm=Normalize(tmin[0], tmin[-1]), linewidths=0.6, alpha=0.85
    )
    lc.set_array(tmin[:-1])
    ax.add_collection(lc)
    ax.plot(0, 0, "+", color="k", ms=10, mew=1.4)
    lim = max(np.percentile(np.abs(x), 99), np.percentile(np.abs(y), 99), 20)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("e_ASC (arcsec)")
    ax.set_ylabel("e_DEC (arcsec)")
    ax.set_title("path (color = time)")
    cb = fig.colorbar(lc, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("min")

    ax = axes[1]
    hb = ax.hexbin(x, y, gridsize=40, cmap="inferno", mincnt=1)
    ax.plot(0, 0, "+", color="w", ms=10, mew=1.4)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("e_ASC (arcsec)")
    ax.set_ylabel("e_DEC (arcsec)")
    ax.set_title("dwell density")
    fig.colorbar(hb, ax=ax, fraction=0.046, pad=0.04, label="samples")

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_oscillation(d: dict, out_path: Path) -> None:
    t = d["t_rel"]
    tmin = t / 60.0
    dt = d["dt_med"]
    fig, axes = plt.subplots(3, 2, figsize=(14, 10.5))
    fig.suptitle(
        f"Oscillation analysis · {d['name']}  ·  high-pass 180 s moving mean",
        fontsize=12,
    )

    for col, (key, label, color) in enumerate(
        [
            ("e_asc_arcsec", "ASC", "#c0392b"),
            ("e_dec_arcsec", "DEC", "#2980b9"),
        ]
    ):
        st = osc_stats(t, d[key])
        ax = axes[0, col]
        ax.plot(tmin, d[key], color=color, lw=0.6, alpha=0.55, label="raw")
        ax.plot(tmin, st["slow"], color="k", lw=1.0, label="slow (180 s)")
        ax.axhline(0, color="k", lw=0.5, alpha=0.4)
        ax.set_title(
            f"{label} error  mean={st['raw_mean']:.1f}\"  "
            f"RMS={st['raw_rms']:.1f}\"  ptp={st['raw_ptp']:.1f}\""
        )
        ax.set_ylabel("arcsec")
        ax.legend(loc="upper right")

        ax = axes[1, col]
        ax.plot(tmin, st["res"], color=color, lw=0.6)
        ax.axhline(0, color="k", lw=0.5, alpha=0.4)
        ax.set_title(
            f"{label} residual  RMS={st['rms']:.1f}\"  ptp={st['ptp']:.1f}\"  "
            f"FFT T={st['fft_T']:.1f}s  AC T={st['ac_T']:.1f}s"
        )
        ax.set_ylabel("arcsec")
        ax.set_xlabel("time (min)")

        ax = axes[2, col]
        xf, mag = st["fft_xf"], st["fft_mag"]
        # skip DC / very slow
        m = xf > 0.005
        ax.plot(xf[m], mag[m], color=color, lw=1.0)
        if st["fft_f"] > 0:
            ax.axvline(st["fft_f"], color="k", ls="--", lw=0.9, label=f"peak {st['fft_f']:.3f} Hz")
        ax.set_xlim(0, min(0.5, 1.0 / (4 * dt)))
        ax.set_xlabel("frequency (Hz)")
        ax.set_ylabel("|FFT|")
        ax.set_title(f"{label} residual spectrum")
        ax.legend(loc="upper right")

        print(
            f"{d['name']} {label}: FFT T={st['fft_T']:.2f}s ({st['fft_f']:.4f} Hz)  "
            f"AC T={st['ac_T']:.2f}s  residual RMS={st['rms']:.1f}\" ptp={st['ptp']:.1f}\"  "
            f"raw RMS={st['raw_rms']:.1f}\" mean={st['raw_mean']:.1f}\""
        )

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_zoom(d: dict, out_path: Path, start_min: float = 8.0, span_min: float = 4.0) -> None:
    tmin = d["t_rel"] / 60.0
    m = (tmin >= start_min) & (tmin <= start_min + span_min)
    if m.sum() < 50:
        m = tmin >= (tmin[-1] - span_min)
    fig, axes = plt.subplots(3, 1, figsize=(14, 8.5), sharex=True)
    fig.suptitle(
        f"Zoom {start_min:.0f}–{start_min + span_min:.0f} min · {d['name']}",
        fontsize=12,
    )
    ax = axes[0]
    ax.plot(tmin[m], d["e_asc_arcsec"][m], color="#c0392b", lw=1.1, label="e_ASC")
    ax.plot(tmin[m], d["e_dec_arcsec"][m], color="#2980b9", lw=1.1, label="e_DEC")
    ax.axhline(0, color="k", lw=0.6, alpha=0.5)
    ax.set_ylabel("error (arcsec)")
    ax.legend(loc="upper right", ncol=2)

    ax = axes[1]
    ax.plot(tmin[m], d["e_asc_px"][m], color="#c0392b", lw=1.1, label="e_ASC")
    ax.plot(tmin[m], d["e_dec_px"][m], color="#2980b9", lw=1.1, label="e_DEC")
    ax.axhspan(-DEADBAND_PX, DEADBAND_PX, color="0.7", alpha=0.25, label="deadband")
    ax.axhline(0, color="k", lw=0.6, alpha=0.5)
    ax.set_ylabel("error (px)")
    ax.legend(loc="upper right", ncol=2)

    ax = axes[2]
    ax.plot(tmin[m], d["dAsc"][m], color="#e67e22", lw=1.2, label="dASC")
    ax.plot(tmin[m], d["dDec"][m], color="#8e44ad", lw=1.2, label="dDEC")
    ax.axhline(TRIM_MAX, color="0.3", ls=":", lw=0.8)
    ax.axhline(-TRIM_MAX, color="0.3", ls=":", lw=0.8)
    ax.axhline(0, color="k", lw=0.6, alpha=0.5)
    ax.set_ylim(-TRIM_MAX - 0.4, TRIM_MAX + 0.4)
    ax.set_ylabel("trim (STEP/s)")
    ax.set_xlabel("time (min)")
    ax.legend(loc="upper right", ncol=2)

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_compare(ds: list[dict], out_path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 8.5), sharex=False)
    fig.suptitle("Both nights · error (arcsec) and PI trim", fontsize=12)
    for row, d in enumerate(ds):
        tmin = d["t_rel"] / 60.0
        ax = axes[row, 0]
        ax.plot(tmin, d["e_asc_arcsec"], color="#c0392b", lw=0.7, label="ASC")
        ax.plot(tmin, d["e_dec_arcsec"], color="#2980b9", lw=0.7, label="DEC")
        ax.axhline(0, color="k", lw=0.5, alpha=0.4)
        ax.set_ylabel("error (arcsec)")
        ax.set_title(f"{d['name']}  δ={d['dec_deg']:.0f}°")
        ax.legend(loc="upper right", ncol=2)

        ax = axes[row, 1]
        ax.plot(tmin, d["dAsc"], color="#e67e22", lw=0.8, label="dASC")
        ax.plot(tmin, d["dDec"], color="#8e44ad", lw=0.8, label="dDEC")
        ax.axhline(TRIM_MAX, color="0.3", ls=":", lw=0.7)
        ax.axhline(-TRIM_MAX, color="0.3", ls=":", lw=0.7)
        ax.set_ylim(-TRIM_MAX - 0.4, TRIM_MAX + 0.4)
        ax.set_ylabel("trim (STEP/s)")
        ax.set_title(d["name"])
        ax.legend(loc="upper right", ncol=2)
        ax.set_xlabel("time (min)")
        axes[row, 0].set_xlabel("time (min)")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def write_summary(ds: list[dict], out_path: Path) -> None:
    lines = [
        "# Guide-trace oscillation summary",
        "",
        f"Loop defaults: Kp={KP} (STEP/s per axis px), Ki={KI} (STEP/s per axis px per s).",
        "Plant: rate command, position error — I-term on an integrator.",
        "",
    ]
    for d in ds:
        lines.append(f"## {d['name']}")
        lines.append("")
        lines.append(
            f"- span {d['span_s']/60:.1f} min, {len(d['t'])} samples, "
            f"{d['hz']:.2f} Hz, f={d['focal_mm']:.0f} mm, bin={d['bin']}, "
            f"δ={d['dec_deg']:.0f}°, stack={d['stack_n']}"
        )
        lines.append(f"- window {d['t_iso0']} → {d['t_iso1']}")
        lines.append(
            f"- DEC trim saturated {sat_frac(d['dDec'])*100:.1f}% of samples; "
            f"ASC trim saturated {sat_frac(d['dAsc'])*100:.1f}%"
        )
        for key, label in [("e_asc_arcsec", "ASC"), ("e_dec_arcsec", "DEC")]:
            st = osc_stats(d["t_rel"], d[key])
            lines.append(
                f"- {label}: mean {st['raw_mean']:.1f}\"  RMS {st['raw_rms']:.1f}\"  "
                f"ptp {st['raw_ptp']:.1f}\"  residual RMS {st['rms']:.1f}\"  "
                f"FFT period {st['fft_T']:.1f}s  autocorr period {st['ac_T']:.1f}s"
            )
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    style()
    OUT.mkdir(parents=True, exist_ok=True)
    ds = [load(p) for p in FILES]
    plot_compare(ds, OUT / "compare_both.png")
    write_summary(ds, OUT / "summary.md")
    for d in ds:
        plot_timeseries(d, OUT / f"{d['name']}_timeseries.png")
        plot_xy(d, OUT / f"{d['name']}_xy.png")
        plot_oscillation(d, OUT / f"{d['name']}_oscillation.png")
        plot_zoom(d, OUT / f"{d['name']}_zoom.png", start_min=8.0, span_min=4.0)
        plot_zoom(d, OUT / f"{d['name']}_zoom_late.png", start_min=15.0, span_min=4.0)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
