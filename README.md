# WLS Stock Screener

Reproducible Screen A and Screen B rankings for a daily-rebalanced, five-stock
portfolio. The current method starts with the Bloomberg World Large, Mid &
Small Cap **Price Return** Index (WLS) universe, applies an investability
filter, ranks the survivors within their sectors, and selects three Screen A
stocks plus two distinct Screen B stocks. Each target position is 20% of
portfolio value. WLS index constituent weights are used only for an index
reference, never as strategy weights.

## The 10,000-to-5,000 first layer

Apply these **strict** gates to every WLS constituent before calculating any
sector percentile or score:

| Bloomberg field | Required value |
| --- | ---: |
| `Price 1 Day ago [USD]` | `> 1` USD |
| `Average Daily Value Traded` (20-day average) | `> 15,000,000` USD |
| `Current Market Cap [USD]` | `> 500,000,000` USD |

Missing values fail. The number surviving varies by date; “5,000” is an
approximation. The supplied October 14 export has 10,417 WLS rows and 4,965
names with usable sector/history after the gates. Its average daily traded
value field is lagged (`Avg D Val Traded 20D:D-20`), so that day's replay is
an estimate of a current liquidity screen.

**Data timing matters:** for a completed-close decision, the price gate must
use the prior completed local-session USD close. A mixed-time intraday `Price`
field must not replace it. The conventional `Main` workbook labels its field
`PriceUSD`; supply the prior completed close there for parity with Bloomberg.
The traded-value and market-cap inputs must also be USD values known at the
decision time.

## Scores and portfolio

Within the filtered universe, `PR(x)` is the midpoint percentile of factor
`x` within the stock's GICS sector. Missing numeric factors get a neutral
`0.5`; missing filter fields fail the first layer.

```text
EPSRevision = (FY1_now - FY1_30_days_earlier)
              / (abs(FY1_now) + abs(FY1_30_days_earlier) + 1e-12)
VolumeRatio = average share volume over 5 sessions / average over 20 sessions
PriceConfirmation = 0.40×PR(price/MA20−1)
                  + 0.30×PR(price/MA50−1)
                  + 0.30×PR(VolumeRatio)

ScreenA = 0.40×PR(3-month return) + 0.25×PR(EPSRevision)
        + 0.25×PriceConfirmation + 0.10×PR(5-session return)

ScreenB = 0.35×EarningsCatalyst + 0.30×PR(20-session volatility)
        + 0.20×PR(5-session return) + 0.15×PR(VolumeRatio)
```

The earnings catalyst is 1.00 when the next report is due in 0–5 weekdays,
0.75 for 6–10, 0.50 for 11–15, and zero otherwise. Each screen exports its
Top 20. The portfolio takes A ranks 1–3, then the two highest B names that
are not already selected for A. Positions remain open overnight; a daily
rebalance sells or resizes them at the next modeled execution price. A closed
local market cannot receive a fictional fill.

See [full methodology](docs/methodology.md) for factor definitions,
tie-breakers, data timing, and limitations.

## Install

Python 3.10 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run with a normalized `Main` / `Prices` / `Turnover` workbook

Use this interface when all WLS candidate stocks, including names that may
fail the first-layer gates, are already in the three-sheet format. `Main`
columns A:T are, in order: ticker, name, USD prior-close price, 20-day USD
average daily value traded, USD market cap, local market cap, local price,
P/E, unused, GICS sector, next earnings date, 20-day volatility, 5-day
average share volume, 20-day average share volume, country, 5-day return,
3-month return, current FY1 EPS estimate, 30-day-old FY1 EPS estimate, and
an unused EPS-change field. `Prices` and `Turnover` contain ticker followed
by dated daily observations. The `Prices` sheet needs at least 50 completed
observations for the moving averages.

```bash
python run_screener.py \
  --input /path/to/wls_main_prices_turnover.xlsx \
  --as-of-date 2026-10-13 \
  --output-dir outputs/screening
```

This exports the gate audit and counts, both full rankings and Top 20 lists,
five equal-weight target positions, an Excel report, and run metadata. It
uses the supplied `Main` fields as dated inputs; it does not reconstruct
missing daily market-cap or traded-value history. The older roughly 5,000-row
workbook is already a filtered subset and cannot demonstrate the full
10,000-to-5,000 reduction by itself.

## Replay the supplied October 14 raw WLS export

The newer `Worksheet`/dated-panel files have a different layout. This
entry point joins the raw approximately 10,000-stock snapshot to the older
price and comparable FY1 EPS/share-volume history, applies the first-layer
filter, and exports the Screen A/B Top 20 and A3/B2 target. The five local
workbooks are inputs only; they are not included in this repository.

```bash
python run_current_snapshot.py \
  --historical-prices /path/to/WLS_as_of_Oct_08_and_Prices_100d.xlsx \
  --eps-volume /path/to/EPS_and_Turnover.xlsx \
  --sector-snapshot /path/to/WLS_as_of_Oct_10.xlsx \
  --interim-snapshot /path/to/20261013_Data.xlsx \
  --current-snapshot /path/to/20261014_Data_USD.xlsx \
  --signal-date 2026-10-13 \
  --decision-date 2026-10-14 \
  --output-dir outputs/oct14_replay
```

The replay writes `filter_audit.csv`, `eligible_scored.csv`, `top20_A.csv`,
`top20_B.csv`, `targets_A3_B2.csv`, `exchange_calendar_inference.csv`, and
`summary.json`. The October 14 workbook's FY1-incompatible BF12M EPS field
is not mixed into the older FY1 series. Complete comparable EPS and 5/20
share-volume observations stop at October 7, and October 8–9 share volumes
were not supplied. This selection is therefore **indicative**, not a
fully refreshed October 13 signal. See the warnings in `summary.json`.

## Historical daily scenario

The standalone historical runner performs a daily A3/B2 next-close replay
on dated price, EPS, and volume panels. A filter cohort supplied to this
runner is an **October snapshot applied retrospectively** because daily
historical USD market caps and 20-day USD traded values were not provided.
It is not a point-in-time implementation of the first layer. A sector CSV
must have `Ticker,Sector` columns. Supply either a verified `Ticker` cohort
or a snapshot CSV containing `Ticker,PriceD1USD,ADV20USD,MarketCapUSD`;
the latter applies the strict gates to that snapshot.

```bash
python research/historical_backtest.py \
  --prices /path/to/WLS_as_of_Oct_08_and_Prices_100d.xlsx \
  --eps-volume /path/to/EPS_and_Turnover.xlsx \
  --sectors /path/to/ticker_sector.csv \
  --filter-snapshot /path/to/snapshot_filter_fields.csv \
  --snapshot-date 2026-10-08 \
  --first-signal 2026-09-07 \
  --final-mark 2026-10-07 \
  --output-dir outputs/backtest
```

Outputs are `summary.json`, `daily.csv`, `holdings.csv`, `trades.csv`, and
`wls_snapshot_proxy_daily.csv`. The supplied data supported a retrospective
full-universe result of −5.86% and a 4,957-name mapped-cohort result of
+14.06% under the same engine. Those figures are **gross local-price
scenarios**, with October membership, sector, eligibility, and expected
earnings dates projected backward. The WLS comparison is a
constituent-weighted *proxy*, not an official WLS index return. To reproduce
the prior October 10 WLS-weight proxy, also pass an optional full-universe
`--wls-weights-snapshot` CSV. See the
[historical runner input contract](research/README.md) and
[result caveats](docs/backtest_2026.md).

## Check the code

```bash
pytest -q
```

Do not commit licensed Bloomberg exports, account holdings, or output files
to the public repository.
