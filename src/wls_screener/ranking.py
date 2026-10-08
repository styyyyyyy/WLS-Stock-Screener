"""Deterministic ranking rules for Screen A and Screen B."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ScreenerConfig


def _assign_rank(
    frame: pd.DataFrame,
    *,
    sort_columns: list[str],
    ascending: list[bool],
) -> pd.Series:
    """Return consecutive integer ranks after a stable multi-key sort."""

    ordered_index = frame.sort_values(
        sort_columns,
        ascending=ascending,
        kind="mergesort",
        na_position="last",
    ).index

    ranks = pd.Series(index=frame.index, dtype="int64")
    ranks.loc[ordered_index] = np.arange(1, len(frame) + 1, dtype=int)
    return ranks.astype(int)


def rank_screens(
    features: pd.DataFrame,
    *,
    config: ScreenerConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Assign Screen A and Screen B ranks and return their top-N tables.

    Tie-breakers
    ------------
    Screen A:
        score -> 3M percentile -> EPS revision percentile -> ADV20 -> ticker.

    Screen B:
        score -> catalyst -> volatility percentile -> 5D percentile -> ADV20
        -> ticker.
    """

    frame = features.copy()

    frame["ScreenARank"] = _assign_rank(
        frame,
        sort_columns=[
            "ScreenAScore",
            "RankReturn3M",
            "RankEPSRevision",
            "ADV20USD",
            "Ticker",
        ],
        ascending=[False, False, False, False, True],
    )

    frame["ScreenBRank"] = _assign_rank(
        frame,
        sort_columns=[
            "ScreenBScore",
            "CatalystScore",
            "RankVol20D",
            "RankReturn5D",
            "ADV20USD",
            "Ticker",
        ],
        ascending=[False, False, False, False, False, True],
    )

    top_a = frame.nsmallest(config.top_n, "ScreenARank").copy()
    top_b = frame.nsmallest(config.top_n, "ScreenBRank").copy()
    return frame, top_a, top_b


def validate_rankings(frame: pd.DataFrame) -> None:
    """Perform internal consistency checks before exporting results."""

    required = {
        "Ticker",
        "ScreenAScore",
        "ScreenBScore",
        "ScreenARank",
        "ScreenBRank",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Ranking output is missing columns: {sorted(missing)}")

    if frame["Ticker"].duplicated().any():
        duplicates = frame.loc[frame["Ticker"].duplicated(), "Ticker"].head().tolist()
        raise ValueError(f"Duplicate tickers remain after cleaning: {duplicates}")

    expected = set(range(1, len(frame) + 1))
    if set(frame["ScreenARank"]) != expected:
        raise ValueError("Screen A ranks are not a complete 1..N sequence.")
    if set(frame["ScreenBRank"]) != expected:
        raise ValueError("Screen B ranks are not a complete 1..N sequence.")

    for column in [
        "RankReturn3M",
        "RankReturn5D",
        "RankEPSRevision",
        "RankVolumeRatio",
        "RankDistanceMA20",
        "RankDistanceMA50",
        "RankVol20D",
        "PriceConfirmationA",
        "ScreenAScore",
        "ScreenBScore",
    ]:
        if not frame[column].between(0.0, 1.0, inclusive="both").all():
            raise ValueError(f"Column {column} contains values outside [0, 1].")
