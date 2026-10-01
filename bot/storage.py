"""ذخیرهٔ اطلاعات تماس در یک فایل SQLite (data.sqlite3 کنار پروژه).

فقط «نام و نام خانوادگی» و «شماره همراه» ذخیره می‌شود؛ برای اطلاع‌رسانی رویدادها.
شماره‌ها فقط از دکمهٔ «ارسال شمارهٔ من» تلگرام می‌آیند و جدا نگه داشته می‌شوند
تا مینی اپ هم بتواند از شمارهٔ تأییدشدهٔ هر کاربر استفاده کند.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data.sqlite3"
TEHRAN = timezone(timedelta(hours=3, minutes=30))


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB, timeout=10)
    con.execute(
        """CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY,
            created TEXT NOT NULL,   -- زمان تهران، ISO
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL
        )"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS verified_phones (
            user_id INTEGER PRIMARY KEY,
            phone TEXT NOT NULL
        )"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS challenge_users (
            user_id INTEGER PRIMARY KEY,
            joined TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL
        )"""
    )
    # هر روز چالش فقط یک بار؛ نتیجه نگه داشته می‌شود تا کاربر دوباره ببیند و روزهای بعد از آن استفاده کنند
    con.execute(
        """CREATE TABLE IF NOT EXISTS challenge_days (
            user_id INTEGER NOT NULL,
            day INTEGER NOT NULL,
            done TEXT NOT NULL,      -- زمان تهران، ISO
            result TEXT NOT NULL,    -- JSON
            PRIMARY KEY (user_id, day)
        )"""
    )
    return con


def save_record(full_name: str, phone: str) -> None:
    with _connect() as con:
        con.execute(
            "INSERT INTO contacts (created, full_name, phone) VALUES (?, ?, ?)",
            (datetime.now(TEHRAN).isoformat(timespec="seconds"), full_name, phone),
        )


def records_for_day(day: str) -> list[dict]:
    """day به شکل YYYY-MM-DD (میلادی، به وقت تهران). هر شماره فقط یک بار (آخرین نام ثبت‌شده)."""
    with _connect() as con:
        rows = con.execute(
            "SELECT full_name, phone FROM contacts WHERE created LIKE ? ORDER BY id", (f"{day}%",)
        ).fetchall()
    unique = {phone: name for name, phone in rows}
    return [{"full": name, "phone": phone} for phone, name in unique.items()]


def save_phone(user_id: int, phone: str) -> None:
    with _connect() as con:
        con.execute("INSERT OR REPLACE INTO verified_phones (user_id, phone) VALUES (?, ?)", (user_id, phone))


def get_phone(user_id: int) -> str | None:
    with _connect() as con:
        row = con.execute("SELECT phone FROM verified_phones WHERE user_id = ?", (user_id,)).fetchone()
    return row[0] if row else None


# ───────────────────────── چالش ۱۰ روزه ─────────────────────────


def challenge_register(user_id: int, full_name: str, phone: str) -> None:
    with _connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO challenge_users (user_id, joined, full_name, phone) VALUES (?, ?, ?, ?)",
            (user_id, datetime.now(TEHRAN).isoformat(timespec="seconds"), full_name, phone),
        )


def challenge_user(user_id: int) -> dict | None:
    with _connect() as con:
        row = con.execute("SELECT full_name, phone FROM challenge_users WHERE user_id = ?", (user_id,)).fetchone()
    return {"full": row[0], "phone": row[1]} if row else None


def challenge_days(user_id: int) -> dict[int, dict]:
    """{روز: {"done": datetime, "result": dict}}"""
    with _connect() as con:
        rows = con.execute("SELECT day, done, result FROM challenge_days WHERE user_id = ?", (user_id,)).fetchall()
    return {day: {"done": datetime.fromisoformat(done), "result": json.loads(result)} for day, done, result in rows}


def challenge_complete(user_id: int, day: int, result: dict) -> bool:
    """False اگر این روز قبلاً ثبت شده باشد (مثلاً دو بار زدن دکمه)."""
    with _connect() as con:
        cur = con.execute(
            "INSERT OR IGNORE INTO challenge_days (user_id, day, done, result) VALUES (?, ?, ?, ?)",
            (user_id, day, datetime.now(TEHRAN).isoformat(timespec="seconds"), json.dumps(result, ensure_ascii=False)),
        )
    return cur.rowcount == 1
