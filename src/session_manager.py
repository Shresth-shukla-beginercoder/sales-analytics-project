"""
Session Manager

Tracks per-user dataset sessions and maps each session ID to its
session-isolated DuckDB database file.

Thread-safe: all registry mutations are guarded by a lock so the
manager is safe under a single Gunicorn worker. (With multiple
workers the in-memory registry is NOT shared — see README limitations.)
"""

import os
import uuid
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session-to-database mappings in memory."""

    def __init__(self):
        # { session_id: { 'db_path': str, 'created_at': datetime,
        #                 'last_accessed': datetime, 'active': bool } }
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Creation / registration
    # ------------------------------------------------------------------

    def create_session(self, db_path: str) -> str:
        """Create a session with a fresh UUID and register its database path."""
        session_id = str(uuid.uuid4())
        return self.register_session(session_id, db_path)

    def register_session(self, session_id: str, db_path: str) -> str:
        """Register an externally generated session ID (e.g. the UUID that
        names the DuckDB file) together with its database path."""
        with self._lock:
            now = datetime.now()
            self._registry[session_id] = {
                'db_path': db_path,
                'created_at': now,
                'last_accessed': now,
                'active': True,
            }
        logger.info(f"Session registered: {session_id}")
        return session_id

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the session record, or None if missing/inactive.

        Touches ``last_accessed`` as a side effect."""
        with self._lock:
            data = self._registry.get(session_id)
            if not data or not data['active']:
                return None
            data['last_accessed'] = datetime.now()
            return dict(data)

    def get_database_path(self, session_id: str) -> Optional[str]:
        """Return the DuckDB file path for a session, or None."""
        data = self.get_session_data(session_id)
        return data['db_path'] if data else None

    def session_exists(self, session_id: str) -> bool:
        """True if the session is registered and still active."""
        return self.get_session_data(session_id) is not None

    def get_session_count(self) -> int:
        """Number of currently active sessions."""
        with self._lock:
            return sum(1 for d in self._registry.values() if d['active'])

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def deactivate_session(self, session_id: str) -> bool:
        """Mark a session inactive without deleting its database file."""
        with self._lock:
            data = self._registry.get(session_id)
            if not data:
                return False
            data['active'] = False
        return True

    def delete_session(self, session_id: str) -> bool:
        """Remove a session from the registry and delete its database file."""
        with self._lock:
            data = self._registry.pop(session_id, None)

        if data is None:
            return False

        db_path = data['db_path']
        if db_path and os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError as exc:
                logger.warning(f"Could not remove database {db_path}: {exc}")
        logger.info(f"Session deleted: {session_id}")
        return True

    def cleanup_expired(self, max_age_hours: int = 2) -> int:
        """Delete sessions older than ``max_age_hours``. Returns count removed."""
        now = datetime.now()
        expired = []
        with self._lock:
            for session_id, data in self._registry.items():
                if now - data['created_at'] > timedelta(hours=max_age_hours):
                    expired.append(session_id)

        removed = 0
        for session_id in expired:
            if self.delete_session(session_id):
                removed += 1
        if removed:
            logger.info(f"Cleaned up {removed} expired session(s)")
        return removed


# ----------------------------------------------------------------------
# Module-level interface
# ----------------------------------------------------------------------

session_manager = SessionManager()


def get_session_data(session_id: str) -> Optional[Dict[str, Any]]:
    """Module-level accessor (used by the chatbot service)."""
    return session_manager.get_session_data(session_id)


def cleanup_session(session_id: str) -> bool:
    """Module-level helper: delete one session and its database file."""
    return session_manager.delete_session(session_id)


def cleanup_expired_sessions(max_age_hours: int = 2) -> int:
    """Module-level helper: delete all sessions older than the given age."""
    return session_manager.cleanup_expired(max_age_hours)
