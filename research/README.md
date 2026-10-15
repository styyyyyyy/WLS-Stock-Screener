# Historical A3/B2 scenario

`historical_backtest.py` reruns the daily Screen A3 + Screen B2 method on a dated
price, EPS and volume panel. It is a **retrospective scenario**, not a
point-in-time trading backtest. The October WLS membership, GICS sectors,
earnings calendar and Bloomberg liquidity/cap filter are applied backward to
September because their daily historical snapshots were not supplied.

## Inputs

- A WLS workbook with `Worksheet` (`Ticker`, `Expected Earnings`, `Weight`) and
  `Prices` (ticker, company, currency, dated close columns) sheets.
- An EPS/volume workbook with `EPS` and `Trad Volume` sheets whose tickers and
  date columns match `Prices` exactly. Dated EPS observations are treated as
  available at that date's close; availability timestamps are not verified.
- A `Ticker,Sector` CSV mapped to the *dated panel's* ticker IDs. Rows with a
  blank or `--` sector cannot be ranked within GICS sector and are excluded.
- Exactly one **snapshot** filter source:
  - `--filter-snapshot`: CSV columns `Ticker,PriceD1USD,ADV20USD,MarketCapUSD`.
    It applies the Bloomberg filter in order: WLS constituent, prior price
    **> USD 1**, 20-day average daily traded value **> USD 15 million**, and
    market cap **> USD 500 million**. These are strict greater-than tests.
    Convert fields to USD upstream and date the file correctly.
  - `--eligible-snapshot`: CSV column `Ticker` listing an independently
    verified eligible cohort, such as the reconciled 4,957 names. This mode
    cannot itself verify the three thresholds and is labelled accordingly.

The snapshot filter is fixed for the entire scenario. Supplying it does **not**
make the September backtest point-in-time. For that, provide historical daily
WLS membership, prior USD price, ADV20 USD, market cap USD, GICS sector, EPS
availability, and earnings dates, then change the engine to use each day's
snapshot before the signal. A current `--filter-snapshot` applies a *single*
snapshot to every historical signal.

## Example

```bash
python research/historical_backtest.py \
  --prices /path/to/wls_prices.xlsx \
  --eps-volume /path/to/eps_and_volume.xlsx \
  --sectors /path/to/dated_ticker_sectors.csv \
  --filter-snapshot /path/to/filter_snapshot.csv \
  --snapshot-date 2026-10-08 \
  --wls-weights-snapshot /path/to/full_wls_weights.csv \
  --first-signal 2026-09-07 \
  --final-mark 2026-10-07 \
  --output-dir outputs/historical_scenario
```

To use a preverified snapshot cohort, replace `--filter-snapshot` with
`--eligible-snapshot /path/to/eligible_tickers.csv`.

`--wls-weights-snapshot` is optional. Its CSV must contain `Ticker,Weight`
for the entire dated WLS panel, already mapped to those ticker IDs. Without it,
the script uses the `Worksheet` weights in `--prices`. With the mapped October 10
weight snapshot from the prior analysis, the full-WLS start-anchored proxy is
`+0.98784775%`; the same-engine September 7–October 7 strategy scenarios were
`−5.860045%` for all 10,416 classified names and `+14.061548%` for the
preverified 4,957 snapshot cohort. These retrospective figures describe
different candidate sets, and the proxy is not the official WLS Index.

## Method and outputs

The model ranks seven continuous factors using midpoint percentiles *within
GICS sector*. Missing numeric factor values receive a neutral 0.5 percentile.
To reproduce the prior scenario exactly, the three-month and EPS 30-day
**calendar reference dates** and the earnings countdown are measured from the
following global close. Every price, EPS and volume **observation** used in a
signal is dated on or before that signal's close; the following day's prices
are used only for execution and later portfolio marks. This date convention
should not be confused with access to future signal data.
Screen A score is 40% three-month price return, 25% symmetric 30-calendar-day
EPS revision, 25% confirmation and 10% five-local-session return. Confirmation
is 40% MA20 distance, 30% MA50 distance and 30% five/twenty-session volume
ratio. Screen B score is 35% earnings catalyst, 30% annualized 20-local-session
volatility, 20% five-session return and 15% volume ratio. The estimated next
earnings date is back-projected from the later snapshot on a three-calendar-month
cadence, with a conflict check if that would imply an event after the snapshot.
The catalyst is 1.0 for 0–5 Monday–Friday days to earnings, 0.75 for 6–10, 0.5
for 11–15, and zero otherwise. Local exchange holidays are not separately
modeled.

At each signal close, the top three A stocks and top two distinct B stocks are
selected. The next global trading close executes an equal 20%-of-NAV target
for each. Existing positions remain open overnight and are resized or sold at
later rebalances. A stock whose local market is closed has its existing shares
frozen at the previous active close; a closed target slot remains cash. The
terminal close marks NAV and liquidates stocks whose markets are open.

The output folder contains:

- `summary.json`: period, filter audit, method, key statistics and limitations.
- `daily.csv`: strategy NAV, return, cash, frozen positions and turnover.
- `holdings.csv`: all five targets, scores and components for every signal.
- `trades.csv`: simulated next-close buys and sells, including terminal sales.
- `wls_snapshot_proxy_daily.csv`: a *full-universe, non-equal-weighted* WLS
  reference, constructed as a start-close buy-and-hold portfolio using later
  snapshot weights. An index member missing a starting price is kept flat
  instead of silently reallocating its weight. It is not the official WLS
  Index series or official alpha.

Results use local-currency price ratios as though FX were constant and omit
dividends, verified split adjustments, commissions, bid/ask spread, taxes and
market impact. No proprietary input workbook or absolute personal path is
included in this repository.
