# Small-Importer Tariff Gap Index

A monthly, self-updating version of the paper *"How did exposure to the 2025 tariff shocks differ
between trade flows dominated by small importers and those dominated by large importers, at the
Los Angeles / Long Beach customs district?"* (Michael Kosenko, August 2026; PDF in `site/`).

The paper stops at June 2026. This repository recomputes the same numbers every month, indefinitely,
and publishes them as a plain website.

## How it works

```
GitHub Actions (every day)                                   Vercel
  1. download the newest Census trade data   ─┐
  2. compute the index (same math as paper)    ├─ commit ──►  redeploys the website
  3. run the checks (stop if anything is off)  │
  4. rebuild site/index.html                  ─┘   (only when the numbers changed)
```

- **Trade data:** U.S. Census Bureau International Trade API (the same numbers USITC DataWeb shows),
  customs district 27 (Los Angeles), imports for consumption: customs value (`CON_VAL_MO`) and
  calculated duty (`CAL_DUT_MO`). Needs the free key stored as the GitHub secret `CENSUS_API_KEY`.
- **Small-business shares:** Census *Profile of U.S. Importing and Exporting Companies*, Table 5d,
  stored in `data/weights.csv`.
- **Formula** (paper Section 4): for each month, every country's value and duties are split into a
  small-importer part (× its share) and a large-importer part (× 1 − share). Each part's tariff rate =
  its duties ÷ its value. Gap = small rate − large rate.

## Files

| Path | What it is |
|---|---|
| `data/weights.csv` | Census Table 5d numbers. **The only file you edit by hand.** |
| `data/index.csv` | The published index, every month (recomputed each run). |
| `data/raw_monthly.csv` | Every country, every month, as downloaded. |
| `data/paper_vintage.csv` | The paper's numbers, frozen. Never regenerated. |
| `data/archive/` | A dated copy of `index.csv` every time it changes. |
| `data/manual_upload/` | Backup: drop a DataWeb Excel export here if the Census API breaks. |
| `pipeline/` | The code: `sources.py` (download), `index.py` (math), `checks.py`, `site.py`, `run.py`. |
| `tests/` | Proves the code reproduces all 54 months of the paper from the paper's own data. |
| `site/` | The website Vercel serves. Generated; don't edit by hand. |

## Once a year: a new Census report comes out

1. Open the new report's **Table 5d** ("Imports by Company Employment Size from World Areas and
   Selected Countries").
2. On GitHub, open `data/weights.csv` → pencil icon (Edit).
3. Add one new row per country, copying the format of the existing rows:
   - `report`: e.g. `Census Profile 2024-2025 Table 5d`
   - `release_date`: the day the report came out, e.g. `2027-05-04`
   - `effective_from`: the first month the new shares apply to = the release month, e.g. `2027-05`
   - `country`, `census_cty_code`: copy from the existing rows (a new country needs its Census
     code from https://www.census.gov/foreign-trade/schedules/c/countrycode.html)
   - `known_value_musd`: the "Known Value" column ($ millions)
   - `large_500plus_musd`: the "500+ employees" value column ($ millions)
4. Keep the old rows. They still apply to the months before `effective_from`.
5. Commit. The update runs automatically within a few minutes and marks the switch on the charts.

## If the Census API stops working

The daily run fails and GitHub emails you; the website keeps showing the last good numbers.
Backup: on https://dataweb.usitc.gov run the paper's query (Imports for Consumption, HTS Items,
Customs Value + Calculated Duties, monthly, years 2022 to now, Use All Countries / Break Out Countries,
district Los Angeles, CA), download the Excel, and upload it into `data/manual_upload/` on GitHub.
The run uses it automatically when the API fails.

## Run it on your own computer

```
pip install -r requirements.txt
python -m unittest -v           # must pass: reproduces the paper
python -m pipeline.run          # needs CENSUS_API_KEY in a .env file or the environment
python -m http.server 8765 --directory site   # then open http://localhost:8765
```

## Limits (from the paper, Section 6)

It measures **exposure, not reaction**: shares are fixed by country, so it cannot show whether small
firms changed what they import. Shares are of import **value**, not of the number of firms. Countries
without a published share (about 12% of the district) are left out. The district includes LAX air cargo.
