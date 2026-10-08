# WLS Stock Screener

A small, reproducible Python project for ranking stocks in a one-month trading competition.

The project creates two lists:

- **Screen A:** core momentum stocks with improving earnings expectations and price confirmation.
- **Screen B:** high-upside stocks with a near earnings event, high volatility, and positive short-term confirmation.

The code was written for a Bloomberg workbook with three sheets:

- `Main`
- `Prices`
- `Turnover`

It produces full rankings, Top-N lists, an Excel report, CSV files, and a JSON run record.

## 1. Project structure

```text
wls-stock-screener/
├── README.md
├── pyproject.toml
├── requirements.txt
├── run_screener.py
├── src/
│   └── wls_screener/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── data.py
│       ├── export.py
│       ├── features.py
│       ├── pipeline.py
│       └── ranking.py
└── tests/
    └── test_core.py
```

## 2. Installation

### Simple setup

```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

### Install as a package

```bash
pip install -e .
```

After package installation, the command `wls-screener` is available.

## 3. Run the model

### Run directly from the repository

```bash
python run_screener.py \
  --input "WLS FIlter index2.xlsx" \
  --output-dir outputs \
  --as-of-date 2026-10-05
```

### Run after package installation

```bash
wls-screener \
  --input "WLS FIlter index2.xlsx" \
  --output-dir outputs \
  --as-of-date 2026-10-05 \
  --top-n 20
```

Passing `--as-of-date` is strongly recommended because Screen B depends on the number of business days to the next earnings date. If it is omitted, the program uses the workbook's modified date.

## 4. Expected input workbook

### `Main` sheet

The first 20 columns, A:T, are expected to contain the following data in this order:

1. Ticker
2. Company name
3. USD or common-currency price
4. 20-day average daily value traded
5. USD or common-currency market capitalization
6. Local market capitalization
7. Local price
8. P/E
9. Unused column
10. Sector
11. Next earnings date
12. 20-day volatility
13. 5-day average volume
14. 20-day average volume
15. Country
16. 5-day return
17. 3-month return
18. Current FY1 EPS consensus
19. FY1 EPS consensus 30 days ago
20. Existing EPS-change field, which is not used by the model

### `Prices` sheet

```text
Ticker | t-0 | t-1 | t-2 | ...
```

`t-0` is the latest price. The model requires 20 complete observations for MA20 and 50 complete observations for MA50.

### `Turnover` sheet

```text
Ticker | t-0 | t-1 | t-2 | ...
```

Turnover is used only as a diagnostic. It is not included in either score because it is usually very similar to the volume-ratio signal.

## 5. Sector percentile rank

Continuous features are compared within the same Bloomberg sector.

For stock `i`:

```text
PR(x_i) = (# values below x_i + 0.5 x # values equal to x_i) / N
```

The result lies between 0 and 1.

- `0.90` means the stock is above about 90% of stocks in the same sector.
- `0.50` is a neutral sector position.
- Missing feature values receive `0.50` by default.

## 6. Screen A

Screen A looks for stocks that are already strong and continue to receive positive confirmation.

### 6.1 Three-month momentum

```text
M3_i = sector percentile of Return 3M
```

### 6.2 Five-day continuation

```text
M5_i = sector percentile of Return 5D
```

### 6.3 EPS revision

The model does not use the workbook's existing EPS-change column. It calculates a symmetric revision:

```text
EPSRevision_i =
    (EPSNow_i - EPS30d_i)
    / (abs(EPSNow_i) + abs(EPS30d_i) + epsilon)
```

This is more stable when EPS is negative or close to zero.

```text
E_i = sector percentile of EPSRevision_i
```

### 6.4 Volume ratio

```text
VolumeRatio_i = AverageVolume5D_i / AverageVolume20D_i
```

```text
VR_i = sector percentile of VolumeRatio_i
```

### 6.5 Moving-average confirmation

```text
MA20_i = average of t-0 through t-19
D20_i  = LatestPrice_i / MA20_i - 1

MA50_i = average of t-0 through t-49
D50_i  = LatestPrice_i / MA50_i - 1
```

The model then calculates sector percentile ranks for `D20` and `D50`.

### 6.6 Price confirmation

```text
PriceConfirmationA_i =
    0.40 x PR(D20_i)
  + 0.30 x PR(D50_i)
  + 0.30 x PR(VolumeRatio_i)
```

### 6.7 Final Screen A score

```text
ScreenAScore_i =
    0.40 x PR(Return3M_i)
  + 0.25 x PR(EPSRevision_i)
  + 0.25 x PriceConfirmationA_i
  + 0.10 x PR(Return5D_i)
```

Screen A tie-breakers are:

1. Screen A score
2. 3-month momentum percentile
3. EPS-revision percentile
4. 20-day average daily value traded
5. Ticker

## 7. Screen B

Screen B looks for stocks that may make a large move during the competition period.

### 7.1 Business days to earnings

The program counts Monday-Friday business days from the model as-of date to the next earnings date. Local exchange holidays are not modeled separately.

### 7.2 Catalyst score

```text
0-5 business days:   1.00
6-10 business days:  0.75
11-15 business days: 0.50
Otherwise:           0.00
```

A catalyst score only says that an event is close. It does not say that the event will be positive.

### 7.3 Volatility rank

```text
VolRank_i = sector percentile of Bloomberg Vol 20D
```

### 7.4 Final Screen B score

```text
ScreenBScore_i =
    0.35 x CatalystScore_i
  + 0.30 x PR(Vol20D_i)
  + 0.20 x PR(Return5D_i)
  + 0.15 x PR(VolumeRatio_i)
```

Screen B tie-breakers are:

1. Screen B score
2. Catalyst score
3. 20-day volatility percentile
4. 5-day return percentile
5. 20-day average daily value traded
6. Ticker

## 8. Optional filter flag

The program calculates the following flag:

```text
Price >= USD 2
Market capitalization >= USD 300 million
ADV20 >= USD 5 million
```

This flag is diagnostic only. It does **not** remove stocks or change their rank.

## 9. Output files

A standard run creates:

```text
WLS_Screen_A_B_Rankings.xlsx
WLS_All_Rankings.csv
WLS_Screen_A_Top20.csv
WLS_Screen_B_Top20.csv
WLS_Run_Metadata.json
```

The Excel report contains:

- `Screen A Top`
- `Screen B Top`
- `All Rankings`
- `Methodology`
- `Data Quality`
- `Controls`

## 10. Important limitations

- The model uses a simple earnings-date catalyst, not a full qualitative event analysis.
- Screen B should be refreshed frequently because earnings dates and short-term prices change.
- A high ranking is a watchlist signal, not an automatic trade instruction.
- Sector percentile ranks control broad sector differences, but they do not neutralize country, currency, beta, or industry exposure.
- The current model does not use options data, short interest, guidance, news sentiment, or historical earnings gaps.

## 11. Tests

Install development dependencies and run:

```bash
pip install -e ".[dev]"
pytest
```
