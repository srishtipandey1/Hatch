from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Iterator

from backend.app.models import AgentSpec, Provenance, TestReport
from contextlib import contextmanager


class HatchStore:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """CREATE TABLE IF NOT EXISTS agents (
                       id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at REAL NOT NULL
                   );
                   CREATE TABLE IF NOT EXISTS spec_versions (
                       id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, version INTEGER NOT NULL,
                       spec_json TEXT NOT NULL, status TEXT NOT NULL,
                       FOREIGN KEY(agent_id) REFERENCES agents(id)
                   );
                   CREATE TABLE IF NOT EXISTS test_runs (
                       id TEXT PRIMARY KEY, version_id TEXT NOT NULL, report_json TEXT NOT NULL,
                       started_at REAL NOT NULL
                   );"""
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def save_agent(self, spec: AgentSpec, status: str = "draft") -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO agents(id, name, created_at) VALUES (?, ?, ?)",
                (spec.agent_id, spec.name, time.time()),
            )
            connection.execute(
                """INSERT INTO spec_versions(id, agent_id, version, spec_json, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    f"{spec.agent_id}:v{spec.version}",
                    spec.agent_id,
                    spec.version,
                    spec.model_dump_json(),
                    status,
                ),
            )

    def save_spec_version(self, spec: AgentSpec, status: str = "draft") -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO spec_versions(id, agent_id, version, spec_json, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    f"{spec.agent_id}:v{spec.version}",
                    spec.agent_id,
                    spec.version,
                    spec.model_dump_json(),
                    status,
                ),
            )

    def get_spec(self, agent_id: str) -> AgentSpec | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT spec_json FROM spec_versions WHERE agent_id = ? ORDER BY version DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
        if row is None:
            return None
        spec = AgentSpec.model_validate_json(row["spec_json"])
        for field in AgentSpec.model_fields:
            if field == "provenance":
                continue
            spec.provenance.setdefault(
                field,
                Provenance(
                    source="defaulted",
                    evidence="Legacy spec had no recorded provenance for this field.",
                ),
            )
        return spec

    def list_agents(self) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT a.id, a.name, a.created_at, s.status
                   FROM agents a JOIN spec_versions s ON s.agent_id = a.id
                   ORDER BY a.created_at DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def save_report(self, report: TestReport) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO test_runs(id, version_id, report_json, started_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), report.version_id, report.model_dump_json(), time.time()),
            )

    def get_report(self, version_id: str) -> TestReport | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT report_json FROM test_runs WHERE version_id = ? ORDER BY started_at DESC LIMIT 1",
                (version_id,),
            ).fetchone()
        return TestReport.model_validate_json(row["report_json"]) if row else None
