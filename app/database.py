import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("PV_DB_PATH", "/data/pv_trials.db"))


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS trial_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def save_record(title: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    final_title = title or f"试算 {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO trial_records (title, payload, created_at) VALUES (?, ?, ?)",
            (final_title, json.dumps(payload, ensure_ascii=False), created_at),
        )
        record_id = cursor.lastrowid
    return {"id": record_id, "title": final_title, "createdAt": created_at}


def list_records() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, title, created_at FROM trial_records ORDER BY id DESC"
        ).fetchall()
    return [
        {"id": row["id"], "title": row["title"], "createdAt": row["created_at"]}
        for row in rows
    ]


def get_record(record_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, title, payload, created_at FROM trial_records WHERE id = ?",
            (record_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "createdAt": row["created_at"],
        "payload": json.loads(row["payload"]),
    }


def delete_record(record_id: int) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM trial_records WHERE id = ?", (record_id,))
    return cursor.rowcount > 0
