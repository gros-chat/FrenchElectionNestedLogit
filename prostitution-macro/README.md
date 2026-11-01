# Prostitution regimes, GDP, money velocity and the multiplier

Does banning — or re-legalising — prostitution move a country's GDP, the
velocity of money, or the money multiplier?

This folder collects the data, ranks jurisdictions by how much data they
actually have, and runs the test.

## The short answer

For every jurisdiction with usable data except South Korea, **the sector is far
too small for the question to be answerable with annual macro data.** Suppressing
half of the UK's measured prostitution sector moves GDP by 0.19%, against a
3.3% standard deviation of the annual idiosyncratic surprise in real GDP per
capita among advanced economies — a signal roughly one twentieth of the noise.
The currency-drain channel into the money multiplier is one to two orders of
magnitude smaller still. South Korea's 2004 ban is the only event anywhere whose
mechanical size (≈2% of GDP) comes within an order of magnitude of the noise.

So the estimates below are reported as **bounds**, not as discoveries: what the
data can rule out, rather than what it reveals.

## Layout

```
data/
  regimes.csv              20 dated regime changes, 1999-2022, with sources
  sector_measurement.csv   how much prostitution data each jurisdiction has
  prostitution_measures.csv the actual measured figures, with sources
  panel.csv                built macro panel, 214 countries x 1960-2020
  abundance.csv            the data-abundance ranking
src/
  01_build_panel.py        pull WDI, derive velocity and multiplier proxies
  02_abundance.py          score jurisdictions on data abundance
  03_estimate.py           event study, Callaway-Sant'Anna, randomization
                           inference, synthetic control
  04_arithmetic.py         mechanical effect sizes and the noise floor
  05_report.py             render the HTML report
out/
  abundance.json  arithmetic.json  results.json
```

Run in order: `01` → `02` → `03` → `04` → `05`.

## Data sources

**Macro.** World Bank World Development Indicators, 1960-2020, via the public
mirror `github.com/ZeningQu/World-Bank-Data-by-Indicators`. The live World Bank,
IMF, FRED, ONS, Bank of England and BEA endpoints are all blocked by this
environment's network policy, so the mirror is the data channel. Series used:
GDP (current and constant LCU), GDP per capita (constant LCU), GDP deflator,
broad money (current LCU and % of GDP), bank liquid reserves to bank assets,
domestic credit to the private sector, net domestic credit, CPI.

**Prostitution.** Hand-compiled from official statistical and legislative
sources, every row carrying its own URL in `data/prostitution_measures.csv` and
`data/regimes.csv`. The main ones: ONS's 2014 methodology article and FOI
release on illegal production in the UK National Accounts; CBS's 2024 longread
on estimating illegal activities in the Dutch national accounts; BEA's February
2021 *Survey of Current Business* research spotlight; Destatis releases on
registered sex workers; the Northern Ireland Department of Justice / Queen's
University Belfast statutory review of the 2015 sex-purchase offence; the
Korean Institute of Criminology and Korea Women's Development Institute
turnover estimates; `legislation.gov.uk` for the Northern Ireland Act; and the
European Parliament's 2021 and 2024 studies on prostitution regulation in the EU.

## Derived quantities

| Quantity | Definition |
|---|---|
| Velocity of broad money | `V = nominal GDP / M2` |
| Credit multiplier | `private credit (%GDP) / broad money (%GDP)` |
| Bank liquidity multiplier | `bank assets / bank liquid reserves` |
| Money multiplier (analytic) | `m = (1+c)/(r+c)`, `c` currency/deposits, `r` reserves/deposits |

The textbook `M2/M0` multiplier is **not** constructible here: no reachable
source carries monetary base or M1 for a country panel. The two ratio proxies
and the analytic multiplier are what the available data supports, and the
report says so where it matters.

## Two structural limits worth knowing before reading the results

1. **Euro-area events cannot be tested on money at all.** National broad-money
   series end with monetary union, so WDI carries zero observations for Germany,
   France, the Netherlands, Italy, Ireland, Belgium, Spain and Austria. That
   removes the Netherlands 2000 brothel-ban lift, Germany 2002 and 2017, France
   2016 and Ireland 2017 from every velocity and multiplier test. Canada drops
   out too: its broad-money series ends in 2008, six years before PCEPA.
2. **The "reinstatement" arm is thin.** Liberalisations with both GDP and money
   data come down to Denmark 1999, Hungary 1999 and New Zealand 2003. Any
   statement about re-legalisation rests on those three countries.

## Inference

With three to nine treated countries, cluster-robust *t*-statistics are not
credible. The reported *p*-values come from **randomization inference**: the
observed multiset of event years is handed to randomly chosen never-treated
countries, the estimator is re-run 2,000 times, and the *p*-value is the share
of placebo draws at least as large in absolute value. Synthetic-control
*p*-values are in-space placebo ranks on the post/pre RMSPE ratio.
