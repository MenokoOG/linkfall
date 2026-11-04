"""The log schema. Both tables are append-only: triggers abort every UPDATE and DELETE."""

SCHEMA_VERSION = 1

DDL = """
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    seed INTEGER NOT NULL,
    mode TEXT NOT NULL,
    scenario TEXT NOT NULL,
    schema_version INTEGER NOT NULL
) STRICT;

CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs (run_id),
    turn INTEGER NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL
) STRICT;

CREATE INDEX events_by_run ON events (run_id, id);

CREATE TRIGGER runs_no_update BEFORE UPDATE ON runs
BEGIN SELECT RAISE(ABORT, 'event log is append-only'); END;
CREATE TRIGGER runs_no_delete BEFORE DELETE ON runs
BEGIN SELECT RAISE(ABORT, 'event log is append-only'); END;
CREATE TRIGGER events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'event log is append-only'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'event log is append-only'); END;
"""
