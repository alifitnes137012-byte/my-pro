#!/usr/bin/env python3
"""Collect recent Instagram posts/reels of the teachers via the official
Instagram Graph API (Business Discovery).

Needs two environment variables (set in the cloud environment settings):
  IG_USER_ID       your Instagram Business/Creator account id
  IG_ACCESS_TOKEN  a token with instagram_basic, pages_show_list,
                   pages_read_engagement and business_management
Optional: IG_GRAPH_VERSION (e.g. "v23.0"); unversioned calls by default.

Business Discovery only returns Business/Creator accounts, and never stories.
Without the variables the script records "not configured" and exits 0.

Usage: python3 scripts/collect_instagram.py [--hours 36] [--out work/instagram.json]
"""
import argparse
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ("username,name,followers_count,media_count,"
          "media.limit(15){caption,media_type,media_product_type,permalink,timestamp,"
          "like_count,comments_count}")


def discover(handle, user_id, token, version):
    base = "https://graph.facebook.com/" + (f"{version}/" if version else "")
    query = urllib.parse.urlencode({
        "fields": f"business_discovery.username({handle}){{{FIELDS}}}",
        "access_token": token,
    })
    try:
        with urllib.request.urlopen(f"{base}{user_id}?{query}", timeout=20) as r:
            return json.loads(r.read())["business_discovery"]
    except urllib.error.HTTPError as exc:
        # Graph API puts the useful reason in the JSON body; never echo the token.
        msg = json.loads(exc.read() or b"{}").get("error", {}).get("message", str(exc))
        raise RuntimeError(msg.replace(token, "***")) from None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=36)
    ap.add_argument("--out", default=str(ROOT / "work" / "instagram.json"))
    args = ap.parse_args()
    socket.setdefaulttimeout(20)

    user_id, token = os.environ.get("IG_USER_ID"), os.environ.get("IG_ACCESS_TOKEN")
    cfg = json.loads((ROOT / "sources.json").read_text())
    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "configured": bool(user_id and token),
              "items": [], "profiles": [], "errors": []}

    for t in cfg["teachers"]:
        for handle in t["instagram"]:
            if not result["configured"]:
                result["errors"].append({"teacher": t["id"], "source": handle,
                                         "error": "not configured: IG_USER_ID / IG_ACCESS_TOKEN missing"})
                continue
            try:
                bd = discover(handle, user_id, token, os.environ.get("IG_GRAPH_VERSION"))
            except Exception as exc:
                result["errors"].append({"teacher": t["id"], "source": handle, "error": str(exc)[:300]})
                continue
            result["profiles"].append({"teacher": t["id"], "handle": handle,
                                       "followers": bd.get("followers_count"), "posts": bd.get("media_count")})
            for m in bd.get("media", {}).get("data", []):
                ts = datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
                if ts < cutoff:
                    continue
                result["items"].append({
                    "teacher": t["id"], "source_type": "instagram", "handle": handle,
                    "type": m.get("media_product_type") or m.get("media_type"),
                    "url": m.get("permalink"), "published": ts.isoformat(),
                    "caption": (m.get("caption") or "")[:2000],
                    "likes": m.get("like_count"), "comments": m.get("comments_count"),
                })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"instagram: configured={result['configured']}, {len(result['items'])} recent items, "
          f"{len(result['errors'])} errors -> {out}")


if __name__ == "__main__":
    main()
