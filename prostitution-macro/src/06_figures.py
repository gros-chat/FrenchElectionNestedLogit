#!/usr/bin/env python3
"""Figures for the article.  Writes 300-dpi PNGs to out/fig/."""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(HERE, *p)
os.makedirs(D("out", "fig"), exist_ok=True)

R = json.load(open(D("out", "results.json")))
A = json.load(open(D("out", "arithmetic.json")))

BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#8c8c8c"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.edgecolor": "#444444", "axes.linewidth": 0.6,
    "axes.grid": True, "grid.color": "#dddddd", "grid.linewidth": 0.5,
    "xtick.color": "#444444", "ytick.color": "#444444",
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
})


# ---------------------------------------------------------------- Figure 1
def fig1():
    noise = A["noise"]["gdppc_con"]["sd_advanced"] * 100
    cases = A["cases"]
    names = [c["jurisdiction"] for c in cases]
    sig = [abs(c["channels"]["phi50"]["dln_gdp_pct"]) for c in cases]
    order = np.argsort(sig)
    names = [names[i] for i in order]
    sig = [sig[i] for i in order]
    y = np.arange(len(names))

    fig, ax = plt.subplots(figsize=(6.3, 2.6))
    for i, s in enumerate(sig):
        ax.plot([s, noise], [i, i], color="#cccccc", lw=2.0, zorder=1,
                solid_capstyle="round")
    ax.scatter(sig, y, s=34, color=BLUE, zorder=3, label="Mechanical effect on GDP of suppressing half the sector")
    ax.scatter([noise] * len(y), y, s=34, color=ORANGE, zorder=3, marker="s",
               label="One-year idiosyncratic surprise in real GDP p.c. (s.d.)")
    for i, s in enumerate(sig):
        ax.annotate(f"{noise/s:,.0f}×", (noise, i), xytext=(9, 0),
                    textcoords="offset points", va="center", fontsize=8,
                    color="#444444")
    ax.set_xscale("log")
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=8.5)
    ax.set_xlabel("per cent of GDP (log scale)", fontsize=8.5)
    ax.set_xlim(min(sig) * 0.6, noise * 2.2)
    ticks = [t for t in (0.05, 0.1, 0.2, 0.5, 1, 2, 3)
             if min(sig) * 0.6 <= t <= noise * 2.2]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:g}%" for t in ticks], fontsize=8)
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), frameon=False,
              fontsize=8, ncol=1, handletextpad=0.4, borderaxespad=0)
    fig.savefig(D("out", "fig", "fig1_signal_noise.png"))
    plt.close(fig)


# ---------------------------------------------------------------- Figure 2
def panel_event(ax, key, title):
    es = R["event_study"].get(key, {})
    cs = R["cs"].get(key, {}).get("by_k", {})
    ks = sorted(int(k[1:]) for k in es if not k.startswith("_"))
    b = np.array([es[f"k{k:+d}"][0] for k in ks]) * 100
    se = np.array([es[f"k{k:+d}"][1] for k in ks]) * 100
    ax.axhline(0, color="#666666", lw=0.8)
    ax.axvline(-0.5, color=GREY, lw=0.9, ls="--")
    ax.errorbar(ks, b, yerr=1.96 * se, fmt="o", ms=4, color=BLUE, lw=1.3,
                capsize=2.4, label="Two-way FE event study, 95% CI", zorder=3)
    ck = sorted((int(k), v * 100) for k, v in cs.items()
                if v is not None and ks[0] <= int(k) <= ks[-1])
    if ck:
        ax.plot([k for k, _ in ck], [v for _, v in ck], color=ORANGE, lw=1.3,
                ls=(0, (4, 2)), marker="s", ms=3.4,
                label="Callaway–Sant'Anna (not-yet-treated)", zorder=4)
    ax.set_title(title, fontsize=9, pad=6)
    ax.set_xlabel("years from reform", fontsize=8.5)
    ax.set_ylabel("per cent", fontsize=8.5)
    ax.tick_params(labelsize=8)


def fig2():
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.7))
    panel_event(axes[0], "ban|ln_rgdp_pc|all", "(a) Real GDP per capita")
    panel_event(axes[1], "ban|ln_velocity|all", "(b) Velocity of broad money")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, -0.17),
               frameon=False, ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(D("out", "fig", "fig2_event_study.png"))
    plt.close(fig)


# ---------------------------------------------------------------- Figure 3
def panel_scm(ax, key, title):
    r = R["scm"].get(key)
    if not r:
        ax.set_visible(False); return
    ys = r["years"]
    ax.plot(ys, r["actual"], color=BLUE, lw=1.6, label="Actual")
    ax.plot(ys, r["synthetic"], color=ORANGE, lw=1.4, ls=(0, (4, 2)),
            label="Synthetic control")
    ax.axvline(r["t0"] - 0.5, color=GREY, lw=0.9, ls="--")
    ax.annotate(str(r["t0"]), (r["t0"] - 0.5, ax.get_ylim()[1]),
                xytext=(3, -10), textcoords="offset points", fontsize=7.5,
                color="#444444")
    ax.set_title(title, fontsize=9, pad=6)
    ax.set_xlabel("year", fontsize=8.5)
    ax.set_xticks([y for y in ys if y % 4 == 0])
    ax.set_xticklabels([str(y) for y in ys if y % 4 == 0])
    ax.tick_params(labelsize=8)


def fig3():
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.7))
    panel_scm(axes[0], "KOR|2004|ln_rgdp_pc", "(a) Korea: log real GDP per capita")
    panel_scm(axes[1], "KOR|2004|ln_velocity", "(b) Korea: log velocity of broad money")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, -0.14),
               frameon=False, ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(D("out", "fig", "fig3_scm_korea.png"))
    plt.close(fig)


if __name__ == "__main__":
    fig1(); fig2(); fig3()
    for f in sorted(os.listdir(D("out", "fig"))):
        print("wrote out/fig/" + f)
