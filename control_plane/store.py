from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Protocol

from .models import DecisionTrace


class RunRepository(Protocol):
    def save(self, trace: DecisionTrace) -> None: ...

    def get(self, run_id: str) -> DecisionTrace | None: ...

    def list(self) -> list[DecisionTrace]: ...

    def find_by_idempotency_key(self, key: str) -> DecisionTrace | None: ...


class InMemoryRunRepository:
    def __init__(self) -> None:
        self._runs: dict[str, DecisionTrace] = {}
        self._idempotency_index: dict[str, str] = {}

    @staticmethod
    def _clone(trace: DecisionTrace) -> DecisionTrace:
        return trace.model_copy(deep=True)

    def save(self, trace: DecisionTrace) -> None:
        self._runs[trace.run_id] = self._clone(trace)
        if trace.idempotency_key:
            self._idempotency_index[trace.idempotency_key] = trace.run_id

    def get(self, run_id: str) -> DecisionTrace | None:
        trace = self._runs.get(run_id)
        return self._clone(trace) if trace is not None else None

    def list(self) -> list[DecisionTrace]:
        return [self._clone(trace) for trace in self._runs.values()]

    def find_by_idempotency_key(self, key: str) -> DecisionTrace | None:
        run_id = self._idempotency_index.get(key)
        return self.get(run_id) if run_id is not None else None


class SQLiteRunRepository:
    """Durable DecisionTrace repository using only Python's stdlib SQLite driver."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                idempotency_key TEXT UNIQUE,
                request_fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                trace_json TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_updated_at ON runs(updated_at DESC)"
        )
        self._connection.commit()

    @staticmethod
    def _decode(payload: str) -> DecisionTrace:
        return DecisionTrace.model_validate_json(payload)

    def save(self, trace: DecisionTrace) -> None:
        payload = trace.model_dump_json()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO runs (
                    run_id, idempotency_key, request_fingerprint,
                    created_at, updated_at, trace_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    idempotency_key = excluded.idempotency_key,
                    request_fingerprint = excluded.request_fingerprint,
                    updated_at = excluded.updated_at,
                    trace_json = excluded.trace_json
                """,
                (
                    trace.run_id,
                    trace.idempotency_key,
                    trace.request_fingerprint,
                    trace.created_at.isoformat(),
                    trace.updated_at.isoformat(),
                    payload,
                ),
            )

    def get(self, run_id: str) -> DecisionTrace | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT trace_json FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._decode(row[0]) if row else None

    def list(self) -> list[DecisionTrace]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT trace_json FROM runs ORDER BY created_at ASC"
            ).fetchall()
        return [self._decode(row[0]) for row in rows]

    def find_by_idempotency_key(self, key: str) -> DecisionTrace | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT trace_json FROM runs WHERE idempotency_key = ?", (key,)
            ).fetchone()
        return self._decode(row[0]) if row else None

    def close(self) -> None:
        with self._lock:
            self._connection.close()
