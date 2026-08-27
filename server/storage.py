"""SQLite 持久化存储 — 替代内存字典，服务器重启不丢数据"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


_STORAGE_DIR = os.getenv("STORAGE_DIR", str(Path.home() / ".paper-review-data"))
_DB_PATH = os.path.join(_STORAGE_DIR, "paper_review.db")

DB_SCHEMAS = """
CREATE TABLE IF NOT EXISTS history_records (
    id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS original_texts (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS original_files (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS journals_data (
    id TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS models_used (
    id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history_records(timestamp);
"""


def _get_conn() -> sqlite3.Connection:
    os.makedirs(_STORAGE_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _get_conn() as conn:
        conn.executescript(DB_SCHEMAS)
        conn.commit()


def save_history_record(id: str, file_name: str, timestamp: str, summary: dict) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO history_records (id, file_name, timestamp, summary) VALUES (?, ?, ?, ?)",
            (id, file_name, timestamp, json.dumps(summary)),
        )
        conn.commit()


def get_all_history() -> list[dict]:
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT id, file_name, timestamp, summary FROM history_records ORDER BY timestamp DESC"
        )
        return [
            {
                "id": row[0],
                "file_name": row[1],
                "timestamp": row[2],
                "summary": json.loads(row[3]),
            }
            for row in cursor.fetchall()
        ]


def delete_history_record(id: str) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM history_records WHERE id = ?", (id,))
        conn.execute("DELETE FROM reports WHERE id = ?", (id,))
        conn.execute("DELETE FROM original_texts WHERE id = ?", (id,))
        conn.execute("DELETE FROM original_files WHERE id = ?", (id,))
        conn.execute("DELETE FROM journals_data WHERE id = ?", (id,))
        conn.execute("DELETE FROM models_used WHERE id = ?", (id,))
        conn.commit()


def save_report(id: str, data: dict) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reports (id, data) VALUES (?, ?)",
            (id, json.dumps(data, default=str)),
        )
        conn.commit()


def get_report(id: str) -> Optional[dict]:
    with _get_conn() as conn:
        cursor = conn.execute("SELECT data FROM reports WHERE id = ?", (id,))
        row = cursor.fetchone()
        return json.loads(row[0]) if row else None


def save_original_text(id: str, text: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO original_texts (id, text) VALUES (?, ?)",
            (id, text),
        )
        conn.commit()


def get_original_text(id: str) -> Optional[str]:
    with _get_conn() as conn:
        cursor = conn.execute("SELECT text FROM original_texts WHERE id = ?", (id,))
        row = cursor.fetchone()
        return row[0] if row else None


def save_original_file(id: str, filename: str, file_bytes: bytes) -> None:
    os.makedirs(_STORAGE_DIR, exist_ok=True)
    file_dir = os.path.join(_STORAGE_DIR, "files")
    os.makedirs(file_dir, exist_ok=True)
    file_path = os.path.join(file_dir, id)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO original_files (id, filename, filepath) VALUES (?, ?, ?)",
            (id, filename, file_path),
        )
        conn.commit()


def get_original_file(id: str) -> Optional[tuple[str, bytes]]:
    with _get_conn() as conn:
        cursor = conn.execute("SELECT filename, filepath FROM original_files WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            return None
        try:
            with open(row[1], "rb") as f:
                return (row[0], f.read())
        except FileNotFoundError:
            return None


def delete_original_file(id: str) -> None:
    with _get_conn() as conn:
        cursor = conn.execute("SELECT filepath FROM original_files WHERE id = ?", (id,))
        row = cursor.fetchone()
        if row:
            try:
                os.remove(row[0])
            except OSError:
                pass
    with _get_conn() as conn:
        conn.execute("DELETE FROM original_files WHERE id = ?", (id,))
        conn.commit()


def save_journals(id: str, journals: list[dict]) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO journals_data (id, data) VALUES (?, ?)",
            (id, json.dumps(journals, default=str)),
        )
        conn.commit()


def get_journals(id: str) -> Optional[list[dict]]:
    with _get_conn() as conn:
        cursor = conn.execute("SELECT data FROM journals_data WHERE id = ?", (id,))
        row = cursor.fetchone()
        return json.loads(row[0]) if row else None


def save_model_used(id: str, model_name: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO models_used (id, model_name) VALUES (?, ?)",
            (id, model_name),
        )
        conn.commit()


def get_model_used(id: str) -> Optional[str]:
    with _get_conn() as conn:
        cursor = conn.execute("SELECT model_name FROM models_used WHERE id = ?", (id,))
        row = cursor.fetchone()
        return row[0] if row else None
