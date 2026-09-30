"""محاسبهٔ رمز عابر بانک ۴ رقمی و کد کارماسوزی ۷ رقمی.

روش (قطعی و در کد):
۱. اعداد هویتی فرد با سه سیستم محاسبه می‌شوند:
   - فیثاغورثی و کلدانی: روی معادل لاتین حروف (جدول TRANSLIT)
   - ابجد: ریشهٔ عددی جمع ابجد کبیر
   روی اسم شناسنامه‌ای کامل، اسم صدا زده‌شده (اگر داده شده)، عدد مسیر زندگی
   (تاریخ تولد میلادی) و روز تولد.
۲. عدد فرمانده: اول ۳ و ۵ بررسی می‌شوند. عددی که با اعداد هویتی بیشترین سازگاری
   را دارد و با مسیر زندگی و اسم شناسنامه‌ای «دشمن» نیست انتخاب می‌شود.
   اگر هیچ‌کدام سازگار نبود: ۱، ۹، ۲ یا ۷. عددهای ۴، ۶ و ۸ هرگز فرمانده نمی‌شوند.
۳. رقم‌های مجاز: رقم‌هایی که با فرمانده و مسیر زندگی دشمن نیستند. ۸ فقط وقتی
   مجاز است که با هیچ عدد اسم شناسنامه‌ای هم دشمن نباشد. ۴ و ۶ فقط یک بار و
   هرگز در جایگاه اول می‌آیند.
۴. رمز ۴ رقمی: با فرمانده شروع می‌شود و فرمانده فقط یک بار در آن است.
   رمزهای الگودار، پشت‌سرهم و تاریخ‌تولدی حذف می‌شوند.
۵. کد کارماسوزی ۷ رقمی: درس‌های کارمایی (رقم‌های غایب در اسم کامل)، عدد نام پدر،
   عدد نام مادر و مسیر زندگی در آن گنجانده می‌شوند، البته اگر مجاز باشند.
   ریشهٔ عددی کد ۹ (رهایی) است؛ اگر با رقم‌های مجاز ممکن نباشد، ریشهٔ آن
   همان عدد فرمانده می‌شود. دو رقم یکسان کنار هم نمی‌آیند.
۶. از بین همهٔ ترکیب‌های معتبر، یکی با یک کلید مخفی و شناسهٔ تلگرام کاربر انتخاب
   می‌شود. پس خروجی برای هر نفر شخصی است و کسی که اطلاعات شما را دارد نمی‌تواند
   از بات دیگری یا حساب تلگرام دیگری همان رمز را بگیرد.

جدول ENEMIES (دشمنی اعداد بر اساس دوستی و دشمنی سیارات کلدانی) قابل تغییر است.
"""

import hashlib
import hmac
import itertools
import os
import random
import secrets
from dataclasses import dataclass
from pathlib import Path

from .abjad import ABJAD, clean

ROOT = Path(__file__).resolve().parent.parent

TRANSLIT = {
    "ا": "A", "آ": "A", "أ": "A", "إ": "E", "ء": "", "ئ": "E", "ؤ": "O",
    "ب": "B", "پ": "P", "ت": "T", "ث": "S", "ج": "J", "چ": "CH", "ح": "H",
    "خ": "KH", "د": "D", "ذ": "Z", "ر": "R", "ز": "Z", "ژ": "ZH", "س": "S",
    "ش": "SH", "ص": "S", "ض": "Z", "ط": "T", "ظ": "Z", "ع": "A", "غ": "GH",
    "ف": "F", "ق": "GH", "ک": "K", "ك": "K", "گ": "G", "ل": "L", "م": "M",
    "ن": "N", "و": "V", "ه": "H", "ة": "H", "ۀ": "H", "ی": "Y", "ي": "Y", "ى": "Y",
}

PYTHAGOREAN = {c: (i % 9) + 1 for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
CHALDEAN = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", [1, 2, 3, 4, 5, 8, 3, 5, 1, 1, 2, 3, 4, 5, 7, 8, 1, 2, 3, 4, 6, 6, 6, 5, 1, 7]))

# جفت‌عددهای ناسازگار (دوطرفه)
ENEMIES = {frozenset(p) for p in [(1, 6), (1, 8), (2, 8), (3, 6), (2, 4), (4, 9), (5, 9), (8, 9)]}
COMMANDERS = (3, 5)
FALLBACK_COMMANDERS = (1, 9, 2, 7)
STABLE = {4, 6}
HEAVY = {8}


def enemy(a: int, b: int) -> bool:
    return frozenset((a, b)) in ENEMIES


def reduce(n: int) -> int:
    return 0 if n == 0 else 1 + (n - 1) % 9


def latin(name: str) -> str:
    return "".join(TRANSLIT.get(ch, "") for ch in clean(name))


def pythagorean(name: str) -> int:
    return reduce(sum(PYTHAGOREAN[c] for c in latin(name)))


def chaldean(name: str) -> int:
    return reduce(sum(CHALDEAN[c] for c in latin(name)))


def abjad_root(name: str) -> int:
    return reduce(sum(ABJAD.get(ch, 0) for ch in clean(name)))


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd
    days += (jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    months = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gd > months[gm]:
        gd -= months[gm]
        gm += 1
    return gy, gm + 1, gd


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        return jy, 1 + days // 31, 1 + days % 31
    return jy, 7 + (days - 186) // 30, 1 + (days - 186) % 30


def to_gregorian(day: int, month: int, year: int) -> tuple[int, int, int]:
    """(روز، ماه، سال) → (سال، ماه، روز) میلادی. سال‌های کمتر از ۱۷۰۰ شمسی فرض می‌شوند."""
    return jalali_to_gregorian(year, month, day) if year < 1700 else (year, month, day)


@dataclass
class PinInput:
    full_name: str
    called_name: str  # ممکن است خالی باشد
    day: int
    month: int
    year: int
    father_name: str
    mother_name: str


def _secret() -> bytes:
    if os.environ.get("NUMEROLOGY_SECRET"):
        return os.environ["NUMEROLOGY_SECRET"].encode()
    path = ROOT / "secret.key"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip().encode()


def _rng(p: PinInput, user_id: int) -> random.Random:
    msg = "|".join(map(str, (user_id, p.full_name, p.called_name, p.day, p.month, p.year, p.father_name, p.mother_name)))
    return random.Random(hmac.new(_secret(), msg.encode(), hashlib.sha256).digest())


def _no_pattern(code: str, banned: set[str]) -> bool:
    d = [int(c) for c in code]
    steps = {b - a for a, b in zip(d, d[1:])}
    return (
        max(code.count(c) for c in code) <= 2
        and all(a != b for a, b in zip(code, code[1:]))
        and steps not in ({1}, {-1}, {0})
        and code not in banned
    )


def design_pin(p: PinInput, user_id: int) -> tuple[str, str] | None:
    gy, gm, gd = to_gregorian(p.day, p.month, p.year)
    life_path = reduce(reduce(gd) + reduce(gm) + reduce(gy))
    legal = [pythagorean(p.full_name), chaldean(p.full_name), abjad_root(p.full_name)]
    called = [pythagorean(p.called_name), chaldean(p.called_name)] if latin(p.called_name) else []
    identity = legal + called + [life_path, reduce(gd)]

    def ok_commander(c: int) -> bool:
        return not enemy(c, life_path) and not any(enemy(c, n) for n in legal)

    def score(c: int) -> int:
        return sum(not enemy(c, n) for n in identity)

    commander = next(
        (max(pool, key=score) for pool in (
            [c for c in COMMANDERS if ok_commander(c)],
            [c for c in FALLBACK_COMMANDERS if ok_commander(c)],
        ) if pool),
        None,
    )
    if commander is None:
        return None

    allowed = [
        d for d in range(1, 10)
        if not enemy(d, commander) and not enemy(d, life_path)
        and (d not in HEAVY or not any(enemy(d, n) for n in legal))
    ]
    rng = _rng(p, user_id)

    # تاریخ تولد نباید در رمز باشد
    banned = {f"{y:04d}"[-4:] for y in (p.year, gy)}
    for d, m in ((p.day, p.month), (gd, gm)):
        banned |= {f"{d:02d}{m:02d}", f"{m:02d}{d:02d}"}

    pins = []
    for rest in itertools.product([d for d in allowed if d != commander], repeat=3):
        code = f"{commander}{''.join(map(str, rest))}"
        n_stable = sum(int(c) in STABLE for c in code)
        if n_stable <= 1 and _no_pattern(code, banned):
            pins.append(code)
    if not pins:
        return None
    pin = rng.choice(sorted(pins))

    # کد کارماسوزی
    present = {PYTHAGOREAN[c] for c in latin(p.full_name)}
    lessons = [d for d in range(1, 10) if d not in present and d in allowed]
    wanted = lessons[:3] + [pythagorean(p.father_name), abjad_root(p.mother_name), life_path]
    required = list(dict.fromkeys(d for d in wanted if d in allowed))[:5]
    for root in (9, commander, None):
        for _ in range(5000):
            digits = required + [rng.choice(allowed) for _ in range(7 - len(required))]
            rng.shuffle(digits)
            code = "".join(map(str, digits))
            if (
                (root is None or reduce(sum(digits)) == root)
                and sum(d in STABLE for d in digits) <= 2
                and _no_pattern(code, banned)
                and pin not in code
            ):
                return pin, code
    return None
