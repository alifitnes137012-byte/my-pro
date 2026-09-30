"""ربات تلگرامی «مینی اپ علم اعداد».

اجرا:  python -m bot.main   (متغیر TELEGRAM_BOT_TOKEN لازم است)
"""

import logging
import os
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .abjad import abjad, to_ascii_digits, unknown_letters
from .zikr import Person, design

logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO)

BTN_ZIKR = "✨ طراحی ذکر شخصی"
BTN_CANCEL = "❌ انصراف"

# دکمه‌های بعدی منو را این‌جا اضافه کنید (هر لیست یک ردیف است).
MAIN_MENU = ReplyKeyboardMarkup([[BTN_ZIKR]], resize_keyboard=True)
CANCEL_KB = ReplyKeyboardMarkup([[BTN_CANCEL]], resize_keyboard=True)

FIRST, LAST, MOTHER, DATE, CONFIRM = range(5)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "به مینی اپ علم اعداد خوش آمدید 🌙\nلطفاً یکی از گزینه‌های منو را انتخاب کنید.",
        reply_markup=MAIN_MENU,
    )
    return ConversationHandler.END


def _bad_name(text: str) -> bool:
    return not text or abjad(text) == 0 or bool(unknown_letters(text))


async def zikr_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "لطفاً «نام» خود را مطابق شناسنامه و به فارسی وارد کنید:", reply_markup=CANCEL_KB
    )
    return FIRST


async def got_first(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if _bad_name(text):
        await update.message.reply_text("لطفاً نام را فقط با حروف فارسی بنویسید:")
        return FIRST
    context.user_data["first"] = text
    await update.message.reply_text("«نام خانوادگی» خود را وارد کنید:")
    return LAST


async def got_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if _bad_name(text):
        await update.message.reply_text("لطفاً نام خانوادگی را فقط با حروف فارسی بنویسید:")
        return LAST
    context.user_data["last"] = text
    await update.message.reply_text("«نام مادر» را مطابق شناسنامه وارد کنید:")
    return MOTHER


async def got_mother(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if _bad_name(text):
        await update.message.reply_text("لطفاً نام مادر را فقط با حروف فارسی بنویسید:")
        return MOTHER
    context.user_data["mother"] = text
    await update.message.reply_text(
        "«تاریخ تولد» را به شکل سال/ماه/روز وارد کنید.\n"
        "مثال: ۱۳۷۰/۰۵/۱۲\n"
        "اگر تاریخ واقعی تولد با شناسنامه فرق دارد، تاریخ واقعی را بنویسید."
    )
    return DATE


def parse_date(text: str) -> tuple[int, int, int] | None:
    """خروجی (روز، ماه، سال). هم «سال/ماه/روز» و هم «روز/ماه/سال» پذیرفته می‌شود."""
    parts = [int(x) for x in re.findall(r"\d+", to_ascii_digits(text))]
    if len(parts) != 3:
        return None
    if parts[0] > 31:
        year, month, day = parts
    elif parts[2] > 31:
        day, month, year = parts
    else:
        return None
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1000 <= year <= 3000):
        return None
    return day, month, year


def _summary(d: dict) -> str:
    day, month, year = d["date"]
    return (
        "لطفاً اطلاعات را بررسی کنید:\n\n"
        f"نام: {d['first']}\n"
        f"نام خانوادگی: {d['last']}\n"
        f"نام مادر: {d['mother']}\n"
        f"تاریخ تولد: {year}/{month:02d}/{day:02d}"
    )


CONFIRM_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("✅ ارسال", callback_data="zikr:send")],
        [
            InlineKeyboardButton("✏️ ویرایش", callback_data="zikr:edit"),
            InlineKeyboardButton("❌ انصراف", callback_data="zikr:cancel"),
        ],
    ]
)


async def got_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    date = parse_date(update.message.text)
    if not date:
        await update.message.reply_text("تاریخ معتبر نیست. لطفاً مثل ۱۳۷۰/۰۵/۱۲ وارد کنید:")
        return DATE
    context.user_data["date"] = date
    await update.message.reply_text(_summary(context.user_data), reply_markup=CONFIRM_KB)
    return CONFIRM


async def on_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]

    if action == "edit":
        await query.edit_message_reply_markup(None)
        return await zikr_start(update, context)
    if action == "cancel":
        await query.edit_message_reply_markup(None)
        return await cancel(update, context)

    d = context.user_data
    await query.edit_message_text(_summary(d) + "\n\n⏳ در حال محاسبه، لطفاً کمی صبر کنید...")
    person = Person(d["first"], d["last"], d["mother"], *d["date"])
    result = await design(person)
    await query.message.reply_text(result, reply_markup=MAIN_MENU)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text("لغو شد. به منوی اصلی برگشتید.", reply_markup=MAIN_MENU)
    return ConversationHandler.END


def build_app(token: str) -> Application:
    app = Application.builder().token(token).build()
    text = filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^{BTN_CANCEL}$")
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_ZIKR}$"), zikr_start)],
        states={
            FIRST: [MessageHandler(text, got_first)],
            LAST: [MessageHandler(text, got_last)],
            MOTHER: [MessageHandler(text, got_mother)],
            DATE: [MessageHandler(text, got_date)],
            CONFIRM: [CallbackQueryHandler(on_confirm, pattern=r"^zikr:")],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex(f"^{BTN_CANCEL}$"), cancel),
        ],
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    return app


def main() -> None:
    build_app(os.environ["TELEGRAM_BOT_TOKEN"]).run_polling()


if __name__ == "__main__":
    main()
