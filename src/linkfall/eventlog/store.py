"""SQLite access. Parameterized queries only; every write batch is all-or-nothing."""

import json
import sqlite3
import threading
from collections.abc import Sequence
from pathlib import Path

from linkfall.engine.fingerprint import canonical_json
from linkfall.eventlog.schema import DDL, SCHEMA_VERSION
from linkfall.eventlog.types import LogRow, NewRow, RunHeader
from linkfall.runmode import RunMode

_BUSY_TIMEOUT_MS = 5000


class EventLogError(Exception):
    """The log could not be read or written. Never swallowed."""


class RunNotFoundError(EventLogError):
    pass


class EventStore:
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
            raise EventLogError(f"cannot open the event log: {exc}") from exc

    def _init_schema(self) -> None:
        version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        if version == SCHEMA_VERSION:
            return
        if version != 0:
            raise EventLogError(f"unsupported log schema version {version}")
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in _statements(DDL):
                self._conn.execute(statement)
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._conn.execute("COMMIT")
        except sqlite3.Error:
            self._conn.execute("ROLLBACK")
            raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def create_run(self, header: RunHeader, rows: Sequence[NewRow] = ()) -> list[int]:
        """Create a run and its first rows in one transaction."""
        encoded = [_encode(r) for r in rows]
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    "INSERT INTO runs (run_id, seed, mode, scenario, schema_version)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (header.run_id, header.seed, header.mode.value, header.scenario,
                     header.schema_version),
                )  # fmt: skip
                ids = self._insert_rows(header.run_id, encoded)
                self._conn.execute("COMMIT")
                return ids
            except sqlite3.Error as exc:
                self._rollback()
                raise EventLogError(f"cannot create run {header.run_id!r}: {exc}") from exc
            except BaseException:
                self._rollback()
                raise

    def append_batch(self, run_id: str, rows: Sequence[NewRow]) -> list[int]:
        encoded = [_encode(r) for r in rows]
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                ids = self._insert_rows(run_id, encoded)
                self._conn.execute("COMMIT")
                return ids
            except sqlite3.Error as exc:
                self._rollback()
                raise EventLogError(f"cannot append to run {run_id!r}: {exc}") from exc
            except BaseException:
                self._rollback()
                raise

    def _insert_rows(self, run_id: str, encoded: Sequence[tuple[int, str, str]]) -> list[int]:
        ids: list[int] = []
        for turn, kind, payload in encoded:
            cursor = self._conn.execute(
                "INSERT INTO events (run_id, turn, kind, payload) VALUES (?, ?, ?, ?)",
                (run_id, turn, kind, payload),
            )
            if cursor.lastrowid is None:
                raise EventLogError("insert returned no row id")
            ids.append(cursor.lastrowid)
        return ids

    def _rollback(self) -> None:
        if self._conn.in_transaction:
            self._conn.execute("ROLLBACK")

    def get_run(self, run_id: str) -> RunHeader:
        with self._lock:
            row = self._conn.execute(
                "SELECT run_id, seed, mode, scenario, schema_version FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise RunNotFoundError(f"no run {run_id!r}")
        try:
            return RunHeader(row[0], row[1], RunMode(row[2]), row[3], row[4])
        except ValueError as exc:
            raise EventLogError(f"run {run_id!r} has an unknown mode {row[2]!r}") from exc

    def read_rows(self, run_id: str, after_id: int = 0) -> list[LogRow]:
        """Rows of one run in order. `after_id` resumes a stream (Last-Event-ID)."""
        with self._lock:
            found = self._conn.execute(
                "SELECT id, run_id, turn, kind, payload FROM events"
                " WHERE run_id = ? AND id > ? ORDER BY id",
                (run_id, after_id),
            ).fetchall()
        rows: list[LogRow] = []
        for row_id, rid, turn, kind, payload in found:
            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise EventLogError(f"row {row_id} holds invalid JSON") from exc
            if not isinstance(decoded, dict):
                raise EventLogError(f"row {row_id} payload is not an object")
            rows.append(LogRow(row_id, rid, turn, kind, decoded))
        return rows


def _encode(row: NewRow) -> tuple[int, str, str]:
    return row.turn, str(row.kind), canonical_json(row.payload)


def _statements(script: str) -> list[str]:
    """Split the DDL into statements, keeping each trigger body whole."""
    parts: list[str] = []
    buffer = ""
    for line in script.splitlines():
        buffer += line + "\n"
        stripped = line.strip()
        if stripped.endswith(";") and ("CREATE TRIGGER" not in buffer or stripped.endswith("END;")):
            parts.append(buffer.strip())
            buffer = ""
    return [p for p in parts if p]
