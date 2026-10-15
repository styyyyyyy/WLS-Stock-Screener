# Current WLS screening and portfolio rules

This document defines the model used for the October 2026 daily selections. The
input universe is the Bloomberg World Large, Mid & Small Cap **Price Return**
Index constituent list (WLS). A stock's WLS index weight does **not** become
its strategy weight.

## 1. Screen the index universe first

Apply all three strict tests to each constituent using values available at the
decision time:

| Field | Rule |
| --- | --- |
| Previous completed local-session price, converted to USD | `> 1` USD |
| 20-day average daily value traded | `> 15,000,000` USD |
| Current market capitalization | `> 500,000,000` USD |

Missing or nonnumeric values fail the relevant test. A usable GICS (Global Industry Classification Standard) sector and
factor history are also needed for a rank. In the October 14 supplied snapshot,
10,417 WLS rows became 4,965 scored names. This count describes that dated
export; it is not a permanent universe size. The export's field
`Avg D Val Traded 20D:D-20` is a *lagged* average, so its gate is an estimate
of a current 20-day liquidity screen.

The filter must run **before** calculating sector percentiles. Ranking all
10,000 names and only removing the failing ones afterward produces different
scores and a different portfolio.

## 2. Calculate factors inside the filtered universe

For a numeric factor in one GICS sector, its midpoint percentile is

```text
PR(x_i) = (number below x_i + 0.5 × number equal to x_i) / number with data
```

Missing numeric factors receive a neutral `0.5` percentile. Filter fields do
not receive this treatment: a missing price, traded value or market cap fails
the filter. The EPS revision must compare two estimates of the **same** FY1
series and currency:

```text
EPSRevision = (FY1_now - FY1_30_days_earlier)
              / (abs(FY1_now) + abs(FY1_30_days_earlier) + 1e-12)

VolumeRatio = average daily share volume over 5 trading sessions
              / average daily share volume over 20 trading sessions

PriceConfirmation = 0.40 × PR(price / MA20 - 1)
                  + 0.30 × PR(price / MA50 - 1)
                  + 0.30 × PR(VolumeRatio)

ScreenA = 0.40 × PR(3-month return)
        + 0.25 × PR(EPSRevision)
        + 0.25 × PriceConfirmation
        + 0.10 × PR(5-session return)

ScreenB = 0.35 × EarningsCatalyst
        + 0.30 × PR(20-session annualized volatility)
        + 0.20 × PR(5-session return)
        + 0.15 × PR(VolumeRatio)
```

The earnings catalyst equals `1.00` for a report due in 0–5 weekdays, `0.75`
for 6–10, `0.50` for 11–15, and zero otherwise. An already past report date
gets zero. The weekday count does not separately model each exchange holiday.
The 0–5 score is proximity only; it does not predict a positive earnings
surprise. Bloomberg *expected* report dates need event-specific verification.

Screen A ties break by score, 3-month percentile, EPS percentile, traded value,
then ticker. Screen B ties break by score, catalyst, volatility percentile,
5-session percentile, traded value, then ticker.

## 3. Build the five-stock target

Take Screen A ranks 1–3, then the two highest Screen B stocks **excluding**
those already selected for A. Each of the five target positions receives 20%
of strategy NAV. The two screens' Top 20 lists remain separate ranking outputs;
being on both lists does not create two positions. Current account holdings,
open orders and fill prices determine actual trade quantities.

For daily rebalancing, compute the signal from the latest completed prices and
other information available at the decision time. Execute the new target at the
next tradable price used by the backtest. Keep positions overnight and resize or
sell them only at a later rebalance. Do not assume an end-of-day liquidation.
If a local market is closed, do not invent a fill; retain an existing holding
until it can trade, or keep an unfilled target slot in cash.

## 4. Historical data contract

A point-in-time backtest of the full current method needs, for **every** signal
date and candidate stock, the WLS membership, prior completed USD price,
20-session USD traded-value average, USD market cap, GICS sector, dated price
and share-volume history, comparable FY1 estimates at the signal and 30 days
earlier, and the next earnings date as then known. It also needs execution and
mark prices, relevant FX, and official WLS index levels for an exact relative
return. A single October snapshot is not a substitute for these daily
historical fields.

The supplied 100-day panel supports an **illustrative** September–October
scenario. Its October membership, sector, eligibility and expected-report
snapshots are applied retrospectively. Therefore that scenario measures how
the rules would have behaved under stated proxies; it does not establish a
tradable point-in-time return. See [the backtest report](backtest_2026.md).

## 5. October 14 replay data gaps

The October 14 export contains USD `Price:D-1` and `Market Cap:D-1` but also a
mixed-time intraday `Price`. The replay uses `Price:D-1` for the October 13
completed-close signal. Its `BEst EPS BF12M` is a forward-12-month USD metric,
not the FY1 series in the older history, so it is **not** mixed into the EPS
revision. The comparable FY1 and complete 5/20 share-volume windows end on
October 7. October 8–9 share volumes were not supplied; October 10–11 were the
weekend. A sensitivity that adds October 12–13 volumes while skipping 8–9
changes four of the five target names. Treat that day's five-stock list as
indicative until the missing fields are supplied.
