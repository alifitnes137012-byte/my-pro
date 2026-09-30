"""طراحی ذکر شخصی: برای هر عدد نزدیک‌ترین اسم الهیِ تکراری‌نشده انتخاب می‌شود."""

from dataclasses import dataclass

from .abjad import abjad, date_number
from .asma import ASMA

LABELS = ("ذکر اول", "ذکر دوم", "ذکر سوم")


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


def pick_nearest(targets: tuple[int, ...]) -> list[str]:
    """برای هر عدد نزدیک‌ترین اسمی که قبلاً انتخاب نشده."""
    used: list[str] = []
    for t in targets:
        for name, _ in sorted(ASMA, key=lambda a: (abs(a[1] - t), a[1])):
            if name not in used:
                used.append(name)
                break
    return used


def zikr_names(p: Person) -> list[str]:
    return pick_nearest(numbers(p))


def design(p: Person, names: list[str] | None = None) -> str:
    names = names or zikr_names(p)
    body = "\n".join(f"{label}: یا {n}" for label, n in zip(LABELS, names))
    return (
        "با سلام ممنون از اینکه صبوری کردید و منتظر موندید. خدمت شما:\n\n"
        f"نام و نام خانوادگی: {p.full_name}\n{body}"
    )
