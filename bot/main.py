"""ربات تلگرامی «مینی اپ علم اعداد».

اجرا روی کامپیوتر:  python -m bot.main
اجرای ۲۴ ساعته روی PythonAnywhere: فایل bot/web.py
توکن از متغیر TELEGRAM_BOT_TOKEN یا فایل token.txt کنار پروژه خوانده می‌شود.

هر دکمهٔ منو یک Flow است: فهرست فیلدها + تابع محاسبه. برای دکمهٔ جدید
کافی است یک Flow به FLOWS اضافه شود.
"""

import logging
import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)
from telegram.warnings import PTBUserWarning

from .abjad import abjad, to_ascii_digits, unknown_letters
from .card import render
from .pin import PinInput, design_pin, to_gregorian
from .zikr import Person, design, zikr_names

warnings.filterwarnings("ignore", category=PTBUserWarning)
logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO)

VERSION = "۳"
ROOT = Path(__file__).resolve().parent.parent
BTN_CANCEL = "❌ انصراف"
CONFIRM = 100
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
DATE_HELP = (
    "به شکل سال/ماه/روز شمسی وارد کنید.\n"
    "مثال: ۱۳۷۰/۰۵/۱۲\n"
    "اگر تاریخ واقعی تولد با شناسنامه فرق دارد، تاریخ واقعی را بنویسید."
)


# ───────────────────────── فیلدها و اعتبارسنجی ─────────────────────────


@dataclass
class Field:
    key: str
    label: str  # با ایموجی، برای خلاصه و دکمهٔ ویرایش
    prompt: str
    kind: str = "name"  # name | fullname | date
    optional: bool = False


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
    if year < 1700 and month > 6 and day > 30:  # ماه‌های دوم سال شمسی ۳۰ روزه‌اند
        return None
    return day, month, year


def _bad_name(text: str) -> bool:
    return not text or abjad(text) == 0 or bool(unknown_letters(text))


def validate(field: Field, text: str):
    """مقدار معتبر یا (None, پیام خطا)."""
    text = text.strip()
    if field.kind == "date":
        date = parse_date(text)
        return (date, None) if date else (None, "⚠️ تاریخ معتبر نیست. لطفاً مثل ۱۳۷۰/۰۵/۱۲ وارد کنید:")
    if _bad_name(text):
        return None, "⚠️ لطفاً فقط با حروف فارسی بنویسید:"
    text = " ".join(text.split())
    if field.kind == "fullname" and len(text.split()) < 2:
        return None, "⚠️ لطفاً نام و نام خانوادگی را با هم بنویسید (مثلاً: علی صادقی):"
    return text, None


def show(field: Field, value) -> str:
    if field.kind == "date":
        day, month, year = value
        text = f"{year}/{month:02d}/{day:02d}"
        if year < 1700:
            gy, gm, gd = to_gregorian(day, month, year)
            text += f"  (میلادی: {gy}/{gm:02d}/{gd:02d})"
        return text
    return value or "—"


# ───────────────────────── محاسبه‌ها ─────────────────────────

GREETING = "با سلام ممنون از اینکه صبوری کردید و منتظر موندید. خدمت شما:"


def compute_zikr(d: dict, user_id: int) -> tuple[bytes, str]:
    person = Person(d["first"], d["last"], d["mother"], *d["date"])
    names = zikr_names(person)
    subs = ("بر اساس نام و نام خانوادگی", "بر اساس نام، نام خانوادگی و نام مادر", "بر اساس تاریخ تولد")
    items = [(lbl, f"یا {n}", sub) for lbl, n, sub in zip(("ذکر اول", "ذکر دوم", "ذکر سوم"), names, subs)]
    return render("ذکرهای شخصی شما", person.full_name, items), design(person, names)


def compute_pin(d: dict, user_id: int) -> tuple[bytes, str] | None:
    p = PinInput(d["full"], d.get("called") or "", *d["date"], d["father"], d["mother"])
    result = design_pin(p, user_id)
    if not result:
        return None
    pin, karma = result
    caption = (
        f"{GREETING}\n\n"
        f"نام و نام خانوادگی: {p.full_name}\n"
        f"🔐 رمز بانکی ۴ رقمی: {pin}\n"
        f"♾ کد کارماسوزی ۷ رقمی: {karma}\n\n"
        "🔒 این رمز فقط برای شما ساخته شده است؛ آن را برای کسی نفرستید."
    )
    items = [
        ("رمز بانکی ۴ رقمی", " ".join(pin), "پول راحت، زیاد و ماندگار"),
        ("کد کارماسوزی ۷ رقمی", " ".join(karma), "سبک‌سازی مسیر پول"),
    ]
    return render("رمزهای مالی شما", p.full_name, items), caption


@dataclass
class Flow:
    key: str
    button: str
    intro: str
    fields: list[Field]
    compute: Callable[[dict, int], tuple[bytes, str] | None]


FLOWS = [
    Flow(
        "zikr",
        "✨ طراحی ذکر شخصی",
        "✨ طراحی ذکر شخصی",
        [
            Field("first", "👤 نام", "لطفاً «نام» خود را مطابق شناسنامه و به فارسی وارد کنید:"),
            Field("last", "👥 نام خانوادگی", "«نام خانوادگی» خود را وارد کنید:"),
            Field("mother", "🤱 نام مادر", "«نام مادر» را مطابق شناسنامه وارد کنید:"),
            Field("date", "📅 تاریخ تولد", "«تاریخ تولد» را " + DATE_HELP, kind="date"),
        ],
        compute_zikr,
    ),
    Flow(
        "pin",
        "🔐 محاسبه رمز عابر بانکی",
        "🔐 محاسبه رمز عابر بانکی و کد کارماسوزی",
        [
            Field(
                "full",
                "👤 نام و نام خانوادگی",
                "«نام و نام خانوادگی» را دقیقاً مطابق شناسنامه (با پیشوند و پسوند) وارد کنید:",
                kind="fullname",
            ),
            Field(
                "called",
                "🗣 اسم صدا زده‌شده",
                "اسمی که شما را با آن صدا می‌زنند چیست؟\nاگر همان اسم شناسنامه است، «رد شدن» را بزنید.",
                optional=True,
            ),
            Field("date", "📅 تاریخ تولد", "«تاریخ تولد» را " + DATE_HELP, kind="date"),
            Field("father", "👨 نام پدر", "«نام پدر» را وارد کنید:"),
            Field("mother", "🤱 نام مادر", "«نام مادر» را وارد کنید:"),
        ],
        compute_pin,
    ),
]

MENU_BUTTONS = [f.button for f in FLOWS]
# هر لیست یک ردیف منو است
MAIN_MENU = ReplyKeyboardMarkup([[b] for b in MENU_BUTTONS], resize_keyboard=True)
CANCEL_KB = ReplyKeyboardMarkup([[BTN_CANCEL]], resize_keyboard=True)


# ───────────────────────── گفت‌وگو ─────────────────────────


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.message.reply_text(
        "🌙 به «مینی اپ علم اعداد» خوش آمدید\n\n"
        "✨ طراحی ذکر شخصی: سه ذکر مخصوص شما بر اساس ابجد\n"
        "🔐 رمز عابر بانکی: رمز ۴ رقمی و کد کارماسوزی ۷ رقمی\n\n"
        f"👇 یکی از گزینه‌های منو را انتخاب کنید.\n\nنسخه {VERSION}",
        reply_markup=MAIN_MENU,
    )


def _summary(flow: Flow, d: dict, footer: str = "اگر درست است «ارسال» را بزنید.") -> str:
    lines = [f"{f.label}: {show(f, d.get(f.key))}" for f in flow.fields]
    return "📋 لطفاً اطلاعات را بررسی کنید:\n\n" + "\n".join(lines) + f"\n\n{footer}"


def _confirm_kb(flow: Flow) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ ارسال و محاسبه", callback_data=f"{flow.key}:send")],
            [
                InlineKeyboardButton("✏️ ویرایش", callback_data=f"{flow.key}:edit"),
                InlineKeyboardButton("❌ انصراف", callback_data=f"{flow.key}:cancel"),
            ],
        ]
    )


def _edit_kb(flow: Flow) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(f.label, callback_data=f"{flow.key}:e:{i}") for i, f in enumerate(flow.fields)]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("↩️ بازگشت", callback_data=f"{flow.key}:back")])
    return InlineKeyboardMarkup(rows)


def _skip_kb(flow: Flow) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⏭ رد شدن", callback_data=f"{flow.key}:skip")]])


def make_conversation(flow: Flow, text_filter) -> ConversationHandler:
    n = len(flow.fields)

    async def ask(message, i: int, editing: bool = False) -> int:
        field = flow.fields[i]
        prefix = "✏️ " if editing else f"{i + 1} از {n} | ".translate(FA_DIGITS)
        markup = _skip_kb(flow) if field.optional else None
        await message.reply_text(prefix + field.prompt, reply_markup=markup)
        return i

    async def begin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.clear()
        await update.message.reply_text(flow.intro, reply_markup=CANCEL_KB)
        return await ask(update.message, 0)

    async def advance(message, context, i: int) -> int:
        """بعد از ثبت فیلد i: در ویرایش یا آخر کار خلاصه، وگرنه فیلد بعدی."""
        if context.user_data.pop("editing", False) or i + 1 == n:
            await message.reply_text(_summary(flow, context.user_data), reply_markup=_confirm_kb(flow))
            return CONFIRM
        return await ask(message, i + 1)

    def on_text(i: int):
        async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
            value, error = validate(flow.fields[i], update.message.text)
            if error:
                await update.message.reply_text(error)
                return i
            context.user_data[flow.fields[i].key] = value
            return await advance(update.message, context, i)

        return handler

    def on_skip(i: int):
        async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
            query = update.callback_query
            await query.answer()
            await query.edit_message_reply_markup(None)
            context.user_data[flow.fields[i].key] = ""
            return await advance(query.message, context, i)

        return handler

    async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        action = query.data.split(":", 1)[1]
        d = context.user_data

        if action == "edit":
            await query.edit_message_text(
                _summary(flow, d, "✏️ کدام بخش را ویرایش می‌کنید؟"), reply_markup=_edit_kb(flow)
            )
            return CONFIRM
        if action == "back":
            await query.edit_message_text(_summary(flow, d), reply_markup=_confirm_kb(flow))
            return CONFIRM
        if action.startswith("e:"):
            i = int(action[2:])
            d["editing"] = True
            await query.edit_message_text(f"✏️ ویرایش {flow.fields[i].label}")
            return await ask(query.message, i, editing=True)
        if action == "cancel":
            await query.edit_message_reply_markup(None)
            return await cancel(update, context)

        await query.edit_message_text("⏳ در حال محاسبه، لطفاً کمی صبر کنید...")
        result = flow.compute(d, update.effective_user.id)
        if result is None:
            await query.message.reply_text(
                "⚠️ با این اطلاعات عددی که همهٔ شرط‌ها را داشته باشد پیدا نشد.", reply_markup=MAIN_MENU
            )
        else:
            photo, caption = result
            await query.message.reply_photo(photo, caption=caption, reply_markup=MAIN_MENU)
        await query.delete_message()
        context.user_data.clear()
        return ConversationHandler.END

    states = {i: [MessageHandler(text_filter, on_text(i))] for i in range(n)}
    for i, field in enumerate(flow.fields):
        if field.optional:
            states[i].append(CallbackQueryHandler(on_skip(i), pattern=f"^{flow.key}:skip$"))
    states[CONFIRM] = [CallbackQueryHandler(on_button, pattern=f"^{flow.key}:")]

    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(flow.button)}$"), begin)],
        states=states,
        fallbacks=[
            # دکمهٔ دیگری از منو یا /start: این گفت‌وگو بی‌صدا تمام می‌شود
            MessageHandler(filters.Regex("^(" + "|".join(map(re.escape, MENU_BUTTONS)) + ")$"), end_silently),
            CommandHandler("start", end_silently),
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex(f"^{BTN_CANCEL}$"), cancel),
        ],
        name=f"{flow.key}_v3",
        persistent=True,
        per_message=False,
    )


async def end_silently(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text("لغو شد. به منوی اصلی برگشتید.", reply_markup=MAIN_MENU)
    return ConversationHandler.END


def load_token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN") or (ROOT / "token.txt").read_text().strip()


def build_app(token: str, **builder_options) -> Application:
    persistence = PicklePersistence(ROOT / "bot_state.pickle")
    builder = Application.builder().token(token).persistence(persistence)
    for name, value in builder_options.items():
        builder = getattr(builder, name)(value)
    app = builder.build()

    reserved = "^(" + "|".join(map(re.escape, MENU_BUTTONS + [BTN_CANCEL])) + ")$"
    text = filters.TEXT & ~filters.COMMAND & ~filters.Regex(reserved)
    # هر گفت‌وگو در گروه جدا، تا زدن دکمهٔ دیگر منو گفت‌وگوی قبلی را ببندد و بعدی را شروع کند
    app.add_handler(CommandHandler("start", start), group=0)
    for g, flow in enumerate(FLOWS, start=1):
        app.add_handler(make_conversation(flow, text), group=g)
    return app


def main() -> None:
    build_app(load_token()).run_polling()


if __name__ == "__main__":
    main()
