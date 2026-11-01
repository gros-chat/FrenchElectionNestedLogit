#!/usr/bin/env python3
"""Build the macro panel used to test prostitution-regime effects on GDP,
money velocity and multiplier proxies.

Source: World Bank World Development Indicators, 1960-2020, via the public
mirror github.com/ZeningQu/World-Bank-Data-by-Indicators (raw.githubusercontent).
The live World Bank / IMF / FRED / ONS / BEA endpoints are not reachable from
this environment, so the mirror is the data channel; it is the same WDI
extract, pre-cleaned.

Writes data/panel.csv
"""
import csv, io, os, sys, urllib.request, json

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("PM_CACHE", os.path.join(HERE, ".cache"))
os.makedirs(CACHE, exist_ok=True)

BASE = ("https://raw.githubusercontent.com/ZeningQu/"
        "World-Bank-Data-by-Indicators/master")
FILES = {"eco": "economy-and-growth/economy-and-growth.csv",
         "fin": "financial-sector/financial-sector.csv"}

# WDI series we need, keyed by the mirror's column label (newlines collapsed).
WANT = {
 "eco": {
  "average_value_GDP (current LCU)":            "gdp_cur",
  "average_value_GDP (constant LCU)":           "gdp_con",
  "average_value_GDP per capita (constant LCU)":"gdppc_con",
  "average_value_GDP deflator (base year varies by country)": "deflator",
  "average_value_GDP growth (annual %)":        "gdp_growth",
  "average_value_GDP (current US$)":            "gdp_usd",
  "average_value_Gross domestic savings (% of GDP)": "savings_gdp",
 },
 "fin": {
  "average_value_Broad money (current LCU)":    "m2_cur",
  "average_value_Broad money (% of GDP)":       "m2_gdp",
  "average_value_Broad money growth (annual %)":"m2_growth",
  "average_value_Bank liquid reserves to bank assets ratio (%)": "res_ratio",
  "average_value_Domestic credit to private sector (% of GDP)":  "cred_priv_gdp",
  "average_value_Domestic credit provided by financial sector (% of GDP)": "cred_fin_gdp",
  "average_value_Net domestic credit (current LCU)": "net_credit",
  "average_value_Consumer price index (2010 = 100)": "cpi",
  "average_value_Inflation, consumer prices (annual %)": "infl",
 },
}

# World Bank regional / income aggregates -> not countries.
AGG = set("""ARB CSS CEB EAR EAS EAP TEA EMU ECS ECA TEC EUU FCS HPC HIC
IBD IBT IDB IDX IDA IMN INX LTE LCN LAC TLA LDC LMY LIC LMC MEA MNA TMN MIC
NAC INX OED OSS PSS PST PRE SST SAS TSA SSF SSA TSS UMC WLD AFE AFW LAC
EAS ECS LCN MEA NAC SAS SSF CHI XKX""".split())

def fetch(key):
    url = f"{BASE}/{FILES[key]}"
    dst = os.path.join(CACHE, key + ".csv")
    if not os.path.exists(dst) or os.path.getsize(dst) < 1000:
        sys.stderr.write(f"downloading {url}\n")
        req = urllib.request.Request(url, headers={"User-Agent": "research/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r, open(dst, "wb") as f:
            f.write(r.read())
    return dst

def num(s):
    s = (s or "").strip()
    if s in ("", "null", "NA", "NaN"):
        return None
    try:
        return float(s)
    except ValueError:
        return None

def read(key):
    """-> {(iso3, year): {var: value}}"""
    path = fetch(key)
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.reader(f)
        head = [h.replace("\n", " ").replace("\r", " ").strip() for h in next(rdr)]
        idx = {}
        for label, var in WANT[key].items():
            if label in head:
                idx[var] = head.index(label)
            else:
                sys.stderr.write(f"  !! column not found in {key}: {label}\n")
        for row in rdr:
            if len(row) < 3:
                continue
            iso, yr = row[1].strip(), row[2].strip()
            if not iso or iso in AGG or len(iso) != 3 or not yr.isdigit():
                continue
            rec = out.setdefault((iso, int(yr)), {})
            rec["country"] = row[0].strip()
            for var, i in idx.items():
                if i < len(row):
                    v = num(row[i])
                    if v is not None:
                        rec[var] = v
    return out

def main():
    eco, fin = read("eco"), read("fin")
    keys = sorted(set(eco) | set(fin))
    rows = []
    for k in keys:
        r = {}
        r.update(eco.get(k, {}))
        r.update(fin.get(k, {}))
        r["iso3"], r["year"] = k[0], k[1]
        rows.append(r)

    # ---- derived monetary objects -------------------------------------
    for r in rows:
        gdp, m2, m2g = r.get("gdp_cur"), r.get("m2_cur"), r.get("m2_gdp")
        # Velocity of broad money: V = PY / M.  Prefer the ratio of the two
        # LCU levels; fall back on the published M2/GDP share.
        if gdp and m2 and m2 > 0:
            r["velocity"] = gdp / m2
        elif m2g and m2g > 0:
            r["velocity"] = 100.0 / m2g
        # Bank liquidity multiplier: inverse of liquid reserves / assets.
        rr = r.get("res_ratio")
        if rr and rr > 0:
            r["mult_liq"] = 100.0 / rr
        # Credit multiplier: private credit created per unit of broad money.
        cp = r.get("cred_priv_gdp")
        if cp is not None and m2g and m2g > 0:
            r["mult_credit"] = cp / m2g
        cf = r.get("cred_fin_gdp")
        if cf is not None and m2g and m2g > 0:
            r["mult_credit_fin"] = cf / m2g

    # ---- treatment ---------------------------------------------------
    regimes = []
    with open(os.path.join(HERE, "data", "regimes.csv"), newline="") as f:
        for d in csv.DictReader(f):
            d["event_year"] = int(d["event_year"])
            d["direction"] = int(d["direction"])
            regimes.append(d)

    # national events only enter the country panel
    nat = [d for d in regimes if d["level"] == "national"]
    by_iso = {}
    for d in nat:
        by_iso.setdefault(d["iso3"], []).append(d)

    for r in rows:
        evs = by_iso.get(r["iso3"], [])
        bans = [d["event_year"] for d in evs if d["direction"] == -1]
        libs = [d["event_year"] for d in evs if d["direction"] == +1]
        r["n_events"] = len(evs)
        r["ever_ban"] = int(bool(bans))
        r["ever_lib"] = int(bool(libs))
        # first event of each sign, and event time relative to it
        r["ban_year"] = min(bans) if bans else ""
        r["lib_year"] = min(libs) if libs else ""
        r["k_ban"] = (r["year"] - min(bans)) if bans else ""
        r["k_lib"] = (r["year"] - min(libs)) if libs else ""
        # post indicators (absorbing)
        r["post_ban"] = int(bool(bans) and r["year"] >= min(bans))
        r["post_lib"] = int(bool(libs) and r["year"] >= min(libs))
        # cumulative legal-stance index: +1 each liberalisation, -1 each ban
        r["stance"] = sum(d["direction"] for d in evs if r["year"] >= d["event_year"])

    cols = ["iso3", "country", "year", "gdp_cur", "gdp_con", "gdppc_con",
            "deflator", "gdp_growth", "gdp_usd", "savings_gdp",
            "m2_cur", "m2_gdp", "m2_growth", "res_ratio", "cred_priv_gdp",
            "cred_fin_gdp", "net_credit", "cpi", "infl",
            "velocity", "mult_liq", "mult_credit", "mult_credit_fin",
            "n_events", "ever_ban", "ever_lib", "ban_year", "lib_year",
            "k_ban", "k_lib", "post_ban", "post_lib", "stance"]
    out = os.path.join(HERE, "data", "panel.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["iso3"], r["year"])):
            w.writerow(r)

    n_v = sum(1 for r in rows if r.get("velocity") is not None)
    sys.stderr.write(f"wrote {out}: {len(rows)} country-years, "
                     f"{len({r['iso3'] for r in rows})} countries, "
                     f"{n_v} with velocity\n")

if __name__ == "__main__":
    main()
