"""طراحی ذکر شخصی: محاسبهٔ اعداد در کد، انتخاب نهایی (اختیاری) با Claude.

محاسبهٔ ابجد و جمع ارقام تاریخ کاملاً قطعی است و در کد انجام می‌شود، چون
مدل‌های زبانی در جمع حروف خطا می‌کنند. برای هر ذکر چند اسم نزدیک پیدا
می‌شود و Claude فقط از بین همین نامزدها، با توجه به نزدیکی عدد و تناسب
معنا، سه اسم متفاوت انتخاب می‌کند. اگر کلید API تنظیم نشده باشد یا پاسخ
مدل معتبر نباشد، نزدیک‌ترین اسم‌ها به ترتیب انتخاب می‌شوند.
"""

import json
import logging
import os
from dataclasses import dataclass

from .abjad import abjad, date_number
from .asma import ASMA

log = logging.getLogger(__name__)

CANDIDATES = 6
LABELS = ("ذکر اول", "ذکر دوم", "ذکر سوم")
KEYS = ("first", "second", "third")


@dataclass
class Person:
    first_name: str
    last_name: str
    mother_name: str
    day: int
    month: int
    year: int

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


def numbers(p: Person) -> tuple[int, int, int]:
    name = abjad(p.first_name) + abjad(p.last_name)
    return name, name + abjad(p.mother_name), date_number(p.day, p.month, p.year)


def candidates(target: int, k: int = CANDIDATES) -> list[tuple[str, int]]:
    return sorted(ASMA, key=lambda a: (abs(a[1] - target), a[1]))[:k]


def pick_nearest(targets: tuple[int, ...]) -> list[str]:
    """برای هر عدد نزدیک‌ترین اسمی که قبلاً انتخاب نشده."""
    used: list[str] = []
    for t in targets:
        for name, _ in sorted(ASMA, key=lambda a: (abs(a[1] - t), a[1])):
            if name not in used:
                used.append(name)
                break
    return used


SYSTEM_PROMPT = """شما متخصص علم حروف، ابجد کبیر و اسماءالحسنی هستید.
برای یک فرد سه ذکر مستقل انتخاب می‌کنید. اعداد ابجد قبلاً دقیق محاسبه شده‌اند و نباید دوباره محاسبه شوند:
- ذکر اول: عدد ابجد «نام و نام خانوادگی»
- ذکر دوم: عدد ابجد «نام و نام خانوادگی + نام مادر»
- ذکر سوم: جمع ارقام تاریخ تولد
برای هر ذکر فهرستی از اسماءالحسنیِ نزدیک به آن عدد (با عدد ابجدشان) داده می‌شود.
از هر فهرست دقیقاً یک اسم انتخاب کن. معیار اول نزدیکی عدد است و معیار دوم تناسب معنای اسم الهی با آن عدد.
سه اسم انتخابی باید با هم متفاوت باشند؛ اگر نزدیک‌ترین اسم در ذکر دیگری انتخاب شده، اسم مناسب و نزدیک بعدی را بردار.
نیت شخص در انتخاب دخالت ندارد. اسم‌ها را دقیقاً با همان املای فهرست و بدون «یا» برگردان."""

_SCHEMA = {
    "type": "object",
    "properties": {k: {"type": "string"} for k in KEYS},
    "required": list(KEYS),
    "additionalProperties": False,
}


async def pick_with_claude(targets: tuple[int, int, int]) -> list[str] | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        return None

    pools = [candidates(t) for t in targets]
    lines = []
    for label, t, pool in zip(LABELS, targets, pools):
        opts = "، ".join(f"{n} ({v})" for n, v in pool)
        lines.append(f"{label} — عدد {t}: {opts}")

    client = AsyncAnthropic()
    try:
        resp = await client.beta.messages.create(
            model=os.environ.get("CLAUDE_MODEL", "claude-opus-5-5"),
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": "\n".join(lines)}],
            output_config={
                "effort": os.environ.get("CLAUDE_EFFORT", "low"),
                "format": {"type": "json_schema", "schema": _SCHEMA},
            },
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except Exception:
        log.exception("Claude request failed")
        return None

    if resp.stop_reason != "refusal":
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            data = json.loads(text)
            chosen = [data[k].replace("یا ", "", 1).strip() for k in KEYS]
        except (ValueError, KeyError, AttributeError):
            chosen = []
        valid = len(set(chosen)) == 3 and all(
            c in {n for n, _ in pool} for c, pool in zip(chosen, pools)
        )
        if valid:
            return chosen
    log.warning("Claude answer rejected, using nearest names: %s", resp.stop_reason)
    return None


async def design(p: Person) -> str:
    targets = numbers(p)
    names = await pick_with_claude(targets) or pick_nearest(targets)
    body = "\n".join(f"{label}: یا {n}" for label, n in zip(LABELS, names))
    return (
        "با سلام ممنون از اینکه صبوری کردید و منتظر موندید. خدمت شما:\n\n"
        f"نام و نام خانوادگی: {p.full_name}\n{body}"
    )
