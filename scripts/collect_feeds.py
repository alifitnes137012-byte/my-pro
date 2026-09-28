#!/usr/bin/env python3
"""Collect recent items from site RSS feeds and YouTube channel feeds.

Deterministic first pass for the daily report; the collector agents fill in
Instagram, X, Facebook and anything the feeds miss.

Usage: python3 scripts/collect_feeds.py [--hours 36] [--out work/feeds.json]
"""
import argparse
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
NS = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse_date(s):
    if not s:
        return None
    try:
        return parsedate_to_datetime(s)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def parse_feed(xml_text):
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):  # RSS 2.0
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "url": (it.findtext("link") or "").strip(),
            "published": it.findtext("pubDate"),
            "summary": strip_html(it.findtext("description"))[:1500],
        })
    for e in root.findall("atom:entry", NS):  # Atom (YouTube)
        link = e.find("atom:link", NS)
        desc = e.find("media:group/media:description", NS)
        items.append({
            "title": (e.findtext("atom:title", namespaces=NS) or "").strip(),
            "url": link.get("href") if link is not None else "",
            "published": e.findtext("atom:published", namespaces=NS),
            "summary": (desc.text or "")[:1500] if desc is not None else "",
        })
    return items


def youtube_feed_url(ref):
    if re.fullmatch(r"UC[\w-]{22}", ref):
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={ref}"
    page = ref if ref.startswith("http") else f"https://www.youtube.com/{ref}"
    m = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', fetch(page))
    if not m:
        raise ValueError(f"channel id not found for {ref}")
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=36)
    ap.add_argument("--out", default=str(ROOT / "work" / "feeds.json"))
    args = ap.parse_args()

    cfg = json.loads((ROOT / "sources.json").read_text())
    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "hours": args.hours,
              "items": [], "errors": []}

    for t in cfg["teachers"]:
        jobs = [("site", u) for u in t["feeds"]] + [("youtube", y) for y in t["youtube"]]
        for kind, ref in jobs:
            try:
                url = youtube_feed_url(ref) if kind == "youtube" else ref
                for item in parse_feed(fetch(url)):
                    dt = parse_date(item["published"])
                    if dt and dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt and dt < cutoff:
                        continue
                    item.update(teacher=t["id"], source_type=kind, feed=url,
                                published=dt.isoformat() if dt else None)
                    result["items"].append(item)
            except Exception as exc:  # network/policy failures are reported, not fatal
                result["errors"].append({"teacher": t["id"], "source": ref, "error": str(exc)[:300]})

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"{len(result['items'])} recent items, {len(result['errors'])} errors -> {out}")


if __name__ == "__main__":
    sys.exit(main())
