"""Feature engineering for Screen A and Screen B."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ScreenerConfig


def build_filter_audit(main: pd.DataFrame, config: ScreenerConfig) -> pd.DataFrame:
    """Audit the strict Bloomberg WLS investability gates for every input name.

    The input ``Main`` sheet is assumed to be the point-in-time WLS universe.
    All three numeric gates are strict; a missing or nonfinite value fails.
    The three-gate pass count is kept separate from the number with a usable
    GICS sector. Ranking uses ``PassesScoringUniverse``, so no synthetic
    ``Unknown`` sector enters a percentile denominator.
    """

    columns = [
        "Ticker", "Name", "Sector", "Country", "PriceUSD", "ADV20USD", "MarketCapUSD"
    ]
    audit = main.loc[:, columns].copy()

    for source, output, threshold in (
        ("PriceUSD", "PassPriceUSD", config.min_price_usd),
        ("ADV20USD", "PassADV20USD", config.min_adv20_usd),
        ("MarketCapUSD", "PassMarketCapUSD", config.min_market_cap_usd),
    ):
        values = pd.to_numeric(audit[source], errors="coerce").astype(float)
        audit[output] = values.gt(threshold) & np.isfinite(values)

    audit["PassPriceAndADV"] = audit["PassPriceUSD"] & audit["PassADV20USD"]
    audit["PassesUniverseFilter"] = (
        audit["PassPriceAndADV"] & audit["PassMarketCapUSD"]
    )

    sector_text = audit["Sector"].astype("string").str.strip().str.lower()
    invalid_sectors = {"", "--", "unknown", "n/a", "na", "none", "null", "nan"}
    audit["PassGICSSector"] = sector_text.notna() & ~sector_text.isin(invalid_sectors)
    audit["PassesScoringUniverse"] = (
        audit["PassesUniverseFilter"] & audit["PassGICSSector"]
    )

    flags = ("PassPriceUSD", "PassADV20USD", "PassMarketCapUSD", "PassGICSSector")
    labels = ("price_usd", "adv20_usd", "market_cap_usd", "gics_sector")
    audit["FilterFailureReasons"] = [
        ";".join(label for flag, label in zip(flags, labels) if not row[flag])
        for _, row in audit[list(flags)].iterrows()
    ]
    return audit


def build_filter_counts(audit: pd.DataFrame) -> dict[str, int]:
    """Return stage counts for the 10k-to-5k universe reduction."""

    return {
        "input_wls_universe_size": int(len(audit)),
        "pass_price_usd_count": int(audit["PassPriceUSD"].sum()),
        "pass_price_and_adv20_usd_count": int(audit["PassPriceAndADV"].sum()),
        "eligible_universe_size": int(audit["PassesUniverseFilter"].sum()),
        "eligible_with_valid_gics_sector": int(audit["PassesScoringUniverse"].sum()),
        "eligible_without_gics_sector": int(
            (audit["PassesUniverseFilter"] & ~audit["PassGICSSector"]).sum()
        ),
        "scored_universe_size": int(audit["PassesScoringUniverse"].sum()),
        "fail_price_usd_count": int((~audit["PassPriceUSD"]).sum()),
        "fail_adv20_usd_count": int((~audit["PassADV20USD"]).sum()),
        "fail_market_cap_usd_count": int((~audit["PassMarketCapUSD"]).sum()),
    }


def mid_percentile(
    series: pd.Series,
    *,
    missing_value: float = 0.50,
) -> pd.Series:
    """Calculate a mid-percentile rank on valid observations.

    For a valid observation ``x_i`` in a group of size ``N``:

    ``PR(x_i) = (# lower + 0.5 * # equal) / N``

    This is equivalent to ``(average_rank - 0.5) / N``. Missing observations
    receive the neutral score supplied by ``missing_value``.
    """

    valid = series.dropna()
    output = pd.Series(np.nan, index=series.index, dtype=float)

    if not valid.empty:
        average_rank = valid.rank(method="average", ascending=True)
        output.loc[valid.index] = (average_rank - 0.5) / len(valid)

    return output.fillna(missing_value)


def add_sector_percentile(
    frame: pd.DataFrame,
    source_column: str,
    output_column: str,
    *,
    missing_value: float,
) -> None:
    """Add a within-sector percentile column to ``frame`` in place."""

    frame[output_column] = frame.groupby(
        "Sector",
        dropna=False,
        group_keys=False,
    )[source_column].transform(
        lambda values: mid_percentile(values, missing_value=missing_value)
    )


def _available_window_columns(
    panel: pd.DataFrame,
    window: int,
) -> list[str] | None:
    required = [f"t-{offset}" for offset in range(window)]
    return required if all(column in panel.columns for column in required) else None


def _panel_average(
    panel: pd.DataFrame,
    window: int,
    *,
    require_complete_window: bool,
) -> pd.Series:
    columns = _available_window_columns(panel, window)
    if columns is None:
        return pd.Series(np.nan, index=panel.index, dtype=float)

    return panel[columns].mean(
        axis=1,
        skipna=not require_complete_window,
    )


def _days_to_event(
    event_dates: pd.Series,
    as_of_date: pd.Timestamp,
) -> pd.Series:
    """Count Monday-Friday business days from ``as_of_date`` to each event."""

    output = pd.Series(np.nan, index=event_dates.index, dtype=float)
    valid = event_dates.notna()
    if not valid.any():
        return output

    start = np.datetime64(as_of_date.date(), "D")
    end = event_dates.loc[valid].dt.normalize().values.astype("datetime64[D]")
    output.loc[valid] = np.busday_count(start, end)
    return output


def _catalyst_score(days: pd.Series, config: ScreenerConfig) -> pd.Series:
    conditions = [
        days.between(0, config.catalyst_near_max_days),
        days.between(
            config.catalyst_near_max_days + 1,
            config.catalyst_medium_max_days,
        ),
        days.between(
            config.catalyst_medium_max_days + 1,
            config.catalyst_far_max_days,
        ),
    ]
    scores = [
        config.catalyst_near_score,
        config.catalyst_medium_score,
        config.catalyst_far_score,
    ]
    return pd.Series(
        np.select(conditions, scores, default=0.0),
        index=days.index,
        dtype=float,
    )


def compute_features(
    main: pd.DataFrame,
    prices: pd.DataFrame,
    turnover: pd.DataFrame,
    *,
    as_of_date: pd.Timestamp,
    config: ScreenerConfig,
) -> pd.DataFrame:
    """Create all raw and ranked features used by both screens."""

    config.validate()
    if not build_filter_audit(main, config)["PassesScoringUniverse"].all():
        raise ValueError(
            "compute_features requires a prefiltered WLS universe with valid GICS sectors."
        )
    frame = main.copy()

    # ------------------------------------------------------------------
    # Event timing
    # ------------------------------------------------------------------
    frame["NextEarningDate"] = pd.to_datetime(
        frame["NextEarning"],
        dayfirst=True,
        errors="coerce",
    )
    frame["DaysToEarnings"] = _days_to_event(
        frame["NextEarningDate"],
        as_of_date,
    )
    frame["CatalystScore"] = _catalyst_score(
        frame["DaysToEarnings"],
        config,
    )

    # ------------------------------------------------------------------
    # Price-based moving averages
    # ------------------------------------------------------------------
    frame["PriceHistoryCount"] = frame["Ticker"].map(prices.notna().sum(axis=1))
    frame["Price_t0"] = frame["Ticker"].map(prices["t-0"])

    for window in (config.ma_short_window, config.ma_long_window):
        moving_average = _panel_average(
            prices,
            window,
            require_complete_window=True,
        )
        distance = prices["t-0"] / moving_average - 1.0
        frame[f"MA{window}"] = frame["Ticker"].map(moving_average)
        frame[f"DistanceMA{window}"] = frame["Ticker"].map(distance)

    # ------------------------------------------------------------------
    # Trading-activity features
    # ------------------------------------------------------------------
    frame["VolumeRatio5D20D"] = (
        frame["AvgVol5D"] / frame["AvgVol20D"].replace(0.0, np.nan)
    )

    turnover_recent = _panel_average(
        turnover,
        config.recent_window,
        require_complete_window=False,
    )
    turnover_normal = _panel_average(
        turnover,
        config.normal_window,
        require_complete_window=False,
    )
    turnover_ratio = turnover_recent / turnover_normal.replace(0.0, np.nan)
    frame["TurnoverRatio5D20D"] = frame["Ticker"].map(turnover_ratio)

    # ------------------------------------------------------------------
    # Analyst estimate revision
    # ------------------------------------------------------------------
    # Symmetric percentage change is bounded approximately by [-1, 1] and is
    # more stable than the usual percentage change when EPS is negative or
    # close to zero.
    denominator = frame["EPSNow"].abs() + frame["EPS30d"].abs() + 1e-12
    frame["EPSRevision"] = (frame["EPSNow"] - frame["EPS30d"]) / denominator

    # The pipeline applies the numeric and GICS-sector gates first, so the
    # percentile denominator contains scored names only.
    frame["PassesUniverseFilter"] = True
    frame["PassesScoringUniverse"] = True

    # ------------------------------------------------------------------
    # Within-sector percentile ranks
    # ------------------------------------------------------------------
    percentile_features = {
        "Return3M": "RankReturn3M",
        "Return5D": "RankReturn5D",
        "EPSRevision": "RankEPSRevision",
        "VolumeRatio5D20D": "RankVolumeRatio",
        f"DistanceMA{config.ma_short_window}": "RankDistanceMA20",
        f"DistanceMA{config.ma_long_window}": "RankDistanceMA50",
        "Vol20D": "RankVol20D",
    }

    for source_column, output_column in percentile_features.items():
        add_sector_percentile(
            frame,
            source_column,
            output_column,
            missing_value=config.missing_percentile,
        )

    # ------------------------------------------------------------------
    # Screen A and Screen B scores
    # ------------------------------------------------------------------
    frame["PriceConfirmationA"] = (
        config.price_confirmation_ma20_weight * frame["RankDistanceMA20"]
        + config.price_confirmation_ma50_weight * frame["RankDistanceMA50"]
        + config.price_confirmation_volume_weight * frame["RankVolumeRatio"]
    )

    frame["ScreenAScore"] = (
        config.a_return_3m_weight * frame["RankReturn3M"]
        + config.a_eps_revision_weight * frame["RankEPSRevision"]
        + config.a_price_confirmation_weight * frame["PriceConfirmationA"]
        + config.a_return_5d_weight * frame["RankReturn5D"]
    )

    frame["ScreenBScore"] = (
        config.b_catalyst_weight * frame["CatalystScore"]
        + config.b_volatility_weight * frame["RankVol20D"]
        + config.b_return_5d_weight * frame["RankReturn5D"]
        + config.b_volume_weight * frame["RankVolumeRatio"]
    )

    frame["ModelAsOfDate"] = as_of_date.normalize()
    return frame


def build_quality_summary(frame: pd.DataFrame) -> dict[str, object]:
    """Return a compact, JSON-serializable data-quality summary."""

    correlation = frame[["TurnoverRatio5D20D", "VolumeRatio5D20D"]].corr().iloc[0, 1]

    return {
        "universe_size": int(len(frame)),
        "sector_count": int(frame["Sector"].nunique(dropna=False)),
        "country_count": int(frame["Country"].nunique(dropna=True)),
        "missing_return_3m": int(frame["Return3M"].isna().sum()),
        "missing_return_5d": int(frame["Return5D"].isna().sum()),
        "missing_eps_revision": int(frame["EPSRevision"].isna().sum()),
        "missing_next_earnings": int(frame["NextEarningDate"].isna().sum()),
        "missing_ma20": int(frame["DistanceMA20"].isna().sum()),
        "missing_ma50": int(frame["DistanceMA50"].isna().sum()),
        "missing_volatility_20d": int(frame["Vol20D"].isna().sum()),
        "events_0_to_5_business_days": int(frame["DaysToEarnings"].between(0, 5).sum()),
        "events_6_to_10_business_days": int(frame["DaysToEarnings"].between(6, 10).sum()),
        "events_11_to_15_business_days": int(frame["DaysToEarnings"].between(11, 15).sum()),
        "past_event_dates": int(frame["DaysToEarnings"].lt(0).sum()),
        "turnover_volume_ratio_correlation": (
            None if pd.isna(correlation) else float(correlation)
        ),
    }
