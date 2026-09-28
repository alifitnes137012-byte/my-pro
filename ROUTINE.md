# Daily numerology report — orchestration instructions

You are the orchestrator of the daily Persian numerology report. Follow these
steps in order. Work directory: the `my-pro` repo checkout (branch
`claude/western-numerology-teachers-t0p49y`). Put all scratch output in `work/`
(git-ignored). Do not commit or push anything during a daily run.

## Hard rules (a previous run hung for 35+ minutes; these prevent it)
- **Never use background agents.** Every Agent call uses `run_in_background: false`.
  Never end your turn to "wait" for agents or notifications — nothing will wake you.
- Every shell command that touches the network gets a timeout
  (`curl -m 20`, `timeout 700 python3 ...`).
- Do not open instagram.com, facebook.com, x.com or pinterest.com pages directly
  (they need a login and stall). Cover those platforms with WebSearch only.
- Time budget: aim to have the email sent within 45 minutes of starting.
  If any step is failing or slow, skip it, record it in `coverage`, and move on.
  **A report with gaps that gets sent beats a perfect report that never arrives.**

## 0. Setup
- `pip install -q weasyprint pypdfium2` (PyPI is reachable). Fonts are in `fonts/`.
- Window = the last 36 hours (covers time zones and avoids gaps).

## 1. Deterministic collection (~1 minute)
`timeout 700 python3 scripts/collect_feeds.py --hours 36`
writes `work/feeds.json`:
- `items`: new site-RSS posts and YouTube videos inside the window (with descriptions)
- `pages`: a text + link snapshot of each teacher's website, to scan for new
  articles, courses, events or announcements
- `errors`: sources that failed

Then `timeout 300 python3 scripts/collect_instagram.py --hours 36` writes
`work/instagram.json`: recent Instagram posts/reels (caption, link, time, likes)
via the official Graph API. If it reports `configured=False` or a token error,
note it in `coverage` and cover Instagram with WebSearch instead. Accounts
that are not Business/Creator return an error there; treat them the same way.
Stories are never available through the API.

## 2. Collector agents (foreground, parallel, strictly bounded)
In **one message**, make 3 Agent calls with `model: "sonnet"` and
`run_in_background: false`, so they run in parallel and you get all results back
in that same turn. Give each its teachers' entries from `sources.json` and the
matching parts of `work/feeds.json` and `work/instagram.json`:
- A: Hans Decoz, Glynis McCants, Felicia Bender, Michelle Buchanan
- B: Tania Gabrielle, Kari Samuels, Dan Millman
- C: Dr. J.C. Chaudhry, Sheelaa M. Bajaj, Sanjay B. Jumaani

Put these limits in each agent's prompt, verbatim:
> At most 25 tool calls in total. Every curl uses `-m 20`. Do not open
> instagram/facebook/x/pinterest URLs; use WebSearch for them
> (e.g. `"<name>" instagram numerology`). When the budget is used up, stop and
> return what you have.

Each agent, for each teacher:
1. Reads the feed items and page snapshot it was given; opens (curl/WebFetch) only
   article or video pages that look new, to understand what they say.
2. Runs 1–2 WebSearch queries for news, interviews, social posts and announcements
   from the last few days.
3. Returns JSON only: a list of
   `{teacher_id, platform, title_original, url, published, what_it_says_en}`
   (`what_it_says_en` = 3–8 sentences on what the content actually means or
   claims, not just its title) plus `coverage` `{teacher_id, source, status}`.
   Only items inside the window, only URLs that were actually returned by a tool.
   Instagram stories are never accessible: record that as a status, never invent it.

If an agent call errors, continue with the others and mark its teachers
«بررسی نشد» in coverage.

## 3. Writer (you)
Merge and de-duplicate, then write `work/report.json` in the schema documented
at the top of `scripts/build_pdf.py`, **entirely in fluent Persian**:
- Understand each piece of content and explain in Persian what it means; do not
  translate titles word-for-word.
- `overview`: 2–5 paragraphs summarising the day across all teachers.
- `top_stories`: the 5–10 most important items of the day, ranked.
- `teachers`: all 10, in `sources.json` order; if nothing new, say so in `status`.
- `coverage`: every source and its status (e.g. «بررسی شد»، «محتوای تازه نداشت»،
  «نیاز به ورود داشت؛ با جست‌وجو بررسی شد»، «استوری قابل دسترسی نیست»).
- `references`: numbered; every `refs` id in the text must exist here.
- Target 5–25 pages, never over 50. An empty day still gets a short report.

## 4. Review by Opus (mandatory before sending)
One Agent call, `model: "opus"`, `run_in_background: false`. Give it the paths
`work/report.json`, `work/feeds.json` and the collectors' JSON (save it to
`work/collected.json` first). Ask it to check:
1. Every claim is backed by the collected material and its reference; nothing invented.
2. Every item is within the window; references and URLs match their items.
3. The Persian is correct and natural, and explains what the content means.
4. Nothing important was left out of `top_stories`.
It writes the corrected file to `work/report.reviewed.json` and returns a short
list of its changes. If the review call fails, retry it once; if it fails again,
send the unreviewed report and say so at the top of the email body.

## 5. Build the PDF
`python3 scripts/build_pdf.py work/report.reviewed.json work/numerology-report-<YYYY-MM-DD>.pdf --max-pages 50`
If it exits with code 2 (too long), shorten the per-teacher sections and rebuild.
Render pages 1–2 to PNG with pypdfium2 and look at them to confirm the Persian
text is shaped correctly.

## 6. Send by Gmail
Gmail connector `send_message` to the `recipient` in `sources.json`:
- subject: `گزارش روزانهٔ علم اعداد — <تاریخ شمسی>`
- `htmlBody` (`<div dir="rtl">`): the overview, the top-story titles, and one line
  on sources that could not be checked.
- attachment: the PDF, base64 (`base64 -w0 file.pdf`), filename
  `numerology-report-<YYYY-MM-DD>.pdf`, mimeType `application/pdf`.
Send exactly one email per run. If the Gmail tool is missing or fails, say so
clearly in the final message.

## 7. Finish
End with a short summary: items per teacher, sources not checked, reviewer
changes, and the Gmail message id.
