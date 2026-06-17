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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Current schema version — bump when altering tables
_SCHEMA_VERSION = 3

_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS session_tps (
    session_id          TEXT PRIMARY KEY,
    call_count          INTEGER NOT NULL DEFAULT 0,
    total_output_tokens INTEGER NOT NULL DEFAULT 0,
    total_input_tokens  INTEGER NOT NULL DEFAULT 0,
    total_duration      REAL    NOT NULL DEFAULT 0.0,
    peak_tps            REAL    NOT NULL DEFAULT 0.0,
    last_call_tps       REAL    NOT NULL DEFAULT 0.0,
    avg_tps             REAL    NOT NULL DEFAULT 0.0,
    updated_at          TEXT    NOT NULL
);
"""

_UPSERT = """
INSERT OR REPLACE INTO session_tps
    (session_id, call_count, total_output_tokens, total_input_tokens,
     total_duration, peak_tps, last_call_tps, avg_tps, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

_LOAD_ONE = """
SELECT session_id, call_count, total_output_tokens, total_input_tokens,
       total_duration, peak_tps, last_call_tps, avg_tps, updated_at
FROM session_tps WHERE session_id = ?;
"""

_LOAD_ALL = """
SELECT session_id, call_count, total_output_tokens, total_input_tokens,
       total_duration, peak_tps, last_call_tps, avg_tps, updated_at
FROM session_tps;
"""

_DELETE_ONE = "DELETE FROM session_tps WHERE session_id = ?;"

_DELETE_ONE_EVENT = "DELETE FROM call_events WHERE session_id = ?;"

_DELETE_EXPIRED = "DELETE FROM session_tps WHERE updated_at < ?;"

_DELETE_ORPHANED_EVENTS = "DELETE FROM call_events WHERE session_id NOT IN (SELECT session_id FROM session_tps);"

_COUNT = "SELECT COUNT(*) FROM session_tps;"

_CALL_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS call_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT    NOT NULL,
    model           TEXT    NOT NULL DEFAULT '',
    provider        TEXT    NOT NULL DEFAULT '',
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    duration        REAL    NOT NULL DEFAULT 0.0,
    tps             REAL    NOT NULL DEFAULT 0.0,
    created_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_call_events_session_time
    ON call_events (session_id, created_at);
"""

_INSERT_EVENT = """
INSERT INTO call_events (session_id, model, provider, input_tokens, output_tokens, duration, tps, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?);
"""

_LOAD_EVENTS = """
SELECT id, session_id, model, provider, input_tokens, output_tokens, duration, tps, created_at
FROM call_events WHERE session_id = ?
"""

_LOAD_EVENTS_SINCE = " AND created_at >= ?"
_LOAD_EVENTS_UNTIL = " AND created_at <= ?"
_LOAD_EVENTS_ORDER = " ORDER BY created_at ASC LIMIT ?;"

_AGGREGATE_BY_MODEL = """
SELECT model,
       COUNT(*) as calls,
       SUM(output_tokens) as total_output,
       SUM(input_tokens) as total_input,
       SUM(duration) as total_duration,
       AVG(tps) as avg_tps,
       MAX(tps) as peak_tps
FROM call_events WHERE session_id = ?
"""

_AGGREGATE_BY_PROVIDER = """
SELECT provider,
       COUNT(*) as calls,
       SUM(output_tokens) as total_output,
       SUM(input_tokens) as total_input,
       SUM(duration) as total_duration,
       AVG(tps) as avg_tps,
       MAX(tps) as peak_tps
FROM call_events WHERE session_id = ?
"""

_AGGREGATE_SINCE = " AND created_at >= ?"
_AGGREGATE_GROUP = " GROUP BY {};"

_DELETE_EXPIRED_EVENTS = "DELETE FROM call_events WHERE created_at < ?;"

# -- Export queries (cross-session, bounded) --

_EXPORT_EVENTS_BASE = """
SELECT id, session_id, model, provider, input_tokens, output_tokens, duration, tps, created_at
FROM call_events WHERE 1=1
"""

_EXPORT_EVENTS_SINCE = " AND created_at >= ?"
_EXPORT_EVENTS_UNTIL = " AND created_at <= ?"
_EXPORT_EVENTS_ORDER = " ORDER BY created_at DESC LIMIT ?;"

_EXPORT_SESSIONS_BASE = """
SELECT session_id, call_count, total_output_tokens, total_input_tokens,
       total_duration, peak_tps, last_call_tps, avg_tps, updated_at
FROM session_tps WHERE 1=1
"""

_EXPORT_SESSIONS_IDS_PLACEHOLDER = " AND session_id IN ({})"
_EXPORT_SESSIONS_SINCE = " AND updated_at >= ?"
_EXPORT_SESSIONS_UNTIL = " AND updated_at <= ?"
_EXPORT_SESSIONS_ORDER = " ORDER BY updated_at DESC LIMIT ?;"


class PersistentSessionStore:
    """Thread-safe SQLite store for per-session TPS state.

    Usage::

        store = PersistentSessionStore("/path/to/tps.db")
        store.save("sess-1", state_dict)
        data = store.load("sess-1")
        store.close()
    """

    def __init__(self, db_path: str, retention_days: int = 7) -> None:
        self._db_path = db_path
        self._retention_days = retention_days
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._event_write_counter: int = 0  # triggers lazy expiry every 100 writes
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
            self._conn.executescript(_CALL_EVENTS_DDL)
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
                (1,),
            )
        if current < 2:
            # Add total_input_tokens column to existing tables
            try:
                self._conn.execute(
                    "ALTER TABLE session_tps ADD COLUMN total_input_tokens INTEGER NOT NULL DEFAULT 0"
                )
            except Exception:
                pass  # Column already exists
            self._conn.execute("DELETE FROM schema_version")
            self._conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (_SCHEMA_VERSION,),
            )
        if current < 3:
            # Create call_events table for per-call event storage
            try:
                self._conn.executescript(_CALL_EVENTS_DDL)
            except Exception:
                pass  # Table already exists
            self._conn.execute("DELETE FROM schema_version")
            self._conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (_SCHEMA_VERSION,),
            )

    @staticmethod
    def _row_to_dict(row: tuple) -> Dict[str, Any]:
        """Convert a DB row tuple to a dict matching _SessionTPS fields."""
        return {
            "session_id": row[0],
            "call_count": row[1],
            "total_output_tokens": row[2],
            "total_input_tokens": row[3],
            "total_duration": row[4],
            "peak_tps": row[5],
            "last_call_tps": row[6],
            "avg_tps": row[7],
            "updated_at": row[8],
        }

    @staticmethod
    def _state_to_row(session_id: str, state: Any) -> tuple:
        """Extract a UPSERT row from a _SessionTPS instance or dict."""
        if isinstance(state, dict):
            return (
                session_id,
                state.get("call_count", 0),
                state.get("total_output_tokens", 0),
                state.get("total_input_tokens", 0),
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
            state.total_input_tokens,
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

    def delete(self, session_id: str) -> bool:
        """Remove one session row and its call_events. Returns True if a row was deleted."""
        if self._conn is None:
            return False
        try:
            with self._lock:
                self._conn.execute(_DELETE_ONE_EVENT, (session_id,))
                cur = self._conn.execute(_DELETE_ONE, (session_id,))
                self._conn.commit()
                return cur.rowcount > 0
        except Exception as exc:
            logger.warning("tps-counter: DB delete failed for %s: %s", session_id, exc)
            return False

    def delete_expired(self, max_age_seconds: float) -> int:
        """Remove sessions older than *max_age_seconds*. Returns count deleted.
        
        Also cleans up orphaned call_events whose session_id no longer exists
        in session_tps.
        """
        if self._conn is None:
            return 0
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        ).isoformat()
        try:
            with self._lock:
                cur = self._conn.execute(_DELETE_EXPIRED, (cutoff,))
                deleted = cur.rowcount
                self._conn.execute(_DELETE_ORPHANED_EVENTS)
                self._conn.commit()
                return deleted
        except Exception as exc:
            logger.warning("tps-counter: DB delete_expired failed: %s", exc)
            return 0

    def count(self) -> int:
        """Return total number of rows in session_tps."""
        if self._conn is None:
            return 0
        try:
            with self._lock:
                cur = self._conn.execute(_COUNT)
                row = cur.fetchone()
            return row[0] if row else 0
        except Exception as exc:
            logger.warning("tps-counter: DB count failed: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Event storage API
    # ------------------------------------------------------------------

    def record_event(
        self,
        session_id: str,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        duration: float,
        tps: float,
    ) -> None:
        """Insert a per-call event into call_events. Thread-safe."""
        if self._conn is None:
            return
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._lock:
                self._conn.execute(
                    _INSERT_EVENT,
                    (session_id, model, provider, input_tokens, output_tokens, duration, tps, now),
                )
                self._conn.commit()
                self._event_write_counter += 1
                if self._event_write_counter >= 100:
                    self._event_write_counter = 0
                    self._delete_expired_events_unlocked(self._retention_days * 86400)
        except Exception as exc:
            logger.warning("tps-counter: event record failed for %s: %s", session_id, exc)

    def load_events(
        self,
        session_id: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Load call events for a session, optionally filtered by time range."""
        if self._conn is None:
            return []
        sql = _LOAD_EVENTS
        params: list = [session_id]
        if since:
            sql += _LOAD_EVENTS_SINCE
            params.append(since)
        if until:
            sql += _LOAD_EVENTS_UNTIL
            params.append(until)
        sql += _LOAD_EVENTS_ORDER
        params.append(limit)
        try:
            with self._lock:
                cur = self._conn.execute(sql, params)
                rows = cur.fetchall()
            return [self._event_row_to_dict(row) for row in rows]
        except Exception as exc:
            logger.warning("tps-counter: load_events failed for %s: %s", session_id, exc)
            return []

    def aggregate_by_model(
        self, session_id: str, since: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate call events grouped by model for a session."""
        if self._conn is None:
            return {}
        sql = _AGGREGATE_BY_MODEL
        params: list = [session_id]
        if since:
            sql += _AGGREGATE_SINCE
            params.append(since)
        sql += _AGGREGATE_GROUP.format("model")
        try:
            with self._lock:
                cur = self._conn.execute(sql, params)
                rows = cur.fetchall()
            return {
                row[0]: {
                    "calls": row[1],
                    "total_output": row[2],
                    "total_input": row[3],
                    "total_duration": round(row[4], 3),
                    "avg_tps": round(row[5], 2),
                    "peak_tps": round(row[6], 2),
                }
                for row in rows
            }
        except Exception as exc:
            logger.warning("tps-counter: aggregate_by_model failed for %s: %s", session_id, exc)
            return {}

    def aggregate_by_provider(
        self, session_id: str, since: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate call events grouped by provider for a session."""
        if self._conn is None:
            return {}
        sql = _AGGREGATE_BY_PROVIDER
        params: list = [session_id]
        if since:
            sql += _AGGREGATE_SINCE
            params.append(since)
        sql += _AGGREGATE_GROUP.format("provider")
        try:
            with self._lock:
                cur = self._conn.execute(sql, params)
                rows = cur.fetchall()
            return {
                row[0]: {
                    "calls": row[1],
                    "total_output": row[2],
                    "total_input": row[3],
                    "total_duration": round(row[4], 3),
                    "avg_tps": round(row[5], 2),
                    "peak_tps": round(row[6], 2),
                }
                for row in rows
            }
        except Exception as exc:
            logger.warning("tps-counter: aggregate_by_provider failed for %s: %s", session_id, exc)
            return {}

    def delete_expired_events(self, retention_seconds: float) -> int:
        """Delete call_events older than retention_seconds. Returns count deleted.
        
        Thread-safe: acquires lock if not already held.
        """
        if self._conn is None:
            return 0
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=retention_seconds)
        ).isoformat()
        try:
            with self._lock:
                cur = self._conn.execute(_DELETE_EXPIRED_EVENTS, (cutoff,))
                self._conn.commit()
                return cur.rowcount
        except Exception as exc:
            logger.warning("tps-counter: delete_expired_events failed: %s", exc)
            return 0

    def _delete_expired_events_unlocked(self, retention_seconds: float) -> int:
        """Internal: delete old events. Caller must hold self._lock."""
        if self._conn is None:
            return 0
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=retention_seconds)
        ).isoformat()
        try:
            cur = self._conn.execute(_DELETE_EXPIRED_EVENTS, (cutoff,))
            self._conn.commit()
            return cur.rowcount
        except Exception as exc:
            logger.warning("tps-counter: delete_expired_events failed: %s", exc)
            return 0

    @staticmethod
    def _event_row_to_dict(row: tuple) -> Dict[str, Any]:
        """Convert a call_events DB row to a dict."""
        return {
            "id": row[0],
            "session_id": row[1],
            "model": row[2],
            "provider": row[3],
            "input_tokens": row[4],
            "output_tokens": row[5],
            "duration": row[6],
            "tps": row[7],
            "created_at": row[8],
        }

    def event_count(self) -> int:
        """Return total number of rows in call_events."""
        if self._conn is None:
            return 0
        try:
            with self._lock:
                cur = self._conn.execute("SELECT COUNT(*) FROM call_events;")
                row = cur.fetchone()
            return row[0] if row else 0
        except Exception as exc:
            logger.warning("tps-counter: event_count failed: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Export API (bounded, cross-session)
    # ------------------------------------------------------------------

    def export_events(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
        max_limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Export call events across all sessions with bounded SQL.

        Returns at most ``min(limit, max_limit)`` rows ordered by created_at
        descending.  Does **not** call ``load_all()`` — uses direct bounded SQL.
        """
        if self._conn is None:
            return []
        effective_limit = max(1, min(limit, max_limit))
        sql = _EXPORT_EVENTS_BASE
        params: list = []
        if since:
            sql += _EXPORT_EVENTS_SINCE
            params.append(since)
        if until:
            sql += _EXPORT_EVENTS_UNTIL
            params.append(until)
        sql += _EXPORT_EVENTS_ORDER
        params.append(effective_limit)
        try:
            with self._lock:
                cur = self._conn.execute(sql, params)
                rows = cur.fetchall()
            return [self._event_row_to_dict(row) for row in rows]
        except Exception as exc:
            logger.warning("tps-counter: export_events failed: %s", exc)
            return []

    def export_sessions(
        self,
        session_ids: Optional[List[str]] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
        max_limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Export session TPS rows with bounded SQL.

        Optionally filters by a list of session IDs, a time window on
        ``updated_at``, and an enforced row limit.
        """
        if self._conn is None:
            return []
        effective_limit = max(1, min(limit, max_limit))
        sql = _EXPORT_SESSIONS_BASE
        params: list = []
        if session_ids:
            placeholders = ", ".join("?" for _ in session_ids)
            sql += _EXPORT_SESSIONS_IDS_PLACEHOLDER.format(placeholders)
            params.extend(session_ids)
        if since:
            sql += _EXPORT_SESSIONS_SINCE
            params.append(since)
        if until:
            sql += _EXPORT_SESSIONS_UNTIL
            params.append(until)
        sql += _EXPORT_SESSIONS_ORDER
        params.append(effective_limit)
        try:
            with self._lock:
                cur = self._conn.execute(sql, params)
                rows = cur.fetchall()
            return [self._row_to_dict(row) for row in rows]
        except Exception as exc:
            logger.warning("tps-counter: export_sessions failed: %s", exc)
            return []

    def close(self) -> None:
        """Clean shutdown of the DB connection."""
        if self._conn is not None:
            try:
                with self._lock:
                    self._conn.close()
            except Exception:
                pass
            self._conn = None
