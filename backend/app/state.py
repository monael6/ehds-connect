"""App state in SQLite: users and roles, decisions, consents, discharge letters, provisions, audit log.

Analytical data (patients, SPEs) lives in DuckDB, see datastore.py / engine/spe.py.
Keeping the two apart mirrors the EHDS split between operational systems and the HDAB.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
    organisation TEXT NOT NULL, data_holder TEXT, sign_in_method TEXT, patient_id TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
    user_id TEXT, user_name TEXT, role TEXT, organisation TEXT,
    area TEXT NOT NULL, action TEXT NOT NULL, patient_id TEXT, request_id TEXT,
    outcome TEXT, details TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
    request_id TEXT PRIMARY KEY, submitted_by TEXT, applicant TEXT, purpose TEXT,
    requested_as TEXT, decision TEXT NOT NULL, articles TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'automatic', staff_note TEXT,
    result TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provisions (
    request_id TEXT NOT NULL, data_holder TEXT NOT NULL, status TEXT NOT NULL,
    provided_by TEXT, provided_at TEXT, PRIMARY KEY (request_id, data_holder)
);
CREATE TABLE IF NOT EXISTS consents (
    patient_id TEXT PRIMARY KEY, cross_border INTEGER NOT NULL DEFAULT 0,
    hidden_sections TEXT NOT NULL DEFAULT '[]', since TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS letters (
    id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, encounter_id TEXT,
    version INTEGER NOT NULL, status TEXT NOT NULL, supersedes TEXT,
    content TEXT NOT NULL, signed_by TEXT, signed_at TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS letter_edits (
    id INTEGER PRIMARY KEY AUTOINCREMENT, letter_id TEXT NOT NULL, section TEXT NOT NULL,
    before TEXT, after TEXT, reason TEXT, editor_id TEXT, editor_name TEXT, ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS permissions (
    user_id TEXT NOT NULL, permission TEXT NOT NULL, granted_by TEXT, granted_by_name TEXT,
    granted_at TEXT NOT NULL, PRIMARY KEY (user_id, permission)
);
CREATE TABLE IF NOT EXISTS security_keys (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL, label TEXT,
    credential_id TEXT NOT NULL, public_key BLOB NOT NULL, sign_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, status_changed_at TEXT
);
CREATE TABLE IF NOT EXISTS key_challenges (
    challenge TEXT PRIMARY KEY, user_id TEXT NOT NULL, purpose TEXT NOT NULL, ref TEXT,
    created_at TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS recovery_codes (
    code_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, issued_by TEXT, expires_at TEXT NOT NULL, used_at TEXT
);
CREATE TABLE IF NOT EXISTS catalogue_entries (
    data_holder TEXT PRIMARY KEY, entry TEXT NOT NULL, updated_by TEXT, updated_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None or path is not None:
            p = str(path or settings.state_db)
            if p != ":memory:":
                Path(p).parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(p, check_same_thread=False, isolation_level=None)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL") if p != ":memory:" else None
            _conn.execute("PRAGMA foreign_keys=ON")
            _conn.executescript(SCHEMA)
            _migrate(_conn)
        return _conn


# Columns added after the first release; existing state.sqlite files get them on start.
MIGRATIONS = {
    "users": {"email": "TEXT", "password_hash": "TEXT", "hospital_role": "TEXT",
              "status": "TEXT NOT NULL DEFAULT 'active'"},
    "letters": {"signature": "TEXT"},
}


def _migrate(c: sqlite3.Connection) -> None:
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
        for col, decl in cols.items():
            if col not in have:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


@contextmanager
def tx():
    """One transaction; concurrent writers are serialised by the lock and SQLite."""
    c = connect()
    with _lock:
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise


def query(sql: str, params: tuple | dict = ()) -> list[dict]:
    with _lock:
        return [dict(r) for r in connect().execute(sql, params).fetchall()]


def one(sql: str, params: tuple | dict = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def audit(user: dict | None, area: str, action: str, *, patient_id: str | None = None,
          request_id: str | None = None, outcome: str | None = None, details: dict | None = None,
          conn: sqlite3.Connection | None = None) -> None:
    u = user or {}
    row = (now(), u.get("id"), u.get("name"), u.get("role"), u.get("organisation"), area, action,
           patient_id, request_id, outcome, json.dumps(details or {}, ensure_ascii=False, default=str))
    sql = ("INSERT INTO audit (ts,user_id,user_name,role,organisation,area,action,patient_id,request_id,outcome,details)"
           " VALUES (?,?,?,?,?,?,?,?,?,?,?)")
    if conn is not None:
        conn.execute(sql, row)
    else:
        with tx() as c:
            c.execute(sql, row)


def audit_rows(**filters) -> list[dict]:
    where, params = [], []
    for col in ("user_id", "role", "area", "patient_id", "request_id", "outcome"):
        if filters.get(col):
            where.append(f"{col} = ?")
            params.append(filters[col])
    if filters.get("since"):
        where.append("ts >= ?")
        params.append(filters["since"])
    if filters.get("until"):
        where.append("ts <= ?")
        params.append(filters["until"])
    sql = "SELECT * FROM audit" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC LIMIT ?"
    params.append(int(filters.get("limit") or 500))
    rows = query(sql, tuple(params))
    for r in rows:
        r["details"] = json.loads(r["details"] or "{}")
    return rows
