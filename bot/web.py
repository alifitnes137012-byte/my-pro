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
from pathlib import Path
from urllib.parse import parse_qsl

from flask import Flask, abort, jsonify, request, send_from_directory
from telegram import MenuButtonWebApp, Update, WebAppInfo
from telegram.error import InvalidToken, NetworkError, TelegramError

from .card import ASSETS, FONTS, render
from .main import ACTIVE_FLOWS, ROOT, build_app, load_token, send_result, validate

TOKEN = load_token()
if not re.fullmatch(r"\d{5,}:[A-Za-z0-9_-]{30,}", TOKEN):
    raise ValueError(
        "توکن داخل token.txt شکل درستی ندارد. توکن باید مثل 7123456789:AAH... باشد "
        f"(اول عدد، بعد یک دونقطه، بعد حروف انگلیسی). الان {len(TOKEN)} حرف دارد و با "
        f"«{TOKEN[:4]}» شروع می‌شود."
    )
SECRET = hashlib.sha256(TOKEN.encode()).hexdigest()[:32]
WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"

# PythonAnywhere رایگان هر پروسه را تک‌نخی اجرا می‌کند، پس یک event loop کافی است.
loop = asyncio.new_event_loop()
bot_app = build_app(TOKEN, updater=None)
app = Flask(__name__, static_folder=None)

# اتصال به تلگرام در اولین درخواستی که لازمش دارد انجام می‌شود، با چند بار تلاش.
# اگر پراکسی PythonAnywhere لحظه‌ای قطع باشد، سایت از کار نمی‌افتد و دفعهٔ بعد دوباره تلاش می‌کند.
NEEDS_BOT = {"/webhook", "/setup", "/api/compute"}


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
        f"✅ مینی اپ: {base}app<br>حالا در تلگرام /start بزنید."
    )


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

    result = flow.compute(values, user["id"])
    if result is None:
        return jsonify(ok=False, error="با این اطلاعات عددی که همهٔ شرط‌ها را داشته باشد پیدا نشد.")

    # نتیجه در چت هم فرستاده می‌شود تا ذخیره بماند
    try:
        loop.run_until_complete(send_result(bot_app.bot, user["id"], result))
        sent = True
    except TelegramError:
        sent = False
    card = base64.b64encode(render(result.title, result.name, result.items)).decode()
    return jsonify(
        ok=True,
        title=result.title,
        name=result.name,
        items=[{"label": a, "value": b, "sub": c} for a, b, c in result.items],
        card=card,
        sent=sent,
    )
