#!/usr/bin/env python3
"""Render the reviewed report as a compact RTL HTML email body.

The PDF is linked, not attached: the Gmail tool takes attachments as inline
base64, and even a small Persian PDF (embedded fonts) is far too long to pass
that way reliably.

Usage: python3 scripts/build_email.py work/report.reviewed.json <pdf_url> > work/email.html
"""
import json
import sys
from html import escape
from pathlib import Path


def main():
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    pdf_url = sys.argv[2]
    refs = {r["id"]: r for r in report.get("references", [])}

    def links(ids):
        return " ".join(f'<a href="{escape(refs[i]["url"])}">[{i}]</a>' for i in ids or [] if i in refs)

    parts = [f'<div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;font-size:14px;line-height:1.9;color:#1d1d1f">',
             f'<h2 style="color:#3b2a6e">گزارش روزانهٔ علم اعداد — {escape(report.get("date_fa", ""))}</h2>',
             f'<p><a href="{escape(pdf_url)}"><b>📄 دریافت نسخهٔ PDF گزارش</b></a></p>',
             '<h3 style="color:#3b2a6e">جمع‌بندی کلی</h3>']
    parts += [f"<p>{escape(p)}</p>" for p in report.get("overview", [])]
    parts.append('<h3 style="color:#3b2a6e">مهم‌ترین خبرها</h3>')
    for s in report.get("top_stories", []):
        body = "".join(f"<p>{escape(p)}</p>" for p in s["body"].split("\n") if p.strip())
        parts.append(f'<div style="border-right:4px solid #6b5ca5;padding-right:10px;margin:12px 0">'
                     f'<b>{escape(s["title"])}</b> <span style="color:#6b5ca5">({escape(s.get("teacher", ""))})</span>'
                     f'{body}<div style="font-size:12px">{links(s.get("refs"))}</div></div>')
    parts.append('<h3 style="color:#3b2a6e">وضعیت اساتید</h3><ul>')
    for t in report.get("teachers", []):
        n = len(t.get("items", []))
        note = f"{str(n).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))} مطلب تازه" if n else escape(t.get("status") or "مطلب تازه‌ای نبود")
        parts.append(f"<li><b>{escape(t['name_fa'])}</b>: {note}</li>")
    parts.append('</ul><h3 style="color:#3b2a6e">منابع</h3><ol>')
    parts += [f'<li><a href="{escape(r["url"])}">{escape(r.get("title", ""))}</a> — {escape(r.get("platform", ""))}</li>'
              for r in report.get("references", [])]
    parts.append("</ol></div>")
    print("\n".join(parts))


if __name__ == "__main__":
    main()
