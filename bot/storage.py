"""ذخیرهٔ اطلاعات کاربران در یک فایل SQLite (data.sqlite3 کنار پروژه) برای گزارش روزانه."""

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
        """CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY,
            created TEXT NOT NULL,          -- زمان تهران، ISO
            flow TEXT NOT NULL,
            user_id INTEGER,
            username TEXT,
            data TEXT NOT NULL              -- ورودی‌های فرم به صورت JSON
        )"""
    )
    return con


def save_record(flow: str, data: dict, user_id: int | None, username: str | None) -> None:
    clean = {k: v for k, v in data.items() if k != "editing"}
    with _connect() as con:
        con.execute(
            "INSERT INTO records (created, flow, user_id, username, data) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(TEHRAN).isoformat(timespec="seconds"), flow, user_id, username,
             json.dumps(clean, ensure_ascii=False)),
        )


def records_for_day(day: str) -> list[dict]:
    """day به شکل YYYY-MM-DD (میلادی، به وقت تهران)."""
    with _connect() as con:
        rows = con.execute(
            "SELECT created, flow, user_id, username, data FROM records WHERE created LIKE ? ORDER BY id",
            (f"{day}%",),
        ).fetchall()
    return [
        {"created": c, "flow": f, "user_id": u, "username": n, **json.loads(d)} for c, f, u, n, d in rows
    ]
