"""Checks that must pass before anything is published (ported from the 'Checks'
sheet of Index_calculations.xlsx). Errors stop the update; warnings are only printed."""
import math
import re

from . import config
from .sources import TOTAL


def _next_month(m):
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y + (mo == 12)}-{mo % 12 + 1:02d}"


def _words(name):
    return set(re.sub(r"[^A-Z ]", " ", name.upper()).split())


def run_checks(index_rows, raw_rows, reports, previous=None):
    errors, warnings = [], []

    # 1. Shares are between 0 and 1 (SME share + large share = 1 by construction).
    for rep in reports:
        for code, (name, s) in rep.shares.items():
            if not 0 <= s <= 1:
                errors.append(f"{rep.name}: share for {name} is {s}, outside 0-1")

    # 2. No missing months, starting at the paper's first month.
    months = [r["month"] for r in index_rows]
    if not months:
        return ["No months computed"], warnings
    if months[0] != config.FIRST_MONTH:
        errors.append(f"Data starts at {months[0]}, expected {config.FIRST_MONTH}")
    for a, b in zip(months, months[1:]):
        if b != _next_month(a):
            errors.append(f"Gap in months between {a} and {b}")

    # 3. Every country with a share is present every month.
    for r in index_rows:
        if r["missing_countries"]:
            errors.append(f"{r['month']}: no data for {', '.join(r['missing_countries'])}")

    # 4. Small basket + large basket = the countries' raw total (nothing lost or invented).
    raw_by = {(x["month"], x["cty_code"]): x["customs_value"] for x in raw_rows}
    for r in index_rows:
        if math.isnan(r["district_value_usd"]):
            errors.append(f"{r['month']}: no district total")
            continue
        if abs(r["small_value_usd"] + r["large_value_usd"] - r["covered_value_usd"]) > 1:
            errors.append(f"{r['month']}: small + large basket does not equal the country total")

    # 5. Sanity bounds.
    for r in index_rows:
        for k in ("small_rate_pct", "large_rate_pct"):
            if not 0 < r[k] < 100:
                errors.append(f"{r['month']}: {k} = {r[k]:.2f}, outside 0-100")
        if not 50 <= r["coverage_pct"] <= 100.0001:
            errors.append(f"{r['month']}: coverage {r['coverage_pct']:.1f}% is outside 50-100%")

    # 6. Country codes point at the right countries (catches a typo in weights.csv).
    names_seen = {x["cty_code"]: x["country"] for x in raw_rows}
    for rep in reports:
        for code, (name, _) in rep.shares.items():
            seen = names_seen.get(code)
            if seen and not _words(name) <= _words(seen) and seen != name:
                errors.append(f"weights.csv says code {code} is {name}, but the data calls it {seen}")

    # 7. District total vs the sum of individual countries (warning only).
    by_month = {}
    for x in raw_rows:
        if x["cty_code"] != TOTAL:
            by_month[x["month"]] = by_month.get(x["month"], 0) + x["customs_value"]
    for m in months:
        total = raw_by.get((m, TOTAL))
        if total and abs(by_month.get(m, 0) - total) / total > 0.005:
            warnings.append(f"{m}: countries add up to {by_month.get(m, 0):,} but district total is {total:,}")

    # 8. Big revisions to months already published (warning only; revisions are expected).
    if previous:
        old = {r["month"]: float(r["gap_pp"]) for r in previous}
        for r in index_rows:
            if r["month"] in old and abs(r["gap_pp"] - old[r["month"]]) > 0.25:
                warnings.append(f"{r['month']}: gap revised from {old[r['month']]:.2f} to {r['gap_pp']:.2f} pp")
        if len(index_rows) < len(previous):
            errors.append(f"New data has {len(index_rows)} months, fewer than the {len(previous)} already published")

    return errors, warnings
