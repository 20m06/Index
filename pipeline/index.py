"""The calculation. Same formula as the paper (Section 4, Appendix C).

For each month t, over the countries c whose Census share is in effect that month:

    Small rate = sum(s_c * D_ct) / sum(s_c * V_ct) * 100
    Large rate = sum((1 - s_c) * D_ct) / sum((1 - s_c) * V_ct) * 100
    Gap        = Small rate - Large rate      (percentage points)

V = customs value, D = calculated duties, s = small-business (under 500 employees) share
of that country's import VALUE, from Census Table 5d.
"""
import csv
from collections import defaultdict
from dataclasses import dataclass, field

from .sources import TOTAL


@dataclass
class Report:
    """One Census Table 5d release and the months it applies to."""
    name: str
    release_date: str
    effective_from: str                       # first data month these shares apply to
    shares: dict = field(default_factory=dict)  # cty_code -> (country name, SME share)


def load_weights(path):
    """Read data/weights.csv. The SME share is computed here, never typed in by hand."""
    reports = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            known = float(row["known_value_musd"])
            large = float(row["large_500plus_musd"])
            if known <= 0 or not 0 <= large <= known:
                raise ValueError(f"weights.csv line {i} ({row['country']}): "
                                 f"need 0 <= 500+ value <= known value, got {large} and {known}")
            key = (row["effective_from"].strip(), row["report"].strip())
            rep = reports.setdefault(key, Report(row["report"].strip(), row["release_date"].strip(),
                                                 row["effective_from"].strip()))
            code = row["census_cty_code"].strip()
            if code in rep.shares:
                raise ValueError(f"weights.csv line {i}: {row['country']} listed twice in {rep.name}")
            rep.shares[code] = (row["country"].strip(), (known - large) / known)
    if not reports:
        raise ValueError("weights.csv has no rows")
    ordered = sorted(reports.values(), key=lambda r: r.effective_from)
    starts = [r.effective_from for r in ordered]
    if len(set(starts)) != len(starts):
        raise ValueError("Two Census reports in weights.csv have the same effective_from month")
    return ordered


def report_for(month, reports):
    """New shares apply only from their effective_from month onward."""
    chosen = None
    for rep in reports:
        if rep.effective_from <= month:
            chosen = rep
    if chosen is None:
        raise ValueError(f"No Census shares cover {month}; the earliest report starts {reports[0].effective_from}")
    return chosen


def compute(raw_rows, reports):
    """Return one dict per month, oldest first, with unrounded numbers."""
    by_month = defaultdict(dict)
    for r in raw_rows:
        by_month[r["month"]][r["cty_code"]] = (r["customs_value"], r["calculated_duties"])

    out = []
    for month in sorted(by_month):
        flows = by_month[month]
        rep = report_for(month, reports)
        sv = sd = lv = ld = covered = 0.0
        missing = []
        for code, (name, s) in rep.shares.items():
            if code not in flows:
                missing.append(name)
                continue
            v, d = flows[code]
            sv += v * s
            sd += d * s
            lv += v * (1 - s)
            ld += d * (1 - s)
            covered += v
        district_value = flows[TOTAL][0] if TOTAL in flows else float("nan")
        small_rate = sd / sv * 100
        large_rate = ld / lv * 100
        out.append({
            "month": month,
            "small_rate_pct": small_rate,
            "large_rate_pct": large_rate,
            "gap_pp": small_rate - large_rate,
            "small_value_usd": sv,
            "large_value_usd": lv,
            "small_duties_usd": sd,
            "large_duties_usd": ld,
            "covered_value_usd": covered,
            "district_value_usd": district_value,
            "coverage_pct": covered / district_value * 100,
            "countries": len(rep.shares) - len(missing),
            "missing_countries": missing,
            "weights_report": rep.name,
        })
    return out


INDEX_COLUMNS = ["month", "small_rate_pct", "large_rate_pct", "gap_pp",
                 "small_value_usd", "large_value_usd", "covered_value_usd",
                 "district_value_usd", "coverage_pct", "countries", "weights_report"]


def index_csv_rows(index_rows):
    """Rounded, ready-to-publish rows for data/index.csv."""
    rows = []
    for r in index_rows:
        rows.append({
            "month": r["month"],
            "small_rate_pct": f"{r['small_rate_pct']:.4f}",
            "large_rate_pct": f"{r['large_rate_pct']:.4f}",
            "gap_pp": f"{r['gap_pp']:.4f}",
            "small_value_usd": f"{r['small_value_usd']:.0f}",
            "large_value_usd": f"{r['large_value_usd']:.0f}",
            "covered_value_usd": f"{r['covered_value_usd']:.0f}",
            "district_value_usd": f"{r['district_value_usd']:.0f}",
            "coverage_pct": f"{r['coverage_pct']:.2f}",
            "countries": str(r["countries"]),
            "weights_report": r["weights_report"],
        })
    return rows
