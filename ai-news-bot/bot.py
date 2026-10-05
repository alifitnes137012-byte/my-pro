#!/usr/bin/env python3
"""Daily AI-news -> Persian Instagram Reel script -> Telegram.

Env: GEMINI_API_KEY (preferred, free) or ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Flags: --dry-run  print the message instead of sending it
"""
import json, os, re, sys, time, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

HERE = Path(__file__).parent
STATE = HERE / "state.json"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://openai.com/news/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://huggingface.co/blog/feed.xml",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "https://deepmind.google/blog/rss.xml",
    "https://blogs.nvidia.com/feed/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://the-decoder.com/feed/",
]
HN_AI = re.compile(r"\b(ai|llm|gpt|claude|gemini|openai|anthropic|deepseek|model|agent)\b", re.I)


def get(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "ai-news-bot", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=170) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} from {url.split('?')[0].split('/bot')[0]}: {e.read().decode(errors='replace')[:500]}")


def parse_date(s):
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def collect(hours=24):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    items = []
    for url in FEEDS:
        try:
            root = ET.fromstring(get(url))
        except Exception as e:
            print(f"feed failed {url}: {e}", file=sys.stderr)
            continue
        for it in root.iter():
            tag = it.tag.split("}")[-1]
            if tag not in ("item", "entry"):
                continue
            f = lambda n: next((c for c in it if c.tag.split("}")[-1] == n), None)
            title = (f("title").text or "").strip() if f("title") is not None else ""
            link_el = f("link")
            link = (link_el.text or link_el.get("href") or "").strip() if link_el is not None else ""
            d_el = next((e for e in map(f, ("pubDate", "published", "updated")) if e is not None), None)
            date = parse_date(d_el.text) if d_el is not None and d_el.text else None
            desc_el = next((e for e in map(f, ("description", "summary", "content")) if e is not None), None)
            desc = re.sub(r"<[^>]+>", " ", desc_el.text or "")[:300] if desc_el is not None else ""
            if not title or not link or not date or date < cutoff:
                continue
            if "ycombinator" in url and not HN_AI.search(title):
                continue
            items.append({"date": date, "title": title, "url": link, "summary": " ".join(desc.split()), "source": url.split("/")[2]})
    items.sort(key=lambda i: i["date"], reverse=True)
    return items


N_REELS = int(os.environ.get("N_REELS", "10"))

PROMPT = """You are a Persian-language Instagram Reels scriptwriter for an AI-news page.
From the news items below pick the {n} most important / viral-worthy DIFFERENT stories for today, ranked best first
(prefer major launches, big-company moves, surprising results; skip pure opinion and duplicate coverage of the same event).
If fewer than {n} good distinct stories exist, return fewer. Each story = one separate Reel.
Write everything in fluent, natural, conversational Persian (Farsi); tech terms may stay in English.

Return ONLY JSON: {{"reels": [ {{
 "story_index": <index of the item>,
 "hook": "first 3 seconds, <=12 words, scroll-stopping, curiosity/shock, no clickbait lie",
 "body": ["3-4 short punchy lines, each one spoken beat, simple words, concrete facts/numbers"],
 "cta": "one line asking to follow / comment a specific keyword / save+share",
 "on_screen_text": ["3-5 short captions to overlay on the video"],
 "visual_notes": "b-roll/visual ideas per beat, 1-2 sentences",
 "caption": "Instagram caption, 2-3 lines + question to drive comments",
 "hashtags": ["10-12 hashtags, mix Persian/English"]
}} ]}}
Constraint per reel: hook+body+cta spoken total MUST be 110-140 Persian words (~45-55 seconds). Do not invent facts beyond the items.

NEWS ITEMS:
{items}
"""


def gemini(prompt):
    models = [os.environ["GEMINI_MODEL"]] if os.environ.get("GEMINI_MODEL") else ["gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"]
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 32000}}).encode()
    out = None
    for attempt in range(4):
        for model in models:
            try:
                out = json.loads(get(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", body, {
                    "x-goog-api-key": os.environ["GEMINI_API_KEY"], "content-type": "application/json"}))
                break
            except RuntimeError as e:
                err = e
                print(f"{model}: {str(e)[:120]!r}, trying next/retrying", file=sys.stderr)
        if out:
            break
        time.sleep(10 * (attempt + 1))
    if not out:
        raise err
    text = out["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def claude(prompt):
    body = json.dumps({"model": MODEL, "max_tokens": 16000, "messages": [{"role": "user", "content": prompt}]}).encode()
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    out = json.loads(get(f"{base}/v1/messages", body, {
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
        "content-type": "application/json"}))
    text = out["content"][0]["text"]
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def format_msg(s, story, n, total):
    words = len(" ".join([s["hook"], *s["body"], s["cta"]]).split())
    lines = [
        f"🎬 ریلز {n} از {total}", "",
        f"📰 خبر: {story['title']}", f"🗞 منبع: {story['source']} | 🕒 {story['date'].strftime('%Y-%m-%d %H:%M')} UTC", f"🔗 {story['url']}", "",
        f"🪝 هوک (۳ ثانیه اول):\n{s['hook']}", "",
        "📖 بدنه:\n" + "\n".join(f"{i}. {b}" for i, b in enumerate(s["body"], 1)), "",
        f"📣 CTA:\n{s['cta']}", "",
        "🖼 متن روی ویدیو:\n" + "\n".join(f"• {t}" for t in s["on_screen_text"]), "",
        f"🎥 ایده تصویری:\n{s['visual_notes']}", "",
        f"✍️ کپشن:\n{s['caption']}", "", " ".join("#" + h.lstrip("#").replace(" ", "_") for h in s["hashtags"]), "",
        f"⏱ حدود {words} کلمه ≈ {round(words / 2.6)} ثانیه",
    ]
    return "\n".join(lines)


def telegram(text):
    tok, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    for i in range(0, len(text), 4000):
        get(f"https://api.telegram.org/bot{tok}/sendMessage",
            json.dumps({"chat_id": chat, "text": text[i:i + 4000], "disable_web_page_preview": True}).encode(),
            {"content-type": "application/json"})


def main():
    seen = set(json.loads(STATE.read_text())) if STATE.exists() else set()
    items = [i for i in collect(24) if i["url"] not in seen]
    if len(items) < N_REELS * 2:  # too few fresh stories: widen the window to 48h
        items = [i for i in collect(48) if i["url"] not in seen]
    per_source, picked = {}, []
    for i in items:  # newest first, max 6 per source for variety
        if per_source.get(i["source"], 0) < 6:
            per_source[i["source"]] = per_source.get(i["source"], 0) + 1
            picked.append(i)
    items = picked[:60]
    if not items:
        print("no new items"); return
    listing = "\n".join(f"[{n}] ({i['source']}) {i['title']} — {i['summary']}" for n, i in enumerate(items))
    llm = gemini if os.environ.get("GEMINI_API_KEY") else claude
    reels, used = [], set()
    for r in llm(PROMPT.format(n=N_REELS, items=listing))["reels"]:
        try:
            idx = int(r["story_index"])
            if idx in used or not 0 <= idx < len(items):
                continue
            format_msg(r, items[idx], 1, 1)  # validate fields
        except (KeyError, ValueError, TypeError) as e:
            print(f"skipping malformed reel: {e!r}", file=sys.stderr)
            continue
        used.add(idx)
        reels.append((items[idx], r))
    reels = reels[:N_REELS]
    reels = [(st, format_msg(r, st, n, len(reels))) for n, (st, r) in enumerate(reels, 1)]
    if "--dry-run" in sys.argv:
        print("\n\n=====\n\n".join(m for _, m in reels)); return
    sent = set()
    try:
        for n, (story, msg) in enumerate(reels, 1):
            telegram(msg)
            sent.add(story["url"])
            print(f"sent {n}/{len(reels)}:", story["title"])
            time.sleep(1.5)
    finally:
        STATE.write_text(json.dumps(sorted(seen | sent)[-500:], indent=1))


if __name__ == "__main__":
    main()
