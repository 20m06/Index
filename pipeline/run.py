"""Monthly update, start to finish.

    python -m pipeline.run                 # normal run (Census API, Excel backup)
    python -m pipeline.run --excel FILE    # use a DataWeb Excel export instead of the API

1. load the Census small-business shares (data/weights.csv)
2. download the monthly trade numbers
3. compute the index
4. run the checks; stop without publishing anything if one fails
5. save the data only if something changed (new month or revised numbers)
6. rebuild the website from the saved data
"""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config, site
from .checks import run_checks
from .index import INDEX_COLUMNS, compute, index_csv_rows, load_weights
from .sources import SourceError, census_key, fetch_census, newest_manual_upload, read_dataweb_excel

RAW_COLUMNS = ["month", "cty_code", "country", "customs_value", "calculated_duties"]


def _csv_text(rows, columns):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _read_csv(path):
    if not path.exists():
        return None
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _report_error(title, message):
    """Print the error; on GitHub it also appears on the run's public summary page."""
    print(f"\n{title}: {message}")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error title={title}::{message}")


def get_rows(reports, excel=None):
    name_to_code = {name: code for rep in reports for code, (name, _) in rep.shares.items()}
    if excel:
        return read_dataweb_excel(Path(excel), name_to_code), f"USITC DataWeb export ({Path(excel).name})"
    key = census_key()
    # Safe to print: says whether a key exists and how long it is, never the key itself.
    print(f"Census key found: {'yes' if key else 'NO'}"
          + (f" ({len(key)} characters; Census keys are 40)" if key else ""))
    try:
        return fetch_census(), "U.S. Census Bureau International Trade API"
    except SourceError as e:
        backup = newest_manual_upload()
        if not backup:
            raise
        print(f"Census API failed ({e}); using backup file {backup.name}")
        return read_dataweb_excel(backup, name_to_code), f"USITC DataWeb export ({backup.name})"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--excel", help="DataWeb Excel export to use instead of the Census API")
    args = p.parse_args(argv)

    reports = load_weights(config.WEIGHTS)
    try:
        raw_rows, source = get_rows(reports, args.excel)
    except SourceError as e:
        _report_error("Download failed - nothing was published", str(e))
        return 1
    raw_rows.sort(key=lambda r: (r["month"], r["cty_code"]))
    index_rows = compute(raw_rows, reports)

    previous = _read_csv(config.INDEX)
    errors, warnings = run_checks(index_rows, raw_rows, reports, previous)
    for w in warnings:
        print("WARNING:", w)
    if errors:
        _report_error("Checks failed - nothing was published", "; ".join(errors[:10]))
        return 1

    raw_text = _csv_text(raw_rows, RAW_COLUMNS)
    index_text = _csv_text(index_csv_rows(index_rows), INDEX_COLUMNS)
    weights_hash = hashlib.sha256(config.WEIGHTS.read_bytes()).hexdigest()
    meta = json.loads(config.META.read_text(encoding="utf-8")) if config.META.exists() else {}

    changed = (
        not meta
        or not config.RAW.exists() or config.RAW.read_text(encoding="utf-8") != raw_text
        or not config.INDEX.exists() or config.INDEX.read_text(encoding="utf-8") != index_text
        or meta.get("weights_sha256") != weights_hash
    )
    if changed:
        today = datetime.now(timezone.utc).date().isoformat()
        config.DATA.mkdir(exist_ok=True)
        config.ARCHIVE.mkdir(exist_ok=True)
        config.RAW.write_text(raw_text, encoding="utf-8", newline="\n")
        config.INDEX.write_text(index_text, encoding="utf-8", newline="\n")
        (config.ARCHIVE / f"index_{today}.csv").write_text(index_text, encoding="utf-8", newline="\n")
        meta = {
            "data_through": index_rows[-1]["month"],
            "last_changed": today,
            "source": source,
            "weights_sha256": weights_hash,
        }
        config.META.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"Updated: data through {meta['data_through']} (source: {source})")
    else:
        print(f"No change: data still through {meta.get('data_through')}")

    site.build(_read_csv(config.INDEX), reports, meta)
    print("Website rebuilt in", config.SITE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
