"""The pipeline must reproduce the paper exactly when fed the paper's own data
(the USITC DataWeb export pulled on Aug 12, 2026). Run:  python -m unittest -v"""
import csv
import unittest
from pathlib import Path

from pipeline import config
from pipeline.checks import run_checks
from pipeline.index import Report, compute, load_weights, report_for
from pipeline.sources import read_dataweb_excel

FIXTURE = Path(__file__).parent / "fixtures" / "dataweb_export_2026-08-12.xlsx"


class ReproducesPaper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports = load_weights(config.WEIGHTS)
        names = {name: code for code, (name, _) in cls.reports[0].shares.items()}
        cls.raw = read_dataweb_excel(FIXTURE, names)
        cls.rows = compute(cls.raw, cls.reports)
        cls.by = {r["month"]: r for r in cls.rows}
        with open(config.PAPER_VINTAGE, newline="", encoding="utf-8") as f:
            cls.paper = list(csv.DictReader(f))

    def test_54_months(self):
        self.assertEqual(len(self.rows), 54)
        self.assertEqual(self.rows[0]["month"], "2022-01")
        self.assertEqual(self.rows[-1]["month"], "2026-06")

    def test_every_month_matches_paper_calculation_file(self):
        for p in self.paper:
            r = self.by[p["month"]]
            for k in ("small_rate_pct", "large_rate_pct", "gap_pp"):
                self.assertAlmostEqual(r[k], float(p[k]), places=5, msg=f"{p['month']} {k}")

    def test_headline_numbers(self):
        peak = max(self.rows, key=lambda r: r["gap_pp"])
        self.assertEqual(peak["month"], "2025-05")
        self.assertAlmostEqual(peak["gap_pp"], 2.74, places=2)
        self.assertAlmostEqual(peak["small_rate_pct"], 19.66, places=2)
        self.assertAlmostEqual(peak["large_rate_pct"], 16.93, places=2)
        base = [r["gap_pp"] for r in self.rows if r["month"] <= "2024-12"]
        self.assertAlmostEqual(sum(base) / len(base), 1.01, places=2)
        after = [r["gap_pp"] for r in self.rows if "2025-03" <= r["month"] <= "2026-06"]
        self.assertAlmostEqual(sum(after) / len(after), 2.03, places=2)
        self.assertAlmostEqual(self.by["2026-06"]["gap_pp"], 1.20, places=2)
        self.assertAlmostEqual(self.by["2025-01"]["small_value_usd"] / 1e9, 11.03, places=2)

    def test_coverage_2025_is_88_2_percent(self):
        yr = [r for r in self.rows if r["month"].startswith("2025")]
        cov = sum(r["covered_value_usd"] for r in yr) / sum(r["district_value_usd"] for r in yr) * 100
        self.assertAlmostEqual(cov, 88.16, places=2)

    def test_china_may_2025_raw_numbers(self):
        china = [r for r in self.raw if r["month"] == "2025-05" and r["country"] == "China"][0]
        self.assertEqual(china["customs_value"], 3_917_409_664)
        self.assertEqual(china["calculated_duties"], 2_339_771_002)

    def test_checks_pass(self):
        errors, _ = run_checks(self.rows, self.raw, self.reports)
        self.assertEqual(errors, [])


class NewSharesApplyOnlyFromReleaseOnward(unittest.TestCase):
    def test_switch(self):
        old = Report("old", "2026-05-05", "2022-01", {"A": ("A", 0.5)})
        new = Report("new", "2027-05-04", "2027-05", {"A": ("A", 0.1)})
        self.assertIs(report_for("2027-04", [old, new]), old)
        self.assertIs(report_for("2027-05", [old, new]), new)
        self.assertIs(report_for("2030-01", [old, new]), new)


if __name__ == "__main__":
    unittest.main()
