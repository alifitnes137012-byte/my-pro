"""ربات تلگرامی که پیام کاربر را همراه با یک پرامپت ثابت به ChatGPT می‌فرستد
و جواب را همان‌جا در تلگرام برمی‌گرداند."""

import logging
import os
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BASE_DIR = Path(__file__).resolve().parent
PROMPT_FILE = BASE_DIR / "prompt.txt"
TELEGRAM_LIMIT = 4096

load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
HISTORY_LENGTH = int(os.getenv("HISTORY_LENGTH", "10"))
ALLOWED_USER_IDS = {
    int(x) for x in os.getenv("ALLOWED_USER_IDS", "").replace(" ", "").split(",") if x
}

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bot")

client = AsyncOpenAI()  # OPENAI_API_KEY را از محیط می‌خواند
history: dict[int, deque] = defaultdict(lambda: deque(maxlen=HISTORY_LENGTH * 2))


def load_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8").strip() if PROMPT_FILE.exists() else ""


def is_allowed(update: Update) -> bool:
    return not ALLOWED_USER_IDS or update.effective_user.id in ALLOWED_USER_IDS


def split_message(text: str) -> list[str]:
    """پیام‌های طولانی‌تر از سقف تلگرام را در مرز خط‌ها تکه می‌کند."""
    chunks = []
    while len(text) > TELEGRAM_LIMIT:
        cut = text.rfind("\n", 0, TELEGRAM_LIMIT)
        if cut <= 0:
            cut = TELEGRAM_LIMIT
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "سلام! متن یا داده‌هایت را بفرست تا طبق پرامپت تنظیم‌شده محاسبه کنم.\n\n"
        "دستورها:\n"
        "/prompt — نمایش پرامپت فعلی\n"
        "/setprompt متن — تغییر پرامپت\n"
        "/reset — پاک کردن حافظهٔ گفتگو\n"
        "/myid — نمایش آیدی عددی شما"
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(str(update.effective_user.id))


async def show_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    await update.message.reply_text(load_prompt() or "پرامپتی تنظیم نشده است.")


async def set_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    # متن بعد از خود دستور، با حفظ خط‌های جدید
    new_prompt = update.message.text.partition(" ")[2].strip()
    if not new_prompt:
        await update.message.reply_text("بعد از /setprompt متن پرامپت را بنویسید.")
        return
    PROMPT_FILE.write_text(new_prompt + "\n", encoding="utf-8")
    history.clear()
    await update.message.reply_text("پرامپت ذخیره شد و حافظهٔ گفتگوها پاک شد.")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    history.pop(update.effective_chat.id, None)
    await update.message.reply_text("حافظهٔ گفتگو پاک شد.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await update.message.reply_text("شما اجازهٔ استفاده از این ربات را ندارید.")
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)

    messages = []
    prompt = load_prompt()
    if prompt:
        messages.append({"role": "system", "content": prompt})
    messages.extend(history[chat_id])
    messages.append({"role": "user", "content": user_text})

    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL, messages=messages
        )
        answer = response.choices[0].message.content or "(پاسخ خالی)"
    except Exception:
        log.exception("OpenAI request failed")
        await update.message.reply_text("خطا در ارتباط با ChatGPT. دوباره امتحان کنید.")
        return

    history[chat_id].append({"role": "user", "content": user_text})
    history[chat_id].append({"role": "assistant", "content": answer})

    for chunk in split_message(answer):
        await update.message.reply_text(chunk)


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("prompt", show_prompt))
    app.add_handler(CommandHandler("setprompt", set_prompt))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("Bot started with model %s", OPENAI_MODEL)
    app.run_polling()


if __name__ == "__main__":
    main()
