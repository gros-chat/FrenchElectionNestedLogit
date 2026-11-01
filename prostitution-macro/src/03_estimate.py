#!/usr/bin/env python3
"""Effect of prostitution bans and liberalisations ("reinstatement") on GDP,
money velocity and multiplier proxies.

Estimators
  1. Two-way fixed effects event study (linearmodels.PanelOLS, clustered by country)
  2. Callaway-Sant'Anna (2021) group-time ATT with a not-yet-treated comparison,
     aggregated over event time
  3. Randomization inference: event dates reassigned to never-treated countries,
     B draws, exact two-sided p-value.  With 3-9 treated clusters this, not the
     cluster-robust t, is the inference we rely on.
  4. Synthetic control for the focus jurisdictions, with in-space placebo p-values
  5. Minimum detectable effect vs the arithmetic size of the sector, and the
     output multiplier implied by the point estimate

Writes out/results.json
"""
import json, os, warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize

warnings.filterwarnings("ignore")
rng = np.random.default_rng(20261101)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(HERE, *p)

# ---------------------------------------------------------------- data
panel = pd.read_csv(D("data", "panel.csv"))
regimes = pd.read_csv(D("data", "regimes.csv"))
sector = pd.read_csv(D("data", "sector_measurement.csv"))

NAT = regimes[regimes.level == "national"].copy()

OUTCOMES = {
    "ln_rgdp_pc":  ("gdppc_con",   "log real GDP per capita (constant LCU)"),
    "ln_velocity": ("velocity",    "log velocity of broad money (nominal GDP / M2)"),
    "ln_mult_credit": ("mult_credit", "log credit multiplier (private credit / broad money)"),
    "ln_mult_liq": ("mult_liq",    "log bank liquidity multiplier (assets / liquid reserves)"),
}
# Rate outcomes.  MV = PY is an identity: if a ban moves velocity while the
# central bank holds M, the adjustment has to turn up in P or in Y.  Testing
# inflation and money growth closes the identity instead of leaving the
# velocity result hanging.  Stored as fractions so they print as percentage
# points on the same formatting path as the log outcomes.
RATE_OUTCOMES = {"infl_rate": ("infl", "CPI inflation (annual, pp)"),
                 "m2_growth_rate": ("m2_growth", "Broad money growth (annual, pp)")}

d = panel.copy()
for name, (src, _) in OUTCOMES.items():
    v = pd.to_numeric(d[src], errors="coerce")
    d[name] = np.log(v.where(v > 0))
for name, (src, _) in RATE_OUTCOMES.items():
    d[name] = pd.to_numeric(d[src], errors="coerce") / 100.0
OUTCOMES.update(RATE_OUTCOMES)

# Outlier guard: drop country-years whose outcome jumps implausibly (data
# breaks, redenominations, hyperinflation).  Documented, symmetric, applied
# identically to treated and control units.
for name in OUTCOMES:
    g = d.sort_values("year").groupby("iso3")[name]
    jump = (g.diff().abs() > 0.60)
    d.loc[jump.fillna(False), name] = np.nan

ADVANCED = set("""AUS AUT BEL CAN CHE CYP CZE DEU DNK ESP EST FIN FRA GBR GRC
HRV HUN IRL ISL ISR ITA JPN KOR LTU LUX LVA MLT NLD NOR NZL POL PRT SVK SVN
SWE USA""".split())

# ------------------------------------------------- treatment definition
def arms(direction):
    """first event of the given sign per country, and the year at which the
    post window must be censored because an opposite-sign event arrives."""
    out = {}
    for iso, grp in NAT.groupby("iso3"):
        same = sorted(grp.loc[grp.direction == direction, "event_year"])
        opp = sorted(grp.loc[grp.direction == -direction, "event_year"])
        if not same:
            continue
        t0 = same[0]
        later_opp = [y for y in opp if y > t0]
        out[iso] = (t0, later_opp[0] if later_opp else None)
    return out

BANS, LIBS = arms(-1), arms(+1)
TREATED_ANY = set(NAT.iso3)
NEVER = sorted(set(d.iso3) - TREATED_ANY)

KMIN, KMAX = -6, 6

def build(outcome, events, sample=None, min_obs=15):
    """panel with event time k, censored after an opposite reform."""
    x = d[["iso3", "year", outcome]].dropna().copy()
    if sample is not None:
        x = x[x.iso3.isin(sample)]
    keep = x.groupby("iso3")[outcome].transform("size") >= min_obs
    x = x[keep]
    x["t0"] = x.iso3.map({k: v[0] for k, v in events.items()})
    cens = pd.to_numeric(x.iso3.map({k: v[1] for k, v in events.items()}),
                         errors="coerce")
    x = x[cens.isna() | (x.year < cens)]
    x["k"] = x.year - x.t0
    x["treated"] = x.t0.notna().astype(int)
    return x

def event_study(x, outcome):
    """TWFE event study; returns dict k -> (beta, se) with k=-1 omitted."""
    from linearmodels.panel import PanelOLS
    z = x.copy()
    kk = z.k.where(z.treated == 1)
    kb = kk.clip(KMIN, KMAX)
    cols = {}
    for k in range(KMIN, KMAX + 1):
        if k == -1:
            continue
        cols[f"k{k:+d}"] = (kb == k).astype(float)
    Z = pd.DataFrame(cols, index=z.index)
    Z = Z.loc[:, Z.sum() > 0]
    if Z.shape[1] == 0:
        return {}
    df = pd.concat([z[["iso3", "year", outcome]], Z], axis=1)
    df = df.set_index(["iso3", "year"])
    y = df[outcome]
    X = df[Z.columns]
    try:
        res = PanelOLS(y, X, entity_effects=True, time_effects=True,
                       drop_absorbed=True).fit(cov_type="clustered",
                                               cluster_entity=True)
    except Exception as e:
        return {"error": str(e)}
    o = {}
    for c in Z.columns:
        if c in res.params.index:
            o[c] = [float(res.params[c]), float(res.std_errors[c])]
    o["_nobs"] = int(res.nobs)
    o["_nclust"] = int(df.index.get_level_values(0).nunique())
    return o

# ------------------------------- Callaway-Sant'Anna, not-yet-treated
def to_matrix(x, outcome):
    """-> (Y[n_units, n_years], units, years, t0 vector aligned to units)"""
    units = np.array(sorted(x.iso3.unique()))
    years = np.arange(int(x.year.min()), int(x.year.max()) + 1)
    ui = {u: i for i, u in enumerate(units)}
    yi = {y: i for i, y in enumerate(years)}
    Y = np.full((len(units), len(years)), np.nan)
    Y[x.iso3.map(ui).values, x.year.map(yi).values] = x[outcome].values
    t0 = np.full(len(units), np.nan)
    for u, v in x.groupby("iso3").t0.first().items():
        if np.isfinite(v):
            t0[ui[u]] = v
    return Y, units, years, t0


def cs_att_np(Y, years, t0, kmin=-5, kmax=5, min_ctrl=5):
    """Callaway-Sant'Anna group-time ATT against not-yet-treated, aggregated
    by event time.  Fully vectorised over units."""
    y0 = years[0]
    nY = Y.shape[1]
    groups = np.unique(t0[np.isfinite(t0)]).astype(int)
    out = {}
    for k in range(kmin, kmax + 1):
        num = den = 0.0
        for g in groups:
            tt, base = g + k, g - 1
            it, ib = tt - y0, base - y0
            if not (0 <= it < nY and 0 <= ib < nY):
                continue
            ok = np.isfinite(Y[:, it]) & np.isfinite(Y[:, ib])
            dif = Y[:, it] - Y[:, ib]
            tr = ok & (t0 == g)
            if not tr.any():
                continue
            cutoff = max(tt, g)
            ctl = ok & (~np.isfinite(t0) | (t0 > cutoff)) & (t0 != g)
            if ctl.sum() < min_ctrl:
                continue
            num += tr.sum() * (dif[tr].mean() - dif[ctl].mean())
            den += tr.sum()
        out[k] = num / den if den else np.nan
    post = [out[k] for k in range(0, kmax + 1) if np.isfinite(out.get(k, np.nan))]
    pre = [out[k] for k in range(kmin, -1) if np.isfinite(out.get(k, np.nan))]
    return dict(by_k={str(k): (None if not np.isfinite(v) else float(v))
                      for k, v in out.items()},
                att_post=float(np.mean(post)) if post else None,
                pretrend_max=float(np.max(np.abs(pre))) if pre else None,
                pretrend_mean=float(np.mean(np.abs(pre))) if pre else None)


def cs_att(x, outcome, kmin=-5, kmax=5):
    Y, units, years, t0 = to_matrix(x, outcome)
    return cs_att_np(Y, years, t0, kmin, kmax)


def ri_pvalue(x, outcome, events, B=2000, kmax=5):
    """Randomization inference: hand the observed multiset of event years to
    randomly chosen never-treated countries, recompute the aggregate post ATT.
    With 3-9 treated clusters this is the inference we report."""
    Y, units, years, t0 = to_matrix(x, outcome)
    obs = cs_att_np(Y, years, t0, kmax=kmax)["att_post"]
    if obs is None:
        return dict(att_post=None, p_two_sided=None, B=0)
    yrs = [int(events[u][0]) for u in units if u in events]
    pool = np.array([i for i, u in enumerate(units) if u not in TREATED_ANY])
    if len(pool) < len(yrs) + 5 or not yrs:
        return dict(att_post=float(obs), p_two_sided=None, B=0)
    # placebo panel: donors only, so no real reform contaminates the null
    Yp = Y[pool, :]
    draws = []
    for _ in range(B):
        pick = rng.choice(len(pool), size=len(yrs), replace=False)
        tp = np.full(len(pool), np.nan)
        tp[pick] = yrs
        v = cs_att_np(Yp, years, tp, kmax=kmax)["att_post"]
        if v is not None and np.isfinite(v):
            draws.append(v)
    draws = np.array(draws)
    if draws.size < 50:
        return dict(att_post=float(obs), p_two_sided=None, B=int(draws.size))
    return dict(att_post=float(obs),
                p_two_sided=float((np.abs(draws) >= abs(obs)).mean()),
                B=int(draws.size), placebo_sd=float(draws.std()),
                placebo_q=[float(np.quantile(draws, q)) for q in (.025, .5, .975)])


# ------------------------------------------------------ synthetic control
MAX_DONORS = 35   # cap; rarely binds once the pool is curated


def scm(outcome, unit, t0, pre_len=12, post_len=6, donors=None):
    x = d[["iso3", "year", outcome]].dropna()
    y0, y1 = t0 - pre_len, t0 + post_len - 1
    x = x[(x.year >= y0) & (x.year <= y1)]
    w = x.pivot_table(index="year", columns="iso3", values=outcome)
    need = list(range(y0, y1 + 1))
    w = w.reindex(need)
    w = w.loc[:, w.notna().all()]
    if unit not in w.columns:
        return None
    pool = donors if donors is not None else [c for c in w.columns
                                              if c not in TREATED_ANY]
    pool = [c for c in pool if c in w.columns and c != unit]
    if len(pool) < 8:
        return None
    pre = [t for t in need if t < t0]
    post = [t for t in need if t >= t0]
    # Keep the MAX_DONORS donors whose pre-reform growth path tracks the treated
    # unit most closely.  Restricting the donor pool this way is standard and
    # makes the in-space placebo loop tractable; the weights themselves still
    # come from the constrained fit below.
    if len(pool) > MAX_DONORS:
        tg = np.diff(w.loc[pre, unit].values)
        sc = {}
        for c in pool:
            cg = np.diff(w.loc[pre, c].values)
            sc[c] = -abs(np.corrcoef(tg, cg)[0, 1]) if cg.std() > 1e-12 else 1.0
        pool = sorted(pool, key=lambda c: sc[c])[:MAX_DONORS]

    def fit(target, dpool):
        Y = w.loc[pre, target].values
        X = w.loc[pre, dpool].values
        # demean so the fit is on the shape of the path, not its level
        mu = Y.mean()
        Yc, Xc = Y - mu, X - X.mean(axis=0)
        n = len(dpool)
        def obj(ww):
            return float(np.mean((Yc - Xc @ ww) ** 2))
        cons = ({"type": "eq", "fun": lambda ww: ww.sum() - 1.0},)
        r = minimize(obj, np.full(n, 1.0 / n), method="SLSQP", bounds=[(0, 1)] * n,
                     constraints=cons, options=dict(maxiter=200, ftol=1e-10))
        ww = np.clip(r.x, 0, None); ww = ww / ww.sum()
        shift = Y.mean() - (X @ ww).mean()
        path = w.loc[need, dpool].values @ ww + shift
        gap = w.loc[need, target].values - path
        pre_r = float(np.sqrt(np.mean(gap[:len(pre)] ** 2)))
        post_r = float(np.sqrt(np.mean(gap[len(pre):] ** 2)))
        return ww, path, gap, pre_r, post_r

    ww, path, gap, pre_r, post_r = fit(unit, pool)
    ratio = post_r / pre_r if pre_r > 0 else np.nan
    # in-space placebos
    pl = []
    for c in pool:
        others = [k for k in pool if k != c]
        try:
            _, _, g2, a, b = fit(c, others)
            if a > 0:
                pl.append(b / a)
        except Exception:
            pass
    p = float((np.array(pl) >= ratio).mean()) if pl else None
    wts = sorted(((c, float(v)) for c, v in zip(pool, ww) if v > 0.01),
                 key=lambda t: -t[1])
    return dict(unit=unit, t0=int(t0), outcome=outcome,
                years=[int(t) for t in need],
                actual=[float(v) for v in w.loc[need, unit].values],
                synthetic=[float(v) for v in path],
                gap=[float(v) for v in gap],
                pre_rmspe=pre_r, post_rmspe=post_r, ratio=float(ratio),
                placebo_p=p, n_placebo=len(pl),
                post_mean_gap=float(np.mean(gap[len(pre):])),
                weights=wts[:10], n_donors=len(pool))

# Donor pool for every synthetic control.  Choosing donors by growth-path
# correlation across all 214 countries produced economically meaningless
# controls - Laos came out as the synthetic South Korea - so the pool is
# restricted up front on economic similarity: a donor must never have reformed
# and must sit within a factor of three of the treated unit's own pre-reform
# income per head.  A fixed list of advanced economies was the obvious
# alternative but leaves too few own-currency donors once the euro area drops
# out, so the band is relative to the treated unit instead.
PC_USD = {}
for _r in panel.itertuples():
    gu, gc, pc = (getattr(_r, "gdp_usd", None), getattr(_r, "gdp_con", None),
                  getattr(_r, "gdppc_con", None))
    if (gu and gc and pc and np.isfinite(gu) and np.isfinite(gc)
            and np.isfinite(pc) and pc > 0):
        pop = gc / pc
        if pop > 0:
            PC_USD[(_r.iso3, int(_r.year))] = gu / pop

ALL_ISO = sorted(set(panel["iso3"]))


def scm_donors(unit, t0, pre_len=12, band=3.0):
    yrs = [y for y in range(t0 - pre_len, t0) if y >= 1960]

    def inc(c):
        v = [PC_USD[(c, y)] for y in yrs if (c, y) in PC_USD]
        return float(np.mean(v)) if v else None

    base = inc(unit)
    if base is None:
        return sorted(ADVANCED - TREATED_ANY)
    out = [c for c in ALL_ISO
           if c not in TREATED_ANY and c != unit
           and (lambda v: v is not None and base / band <= v <= base * band)(inc(c))]
    return out if len(out) >= 8 else sorted(set(out) | (ADVANCED - TREATED_ANY))

# ============================================================ run
results = {"meta": {}, "event_study": {}, "cs": {}, "ri": {}, "scm": {},
           "power": {}, "samples": {}}

results["meta"]["n_countries"] = int(d.iso3.nunique())
results["meta"]["years"] = [int(d.year.min()), int(d.year.max())]
results["meta"]["n_national_events"] = int(len(NAT))

for arm_name, events in (("ban", BANS), ("lib", LIBS)):
    for oname, (src, label) in OUTCOMES.items():
        for samp_name, samp in (("all", None), ("advanced", ADVANCED)):
            x = build(oname, events, sample=samp)
            tr = sorted(set(x.loc[x.treated == 1, "iso3"]))
            key = f"{arm_name}|{oname}|{samp_name}"
            if len(tr) == 0:
                continue
            results["samples"][key] = dict(
                treated=tr, n_treated=len(tr),
                n_control=int(x.loc[x.treated == 0, "iso3"].nunique()),
                nobs=int(len(x)))
            results["event_study"][key] = event_study(x, oname)
            results["cs"][key] = cs_att(x, oname)
            if samp_name == "all":
                results["ri"][key] = ri_pvalue(x, oname, events,
                                               B=2000)
            print(f"{key:48s} nT={len(tr)} "
                  f"ATTpost={results['cs'][key]['att_post']}", flush=True)

with open(D("out", "results.json"), "w") as f:
    json.dump(results, f, indent=1)
print("checkpoint: panel estimates written", flush=True)

# focus jurisdictions
for unit, t0, outs, pre in (("GBR", 2010, ["ln_rgdp_pc", "ln_velocity", "ln_mult_credit"], 12),
                            ("KOR", 2004, ["ln_rgdp_pc", "ln_velocity", "ln_mult_credit"], 12),
                            ("SWE", 1999, ["ln_rgdp_pc", "ln_velocity", "ln_mult_credit"], 12),
                            ("DNK", 1999, ["ln_rgdp_pc", "ln_velocity", "ln_mult_credit"], 12),
                            ("NZL", 2003, ["ln_rgdp_pc", "ln_velocity"], 12),
                            ("NOR", 2009, ["ln_rgdp_pc", "ln_velocity"], 12)):
    for o in outs:
        r = scm(o, unit, t0, pre_len=pre, post_len=6,
                donors=scm_donors(unit, t0, pre))
        if r:
            results["scm"][f"{unit}|{t0}|{o}"] = r
            print(f"SCM {unit} {t0} {o:16s} gap={r['post_mean_gap']:+.4f} "
                  f"ratio={r['ratio']:.2f} p={r['placebo_p']}", flush=True)
            with open(D("out", "results.json"), "w") as fh:
                json.dump(results, fh, indent=1)

# ---- SCM robustness: fewer donors, longer pre-period ------------------
# With 35 donors on 12 pre-periods the simplex interpolates the pre-path almost
# exactly (pre-RMSPE near zero), which inflates the post/pre ratio and makes the
# placebo rank meaningless.  Re-run with 12 donors and 20 pre-periods so the fit
# is identified: 20 targets, 12 free weights on a simplex.
globals()["MAX_DONORS"] = 12
results["scm_robust"] = {}
for unit, t0, outs in (("GBR", 2010, ["ln_rgdp_pc", "ln_velocity", "ln_mult_credit"]),
                       ("KOR", 2004, ["ln_rgdp_pc", "ln_velocity", "ln_mult_credit"]),
                       ("SWE", 1999, ["ln_rgdp_pc", "ln_velocity"]),
                       ("DNK", 1999, ["ln_rgdp_pc", "ln_velocity"]),
                       ("NZL", 2003, ["ln_rgdp_pc", "ln_velocity"]),
                       ("NOR", 2009, ["ln_rgdp_pc", "ln_velocity"])):
    for o in outs:
        r = scm(o, unit, t0, pre_len=20, post_len=6,
                    donors=scm_donors(unit, t0, 20))
        if r:
            results["scm_robust"][f"{unit}|{t0}|{o}"] = r
            print(f"ROBUST {unit} {t0} {o:16s} gap={r['post_mean_gap']:+.4f} "
                  f"pre={r['pre_rmspe']:.5f} ratio={r['ratio']:.2f} "
                  f"p={r['placebo_p']} donors={r['n_donors']}", flush=True)

# --------------------------------------------- power / arithmetic bound
sec = sector.set_index("iso3")["sector_share_gdp_pct"].to_dict()
pw = {}
for key, es in results["event_study"].items():
    if not es or "error" in es:
        continue
    ses = [v[1] for k, v in es.items() if not k.startswith("_")]
    if not ses:
        continue
    se = float(np.median(ses))
    pw[key] = dict(median_se=se, mde_80pct=2.80 * se,
                   n_treated=results["samples"][key]["n_treated"])
results["power"] = pw

mech = {}
for iso, share in sec.items():
    for phi in (0.25, 0.50, 1.00):
        mech[f"{iso}|phi{int(phi*100)}"] = phi * share / 100.0
results["mechanical"] = dict(shares=sec, effects=mech)

with open(D("out", "results.json"), "w") as f:
    json.dump(results, f, indent=1)
print("\nwrote out/results.json")
