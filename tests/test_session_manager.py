"""
Test suite for Session Manager functionality.
"""

import pytest
from src.session_manager import SessionManager
from datetime import datetime, timedelta


class TestSessionManager:
    """Test session management operations."""

    @pytest.fixture
    def session_manager(self):
        """Create fresh session manager for each test."""
        return SessionManager()

    def test_create_session(self, session_manager):
        """Test session creation."""
        db_path = '/tmp/test.duckdb'
        session_id = session_manager.create_session(db_path)

        assert session_id is not None
        assert len(session_id) > 0

    def test_get_session_data(self, session_manager):
        """Test retrieving session data."""
        db_path = '/tmp/test.duckdb'
        session_id = session_manager.create_session(db_path)

        session_data = session_manager.get_session_data(session_id)

        assert session_data is not None
        assert session_data['db_path'] == db_path
        assert session_data['active'] is True
        assert 'created_at' in session_data
        assert 'last_accessed' in session_data

    def test_get_database_path(self, session_manager):
        """Test getting database path for a session."""
        db_path = '/tmp/test.duckdb'
        session_id = session_manager.create_session(db_path)

        retrieved_path = session_manager.get_database_path(session_id)

        assert retrieved_path == db_path

    def test_session_exists(self, session_manager):
        """Test checking if session exists."""
        db_path = '/tmp/test.duckdb'
        session_id = session_manager.create_session(db_path)

        assert session_manager.session_exists(session_id) is True
        assert session_manager.session_exists('nonexistent') is False

    def test_deactivate_session(self, session_manager):
        """Test deactivating a session."""
        db_path = '/tmp/test.duckdb'
        session_id = session_manager.create_session(db_path)

        assert session_manager.session_exists(session_id) is True

        success = session_manager.deactivate_session(session_id)

        assert success is True
        assert session_manager.session_exists(session_id) is False

    def test_delete_session(self, session_manager):
        """Test deleting a session."""
        db_path = '/tmp/test.duckdb'
        session_id = session_manager.create_session(db_path)

        success = session_manager.delete_session(session_id)

        assert success is True
        assert session_manager.get_session_data(session_id) is None

    def test_get_session_count(self, session_manager):
        """Test getting active session count."""
        initial_count = session_manager.get_session_count()

        session_manager.create_session('/tmp/test1.duckdb')
        session_manager.create_session('/tmp/test2.duckdb')

        assert session_manager.get_session_count() == initial_count + 2

    def test_multiple_sessions(self, session_manager):
        """Test managing multiple sessions."""
        session_1 = session_manager.create_session('/tmp/db1.duckdb')
        session_2 = session_manager.create_session('/tmp/db2.duckdb')
        session_3 = session_manager.create_session('/tmp/db3.duckdb')

        assert session_manager.session_exists(session_1)
        assert session_manager.session_exists(session_2)
        assert session_manager.session_exists(session_3)

        # Each should have different paths
        path_1 = session_manager.get_database_path(session_1)
        path_2 = session_manager.get_database_path(session_2)
        path_3 = session_manager.get_database_path(session_3)

        assert path_1 != path_2
        assert path_2 != path_3
        assert path_1 != path_3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
