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


def select_targets(
    rankings: pd.DataFrame,
    *,
    config: ScreenerConfig,
) -> pd.DataFrame:
    """Select three A names, then the two best distinct B names by default.

    Selection uses the full eligible ranking, not just a possibly shortened
    Top-N presentation table. A Screen B name already selected by Screen A is
    skipped, rather than double-weighted.
    """

    target_count = config.target_a_count + config.target_b_count
    if len(rankings) < target_count:
        raise ValueError(
            f"Cannot fill {target_count} distinct positions from "
            f"{len(rankings)} eligible WLS names."
        )

    selected_a = rankings.nsmallest(config.target_a_count, "ScreenARank").copy()
    selected_b = (
        rankings.loc[~rankings["Ticker"].isin(selected_a["Ticker"])]
        .nsmallest(config.target_b_count, "ScreenBRank")
        .copy()
    )

    selected_a["Sleeve"] = "A"
    selected_b["Sleeve"] = "B"
    selected_a["SleeveRank"] = np.arange(1, len(selected_a) + 1, dtype=int)
    selected_b["SleeveRank"] = np.arange(1, len(selected_b) + 1, dtype=int)
    selected_a["SelectionRank"] = selected_a["ScreenARank"]
    selected_b["SelectionRank"] = selected_b["ScreenBRank"]
    selected_a["SelectionScore"] = selected_a["ScreenAScore"]
    selected_b["SelectionScore"] = selected_b["ScreenBScore"]
    targets = pd.concat([selected_a, selected_b], ignore_index=True)
    targets["TargetWeight"] = config.target_weight

    if targets["Ticker"].duplicated().any():
        raise ValueError("Portfolio targets must have distinct tickers.")
    if abs(float(targets["TargetWeight"].sum()) - 1.0) > 1e-9:
        raise ValueError("Portfolio target weights must sum to 100%.")
    return targets


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
