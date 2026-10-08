"""End-to-end screening pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import ScreenerConfig
from .data import infer_as_of_date, load_source_data
from .features import build_quality_summary, compute_features
from .ranking import rank_screens, validate_rankings


@dataclass
class ScreeningResult:
    """All model outputs produced by one screening run."""

    all_rankings: pd.DataFrame
    screen_a_top: pd.DataFrame
    screen_b_top: pd.DataFrame
    quality_summary: dict[str, object]
    as_of_date: pd.Timestamp
    input_path: Path
    config: ScreenerConfig


def run_screening(
    input_path: str | Path,
    *,
    as_of_date: str | pd.Timestamp | None = None,
    config: ScreenerConfig | None = None,
) -> ScreeningResult:
    """Load the workbook, calculate features, and rank both screens."""

    source = Path(input_path).expanduser().resolve()
    model_config = config or ScreenerConfig()
    model_config.validate()

    resolved_date = infer_as_of_date(source, as_of_date)
    main, prices, turnover = load_source_data(source)

    features = compute_features(
        main,
        prices,
        turnover,
        as_of_date=resolved_date,
        config=model_config,
    )
    all_rankings, top_a, top_b = rank_screens(features, config=model_config)
    validate_rankings(all_rankings)

    quality = build_quality_summary(all_rankings)
    quality["as_of_date"] = resolved_date.strftime("%Y-%m-%d")
    quality["input_file"] = source.name

    return ScreeningResult(
        all_rankings=all_rankings,
        screen_a_top=top_a,
        screen_b_top=top_b,
        quality_summary=quality,
        as_of_date=resolved_date,
        input_path=source,
        config=model_config,
    )
