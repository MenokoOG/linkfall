"""The range log: its own SQLite file, append-only by trigger, parameterized queries only.

It mirrors the mission event log on purpose and stays separate from it (ADR 0009).
"""

import json
import sqlite3
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from linkfall.engine.fingerprint import canonical_json
from linkfall.range.rows import LogRow, NewRow

SCHEMA_VERSION = 1
_BUSY_TIMEOUT_MS = 5000

_DDL = (
    """CREATE TABLE range_runs (
        run_id TEXT PRIMARY KEY,
        target TEXT NOT NULL,
        kind TEXT NOT NULL,
        created_at TEXT NOT NULL,
        schema_version INTEGER NOT NULL
    ) STRICT""",
    """CREATE TABLE range_rows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES range_runs (run_id),
        probe TEXT NOT NULL,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL
    ) STRICT""",
    "CREATE INDEX range_rows_by_run ON range_rows (run_id, id)",
    *(
        f"CREATE TRIGGER {table}_no_{verb.lower()} BEFORE {verb} ON {table}"
        " BEGIN SELECT RAISE(ABORT, 'range log is append-only'); END"
        for table in ("range_runs", "range_rows")
        for verb in ("UPDATE", "DELETE")
    ),
)


class RangeLogError(Exception):
    """The range log could not be read or written. Never swallowed."""


class RangeRunNotFoundError(RangeLogError):
    pass


@dataclass(frozen=True, slots=True)
class RangeHeader:
    run_id: str
    target: str
    kind: str
    created_at: str
    schema_version: int = SCHEMA_VERSION


class RangeStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._lock = threading.Lock()
        try:
            self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
            if str(path) != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL")
            self._init_schema()
        except sqlite3.Error as exc:
            raise RangeLogError(f"cannot open the range log: {exc}") from exc

    def _init_schema(self) -> None:
        version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        if version == SCHEMA_VERSION:
            return
        if version != 0:
            raise RangeLogError(f"unsupported range log schema version {version}")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in _DDL:
                self._conn.execute(statement)
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._conn.execute("COMMIT")
        except sqlite3.Error:
            self._conn.execute("ROLLBACK")
            raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def create_run(self, header: RangeHeader) -> None:
        self._write(
            f"cannot create range run {header.run_id!r}",
            "INSERT INTO range_runs (run_id, target, kind, created_at, schema_version)"
            " VALUES (?, ?, ?, ?, ?)",
            [(header.run_id, header.target, header.kind, header.created_at, header.schema_version)],
        )

    def append(self, run_id: str, rows: Sequence[NewRow]) -> None:
        """All of the rows or none of them."""
        self._write(
            f"cannot append to range run {run_id!r}",
            "INSERT INTO range_rows (run_id, probe, kind, payload) VALUES (?, ?, ?, ?)",
            [(run_id, r.probe, r.kind.value, canonical_json(r.payload)) for r in rows],
        )

    def _write(self, what: str, sql: str, batch: Sequence[tuple[object, ...]]) -> None:
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                for values in batch:
                    self._conn.execute(sql, values)
                self._conn.execute("COMMIT")
            except sqlite3.Error as exc:
                self._rollback()
                raise RangeLogError(f"{what}: {exc}") from exc
            except BaseException:
                self._rollback()
                raise

    def _rollback(self) -> None:
        if self._conn.in_transaction:
            self._conn.execute("ROLLBACK")

    def get_run(self, run_id: str) -> RangeHeader:
        with self._lock:
            row = self._conn.execute(
                "SELECT run_id, target, kind, created_at, schema_version FROM range_runs"
                " WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise RangeRunNotFoundError(f"no range run {run_id!r}")
        return RangeHeader(*row)

    def read_rows(self, run_id: str) -> list[LogRow]:
        with self._lock:
            found = self._conn.execute(
                "SELECT id, probe, kind, payload FROM range_rows WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        rows: list[LogRow] = []
        for row_id, probe, kind, payload in found:
            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise RangeLogError(f"row {row_id} holds invalid JSON") from exc
            if not isinstance(decoded, dict):
                raise RangeLogError(f"row {row_id} payload is not an object")
            rows.append(LogRow(row_id, probe, kind, decoded))
        return rows
