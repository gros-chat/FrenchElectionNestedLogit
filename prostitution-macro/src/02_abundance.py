#!/usr/bin/env python3
"""Data-abundance index over candidate jurisdictions.

Answering "what does a prostitution ban or reinstatement do to GDP, money
velocity and the multiplier" needs three legs at once:

  L1  a measured prostitution sector          (how big is the thing being banned)
  L2  a dated regime change that is testable  (>=3 pre and >=3 post years, and a
                                               national monetary aggregate that
                                               exists over the event window)
  L3  monetary aggregates                     (velocity and multiplier proxies)
  L4  national accounts                       (GDP levels and growth)

A jurisdiction missing any leg cannot answer the question at all, so the
composite is the GEOMETRIC mean of the four normalised legs: a zero anywhere
drives the score to zero. The additive score is reported alongside so the
reader can see what the weighting does.

Writes data/abundance.csv and out/abundance.json
"""
import csv, json, os, math

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(HERE, *p)

def load_csv(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))

panel = load_csv(D("data", "panel.csv"))
regimes = load_csv(D("data", "regimes.csv"))
sector = load_csv(D("data", "sector_measurement.csv"))

def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

# ---- machine-counted macro coverage, per iso3 -------------------------
cov = {}
for r in panel:
    c = cov.setdefault(r["iso3"], dict(gdp=0, m2=0, vel=0, mlq=0, mcr=0, years=set()))
    c["years"].add(int(r["year"]))
    if f(r["gdp_cur"]) is not None: c["gdp"] += 1
    if f(r["m2_cur"]) is not None:  c["m2"] += 1
    if f(r["velocity"]) is not None: c["vel"] += 1
    if f(r["mult_liq"]) is not None: c["mlq"] += 1
    if f(r["mult_credit"]) is not None: c["mcr"] += 1

# money-availability lookup: iso3 -> set of years with broad money
m2yrs = {}
for r in panel:
    if f(r["m2_cur"]) is not None:
        m2yrs.setdefault(r["iso3"], set()).add(int(r["year"]))

WIN = (1960, 2020)

def testable(ev_iso, yr):
    """Event is testable if the currency area has broad money for >=3 years
    either side of the event, inside the data window."""
    base = ev_iso.split("-")[0]          # GBR-NIR -> GBR, USA-RI -> USA
    ys = m2yrs.get(base, set())
    pre = sum(1 for k in range(yr - 3, yr) if k in ys and k >= WIN[0])
    post = sum(1 for k in range(yr, yr + 4) if k in ys and k <= WIN[1])
    return pre >= 3 and post >= 3

# events per jurisdiction key used in sector_measurement (national iso3) and
# the two subnational cases
ev_by_juris = {}
for d in regimes:
    key = d["iso3"]
    ev_by_juris.setdefault(key, []).append(d)

rows = []
for s in sector:
    iso = s["iso3"]
    c = cov.get(iso, dict(gdp=0, m2=0, vel=0, mlq=0, mcr=0))
    evs = ev_by_juris.get(iso, [])
    # a subnational unit's own events live under e.g. GBR-NIR / USA-RI
    sub_keys = [k for k in ev_by_juris if k.startswith(iso + "-")]
    sub_evs = [e for k in sub_keys for e in ev_by_juris[k]]
    all_evs = evs + sub_evs
    n_ev = len(all_evs)
    n_test_nat = sum(1 for e in evs if WIN[0] <= int(e["event_year"]) <= WIN[1]
                     and testable(e["iso3"], int(e["event_year"])))
    # subnational events cannot be tested on velocity/multiplier - no separate
    # money stock for a region - so they count for GDP-side identification only
    n_test_sub = sum(1 for e in sub_evs if WIN[0] <= int(e["event_year"]) <= WIN[1])
    rows.append(dict(
        jurisdiction=s["jurisdiction"], iso3=iso,
        gdp_years=c["gdp"], m2_years=c["m2"], velocity_years=c["vel"],
        mult_liq_years=c["mlq"], mult_credit_years=c["mcr"],
        official_output_years=int(s["official_output_years"]),
        in_official_gdp=int(s["in_official_gdp"]),
        independent_estimates=int(s["independent_estimates"]),
        sector_share_gdp_pct=float(s["sector_share_gdp_pct"]),
        subnational_variation=int(s["subnational_variation"]),
        n_events=n_ev, n_events_testable_national=n_test_nat,
        n_events_subnational=n_test_sub,
        note=s["note"]))

# ---- legs, each normalised to its own max across candidates -----------
def norm(key, rows, cap=None):
    vals = [r[key] for r in rows]
    mx = max(vals) if cap is None else cap
    return [0.0 if mx == 0 else min(1.0, v / mx) for v in vals]

# L1 measurement: years of prostitution-specific official output, with a bonus
#    for being inside official GDP and for independent market-size estimates
for r in rows:
    r["_meas_raw"] = (r["official_output_years"] * (1.0 + 0.5 * r["in_official_gdp"])
                      + 3.0 * r["independent_estimates"])
# L2 events: national testable events count double (they support the monetary
#    tests); subnational events support GDP-side tests only
for r in rows:
    r["_ev_raw"] = 2.0 * r["n_events_testable_national"] + 1.0 * r["n_events_subnational"]
# L3 monetary coverage
for r in rows:
    r["_mon_raw"] = r["velocity_years"] + 0.5 * (r["mult_credit_years"] + r["mult_liq_years"])
# L4 national accounts
for r in rows:
    r["_na_raw"] = r["gdp_years"]

for leg, key in (("L1_measurement", "_meas_raw"), ("L2_events", "_ev_raw"),
                 ("L3_money", "_mon_raw"), ("L4_accounts", "_na_raw")):
    for r, v in zip(rows, norm(key, rows)):
        r[leg] = round(v, 4)

EPS = 1e-3
for r in rows:
    legs = [r["L1_measurement"], r["L2_events"], r["L3_money"], r["L4_accounts"]]
    r["score_additive"] = round(sum(legs) / 4, 4)
    r["score_geometric"] = round(math.exp(sum(math.log(max(x, EPS)) for x in legs) / 4), 4)

rows.sort(key=lambda r: -r["score_geometric"])
for i, r in enumerate(rows, 1):
    r["rank"] = i
    for k in list(r):
        if k.startswith("_"):
            del r[k]

cols = ["rank", "jurisdiction", "iso3", "score_geometric", "score_additive",
        "L1_measurement", "L2_events", "L3_money", "L4_accounts",
        "official_output_years", "in_official_gdp", "independent_estimates",
        "sector_share_gdp_pct", "n_events", "n_events_testable_national",
        "n_events_subnational", "subnational_variation",
        "gdp_years", "m2_years", "velocity_years", "mult_credit_years",
        "mult_liq_years", "note"]
with open(D("data", "abundance.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)
with open(D("out", "abundance.json"), "w") as fh:
    json.dump(rows, fh, indent=1)

w = max(60, 0)
print(f"{'rk':>2} {'jurisdiction':<16}{'geo':>7}{'add':>7}{'L1':>6}{'L2':>6}{'L3':>6}{'L4':>6}"
      f"{'offyr':>6}{'%gdp':>6}{'evN':>4}{'evS':>4}{'velyr':>6}")
for r in rows:
    print(f"{r['rank']:>2} {r['jurisdiction'][:16]:<16}{r['score_geometric']:>7.3f}"
          f"{r['score_additive']:>7.3f}{r['L1_measurement']:>6.2f}{r['L2_events']:>6.2f}"
          f"{r['L3_money']:>6.2f}{r['L4_accounts']:>6.2f}"
          f"{r['official_output_years']:>6}{r['sector_share_gdp_pct']:>6.2f}"
          f"{r['n_events_testable_national']:>4}{r['n_events_subnational']:>4}"
          f"{r['velocity_years']:>6}")
