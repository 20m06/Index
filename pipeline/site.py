"""Builds site/index.html: one plain black-on-white page. Charts are inline SVG drawn
here in Python, so the page needs no JavaScript and no chart library."""
import html
import math
import shutil

from . import config

LONG = ["January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December"]
SHORT = [m[:3] for m in LONG]
PAPER_LAST_MONTH = "2026-06"
PAPER_TITLE = ("How did exposure to the 2025 tariff shocks differ between trade flows dominated by "
               "small importers and those dominated by large importers, at the Los Angeles / Long Beach "
               "customs district?")


def esc(s):
    return html.escape(str(s), quote=True)


def mlong(m):
    return f"{LONG[int(m[5:7]) - 1]} {m[:4]}"


def mshort(m):
    return f"{SHORT[int(m[5:7]) - 1]} {m[:4]}"


def date_long(d):
    return f"{int(d[8:10])} {LONG[int(d[5:7]) - 1]} {d[:4]}"


# --------------------------------------------------------------------------- charts

def _ticks(lo, hi, n=5):
    raw = (hi - lo) / n or 1
    mag = 10 ** math.floor(math.log10(raw))
    step = next(k * mag for k in (1, 2, 2.5, 5, 10) if raw <= k * mag)
    t, out = math.floor(lo / step) * step, []
    while t <= hi + step * 0.999:
        out.append(round(t, 10))
        t += step
    return out


def svg_chart(months, series, tips, *, width, height, font, y_fmt, ref=None, markers=(), label):
    """series: [(legend label, values, dashed?)]; ref: (value, legend label) drawn as a grey dashed line;
    markers: [(month, text)] drawn as dotted vertical lines; tips: hover text per month."""
    n = len(months)
    ml, mr, mt, mb = font * 3.4, font * 0.9, font * 3.4, font * 2.2
    pw, ph = width - ml - mr, height - mt - mb
    values = [v for _, vals, _ in series for v in vals] + ([ref[0]] if ref else [])
    yt = _ticks(min(0.0, min(values)), max(values))
    lo, hi = yt[0], yt[-1]

    def x(i):
        return ml + pw * i / (n - 1)

    def y(v):
        return mt + ph * (1 - (v - lo) / (hi - lo))

    sw = max(1.5, font / 7)
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(label)}" '
           f'font-family="inherit" font-size="{font}">']
    for t in yt:  # horizontal gridlines and y labels
        out.append(f'<line x1="{ml:.1f}" x2="{width - mr:.1f}" y1="{y(t):.1f}" y2="{y(t):.1f}" '
                   f'stroke="{"#000" if t == 0 else "#ddd"}" stroke-width="1"/>')
        out.append(f'<text x="{ml - font * 0.4:.1f}" y="{y(t) + font * 0.35:.1f}" text-anchor="end">{esc(y_fmt(t))}</text>')
    for i, m in enumerate(months):  # a label for every January
        if m.endswith("-01"):
            out.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{mt + ph:.1f}" y2="{mt + ph + font * 0.4:.1f}" stroke="#000"/>')
            out.append(f'<text x="{x(i):.1f}" y="{mt + ph + font * 1.5:.1f}" text-anchor="start">{m[:4]}</text>')
    for m, text in markers:
        if m in months:
            i = months.index(m)
            out.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{mt:.1f}" y2="{mt + ph:.1f}" '
                       f'stroke="#000" stroke-dasharray="1 3"/>')
            out.append(f'<text x="{x(i) - font * 0.3:.1f}" y="{mt + font:.1f}" text-anchor="end" '
                       f'font-size="{font * 0.85:.1f}">{esc(text)}</text>')
    if ref:
        out.append(f'<line x1="{ml:.1f}" x2="{width - mr:.1f}" y1="{y(ref[0]):.1f}" y2="{y(ref[0]):.1f}" '
                   f'stroke="#777" stroke-width="{sw * 0.7:.1f}" stroke-dasharray="5 4"/>')
    for _, vals, dashed in series:
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        dash = ' stroke-dasharray="7 4"' if dashed else ""
        out.append(f'<polyline points="{pts}" fill="none" stroke="#000" stroke-width="{sw:.1f}"{dash} '
                   f'stroke-linejoin="round"/>')
        out.append(f'<circle cx="{x(n - 1):.1f}" cy="{y(vals[-1]):.1f}" r="{sw * 1.6:.1f}" fill="#000"/>')
    # legend, top left
    lx, ly = ml, font * 1.2
    items = [(lbl, "7 4" if d else None, "#000") for lbl, _, d in series]
    if ref:
        items.append((ref[1], "5 4", "#777"))
    for lbl, dash, color in items:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<line x1="{lx:.1f}" x2="{lx + font * 2:.1f}" y1="{ly - font * 0.35:.1f}" '
                   f'y2="{ly - font * 0.35:.1f}" stroke="{color}" stroke-width="{sw:.1f}"{d}/>')
        out.append(f'<text x="{lx + font * 2.5:.1f}" y="{ly:.1f}">{esc(lbl)}</text>')
        lx += font * 2.5 + len(lbl) * font * 0.56 + font * 1.4
        if lx > width - font * 12:
            lx, ly = ml, ly + font * 1.3
    # invisible hover columns: the browser shows the <title> as a tooltip
    col = pw / (n - 1)
    for i, tip in enumerate(tips):
        out.append(f'<rect x="{x(i) - col / 2:.1f}" y="{mt:.1f}" width="{col:.1f}" height="{ph:.1f}" '
                   f'fill="#fff" fill-opacity="0"><title>{esc(tip)}</title></rect>')
    out.append("</svg>")
    return "".join(out)


def chart_pair(*args, **kw):
    """A wide version for computers and a narrow one for phones (CSS shows one)."""
    wide = svg_chart(*args, width=720, height=340, font=13, **kw)
    narrow = svg_chart(*args, width=360, height=260, font=11, **kw)
    return f'<div class="wide">{wide}</div><div class="narrow">{narrow}</div>'


# --------------------------------------------------------------------------- page

CSS = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:#000;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:780px;margin:0 auto;padding:28px 16px 64px}
h1{font-size:1.7rem;line-height:1.2;margin:0 0 10px}
h2{font-size:1.2rem;margin:44px 0 10px;padding-top:14px;border-top:2px solid #000}
p{margin:0 0 12px}
a{color:#000}
.small{font-size:.9rem}
.headline{border:2px solid #000;padding:14px 16px;margin:22px 0}
.headline .big{font-size:2.6rem;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums}
figure{margin:18px 0 6px}
figure svg{display:block;width:100%;height:auto}
figcaption{font-size:.9rem;margin-top:4px}
.narrow{display:none}
@media (max-width:600px){.wide{display:none}.narrow{display:block}h1{font-size:1.4rem}.headline .big{font-size:2.1rem}}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:.95rem}
th,td{padding:5px 8px;border-bottom:1px solid #ddd;text-align:right;vertical-align:top}
th:first-child,td:first-child{text-align:left}
thead th{border-bottom:2px solid #000}
td.note{text-align:left;font-size:.85rem;border-bottom:2px solid #000}
.scroll{overflow-x:auto}
pre{font-size:.9rem;overflow-x:auto;border-left:3px solid #000;padding:6px 12px}
ul,ol{padding-left:22px}
li{margin-bottom:6px}
"""


def build(index_rows, reports, meta):
    rows = [{**r, **{k: float(r[k]) for k in ("small_rate_pct", "large_rate_pct", "gap_pp", "coverage_pct")}}
            for r in index_rows]
    months = [r["month"] for r in rows]
    gap = [r["gap_pp"] for r in rows]
    small = [r["small_rate_pct"] for r in rows]
    large = [r["large_rate_pct"] for r in rows]
    latest, prev = rows[-1], rows[-2]
    base = [r["gap_pp"] for r in rows if config.BASELINE[0] <= r["month"] <= config.BASELINE[1]]
    base_avg = sum(base) / len(base)
    peak = max(rows, key=lambda r: r["gap_pp"])
    tips = [f"{mshort(r['month'])}: gap {r['gap_pp']:.2f} pp (small-importer flows {r['small_rate_pct']:.2f}%, "
            f"large-importer flows {r['large_rate_pct']:.2f}%)" for r in rows]
    markers = [(rep.effective_from, "new Census shares") for rep in reports[1:]]

    gap_chart = chart_pair(months, [("Gap", gap, False)], tips, y_fmt=lambda t: f"{t:g}",
                           ref=(base_avg, f"2022–2024 average ({base_avg:.2f} pp)"), markers=markers,
                           label="Line chart of the monthly gap in percentage points")
    rate_chart = chart_pair(months, [("Small-importer flows", small, False), ("Large-importer flows", large, True)],
                            tips, y_fmt=lambda t: f"{t:g}%", markers=markers,
                            label="Line chart of the two monthly tariff rates in percent")

    table = []
    for r in reversed(rows):
        table.append(f"<tr><td>{mshort(r['month'])}</td><td>{r['small_rate_pct']:.2f}%</td>"
                     f"<td>{r['large_rate_pct']:.2f}%</td><td>{r['gap_pp']:.2f} pp</td>"
                     f"<td>{r['coverage_pct']:.1f}%</td></tr>")
        if r["month"] == PAPER_LAST_MONTH and r is not rows[-1]:
            table.insert(len(table) - 1, '<tr><td class="note" colspan="5">Months above were added after the '
                                         'paper. The paper covers January 2022 – June 2026.</td></tr>')

    share_tables = []
    for i, rep in enumerate(reports):
        until = f" to {mlong(_prev_month(reports[i + 1].effective_from))}" if i + 1 < len(reports) else " onward"
        trs = "".join(f"<tr><td>{esc(name)}</td><td>{s * 100:.1f}%</td></tr>"
                      for name, s in sorted(rep.shares.values(), key=lambda t: -t[1]))
        share_tables.append(
            f"<p><b>{esc(rep.name)}</b> (released {date_long(rep.release_date)}). Applies to months from "
            f"{mlong(rep.effective_from)}{until}.</p><div class=\"scroll\"><table><thead><tr><th>Country</th>"
            f"<th>Share of import value from firms under 500 employees</th></tr></thead><tbody>{trs}"
            f"</tbody></table></div>")

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Small-Importer Tariff Gap Index</title>
<meta name="description" content="Monthly tariff rate on trade flows dominated by small importers vs large importers, Los Angeles / Long Beach customs district. Updated automatically from U.S. Census Bureau data.">
<link rel="icon" href="data:,">
<style>{CSS}</style>
</head>
<body>
<main>
<h1>Small-Importer Tariff Gap Index</h1>
<p>Los Angeles / Long Beach customs district. Each month, imports are split into a part dominated by
small importers (firms under 500 employees) and a part dominated by large importers, and the tariff
rate on each part is compared. This page continues the calculation from <a href="#paper">the paper</a>,
which stops at June 2026, and updates itself when new government data comes out.</p>

<div class="headline">
<div class="small">Latest month: <b>{mlong(latest["month"])}</b></div>
<div class="big">{latest["gap_pp"]:.2f} pp</div>
<p>Tariff rate on trade flows dominated by small importers: <b>{latest["small_rate_pct"]:.2f}%</b>.
On flows dominated by large importers: <b>{latest["large_rate_pct"]:.2f}%</b>.</p>
<p class="small">Previous month ({mshort(prev["month"])}): {prev["gap_pp"]:.2f} pp.
2022–2024 average: {base_avg:.2f} pp. Highest: {peak["gap_pp"]:.2f} pp in {mlong(peak["month"])}.</p>
</div>

<h2>The gap</h2>
<figure>{gap_chart}
<figcaption>Small-importer tariff rate minus large-importer tariff rate, in percentage points (pp).
Dashed line: 2022–2024 average. Hover over the chart for exact values.</figcaption></figure>

<h2>The two tariff rates</h2>
<figure>{rate_chart}
<figcaption>Tariffs charged as a percentage of the value of goods. Both rates rose sharply in 2025;
the gap above is the difference between these two lines.</figcaption></figure>

<h2>Every month</h2>
<div class="scroll"><table>
<thead><tr><th>Month</th><th>Small-importer flows</th><th>Large-importer flows</th><th>Gap</th><th>Coverage</th></tr></thead>
<tbody>{"".join(table)}</tbody></table></div>
<p class="small">Coverage: share of the district's import value that comes from the countries with a
published small-business share (the rest is left out of both parts).</p>

<h2>Download the data</h2>
<ul>
<li><a href="data/index.csv">index.csv</a>: every month on this page, recomputed from the newest data.</li>
<li><a href="data/paper_vintage.csv">paper_vintage.csv</a>: the numbers exactly as published in the
paper (data pulled 12 August 2026). The government revises past months, so later numbers for the same
months can differ slightly.</li>
<li><a href="data/weights.csv">weights.csv</a>: the Census numbers the small-business shares come from.</li>
<li><a href="data/raw_monthly.csv">raw_monthly.csv</a>: value and tariffs for every country and month, as downloaded.</li>
</ul>

<h2>How it is calculated</h2>
<ol>
<li>Every month the U.S. Census Bureau publishes, for each country, the dollar value of goods entering
through the Los Angeles customs district and the tariffs charged on them.</li>
<li>A separate Census report gives, for each country, the share of U.S. import <b>dollars</b> that
belongs to companies with fewer than 500 employees: for example 39.4% for China and 17.8% for Japan.</li>
<li>Each country's goods and tariffs are split by that share. For China, 39.4% goes into the
small-importer part and 60.6% into the large-importer part.</li>
<li>Adding up all countries gives two parts. The tariff rate of each part is its tariffs divided by its
value. The gap is the small-importer rate minus the large-importer rate.</li>
</ol>
<pre>Small rate = Σ s × Duties  ÷  Σ s × Value
Large rate = Σ (1 − s) × Duties  ÷  Σ (1 − s) × Value
Gap        = Small rate − Large rate</pre>
<p>Inside one country both parts get the same tariff rate. The gap comes only from which countries
each part leans toward.</p>

<h2>What this shows and what it does not</h2>
<ul>
<li><b>Exposure, not reaction.</b> It shows how heavily the trade flows that small importers sit in were
taxed. It cannot show whether small firms cut their imports more, switched suppliers or raised prices.
That would need company-level data, which is not public.</li>
<li><b>A share of dollars, not of businesses.</b> By count, firms under 500 employees are about 99% of
U.S. importers; by import value their share is 4.5% to 48% depending on the country.</li>
<li><b>China drives most of the gap.</b> The paper shows that without China the gap stays between
−0.37 and +0.80 pp.</li>
<li><b>Not every country is included.</b> Only countries with a published small-business share count
(about 88% of the district's imports; see Coverage above).</li>
<li><b>A district, not just a port.</b> The Los Angeles customs district includes LAX air cargo as well
as the seaports, and it leans toward China more than the U.S. as a whole.</li>
<li><b>Shares are fixed.</b> New Census shares apply only from the month their report is released; earlier
months keep the shares that were in effect.</li>
</ul>

<h2>Sources and updates</h2>
<p>Data through <b>{mlong(meta["data_through"])}</b>. Numbers last changed on {date_long(meta["last_changed"])}.
New months usually appear about five weeks after the month ends; this page checks every day.</p>
<p>Trade data: {esc(meta["source"])}, dataset <i>International Trade: Imports by HS</i>, customs district 27
(Los Angeles, CA), imports for consumption, customs value and calculated duty. These are the same numbers
USITC DataWeb shows.</p>
<p>Small-business shares: U.S. Census Bureau, <i>A Profile of U.S. Importing and Exporting Companies</i>,
Table 5d. Share = (known import value − value imported by firms with 500+ employees) ÷ known import value.</p>
{"".join(share_tables)}

<h2 id="paper">The paper</h2>
<p>Michael Kosenko (August 15, 2026). <i>{esc(PAPER_TITLE)}</i>
<a href="{config.PAPER_PDF_NAME}">Read the PDF</a>.</p>
<p class="small">Code and full history: <a href="{config.REPO_URL}">{config.REPO_URL}</a></p>
</main>
</body>
</html>
"""
    config.SITE.mkdir(exist_ok=True)
    (config.SITE / "index.html").write_text(page, encoding="utf-8", newline="\n")
    out = config.SITE / "data"
    out.mkdir(exist_ok=True)
    for src in (config.INDEX, config.PAPER_VINTAGE, config.WEIGHTS, config.RAW):
        if src.exists():
            shutil.copyfile(src, out / src.name)


def _prev_month(m):
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y - (mo == 1)}-{(mo - 2) % 12 + 1:02d}"
