"""
DuckDB Database Manager
Handles creation, querying, and cleanup of session-isolated DuckDB databases.
"""

import os
import duckdb
import pandas as pd
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class DuckDBManager:
    """Manages DuckDB databases for sales data storage."""

    def __init__(self, base_dir: str = None):
        """
        Initialize DuckDB manager.

        Args:
            base_dir: Base directory for database files (default: temp directory)
        """
        if base_dir is None:
            # Use temp directory, fallback to local temp folder
            import tempfile
            self.base_dir = os.path.join(tempfile.gettempdir(), 'sales_analytics_dbs')
        else:
            self.base_dir = base_dir

        # Create base directory if it doesn't exist
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info(f"DuckDB Manager initialized with base_dir: {self.base_dir}")

    def create_database(self, session_id: str) -> str:
        """
        Create a new DuckDB database for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            str: Path to the created database file
        """
        db_path = os.path.join(self.base_dir, f"sales_{session_id}.duckdb")

        try:
            # Create database (will be created on first connection)
            conn = duckdb.connect(db_path)
            conn.close()

            logger.info(f"Created DuckDB database: {db_path}")
            return db_path

        except Exception as e:
            logger.error(f"Error creating database for session {session_id}: {str(e)}")
            raise

    def load_dataframe(
        self,
        db_path: str,
        dataframe: pd.DataFrame,
        table_name: str = 'sales'
    ) -> bool:
        """
        Load a pandas DataFrame into a DuckDB table.

        Args:
            db_path: Path to the database file
            dataframe: DataFrame to load
            table_name: Name of the table to create

        Returns:
            bool: True if successful
        """
        try:
            conn = duckdb.connect(db_path)

            # Convert Pandas 3.0 string dtype to object for DuckDB compatibility
            df_copy = dataframe.copy()
            for col in df_copy.columns:
                if hasattr(df_copy[col], 'dtype'):
                    dtype_str = str(df_copy[col].dtype)
                    # Check for 'string' or 'str' dtype (Pandas 3.0 uses 'string')
                    if dtype_str in ('string', 'str') or dtype_str.startswith('string'):
                        df_copy[col] = df_copy[col].astype('object')

            # Drop table if exists
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")

            # Create table from DataFrame using DuckDB's direct DataFrame support
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df_copy")

            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            conn.close()

            logger.info(f"Loaded {row_count} rows into {table_name} table in {db_path}")
            return True

        except Exception as e:
            logger.error(f"Error loading data into {db_path}: {str(e)}")
            if 'conn' in locals():
                conn.close()
            raise

    def query(
        self,
        db_path: str,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Execute a SQL query and return results as a DataFrame.

        Args:
            db_path: Path to the database file
            sql: SQL query to execute
            params: Optional query parameters

        Returns:
            pd.DataFrame: Query results
        """
        try:
            conn = duckdb.connect(db_path, read_only=True)

            if params:
                result = conn.execute(sql, params).df()
            else:
                result = conn.execute(sql).df()

            conn.close()

            logger.debug(f"Query executed successfully, returned {len(result)} rows")
            return result

        except Exception as e:
            logger.error(f"Error executing query on {db_path}: {str(e)}")
            if 'conn' in locals():
                conn.close()
            raise

    def get_table_schema(self, db_path: str, table_name: str = 'sales') -> List[Tuple[str, str]]:
        """
        Get the schema of a table.

        Args:
            db_path: Path to the database file
            table_name: Name of the table

        Returns:
            List of tuples (column_name, column_type)
        """
        try:
            conn = duckdb.connect(db_path, read_only=True)

            result = conn.execute(f"DESCRIBE {table_name}").fetchall()
            schema = [(row[0], row[1]) for row in result]

            conn.close()

            logger.debug(f"Retrieved schema for {table_name}: {len(schema)} columns")
            return schema

        except Exception as e:
            logger.error(f"Error getting schema from {db_path}: {str(e)}")
            if 'conn' in locals():
                conn.close()
            raise

    def list_tables(self, db_path: str) -> List[str]:
        """
        List all tables in the database.

        Args:
            db_path: Path to the database file

        Returns:
            List of table names
        """
        try:
            conn = duckdb.connect(db_path, read_only=True)

            result = conn.execute("SHOW TABLES").fetchall()
            tables = [row[0] for row in result]

            conn.close()

            return tables

        except Exception as e:
            logger.error(f"Error listing tables in {db_path}: {str(e)}")
            if 'conn' in locals():
                conn.close()
            raise

    def get_row_count(self, db_path: str, table_name: str = 'sales') -> int:
        """
        Get the number of rows in a table.

        Args:
            db_path: Path to the database file
            table_name: Name of the table

        Returns:
            int: Number of rows
        """
        try:
            conn = duckdb.connect(db_path, read_only=True)

            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            conn.close()

            return count

        except Exception as e:
            logger.error(f"Error getting row count from {db_path}: {str(e)}")
            if 'conn' in locals():
                conn.close()
            raise

    def delete_database(self, db_path: str) -> bool:
        """
        Delete a database file.

        Args:
            db_path: Path to the database file

        Returns:
            bool: True if successful
        """
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
                logger.info(f"Deleted database: {db_path}")
                return True
            else:
                logger.warning(f"Database not found: {db_path}")
                return False

        except Exception as e:
            logger.error(f"Error deleting database {db_path}: {str(e)}")
            raise

    def database_exists(self, db_path: str) -> bool:
        """
        Check if a database file exists.

        Args:
            db_path: Path to the database file

        Returns:
            bool: True if exists
        """
        return os.path.exists(db_path)

    def get_database_size_mb(self, db_path: str) -> float:
        """
        Get the size of a database file in MB.

        Args:
            db_path: Path to the database file

        Returns:
            float: Size in MB
        """
        try:
            if os.path.exists(db_path):
                size_bytes = os.path.getsize(db_path)
                return size_bytes / (1024 * 1024)
            else:
                return 0.0

        except Exception as e:
            logger.error(f"Error getting database size: {str(e)}")
            return 0.0

    def cleanup_old_databases(self, max_age_hours: int = 24) -> int:
        """
        Clean up database files older than specified hours.

        Args:
            max_age_hours: Maximum age in hours before deletion

        Returns:
            int: Number of databases deleted
        """
        try:
            deleted_count = 0
            current_time = datetime.now()

            for filename in os.listdir(self.base_dir):
                if filename.startswith('sales_') and filename.endswith('.duckdb'):
                    file_path = os.path.join(self.base_dir, filename)

                    # Get file modification time
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    age_hours = (current_time - file_mtime).total_seconds() / 3600

                    if age_hours > max_age_hours:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.info(f"Deleted old database: {filename} (age: {age_hours:.1f}h)")

            if deleted_count > 0:
                logger.info(f"Cleanup completed: {deleted_count} databases deleted")

            return deleted_count

        except Exception as e:
            logger.error(f"Error during database cleanup: {str(e)}")
            return 0

    def get_all_databases(self) -> List[Dict[str, Any]]:
        """
        Get information about all databases in the base directory.

        Returns:
            List of dictionaries with database info
        """
        try:
            databases = []

            for filename in os.listdir(self.base_dir):
                if filename.startswith('sales_') and filename.endswith('.duckdb'):
                    file_path = os.path.join(self.base_dir, filename)

                    # Extract session ID from filename
                    session_id = filename.replace('sales_', '').replace('.duckdb', '')

                    # Get file info
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    size_mb = self.get_database_size_mb(file_path)

                    databases.append({
                        'session_id': session_id,
                        'path': file_path,
                        'size_mb': size_mb,
                        'modified': file_mtime
                    })

            return databases

        except Exception as e:
            logger.error(f"Error listing databases: {str(e)}")
            return []


# Global instance
db_manager = DuckDBManager()
