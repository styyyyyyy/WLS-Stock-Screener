"""Portable checks for the five-workbook replay's easy-to-misread inputs."""

import math
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

import numpy as np
from openpyxl import Workbook

from wls_screener.current_snapshot import (
    _recent_business_days,
    _three_month_return,
    current_key_map,
    date_value,
    infer_closed_exchanges,
    investable_gates,
    read_worksheet,
    signal_close_usd,
)


class CurrentSnapshotTests(unittest.TestCase):
    def test_signal_uses_completed_close_and_strict_usd_gates(self) -> None:
        row = {"Price": 99.0, "Price:D-1": 1.00}
        self.assertEqual(signal_close_usd(row), 1.00)
        gates = investable_gates(
            close_usd=signal_close_usd(row), adv_usd=15_000_000.0,
            cap_usd=500_000_000.0, sector="Information Technology", has_history=True,
        )
        self.assertFalse(gates["price_gate"])
        self.assertFalse(gates["adv_gate"])
        self.assertFalse(gates["cap_gate"])
        self.assertTrue(all(investable_gates(
            close_usd=1.01, adv_usd=15_000_001.0, cap_usd=500_000_001.0,
            sector="Industrials", has_history=True,
        ).values()))
        self.assertFalse(investable_gates(
            close_usd=1.01, adv_usd=15_000_001.0, cap_usd=500_000_001.0,
            sector="Unknown", has_history=True,
        )["sector_gate"])

    def test_known_ticker_alias_is_one_to_one(self) -> None:
        self.assertEqual(current_key_map(["TCBI UW Equity", "MAT UW Equity"]), {
            "TCBI VT Equity": "TCBI UW Equity", "MAT UW Equity": "MAT UW Equity",
        })
        with self.assertRaisesRegex(ValueError, "collision"):
            current_key_map(["TCBI UW Equity", "TCBI VT Equity"])

    def test_exchange_closure_requires_group_carry_forward(self) -> None:
        pairs = [("BS", 10.0 + i, 10.0 + i) for i in range(6)]
        pairs += [("UW", 10.0 + i, 11.0 + i) for i in range(6)]
        pairs += [("TT", 10.0, 10.0)]  # one unchanged security is inconclusive
        closed, audit = infer_closed_exchanges(pairs)
        self.assertEqual(closed, {"BS"})
        self.assertEqual(next(row for row in audit if row["exchange"] == "BS")["paired"], 6)

    def test_replay_dates_and_expected_report_formats(self) -> None:
        self.assertEqual(_recent_business_days(date(2026, 10, 13)), (
            date(2026, 10, 8), date(2026, 10, 9), date(2026, 10, 12),
        ))
        self.assertEqual(date_value(20261021), date(2026, 10, 21))
        self.assertEqual(date_value(datetime(2026, 10, 21, 14, 0)), date(2026, 10, 21))
        self.assertIsNone(date_value("--"))

    def test_three_month_return_anchors_to_signal_close(self) -> None:
        # The next-day decision is October 15, but the completed signal close
        # is October 14. July 14 and July 15 deliberately have different prices.
        trade_dates = [date(2026, 7, 14), date(2026, 7, 15), date(2026, 10, 14)]
        self.assertAlmostEqual(
            _three_month_return(
                np.array([80.0, 100.0, 120.0]), trade_dates, date(2026, 10, 14),
            ),
            0.5,
        )
        self.assertTrue(math.isnan(_three_month_return(
            np.array([100.0, 120.0]), trade_dates[1:], date(2026, 10, 14),
        )))

    def test_worksheet_header_newlines_and_missing_fields(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Worksheet"
        sheet.append(["Ticker", "Name", "Price\n", "Price:D-1\n"])
        sheet.append(["MAT UW Equity", "Mattel", 100.0, 99.0])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "snapshot.xlsx"
            workbook.save(path)
            self.assertEqual(read_worksheet(path, ("Ticker", "Name", "Price:D-1"))[
                "MAT UW Equity"]["Price:D-1"], 99.0)
            with self.assertRaisesRegex(ValueError, "missing columns"):
                read_worksheet(path, ("Ticker", "Exp Rep Dt"))


if __name__ == "__main__":
    unittest.main()
