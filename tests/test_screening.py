from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from wls_screener.config import ScreenerConfig
from wls_screener.features import build_filter_audit, build_filter_counts
from wls_screener.pipeline import run_screening
from wls_screener.ranking import select_targets


def test_strict_filter_excludes_boundaries_and_missing_values() -> None:
    main = pd.DataFrame(
        {
            "Ticker": ["PASS", "PRICE", "ADV", "CAP", "MISSING"],
            "Name": ["Pass", "Price", "ADV", "Cap", "Missing"],
            "Sector": ["Tech"] * 5,
            "Country": ["US"] * 5,
            "PriceUSD": [1.01, 1.00, 2.00, 2.00, pd.NA],
            "ADV20USD": [15_000_001, 20_000_000, 15_000_000, 20_000_000, 20_000_000],
            "MarketCapUSD": [500_000_001, 700_000_000, 700_000_000, 500_000_000, 700_000_000],
        }
    )

    audit = build_filter_audit(main, ScreenerConfig())
    assert audit.loc[audit["PassesUniverseFilter"], "Ticker"].tolist() == ["PASS"]
    assert audit.loc[audit["Ticker"].eq("PRICE"), "FilterFailureReasons"].item() == "price_usd"
    assert audit.loc[audit["Ticker"].eq("ADV"), "FilterFailureReasons"].item() == "adv20_usd"
    assert audit.loc[audit["Ticker"].eq("CAP"), "FilterFailureReasons"].item() == "market_cap_usd"
    assert build_filter_counts(audit)["eligible_universe_size"] == 1


def test_pipeline_filters_before_sector_percentiles() -> None:
    tickers = [f"OK{i}" for i in range(5)] + ["REJECT", "NOSECTOR"]
    main = pd.DataFrame(
        {
            "Ticker": tickers,
            "Name": tickers,
            "Sector": ["Tech"] * 6 + ["Unknown"],
            "Country": ["US"] * 7,
            "PriceUSD": [5.0] * 5 + [0.50, 5.0],
            "ADV20USD": [20_000_000.0] * 7,
            "MarketCapUSD": [700_000_000.0] * 7,
            "NextEarning": ["20/10/2026"] * 7,
            "AvgVol5D": [200.0] * 7,
            "AvgVol20D": [100.0] * 7,
            "EPSNow": [2.0] * 7,
            "EPS30d": [1.0] * 7,
            "Return3M": [1, 2, 3, 4, 5, 1000, 2000],
            "Return5D": [1, 2, 3, 4, 5, 1000, 2000],
            "Vol20D": [1, 2, 3, 4, 5, 1000, 2000],
        }
    )
    prices = pd.DataFrame(
        {f"t-{day}": [100.0 + 0.1 * i for i in range(7)] for day in range(50)},
        index=tickers,
    )
    turnover = pd.DataFrame(
        {f"t-{day}": [100.0] * 7 for day in range(20)},
        index=tickers,
    )

    with patch("wls_screener.pipeline.load_source_data", return_value=(main, prices, turnover)):
        result = run_screening("synthetic.xlsx", as_of_date="2026-10-14")

    assert len(result.filter_audit) == 7
    assert len(result.all_rankings) == 5
    assert "REJECT" not in result.all_rankings["Ticker"].tolist()
    assert "NOSECTOR" not in result.all_rankings["Ticker"].tolist()
    ranks = result.all_rankings.set_index("Ticker")["RankReturn3M"]
    assert ranks.loc["OK0"] == 0.1
    assert ranks.loc["OK4"] == 0.9
    assert result.quality_summary["input_wls_universe_size"] == 7
    assert result.quality_summary["eligible_universe_size"] == 6
    assert result.quality_summary["scored_universe_size"] == 5
    assert result.quality_summary["eligible_without_gics_sector"] == 1


def test_missing_gics_sectors_keep_numeric_pass_in_audit() -> None:
    sectors = ["Technology", "Unknown", "--", "", pd.NA]
    main = pd.DataFrame(
        {
            "Ticker": list("ABCDE"),
            "Name": list("ABCDE"),
            "Sector": sectors,
            "Country": ["US"] * 5,
            "PriceUSD": [2.0] * 5,
            "ADV20USD": [20_000_000.0] * 5,
            "MarketCapUSD": [800_000_000.0] * 5,
        }
    )

    audit = build_filter_audit(main, ScreenerConfig())
    counts = build_filter_counts(audit)
    assert counts["eligible_universe_size"] == 5
    assert counts["scored_universe_size"] == 1
    assert counts["eligible_without_gics_sector"] == 4
    assert audit.loc[audit["PassesScoringUniverse"], "Ticker"].tolist() == ["A"]
    assert audit.loc[audit["Ticker"].eq("B"), "FilterFailureReasons"].item() == "gics_sector"


def test_a3_b2_targets_are_distinct_and_equal_weighted() -> None:
    rankings = pd.DataFrame(
        {
            "Ticker": ["A", "B", "C", "D", "E", "F"],
            "ScreenARank": [1, 2, 3, 4, 5, 6],
            "ScreenBRank": [2, 1, 3, 4, 5, 6],
            "ScreenAScore": [.99, .98, .97, .96, .95, .94],
            "ScreenBScore": [.98, .99, .97, .96, .95, .94],
        }
    )

    targets = select_targets(rankings, config=ScreenerConfig(top_n=2))
    assert targets["Ticker"].tolist() == ["A", "B", "C", "D", "E"]
    assert targets["Sleeve"].tolist() == ["A", "A", "A", "B", "B"]
    assert targets["TargetWeight"].tolist() == [0.2] * 5
    assert targets["Ticker"].is_unique
