"""
Test suite for Phase 1 critical fixes.
"""

import pytest
import pandas as pd
from src.utils import (
    allowed_file,
    sanitize_filename,
    validate_dataframe_size,
    validate_required_columns
)


class TestFileValidation:
    """Test file validation functions."""

    def test_allowed_file_csv(self):
        """Test CSV files are allowed."""
        assert allowed_file('test.csv') is True
        assert allowed_file('TEST.CSV') is True

    def test_allowed_file_xlsx(self):
        """Test Excel files are allowed."""
        assert allowed_file('test.xlsx') is True
        assert allowed_file('TEST.XLSX') is True

    def test_allowed_file_invalid(self):
        """Test invalid extensions are rejected."""
        assert allowed_file('test.txt') is False
        assert allowed_file('test.pdf') is False
        assert allowed_file('test.py') is False
        assert allowed_file('test') is False

    def test_sanitize_filename_basic(self):
        """Test basic filename sanitization."""
        result = sanitize_filename('test_file.csv')
        assert result == 'test_file.csv'

    def test_sanitize_filename_dangerous(self):
        """Test sanitization of dangerous filenames."""
        result = sanitize_filename('../../etc/passwd.csv')
        assert '..' not in result
        assert '/' not in result
        assert '\\' not in result

    def test_sanitize_filename_special_chars(self):
        """Test sanitization removes special characters."""
        result = sanitize_filename('test<>:"|?*.csv')
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result


class TestDataFrameValidation:
    """Test DataFrame validation functions."""

    def test_validate_size_valid(self):
        """Test valid DataFrame size."""
        df = pd.DataFrame({'a': range(100)})
        valid, error = validate_dataframe_size(df)
        assert valid is True
        assert error is None

    def test_validate_size_empty(self):
        """Test empty DataFrame is rejected."""
        df = pd.DataFrame()
        valid, error = validate_dataframe_size(df)
        assert valid is False
        assert 'empty' in error.lower()

    def test_validate_size_too_large(self):
        """Test oversized DataFrame is rejected."""
        # Create DataFrame with more than MAX_ROWS
        from config.settings import Config
        df = pd.DataFrame({'a': range(Config.MAX_ROWS + 1)})
        valid, error = validate_dataframe_size(df)
        assert valid is False
        assert 'exceeds' in error.lower()

    def test_validate_required_columns_valid(self):
        """Test DataFrame with all required columns."""
        df = pd.DataFrame({
            'Product': ['A', 'B'],
            'Quantity': [1, 2],
            'Price': [10, 20]
        })
        valid, error = validate_required_columns(df)
        assert valid is True
        assert error is None

    def test_validate_required_columns_missing(self):
        """Test DataFrame missing required columns."""
        df = pd.DataFrame({
            'Product': ['A', 'B'],
            'Quantity': [1, 2]
            # Missing 'Price'
        })
        valid, error = validate_required_columns(df)
        assert valid is False
        assert 'missing' in error.lower()
        assert 'price' in error.lower()

    def test_validate_required_columns_case_insensitive(self):
        """Test column validation is case-insensitive."""
        df = pd.DataFrame({
            'PRODUCT': ['A', 'B'],
            'quantity': [1, 2],
            'Price': [10, 20]
        })
        valid, error = validate_required_columns(df)
        assert valid is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
