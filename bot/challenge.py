"""چالش ۱۰ روزهٔ جذب ثروت.

قانون‌ها:
- اول ثبت‌نام (نام و نام خانوادگی + شمارهٔ تأییدشده از تلگرام).
- همهٔ روزها از اول دیده می‌شوند (معرفی و اینکه هر روز چه چیزی می‌گیرد)، ولی فقط یکی‌یکی باز می‌شوند.
- روز n فقط وقتی باز می‌شود که روز n-1 انجام شده باشد و از انجامش WAIT_HOURS ساعت گذشته باشد.
  اگر روز قبل انجام نشده باشد، روز بعد قفل می‌ماند؛ هر چقدر هم زمان گذشته باشد.
- هر روز فقط یک بار اجرا می‌شود و نتیجه‌اش ذخیره می‌ماند تا کاربر دوباره ببیند.

⚠️ محاسبه‌های این فایل فعلاً «نمونهٔ نمایشی» هستند (PLACEHOLDER = True) تا ظاهر و جریان
چالش دیده شود. روش محاسبهٔ نهایی هر روز بعداً جایگزین تابع‌های compute_day* می‌شود.
"""

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from .main import Field, parse_date, validate
from .pin import chaldean, reduce, to_gregorian
from .storage import TEHRAN, challenge_days

PLACEHOLDER = True
WAIT_HOURS = float(os.environ.get("CHALLENGE_WAIT_HOURS", "24"))

# لینک ویدیوها و سفارش گنج‌نامه؛ وقتی آماده شد این‌جا بگذارید
VIDEO_AWAKENING = ""  # روز نهم: ویدیوی بیدارسازی
VIDEO_PRESENT = ""  # روز دهم: ویدیوی پرزنت و فروش
ORDER_URL = ""  # روز دهم: لینک سفارش گنج‌نامه (مثلاً https://t.me/...)

TITLE = "چالش ۱۰ روزه جذب ثروت"
INTRO = (
    "در این ۱۰ روز، قدم‌به‌قدم ارتعاش اسم، تاریخ تولد، زودیاک، عنصر، چاکرا و کارمای تو بررسی می‌شه "
    "و کدهای اختصاصی جذب ثروتت رو می‌گیری. هر روز فقط یک مرحله باز می‌شه؛ "
    "پس هر روز سر بزن تا هیچ قدمی رو از دست ندی 🌙"
)

MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
WISHES = ["ثروت و پول", "سلامتی", "عشق و ازدواج", "شغل و کسب‌وکار", "خانه و ملک", "رهایی از بدهی"]
YES_SOMETIMES_NO = ["بله", "گاهی", "نه"]
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
FREQ = ["همیشه", "گاهی", "به‌ندرت"]


@dataclass
class Question:
    key: str
    label: str
    kind: str  # fullname | name | month | year | date | choice
    hint: str = ""
    options: list[str] = field(default_factory=list)
    prefill: str = ""  # "name": اسم ثبت‌نامی کاربر از قبل نوشته می‌شود


@dataclass
class Day:
    n: int
    icon: str
    title: str
    gets: str  # در دمو: این روز چه چیزی می‌گیری
    needs: str  # در دمو: چه چیزی باید وارد کنی
    questions: list[Question]
    compute: Callable[[dict, dict], dict]
    cta: str


# ───────────────────────── کمکی‌ها ─────────────────────────


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest(), 16)


def _code(length: int, *parts) -> str:
    """کد نمایشی بدون دو رقم یکسان کنار هم و بدون صفر."""
    s, out = _seed(*parts), ""
    while len(out) < length:
        s, d = divmod(s, 9)
        if not out or str(d + 1) != out[-1]:
            out += str(d + 1)
        if s == 0:
            s = _seed(out, *parts)
    return out


def _item(label: str, value, sub: str = "") -> dict:
    return {"label": label, "value": str(value), "sub": sub}


def _score(values: dict, keys: list[str]) -> int:
    """جمع امتیاز جواب‌های چندگزینه‌ای: گزینهٔ اول ۲، دوم ۱، سوم ۰."""
    return sum(2 - int(values[k]) for k in keys)


# ───────────────────────── محاسبهٔ روزها (نمونهٔ نمایشی) ─────────────────────────

WEALTHY = {1, 3, 5, 6, 8}


def compute_day1(v: dict, ctx: dict) -> dict:
    root = chaldean(v["full"])
    good = root in WEALTHY
    return {
        "items": [
            _item("ارتعاش اسم شما", "ثروت‌ساز" if good else "نیازمند تقویت", "بر اساس عدد کلدانی اسم"),
            _item("عدد اسم", root, "ارتعاش پایهٔ نام و نام خانوادگی"),
            _item("کد ثروت شما", _code(6, "d1", ctx["user_id"], v["full"]), "روزی چند بار تکرار کن"),
        ],
        "notes": [
            "ارتعاش اسم تو با انرژی پول هم‌سوئه؛ با کد ثروت این انرژی رو فعال نگه دار."
            if good
            else "ارتعاش اسم تو برای جذب پول نیاز به تقویت داره؛ کد ثروت دقیقاً برای همین ساخته شده."
        ],
    }


LUCK_DAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
LUCK_COLORS = ["طلایی", "سبز زمردی", "آبی آسمانی", "بنفش", "قرمز یاقوتی", "سفید صدفی", "نارنجی", "فیروزه‌ای", "کرم"]


def compute_day2(v: dict, ctx: dict) -> dict:
    m = int(v["month"])
    return {
        "items": [
            _item("روز شانس", LUCK_DAYS[(m * 3) % 7], "کارهای مالی مهم رو این روز انجام بده"),
            _item("عدد شانس", reduce(m * 7 + 2), "در تاریخ‌ها و مبلغ‌ها از این عدد استفاده کن"),
            _item("رنگ شانس", LUCK_COLORS[(m * 5) % 9], "در لباس و کیف پولت از این رنگ استفاده کن"),
        ],
        "notes": [f"متولدین {MONTHS[m - 1]}، این سه نشانه کلید باز شدن درهای فرصت برای شماست."],
    }


# سیارهٔ حاکم هر عدد (سیستم ودایی)
PLANETS = {1: "خورشید", 2: "ماه", 3: "مشتری", 4: "راهو", 5: "عطارد", 6: "زهره", 7: "کتو", 8: "زحل", 9: "مریخ"}


def compute_day3(v: dict, ctx: dict) -> dict:
    day, month, year = v["date"]
    gy, gm, gd = to_gregorian(day, month, year)
    driver = reduce(gd)
    conductor = reduce(sum(int(c) for c in f"{gy}{gm}{gd}"))
    hurt = 8 if _score(v, ["q1", "q2", "q3"]) >= 3 else 4
    planets = [(driver, "سیارهٔ روز تولد"), (conductor, "سیارهٔ مسیر زندگی"), (hurt, "سیارهٔ آسیب‌دیده؛ درمان")]
    return {
        "items": [
            _item(PLANETS[n], _code(5, "d3", ctx["user_id"], n, v["date"]), f"{why} — کد جذب ثروت")
            for n, why in planets
        ],
        "notes": [
            f"سیارهٔ {PLANETS[driver]} بر روز تولدت و سیارهٔ {PLANETS[conductor]} بر مسیر زندگیت حاکمه.",
            f"با توجه به جواب‌هات، سیارهٔ {PLANETS[hurt]} آسیب دیده؛ کدش رو هر روز ۹ بار تکرار کن.",
        ],
    }


ANIMALS = ["موش", "گاو", "ببر", "خرگوش", "اژدها", "مار", "اسب", "بز", "میمون", "خروس", "سگ", "خوک"]
ANIMAL_TRAITS = {
    "موش": "باهوش، زیرک و فرصت‌شناس",
    "گاو": "صبور، پرتلاش و قابل اعتماد",
    "ببر": "شجاع، رهبر و ریسک‌پذیر",
    "خرگوش": "آرام، خوش‌سلیقه و دیپلمات",
    "اژدها": "پرانرژی، جاه‌طلب و خوش‌شانس",
    "مار": "عمیق، باهوش و مرموز",
    "اسب": "آزاد، فعال و پرشور",
    "بز": "مهربان، خلاق و هنرمند",
    "میمون": "باهوش، شوخ و چندکاره",
    "خروس": "دقیق، منظم و صادق",
    "سگ": "وفادار، منصف و مسئولیت‌پذیر",
    "خوک": "سخاوتمند، صبور و خوش‌قلب",
}


def zodiac(jalali_year: int) -> tuple[int, str]:
    """زودیاک چینی. بیشتر سال شمسی (فروردین تا بهمن) در سال چینیِ jy+621 است."""
    gy = jalali_year + 621
    return gy, ANIMALS[(gy - 4) % 12]


def compute_day4(v: dict, ctx: dict) -> dict:
    gy, animal = zodiac(int(v["year"]))
    return {
        "items": [
            _item("سال تولد میلادی", gy, f"معادل سال {v['year']} شمسی"),
            _item("زودیاک سال تولد", animal, ANIMAL_TRAITS[animal]),
        ],
        "notes": [f"متولدین سال {animal} {ANIMAL_TRAITS[animal]} هستند."],
        "zodiac": animal,
    }


def compute_day5(v: dict, ctx: dict) -> dict:
    animal = ctx["results"][4]["zodiac"]
    stars = 3 + _seed("d5", animal) % 3
    return {
        "items": [
            _item("زودیاک شما", animal, "بر اساس محاسبهٔ روز چهارم"),
            _item("امتیاز مالی ۲۰۲۷", f"{stars} از ۵".translate(FA), "سال ۲۰۲۷، سال بز آتش"),
            _item("بهترین فصل درآمد", ["بهار", "تابستان", "پاییز", "زمستان"][_seed("d5s", animal) % 4], "فرصت‌ها رو از دست نده"),
        ],
        "notes": [
            f"سال ۲۰۲۷ برای متولدین سال {animal} سال باز شدن درهای تازهٔ درآمده؛ "
            "به شرطی که مسیر پول رو از قبل آماده کرده باشی."
        ],
    }


ELEMENTS = ["فلز", "فلز", "آب", "آب", "چوب", "چوب", "آتش", "آتش", "خاک", "خاک"]
STONES = {"فلز": "عقیق سفید", "آب": "لاجورد", "چوب": "زمرد", "آتش": "یاقوت سرخ", "خاک": "ببر چشم"}
MONEY_CODES = {"فلز": "7189", "آب": "2579", "چوب": "3581", "آتش": "9157", "خاک": "5289"}


def compute_day6(v: dict, ctx: dict) -> dict:
    gy, _ = zodiac(int(v["year"]))
    element = ELEMENTS[gy % 10]
    return {
        "items": [
            _item("عنصر شانس", element, "عنصر وجودی تو"),
            _item("سنگ شانس", STONES[element], "همراه خودت داشته باش"),
            _item("کد عمومی پول", MONEY_CODES[element], f"کد عنصر {element}"),
        ],
        "notes": ["این کد عمومی همهٔ متولدین این عنصره؛ کدهای اختصاصی خودت در روزهای بعد ساخته می‌شه."],
    }


CHAKRA_KEYS = ["c1", "c2", "c3", "c4", "c5"]


def compute_day7(v: dict, ctx: dict) -> dict:
    score = _score(v, CHAKRA_KEYS)
    blocked = score >= 5
    return {
        "items": [
            _item("وضعیت چاکرای ثروت", "نیاز به پاکسازی" if blocked else "فعال", f"امتیاز تست: {score} از ۱۰"),
            _item(
                "کد پاکسازی چاکرا" if blocked else "کد تقویت چاکرا",
                _code(7, "d7", ctx["user_id"], score),
                "صبح و شب ۲۱ بار",
            ),
        ],
        "notes": [
            "چاکرای ثروتت بسته شده و جلوی جریان پول رو گرفته؛ با کد پاکسازی بازش کن."
            if blocked
            else "چاکرای ثروتت فعاله؛ با کد تقویت، جریان پول رو قوی‌تر کن."
        ],
    }


def compute_day8(v: dict, ctx: dict) -> dict:
    who = ["پدر", "مادر"][int(v["who"])]
    return {
        "items": [
            _item("کد کارماسوزی", _code(7, "d8", ctx["user_id"], v["parent"]), f"بر اساس نام {who}: {v['parent']}"),
        ],
        "notes": ["کارمای مالی که از خانواده به تو رسیده با این کد سبک می‌شه. هر شب قبل از خواب ۷ بار تکرار کن."],
    }


def compute_day9(v: dict, ctx: dict) -> dict:
    wish = WISHES[int(v["w1"])]
    return {
        "items": [_item("خواستهٔ اصلی تو", wish, "بر اساس جواب‌های تست")],
        "notes": [
            "مسترکد، کد مادر خواسته‌هاست: کدی که همهٔ کدهای قبلی تو رو به هم وصل می‌کنه و به سمت یک خواستهٔ مشخص هدایت می‌کنه.",
            "گنج‌نامه، نقشهٔ کامل رسیدن به همون خواسته‌ست: مسترکد اختصاصی، روش استفاده و برنامهٔ روزانه.",
            "اول ویدیوی بیدارسازی رو کامل ببین 👇",
        ],
        "video": {"title": "🎬 ویدیوی بیدارسازی", "url": VIDEO_AWAKENING},
    }


def compute_day10(v: dict, ctx: dict) -> dict:
    wish = WISHES[int(v["wish"])]
    return {
        "items": [_item("گنج‌نامهٔ انتخابی شما", wish, "مجوز گنج‌نامه برای شما صادر شد")],
        "notes": [
            "🎉 تبریک! شما که ۹ مرحلهٔ قبل رو گذروندید، اجازهٔ داشتن گنج‌نامهٔ مربوط به خواسته‌تون براتون صادر شد.",
            "اول ویدیو رو ببینید و بعد با توجه به خواسته‌تون، گنج‌نامهٔ مخصوص خودتون رو سفارش بدید!",
        ],
        "video": {"title": "🎬 ویدیوی معرفی گنج‌نامه", "url": VIDEO_PRESENT},
        "order": {"title": f"🗝 سفارش گنج‌نامهٔ «{wish}»", "url": ORDER_URL},
    }


# ───────────────────────── تعریف روزها ─────────────────────────

DAYS = [
    Day(
        1, "✨", "محاسبهٔ ارتعاش اسم",
        "آیا ارتعاش اسمت ثروت‌سازه؟ + کد شانس و ثروت",
        "اسم و فامیل",
        [Question("full", "نام و نام خانوادگی", "fullname", "به فارسی و مطابق شناسنامه", prefill="name")],
        compute_day1,
        "فردا حتماً آنلاین باش؛ قراره روز شانس، عدد شانس و رنگ شانست بهت گفته بشه.",
    ),
    Day(
        2, "🍀", "روز، عدد و رنگ شانس",
        "روز شانس، عدد شانس و رنگ شانس تو",
        "ماه تولد",
        [Question("month", "ماه تولد (شمسی)", "month")],
        compute_day2,
        "فردا قراره سیارات حاکم بر تاریخ تولدت بررسی بشه و بهت بگم چطور باید سیارات آسیب‌دیده رو درمان کنی.",
    ),
    Day(
        3, "🪐", "سیارات حاکم",
        "سیاره‌های حاکم بر تاریخ تولدت + کد جذب ثروت هر سیاره",
        "تاریخ تولد کامل + ۳ سؤال مالی",
        [
            Question("date", "تاریخ تولد", "date", "تاریخ شمسی"),
            Question("q1", "پول راحت به دستت می‌رسه ولی زود از دستت می‌ره؟", "choice", options=YES_SOMETIMES_NO),
            Question("q2", "در کار و درآمدت احساس می‌کنی حقت رو نمی‌گیری؟", "choice", options=YES_SOMETIMES_NO),
            Question("q3", "بدهی یا قرضی داری که مدت‌هاست تسویه نشده؟", "choice", options=YES_SOMETIMES_NO),
        ],
        compute_day3,
        "فردا قراره زودیاک‌های شما بررسی بشه.",
    ),
    Day(
        4, "🐉", "زودیاک تولد",
        "زودیاک سال تولدت و ویژگی‌هاش",
        "سال تولد شمسی",
        [Question("year", "سال تولد (شمسی)", "year", "به‌صورت خودکار به میلادی تبدیل می‌شه")],
        compute_day4,
        "فردا قراره سرنوشت مالی زودیاک شما در سال ۲۰۲۷ محاسبه بشه.",
    ),
    Day(
        5, "🔮", "تحلیل زودیاک در ۲۰۲۷",
        "تحلیل مالی زودیاک تو در سال ۲۰۲۷",
        "نیازی به ورود اطلاعات نیست؛ از زودیاک روز چهارم استفاده می‌شه",
        [],
        compute_day5,
        "هنوز تحلیل تولدت تموم نشده! اگر واقعاً می‌خوای به خواسته‌های مالیت برسی، فردا حتماً عنصر وجودیت رو به دست بیار.",
    ),
    Day(
        6, "💎", "عنصر و سنگ شانس",
        "عنصر شانس، سنگ شانس و کد عمومی پول عنصرت",
        "سال تولد",
        [Question("year", "سال تولد (شمسی)", "year")],
        compute_day6,
        "کدهای عمومی کافی نیست، باید کدهای اختصاصی خودت رو داشته باشی. اول باید ارتعاش چاکراها و کارماهات بررسی بشه.",
    ),
    Day(
        7, "🌀", "چاکرای ثروت",
        "تحلیل چاکرای ثروت + کد تقویت یا پاکسازی چاکرا",
        "تست چاکرای ثروت",
        [
            Question("c1", "وقتی پول خرج می‌کنی احساس گناه یا نگرانی داری؟", "choice", options=FREQ),
            Question("c2", "احساس می‌کنی لیاقت پول زیاد رو نداری؟", "choice", options=FREQ),
            Question("c3", "درآمدت با تلاشت هم‌خوانی نداره؟", "choice", options=FREQ),
            Question("c4", "از صحبت دربارهٔ پول معذب می‌شی؟", "choice", options=FREQ),
            Question("c5", "پس‌انداز کردن برات سخته؟", "choice", options=FREQ),
        ],
        compute_day7,
        "برای جذب ثروت حتماً باید درمانگری‌ها رو انجام بدی؛ پس حتماً فردا که قراره کد کارماسوزی رو بگیری، حضور داشته باش.",
    ),
    Day(
        8, "♾", "کارماسوزی",
        "کد کارماسوزی اختصاصی تو",
        "اسم پدر یا مادر",
        [
            Question("who", "اسم کدوم رو وارد می‌کنی؟", "choice", options=["پدر", "مادر"]),
            Question("parent", "اسم پدر یا مادر", "name", "مطابق شناسنامه"),
        ],
        compute_day8,
        "تا الان ارتعاش اسم، تاریخ تولد، زودیاک و... رو محاسبه کردیم، ولی هنوز کدهای مادر (مسترکدها) برای جذب "
        "خواسته‌هات رو نداری. فردا باید دقیقاً خواسته‌ات مشخص بشه.",
    ),
    Day(
        9, "🎯", "تست خواسته‌ها",
        "ویدیوی بیدارسازی + آشنایی با مسترکد و گنج‌نامه",
        "تست خواسته‌ها (ثروت، سلامتی، عشق و...)",
        [
            Question("w1", "الان بزرگ‌ترین خواسته‌ات چیه؟", "choice", options=WISHES),
            Question("w2", "چند وقته دنبال این خواسته‌ای؟", "choice", options=["کمتر از یک سال", "۱ تا ۵ سال", "بیشتر از ۵ سال"]),
            Question("w3", "چقدر برای رسیدن بهش آماده‌ای؟", "choice", options=["کاملاً آماده‌ام", "تا حدی", "هنوز مطمئن نیستم"]),
        ],
        compute_day9,
        "🎁 فردا روز ویژه‌ست! گنج‌نامهٔ مخصوص خواسته‌ات معرفی می‌شه و می‌تونی سفارشش بدی. حتماً آنلاین باش.",
    ),
    Day(
        10, "🗝", "پرزنت و گنج‌نامه",
        "ویدیوی معرفی و سفارش گنج‌نامهٔ مخصوص خواسته‌ات",
        "انتخاب خواسته از لیست",
        [Question("wish", "گنج‌نامهٔ کدوم خواسته رو می‌خوای؟", "choice", options=WISHES)],
        compute_day10,
        "",
    ),
]
BY_N = {d.n: d for d in DAYS}


# ───────────────────────── وضعیت و اجرا ─────────────────────────


def check(q: Question, raw) -> tuple[object, str | None]:
    text = str(raw if raw is not None else "").strip()
    if not text:
        return None, "این بخش را پر کنید"
    if q.kind in ("fullname", "name"):
        value, error = validate(Field(q.key, q.label, "", kind=q.kind), text)
        return value, error and error.replace("⚠️ ", "").rstrip(":")
    if q.kind == "date":
        date = parse_date(text)
        return (date, None) if date else (None, "تاریخ معتبر نیست")
    if q.kind == "month":
        return (text, None) if re.fullmatch(r"([1-9]|1[0-2])", text) else (None, "ماه را انتخاب کنید")
    if q.kind == "year":
        return (text, None) if re.fullmatch(r"1[34]\d\d", text) and 1300 <= int(text) <= 1404 else (None, "سال را انتخاب کنید")
    if q.kind == "choice":
        return (text, None) if text.isdigit() and int(text) < len(q.options) else (None, "یک گزینه را انتخاب کنید")
    return None, "نامعتبر"


def status(user_id: int, now: datetime | None = None) -> list[dict]:
    """وضعیت هر روز: done | open | wait (روز قبل انجام شده، هنوز ۲۴ ساعت نگذشته) | locked"""
    now = now or datetime.now(TEHRAN)
    done = challenge_days(user_id)
    out = []
    for d in DAYS:
        info = {"n": d.n, "icon": d.icon, "title": d.title, "gets": d.gets, "needs": d.needs}
        if d.n in done:
            info.update(state="done", result=done[d.n]["result"])
        elif d.n == 1:
            info["state"] = "open"
        elif d.n - 1 in done:
            unlock = done[d.n - 1]["done"] + timedelta(hours=WAIT_HOURS)
            info["state"] = "open" if now >= unlock else "wait"
            info["seconds"] = max(0, int((unlock - now).total_seconds()))
        else:
            info["state"] = "locked"
        if info["state"] == "open":
            info["questions"] = [
                {"key": q.key, "label": q.label, "kind": q.kind, "hint": q.hint, "options": q.options, "prefill": q.prefill}
                for q in d.questions
            ]
        out.append(info)
    return out


def run_day(day: Day, values: dict, user_id: int) -> dict:
    results = {n: x["result"] for n, x in challenge_days(user_id).items()}
    result = day.compute(values, {"user_id": user_id, "results": results})
    result.update(day=day.n, title=f"روز {day.n}: {day.title}".translate(FA), cta=day.cta, demo=PLACEHOLDER)
    return result


def chat_text(result: dict, name: str) -> str:
    """متن نتیجه برای چت بات."""
    lines = [f"🌙 {TITLE}", f"✨ {result['title']}", "", f"👤 {name}", ""]
    lines += [f"▫️ {it['label']}: {it['value']}" for it in result["items"]]
    if result.get("notes"):
        lines += [""] + result["notes"]
    for key in ("video", "order"):
        if result.get(key, {}).get("url"):
            lines += ["", f"{result[key]['title']}: {result[key]['url']}"]
    if result.get("cta"):
        lines += ["", f"📣 {result['cta']}"]
    return "\n".join(lines)
