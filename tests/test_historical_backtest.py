"""Behavioral checks for the retrospective daily-close engine."""

from __future__ import annotations

import copy
import csv
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
from historical_backtest import (  # noqa: E402
    FeatureBank,
    Inputs,
    execute,
    load_filter_snapshot,
    select_five,
    weighted_wls_proxy,
)


def sample_inputs() -> Inputs:
    dates = [stamp.date() for stamp in pd.bdate_range("2026-06-01", periods=82)]
    tickers = [f"S{i} US Equity" for i in range(6)]
    steps = np.arange(len(dates), dtype=float)
    prices = np.array([20 + i + steps * (0.10 + i * 0.03) for i in range(6)])
    eps = np.array([1 + i * 0.1 + steps * (0.001 + i * 0.0003) for i in range(6)])
    volume = np.full_like(prices, 1_000_000.0)
    return Inputs(
        dates=dates, tickers=tickers, prices=prices, eps=eps, volume=volume,
        metadata={t: {"name": t, "currency": "USD"} for t in tickers},
        earnings={t: date(2026, 9, 15) for t in tickers},
        weights={t: 1.0 for t in tickers},
        sectors={t: "Technology" for t in tickers},
        eligible=set(tickers), snapshot_date=date(2026, 9, 1),
    )


def test_signal_uses_no_future_price_volume_or_eps() -> None:
    original = sample_inputs()
    signal = original.dates[70]
    baseline = FeatureBank(original).ranked(signal).sort_values("ticker").reset_index(drop=True)
    changed = copy.deepcopy(original)
    changed.prices[:, 71:] *= 100
    changed.eps[:, 71:] *= -500
    changed.volume[:, 71:] *= 20
    after = FeatureBank(changed).ranked(signal).sort_values("ticker").reset_index(drop=True)
    pd.testing.assert_frame_equal(baseline, after)


def test_selection_is_three_a_two_distinct_b_equal_weight() -> None:
    frame = FeatureBank(sample_inputs()).ranked(sample_inputs().dates[70])
    selected = select_five(frame)
    assert selected.screen.tolist() == ["A", "A", "A", "B", "B"]
    assert len(set(selected.ticker)) == 5
    assert selected.target_weight.tolist() == [0.20] * 5


def test_closed_market_position_is_frozen_then_sold_when_reopened() -> None:
    data = sample_inputs()
    first_signal = data.dates[69]
    first_execution = data.dates[70]
    closed_day = data.dates[71]
    reopen_day = data.dates[72]
    frozen_ticker = data.tickers[0]
    data.volume[0, 71] = 0.0
    signals = {
        first_signal: data.tickers[:5],
        first_execution: data.tickers[1:6],
    }
    bank = FeatureBank(data)
    daily, trades = execute(data, bank, signals, first_execution, reopen_day)
    assert daily[0]["positions_after_rebalance"] == 5
    assert daily[1]["frozen_positions_after_rebalance"] == 1
    assert not any(t["ticker"] == frozen_ticker and t["date"] == closed_day.isoformat()
                   for t in trades)
    assert any(t["ticker"] == frozen_ticker and t["date"] == reopen_day.isoformat()
               and t["side"] == "SELL" for t in trades)


def test_snapshot_filter_has_strict_thresholds_and_eligible_mode(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.csv"
    with metrics.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["Ticker", "PriceD1USD", "ADV20USD", "MarketCapUSD"])
        writer.writeheader()
        writer.writerows([
            {"Ticker": "PASS", "PriceD1USD": 1.01, "ADV20USD": 15_000_001, "MarketCapUSD": 500_000_001},
            {"Ticker": "PRICE_EQ", "PriceD1USD": 1, "ADV20USD": 20_000_000, "MarketCapUSD": 600_000_000},
            {"Ticker": "ADV_EQ", "PriceD1USD": 2, "ADV20USD": 15_000_000, "MarketCapUSD": 600_000_000},
            {"Ticker": "CAP_EQ", "PriceD1USD": 2, "ADV20USD": 20_000_000, "MarketCapUSD": 500_000_000},
            {"Ticker": "MISSING", "PriceD1USD": "", "ADV20USD": 20_000_000, "MarketCapUSD": 600_000_000},
        ])
    eligible, audit = load_filter_snapshot(metrics, "metrics")
    assert eligible == {"PASS"}
    assert audit["rows_with_missing_metrics"] == 1
    assert audit["strict_thresholds"]["adv20_usd_gt"] == 15_000_000

    cohort = tmp_path / "eligible.csv"
    cohort.write_text("Ticker\nPASS\nPRICE_EQ\n", encoding="utf-8")
    selected, cohort_audit = load_filter_snapshot(cohort, "eligible")
    assert selected == {"PASS", "PRICE_EQ"}
    assert cohort_audit["mode"] == "eligible_snapshot_proxy"


def test_snapshot_cohort_restricts_ranked_universe() -> None:
    data = sample_inputs()
    data.eligible.remove(data.tickers[-1])
    frame = FeatureBank(data).ranked(data.dates[70])
    assert set(frame.ticker) == data.eligible
    assert len(select_five(frame)) == 5


def test_wls_reference_uses_weights_from_full_universe() -> None:
    data = sample_inputs()
    data.weights = {ticker: 1.0 for ticker in data.tickers}
    data.weights[data.tickers[-1]] = 90.0
    bank = FeatureBank(data)
    first, last = data.dates[70], data.dates[72]
    reference = weighted_wls_proxy(data, bank, first, last)
    equal_weight_return = np.mean(data.prices[:, 72] / data.prices[:, 70])
    assert reference[0]["snapshot_weighted_proxy_nav"] == pytest.approx(1.0)
    assert reference[-1]["snapshot_weighted_proxy_nav"] != pytest.approx(equal_weight_return)
    assert reference[-1]["constituent_count"] == 6


def test_filter_rejects_duplicate_ticker(tmp_path: Path) -> None:
    path = tmp_path / "dupes.csv"
    path.write_text("Ticker\nS1\nS1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_filter_snapshot(path, "eligible")
