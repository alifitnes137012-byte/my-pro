"""ربات تلگرامی «مینی اپ علم اعداد».

اجرا روی کامپیوتر:  python -m bot.main
اجرای ۲۴ ساعته روی PythonAnywhere: فایل bot/web.py
توکن از متغیر TELEGRAM_BOT_TOKEN یا فایل token.txt کنار پروژه خوانده می‌شود.
"""

import logging
import os
import re
import warnings
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.warnings import PTBUserWarning
from telegram.ext import (
    Application,
    PicklePersistence,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .abjad import abjad, to_ascii_digits, unknown_letters
from .card import render
from .zikr import Person, design, zikr_names

warnings.filterwarnings("ignore", category=PTBUserWarning)
logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO)

BTN_ZIKR = "✨ طراحی ذکر شخصی"
BTN_CANCEL = "❌ انصراف"

# دکمه‌های بعدی منو را این‌جا اضافه کنید (هر لیست یک ردیف است).
MAIN_MENU = ReplyKeyboardMarkup([[BTN_ZIKR]], resize_keyboard=True)
CANCEL_KB = ReplyKeyboardMarkup([[BTN_CANCEL]], resize_keyboard=True)

ROOT = Path(__file__).resolve().parent.parent
FIRST, LAST, MOTHER, DATE, CONFIRM = range(5)

# فیلد ← (وضعیت، عنوان دکمه، پیام پرسش)
FIELDS = {
    "first": (FIRST, "👤 نام", "۱ از ۴ | لطفاً «نام» خود را مطابق شناسنامه و به فارسی وارد کنید:"),
    "last": (LAST, "👥 نام خانوادگی", "۲ از ۴ | «نام خانوادگی» خود را وارد کنید:"),
    "mother": (MOTHER, "🤱 نام مادر", "۳ از ۴ | «نام مادر» را مطابق شناسنامه وارد کنید:"),
    "date": (
        DATE,
        "📅 تاریخ تولد",
        "۴ از ۴ | «تاریخ تولد» را به شکل سال/ماه/روز وارد کنید.\n"
        "مثال: ۱۳۷۰/۰۵/۱۲\n"
        "اگر تاریخ واقعی تولد با شناسنامه فرق دارد، تاریخ واقعی را بنویسید.",
    ),
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "🌙 به «مینی اپ علم اعداد» خوش آمدید\n\n"
        "✨ با «طراحی ذکر شخصی» سه ذکر مخصوص شما بر اساس ابجد نام، نام مادر و تاریخ تولد "
        "محاسبه می‌شود.\n\n"
        "👇 یکی از گزینه‌های منو را انتخاب کنید.",
        reply_markup=MAIN_MENU,
    )
    return ConversationHandler.END


def _bad_name(text: str) -> bool:
    return not text or abjad(text) == 0 or bool(unknown_letters(text))


async def zikr_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(FIELDS["first"][2], reply_markup=CANCEL_KB)
    return FIRST


async def _after(update: Update, context: ContextTypes.DEFAULT_TYPE, next_field: str | None) -> int:
    """بعد از ثبت یک فیلد: در حالت ویرایش یا انتهای کار خلاصه را نشان بده، وگرنه فیلد بعدی."""
    if context.user_data.pop("editing", False) or next_field is None:
        await update.message.reply_text(_summary(context.user_data), reply_markup=CONFIRM_KB)
        return CONFIRM
    state, _, prompt = FIELDS[next_field]
    await update.message.reply_text(prompt)
    return state


async def _got_name(update, context, key: str, what: str, state: int, next_field: str | None) -> int:
    text = update.message.text.strip()
    if _bad_name(text):
        await update.message.reply_text(f"⚠️ لطفاً {what} را فقط با حروف فارسی بنویسید:")
        return state
    context.user_data[key] = text
    return await _after(update, context, next_field)


async def got_first(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _got_name(update, context, "first", "نام", FIRST, "last")


async def got_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _got_name(update, context, "last", "نام خانوادگی", LAST, "mother")


async def got_mother(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _got_name(update, context, "mother", "نام مادر", MOTHER, "date")


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
        "📋 لطفاً اطلاعات را بررسی کنید:\n\n"
        f"👤 نام: {d['first']}\n"
        f"👥 نام خانوادگی: {d['last']}\n"
        f"🤱 نام مادر: {d['mother']}\n"
        f"📅 تاریخ تولد: {year}/{month:02d}/{day:02d}\n\n"
        "اگر درست است «ارسال» را بزنید."
    )


CONFIRM_KB = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("✅ ارسال و محاسبه", callback_data="zikr:send")],
        [
            InlineKeyboardButton("✏️ ویرایش", callback_data="zikr:edit"),
            InlineKeyboardButton("❌ انصراف", callback_data="zikr:cancel"),
        ],
    ]
)

EDIT_KB = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(FIELDS["first"][1], callback_data="edit:first"),
            InlineKeyboardButton(FIELDS["last"][1], callback_data="edit:last"),
        ],
        [
            InlineKeyboardButton(FIELDS["mother"][1], callback_data="edit:mother"),
            InlineKeyboardButton(FIELDS["date"][1], callback_data="edit:date"),
        ],
        [InlineKeyboardButton("↩️ بازگشت", callback_data="edit:back")],
    ]
)


async def got_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    date = parse_date(update.message.text)
    if not date:
        await update.message.reply_text("⚠️ تاریخ معتبر نیست. لطفاً مثل ۱۳۷۰/۰۵/۱۲ وارد کنید:")
        return DATE
    context.user_data["date"] = date
    return await _after(update, context, None)


async def on_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    field = query.data.split(":", 1)[1]
    if field == "back":
        await query.edit_message_text(_summary(context.user_data), reply_markup=CONFIRM_KB)
        return CONFIRM
    state, label, prompt = FIELDS[field]
    context.user_data["editing"] = True
    await query.edit_message_text(f"✏️ ویرایش {label}")
    # بدون شمارهٔ مرحله («۱ از ۴ | ...»)
    await query.message.reply_text(prompt.split(" | ", 1)[-1])
    return state


async def on_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]

    if action == "edit":
        await query.edit_message_text(
            _summary(context.user_data).rsplit("\n\n", 1)[0] + "\n\n✏️ کدام بخش را ویرایش می‌کنید؟",
            reply_markup=EDIT_KB,
        )
        return CONFIRM
    if action == "cancel":
        await query.edit_message_reply_markup(None)
        return await cancel(update, context)

    d = context.user_data
    await query.edit_message_text("⏳ در حال محاسبه، لطفاً کمی صبر کنید...")
    person = Person(d["first"], d["last"], d["mother"], *d["date"])
    names = zikr_names(person)
    await query.message.reply_photo(
        render(person.full_name, names), caption=design(person, names), reply_markup=MAIN_MENU
    )
    await query.delete_message()
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text("لغو شد. به منوی اصلی برگشتید.", reply_markup=MAIN_MENU)
    return ConversationHandler.END


def load_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or (ROOT / "token.txt").read_text().strip()
    return token


def build_app(token: str, **builder_options) -> Application:
    persistence = PicklePersistence(ROOT / "bot_state.pickle")
    builder = Application.builder().token(token).persistence(persistence)
    for name, value in builder_options.items():
        builder = getattr(builder, name)(value)
    app = builder.build()
    text = filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^{BTN_CANCEL}$")
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BTN_ZIKR}$"), zikr_start)],
        states={
            FIRST: [MessageHandler(text, got_first)],
            LAST: [MessageHandler(text, got_last)],
            MOTHER: [MessageHandler(text, got_mother)],
            DATE: [MessageHandler(text, got_date)],
            CONFIRM: [
                CallbackQueryHandler(on_confirm, pattern=r"^zikr:"),
                CallbackQueryHandler(on_edit, pattern=r"^edit:"),
            ],
        },
        name="zikr",
        persistent=True,
        per_message=False,
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
    build_app(load_token()).run_polling()


if __name__ == "__main__":
    main()
