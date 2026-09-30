"""اجرای ۲۴ ساعته روی PythonAnywhere (وب‌هوک تلگرام با Flask).

تلگرام هر پیام را به آدرس /webhook می‌فرستد. بعد از راه‌اندازی، یک بار آدرس
/setup سایت را در مرورگر باز کنید تا وب‌هوک ثبت شود.
"""

import asyncio
import hashlib

from flask import Flask, abort, request
from telegram import Update

from .main import build_app, load_token

TOKEN = load_token()
SECRET = hashlib.sha256(TOKEN.encode()).hexdigest()[:32]

# PythonAnywhere رایگان هر پروسه را تک‌نخی اجرا می‌کند، پس یک event loop کافی است.
loop = asyncio.new_event_loop()
bot_app = build_app(TOKEN, updater=None)
loop.run_until_complete(bot_app.initialize())

app = Flask(__name__)


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
    url = request.host_url.replace("http://", "https://") + "webhook"
    loop.run_until_complete(bot_app.bot.set_webhook(url, secret_token=SECRET))
    return f"✅ وب‌هوک ثبت شد: {url}<br>حالا در تلگرام /start بزنید."


@app.get("/")
def home():
    return "مینی اپ علم اعداد روشن است ✅"
