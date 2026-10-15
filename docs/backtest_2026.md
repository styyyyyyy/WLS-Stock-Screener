# September–October 2026 historical scenario

The supplied historical panel covers 10,418 securities and 100 dated price,
EPS-estimate and share-volume observations. A later GICS snapshot identifies
sectors for 10,416 of them. Signals run from September 7 through October 5;
the first modeled execution is the September 8 global close, the last rebalance
is the October 6 global close, and the terminal mark is October 7. There are 21
daily A3/B2 signals and 105 selected stock-day slots.

| Universe and convention | Gross strategy return | Meaning |
| --- | ---: | --- |
| 10,416 sector-classified stocks, same factor engine | **−5.86%** | Full dated-panel scenario |
| 4,957 mapped stocks, same factor engine | **+14.06%** | Retrospective smaller-universe comparison |

The controlled comparison changes **82 of 105** A/B stock-day slots. A smaller,
more liquid candidate pool therefore changed the selections materially. It
does **not** prove that a daily implementation of the current Bloomberg
price/ADV/cap filter would have earned +14.06%: the supplied historical panel
does not contain each day's USD market cap and 20-day USD traded value. The
4,957-stock cohort is a later snapshot mapping used retrospectively.

An earlier published +15.81% result on about 4,957 stocks used a different
earnings-date anchor and implementation convention. It cannot be compared to
−5.86% as a pure universe effect. The +14.06% line above holds the factor engine,
earnings anchor and execution convention constant.

## Execution convention

For each signal, rank eligible names by within-sector midpoint percentiles,
choose A top 3 plus two distinct B names, and set each selected name's target
to 20% of portfolio value. A signal uses observations at or before its signal
close. The portfolio rebalances at the **next** modeled global close, holds
positions overnight, and marks the resulting holdings daily. It does not close
all positions at every day's end. A closed local exchange cannot execute a new
trade; an existing position remains frozen and an unfilled slot remains cash.
No commissions, spread or market impact are deducted.
To reproduce the earlier calculation exactly, the 3-month and 30-calendar-day
lookback dates and earnings countdown use the following global close as their
calendar anchor. The factor observations themselves never extend beyond the
signal close.

The October 8 next-earnings snapshot is rolled backward on an assumed
three-calendar-month reporting cycle for Screen B. This is not a history of
announcements actually visible to a trader on each September date. Moving
that inferred event schedule five calendar days earlier or later changes the
full-universe gross result to +0.88% or −4.36%, respectively.

## WLS comparison

The portfolio is equal-weighted across its **five positions**. WLS itself is
not equal-weighted. Using the October 10 WLS constituent-weight snapshot with local
price ratios gives an approximate full-index reference of **+0.99%** under a
start-weight convention or **+0.19%** under an end-weight convention. These are
retrospective proxies, **not** official WLS Index returns. No exact excess
return versus the official index can be computed without historical index
levels or point-in-time weights. The historical runner defaults to the October
8 `Worksheet` weights; to reproduce the +0.99% start-weight proxy, supply
mapped October 10 `Ticker,Weight` values through `--wls-weights-snapshot`.
The +0.19% end-weight figure is from the earlier separate analysis and is
not emitted by this runner.

All returns compound local-currency price ratios. They omit actual daily FX,
dividends, verified corporate-action adjustments and trading costs. One
selected raw-price jump exceeded 50%, so split/corporate-action verification
is material. October sector and membership data are applied to September.
These limitations prevent labeling the result a point-in-time executable
backtest.

## Data needed for a strict rerun

For each September and October signal date, supply as-of-time WLS membership,
previous close in USD, 20-day USD average daily traded value, USD market cap,
GICS sector, comparable FY1 EPS now and 30 days earlier, next earnings date,
share volumes, adjusted prices, FX, and official WLS Index close. With those
dated fields, the first-layer 10,000-to-5,000 screen can be recomputed **each
day before ranks**, rather than carried backward from a later snapshot.
