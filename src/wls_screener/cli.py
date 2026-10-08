"""Command-line interface for the WLS stock screener."""

from __future__ import annotations

import argparse
import logging
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .config import ScreenerConfig
from .export import export_results
from .pipeline import run_screening


LOGGER = logging.getLogger("wls_screener")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wls-screener",
        description=(
            "Calculate Screen A momentum rankings and Screen B catalyst-volatility "
            "rankings from the Bloomberg WLS workbook."
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to the input .xlsx workbook.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for Excel, CSV, and JSON outputs. Default: ./outputs",
    )
    parser.add_argument(
        "--as-of-date",
        default=None,
        help=(
            "Model date in YYYY-MM-DD format. If omitted, the workbook's modified "
            "date is used. Passing this explicitly is recommended."
        ),
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of stocks to retain in each top list. Default: 20",
    )
    parser.add_argument(
        "--prefix",
        default="WLS",
        help="Filename prefix for exported files. Default: WLS",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity. Default: INFO",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s | %(message)s",
    )

    config = replace(ScreenerConfig(), top_n=args.top_n)

    LOGGER.info("Reading workbook: %s", args.input)
    result = run_screening(
        args.input,
        as_of_date=args.as_of_date,
        config=config,
    )

    LOGGER.info(
        "Loaded %s stocks across %s sectors. Model as-of date: %s",
        f"{len(result.all_rankings):,}",
        result.quality_summary["sector_count"],
        result.as_of_date.strftime("%Y-%m-%d"),
    )

    today = pd.Timestamp.today().normalize()
    age_days = int((today - result.as_of_date).days)
    if age_days > 0:
        LOGGER.warning(
            "The input snapshot is %d calendar day(s) old. Screen B should be "
            "refreshed before trading because event timing changes quickly.",
            age_days,
        )

    paths = export_results(result, args.output_dir, prefix=args.prefix)
    for label, path in paths.items():
        LOGGER.info("%-14s %s", label + ":", path)

    LOGGER.info("Screen A top ticker: %s", result.screen_a_top.iloc[0]["Ticker"])
    LOGGER.info("Screen B top ticker: %s", result.screen_b_top.iloc[0]["Ticker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
