"""
Test suite for DuckDB Manager functionality.
"""

import pytest
import pandas as pd
import os
import tempfile
from src.duckdb_manager import DuckDBManager


class TestDuckDBManager:
    """Test DuckDB database operations."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test databases."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup after tests
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def db_manager(self, temp_dir):
        """Create DuckDB manager with temp directory."""
        return DuckDBManager(base_dir=temp_dir)

    @pytest.fixture
    def sample_dataframe(self):
        """Create sample sales DataFrame."""
        return pd.DataFrame({
            'product': ['Laptop', 'Mouse', 'Keyboard'],
            'quantity': [2, 10, 5],
            'price': [50000, 500, 1200],
            'sales': [100000, 5000, 6000],
            'city': ['Delhi', 'Mumbai', 'Delhi']
        })

    def test_create_database(self, db_manager):
        """Test database creation."""
        session_id = 'test_session_123'
        db_path = db_manager.create_database(session_id)

        assert os.path.exists(db_path)
        assert 'test_session_123' in db_path
        assert db_path.endswith('.duckdb')

    def test_load_dataframe(self, db_manager, sample_dataframe):
        """Test loading DataFrame into DuckDB."""
        session_id = 'test_load'
        db_path = db_manager.create_database(session_id)

        success = db_manager.load_dataframe(db_path, sample_dataframe, 'sales')

        assert success is True

        # Verify row count
        row_count = db_manager.get_row_count(db_path, 'sales')
        assert row_count == 3

    def test_query_data(self, db_manager, sample_dataframe):
        """Test querying data from DuckDB."""
        session_id = 'test_query'
        db_path = db_manager.create_database(session_id)
        db_manager.load_dataframe(db_path, sample_dataframe, 'sales')

        # Query all data
        result = db_manager.query(db_path, "SELECT * FROM sales")

        assert len(result) == 3
        assert 'product' in result.columns
        assert 'Laptop' in result['product'].values

    def test_query_with_filter(self, db_manager, sample_dataframe):
        """Test querying with WHERE clause."""
        session_id = 'test_filter'
        db_path = db_manager.create_database(session_id)
        db_manager.load_dataframe(db_path, sample_dataframe, 'sales')

        # Query filtered data
        result = db_manager.query(
            db_path,
            "SELECT * FROM sales WHERE city = 'Delhi'"
        )

        assert len(result) == 2
        assert all(result['city'] == 'Delhi')

    def test_get_table_schema(self, db_manager, sample_dataframe):
        """Test retrieving table schema."""
        session_id = 'test_schema'
        db_path = db_manager.create_database(session_id)
        db_manager.load_dataframe(db_path, sample_dataframe, 'sales')

        schema = db_manager.get_table_schema(db_path, 'sales')

        assert len(schema) > 0
        column_names = [col[0] for col in schema]
        assert 'product' in column_names
        assert 'quantity' in column_names

    def test_delete_database(self, db_manager):
        """Test database deletion."""
        session_id = 'test_delete'
        db_path = db_manager.create_database(session_id)

        assert os.path.exists(db_path)

        success = db_manager.delete_database(db_path)

        assert success is True
        assert not os.path.exists(db_path)

    def test_database_exists(self, db_manager):
        """Test checking database existence."""
        session_id = 'test_exists'
        db_path = db_manager.create_database(session_id)

        assert db_manager.database_exists(db_path) is True

        db_manager.delete_database(db_path)

        assert db_manager.database_exists(db_path) is False

    def test_get_database_size(self, db_manager, sample_dataframe):
        """Test getting database file size."""
        session_id = 'test_size'
        db_path = db_manager.create_database(session_id)
        db_manager.load_dataframe(db_path, sample_dataframe, 'sales')

        size_mb = db_manager.get_database_size_mb(db_path)

        assert size_mb > 0
        assert size_mb < 1  # Should be very small for test data

    def test_multiple_sessions(self, db_manager, sample_dataframe):
        """Test multiple isolated sessions."""
        # Create two separate databases
        session_1 = 'session_1'
        session_2 = 'session_2'

        db_path_1 = db_manager.create_database(session_1)
        db_path_2 = db_manager.create_database(session_2)

        # Load same data into both
        db_manager.load_dataframe(db_path_1, sample_dataframe, 'sales')
        db_manager.load_dataframe(db_path_2, sample_dataframe, 'sales')

        # Verify both exist independently
        result_1 = db_manager.query(db_path_1, "SELECT COUNT(*) as cnt FROM sales")
        result_2 = db_manager.query(db_path_2, "SELECT COUNT(*) as cnt FROM sales")

        assert result_1['cnt'].iloc[0] == 3
        assert result_2['cnt'].iloc[0] == 3

        # Delete one shouldn't affect the other
        db_manager.delete_database(db_path_1)
        assert not db_manager.database_exists(db_path_1)
        assert db_manager.database_exists(db_path_2)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
