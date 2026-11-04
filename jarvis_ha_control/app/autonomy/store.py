"""Stockage SQLite : journal des décisions, propositions à valider, alertes en cours."""
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

DB_PATH = os.getenv("JARVIS_DB", "/data/jarvis.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    severity TEXT NOT NULL,
    kind TEXT NOT NULL,
    entity_id TEXT,
    message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    status TEXT NOT NULL,
    rule TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    message TEXT NOT NULL,
    action TEXT NOT NULL,
    expect_state TEXT,
    decided_by TEXT,
    result TEXT
);
CREATE TABLE IF NOT EXISTS active (
    key TEXT PRIMARY KEY,
    severity TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_notified TEXT NOT NULL,
    notified_count INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | None = None):
        self.path = path or DB_PATH
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()

    # --- journal -----------------------------------------------------------
    def log(self, severity: str, kind: str, message: str, entity_id: str | None = None) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO journal (ts, severity, kind, entity_id, message) VALUES (?,?,?,?,?)",
                (_now(), severity, kind, entity_id, message),
            )
            self._db.commit()
            return cur.lastrowid

    def journal(self, limit: int = 50, since: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM journal", []
        if since:
            q += " WHERE ts > ?"
            args.append(since)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(int(limit))
        with self._lock:
            return [dict(r) for r in self._db.execute(q, args).fetchall()]

    # --- propositions ------------------------------------------------------
    def add_proposal(self, rule: str, entity_id: str, message: str, action: dict, expect_state: str | None) -> int:
        now = _now()
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO proposals (created, updated, status, rule, entity_id, message, action, expect_state) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (now, now, "pending", rule, entity_id, message, json.dumps(action), expect_state),
            )
            self._db.commit()
            return cur.lastrowid

    def get_proposal(self, pid: int) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
        return self._proposal(row) if row else None

    def proposals(self, status: str | None = "pending", limit: int = 50) -> list[dict]:
        q, args = "SELECT * FROM proposals", []
        if status:
            q += " WHERE status=?"
            args.append(status)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(int(limit))
        with self._lock:
            rows = self._db.execute(q, args).fetchall()
        return [self._proposal(r) for r in rows]

    def pending_for(self, rule: str, entity_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM proposals WHERE status='pending' AND rule=? AND entity_id=?", (rule, entity_id)
            ).fetchone()
        return self._proposal(row) if row else None

    def set_proposal(self, pid: int, status: str, decided_by: str | None = None, result: str | None = None) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE proposals SET status=?, updated=?, decided_by=COALESCE(?, decided_by), result=COALESCE(?, result) "
                "WHERE id=?",
                (status, _now(), decided_by, result, pid),
            )
            self._db.commit()

    def expire_proposals(self, older_than_iso: str) -> int:
        with self._lock:
            cur = self._db.execute(
                "UPDATE proposals SET status='expired', updated=? WHERE status='pending' AND created < ?",
                (_now(), older_than_iso),
            )
            self._db.commit()
            return cur.rowcount

    @staticmethod
    def _proposal(row) -> dict:
        d = dict(row)
        d["action"] = json.loads(d["action"])
        return d

    # --- alertes en cours (survivent à un redémarrage) ---------------------
    def active_load(self) -> dict:
        with self._lock:
            rows = self._db.execute("SELECT * FROM active").fetchall()
        return {r["key"]: dict(r) for r in rows}

    def active_save(self, key: str, severity: str, first_seen: str, last_notified: str, count: int) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO active (key, severity, first_seen, last_notified, notified_count) VALUES (?,?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET severity=excluded.severity, last_notified=excluded.last_notified, "
                "notified_count=excluded.notified_count",
                (key, severity, first_seen, last_notified, count),
            )
            self._db.commit()

    def active_delete(self, key: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM active WHERE key=?", (key,))
            self._db.commit()

    # --- meta --------------------------------------------------------------
    def meta_get(self, k: str) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return row["v"] if row else None

    def meta_set(self, k: str, v: str) -> None:
        with self._lock:
            self._db.execute("INSERT INTO meta (k, v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))
            self._db.commit()
