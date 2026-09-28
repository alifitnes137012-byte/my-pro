# Daily numerology report — orchestration instructions

You are the orchestrator of the daily Persian numerology report. Follow these
steps in order. Work directory: the `my-pro` repo checkout (branch
`claude/western-numerology-teachers-t0p49y`). Put all scratch output in `work/`
(git-ignored). Do not commit or push anything during a daily run.

## 0. Setup
- `pip install -q weasyprint` (PyPI is reachable). Fonts are in `fonts/`.
- Today's window = the last 36 hours (to cover time-zone differences and avoid gaps).

## 1. Deterministic pass
Run `python3 scripts/collect_feeds.py --hours 36`. It writes `work/feeds.json`
(site RSS + YouTube feeds) and lists any sources it could not reach.

## 2. Collector agents (run in parallel, `model: "sonnet"`)
Spawn 4 collector agents with the Agent tool, each given its teachers' full
entry from `sources.json` plus the relevant part of `work/feeds.json`:
- A: Hans Decoz, Glynis McCants, Felicia Bender
- B: Michelle Buchanan, Tania Gabrielle, Kari Samuels, Dan Millman
- C: Dr. J.C. Chaudhry, Sheelaa M. Bajaj
- D: Sanjay B. Jumaani + a WebSearch sweep for news *about* all ten teachers (interviews, press, new books/courses)

Each collector must, for each of its teachers:
1. Check the website (home, blog/articles, news/media pages) with WebFetch or curl.
2. YouTube: new videos/Shorts/lives in the window. When a transcript tool is
   available (e.g. `vidiq_video_transcript`), read the transcript to understand the content.
3. Instagram: posts/reels in the window (e.g. `vidiq_ig_profile_reels` if the
   vidIQ account has credits, otherwise the public page). **Stories cannot be read
   by any available tool** — record that as "not accessible", never invent it.
4. X, Facebook, Pinterest, Linktree: whatever is publicly readable.
5. If a source is blocked or needs login, fall back to WebSearch
   (e.g. `"<name>" numerology` limited to the last days) and record the status.

Collectors return JSON only: a list of
`{teacher_id, platform, title_original, url, published, what_it_says_en}`
(`what_it_says_en` = 3–8 sentences on what the content actually means/claims,
not just its title), plus a `coverage` list `{teacher_id, source, status}`.
Rules: only items published inside the window; every item needs a real URL
that was actually opened or returned by a tool; no guessing.

## 3. Writer (you, the orchestrator)
Merge and de-duplicate the collectors' output, then write `work/report.json`
in the schema documented at the top of `scripts/build_pdf.py`, **entirely in
fluent Persian**:
- Understand each piece of content and explain in Persian what it means — do
  not translate titles literally or word-for-word.
- `overview`: 2–5 paragraphs summarising the day across all teachers.
- `top_stories`: the 5–10 most important items of the day, ranked.
- `teachers`: one section per teacher (all 10, in `sources.json` order); if
  nothing new, set `status` to say so.
- `coverage`: every source checked and its status (e.g. «بررسی شد»، «محتوای
  تازه نداشت»، «مسدود بود»، «استوری قابل دسترسی نیست»).
- `references`: numbered; every `refs` id in the text must exist here.
- Keep it well under 50 pages (the target is 5–25). If a day is empty, still
  produce a short report that says so.

## 4. Review by Opus (mandatory before sending)
Spawn a reviewer with the Agent tool, `model: "opus"`, `run_in_background: false`.
Give it `work/report.json` and the collectors' raw JSON and ask it to check:
1. Every claim is backed by the collected material and its reference; no invented items.
2. Every item is within the date window; references and URLs match their items.
3. The Persian is correct, natural and actually explains the content's meaning.
4. Nothing important from the raw material was left out of `top_stories`.
The reviewer returns a corrected `report.json` (written to `work/report.reviewed.json`)
and a short list of the changes it made. Use the reviewed file from now on.

## 5. Build the PDF
`python3 scripts/build_pdf.py work/report.reviewed.json work/numerology-report-<YYYY-MM-DD>.pdf --max-pages 50`
If it exits with code 2 (too long), shorten the per-teacher sections and rebuild.
Render page 1–2 to PNG (`pypdfium2`) and look at them to confirm the Persian text
is shaped correctly (not disconnected letters or boxes).

## 6. Send by Gmail
Use the Gmail connector's `send_message` to the `recipient` in `sources.json`:
- subject: `گزارش روزانهٔ علم اعداد — <تاریخ شمسی>`
- `htmlBody` (dir="rtl"): the overview plus the top-story titles, and a one-line
  note on sources that were not reachable.
- attachment: the PDF (base64), filename `numerology-report-<YYYY-MM-DD>.pdf`,
  mimeType `application/pdf`.
Send exactly one email per run. If sending fails, say why in the final message.

## 7. Finish
End with a short summary: items found per teacher, sources that were blocked,
reviewer changes, and the Gmail message id.
