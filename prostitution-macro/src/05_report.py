#!/usr/bin/env python3
"""Render the self-contained HTML report (repo convention: one file, inline
SVG with <title> tooltips, light/dark via tokens)."""
import csv, json, os, html
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)
D = lambda *p: os.path.join(HERE, *p)

def jload(p, default=None):
    try:
        with open(p) as f: return json.load(f)
    except Exception: return default if default is not None else {}

def cload(p):
    with open(p, newline="") as f: return list(csv.DictReader(f))

RES = jload(D("out", "results.json"))
ARI = jload(D("out", "arithmetic.json"))
ABU = jload(D("out", "abundance.json"), [])
REG = cload(D("data", "regimes.csv"))
MEA = cload(D("data", "prostitution_measures.csv"))

e = html.escape
def f2(v, n=2, pct=False, sign=False):
    if v is None or (isinstance(v, float) and not np.isfinite(v)): return "&mdash;"
    s = f"{v*100:+.{n}f}" if (pct and sign) else (f"{v*100:.{n}f}" if pct else
        (f"{v:+.{n}f}" if sign else f"{v:.{n}f}"))
    return s.replace("-", "\u2212") + ("%" if pct else "")

OUTLAB = {"ln_rgdp_pc": "Real GDP per capita",
          "infl_rate": "CPI inflation",
          "m2_growth_rate": "Broad money growth",
          "ln_velocity": "Velocity of broad money",
          "ln_mult_credit": "Credit multiplier",
          "ln_mult_liq": "Bank liquidity multiplier"}
ARMLAB = {"ban": "Ban (purchase criminalised)", "lib": "Reinstatement (legalised / decriminalised)"}

# ====================================================== chart helpers
def ax_ticks(lo, hi, n=5):
    if hi <= lo: hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** np.floor(np.log10(raw))
    step = min([m for m in (1, 2, 2.5, 5, 10) if m * mag >= raw] or [10]) * mag
    t0 = np.floor(lo / step) * step
    return [t0 + i * step for i in range(int((hi - t0) / step) + 2) if t0 + i * step <= hi + 1e-9]

def event_chart(es, cs, title, cid):
    """event-study coefficients with 95% CI, plus the CS-DiD path."""
    if not es or "error" in es: return f'<p class="note">Not estimable: {e(str(es.get("error","no data")))}</p>'
    ks = sorted(int(k[1:]) for k in es if not k.startswith("_"))
    if not ks: return '<p class="note">Not estimable.</p>'
    pts = [(k, es[f"k{k:+d}"][0], es[f"k{k:+d}"][1]) for k in ks]
    csk = (cs or {}).get("by_k", {})
    W, H, L, R, T, B = 760, 250, 56, 14, 14, 34
    lo = min(min(b - 2*s for _, b, s in pts), min([v for v in csk.values() if v is not None] or [0]))
    hi = max(max(b + 2*s for _, b, s in pts), max([v for v in csk.values() if v is not None] or [0]))
    pad = 0.08 * (hi - lo or 0.02); lo -= pad; hi += pad
    sx = lambda k: L + (k - ks[0]) / max(1, (ks[-1] - ks[0])) * (W - L - R)
    sy = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    s = []
    for t in ax_ticks(lo, hi):
        s.append(f'<line x1="{L}" y1="{sy(t):.1f}" x2="{W-R}" y2="{sy(t):.1f}" stroke="var(--line)"/>'
                 f'<text x="{L-8}" y="{sy(t)+4:.1f}" text-anchor="end">{t*100:.1f}%</text>')
    s.append(f'<line x1="{L}" y1="{sy(0):.1f}" x2="{W-R}" y2="{sy(0):.1f}" stroke="var(--ink-3)" stroke-width="1.5"/>')
    x0 = sx(-0.5) if ks[0] <= -1 else L
    s.append(f'<line x1="{x0:.1f}" y1="{T}" x2="{x0:.1f}" y2="{H-B}" stroke="var(--warn)" stroke-width="1.5"/>'
             f'<text x="{x0+5:.1f}" y="{T+11}" style="fill:var(--warn);font-size:10.5px">reform</text>')
    # CI whiskers + dots (series 1 = blue)
    for k, b, se in pts:
        X = sx(k); loq, hiq = b - 1.96*se, b + 1.96*se
        sig = (loq > 0) or (hiq < 0)
        s.append(f'<g><title>k = {k:+d}: {b*100:+.2f}% (95% CI {loq*100:+.2f}% to {hiq*100:+.2f}%)</title>'
                 f'<line x1="{X:.1f}" y1="{sy(loq):.1f}" x2="{X:.1f}" y2="{sy(hiq):.1f}" stroke="var(--s1)" stroke-width="2"/>'
                 f'<circle cx="{X:.1f}" cy="{sy(b):.1f}" r="4.5" fill="{"var(--s1)" if sig else "var(--surface)"}" stroke="var(--s1)" stroke-width="2"/></g>')
        s.append(f'<text x="{X:.1f}" y="{H-B+15}" text-anchor="middle">{k:+d}</text>')
    # CS-DiD path (series 2 = orange), dashed to double-encode
    cp = [(int(k), v) for k, v in csk.items() if v is not None and ks[0] <= int(k) <= ks[-1]]
    if len(cp) > 1:
        cp.sort()
        s.append('<polyline fill="none" stroke="var(--s2)" stroke-width="2" stroke-dasharray="5 3" points="'
                 + " ".join(f"{sx(k):.1f},{sy(v):.1f}" for k, v in cp) + '"/>')
        for k, v in cp:
            s.append(f'<g><title>Callaway-Sant\'Anna k = {k:+d}: {v*100:+.2f}%</title>'
                     f'<rect x="{sx(k)-5:.1f}" y="{sy(v)-5:.1f}" width="10" height="10" fill="var(--s2)" stroke="var(--surface)" stroke-width="2"/></g>')
    s.append(f'<text x="{L}" y="{H-2}" style="font-size:10.5px">years from reform</text>')
    return (f'<div class="chart"><svg viewBox="0 0 {W} {H}" role="img" aria-label="{e(title)}">'
            + "".join(s) + '</svg>'
            '<div class="legend"><span><span class="dot" style="background:var(--s1)"></span>Two-way FE event study, 95% CI</span>'
            '<span><span class="dot" style="background:var(--s2)"></span>Callaway&ndash;Sant\'Anna (not-yet-treated)</span>'
            '<span>Filled dot: 95% CI excludes zero</span></div></div>')

def dumbbell(rows, cid):
    """log-scale dot plot: mechanical signal vs detection noise, per jurisdiction."""
    W, L, R, T = 760, 132, 86, 16
    rh, B = 30, 40
    H = T + rh*len(rows) + B
    vals = [v for r in rows for v in (r["signal"], r["noise"]) if v and v > 0]
    lo, hi = min(vals)*0.6, max(vals)*1.6
    lx = lambda v: L + (np.log10(max(v, 1e-9)) - np.log10(lo)) / (np.log10(hi) - np.log10(lo)) * (W-L-R)
    s = []
    dec = range(int(np.floor(np.log10(lo))), int(np.ceil(np.log10(hi)))+1)
    for d in dec:
        v = 10.0**d
        if not (lo <= v <= hi): continue
        s.append(f'<line x1="{lx(v):.1f}" y1="{T}" x2="{lx(v):.1f}" y2="{H-B+4}" stroke="var(--line)"/>'
                 f'<text x="{lx(v):.1f}" y="{H-B+19}" text-anchor="middle">{v:g}%</text>')
    for i, r in enumerate(rows):
        y = T + rh*i + rh/2
        a, b = lx(r["signal"]), lx(r["noise"])
        s.append(f'<text x="{L-10}" y="{y+4:.1f}" text-anchor="end" style="fill:var(--ink);font-size:12.5px">{e(r["label"])}</text>')
        s.append(f'<line x1="{min(a,b):.1f}" y1="{y:.1f}" x2="{max(a,b):.1f}" y2="{y:.1f}" stroke="var(--line)" stroke-width="3"/>')
        s.append(f'<g><title>{e(r["label"])}: mechanical effect of suppressing half the sector = {r["signal"]:.3f}% of GDP</title>'
                 f'<circle cx="{a:.1f}" cy="{y:.1f}" r="5.5" fill="var(--s1)" stroke="var(--surface)" stroke-width="2"/></g>')
        s.append(f'<g><title>{e(r["label"])}: one-year idiosyncratic surprise in this outcome = {r["noise"]:.2f}%</title>'
                 f'<circle cx="{b:.1f}" cy="{y:.1f}" r="5.5" fill="var(--s2)" stroke="var(--surface)" stroke-width="2"/></g>')
        ratio = r["noise"]/r["signal"] if r["signal"] else float("inf")
        s.append(f'<text x="{W-R+8}" y="{y+4:.1f}" style="fill:var(--ink-2);font-size:12px">{ratio:,.0f}&times;</text>')
    s.append(f'<text x="{W-R+8}" y="{T-2}" style="fill:var(--ink-3);font-size:10.5px">noise/signal</text>')
    return (f'<div class="chart"><svg viewBox="0 0 {W} {H}" role="img" aria-label="Mechanical signal against noise floor">'
            + "".join(s) + '</svg>'
            '<div class="legend"><span><span class="dot" style="background:var(--s1)"></span>Mechanical effect on GDP of suppressing half the sector</span>'
            '<span><span class="dot" style="background:var(--s2)"></span>One-year idiosyncratic surprise (sd), advanced economies</span></div>'
            '<p class="cap">Log scale. The right-hand column is how many times larger the noise is than the thing being looked for.</p></div>')

def scm_chart(r, title):
    if not r: return '<p class="note">Not estimable (donor pool or coverage too thin).</p>'
    W, H, L, R, T, B = 760, 270, 62, 60, 16, 34
    ys, act, syn = r["years"], r["actual"], r["synthetic"]
    lo, hi = min(min(act), min(syn)), max(max(act), max(syn))
    pad = 0.08*(hi-lo or 1); lo -= pad; hi += pad
    sx = lambda y: L + (y - ys[0])/max(1, ys[-1]-ys[0])*(W-L-R)
    sy = lambda v: T + (hi-v)/(hi-lo)*(H-T-B)
    s = []
    for t in ax_ticks(lo, hi):
        s.append(f'<line x1="{L}" y1="{sy(t):.1f}" x2="{W-R}" y2="{sy(t):.1f}" stroke="var(--line)"/>'
                 f'<text x="{L-8}" y="{sy(t)+4:.1f}" text-anchor="end">{t:.2f}</text>')
    X0 = sx(r["t0"]-0.5)
    s.append(f'<line x1="{X0:.1f}" y1="{T}" x2="{X0:.1f}" y2="{H-B}" stroke="var(--warn)" stroke-width="1.5"/>'
             f'<text x="{X0+5:.1f}" y="{T+11}" style="fill:var(--warn);font-size:10.5px">{r["t0"]}</text>')
    for y in ys:
        if y % 5 == 0:
            s.append(f'<text x="{sx(y):.1f}" y="{H-B+15}" text-anchor="middle">{y}</text>')
    s.append('<polyline fill="none" stroke="var(--s2)" stroke-width="2" stroke-dasharray="5 3" points="'
             + " ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in zip(ys, syn)) + '"/>')
    s.append('<polyline fill="none" stroke="var(--s1)" stroke-width="2" points="'
             + " ".join(f"{sx(y):.1f},{sy(v):.1f}" for y, v in zip(ys, act)) + '"/>')
    for y, a, sv in zip(ys, act, syn):
        s.append(f'<g><title>{y}: actual {a:.3f}, synthetic {sv:.3f}, gap {(a-sv)*100:+.2f}%</title>'
                 f'<rect x="{sx(y)-6:.1f}" y="{T}" width="12" height="{H-T-B}" fill="transparent"/></g>')
    s.append(f'<text x="{sx(ys[-1])+6:.1f}" y="{sy(act[-1])+4:.1f}" style="fill:var(--s1);font-size:11.5px;font-weight:650">{e(r["unit"])}</text>')
    s.append(f'<text x="{sx(ys[-1])+6:.1f}" y="{sy(syn[-1])+4:.1f}" style="fill:var(--s2);font-size:11.5px;font-weight:650">synthetic</text>')
    wts = ", ".join(f"{c} {w:.2f}" for c, w in r["weights"][:5])
    return (f'<div class="chart"><svg viewBox="0 0 {W} {H}" role="img" aria-label="{e(title)}">' + "".join(s) + '</svg>'
            f'<p class="cap">Mean post-reform gap {r["post_mean_gap"]*100:+.2f}%. '
            f'Pre-reform fit RMSPE {r["pre_rmspe"]*100:.2f}%, post {r["post_rmspe"]*100:.2f}%, ratio {r["ratio"]:.2f}. '
            f'In-space placebo p = {("%.3f" % r["placebo_p"]) if r.get("placebo_p") is not None else "&mdash;"} '
            f'over {r.get("n_placebo",0)} donors. Weights: {e(wts)}.</p></div>')

def ranked_bars(rows, unit="", cid=""):
    W, L, R, T = 760, 150, 60, 10
    rh = 24; H = T + rh*len(rows) + 12
    mx = max(r["v"] for r in rows) or 1
    s = []
    for i, r in enumerate(rows):
        y = T + rh*i
        w = max(0.0, r["v"]/mx*(W-L-R))
        s.append(f'<text x="{L-10}" y="{y+16:.1f}" text-anchor="end" style="fill:var(--ink);font-size:12.5px">{e(r["label"])}</text>')
        s.append(f'<g><title>{e(r["label"])}: {r["v"]:.3f}{e(unit)}{e(r.get("extra",""))}</title>'
                 f'<rect x="{L}" y="{y+4}" width="{w:.1f}" height="15" rx="3" fill="var(--s1)"/></g>')
        s.append(f'<text x="{L+w+8:.1f}" y="{y+16:.1f}" style="fill:var(--ink-2);font-size:12px">{r["v"]:.3f}</text>')
    return f'<div class="chart"><svg viewBox="0 0 {W} {H}" role="img" aria-label="ranked bars">' + "".join(s) + '</svg></div>'

def table(headers, rows, cls=""):
    th = "".join(f'<th class="{"l" if i==0 else ""}">{h}</th>' for i, h in enumerate(headers))
    tr = "".join("<tr>" + "".join(f'<td class="{"l" if i==0 else ""}">{c}</td>'
                 for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="tw {cls}"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'

# ====================================================== section builders
def sec_data():
    rows = []
    for r in sorted(REG, key=lambda r: (int(r["event_year"]), r["jurisdiction"])):
        dirn = ('<span class="tag t-m">ban</span>' if r["direction"] == "-1"
                else '<span class="tag t-p">reinstate</span>')
        lvl = "national" if r["level"] == "national" else "subnational"
        cur = {"own": "own currency", "euro": "euro area",
               "own_shared": "shares a currency"}.get(r["currency_area"], r["currency_area"])
        rows.append([f'<a href="{e(r["source"])}">{e(r["jurisdiction"])}</a>',
                     e(r["event_date"]), dirn, e(r["instrument"].replace("_", " ")),
                     lvl, cur])
    t1 = table(["Jurisdiction", "In force", "Direction", "Instrument", "Level", "Money"], rows)
    mrows = []
    for m in MEA:
        val = m["value"]
        unit = m["unit"]
        disp = f'{val} {unit}' if val else "&mdash;"
        pg = f'{m["pct_gdp"]}%' if m["pct_gdp"] else "&mdash;"
        ingdp = {"yes": '<span class="tag t-s">in GDP</span>',
                 "no": '<span class="tag t-n">satellite</span>'}.get(m["in_official_gdp"], '<span class="tag t-n">n/a</span>')
        mrows.append([e(m["jurisdiction"]), m["year"], e(m["measure"].replace("_", " ")),
                      disp, pg, ingdp,
                      f'<a href="{e(m["source"])}">{e(m["source_org"])}</a>'])
    t2 = table(["Jurisdiction", "Year", "Measure", "Value", "% of GDP", "Status", "Source"], mrows)
    return f"""
<section class="step" id="s2"><div class="step-head"><span class="plate">2</span><div>
<h2>What there is to work with</h2>
<p>Two tables. The first is the treatment: every dated change of prostitution
law I could source, in force date and direction. The second is the outcome-side
raw material: every quantitative measurement of the sector I could source, and
whether it sits inside official GDP or only in a research satellite account.</p>
</div></div>
<h3>Regime changes, 1999&ndash;2022</h3>
{t1}
<p class="note">Twenty events. Fourteen are bans or tightenings, six are
legalisations or decriminalisations. The <b>Money</b> column is what decides
whether an event can be tested on velocity at all: a country inside the euro
area has no national money stock, and a region has no money stock of its own.</p>
<h3>Measured size of the sector</h3>
{t2}
<p class="note">Note the spread in official estimates: the ONS puts UK
prostitution at about 0.35&ndash;0.4% of GDP, while CBS puts the Dutch figure at
roughly 0.08% &mdash; a fivefold methodological divergence between two
neighbouring statistical agencies measuring the same thing under the same ESA
2010 obligation. The BEA's US figure is smaller again, and is not in GDP.
South Korea is the outlier by two orders of magnitude.</p>
</section>"""

def sec_abundance():
    if not ABU: return ""
    rows = []
    for r in ABU:
        rows.append([
            f'{r["rank"]}. {e(r["jurisdiction"])}',
            f'<b>{r["score_geometric"]:.3f}</b>', f'{r["score_additive"]:.3f}',
            f'{r["L1_measurement"]:.2f}', f'{r["L2_events"]:.2f}',
            f'{r["L3_money"]:.2f}', f'{r["L4_accounts"]:.2f}',
            r["official_output_years"], r["n_events_testable_national"],
            r["n_events_subnational"], r["velocity_years"],
            f'{r["sector_share_gdp_pct"]:.2f}%'])
    t = table(["Jurisdiction", "Score", "Additive", "L1 sector", "L2 events",
               "L3 money", "L4 accounts", "Official yrs", "Nat. events",
               "Sub. events", "Velocity yrs", "Sector"], rows)
    bars = ranked_bars([{"label": r["jurisdiction"], "v": r["score_geometric"],
                         "extra": f' (sector measurement {r["L1_measurement"]:.2f}, events {r["L2_events"]:.2f}, money {r["L3_money"]:.2f}, accounts {r["L4_accounts"]:.2f})'}
                        for r in ABU[:12]])
    top = ABU[0]; second = ABU[1] if len(ABU) > 1 else None
    kor = next((r for r in ABU if r["iso3"] == "KOR"), None)
    return f"""
<section class="step" id="s3"><div class="step-head"><span class="plate">3</span><div>
<h2>Where the data is most abundant</h2>
<p>The question needs four things at once, and a jurisdiction missing any one of
them cannot answer it. So the score is the <b>geometric</b> mean of four
normalised legs &mdash; a zero anywhere takes the whole score to zero. The
additive score is shown beside it so you can see exactly what the weighting does.</p>
</div></div>
<ul class="flow">
<li><span class="plate">L1</span><span><b>A measured sector</b><span>Years of
prostitution-specific official output, weighted up if it is inside GDP, plus
independent market-size estimates.</span></span></li>
<li><span class="plate">L2</span><span><b>A testable reform</b><span>Dated, with
at least three years either side inside the data window, and a money stock that
exists over it.</span></span></li>
<li><span class="plate">L3</span><span><b>Monetary aggregates</b><span>Years of
broad money, and of the two multiplier proxies.</span></span></li>
<li><span class="plate">L4</span><span><b>National accounts</b><span>Years of
GDP in current and constant local currency.</span></span></li>
</ul>
{bars}
{t}
<p><b>The United Kingdom wins</b>, at {top["score_geometric"]:.3f}. It is the only
jurisdiction strong on all four legs: {top["official_output_years"]} years of
prostitution output inside official GDP (the ONS line, the largest official
share anywhere at {top["sector_share_gdp_pct"]:.2f}% of GDP), a national reform in
2010, a <i>within-country</i> reform in Northern Ireland in 2015 that leaves
England, Wales and Scotland as controls, and {top["velocity_years"]} unbroken
years of its own broad money.</p>
<p class="note">{"The United States is a close second ("+("%.3f"%second["score_geometric"])+") and actually wins the measurement leg outright, with "+str(second["official_output_years"])+" years of BEA prostitution estimates &mdash; but they sit in a research satellite account rather than in GDP, the sector is measured at only "+("%.2f"%second["sector_share_gdp_pct"])+"% of GDP, and there has never been a national reform to test. " if second else ""}South
Korea ranks {kor["rank"] if kor else "&mdash;"} on abundance yet matters more than its rank
suggests: at {kor["sector_share_gdp_pct"]:.2f}% of GDP its sector is the only one
anywhere large enough for the question to have any statistical power at all. So
the rest of this report runs the panel on every testable event, and then looks
hard at both the UK (most data) and Korea (biggest shock).</p>
<p class="note">Euro-area members cluster at the bottom not because their
prostitution data is poor &mdash; the Netherlands and Italy publish more of it
than most &mdash; but because monetary union erased their national money stocks.
Their velocity and multiplier legs are literally zero.</p>
</section>"""

def sec_arithmetic():
    noise = ARI.get("noise", {})
    ng = noise.get("gdppc_con", {}).get("sd_advanced")
    nv = noise.get("velocity", {}).get("sd_advanced")
    nm = noise.get("mult_credit", {}).get("sd_advanced")
    cases = ARI.get("cases", [])
    db = [{"label": c["jurisdiction"],
           "signal": abs(c["channels"]["phi50"]["dln_gdp_pct"]),
           "noise": ng*100} for c in cases]
    rows = []
    for c in cases:
        ch = c["channels"]["phi50"]
        dm = ch["multiplier"].get("c0.05|n20", {})
        rows.append([e(c["jurisdiction"]), f'{c["sector_pct_gdp"]:.2f}%',
                     f'{c["m2_pct_gdp"]:.0f}%', f'{c["velocity"]:.3f}',
                     f'{c["reserve_ratio"]*100:.1f}%',
                     f'<b>{ch["dln_gdp_pct"]:+.3f}%</b>',
                     f'{ch["dln_velocity_pct"]:+.3f}%',
                     f'{dm.get("dln_m", float("nan"))*100:+.4f}%',
                     f'{(ng*100)/abs(ch["dln_gdp_pct"]):,.0f}&times;'])
    t = table(["Jurisdiction", "Sector", "M2/GDP", "V", "Reserve ratio r",
               "&Delta;ln GDP", "&Delta;ln V", "&Delta;ln m", "Noise / signal"], rows)
    kor = next((c for c in cases if c["iso3"] == "KOR"), None)
    gbr = next((c for c in cases if c["iso3"] == "GBR"), None)
    return f"""
<section class="step" id="s4"><div class="step-head"><span class="plate">4</span><div>
<h2>How big could the effect possibly be?</h2>
<p>This has to come before any regression, because it sets the bar the
regression then has to clear. No identification is involved &mdash; it is
arithmetic on the size of the sector.</p>
</div></div>
<div class="eq eqwrap">
&Delta;ln Y = &minus;&phi;&middot;s &nbsp;&nbsp;&middot;&nbsp;&nbsp;
V = PY / M &nbsp;&rArr;&nbsp; &Delta;ln V &asymp; &Delta;ln Y &nbsp;&nbsp;&middot;&nbsp;&nbsp;
m = (1+c)/(r+c) &nbsp;&rArr;&nbsp; &part;m/&part;c = (r&minus;1)/(r+c)<sup>2</sup> &lt; 0
</div>
<p>A ban suppresses a fraction &phi; of a sector worth <i>s</i> per cent of GDP,
so measured output falls by &phi;&middot;s. Monetary policy, not the sex trade,
sets the money stock <i>M</i>, so to a first order velocity falls by the same
amount. The multiplier moves through a different door: the suppressed trade
settles in cash, which raises the currency-to-deposit ratio <i>c</i>, and the
multiplier falls in <i>c</i>. If a currency unit is re-spent <i>n</i> times a
year, the extra currency held is &phi;&middot;T/n.</p>
<h3>The signal against the noise</h3>
{dumbbell(db, "dbl")}
<p>The orange dot is the standard deviation of a one-year idiosyncratic surprise
in real GDP per capita among advanced economies &mdash; {f2(ng, 2, pct=True)},
after taking out the common year effect. The blue dot is the whole mechanical
effect of suppressing <i>half</i> the measured sector. For the UK the noise is
about {(ng*100)/abs(gbr["channels"]["phi50"]["dln_gdp_pct"]):,.0f} times the
signal. {f'For Korea it is {(ng*100)/abs(kor["channels"]["phi50"]["dln_gdp_pct"]):,.0f} times &mdash; still larger, but within one order of magnitude, which is why Korea is the only case worth taking seriously.' if kor else ''}</p>
<h3>Every channel, every case</h3>
{t}
<p class="note">&Delta;ln m is computed at c = 0.05 and n = 20. r is the WDI
bank-liquid-reserves-to-assets ratio in the reform year where it exists; the UK
and New Zealand do not report it, so the advanced-economy median for that year
is substituted. Velocity
noise is {f2(nv, 2, pct=True)} and credit-multiplier noise {f2(nm, 2, pct=True)},
so the multiplier column is between one and two orders of magnitude below its own
detection threshold in <i>every</i> case, Korea included.</p>
<h3>Try it yourself</h3>
<div class="controls" id="calc">
 <div class="ctl"><label for="cSec">Sector, % of GDP <output id="oSec">0.37</output></label>
  <input type="range" id="cSec" min="0.02" max="5" step="0.01" value="0.37">
  <div class="hint">ONS UK 0.37 &middot; CBS Netherlands 0.08 &middot; BEA US 0.02 &middot; Korea 4.10</div></div>
 <div class="ctl"><label for="cPhi">Fraction suppressed &phi; <output id="oPhi">0.50</output></label>
  <input type="range" id="cPhi" min="0" max="1" step="0.01" value="0.5">
  <div class="hint">How much of the trade the ban actually stops. Northern Ireland's own statutory review found online advertising <i>rose</i> after its ban, so low values are the realistic ones.</div></div>
 <div class="ctl"><label for="cN">Cash turnover n / year <output id="oN">20</output></label>
  <input type="range" id="cN" min="4" max="104" step="1" value="20">
  <div class="hint">Times a banknote is re-spent per year. Higher n means less cash has to be held to carry the same trade.</div></div>
 <div class="ctl"><label for="cC">Currency / deposits c <output id="oC">0.05</output></label>
  <input type="range" id="cC" min="0.01" max="0.4" step="0.005" value="0.05">
  <div class="hint">Plus reserve ratio r, fixed at 3%, and M2/GDP at 160%.</div></div>
</div>
<div class="kpis">
 <div><b id="kY">&minus;0.185%</b><span>&Delta;ln GDP</span></div>
 <div><b id="kV">&minus;0.185%</b><span>&Delta;ln velocity</span></div>
 <div><b id="kM">&minus;0.021%</b><span>&Delta;ln money multiplier</span></div>
 <div><b id="kD">no</b><span>Detectable against a {f2(ng,2,pct=True)} noise floor?</span></div>
</div>
<p class="note" id="calcNote"></p>
</section>"""

def sec_estimates():
    if not RES.get("cs"): return '<section class="step" id="s5"><p class="note">Estimation output missing.</p></section>'
    noise = ARI.get("noise", {})
    nmap = {"ln_rgdp_pc": noise.get("gdppc_con", {}).get("sd_advanced"),
            "ln_velocity": noise.get("velocity", {}).get("sd_advanced"),
            "ln_mult_credit": noise.get("mult_credit", {}).get("sd_advanced"),
            "ln_mult_liq": noise.get("mult_credit", {}).get("sd_advanced")}
    rows, charts = [], []
    nsig = ntot = 0
    for arm in ("ban", "lib"):
        for o in OUTCOMES_ORDER:
            key = f"{arm}|{o}|all"
            cs, ri = RES["cs"].get(key), RES["ri"].get(key, {})
            samp, pw = RES["samples"].get(key, {}), RES["power"].get(key, {})
            if not cs: continue
            p = ri.get("p_two_sided")
            att = cs.get("att_post")
            if att is not None:
                ntot += 1
            mde = pw.get("mde_80pct")
            if p is not None and p < 0.05: nsig += 1
            flag = ('<span class="tag t-w">p &lt; 0.05</span>' if (p is not None and p < 0.05)
                    else ('<span class="tag t-n">n.s.</span>' if att is not None
                          else '<span class="tag t-n">not estimable</span>'))
            rows.append([
                ARMLAB[arm].split(" (")[0] + " &middot; " + OUTLAB[o],
                samp.get("n_treated", "&mdash;"),
                (lambda t: t if len(t) <= 44 else t[:43].rstrip(", ") + "\u2026")(", ".join(samp.get("treated", []))),
                f2(att, 2, pct=True, sign=True),
                f2(cs.get("pretrend_max"), 2, pct=True),
                ("%.3f" % p) if p is not None else "&mdash;",
                f2(mde, 2, pct=True) if mde else "&mdash;",
                flag])
            charts.append((arm, o, key, cs, ri, samp, pw))
    t = table(["Arm &middot; outcome", "n treated", "Treated countries",
               "Post ATT", "Max pre-trend", "RI p", "MDE (80%)", ""], rows)
    blocks = []
    for arm, o, key, cs, ri, samp, pw in charts:
        if o not in ("ln_rgdp_pc", "ln_velocity", "ln_mult_credit",
                     "infl_rate"): continue
        es = RES["event_study"].get(key, {})
        mde = pw.get("mde_80pct"); mech = None
        if o in ("ln_rgdp_pc", "ln_velocity"):
            cs_case = [c for c in ARI.get("cases", []) if c["iso3"] in samp.get("treated", [])]
            if cs_case:
                mech = np.mean([abs(c["channels"]["phi50"]["dln_gdp_pct"]) for c in cs_case]) / 100
        ratio = (mde / mech) if (mde and mech) else None
        blocks.append(f"""<h4>{ARMLAB[arm]} &middot; {OUTLAB[o]}</h4>
{event_chart(es, cs, f"{arm} {o}", key)}
<p class="note">{samp.get('n_treated',0)} treated countries, {samp.get('n_control',0)} controls,
{samp.get('nobs',0):,} country-years. Aggregate post-reform ATT
{f2(cs.get('att_post'),2,pct=True,sign=True)} with randomization-inference
p = {("%.3f" % ri["p_two_sided"]) if ri.get("p_two_sided") is not None else "&mdash;"}
from {ri.get('B',0):,} placebo draws. The smallest effect this design could detect
80% of the time is {f2(mde,2,pct=True) if mde else "&mdash;"}
{f"&mdash; about {ratio:,.0f} times the mechanical effect of suppressing half the sector." if ratio else ""}</p>""")
    return f"""
<section class="step" id="s5"><div class="step-head"><span class="plate">5</span><div>
<h2>The panel estimates</h2>
<p>Staggered event study with country and year fixed effects, alongside the
Callaway&ndash;Sant'Anna group-time estimator using not-yet-treated countries as
the comparison. With three to nine treated countries a clustered <i>t</i> would
be fiction, so the p-values come from randomization inference: hand the observed
event years to randomly chosen never-reforming countries, re-run the estimator
2,000 times, and read off where the real estimate falls.</p>
</div></div>
{t}
<p>{"None" if nsig == 0 else str(nsig)} of the {ntot}
arm-by-outcome combinations reaches p &lt; 0.05 under randomization inference. That is what the arithmetic in section 4 predicted: the minimum
detectable effects sit one to three orders of magnitude above the largest
effect the sector could mechanically produce. <b>These are bounds, not
findings.</b> The useful statement is not "prostitution law does not affect
GDP" but "an effect of the size this sector could generate is invisible at this
frequency, and anything large enough to see here would have to come from
somewhere other than the sex trade itself."</p>
{"".join(blocks)}
</section>"""

def sec_cases():
    scm = RES.get("scm", {})
    if not scm: return ""
    blocks = []
    LAB = {"GBR": "United Kingdom &mdash; 2010 client offence (most data)",
           "KOR": "South Korea &mdash; 2004 ban (biggest shock)",
           "SWE": "Sweden &mdash; 1999 purchase ban",
           "DNK": "Denmark &mdash; 1999 decriminalisation",
           "NZL": "New Zealand &mdash; 2003 decriminalisation",
           "NOR": "Norway &mdash; 2009 purchase ban"}
    order = ["KOR", "GBR", "SWE", "DNK", "NZL", "NOR"]
    srows = []
    for u in order:
        for o in ("ln_rgdp_pc", "ln_velocity", "ln_mult_credit"):
            k = next((kk for kk in scm if kk.startswith(u + "|") and kk.endswith(o)), None)
            if not k: continue
            r = scm[k]
            p = r.get("placebo_p")
            srows.append([LAB.get(u, u).split(" &mdash;")[0], str(r["t0"]), OUTLAB[o],
                          f2(r["post_mean_gap"], 2, pct=True, sign=True),
                          f'{r["pre_rmspe"]*100:.2f}%', f'{r["ratio"]:.2f}',
                          ("%.3f" % p) if p is not None else "&mdash;",
                          r.get("n_donors", "&mdash;"),
                          ('<span class="tag t-w">p &lt; 0.05</span>' if (p is not None and p < 0.05)
                           else '<span class="tag t-n">n.s.</span>')])
    t = table(["Jurisdiction", "Reform", "Outcome", "Mean post gap",
               "Pre-fit RMSPE", "Post/pre", "Placebo p", "Donors", ""], srows)
    for u in order:
        inner = []
        for o in ("ln_rgdp_pc", "ln_velocity"):
            k = next((kk for kk in scm if kk.startswith(u + "|") and kk.endswith(o)), None)
            if k: inner.append(f'<div><h4>{OUTLAB[o]}</h4>{scm_chart(scm[k], u + " " + o)}</div>')
        if inner:
            blocks.append(f'<h3>{LAB.get(u,u)}</h3><div class="grid2">{"".join(inner)}</div>')
    # robustness: 12 donors, 20 pre-periods -> an identified fit
    rob = RES.get("scm_robust", {})
    rrows = []
    for u in order:
        for o in ("ln_rgdp_pc", "ln_velocity", "ln_mult_credit"):
            kb = next((kk for kk in rob if kk.startswith(u + "|") and kk.endswith(o)), None)
            km = next((kk for kk in scm if kk.startswith(u + "|") and kk.endswith(o)), None)
            if not kb and not km: continue
            m = scm.get(km); b = rob.get(kb)
            def cell(r, f):
                return f(r) if r else "&mdash;"
            rrows.append([LAB.get(u, u).split(" &mdash;")[0], OUTLAB[o],
                cell(m, lambda r: f'{r["pre_rmspe"]*100:.3f}%'),
                cell(m, lambda r: f2(r["post_mean_gap"], 2, pct=True, sign=True)),
                cell(m, lambda r: ("%.3f" % r["placebo_p"]) if r.get("placebo_p") is not None else "&mdash;"),
                cell(b, lambda r: f'{r["pre_rmspe"]*100:.3f}%'),
                cell(b, lambda r: f2(r["post_mean_gap"], 2, pct=True, sign=True)),
                cell(b, lambda r: ("%.3f" % r["placebo_p"]) if r.get("placebo_p") is not None else "&mdash;")])
    trob = table(["Jurisdiction", "Outcome", "Pre-fit", "Gap", "p",
                  "Pre-fit", "Gap", "p"], rrows) if rrows else ""
    robnote = """<h3>Is the fit real, or is it interpolation?</h3>
<p>The left block is the main specification: 35 donors fitted to 12 pre-reform
years. Several pre-fit RMSPEs there are under 0.01% &mdash; the simplex is
reproducing the pre-path almost exactly, which is interpolation, not a control
group, and it inflates the post/pre ratio that the placebo rank is built on.
The right block re-runs each case with <b>12 donors and 20 pre-reform years</b>,
so there are more targets than free weights and the fit has to be earned.</p>
""" + trob + """
<p class="note">Read the two <b>Gap</b> columns against each other. Where a case
survives the tighter specification the gap stays put; where it was interpolation
the gap and its p-value move sharply. Either way the gaps are percentages of GDP
one to three orders of magnitude above what the sector can supply &mdash; which
is the point.</p>"""

    return f"""
<section class="step" id="s6"><div class="step-head"><span class="plate">6</span><div>
<h2>Case by case</h2>
<p>A synthetic control for each reform: a weighted average of never-reforming
countries chosen to track the country's own pre-reform path, then extended past
the reform. The p-value is an in-space placebo rank &mdash; how unusual the
post/pre fit deterioration is against the same exercise run on every donor.</p>
</div></div>
{t}
{robnote}
{"".join(blocks)}
</section>"""

OUTCOMES_ORDER = ["ln_rgdp_pc", "ln_velocity", "ln_mult_credit",
                  "ln_mult_liq", "infl_rate", "m2_growth_rate"]

CSS = """
:root{
  --paper:#F5F6F4; --surface:#FFFFFF; --muted:#ECEFEC; --ink:#15213B; --ink-2:#48536B; --ink-3:#737D90; --line:#D5DAD7;
  --zinc:#5A6A70; --zinc-ink:#FFFFFF; --accent:#35599E; --accent-soft:#E3EAF6; --warn:#8A5300; --warn-soft:#FBF1DF; --pos:#1F7A4D; --neg:#B3261E;
  --s1:#2a78d6; --s2:#eb6834;
  --font:"Archivo","Helvetica Neue",Arial,system-ui,sans-serif; --r-s:3px; --r-m:6px;
  box-sizing:border-box; padding-top:env(safe-area-inset-top,0px); padding-bottom:env(safe-area-inset-bottom,0px);
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --paper:#0F141D; --surface:#161C27; --muted:#1D2431; --ink:#E6E9EF; --ink-2:#AAB3C4; --ink-3:#7F889B; --line:#2B3443;
  --zinc:#6F8087; --accent:#8EAEEB; --accent-soft:#1E2A40; --warn:#E9B35C; --warn-soft:#2E2618; --pos:#5CC08D; --neg:#EC6B63;
  --s1:#3987e5; --s2:#d95926; } }
:root[data-theme="dark"]{
  --paper:#0F141D; --surface:#161C27; --muted:#1D2431; --ink:#E6E9EF; --ink-2:#AAB3C4; --ink-3:#7F889B; --line:#2B3443;
  --zinc:#6F8087; --accent:#8EAEEB; --accent-soft:#1E2A40; --warn:#E9B35C; --warn-soft:#2E2618; --pos:#5CC08D; --neg:#EC6B63;
  --s1:#3987e5; --s2:#d95926; }
*,*::before,*::after{box-sizing:inherit}
html{scroll-padding-top:calc(env(safe-area-inset-top,0px) + 16px)}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--font);font-size:16px;line-height:1.55;font-variant-numeric:tabular-nums}
a{color:var(--accent)} :focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.shell{display:grid;grid-template-columns:232px minmax(0,1fr);max-width:1360px;margin:0 auto}
.rail{position:sticky;top:env(safe-area-inset-top,0px);height:100vh;height:100dvh;padding:28px 18px 28px 24px;border-right:1px solid var(--line);overflow-y:auto}
.rail .brand{font-stretch:112%;font-weight:700;font-size:15px;line-height:1.25;margin:0 0 26px}
.rail .brand span{display:block;font-weight:400;font-stretch:100%;color:var(--ink-3);font-size:13px;margin-top:4px}
.rail ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.rail a{display:grid;grid-template-columns:34px 1fr;align-items:center;gap:10px;text-decoration:none;color:var(--ink-2);padding:6px 6px 6px 0;font-size:14px;line-height:1.25}
.plate{display:inline-grid;place-items:center;width:34px;height:40px;background:var(--muted);color:var(--ink-2);border-radius:2px;font-weight:800;font-stretch:72%;font-size:21px;box-shadow:inset 0 0 0 1px var(--line)}
.rail a[aria-current="true"]{color:var(--ink)} .rail a[aria-current="true"] .plate{background:var(--zinc);color:var(--zinc-ink);box-shadow:none}
.rail .foot{margin-top:28px;font-size:12px;color:var(--ink-3)}
main{padding:0 40px 80px;min-width:0}
.mast{padding:40px 0 30px;border-bottom:1px solid var(--line)}
.mast h1{font-stretch:118%;font-weight:750;font-size:clamp(30px,4.2vw,50px);line-height:1.02;letter-spacing:-0.01em;margin:0 0 14px;max-width:20ch}
.mast p.lede{max-width:68ch;color:var(--ink-2);margin:0;font-size:17px}
section.step{padding:44px 0 10px;border-bottom:1px solid var(--line)}
.step-head{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:start;margin-bottom:18px}
.step-head .plate{width:48px;height:58px;font-size:32px;background:var(--zinc);color:var(--zinc-ink);box-shadow:none}
.step-head h2{font-stretch:112%;font-weight:700;font-size:clamp(23px,2.6vw,30px);line-height:1.12;margin:6px 0 6px}
.step-head p{margin:0;color:var(--ink-2);max-width:72ch}
h3{font-stretch:106%;font-weight:650;font-size:18px;margin:30px 0 8px} h4{font-weight:650;font-size:15px;margin:18px 0 6px}
p{max-width:74ch} .note{font-size:13.5px;color:var(--ink-3);max-width:80ch}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:var(--r-m);background:var(--surface);margin:8px 0 6px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:7px 10px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--line)}
th{font-weight:600;color:var(--ink-2);background:var(--muted);font-size:13px;vertical-align:bottom}
td:first-child,th:first-child{text-align:left} td.l,th.l{text-align:left} tr:last-child td{border-bottom:none}
tbody tr:hover td{background:color-mix(in srgb,var(--accent-soft) 45%,transparent)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}
.pos{color:var(--pos)} .neg{color:var(--neg)}
.controls{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px 26px;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-m);padding:18px 20px;margin:12px 0}
.ctl label{display:flex;justify-content:space-between;gap:10px;font-size:14px;font-weight:600}
.ctl label output{font-weight:700;font-stretch:90%}
.ctl .hint{font-size:12.5px;color:var(--ink-3);margin-top:2px;line-height:1.4}
.ctl input[type=range]{width:100%;accent-color:var(--accent);margin:6px 0 0}
button{font:inherit;font-size:14px;font-weight:600;padding:7px 13px;border-radius:var(--r-s);border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer}
button:hover{border-color:var(--ink-3)}
.eq{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--zinc);border-radius:var(--r-s);padding:12px 16px;margin:10px 0;overflow-x:auto;font-size:15.5px;line-height:1.9;white-space:nowrap}
.eq.eqwrap{white-space:normal;font-size:16px;line-height:2.1}
.eq sub,.eq sup{font-size:.72em}
.chart{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-m);padding:10px 12px;margin:8px 0}
.chart svg{display:block;width:100%;height:auto} .chart .cap{font-size:13px;color:var(--ink-3);margin:4px 2px 0;max-width:none}
svg text{fill:var(--ink-2);font-family:var(--font);font-size:11px}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--ink-2);margin:6px 2px}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--line);border-radius:var(--r-m);background:var(--surface);overflow:hidden;margin-bottom:12px}
.kpis div{padding:12px 16px;border-right:1px solid var(--line)} .kpis div:last-child{border-right:none}
.kpis b{display:block;font-stretch:80%;font-weight:760;font-size:22px;line-height:1.15;white-space:nowrap} .kpis span{font-size:12.5px;color:var(--ink-3)}
.tag{display:inline-block;font-size:10.5px;font-weight:700;border-radius:2px;padding:1px 5px;white-space:nowrap;vertical-align:1px}
.t-s{background:var(--accent-soft);color:var(--accent)} .t-w{background:var(--warn-soft);color:var(--warn)} .t-n{background:var(--muted);color:var(--ink-3)}
.t-p{background:var(--muted);color:var(--pos)} .t-m{background:var(--muted);color:var(--neg)}
.flow{list-style:none;margin:6px 0 10px;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.flow li{display:grid;grid-template-columns:auto 1fr;gap:12px;align-items:start;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-m);padding:12px 14px}
.flow b{display:block;font-size:15px} .flow span:not(.plate){display:block;font-size:13px;color:var(--ink-2);line-height:1.4}
.callout{background:var(--warn-soft);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:var(--r-s);padding:14px 18px;margin:16px 0}
.callout p{margin:0;max-width:78ch} .callout p+p{margin-top:8px}
.srcs{columns:2 300px;column-gap:28px;font-size:13.5px;color:var(--ink-2)}
.srcs li{margin:0 0 7px;break-inside:avoid}
.srcs a{overflow-wrap:anywhere;word-break:break-word}
@media (max-width:620px){ .flow{grid-template-columns:minmax(0,1fr)} }
@media (max-width:980px){
  .shell{grid-template-columns:1fr}
  .rail{position:sticky;top:0;z-index:5;height:auto;padding:10px 14px;border-right:none;border-bottom:1px solid var(--line);background:var(--paper);padding-top:calc(env(safe-area-inset-top,0px) + 10px)}
  .rail .brand,.rail .foot{display:none} .rail ol{flex-direction:row;overflow-x:auto;gap:4px} .rail a{grid-template-columns:auto;padding:0} .rail a .t{display:none}
  .plate{width:30px;height:36px;font-size:19px} main{padding:0 16px 60px} .grid2{grid-template-columns:minmax(0,1fr)} }
@media (max-width:600px){ .kpis{grid-template-columns:minmax(0,1fr)} .kpis div{border-right:none;border-bottom:1px solid var(--line)} .kpis div:last-child{border-bottom:none} .srcs{columns:1} }
@media (prefers-reduced-motion:no-preference){ html{scroll-behavior:smooth} }
"""

JS = """
(function(){
 var S={sec:0.37,phi:0.5,n:20,c:0.05}, r=0.03, m2=1.60, NOISE=__NOISE__, MNOISE=__MNOISE__;
 var ids={cSec:'sec',cPhi:'phi',cN:'n',cC:'c'};
 function fmt(v,d){return (v>=0?'+':'\\u2212')+Math.abs(v).toFixed(d);}
 function calc(){
   var dY=-S.phi*S.sec/100, dV=dY;
   var D=m2/(1+S.c), dc=(S.phi*S.sec/100/S.n)/D;
   var m0=(1+S.c)/(r+S.c), dm=(r-1)/Math.pow(r+S.c,2)*dc, dlnm=dm/m0;
   document.getElementById('kY').textContent=fmt(dY*100,3)+'%';
   document.getElementById('kV').textContent=fmt(dV*100,3)+'%';
   document.getElementById('kM').textContent=fmt(dlnm*100,4)+'%';
   var ratio=NOISE/Math.abs(dY||1e-12);
   var det=Math.abs(dY)>=2.8*NOISE/Math.sqrt(6);
   var k=document.getElementById('kD');
   k.textContent=det?'yes':'no';
   k.style.color=det?'var(--pos)':'var(--neg)';
   document.getElementById('calcNote').innerHTML=
     'The GDP effect is '+ratio.toFixed(0)+'\\u00d7 smaller than a one-year idiosyncratic surprise in real GDP per capita ('
     +(NOISE*100).toFixed(2)+'%). With six treated countries the 80%-power threshold is about '
     +(2.8*NOISE/Math.sqrt(6)*100).toFixed(2)+'%, so this configuration is '
     +(det?'in principle detectable.':'not detectable at annual frequency.')
     +' The multiplier moves by '+(dlnm*100).toFixed(4)+'%, against a credit-multiplier surprise of '
     +(MNOISE*100).toFixed(2)+'% \\u2014 a factor of '+(MNOISE/Math.max(Math.abs(dlnm),1e-12)).toFixed(0)+'.';
 }
 Object.keys(ids).forEach(function(id){
   var el=document.getElementById(id); if(!el) return;
   el.addEventListener('input',function(){
     S[ids[id]]=parseFloat(el.value);
     var o=document.getElementById('o'+id.slice(1));
     if(o) o.textContent=(id==='cN')?el.value:parseFloat(el.value).toFixed(id==='cC'?3:2);
     calc();
   });
 });
 calc();
 var secs=[].slice.call(document.querySelectorAll('section.step')),
     links=[].slice.call(document.querySelectorAll('.rail a'));
 function mark(){
   var y=window.scrollY+140, cur=secs[0];
   secs.forEach(function(s){ if(s.offsetTop<=y) cur=s; });
   links.forEach(function(a){ a.setAttribute('aria-current', a.getAttribute('href')==='#'+cur.id ? 'true':'false'); });
 }
 window.addEventListener('scroll',mark,{passive:true}); mark();
})();
"""

NAV = [("s1", "1", "The question"), ("s2", "2", "The data"),
       ("s3", "3", "Where data is richest"), ("s4", "4", "How big could it be"),
       ("s5", "5", "Panel estimates"), ("s6", "6", "Case by case"),
       ("s7", "7", "What this shows")]

def sec_question():
    nev = len(REG)
    nban = sum(1 for r in REG if r["direction"] == "-1")
    pr = plausibility_rows()
    rr = sorted(float(r[3].replace("&times;", "").replace(",", ""))
                for r in pr if r[3] != "&mdash;")
    nwrong = sum(1 for r in pr if "wrong sign" in r[4])
    nbig = sum(1 for x in rr if x > 5)
    callout_ratio = (
        f"Of the {len(pr)} panel estimates below, {nwrong} carry the wrong sign and "
        f"{nbig} are more than five times the largest effect the trade could produce "
        f"if it vanished entirely &mdash; the worst by a factor of {rr[-1]:,.0f}. The two "
        f"synthetic controls that reach p &lt; 0.05 both collapse once the comparison "
        f"group is tightened. Those are confounds &mdash; the dot-com cycle, the "
        f"financial crisis, euro convergence &mdash; not prostitution policy."
        if rr else "")
    return f"""
<section class="step" id="s1"><div class="step-head"><span class="plate">1</span><div>
<h2>The question, and the chain it has to travel down</h2>
<p>Banning or re-legalising prostitution is supposed to do something to the
economy. The claim is usually about money moving faster or slower, not just
about output. So the test has to follow a chain, and each link has a sign
attached before any data is touched.</p>
</div></div>
<ul class="flow">
<li><span class="plate">&darr;</span><span><b>Output</b><span>A ban suppresses
part of a measured sector, or pushes it out of the accounts. Measured GDP falls
by the suppressed share. A reinstatement does the reverse, and can raise GDP
purely by making activity observable.</span></span></li>
<li><span class="plate">&darr;</span><span><b>Velocity</b><span>V = PY/M. The
central bank sets M, so a fall in measured Y is a fall in measured V of the same
proportion. Bans should <i>lower</i> velocity; legalisation should raise it.</span></span></li>
<li><span class="plate">&darr;</span><span><b>Multiplier</b><span>A banned trade
settles in cash. Currency leaves deposits, the currency-to-deposit ratio rises,
and m = (1+c)/(r+c) falls because &part;m/&part;c &lt; 0. Bans should lower the
multiplier.</span></span></li>
</ul>
<p>So the pre-registered prediction is a clean set of signs: <b>ban &rarr; GDP
down, velocity down, multiplier down</b>; <b>reinstatement &rarr; all three
up</b>. An estimate with the wrong sign, or one many times larger than the
sector could mechanically supply, is evidence of confounding rather than of
effect &mdash; and that turns out to be the whole story.</p>
<div class="callout">
<p><b>What the exercise actually establishes.</b> {nev} dated reforms across
{len({r["iso3"] for r in REG})} jurisdictions, 1999&ndash;2022, {nban} of them
bans. The United Kingdom has the most abundant data by a clear margin. And the
answer to the headline question is a bound rather than a discovery: outside South
Korea the sector is one to three orders of magnitude too small to show up in
annual GDP, velocity or multiplier data, and the currency-drain channel into the
multiplier is undetectable even in Korea.</p>
<p>{callout_ratio}</p>
</div>
</section>"""

def plausibility_rows():
    """|estimate| vs the largest mechanical effect possible (phi = 1)."""
    shares = {c["iso3"]: c["sector_pct_gdp"] for c in ARI.get("cases", [])}
    fallback = {r["iso3"]: float(r["sector_share_gdp_pct"]) for r in ABU} if ABU else {}
    rows = []
    def maxmech(isos):
        v = [shares.get(i, fallback.get(i)) for i in isos]
        v = [x for x in v if x]
        return (np.mean(v) / 100.0) if v else None
    for arm in ("ban", "lib"):
        for o in OUTCOMES_ORDER:
            key = f"{arm}|{o}|all"
            cs, ri = RES.get("cs", {}).get(key), RES.get("ri", {}).get(key, {})
            samp = RES.get("samples", {}).get(key, {})
            if not cs or cs.get("att_post") is None: continue
            mm = maxmech(samp.get("treated", []))
            att = cs["att_post"]
            ratio = abs(att) / mm if mm else None
            # sign the mechanical bound: a ban lowers output, velocity, the
            # multiplier and money growth, and raises prices (MV = PY with Y
            # falling).  A reinstatement reverses all of it.
            up_with_output = o != "infl_rate"
            want = (-1 if arm == "ban" else 1) * (1 if up_with_output else -1)
            signok = (np.sign(att) == want)
            if ratio is None:
                verdict = '<span class="tag t-n">&mdash;</span>'
            elif not signok:
                verdict = '<span class="tag t-m">wrong sign</span>'
            elif ratio > 5:
                verdict = '<span class="tag t-w">right sign, implausible scale</span>'
            else:
                verdict = '<span class="tag t-p">consistent in scale</span>'
            rows.append([ARMLAB[arm].split(" (")[0] + " &middot; " + OUTLAB[o],
                         f2(att, 2, pct=True, sign=True),
                         f2(mm * want, 2, pct=True, sign=True) if mm else "&mdash;",
                         (f'{ratio:,.0f}&times;' if ratio >= 10 else f'{ratio:,.1f}&times;')
                         if ratio else "&mdash;",
                         verdict,
                         ("%.3f" % ri["p_two_sided"]) if ri.get("p_two_sided") is not None else "&mdash;"])
    return rows

def sec_verdict():
    rows = plausibility_rows()
    _cs = RES.get("cs", {}).get("ban|ln_velocity|all", {})
    _bv = _cs.get("att_post")
    _sh = [c["sector_pct_gdp"] for c in ARI.get("cases", [])
           if c["iso3"] in RES.get("samples", {}).get("ban|ln_velocity|all", {}).get("treated", [])]
    velsent = (
        f"A velocity estimate of {_bv*100:+.1f}% after a ban, when the trade in those "
        f"countries averages {np.mean(_sh):.2f}% of GDP and so can account for at most "
        f"that much even if it vanished outright, is not a finding about prostitution."
        if _bv is not None and _sh else
        "An estimate many times the size of the sector is not a finding about prostitution.")
    t = table(["Arm &middot; outcome", "Estimate", "Max mechanical (&phi;=1)",
               "Estimate / max", "Verdict", "RI p"], rows)
    nwrong = sum(1 for r in rows if "wrong sign" in r[4])
    nbig = sum(1 for r in rows if "implausible scale" in r[4])
    srcs = sorted({r["source"] for r in REG} | {m["source"] for m in MEA})
    li = "".join(f'<li><a href="{e(u)}">{e(u.split("//")[-1][:78])}</a></li>' for u in srcs)
    return f"""
<section class="step" id="s7"><div class="step-head"><span class="plate">7</span><div>
<h2>What this shows, and what it cannot</h2>
<p>The plausibility test: compare each estimate with the largest effect the
sector could produce if a ban eliminated it entirely (&phi; = 1).</p>
</div></div>
{t}
<p>{nwrong} of the {len(rows)} panel estimates carry the <i>opposite</i> sign to
the mechanism and a further {nbig} have the right sign but a magnitude the sector
cannot supply. {velsent} It is what a
seven-country treatment group looks like when the events cluster around
1999&ndash;2010 &mdash; euro convergence, the dot-com cycle, the financial crisis.</p>
<h3>Four things that genuinely limit this</h3>
<ul>
<li><b>No national money for the euro area.</b> Monetary union erased the
national broad-money series, so the Netherlands 2000, Germany 2002 and 2017,
France 2016 and Ireland 2017 cannot be tested on velocity or the multiplier at
all. Canada drops out too &mdash; its broad-money series ends in 2008, six years
before PCEPA.</li>
<li><b>No monetary base anywhere.</b> The textbook m = M2/M0 is not
constructible from any source reachable here, so the multiplier is approached
through two ratio proxies and the analytic formula. The reserve ratio exists only
from 2001, which leaves the 2004 Korean ban with three pre-years.</li>
<li><b>The reinstatement arm rests on three countries.</b> Denmark 1999, Hungary
1999 and New Zealand 2003 are the only liberalisations with both GDP and money
data. One of the credit-multiplier cells is identified off two countries and
returns +80%, which is best read as a warning label rather than a result.</li>
<li><b>Annual data, and a measurement problem inside the outcome.</b> The thing
being banned is partly <i>defined</i> by whether statisticians count it. The UK
and the Netherlands differ fivefold in their estimates of the same sector under
the same ESA 2010 obligation, so part of any measured GDP movement around a
reform is the accounting treatment changing, not behaviour.</li>
</ul>
<h3>What would actually settle it</h3>
<p>Not more countries &mdash; more frequency and more locality. Korea is the only
place where the shock is big enough to see, and the test it deserves is quarterly
or monthly: Bank of Korea M1, M2 and base money, currency in circulation, and the
2004 break. Below that, the right design is sub-national and sector-specific:
Rhode Island's 2003&ndash;2009 window against other US states on county business
patterns, and Northern Ireland against Great Britain on regional GVA, both of
which the ONS and BEA publish. Those sources are blocked by this
environment's network policy; with them the same code would run on data that
can actually carry the question.</p>
<h3>Sources</h3>
<ul class="srcs">{li}</ul>
</section>"""

def main():
    nav = "".join(f'<li><a href="#{i}"><span class="plate">{n}</span>'
                  f'<span class="t">{e(t)}</span></a></li>' for i, n, t in NAV)
    noise = ARI.get("noise", {}).get("gdppc_con", {}).get("sd_advanced") or 0.0325
    body = (sec_question() + sec_data() + sec_abundance() + sec_arithmetic()
            + sec_estimates() + sec_cases() + sec_verdict())
    mnoise = ARI.get("noise", {}).get("mult_credit", {}).get("sd_advanced") or 0.0823
    JSOUT = (JS.replace("__NOISE__", f"{noise:.6f}")
               .replace("__MNOISE__", f"{mnoise:.6f}"))
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Prostitution bans and the macroeconomy</title>
<meta name="description" content="Testing whether banning or re-legalising prostitution moves GDP, the velocity of money or the money multiplier, across 20 dated reforms in 1960-2020 macro data.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,300..800&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="shell">
<nav class="rail" aria-label="Sections">
  <p class="brand">Prostitution bans and the macroeconomy<span>GDP, velocity, multiplier &middot; 20 reforms, 214 countries, 1960&ndash;2020</span></p>
  <ol>{nav}</ol>
  <p class="foot">Built from World Bank WDI and hand-sourced legal and
  statistical records. Every figure traceable to a URL in <code>data/</code>.</p>
</nav>
<main>
<header class="mast">
<h1>Does banning prostitution move the money?</h1>
<p class="lede">Twenty dated reforms, 1999&ndash;2022, against 214 countries of
annual macro data. The United Kingdom has the richest data; South Korea has the
only shock big enough to see. The answer is a bound, not a discovery &mdash; and
the bound is tight enough to be worth having.</p>
</header>
{body}
</main>
</div>
<script>{JSOUT}</script>
</body>
</html>"""
    out = os.path.join(ROOT, "prostitution_macro_v1.html")
    with open(out, "w") as f:
        f.write(doc)
    print(f"wrote {out}  ({len(doc):,} bytes)")

if __name__ == "__main__":
    main()
