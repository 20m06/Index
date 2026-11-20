"""Where the monthly numbers come from.

Two sources that carry the same Census numbers:
  1. Census International Trade API (automatic; needs a free key in CENSUS_API_KEY).
  2. A USITC DataWeb Excel export dropped into data/manual_upload/ (backup, by hand).

Both return the same shape: a list of rows like
    {"month": "2025-05", "cty_code": "5700", "country": "China",
     "customs_value": 3917409664, "calculated_duties": 2339771002}
plus one row per month with cty_code "TOTAL": the whole district, all countries.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date

from . import config

API_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
TOTAL = "TOTAL"


class SourceError(RuntimeError):
    pass


# --------------------------------------------------------------------------- Census API

def census_key():
    """The key comes from the environment (GitHub secret) or from a local .env file."""
    key = _clean_key(os.environ.get("CENSUS_API_KEY", ""))
    if key:
        return key
    env = config.ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "CENSUS_API_KEY":
                return _clean_key(value)
    return ""


def _clean_key(value):
    """Forgive common paste mistakes: spaces, quotes, the 'CENSUS_API_KEY=...' line,
    or the whole .env file (comment line included) pasted into the GitHub secret."""
    m = re.search(r"(?im)^\s*CENSUS_API_KEY\s*=\s*[\"']?\s*([A-Za-z0-9]+)", value)
    if m:
        return m.group(1)
    return value.strip().strip('"').strip("'").strip()


def _get(params, retries=3):
    url = API_URL + "?" + urllib.parse.urlencode(params, safe=",")
    last_error = "unknown error"
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "small-importer-tariff-index"})
            with urllib.request.urlopen(request, timeout=180) as response:
                page = urllib.parse.urlparse(response.geturl()).path
                if page.endswith("_key.html"):
                    key = params.get("key", "")
                    shape = ("letters and digits only" if key.isalnum() else
                             "contains spaces or symbols, which a real key never does")
                    raise SourceError(
                        f"The Census API did not accept the key ({page.rsplit('/', 1)[-1]}). "
                        f"The key it was given is {len(key)} characters long and {shape}; "
                        f"a real Census key is 40 letters and digits. Re-paste CENSUS_API_KEY.")
                if response.status == 204:
                    return []
                body = response.read().decode("utf-8")
            if not body.strip():
                return []
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                raise SourceError("The Census API returned a web page instead of data "
                                  "(usually a missing or invalid key).")
        except SourceError:
            raise
        except urllib.error.HTTPError as e:
            # The URL holds the key, so never print it. The status code is enough.
            last_error = f"HTTP {e.code}"
            if e.code in (400, 404):
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_error = type(e).__name__
        time.sleep(5 * (attempt + 1))
    raise SourceError(f"Census API request failed: {last_error}")


def fetch_census(first_month=config.FIRST_MONTH, district=config.DISTRICT):
    """Download every country, every month from first_month onward, for one customs district."""
    key = census_key()
    if not key:
        raise SourceError("No Census API key. Set CENSUS_API_KEY (GitHub secret) or put it in .env.")

    value_f, duty_f = config.CENSUS_VALUE_FIELD, config.CENSUS_DUTY_FIELD
    rows = []
    for year in range(int(first_month[:4]), date.today().year + 1):
        data = _get({
            "get": f"CTY_CODE,CTY_NAME,{value_f},{duty_f},SUMMARY_LVL,YEAR,MONTH",
            "DISTRICT": district,
            "I_COMMODITY": "-",           # "-" = all products combined (one row per country)
            "time": str(year),
            "key": key,
        })
        if not data:
            continue
        col = {name: i for i, name in enumerate(data[0])}
        for rec in data[1:]:
            commodity = rec[col["I_COMMODITY"]] if "I_COMMODITY" in col else "-"
            if commodity not in ("-", "", None):
                continue                      # keep only all-commodity totals
            code = (rec[col["CTY_CODE"]] or "").strip()
            level = rec[col["SUMMARY_LVL"]] if "SUMMARY_LVL" in col else "DET"
            if code == "-":
                code, name = TOTAL, "All countries"
            elif level == "DET":
                name = (rec[col["CTY_NAME"]] or "").strip()
            else:
                continue                      # country groupings (EU, Pacific Rim, ...)
            month = f"{rec[col['YEAR']]}-{int(rec[col['MONTH']]):02d}"
            if month < first_month:
                continue
            rows.append({
                "month": month, "cty_code": code, "country": name,
                "customs_value": int(float(rec[col[value_f]] or 0)),
                "calculated_duties": int(float(rec[col[duty_f]] or 0)),
            })
    if not rows:
        raise SourceError("The Census API returned no rows.")
    if not any(r["cty_code"] == TOTAL for r in rows):
        raise SourceError("The Census API returned no district total row.")
    return rows


# --------------------------------------------------------------------------- DataWeb Excel

def read_dataweb_excel(path, name_to_code, first_month=config.FIRST_MONTH):
    """Read a USITC DataWeb export (the layout used in the paper).

    Sheets 'Customs Value' and 'Calculated Duties'; from row 4: column B country,
    C year, D-O January-December. The export pads months that are not published yet
    with zeros, so months whose district total is zero are dropped.
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)  # not read_only: some exports have no size info
    cells = defaultdict(dict)                 # (country, month) -> {field: dollars}
    for sheet, field in (("Customs Value", "customs_value"), ("Calculated Duties", "calculated_duties")):
        if sheet not in wb.sheetnames:
            raise SourceError(f"{path.name}: no sheet called '{sheet}'. Is this a DataWeb export?")
        for row in wb[sheet].iter_rows(min_row=4, values_only=True):
            name = row[1]
            if not name or str(name).strip().startswith("Total") or row[2] in (None, ""):
                continue
            year = int(float(row[2]))
            for m, cell in enumerate(row[3:15], 1):
                cells[(str(name).strip(), f"{year}-{m:02d}")][field] = int(round(float(cell or 0)))
    wb.close()

    totals = defaultdict(lambda: [0, 0])
    for (name, month), v in cells.items():
        totals[month][0] += v.get("customs_value", 0)
        totals[month][1] += v.get("calculated_duties", 0)
    months = sorted(m for m, t in totals.items() if t[0] > 0 and m >= first_month)
    if not months:
        raise SourceError(f"{path.name}: no months with data.")
    keep = set(months)

    rows = []
    for (name, month), v in cells.items():
        if month in keep:
            rows.append({
                "month": month, "cty_code": name_to_code.get(name, "name:" + name), "country": name,
                "customs_value": v.get("customs_value", 0),
                "calculated_duties": v.get("calculated_duties", 0),
            })
    for month in months:
        rows.append({"month": month, "cty_code": TOTAL, "country": "All countries",
                     "customs_value": totals[month][0], "calculated_duties": totals[month][1]})
    return rows


def newest_manual_upload():
    files = sorted(config.MANUAL_UPLOAD.glob("*.xlsx"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None
