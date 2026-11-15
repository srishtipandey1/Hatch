from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class GnaniLedger:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS gnani_ledger (
                    id INTEGER PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    kind TEXT NOT NULL,
                    model TEXT NOT NULL,
                    units REAL NOT NULL,
                    estimated_inr REAL,
                    request_id TEXT,
                    status INTEGER NOT NULL,
                    latency_ms REAL NOT NULL
                )"""
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def record(
        self,
        *,
        kind: str,
        model: str,
        units: float,
        estimated_inr: float | None,
        request_id: str | None,
        status: int,
        latency_ms: float,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO gnani_ledger
                (timestamp, kind, model, units, estimated_inr, request_id, status, latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (time.time(), kind, model, units, estimated_inr, request_id, status, latency_ms),
            )

    def summary(self) -> dict[str, float | int | None]:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT COUNT(*), SUM(CASE WHEN status < 400 THEN 1 ELSE 0 END),
                          SUM(estimated_inr), MAX(timestamp),
                          SUM(CASE WHEN estimated_inr IS NULL THEN 1 ELSE 0 END)
                   FROM gnani_ledger"""
            ).fetchone()
        return {
            "calls": int(row[0] or 0),
            "successful_calls": int(row[1] or 0),
            "estimated_inr": float(row[2]) if row[2] is not None else None,
            "last_call_timestamp": float(row[3]) if row[3] is not None else None,
            "unpriced_calls": int(row[4] or 0),
        }
