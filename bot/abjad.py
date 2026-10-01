"""محاسبهٔ ابجد کبیر برای نام‌های فارسی و عربی."""

import re

ABJAD = {
    "ا": 1, "آ": 1, "أ": 1, "إ": 1, "ٱ": 1, "ء": 1,
    "ب": 2, "پ": 2,
    "ج": 3, "چ": 3,
    "د": 4,
    "ه": 5, "ة": 5, "ۀ": 5,
    "و": 6, "ؤ": 6,
    "ز": 7, "ژ": 7,
    "ح": 8,
    "ط": 9,
    "ی": 10, "ي": 10, "ى": 10, "ئ": 10,
    "ک": 20, "ك": 20, "گ": 20,
    "ل": 30,
    "م": 40,
    "ن": 50,
    "س": 60,
    "ع": 70,
    "ف": 80,
    "ص": 90,
    "ق": 100,
    "ر": 200,
    "ش": 300,
    "ت": 400,
    "ث": 500,
    "خ": 600,
    "ذ": 700,
    "ض": 800,
    "ظ": 900,
    "غ": 1000,
}

# اعراب، تشدید، تنوین، سکون، الف مقصوره‌ی کوچک و کشیده
_MARKS = re.compile("[ً-ٰٟـ]")

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def clean(text: str) -> str:
    return _MARKS.sub("", text)


def abjad(text: str) -> int:
    """جمع ابجد کبیر همهٔ حروف متن؛ فاصله و علائم نادیده گرفته می‌شوند."""
    return sum(ABJAD.get(ch, 0) for ch in clean(text))


def unknown_letters(text: str) -> set[str]:
    """حروفی که ارزش ابجد ندارند (مثلاً حروف لاتین) تا بشود به کاربر هشدار داد."""
    ignored = set(" ‌‍-_.،,")
    return {ch for ch in clean(text) if ch not in ABJAD and ch not in ignored}


def to_ascii_digits(text: str) -> str:
    return text.translate(_DIGITS)


def date_number(day: int, month: int, year: int) -> int:
    """جمع ارقام روز، ماه و سال (همان تقویمی که کاربر داده، بدون تبدیل)."""
    return sum(int(d) for d in f"{day}{month}{year}")
