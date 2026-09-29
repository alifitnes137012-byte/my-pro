"""ربات تلگرامی که پیام کاربر را همراه با یک پرامپت ثابت به Claude می‌فرستد
و جواب را همان‌جا در تلگرام برمی‌گرداند."""

import json
import logging
import os
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv

import abjad
from anthropic import AsyncAnthropic
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
MAX_TOOL_ROUNDS = 5

# محاسبهٔ اعداد با پایتون انجام می‌شود تا مدل در جمع حروف اشتباه نکند
CALCULATE_TOOL = {
    "name": "calculate",
    "description": (
        "عدد ابجد کبیر ذکر اول (نام و نام خانوادگی)، ذکر دوم (نام و نام خانوادگی + نام مادر) "
        "و عدد ذکر سوم (جمع ارقام تاریخ تولد) را دقیق حساب می‌کند و برای هر عدد، "
        "نزدیک‌ترین اسماءالحسنی را همراه با عدد ابجدشان برمی‌گرداند."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "full_name": {"type": "string", "description": "نام و نام خانوادگی دقیقاً با املای کاربر"},
            "mother_name": {"type": "string", "description": "نام مادر دقیقاً با املای کاربر"},
            "birth_date": {"type": "string", "description": "تاریخ تولد با همان تقویمی که کاربر داده، مثلاً 1370/5/12"},
        },
        "required": ["full_name", "mother_name", "birth_date"],
    },
}
TOOL_INSTRUCTIONS = (
    "\n\nدستور فنی: همهٔ اعداد را فقط با ابزار calculate به دست بیاور و خودت هیچ جمعی انجام نده. "
    "از فهرست nearest_asma هر ذکر، با در نظر گرفتن نزدیکی عدد و تناسب معنا انتخاب کن. "
    "اگر نام، نام خانوادگی، نام مادر یا تاریخ تولد در پیام نیست، فقط همان اطلاعات کم را کوتاه بپرس."
)

load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
# عمق فکر کردن مدل: low / medium / high / xhigh / max (روی Haiku اثری ندارد)
CLAUDE_EFFORT = os.getenv("CLAUDE_EFFORT", "low")
HISTORY_LENGTH = int(os.getenv("HISTORY_LENGTH", "10"))
ALLOWED_USER_IDS = {
    int(x) for x in os.getenv("ALLOWED_USER_IDS", "").replace(" ", "").split(",") if x
}

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
for name in ("httpx", "httpx2"):
    logging.getLogger(name).setLevel(logging.WARNING)
log = logging.getLogger("bot")

client = AsyncAnthropic()  # ANTHROPIC_API_KEY را از محیط می‌خواند
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


async def ask_claude(messages: list) -> object:
    """درخواست را می‌فرستد و تا وقتی مدل ابزار calculate را صدا می‌زند، نتیجه را برمی‌گرداند."""
    messages = list(messages)
    request = dict(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        system=load_prompt() + TOOL_INSTRUCTIONS,
        tools=[CALCULATE_TOOL],
    )
    # Haiku این دو تنظیم را نمی‌پذیرد
    if not CLAUDE_MODEL.startswith("claude-haiku"):
        request["output_config"] = {"effort": CLAUDE_EFFORT}
        # اگر مدل درخواستی را رد کند، سرور خودش با مدل دیگری دوباره امتحان می‌کند
        request["betas"] = ["server-side-fallback-2026-07-01"]
        request["fallbacks"] = "default"
    create = client.beta.messages.create if "betas" in request else client.messages.create

    for _ in range(MAX_TOOL_ROUNDS):
        response = await create(messages=messages, **request)
        if response.stop_reason != "tool_use":
            return response
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                output, is_error = json.dumps(abjad.calculate(**block.input), ensure_ascii=False), False
            except Exception as exc:
                output, is_error = f"خطا: {exc}", True
            log.info("calculate %s -> %s", block.input, output[:200])
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": output, "is_error": is_error})
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": results})
    return response


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await update.message.reply_text("شما اجازهٔ استفاده از این ربات را ندارید.")
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)

    messages = [*history[chat_id], {"role": "user", "content": user_text}]
    try:
        response = await ask_claude(messages)
    except Exception:
        log.exception("Claude request failed")
        await update.message.reply_text("خطا در ارتباط با Claude. دوباره امتحان کنید.")
        return

    if response.stop_reason == "refusal":
        await update.message.reply_text("Claude به این درخواست پاسخ نداد.")
        return
    answer = "".join(b.text for b in response.content if b.type == "text").strip()
    answer = answer or "(پاسخ خالی)"

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
    log.info("Bot started with model %s", CLAUDE_MODEL)
    app.run_polling()


if __name__ == "__main__":
    main()
