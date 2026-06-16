"""SQLite persistence layer for TPS session data.

Provides PersistentSessionStore for durable storage of per-session TPS
metrics. Uses WAL journal mode for read concurrency and UPSERT semantics
for write-through caching.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Current schema version — bump when altering tables
_SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS session_tps (
    session_id          TEXT PRIMARY KEY,
    call_count          INTEGER NOT NULL DEFAULT 0,
    total_output_tokens INTEGER NOT NULL DEFAULT 0,
    total_duration      REAL    NOT NULL DEFAULT 0.0,
    peak_tps            REAL    NOT NULL DEFAULT 0.0,
    last_call_tps       REAL    NOT NULL DEFAULT 0.0,
    avg_tps             REAL    NOT NULL DEFAULT 0.0,
    updated_at          TEXT    NOT NULL
);
"""

_UPSERT = """
INSERT OR REPLACE INTO session_tps
    (session_id, call_count, total_output_tokens, total_duration,
     peak_tps, last_call_tps, avg_tps, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?);
"""

_LOAD_ONE = """
SELECT session_id, call_count, total_output_tokens, total_duration,
       peak_tps, last_call_tps, avg_tps, updated_at
FROM session_tps WHERE session_id = ?;
"""

_LOAD_ALL = """
SELECT session_id, call_count, total_output_tokens, total_duration,
       peak_tps, last_call_tps, avg_tps, updated_at
FROM session_tps;
"""


class PersistentSessionStore:
    """Thread-safe SQLite store for per-session TPS state.

    Usage::

        store = PersistentSessionStore("/path/to/tps.db")
        store.save("sess-1", state_dict)
        data = store.load("sess-1")
        store.close()
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Open connection, enable WAL, create schema if needed."""
        try:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            self._conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                timeout=5.0,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.executescript(_DDL)
            self._migrate()
            self._conn.commit()
            logger.debug("tps-counter: DB initialized at %s", self._db_path)
        except Exception as exc:
            logger.warning("tps-counter: DB init failed: %s", exc)
            self._conn = None
            raise

    def _migrate(self) -> None:
        """Apply schema migrations from current version to latest."""
        cur = self._conn.execute("SELECT version FROM schema_version")
        row = cur.fetchone()
        current = row[0] if row else 0
        if current < 1:
            self._conn.execute("DELETE FROM schema_version")
            self._conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (_SCHEMA_VERSION,),
            )
        # Future migrations: if current < 2: ALTER TABLE ...

    @staticmethod
    def _row_to_dict(row: tuple) -> Dict[str, Any]:
        """Convert a DB row tuple to a dict matching _SessionTPS fields."""
        return {
            "session_id": row[0],
            "call_count": row[1],
            "total_output_tokens": row[2],
            "total_duration": row[3],
            "peak_tps": row[4],
            "last_call_tps": row[5],
            "avg_tps": row[6],
            "updated_at": row[7],
        }

    @staticmethod
    def _state_to_row(session_id: str, state: Any) -> tuple:
        """Extract a UPSERT row from a _SessionTPS instance or dict."""
        if isinstance(state, dict):
            return (
                session_id,
                state.get("call_count", 0),
                state.get("total_output_tokens", 0),
                state.get("total_duration", 0.0),
                state.get("peak_tps", 0.0),
                state.get("last_call_tps", 0.0),
                state.get("avg_tps", 0.0),
                datetime.now(timezone.utc).isoformat(),
            )
        # _SessionTPS object — access attributes directly
        return (
            session_id,
            state.call_count,
            state.total_output_tokens,
            state.total_duration,
            state.peak_tps,
            state.last_call_tps,
            state.avg_tps,
            datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, session_id: str, state: Any) -> None:
        """UPSERT the current TPS state for *session_id*."""
        if self._conn is None:
            return
        try:
            row = self._state_to_row(session_id, state)
            with self._lock:
                self._conn.execute(_UPSERT, row)
                self._conn.commit()
        except Exception as exc:
            logger.warning("tps-counter: DB save failed for %s: %s", session_id, exc)

    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load TPS state for a single session, or None if absent."""
        if self._conn is None:
            return None
        try:
            with self._lock:
                cur = self._conn.execute(_LOAD_ONE, (session_id,))
                row = cur.fetchone()
            return self._row_to_dict(row) if row else None
        except Exception as exc:
            logger.warning("tps-counter: DB load failed for %s: %s", session_id, exc)
            return None

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        """Bulk-load all session TPS records."""
        if self._conn is None:
            return {}
        try:
            with self._lock:
                cur = self._conn.execute(_LOAD_ALL)
                rows = cur.fetchall()
            return {row[0]: self._row_to_dict(row) for row in rows}
        except Exception as exc:
            logger.warning("tps-counter: DB load_all failed: %s", exc)
            return {}

    def close(self) -> None:
        """Clean shutdown of the DB connection."""
        if self._conn is not None:
            try:
                with self._lock:
                    self._conn.close()
            except Exception:
                pass
            self._conn = None
