from __future__ import annotations

import numpy as np
import pandas as pd

from wls_screener.config import ScreenerConfig
from wls_screener.data import parse_scaled_number
from wls_screener.features import mid_percentile


def test_parse_scaled_number() -> None:
    assert parse_scaled_number("43.75M") == 43_750_000.0
    assert parse_scaled_number("21.52B") == 21_520_000_000.0
    assert parse_scaled_number("1.5T") == 1_500_000_000_000.0
    assert parse_scaled_number(12.5) == 12.5
    assert np.isnan(parse_scaled_number("not a number"))


def test_mid_percentile_without_ties() -> None:
    values = pd.Series([10.0, 20.0, 30.0])
    result = mid_percentile(values)
    expected = pd.Series([1 / 6, 3 / 6, 5 / 6])
    pd.testing.assert_series_equal(result, expected)


def test_mid_percentile_with_ties_and_missing() -> None:
    values = pd.Series([10.0, 10.0, 30.0, np.nan])
    result = mid_percentile(values, missing_value=0.50)
    expected = pd.Series([1 / 3, 1 / 3, 5 / 6, 0.50])
    pd.testing.assert_series_equal(result, expected)


def test_default_weight_sums() -> None:
    config = ScreenerConfig()
    config.validate()
