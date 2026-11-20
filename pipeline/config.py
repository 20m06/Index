"""Paths and fixed settings used by every step of the pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA = ROOT / "data"
SITE = ROOT / "site"

WEIGHTS = DATA / "weights.csv"            # Census Table 5d numbers (edited by hand, ~once a year)
RAW = DATA / "raw_monthly.csv"            # every country, every month, as downloaded
INDEX = DATA / "index.csv"                # the published index
META = DATA / "meta.json"                 # "data through" month, last-changed date, source
PAPER_VINTAGE = DATA / "paper_vintage.csv"  # frozen numbers exactly as printed in the paper
ARCHIVE = DATA / "archive"                # a dated copy of index.csv every time it changes
MANUAL_UPLOAD = DATA / "manual_upload"    # backup: drop a DataWeb Excel export here

PAPER_PDF_NAME = "Kosenko_2026_tariff_exposure_small_vs_large_importers.pdf"
REPO_URL = "https://github.com/20m06/Index"

DISTRICT = "27"           # Los Angeles, CA customs district
FIRST_MONTH = "2022-01"   # same start as the paper
BASELINE = ("2022-01", "2024-12")  # the paper's "normal years" window

# Census API field names: imports for consumption, customs value and calculated duty.
CENSUS_VALUE_FIELD = "CON_VAL_MO"
CENSUS_DUTY_FIELD = "CAL_DUT_MO"
