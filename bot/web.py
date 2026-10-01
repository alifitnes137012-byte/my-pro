"""اجرای ۲۴ ساعته روی PythonAnywhere: وب‌هوک تلگرام + مینی اپ.

- /webhook : تلگرام پیام‌ها را این‌جا می‌فرستد
- /setup   : یک بار در مرورگر باز شود؛ وب‌هوک و دکمهٔ مینی اپ را ثبت می‌کند
- /app     : خود مینی اپ (صفحهٔ وب داخل تلگرام)
- /api/... : محاسبه برای مینی اپ
"""

import asyncio
import base64
import hashlib
import hmac
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl

from flask import Flask, Response, abort, jsonify, request, send_from_directory
from telegram import MenuButtonWebApp, Update, WebAppInfo
from telegram.error import InvalidToken, NetworkError, TelegramError

from . import challenge
from . import main as main_module
from . import report
from .card import ASSETS, FONTS, render
from .main import ACTIVE_FLOWS, ROOT, build_app, load_token, send_result, validate
from .storage import (
    TEHRAN,
    challenge_complete,
    challenge_register,
    challenge_user,
    get_phone,
    records_for_day,
    save_record,
)

# سرور تک‌کارگره است؛ مکث عمدی برای انیمیشن باعث صف شدن بقیهٔ کاربران می‌شود
main_module.LOADING_SECONDS = 0
TOKEN = load_token()
if not re.fullmatch(r"\d{5,}:[A-Za-z0-9_-]{30,}", TOKEN):
    raise ValueError(
        "توکن داخل token.txt شکل درستی ندارد. توکن باید مثل 7123456789:AAH... باشد "
        f"(اول عدد، بعد یک دونقطه، بعد حروف انگلیسی). الان {len(TOKEN)} حرف دارد و با "
        f"«{TOKEN[:4]}» شروع می‌شود."
    )
SECRET = hashlib.sha256(TOKEN.encode()).hexdigest()[:32]
REPORT_KEY = hashlib.sha256(b"report" + TOKEN.encode()).hexdigest()[:20]
WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"

# PythonAnywhere رایگان هر پروسه را تک‌نخی اجرا می‌کند، پس یک event loop کافی است.
loop = asyncio.new_event_loop()
bot_app = build_app(TOKEN, updater=None)
app = Flask(__name__, static_folder=None)

# اتصال به تلگرام در اولین درخواستی که لازمش دارد انجام می‌شود، با چند بار تلاش.
# اگر پراکسی PythonAnywhere لحظه‌ای قطع باشد، سایت از کار نمی‌افتد و دفعهٔ بعد دوباره تلاش می‌کند.
NEEDS_BOT = {"/webhook", "/setup", "/api/compute", "/api/challenge/day"}


@app.before_request
def ensure_bot_ready():
    if request.path not in NEEDS_BOT or bot_app._initialized:
        return None
    error = None
    for attempt in range(3):
        try:
            loop.run_until_complete(bot_app.initialize())
            return None
        except InvalidToken:
            return "❌ تلگرام این توکن را قبول نکرد. توکن را دوباره از BotFather کپی کنید و در token.txt بگذارید.", 500
        except NetworkError as exc:
            error = exc
            time.sleep(2 * (attempt + 1))
    return (
        "⏳ اتصال به تلگرام از طریق PythonAnywhere فعلاً برقرار نشد. چند دقیقه بعد دوباره همین صفحه را باز کنید."
        f"<br><small>{type(error).__name__}: {error}</small>",
        503,
    )


@app.post("/webhook")
def webhook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET:
        abort(403)
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    loop.run_until_complete(bot_app.process_update(update))
    loop.run_until_complete(bot_app.update_persistence())
    return "ok"


@app.get("/setup")
def setup():
    base = request.host_url.replace("http://", "https://")
    (ROOT / "webapp_url.txt").write_text(base + "app")
    bot = bot_app.bot
    loop.run_until_complete(bot.set_webhook(base + "webhook", secret_token=SECRET))
    loop.run_until_complete(
        bot.set_chat_menu_button(menu_button=MenuButtonWebApp("مینی اپ", WebAppInfo(base + "app")))
    )
    return (
        f"✅ وب‌هوک ثبت شد: {base}webhook<br>"
        f"✅ مینی اپ: {base}app<br>حالا در تلگرام /start بزنید.<br><br>"
        f"📧 لینک ارسال گزارش روزانه (برای cron-job.org):<br><code>{base}report?key={REPORT_KEY}</code><br>"
        f"📥 دانلود اکسل امروز: <a href='{base}report?key={REPORT_KEY}&download=1'>دانلود</a>"
    )


@app.get("/report")
def daily_report():
    if request.args.get("key") != REPORT_KEY:
        abort(403)
    day = request.args.get("date") or datetime.now(TEHRAN).strftime("%Y-%m-%d")
    if request.args.get("download"):
        xlsx = report.build_excel(day, records_for_day(day))
        return Response(
            xlsx,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=report-{day}.xlsx"},
        )
    try:
        count = report.send_report(day)
    except Exception as exc:  # خطای ایمیل نباید سایت را از کار بیندازد
        return f"❌ ارسال ایمیل ناموفق بود: {type(exc).__name__}: {exc}", 500
    return f"✅ گزارش {day} با {count} ردیف به {report.REPORT_TO} فرستاده شد."


@app.after_request
def catch_up_report(response):
    """پشتیبان: اگر گزارش دیروز فرستاده نشده، بعد از اولین درخواست امروز فرستاده می‌شود."""
    day = report.yesterday()
    if request.path == "/webhook" and day not in report.sent_days() and (ROOT / "mail.txt").exists():
        global _last_catch_up
        if time.time() - _last_catch_up > 3600:  # اگر ایمیل خطا داد، هر ساعت یک بار دوباره
            _last_catch_up = time.time()
            try:
                report.send_report(day)
            except Exception:
                app.logger.exception("daily report catch-up failed")
    return response


_last_catch_up = 0.0


@app.get("/")
def home():
    return "مینی اپ استاد فاطمه سادات جعفرنیا روشن است ✅"


# ───────────────────────── مینی اپ ─────────────────────────


@app.get("/app")
def webapp():
    return send_from_directory(WEBAPP_DIR, "index.html")


@app.get("/static/<path:name>")
def static_files(name: str):
    folder = FONTS if name.endswith(".ttf") else ASSETS
    return send_from_directory(folder, name, max_age=7 * 24 * 3600)


def telegram_user(init_data: str) -> dict | None:
    """بررسی امضای initData تلگرام؛ فقط درخواست‌هایی که واقعاً از داخل تلگرام آمده‌اند قبول می‌شوند."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", "")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received, expected):
        return None
    if time.time() - int(pairs.get("auth_date", 0)) > 24 * 3600:
        return None
    return json.loads(pairs.get("user", "null"))


@app.get("/api/flows")
def flows():
    return jsonify(
        [
            {
                "key": f.key,
                "title": f.button,
                "intro": f.intro,
                "fields": [
                    {"key": x.key, "label": x.label, "prompt": x.prompt, "kind": x.kind, "optional": x.optional}
                    for x in f.fields
                ],
            }
            for f in ACTIVE_FLOWS
        ]
    )


@app.post("/api/compute")
def compute():
    body = request.get_json(force=True)
    user = telegram_user(body.get("initData", ""))
    if not user:
        return jsonify(ok=False, error="لطفاً مینی اپ را از داخل تلگرام باز کنید."), 403
    flow = next((f for f in ACTIVE_FLOWS if f.key == body.get("flow")), None)
    if not flow:
        abort(404)

    values, errors = {}, {}
    raw = body.get("values", {})
    for field in flow.fields:
        if field.kind == "phone":  # فقط شمارهٔ تأییدشده از دکمهٔ «ارسال شمارهٔ من»
            values[field.key] = get_phone(user["id"])
            if not values[field.key]:
                errors[field.key] = "دکمهٔ «ارسال شمارهٔ من» را بزنید و در پنجرهٔ تلگرام «Share» را تأیید کنید"
            continue
        text = str(raw.get(field.key, "")).strip()
        if field.optional and not text:
            values[field.key] = ""
            continue
        value, error = validate(field, text)
        if error:
            errors[field.key] = error.replace("⚠️ ", "").rstrip(":")
        values[field.key] = value
    if errors:
        return jsonify(ok=False, errors=errors)

    save_record(values["full"], values["phone"])
    result = flow.compute(values, user["id"])
    if result is None:
        return jsonify(ok=False, error="با این اطلاعات عددی که همهٔ شرط‌ها را داشته باشد پیدا نشد.")

    # نتیجه در چت هم فرستاده می‌شود تا ذخیره بماند
    try:
        photo = render(result.title, result.name, result.items)
        markup = main_module.miniapp_markup("🌙 بازگشت به مینی اپ")
        loop.run_until_complete(send_result(bot_app.bot, user["id"], result, reply_markup=markup, photo=photo))
        sent = True
    except TelegramError:
        sent = False
    card = base64.b64encode(photo).decode()
    return jsonify(
        ok=True,
        title=result.title,
        name=result.name,
        items=[{"label": a, "value": b, "sub": c} for a, b, c in result.items],
        card=card,
        sent=sent,
    )


# ───────────────────────── چالش ۱۰ روزه ─────────────────────────


def _challenge_user():
    body = request.get_json(force=True, silent=True) or {}
    return body, telegram_user(body.get("initData", ""))


NOT_IN_TELEGRAM = "لطفاً مینی اپ را از داخل تلگرام باز کنید."


@app.post("/api/challenge")
def challenge_state():
    _, user = _challenge_user()
    if not user:
        return jsonify(ok=False, error=NOT_IN_TELEGRAM), 403
    member = challenge_user(user["id"])
    return jsonify(
        ok=True,
        title=challenge.TITLE,
        intro=challenge.INTRO,
        registered=bool(member),
        name=member["full"] if member else "",
        days=challenge.status(user["id"]),
    )


@app.post("/api/challenge/register")
def challenge_signup():
    body, user = _challenge_user()
    if not user:
        return jsonify(ok=False, error=NOT_IN_TELEGRAM), 403
    errors = {}
    full, error = main_module.validate(main_module.Field("full", "", "", kind="fullname"), str(body.get("full", "")))
    if error:
        errors["full"] = error.replace("⚠️ ", "").rstrip(":")
    phone = get_phone(user["id"])
    if not phone:
        errors["phone"] = "دکمهٔ «ارسال شمارهٔ من» را بزنید و در پنجرهٔ تلگرام «Share» را تأیید کنید"
    if errors:
        return jsonify(ok=False, errors=errors)
    challenge_register(user["id"], full, phone)
    save_record(full, phone)
    return jsonify(ok=True)


@app.post("/api/challenge/day")
def challenge_day():
    body, user = _challenge_user()
    if not user:
        return jsonify(ok=False, error=NOT_IN_TELEGRAM), 403
    member = challenge_user(user["id"])
    if not member:
        return jsonify(ok=False, error="اول در چالش ثبت‌نام کنید."), 400
    day = challenge.BY_N.get(int(body.get("day") or 0))
    if not day:
        abort(404)
    state = next(x for x in challenge.status(user["id"]) if x["n"] == day.n)
    if state["state"] == "done":
        return jsonify(ok=False, error="این روز را قبلاً انجام داده‌اید."), 409
    if state["state"] != "open":
        return jsonify(ok=False, error="این روز هنوز باز نشده است."), 409

    raw, values, errors = body.get("values") or {}, {}, {}
    for q in day.questions:
        values[q.key], error = challenge.check(q, raw.get(q.key))
        if error:
            errors[q.key] = error
    if errors:
        return jsonify(ok=False, errors=errors)

    result = challenge.run_day(day, values, user["id"])
    if not challenge_complete(user["id"], day.n, result):
        return jsonify(ok=False, error="این روز را قبلاً انجام داده‌اید."), 409
    save_record(member["full"], member["phone"])  # در اکسل همان روز هم بیاید

    # نتیجه و پیام روز بعد در چت هم فرستاده می‌شود
    try:
        markup = main_module.miniapp_markup("🌙 بازگشت به چالش")
        text = challenge.chat_text(result, member["full"])
        bot = bot_app.bot
        if result["items"] and len(text) <= 1024:
            items = [(x["label"], x["value"], x["sub"]) for x in result["items"][:3]]
            photo = render(result["title"], member["full"], items)
            loop.run_until_complete(bot.send_photo(user["id"], photo, caption=text, reply_markup=markup))
        else:
            loop.run_until_complete(bot.send_message(user["id"], text, reply_markup=markup))
        sent = True
    except TelegramError:
        sent = False
    return jsonify(ok=True, result=result, sent=sent, days=challenge.status(user["id"]))
