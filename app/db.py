"""Small SQLite persistence layer for uploaded documents and passages."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import DATABASE_PATH


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                page_number INTEGER,
                section TEXT,
                body TEXT NOT NULL,
                retrieval_text TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_document
                ON chunks(document_id, chunk_index);
            """
        )

