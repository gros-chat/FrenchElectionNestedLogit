#!/usr/bin/env python3
"""How large an effect *could* a prostitution ban have on GDP, velocity and the
money multiplier, if the behavioural response were as large as anyone claims?

This is the identification-free part of the exercise and it has to come first,
because it sets the scale that the regressions then have to beat.

Channels
  (1) Measurement / output.  A ban suppresses a fraction phi of a sector worth
      s per cent of GDP, or pushes it out of the measured accounts.
          dlnY = -phi * s
  (2) Velocity.  V = PY / M.  Monetary policy sets M, so to a first order
          dlnV = dlnY = -phi * s
      A second-order term appears only if the ban also changes money demand.
  (3) Money multiplier.  m = (1 + c) / (r + c), with c = currency/deposits and
      r = reserves/deposits, M2 = C + D, MB = C + R.
          dm/dc = (r - 1) / (r + c)^2  < 0
      A ban drives the trade into cash.  If the suppressed turnover is phi*T and
      a unit of currency is re-spent n times a year, the extra currency held is
      phi*T/n, so dc = (phi*T/n)/D.  r is taken from the data (WDI bank liquid
      reserves to bank assets); c is parameterised.

Writes out/arithmetic.json
"""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(HERE, *p)

panel = pd.read_csv(D("data", "panel.csv"))
sector = pd.read_csv(D("data", "sector_measurement.csv"))
regimes = pd.read_csv(D("data", "regimes.csv"))

# cases: jurisdiction, iso3, event year, sector share of GDP (%)
CASES = [("United Kingdom", "GBR", 2010, 0.37),
         ("Sweden",         "SWE", 1999, 0.10),
         ("South Korea",    "KOR", 2004, 4.10),
         ("Norway",         "NOR", 2009, 0.10),
         ("Denmark",        "DNK", 1999, 0.10),
         ("New Zealand",    "NZL", 2003, 0.20)]

PHIS = [0.25, 0.50, 1.00]          # fraction of the sector suppressed
NTURN = [10, 20, 52]               # times a currency unit is re-spent per year
C_RATIO = [0.05, 0.10]             # currency / deposits

out = {"cases": [], "params": dict(phi=PHIS, n_turnover=NTURN, c_ratio=C_RATIO)}

for name, iso, t0, s in CASES:
    row = panel[(panel.iso3 == iso) & (panel.year == t0)]
    if row.empty:
        continue
    row = row.iloc[0]
    m2_gdp = float(row.m2_gdp) if np.isfinite(row.m2_gdp) else np.nan
    vel = float(row.velocity) if np.isfinite(row.velocity) else np.nan
    # r from the data where available, else the sample median at that date
    ADV = set("""AUS AUT BEL CAN CHE CZE DEU DNK ESP EST FIN FRA GBR GRC HUN
IRL ISL ISR ITA JPN KOR LTU LUX LVA NLD NOR NZL POL PRT SVK SVN SWE USA""".split())
    rr = row.res_ratio
    if not np.isfinite(rr):
        # advanced-economy median, not the all-country median: the global median
        # is dominated by banking systems nothing like the UK's
        rr = panel.loc[(panel.year == t0) & (panel.iso3.isin(ADV)),
                       "res_ratio"].median()
    r = float(rr) / 100.0 if np.isfinite(rr) else 0.03

    rec = dict(jurisdiction=name, iso3=iso, event_year=t0,
               sector_pct_gdp=s, m2_pct_gdp=m2_gdp, velocity=vel,
               reserve_ratio=r, channels={})

    for phi in PHIS:
        dlnY = -phi * s / 100.0          # output / measurement channel
        dlnV = dlnY                      # first-order velocity channel
        mult = {}
        for c in C_RATIO:
            m0 = (1 + c) / (r + c)
            for n in NTURN:
                # turnover T approximated by the sector's gross output; for a
                # near-pure-labour service, output ~ value added ~ s% of GDP.
                # D = deposits = M2 - C = M2/(1+c)
                if not np.isfinite(m2_gdp) or m2_gdp <= 0:
                    continue
                D_pct_gdp = m2_gdp / (1 + c)
                dc = (phi * s / n) / D_pct_gdp
                dm = (r - 1) / (r + c) ** 2 * dc
                mult[f"c{c}|n{n}"] = dict(m0=m0, dc=dc, dm=dm,
                                          dln_m=dm / m0)
        rec["channels"][f"phi{int(phi*100)}"] = dict(
            dln_gdp=dlnY, dln_gdp_pct=100 * dlnY,
            dln_velocity=dlnV, dln_velocity_pct=100 * dlnV,
            multiplier=mult)
    out["cases"].append(rec)

# ---- noise benchmark: how big is a one-year surprise in each outcome? -----
bench = {}
for col, lab in (("gdppc_con", "ln real GDP per capita"),
                 ("velocity", "ln velocity"),
                 ("mult_credit", "ln credit multiplier")):
    v = pd.to_numeric(panel[col], errors="coerce")
    lv = np.log(v.where(v > 0))
    df = panel[["iso3", "year"]].copy(); df["y"] = lv
    df = df.dropna().sort_values(["iso3", "year"])
    df["d"] = df.groupby("iso3").y.diff()
    df = df[df.d.abs() < 0.6]
    # residual after removing a common year effect = idiosyncratic surprise
    df["dm"] = df.d - df.groupby("year").d.transform("mean")
    adv = set("""AUS AUT BEL CAN CHE DEU DNK ESP FIN FRA GBR GRC HUN IRL ISL
ISR ITA JPN KOR NLD NOR NZL POL PRT SWE USA""".split())
    sub = df[df.iso3.isin(adv)]
    bench[col] = dict(label=lab,
                      sd_all=float(df.dm.std()),
                      sd_advanced=float(sub.dm.std()),
                      n_all=int(len(df)), n_advanced=int(len(sub)))
out["noise"] = bench

with open(D("out", "arithmetic.json"), "w") as f:
    json.dump(out, f, indent=1)

print("Idiosyncratic one-year surprise (sd of year-demeaned log change):")
for k, v in bench.items():
    print(f"  {v['label']:26s} all {v['sd_all']*100:6.2f}%   "
          f"advanced {v['sd_advanced']*100:6.2f}%")
print()
print(f"{'case':16s}{'s %GDP':>8}{'M2/GDP':>8}{'V':>7}{'r':>7}"
      f"{'dlnY|phi=.5':>12}{'dln_m|c=.05,n=20':>18}")
for rec in out["cases"]:
    ch = rec["channels"]["phi50"]
    key = "c0.05|n20"
    dm = ch["multiplier"].get(key, {}).get("dln_m")
    print(f"{rec['jurisdiction'][:16]:16s}{rec['sector_pct_gdp']:>8.2f}"
          f"{rec['m2_pct_gdp']:>8.1f}{rec['velocity']:>7.3f}"
          f"{rec['reserve_ratio']:>7.3f}"
          f"{ch['dln_gdp_pct']:>11.3f}%"
          f"{(dm*100 if dm is not None else float('nan')):>17.4f}%")
