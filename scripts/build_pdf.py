#!/usr/bin/env python3
"""Render the Persian daily numerology report (report.json) to an RTL PDF.

Usage: python3 scripts/build_pdf.py work/report.json out/report.pdf [--max-pages 50]
Exits with code 2 if the PDF exceeds --max-pages, so the caller can shorten it.

report.json schema:
{
  "date_fa": "۶ مهر ۱۴۰۵", "date_gregorian": "2026-09-28",
  "overview": ["paragraph", ...],                       # جمع‌بندی کلی روز
  "top_stories": [{"title", "teacher", "body", "refs": [1, 2]}],
  "teachers": [{"name_fa", "name_en", "status",        # status shown when items is empty
                "items": [{"title", "platform", "body", "refs": [3]}]}],
  "coverage": [{"teacher", "source", "status"}],        # what could / could not be checked
  "references": [{"id": 1, "title", "url", "platform", "published"}]
}
"""
import argparse
import json
import sys
from html import escape
from pathlib import Path

from weasyprint import HTML

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "fonts"
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(n):
    return str(n).translate(FA_DIGITS)


def refs(ids):
    if not ids:
        return ""
    links = "، ".join(f'<a href="#ref-{i}">{fa(i)}</a>' for i in ids)
    return f'<span class="refs">[{links}]</span>'


def paragraphs(text):
    return "".join(f"<p>{escape(p.strip())}</p>" for p in str(text).split("\n") if p.strip())


def render(r):
    top = "".join(
        f'<div class="story"><h3>{escape(s["title"])}</h3>'
        f'<div class="meta">{escape(s.get("teacher", ""))}</div>'
        f'{paragraphs(s["body"])}{refs(s.get("refs"))}</div>'
        for s in r.get("top_stories", [])
    )
    teachers = ""
    for t in r.get("teachers", []):
        items = "".join(
            f'<div class="item"><h4>{escape(i["title"])}'
            f' <span class="badge">{escape(i.get("platform", ""))}</span></h4>'
            f'{paragraphs(i["body"])}{refs(i.get("refs"))}</div>'
            for i in t.get("items", [])
        ) or f'<p class="muted">{escape(t.get("status") or "امروز محتوای تازه‌ای یافت نشد.")}</p>'
        teachers += (f'<section class="teacher"><h2>{escape(t["name_fa"])}'
                     f' <span class="en">{escape(t.get("name_en", ""))}</span></h2>{items}</section>')
    coverage = "".join(
        f'<tr><td>{escape(c["teacher"])}</td><td class="ltr">{escape(c["source"])}</td>'
        f'<td>{escape(c["status"])}</td></tr>'
        for c in r.get("coverage", [])
    )
    references = "".join(
        f'<li id="ref-{x["id"]}"><b>[{fa(x["id"])}]</b> {escape(x.get("title", ""))}'
        f' — {escape(x.get("platform", ""))} {escape(x.get("published") or "")}<br>'
        f'<a class="ltr" href="{escape(x["url"])}">{escape(x["url"])}</a></li>'
        for x in r.get("references", [])
    )
    overview = "".join(f"<p>{escape(p)}</p>" for p in r.get("overview", []))

    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><style>
@font-face {{ font-family: Vazirmatn; font-weight: 400; src: url('{(FONTS / "Vazirmatn-Regular.ttf").as_uri()}'); }}
@font-face {{ font-family: Vazirmatn; font-weight: 700; src: url('{(FONTS / "Vazirmatn-Bold.ttf").as_uri()}'); }}
@font-face {{ font-family: Vazirmatn; font-weight: 900; src: url('{(FONTS / "Vazirmatn-Black.ttf").as_uri()}'); }}
@page {{ size: A4; margin: 18mm 16mm 20mm;
  @bottom-center {{ content: counter(page); font-family: Vazirmatn; font-size: 9pt; color: #777; }} }}
body {{ font-family: Vazirmatn; font-size: 11pt; line-height: 1.85; color: #1d1d1f; direction: rtl; text-align: justify; }}
h1, h2, h3, h4 {{ font-weight: 900; line-height: 1.4; text-align: right; }}
h1 {{ font-size: 26pt; margin: 0 0 4mm; color: #3b2a6e; }}
h2 {{ font-size: 17pt; color: #3b2a6e; border-bottom: 2px solid #d9d2ee; padding-bottom: 2mm; margin-top: 9mm; }}
h3 {{ font-size: 14pt; margin: 5mm 0 1mm; }}
h4 {{ font-size: 12pt; margin: 4mm 0 1mm; font-weight: 700; }}
.cover {{ page-break-after: always; padding-top: 55mm; text-align: center; }}
.cover h1 {{ text-align: center; font-size: 30pt; }}
.cover .sub {{ font-size: 14pt; color: #555; }}
.en {{ font-size: 10pt; color: #888; font-weight: 400; }}
.meta {{ color: #6b5ca5; font-size: 10pt; font-weight: 700; }}
.story {{ background: #f6f4fb; border-right: 4px solid #6b5ca5; padding: 2mm 5mm 3mm; margin: 4mm 0; page-break-inside: avoid; }}
.item {{ page-break-inside: avoid; }}
.badge {{ font-size: 8.5pt; font-weight: 400; background: #ece8f7; color: #3b2a6e; padding: 0.3mm 2mm; border-radius: 2mm; }}
.refs {{ font-size: 9pt; color: #6b5ca5; }}
.refs a, a {{ color: #4a3a8c; text-decoration: none; }}
.muted {{ color: #888; }}
.ltr {{ direction: ltr; unicode-bidi: embed; font-size: 8.5pt; }}
table {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
td {{ border-bottom: 1px solid #e5e5e5; padding: 1.2mm; vertical-align: top; }}
ol.references {{ list-style: none; padding: 0; font-size: 9pt; }}
ol.references li {{ margin-bottom: 2mm; page-break-inside: avoid; }}
section.break {{ page-break-before: always; }}
</style></head><body>
<div class="cover"><h1>گزارش روزانهٔ علم اعداد</h1>
<div class="sub">مهم‌ترین خبرها و محتوای اساتید غربی و هندی</div>
<div class="sub">{escape(r.get("date_fa", ""))} — <span class="ltr">{escape(r.get("date_gregorian", ""))}</span></div></div>
<h2>جمع‌بندی کلی امروز</h2>{overview}
<h2>مهم‌ترین خبرهای امروز</h2>{top or '<p class="muted">خبر مهمی ثبت نشد.</p>'}
<section class="break"><h2>جزئیات به تفکیک استاد</h2></section>{teachers}
<section class="break"><h2>منابعی که بررسی شد</h2><table>{coverage}</table></section>
<section class="break"><h2>فهرست منابع</h2><ol class="references">{references}</ol></section>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("out")
    ap.add_argument("--max-pages", type=int, default=50)
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    doc = HTML(string=render(report), base_url=str(ROOT)).render()
    pages = len(doc.pages)
    if pages > args.max_pages:
        print(f"TOO_LONG: {pages} pages (max {args.max_pages})", file=sys.stderr)
        return 2
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    doc.write_pdf(args.out)
    print(f"OK: {pages} pages -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
