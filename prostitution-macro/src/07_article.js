// Builds the academic article as a .docx.
// Numbers are read from out/*.json so nothing is transcribed by hand.
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  PageNumber, Footer, ImageRun, PageBreak, LevelFormat, convertInchesToTwip,
} = require('docx');

const ROOT = path.resolve(__dirname, '..');
const J = (f) => JSON.parse(fs.readFileSync(path.join(ROOT, 'out', f), 'utf8'));
const R = J('results.json'), A = J('arithmetic.json'), AB = J('abundance.json');

function csv(file) {
  const txt = fs.readFileSync(path.join(ROOT, 'data', file), 'utf8').trim();
  const rows = [];
  let cur = [''], q = false;
  for (let i = 0; i < txt.length; i++) {
    const c = txt[i];
    if (q) {
      if (c === '"' && txt[i + 1] === '"') { cur[cur.length - 1] += '"'; i++; }
      else if (c === '"') q = false;
      else cur[cur.length - 1] += c;
    } else if (c === '"') q = true;
    else if (c === ',') cur.push('');
    else if (c === '\n') { rows.push(cur); cur = ['']; }
    else if (c !== '\r') cur[cur.length - 1] += c;
  }
  rows.push(cur);
  const head = rows.shift();
  return rows.filter(r => r.length > 1).map(r =>
    Object.fromEntries(head.map((h, i) => [h.trim(), (r[i] ?? '').trim()])));
}
const REG = csv('regimes.csv'), MEA = csv('prostitution_measures.csv');

// ---------------------------------------------------------------- numbers
const pct = (x, d = 2) => (x === null || x === undefined || !isFinite(x))
  ? '—' : (x * 100).toFixed(d) + '%';
const spct = (x, d = 2) => (x === null || x === undefined || !isFinite(x))
  ? '—' : (x >= 0 ? '+' : '−') + Math.abs(x * 100).toFixed(d) + '%';
const num = (x, d = 2) => (x === null || x === undefined || !isFinite(x))
  ? '—' : x.toFixed(d);

const CONTENT_W = 9360;                 // Letter, 1" margins, in DXA
const noiseY = A.noise.gdppc_con.sd_advanced;
const noiseV = A.noise.velocity.sd_advanced;
const noiseM = A.noise.mult_credit.sd_advanced;
const caseOf = (iso) => A.cases.find(c => c.iso3 === iso);
const gbr = caseOf('GBR'), kor = caseOf('KOR');
const top = AB[0], second = AB[1];

const OUTLAB = {
  ln_rgdp_pc: 'Real GDP per capita',
  ln_velocity: 'Velocity of broad money',
  ln_mult_credit: 'Credit multiplier',
  ln_mult_liq: 'Bank liquidity multiplier',
  infl_rate: 'CPI inflation',
  m2_growth_rate: 'Broad money growth',
};
const ORDER = ['ln_rgdp_pc', 'ln_velocity', 'ln_mult_credit', 'ln_mult_liq',
  'infl_rate', 'm2_growth_rate'];
const ARM = { ban: 'Ban', lib: 'Reinstatement' };

// mean sector share across a treated set
function maxMech(isos) {
  const v = isos.map(i => {
    const c = caseOf(i);
    if (c) return c.sector_pct_gdp;
    const a = AB.find(x => x.iso3 === i);
    return a ? a.sector_share_gdp_pct : null;
  }).filter(x => x !== null && x !== undefined);
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length / 100 : null;
}

const panelRows = [];
for (const arm of ['ban', 'lib']) {
  for (const o of ORDER) {
    const k = `${arm}|${o}|all`;
    const cs = R.cs[k], ri = R.ri[k] || {}, s = R.samples[k] || {}, pw = R.power[k] || {};
    if (!cs || cs.att_post === null || cs.att_post === undefined) continue;
    const mm = maxMech(s.treated || []);
    const upWithOutput = o !== 'infl_rate';
    const want = (arm === 'ban' ? -1 : 1) * (upWithOutput ? 1 : -1);
    const ok = Math.sign(cs.att_post) === want;
    const ratio = mm ? Math.abs(cs.att_post) / mm : null;
    panelRows.push({ arm, o, k, cs, ri, s, pw, mm, want, ok, ratio });
  }
}
const nWrong = panelRows.filter(r => !r.ok).length;
const nBig = panelRows.filter(r => r.ratio !== null && r.ratio > 5).length;
const nSig = panelRows.filter(r => r.ri.p_two_sided !== null &&
  r.ri.p_two_sided !== undefined && r.ri.p_two_sided < 0.05).length;
const maxRatio = Math.max(...panelRows.map(r => r.ratio || 0));
const nBans = REG.filter(r => r.direction === '-1').length;
const nLibs = REG.filter(r => r.direction === '1').length;
const nJur = new Set(REG.map(r => r.jurisdiction)).size;

// ---------------------------------------------------------------- styling
const SERIF = 'Times New Roman';
const p = (text, o = {}) => new Paragraph({
  alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { line: o.line || 320, before: o.before ?? 0, after: o.after ?? 140 },
  indent: o.indent,
  children: (Array.isArray(text) ? text : [text]).map(t =>
    typeof t === 'string'
      ? new TextRun({ text: t, font: SERIF, size: o.size || 22, italics: o.italics, bold: o.bold })
      : t),
});
const run = (t, o = {}) => new TextRun({
  text: t, font: SERIF, size: o.size || 22,
  bold: o.bold, italics: o.italics, superScript: o.sup, subScript: o.sub,
});
const h1 = (t) => new Paragraph({
  heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 150 },
  children: [new TextRun({ text: t, font: SERIF, size: 26, bold: true, color: '000000' })],
});
const h2 = (t) => new Paragraph({
  heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 110 },
  children: [new TextRun({ text: t, font: SERIF, size: 23, bold: true, color: '000000' })],
});
const cap = (t) => new Paragraph({
  spacing: { before: 140, after: 70 }, alignment: AlignmentType.LEFT,
  children: [new TextRun({ text: t, font: SERIF, size: 19 })],
});
const note = (t) => new Paragraph({
  spacing: { before: 60, after: 190 }, alignment: AlignmentType.JUSTIFIED,
  children: [new TextRun({ text: t, font: SERIF, size: 18 })],
});

const NB = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const LINE = { style: BorderStyle.SINGLE, size: 4, color: '000000' };
const THIN = { style: BorderStyle.SINGLE, size: 2, color: '888888' };

function cell(text, w, o = {}) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    margins: { top: 50, bottom: 50, left: 70, right: 70 },
    borders: {
      top: o.top || NB, bottom: o.bottom || NB, left: NB, right: NB,
    },
    shading: o.shade ? { type: ShadingType.CLEAR, fill: o.shade, color: 'auto' } : undefined,
    children: [new Paragraph({
      alignment: o.align || (o.left ? AlignmentType.LEFT : AlignmentType.RIGHT),
      spacing: { before: 0, after: 0, line: 240 },
      children: [new TextRun({
        text: String(text), font: SERIF, size: o.size || 18,
        bold: o.bold, italics: o.italics,
      })],
    })],
  });
}

/** head: array of strings; rows: array of arrays; widths: DXA summing to CONTENT_W */
function table(head, rows, widths, opt = {}) {
  const leftCols = opt.leftCols ?? 1;
  const trs = [];
  trs.push(new TableRow({
    tableHeader: true, cantSplit: true,
    children: head.map((h, i) => cell(h, widths[i], {
      bold: true, left: i < leftCols, top: LINE, bottom: THIN,
    })),
  }));
  rows.forEach((r, ri) => {
    const last = ri === rows.length - 1;
    trs.push(new TableRow({
      cantSplit: true,
      children: r.map((c, i) => cell(c, widths[i], {
        left: i < leftCols, bottom: last ? LINE : NB,
        italics: opt.italicRows && opt.italicRows.includes(ri),
      })),
    }));
  });
  return new Table({
    columnWidths: widths,
    width: { size: CONTENT_W, type: WidthType.DXA },
    rows: trs,
  });
}

function figure(file, capText) {
  const buf = fs.readFileSync(path.join(ROOT, 'out', 'fig', file));
  // native widths are 6.3-6.6in at 300dpi; scale to 6.2in
  const wIn = 6.2, hIn = file.includes('fig1') ? 2.95 : 2.75;
  // A one-cell borderless table with cantSplit keeps the plate and its caption
  // on the same page; keepNext alone is not honoured by every renderer.
  return [new Table({
    columnWidths: [CONTENT_W],
    width: { size: CONTENT_W, type: WidthType.DXA },
    rows: [new TableRow({
      cantSplit: true,
      children: [new TableCell({
        width: { size: CONTENT_W, type: WidthType.DXA },
        margins: { top: 120, bottom: 160, left: 0, right: 0 },
        borders: { top: NB, bottom: NB, left: NB, right: NB },
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER, spacing: { before: 0, after: 90 },
            children: [new ImageRun({
              type: 'png', data: buf,
              transformation: { width: wIn * 96, height: hIn * 96 },
            })],
          }),
          new Paragraph({
            alignment: AlignmentType.LEFT, spacing: { before: 0, after: 0 },
            children: [new TextRun({ text: capText, font: SERIF, size: 18 })],
          }),
        ],
      })],
    })],
  })];
}

// ================================================================= content
const body = [];

// ---- title block
body.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 400, after: 120 },
  children: [new TextRun({
    text: 'Can a Prostitution Ban Move the Money?',
    font: SERIF, size: 34, bold: true,
  })],
}));
body.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { after: 320 },
  children: [new TextRun({
    text: 'Output, Velocity and the Money Multiplier around Twenty Legal Regime Changes, 1999–2022',
    font: SERIF, size: 26,
  })],
}));
body.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { after: 60 },
  children: [new TextRun({ text: '[Author]', font: SERIF, size: 22 })],
}));
body.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { after: 360 },
  children: [new TextRun({ text: '[Affiliation]  ·  This version: 1 November 2026', font: SERIF, size: 20 })],
}));

body.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { after: 120 },
  children: [new TextRun({ text: 'Abstract', font: SERIF, size: 22, bold: true })],
}));
body.push(new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  indent: { left: convertInchesToTwip(0.5), right: convertInchesToTwip(0.5) },
  spacing: { line: 280, after: 200 },
  children: [new TextRun({
    text: `Advocates and opponents of prostitution law reform both make macroeconomic claims, usually about money circulating faster or more slowly rather than about output alone. This paper tests those claims directly. I assemble ${REG.length} dated changes in prostitution law across ${nJur} jurisdictions between 1999 and 2022 (${nBans} prohibitions or tightenings, ${nLibs} legalisations or decriminalisations) and merge them with a ${R.meta.n_countries}-country annual macroeconomic panel for ${R.meta.years[0]}–${R.meta.years[1]}. Because the exercise needs a measured sector, a dated reform, and national monetary aggregates simultaneously, I first rank jurisdictions on a transparent data-abundance index; the United Kingdom scores highest, South Korea carries by far the largest shock. The central result is established before any regression. A prohibition that suppressed half of the United Kingdom's measured prostitution sector would move GDP by ${pct(Math.abs(gbr.channels.phi50.dln_gdp), 3)}, against a ${pct(noiseY, 2)} standard deviation of the annual idiosyncratic surprise in real GDP per capita among advanced economies; the currency-drain channel into the money multiplier is one to two orders of magnitude smaller still, in every jurisdiction including Korea. Estimation confirms what that arithmetic implies. Across ${panelRows.length} outcome-by-direction combinations, using two-way fixed-effects event studies and the Callaway–Sant'Anna group-time estimator with not-yet-treated comparisons, ${panelRows.length - nSig} are statistically indistinguishable from zero under randomization inference; the single exception rests on two countries and is ${maxRatio.toFixed(0)} times larger than the sector could produce if it vanished outright. ${nWrong} of ${panelRows.length} point estimates carry the sign opposite to the mechanism. Both synthetic controls attaining conventional significance collapse when the donor pool is tightened. The contribution is therefore a bound rather than a discovery, and the bound is informative: effects of the magnitude this sector can generate are undetectable in annual macroeconomic data, and any detectable effect must originate elsewhere.`,
    font: SERIF, size: 20,
  })],
}));
body.push(new Paragraph({
  indent: { left: convertInchesToTwip(0.5), right: convertInchesToTwip(0.5) },
  spacing: { after: 80 },
  children: [run('Keywords: ', { size: 20, bold: true }),
    run('prostitution policy; informal economy; national accounts; velocity of money; money multiplier; difference-in-differences; statistical power.', { size: 20 })],
}));
body.push(new Paragraph({
  indent: { left: convertInchesToTwip(0.5), right: convertInchesToTwip(0.5) },
  spacing: { after: 200 },
  children: [run('JEL codes: ', { size: 20, bold: true }),
    run('E41, E26, K42, C23, O17.', { size: 20 })],
}));
body.push(new Paragraph({ children: [new PageBreak()] }));

// ---- 1 Introduction
body.push(h1('1. Introduction'));
body.push(p(`Prostitution law changes often, and the arguments made for and against change are frequently economic. Prohibition is said to shrink a market; legalisation is said to bring one into the daylight, onto tax rolls and into the national accounts. A recurring and more specific claim concerns money rather than output: that a banned trade is a cash trade, that cash drains from the banking system, and that the circulation of money slows as a result. These are testable propositions about velocity and the money multiplier, not merely about gross domestic product, and they have not to my knowledge been tested.`));
body.push(p(`This paper tests them. The research design is conventional — a staggered difference-in-differences panel with event-study dynamics, supplemented by synthetic controls — but the paper's organising decision is unconventional in one respect: the magnitudes are computed before the estimates. Prostitution is a small sector almost everywhere it is measured. If a reform cannot plausibly move the outcome by more than a few hundredths of a percentage point, and the outcome's own annual variability is several percentage points, then the econometrics cannot settle the question whatever it returns, and a null result carries no information unless it is accompanied by the bound that generated it.`));
body.push(p(`Three contributions follow. First, I assemble and publish a dated panel of prostitution regime changes with sources, together with every quantitative measurement of sector size I could locate from official statistical agencies. Second, I propose a data-abundance index that makes explicit the fact that answering this question requires several kinds of data at once, and I use it to select the jurisdictions on which the question can be asked at all. Third, I report the test and, more usefully, the minimum effect it could have detected — which turns out to exceed the maximum effect the sector could supply by one to three orders of magnitude.`));
body.push(p(`The negative result is not a failure of the design but a property of the object. It also has a constructive corollary. Because the arithmetic locates precisely where the question becomes answerable — a large sector, a sharp reform, high-frequency monetary data — it identifies the research designs that would work: South Korea's 2004 prohibition at monthly or quarterly frequency, and sub-national natural experiments such as Rhode Island's accidental decriminalisation between 2003 and 2009 or the Northern Ireland sex-purchase offence of 2015, both of which sit inside statistical systems that publish regional and county detail.`));

// ---- 2 Background
body.push(h1('2. Background and related literature'));
body.push(p(`The economics of prostitution has an established microeconomic literature. Edlund and Korn (2002) model the wage premium in commercial sex as compensation for forgone marriage-market prospects. Gertler, Shah and Bertozzi (2005) estimate the price of unprotected sex. Cunningham and Shah (2018) exploit Rhode Island's inadvertent decriminalisation of indoor prostitution to show reductions in reported rape and in gonorrhoea incidence. Bisschop, Kastoryano and van der Klaauw (2017) find that opening designated street prostitution zones in Dutch cities reduced sexual abuse and rape. A parallel literature studies the relationship between legal regime and human trafficking, with Cho, Dreher and Neumayer (2013) and Jakobsson and Kotsadam (2013) reporting that legalisation is associated with larger reported inflows, and Lee and Persson (2022) providing a theoretical account of why voluntary and coerced supply may not be substitutes.`));
body.push(p(`What this literature does not contain is a macroeconomic evaluation. That gap is partly explained by measurement. Until recently most national accounts simply excluded the sector. The European System of Accounts 2010 changed this for the European Union by requiring member states to include illegal but consensual production, and from September 2014 prostitution entered official GDP across the Union. The Office for National Statistics (2014) documented the United Kingdom's implementation and published a prostitution series back to 1997; Statistics Netherlands (2024) describes the Dutch estimates. In the United States, by contrast, Soloveichik (2021) produced estimates of illegal prostitution expenditure from 1965 in a research satellite account that remains outside headline GDP.`));
body.push(p(`The monetary side of the claim connects to an older literature on currency demand and the shadow economy, in which the ratio of currency to deposits is used to infer unobserved activity (Schneider and Enste, 2000) and in which cash is understood as the settlement medium of choice for transactions that participants wish to keep unobserved (Rogoff, 2016). The mechanism is standard: if a prohibition drives a trade into cash, the currency-to-deposit ratio rises and the money multiplier falls. The question this paper asks is whether the sector is large enough for that mechanism to register.`));

// ---- 3 Framework
body.push(h1('3. Conceptual framework'));
body.push(p(`Let the sector's gross output be a share ${'s'} of GDP and let a reform suppress a fraction φ of it. Three channels follow, each with a signed prediction fixed before estimation.`));
body.push(h2('3.1 Output'));
body.push(p(`Measured output falls one-for-one with the suppressed share:`));
body.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 100, after: 100 },
  children: [run('Δ ln Y = − φ · s', { italics: true, size: 23 }), run('     (1)', { size: 20 })],
}));
body.push(p(`A reinstatement reverses the sign and may, in addition, raise measured GDP mechanically rather than behaviourally, by moving activity from the unobserved to the observed economy. This accounting channel is neutralised within the European Union after 2014, when illegal production entered the accounts whatever its legal status, but it is live for reforms before that date.`));
body.push(h2('3.2 Velocity'));
body.push(p(`With velocity defined from the quantity identity as V = PY/M, and with the money stock set by the central bank rather than by the sex trade, a first-order change in measured output passes straight through:`));
body.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 100, after: 100 },
  children: [run('Δ ln V ≈ Δ ln Y = − φ · s', { italics: true, size: 23 }), run('     (2)', { size: 20 })],
}));
body.push(p(`Prohibition should therefore lower measured velocity and liberalisation should raise it. Because MV = PY is an identity, the adjustment must also appear in prices or in money growth if it appears at all, which is why inflation and broad money growth are carried as outcomes alongside velocity.`));
body.push(h2('3.3 The money multiplier'));
body.push(p(`The multiplier channel runs through a different door. Writing c for the currency-to-deposit ratio and r for reserves to deposits, with M2 = C + D and the monetary base MB = C + R, the textbook multiplier and its derivative are`));
body.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 100, after: 100 },
  children: [run('m = (1 + c)/(r + c),     ∂m/∂c = (r − 1)/(r + c)² < 0', { italics: true, size: 23 }), run('     (3)', { size: 20 })],
}));
body.push(p(`A prohibition that pushes the trade into cash raises c and therefore lowers m. If the suppressed turnover is φ·T and a unit of currency is re-spent n times a year, the additional currency that must be held is φ·T/n, so Δc = (φ·T/n)/D. Since prostitution is close to a pure labour service, gross output is a reasonable proxy for turnover, and T ≈ s·GDP.`));
body.push(p(`The pre-registered prediction is thus a clean triplet: prohibition lowers output, velocity and the multiplier and raises prices; reinstatement reverses all four. An estimate bearing the wrong sign, or one far larger than the sector can mechanically supply, is evidence of confounding rather than of effect.`));

// ---- 4 Data
body.push(h1('4. Data'));
body.push(h2('4.1 Legal regime changes'));
body.push(p(`I compiled ${REG.length} dated changes in prostitution law between 1999 and 2022 across ${nJur} jurisdictions, ${nBans} of them prohibitions or tightenings and ${nLibs} legalisations, decriminalisations or formal regulation. Each is recorded with its in-force date, the instrument, and a source; the full list appears in Appendix Table A1. ${REG.filter(r => r.level === 'national').length} are national and three are sub-national: the Northern Ireland sex-purchase offence of 1 June 2015, and the two Rhode Island events that bracket the de facto decriminalisation of indoor prostitution between 2003 and 2009.`));
body.push(p(`Coding the date of a reform is not always straightforward, and I use the date on which the operative provision came into force rather than the date of passage. Israel is the clearest case: the statute was adopted on 31 December 2018, published on 10 January 2019 and came into force on 10 July 2020, which leaves it with no post-reform years inside the estimation window.`));
body.push(h2('4.2 Measurement of the sector'));
body.push(p(`Appendix Table A2 lists every quantitative measurement of sector size I could source. Two features deserve emphasis. First, the dispersion across statistical agencies is large: the ONS places UK prostitution at roughly ${gbr.sector_pct_gdp.toFixed(2)}% of GDP while Statistics Netherlands places the Dutch sector at about 0.08%, a fivefold divergence between two neighbouring agencies working under the same ESA 2010 obligation. Part of any measured movement in GDP around a reform is therefore the accounting treatment changing rather than behaviour. Second, South Korea is an outlier by two orders of magnitude: the Korean Institute of Criminology put the 2002 sex trade at 24 trillion won, approximately ${kor.sector_pct_gdp.toFixed(1)}% of GDP, and the Korea Women's Development Institute reported 14 trillion won for 2007, with transactions falling from 170 million to 94 million over the same period.`));
body.push(h2('4.3 Macroeconomic panel'));
body.push(p(`Macroeconomic series come from the World Bank's World Development Indicators for ${R.meta.years[0]}–${R.meta.years[1]}, covering ${R.meta.n_countries} countries: GDP in current and constant local currency, GDP per capita, the GDP deflator, broad money in current local currency and as a share of GDP, the ratio of bank liquid reserves to bank assets, domestic credit to the private sector, net domestic credit and consumer prices. Velocity is constructed as nominal GDP divided by broad money. Two multiplier proxies are used: a credit multiplier, private credit divided by broad money, and a bank liquidity multiplier, the inverse of the liquid-reserves-to-assets ratio.`));
body.push(p(`The textbook M2/M0 multiplier cannot be constructed here, because no reachable source carries monetary base or M1 for a country panel. This is a genuine limitation and the paper is explicit about it: equation (3) is evaluated analytically using the reserve ratio observed in the data and a parameterised currency ratio, while the two observable ratios serve as the empirical multiplier outcomes.`));
body.push(h2('4.4 A data-abundance index'));
body.push(p(`The question requires four things at once: a measured sector (L1), a reform that is testable in the sense of having at least three years either side within the window and a money stock that exists over it (L2), monetary aggregates (L3), and national accounts (L4). A jurisdiction lacking any one of them cannot answer the question, so the composite is the geometric mean of the four normalised legs, which a zero on any leg drives to zero. Table 1 reports the ranking.`));

body.push(cap('Table 1. Data-abundance index, leading jurisdictions.'));
body.push(table(
  ['Jurisdiction', 'Score', 'L1', 'L2', 'L3', 'L4', 'Official yrs', 'Sector, % GDP', 'Velocity yrs'],
  AB.slice(0, 10).map(r => [
    `${r.rank}. ${r.jurisdiction}`, num(r.score_geometric, 3), num(r.L1_measurement, 2),
    num(r.L2_events, 2), num(r.L3_money, 2), num(r.L4_accounts, 2),
    String(r.official_output_years), r.sector_share_gdp_pct.toFixed(2), String(r.velocity_years),
  ]),
  [2100, 820, 720, 720, 720, 720, 1180, 1300, 1080]));
body.push(note(`Notes: Geometric mean of four normalised legs — L1 measured sector, L2 testable reforms, L3 monetary aggregates, L4 national accounts. "Official yrs" counts years for which a statistical agency publishes a prostitution-specific output figure. Full table in the replication materials.`));

body.push(p(`The United Kingdom ranks first at ${num(top.score_geometric, 3)}, and is the only jurisdiction strong on all four legs: ${top.official_output_years} years of prostitution output inside official GDP, a national reform in 2010, a within-country reform in Northern Ireland in 2015 that leaves Great Britain as a control group, and ${top.velocity_years} unbroken years of its own broad money. The United States ranks second at ${num(second.score_geometric, 3)} and wins the measurement leg outright with ${second.official_output_years} years of BEA estimates, but those sit in a satellite account rather than in GDP, the sector is measured at only ${second.sector_share_gdp_pct.toFixed(2)}% of GDP, and there has never been a national reform to test. South Korea ranks fourth yet matters more than its rank implies, because its sector is the only one large enough to give the question any statistical power.`));
body.push(p(`Euro-area members cluster at the bottom, and not because their prostitution data is poor — the Netherlands and Italy publish more of it than most. Monetary union erased their national money stocks, so their velocity and multiplier legs are exactly zero. This removes the Netherlands 2000 brothel-ban repeal, Germany 2002 and 2017, France 2016 and Ireland 2017 from every monetary test. Canada is lost for a different reason: its broad-money series ends in 2008, six years before the Protection of Communities and Exploited Persons Act.`));

// ---- 5 Magnitude
body.push(h1('5. The magnitude problem'));
body.push(p(`Table 2 evaluates equations (1) to (3) at φ = 0.5, c = 0.05 and n = 20, using the observed reserve ratio and broad-money share for each jurisdiction in its reform year. The final column divides the standard deviation of a one-year idiosyncratic surprise in real GDP per capita among advanced economies, ${pct(noiseY, 2)} after removing the common year effect, by the mechanical effect.`));

body.push(cap('Table 2. Mechanical effect of suppressing half the measured sector, against the noise floor.'));
body.push(table(
  ['Jurisdiction', 'Reform', 'Sector, % GDP', 'M2/GDP', 'V', 'r', 'Δ ln Y', 'Δ ln V', 'Δ ln m', 'Noise/signal'],
  A.cases.map(c => {
    const ch = c.channels.phi50, dm = ch.multiplier['c0.05|n20'];
    return [c.jurisdiction, String(c.event_year), c.sector_pct_gdp.toFixed(2),
      (c.m2_pct_gdp).toFixed(0) + '%', c.velocity.toFixed(3),
      (c.reserve_ratio * 100).toFixed(1) + '%',
      ch.dln_gdp_pct.toFixed(3) + '%', ch.dln_velocity_pct.toFixed(3) + '%',
      dm ? (dm.dln_m * 100).toFixed(4) + '%' : '—',
      (noiseY * 100 / Math.abs(ch.dln_gdp_pct)).toFixed(0) + '×'];
  }),
  [1500, 760, 1050, 820, 700, 640, 860, 860, 980, 1190]));
body.push(note(`Notes: Δ ln m evaluated at c = 0.05, n = 20. r is the WDI ratio of bank liquid reserves to bank assets in the reform year where reported; the United Kingdom and New Zealand do not report it, so the advanced-economy median for that year is substituted. Noise is ${pct(noiseY, 2)} for real GDP per capita, ${pct(noiseV, 2)} for velocity and ${pct(noiseM, 2)} for the credit multiplier.`));

body.push(...figure('fig1_signal_noise.png',
  `Figure 1. Mechanical effect of suppressing half the measured prostitution sector, against the one-year idiosyncratic surprise in real GDP per capita. Log scale; the right-hand annotation is the ratio of noise to signal.`));

body.push(p(`The result is stark and it does not depend on any econometric choice. For the United Kingdom the noise is ${(noiseY * 100 / Math.abs(gbr.channels.phi50.dln_gdp_pct)).toFixed(0)} times the signal; for the Nordic cases it is ${(noiseY * 100 / 0.05).toFixed(0)} times. South Korea is the only jurisdiction where the ratio falls below an order of magnitude, at roughly ${(noiseY * 100 / Math.abs(kor.channels.phi50.dln_gdp_pct)).toFixed(0)} to one. The multiplier channel fares worse against its own noise than output does. The largest currency-drain effect anywhere in the table is Korea's at ${num(kor.channels.phi50.multiplier['c0.05|n20'].dln_m * 100, 3)}%; set against a credit-multiplier surprise of ${pct(noiseM, 2)}, that is a ratio of roughly ${(noiseM / Math.abs(kor.channels.phi50.multiplier['c0.05|n20'].dln_m)).toFixed(0)} to one, where Korea's output ratio was only ${(noiseY * 100 / Math.abs(kor.channels.phi50.dln_gdp_pct)).toFixed(0)} to one. For the United Kingdom the multiplier ratio is about ${(noiseM / Math.abs(gbr.channels.phi50.multiplier['c0.05|n20'].dln_m)).toFixed(0)} to one. On the arithmetic alone, the multiplier channel is not merely unproven but undetectable in annual data.`));

// ---- 6 Strategy
body.push(h1('6. Econometric strategy'));
body.push(p(`The panel has staggered adoption in two directions, so I estimate prohibitions and liberalisations as separate arms, taking the first event of each sign per country and censoring the post-window at any subsequent opposite-signed reform. Germany, which liberalised in 2002 and tightened in 2017, is the binding case.`));
body.push(p(`The first estimator is a two-way fixed-effects event study,`));
body.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 100, after: 100 },
  children: [run('y', { italics: true, size: 23 }), run('it', { sub: true, size: 23 }),
    run(' = α', { italics: true, size: 23 }), run('i', { sub: true, size: 23 }),
    run(' + γ', { italics: true, size: 23 }), run('t', { sub: true, size: 23 }),
    run(' + Σ', { size: 23 }), run('k', { sub: true, size: 23 }),
    run(' β', { italics: true, size: 23 }), run('k', { sub: true, size: 23 }),
    run(' D', { italics: true, size: 23 }), run('it', { sup: true, size: 23 }),
    run('(k) + ε', { italics: true, size: 23 }), run('it', { sub: true, size: 23 }),
    run('     (4)', { size: 20 })],
}));
body.push(p(`with event time k running from −6 to +6, endpoints binned and k = −1 omitted, standard errors clustered by country. Because two-way fixed effects with staggered timing and heterogeneous effects can place negative weights on some treated cells (Goodman-Bacon, 2021; de Chaisemartin and D'Haultfœuille, 2020), I also report the Callaway and Sant'Anna (2021) group-time estimator, aggregating ATT(g, t) over event time using not-yet-treated units as the comparison group.`));
body.push(p(`Inference is the delicate part. The arms have between two and ten treated countries, and cluster-robust t-statistics are not credible at that cluster count (Cameron, Gelbach and Miller, 2008; Young, 2019). I therefore report randomization-inference p-values: the observed multiset of event years is reassigned to randomly chosen never-reforming countries, the estimator is re-run 2,000 times, and the p-value is the share of placebo draws at least as large in absolute value as the estimate. Finally, I compute the minimum detectable effect at 80% power and 5% size as 2.8 times the median standard error, which converts each null into an explicit bound.`));
body.push(p(`For individual reforms I estimate synthetic controls (Abadie, Diamond and Hainmueller, 2010; Abadie, 2021) with simplex weights fitted to the pre-reform path. Donors must never have reformed and must lie within a factor of three of the treated unit's pre-reform income per head; an earlier specification that selected donors by growth-path correlation across all ${R.meta.n_countries} countries returned economically meaningless controls, Laos being the leading donor for South Korea. Significance is assessed by in-space placebo ranks on the ratio of post- to pre-reform RMSPE.`));

// ---- 7 Results
body.push(h1('7. Results'));
body.push(h2('7.1 Panel estimates'));
body.push(p(`Table 3 reports the aggregate post-reform ATT for each outcome and arm, with the largest pre-reform coefficient as a parallel-trends diagnostic, the randomization-inference p-value, and the minimum detectable effect.`));

body.push(cap('Table 3. Aggregate post-reform effects, by arm and outcome.'));
body.push(table(
  ['Arm · outcome', 'Treated', 'Controls', 'Obs.', 'ATT', 'Max pre-trend', 'RI p', 'MDE (80%)'],
  panelRows.map(r => [
    `${ARM[r.arm]} · ${OUTLAB[r.o]}`, String(r.s.n_treated), String(r.s.n_control),
    r.s.nobs.toLocaleString('en-US'), spct(r.cs.att_post), pct(r.cs.pretrend_max),
    r.ri.p_two_sided !== null && r.ri.p_two_sided !== undefined ? r.ri.p_two_sided.toFixed(3) : '—',
    pct(r.pw.mde_80pct),
  ]),
  [2680, 820, 900, 900, 940, 1250, 740, 1130]));
body.push(note(`Notes: Callaway–Sant'Anna aggregate ATT over post-reform event time, not-yet-treated comparison. Randomization-inference p-values from 2,000 placebo reassignments of the observed event years to never-reforming countries. MDE is the minimum effect detectable at 80% power and 5% size, computed as 2.8 times the median event-study standard error. One further cell, reinstatement · bank liquidity multiplier, is not estimable.`));

body.push(...figure('fig2_event_study.png',
  `Figure 2. Event-study coefficients around prohibitions. Circles are two-way fixed-effects estimates with 95% confidence intervals clustered by country; the dashed line is the Callaway–Sant'Anna path against not-yet-treated units.`));

body.push(p(`${panelRows.length - nSig} of the ${panelRows.length} combinations are indistinguishable from zero under randomization inference. The single exception, reinstatement acting on the credit multiplier, is identified off two countries and returns ${spct(panelRows.find(r => r.o === 'ln_mult_credit' && r.arm === 'lib').cs.att_post)}, which is better read as a warning label than as a result. The inflation and money-growth outcomes, which close the quantity identity, are equally null: prohibitions are associated with ${spct(panelRows.find(r => r.arm === 'ban' && r.o === 'infl_rate').cs.att_post)} on inflation and ${spct(panelRows.find(r => r.arm === 'ban' && r.o === 'm2_growth_rate').cs.att_post)} on broad money growth, with p-values of ${panelRows.find(r => r.arm === 'ban' && r.o === 'infl_rate').ri.p_two_sided.toFixed(2)} and ${panelRows.find(r => r.arm === 'ban' && r.o === 'm2_growth_rate').ri.p_two_sided.toFixed(2)}.`));
body.push(p(`The minimum detectable effects are the informative quantity. The best-powered cell, prohibition acting on real GDP per capita with ten treated countries, could detect an effect of ${pct(panelRows.find(r => r.arm === 'ban' && r.o === 'ln_rgdp_pc').pw.mde_80pct)}; the mechanical effect available to it is at most ${pct(maxMech(panelRows.find(r => r.arm === 'ban' && r.o === 'ln_rgdp_pc').s.treated))}. The design is therefore roughly ${(panelRows.find(r => r.arm === 'ban' && r.o === 'ln_rgdp_pc').pw.mde_80pct / maxMech(panelRows.find(r => r.arm === 'ban' && r.o === 'ln_rgdp_pc').s.treated)).toFixed(0)} times too blunt, and the velocity and multiplier cells are blunter still.`));

body.push(h2('7.2 Plausibility'));
body.push(p(`Table 4 sets each estimate against the largest effect the sector could produce if a prohibition eliminated it entirely, that is at φ = 1.`));

body.push(cap('Table 4. Estimates against the maximum mechanically available effect.'));
body.push(table(
  ['Arm · outcome', 'Estimate', 'Max mechanical (φ = 1)', 'Ratio', 'Sign as predicted', 'RI p'],
  panelRows.map(r => [
    `${ARM[r.arm]} · ${OUTLAB[r.o]}`, spct(r.cs.att_post),
    r.mm ? spct(r.mm * r.want) : '—',
    r.ratio ? (r.ratio >= 10 ? r.ratio.toFixed(0) : r.ratio.toFixed(1)) + '×' : '—',
    r.ok ? 'yes' : 'no',
    r.ri.p_two_sided !== null && r.ri.p_two_sided !== undefined ? r.ri.p_two_sided.toFixed(3) : '—',
  ]),
  [2900, 1150, 2000, 900, 1450, 960]));
body.push(note(`Notes: The maximum mechanical effect is the mean measured sector share across that cell's treated countries, signed according to the mechanism in Section 3 — negative for prohibitions on output, velocity, the multiplier and money growth, positive for prohibitions on inflation, and reversed for reinstatements.`));

body.push(p(`${nWrong} of the ${panelRows.length} estimates carry the sign opposite to the mechanism, and ${nBig} exceed the maximum mechanically available effect by more than a factor of five, the worst by a factor of ${maxRatio.toFixed(0)}. A velocity estimate of ${spct(panelRows.find(r => r.arm === 'ban' && r.o === 'ln_velocity').cs.att_post)} following prohibition, in countries whose sex trade averages ${pct(maxMech(panelRows.find(r => r.arm === 'ban' && r.o === 'ln_velocity').s.treated))} of GDP, is not a statement about prostitution. It is what a seven-country treatment group looks like when its reforms cluster between 1999 and 2010, a window containing euro convergence, the dot-com cycle and the global financial crisis.`));

body.push(h2('7.3 Individual reforms'));
body.push(p(`Table 5 reports synthetic controls for six reforms under the main specification and under a tighter one with twelve donors and twenty pre-reform years.`));

const scmRows = Object.keys(R.scm).map(k => {
  const m = R.scm[k], b = (R.scm_robust || {})[k];
  const [iso, yr, o] = k.split('|');
  return [`${iso} ${yr}`, OUTLAB[o], pct(m.pre_rmspe), spct(m.post_mean_gap),
    m.placebo_p !== null && m.placebo_p !== undefined ? m.placebo_p.toFixed(3) : '—',
    b ? pct(b.pre_rmspe) : '—', b ? spct(b.post_mean_gap) : '—',
    b && b.placebo_p !== null && b.placebo_p !== undefined ? b.placebo_p.toFixed(3) : '—'];
});
body.push(cap('Table 5. Synthetic control estimates: main specification and tightened donor pool.'));
body.push(table(
  ['Reform', 'Outcome', 'Pre-fit', 'Gap', 'p', 'Pre-fit', 'Gap', 'p'],
  scmRows, [1180, 1900, 920, 1000, 760, 920, 1000, 760]));
body.push(note(`Notes: Columns 3–5 are the main specification (donors within a factor of three of pre-reform income per head, capped at 35, fitted to 12 pre-reform years); columns 6–8 tighten this to 12 donors and 20 pre-reform years. "Pre-fit" is the pre-reform RMSPE, "Gap" the mean post-reform gap, and p an in-space placebo rank. Three velocity cases are not estimable under the tightened specification for want of donors with complete data.`));

body.push(...figure('fig3_scm_korea.png',
  `Figure 3. South Korea and its synthetic control around the 2004 prohibition. The velocity gap in panel (b) opens between 1997 and 2001, several years before the reform.`));

body.push(p(`Two cases attain conventional significance in the main specification — Sweden on real GDP per capita (p = ${R.scm['SWE|1999|ln_rgdp_pc'].placebo_p.toFixed(3)}) and Norway on velocity (p = ${R.scm['NOR|2009|ln_velocity'].placebo_p.toFixed(3)}) — and both lose it under the tightened pool, at p = ${(R.scm_robust['SWE|1999|ln_rgdp_pc'].placebo_p).toFixed(3)} and p = ${(R.scm_robust['NOR|2009|ln_velocity'].placebo_p).toFixed(3)} respectively. Their gaps are in any case ${(Math.abs(R.scm['SWE|1999|ln_rgdp_pc'].post_mean_gap) / 0.001).toFixed(0)} and ${(Math.abs(R.scm['NOR|2009|ln_velocity'].post_mean_gap) / 0.0005).toFixed(0)} times the maximum effect their sectors could supply.`));
body.push(p(`Korea deserves separate comment, because it is the only case with meaningful power. Its synthetic control tracks real GDP per capita closely and shows a post-reform gap of ${spct(R.scm['KOR|2004|ln_rgdp_pc'].post_mean_gap)} with a placebo p of ${R.scm['KOR|2004|ln_rgdp_pc'].placebo_p.toFixed(3)} — precisely nothing, where the mechanical prediction was ${pct(kor.channels.phi50.dln_gdp)}. The velocity panel shows a large gap, but Figure 3(b) makes clear that it opens between 1997 and 2001, during the Asian financial crisis and the subsequent monetary deepening, three to six years before the prohibition. Reading it as a consequence of the 2004 law would require the effect to precede its cause.`));

// ---- 8 Robustness
body.push(h1('8. Robustness'));
body.push(p(`Four checks support the reading above. First, restricting the comparison group to advanced economies moves the point estimates but not the conclusions; the prohibition effect on real GDP per capita falls from ${spct(R.cs['ban|ln_rgdp_pc|all'].att_post)} to ${spct(R.cs['ban|ln_rgdp_pc|advanced'].att_post)} and remains far inside the noise. Second, the Callaway–Sant'Anna path and the two-way fixed-effects coefficients agree closely in Figure 2, so negative weighting is not driving the result. Third, the pre-reform coefficients reported in Table 3 are large relative to the post-reform estimates in the monetary outcomes, which is itself evidence that the design is tracking macroeconomic cycles rather than legal change. Fourth, the synthetic-control results are strongly specification-dependent in exactly the way that fragile findings are: Korea's GDP gap moves from ${spct(R.scm['KOR|2004|ln_rgdp_pc'].post_mean_gap)} to ${spct(R.scm_robust['KOR|2004|ln_rgdp_pc'].post_mean_gap)} when the donor pool is tightened.`));
body.push(p(`A fifth check is worth stating as a caution rather than a reassurance. Under the main specification several pre-reform RMSPEs fall below 0.5%, which means a 35-donor simplex is interpolating a 12-point pre-path almost exactly. That is not a control group, and it inflates the post-to-pre ratio on which the placebo rank is built. The tightened specification, with more targets than free weights, is the one to believe.`));

// ---- 9 Discussion
body.push(h1('9. Discussion'));
body.push(p(`The contribution of this paper is a bound. Across ${REG.length} reforms, ${R.meta.n_countries} countries and six outcomes, I find no evidence that prohibiting or re-legalising prostitution moves GDP, the velocity of money, the money multiplier, inflation or money growth. That statement would be close to vacuous on its own, because an absence of evidence in an underpowered design is uninformative. What makes it useful is that the power calculation is explicit and comes first. The minimum detectable effects in Table 3 exceed the maximum effect the sector could generate by one to three orders of magnitude, and the arithmetic in Table 2 is independent of any identification assumption.`));
body.push(p(`This has a direct implication for policy debate. Macroeconomic arguments for or against prostitution law reform — that a ban will slow the circulation of money, that legalisation will measurably enlarge the economy — are not supported, and more importantly are not supportable at this level of aggregation. A sector of a few tenths of one per cent of GDP cannot move an aggregate whose annual innovation is three percentage points. The case for or against reform has to be made on the grounds the microeconomic literature actually speaks to: violence, health, trafficking and the welfare of the people involved.`));
body.push(p(`There is also a methodological point of general application. Where an intervention's mechanical magnitude can be bounded from outside the regression, reporting that bound alongside the minimum detectable effect converts an uninformative null into an informative one, and discourages the alternative outcome — a specification search across six outcomes, two arms and several comparison groups until something crosses a threshold. In this exercise such a search would have succeeded: ${nSig} panel cell and two synthetic controls reach conventional significance. All three are implausible on magnitude, and the two synthetic controls do not survive a tighter donor pool. Without the prior bound there would be no principled way to dismiss them (Ioannidis, Stanley and Doucouliagos, 2017).`));

// ---- 10 Limitations
body.push(h1('10. Limitations'));
const lims = [
  ['Monetary union removes the richest reforms. ', `National broad-money series end with euro entry, so the Netherlands 2000, Germany 2002 and 2017, France 2016 and Ireland 2017 cannot be tested on velocity or the multiplier at all. Canada is lost separately, its broad-money series ending in 2008.`],
  ['No monetary base. ', `The textbook M2/M0 multiplier is not constructible from the available sources, so the multiplier is approached through two ratio proxies and the analytic formula of equation (3). The reserve ratio is available only from 2001, which leaves the 2004 Korean prohibition with three pre-reform years on that outcome.`],
  ['The reinstatement arm is thin. ', `Denmark 1999, Hungary 1999 and New Zealand 2003 are the only liberalisations with both GDP and monetary data; one cell is identified off two countries. Conclusions about re-legalisation are correspondingly weaker than those about prohibition.`],
  ['Measurement is endogenous to the treatment. ', `What counts as prostitution output depends on whether statisticians count it, and agencies differ fivefold under a common accounting standard. For pre-2014 reforms, part of any measured GDP movement is the accounting treatment changing rather than behaviour.`],
  ['Annual frequency. ', `A reform with a sharp in-force date is being tested against data observed once a year, which discards most of the information in the timing and is a substantial part of why the minimum detectable effects are so large.`],
  ['Donor pools. ', `Income-similarity screening removes the worst pathologies but still admits small open economies such as Andorra and Brunei into some synthetic controls. The tightened specification is preferred for that reason.`],
];
lims.forEach(([b, t]) => body.push(new Paragraph({
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 130, line: 320 },
  indent: { left: convertInchesToTwip(0.3), hanging: convertInchesToTwip(0.3) },
  children: [run('—  '), run(b, { bold: true }), run(t)],
})));

// ---- 11 Conclusion
body.push(h1('11. Conclusion'));
body.push(p(`Banning prostitution does not detectably change the velocity of money, and neither does legalising it. Nor does either move GDP, the money multiplier, inflation or broad money growth. The finding is a bound rather than a discovery, but it is a tight one: in every jurisdiction with usable data except South Korea the sector is one to three orders of magnitude too small to register in annual macroeconomic series, and the currency-drain channel into the multiplier is undetectable even in Korea.`));
body.push(p(`The question becomes answerable only where the shock is large, the data frequent, or the unit of observation small. Three designs follow. Korea's 2004 prohibition deserves a monthly or quarterly treatment using Bank of Korea aggregates, currency in circulation and base money. Rhode Island's 2003 to 2009 decriminalisation can be tested against other American states on county business patterns. And Northern Ireland's 2015 sex-purchase offence can be tested against Great Britain on regional gross value added, which includes illegal activity and is published by region. None of these requires new data collection; all three require data this paper could not reach.`));

// ---- References
body.push(h1('References'));
const REFS = [
  `Abadie, A. (2021). Using synthetic controls: feasibility, data requirements, and methodological aspects. Journal of Economic Literature, 59(2), 391–425.`,
  `Abadie, A., Diamond, A., and Hainmueller, J. (2010). Synthetic control methods for comparative case studies: estimating the effect of California's tobacco control program. Journal of the American Statistical Association, 105(490), 493–505.`,
  `Bisschop, P., Kastoryano, S., and van der Klaauw, B. (2017). Street prostitution zones and crime. American Economic Journal: Economic Policy, 9(4), 28–63.`,
  `Callaway, B., and Sant'Anna, P. H. C. (2021). Difference-in-differences with multiple time periods. Journal of Econometrics, 225(2), 200–230.`,
  `Cameron, A. C., Gelbach, J. B., and Miller, D. L. (2008). Bootstrap-based improvements for inference with clustered errors. Review of Economics and Statistics, 90(3), 414–427.`,
  `Cho, S.-Y., Dreher, A., and Neumayer, E. (2013). Does legalized prostitution increase human trafficking? World Development, 41, 67–82.`,
  `Cunningham, S., and Shah, M. (2018). Decriminalizing indoor prostitution: implications for sexual violence and public health. Review of Economic Studies, 85(3), 1683–1715.`,
  `de Chaisemartin, C., and D'Haultfœuille, X. (2020). Two-way fixed effects estimators with heterogeneous treatment effects. American Economic Review, 110(9), 2964–2996.`,
  `Department of Justice (Northern Ireland) (2019). Review of the operation of Article 64A of the Sexual Offences (Northern Ireland) Order 2008. Belfast.`,
  `Edlund, L., and Korn, E. (2002). A theory of prostitution. Journal of Political Economy, 110(1), 181–214.`,
  `Eurostat (2013). European System of Accounts: ESA 2010. Publications Office of the European Union, Luxembourg.`,
  `Friedman, M. (1956). The quantity theory of money: a restatement. In Studies in the Quantity Theory of Money. University of Chicago Press.`,
  `Gertler, P., Shah, M., and Bertozzi, S. M. (2005). Risky business: the market for unprotected commercial sex. Journal of Political Economy, 113(3), 518–550.`,
  `Goodman-Bacon, A. (2021). Difference-in-differences with variation in treatment timing. Journal of Econometrics, 225(2), 254–277.`,
  `Ioannidis, J. P. A., Stanley, T. D., and Doucouliagos, H. (2017). The power of bias in economics research. Economic Journal, 127(605), F236–F265.`,
  `Jakobsson, N., and Kotsadam, A. (2013). The law and economics of international sex slavery: prostitution laws and trafficking for sexual exploitation. European Journal of Law and Economics, 35(1), 87–107.`,
  `Lee, S., and Persson, P. (2022). Human trafficking and regulating prostitution. American Economic Journal: Economic Policy.`,
  `Office for National Statistics (2014). Changes to National Accounts: inclusion of illegal drugs and prostitution in the UK National Accounts. Newport.`,
  `Rogoff, K. S. (2016). The Curse of Cash. Princeton University Press.`,
  `Schneider, F., and Enste, D. H. (2000). Shadow economies: size, causes, and consequences. Journal of Economic Literature, 38(1), 77–114.`,
  `Soloveichik, R. (2021). Including illegal market activity in the U.S. national economic accounts. Survey of Current Business, 101(2). Bureau of Economic Analysis.`,
  `Statistics Netherlands (CBS) (2024). Estimating illegal activities in the national accounts. The Hague.`,
  `Statistisches Bundesamt (Destatis) (2025). Prostitute Protection Act statistics: registered prostitutes, 2017–2024. Wiesbaden.`,
  `World Bank (2021). World Development Indicators. Washington, DC.`,
  `Young, A. (2019). Channeling Fisher: randomization tests and the statistical insignificance of seemingly significant experimental results. Quarterly Journal of Economics, 134(2), 557–598.`,
];
REFS.forEach(r => body.push(new Paragraph({
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 110, line: 290 },
  indent: { left: convertInchesToTwip(0.4), hanging: convertInchesToTwip(0.4) },
  children: [run(r, { size: 20 })],
})));

// ---- Appendix
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(h1('Appendix A. Legal regime changes'));
body.push(cap('Table A1. Prostitution regime changes, 1999–2022.'));
const dirLab = (d) => d === '-1' ? 'Prohibition' : 'Reinstatement';
body.push(table(
  ['Jurisdiction', 'In force', 'Direction', 'Instrument', 'Level', 'Monetary status'],
  REG.slice().sort((a, b) => a.event_date.localeCompare(b.event_date)).map(r => [
    r.jurisdiction, r.event_date, dirLab(r.direction),
    r.instrument.replace(/_/g, ' '), r.level,
    { own: 'own currency', euro: 'euro area', own_shared: 'shares a currency' }[r.currency_area] || r.currency_area,
  ]),
  [1800, 1180, 1440, 2000, 1340, 1600], { leftCols: 6 }));
body.push(note(`Notes: "Monetary status" determines whether a reform can be tested on velocity or the multiplier at all. Full descriptions and source URLs for every row are in data/regimes.csv in the replication materials.`));

body.push(h1('Appendix B. Measurements of sector size'));
body.push(cap('Table A2. Quantitative measurements of the prostitution sector.'));
body.push(table(
  ['Jurisdiction', 'Year', 'Measure', 'Value', '% of GDP', 'In official GDP', 'Source'],
  MEA.map(m => [
    m.jurisdiction, m.year, m.measure.replace(/_/g, ' '),
    m.value ? `${m.value} ${m.unit}` : '—',
    m.pct_gdp ? m.pct_gdp + '%' : '—',
    { yes: 'yes', no: 'satellite only' }[m.in_official_gdp] || 'n/a',
    m.source_org,
  ]),
  [1420, 580, 1960, 1240, 860, 1420, 1880], { leftCols: 7 }));
body.push(note(`Notes: Source URLs for every row are in data/prostitution_measures.csv in the replication materials.`));

body.push(h1('Appendix C. Data and replication'));
body.push(p(`All data and code are in the prostitution-macro directory of the accompanying repository. Macroeconomic series are World Bank World Development Indicators for ${R.meta.years[0]}–${R.meta.years[1]}, obtained through a public mirror because the World Bank, IMF, FRED, ONS, Bank of England and BEA endpoints were not reachable from the environment in which this analysis was run; that constraint also prevented construction of the monetary base series discussed in Section 4.3 and the sub-national designs proposed in Section 11. Every row of the regime and measurement tables carries its own source URL. Scripts run in order: 01 builds the panel, 02 scores abundance, 03 estimates, 04 computes the arithmetic bound, 05 renders the companion interactive report, 06 the figures and 07 this article.`));

// ================================================================= assemble
const doc = new Document({
  creator: 'Prostitution macro project',
  title: 'Can a Prostitution Ban Move the Money?',
  description: 'Output, velocity and the money multiplier around twenty prostitution regime changes',
  styles: {
    default: {
      document: { run: { font: SERIF, size: 22 } },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: {
          top: convertInchesToTwip(1), bottom: convertInchesToTwip(1),
          left: convertInchesToTwip(1), right: convertInchesToTwip(1),
        },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [PageNumber.CURRENT], font: SERIF, size: 18 })],
        })],
      }),
    },
    children: body,
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = path.resolve(ROOT, '..', 'prostitution_macro_article.docx');
  fs.writeFileSync(out, buf);
  console.log('wrote ' + out + '  (' + buf.length.toLocaleString('en-US') + ' bytes)');
});
