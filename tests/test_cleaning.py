"""
Test suite for data cleaning functionality.
"""

import pytest
import pandas as pd
import numpy as np
from src.cleaning import clean_sales_data


class TestDataCleaning:
    """Test the 10-step cleaning pipeline."""

    def test_column_standardization(self):
        """Test column names are standardized."""
        df = pd.DataFrame({
            ' Order ID ': [1, 2],
            'Product Name': ['A', 'B'],
            'Unit Price': [10, 20]
        })

        cleaned = clean_sales_data(df)

        assert 'order_id' in cleaned.columns
        assert 'product_name' in cleaned.columns
        assert 'unit_price' in cleaned.columns

    def test_duplicate_removal(self):
        """Test duplicate rows are removed."""
        df = pd.DataFrame({
            'product': ['A', 'B', 'A'],
            'quantity': [1, 2, 1],
            'price': [10, 20, 10]
        })

        cleaned = clean_sales_data(df)

        assert len(cleaned) == 2

    def test_whitespace_trimming(self):
        """Test leading/trailing whitespace is removed."""
        df = pd.DataFrame({
            'product': [' Laptop ', 'Mouse  '],
            'city': ['  Delhi', 'Mumbai  '],
            'quantity': [1, 2],
            'price': [50000, 500]
        })

        cleaned = clean_sales_data(df)

        assert cleaned['product'].iloc[0] == 'Laptop'
        assert cleaned['city'].iloc[0] == 'Delhi'

    def test_title_case_standardization(self):
        """Test categorical values are title-cased."""
        df = pd.DataFrame({
            'product': ['laptop', 'MOUSE'],
            'category': ['electronics', 'ELECTRONICS'],
            'city': ['delhi', 'MUMBAI'],
            'quantity': [1, 2],
            'price': [50000, 500]
        })

        cleaned = clean_sales_data(df)

        assert cleaned['category'].iloc[0] == 'Electronics'
        assert cleaned['city'].iloc[0] == 'Delhi'

    def test_date_parsing(self):
        """Test dates are parsed correctly."""
        df = pd.DataFrame({
            'product': ['A', 'B', 'C'],
            'order_date': ['2026-01-15', '15/01/2026', '15-01-2026'],
            'quantity': [1, 2, 3],
            'price': [10, 20, 30]
        })

        cleaned = clean_sales_data(df)

        assert pd.api.types.is_datetime64_any_dtype(cleaned['order_date'])
        assert cleaned['order_date'].notna().all()

    def test_numeric_coercion(self):
        """Test numeric columns are converted properly."""
        df = pd.DataFrame({
            'product': ['A', 'B'],
            'quantity': ['10', '20'],
            'price': ['100.5', '200.75'],
            'sales': ['1050', '4015']
        })

        cleaned = clean_sales_data(df)

        assert pd.api.types.is_numeric_dtype(cleaned['quantity'])
        assert pd.api.types.is_numeric_dtype(cleaned['price'])
        assert pd.api.types.is_numeric_dtype(cleaned['sales'])

    def test_quantity_validation(self):
        """Test invalid quantities are set to NA."""
        df = pd.DataFrame({
            'product': ['A', 'B', 'C', 'D'],
            'quantity': [10, 0, -5, 20],
            'price': [100, 200, 300, 400]
        })

        cleaned = clean_sales_data(df)

        assert cleaned['quantity'].iloc[0] == 10  # Valid
        assert pd.isna(cleaned['quantity'].iloc[1])  # Zero
        assert pd.isna(cleaned['quantity'].iloc[2])  # Negative
        assert cleaned['quantity'].iloc[3] == 20  # Valid

    def test_missing_sales_calculation(self):
        """Test missing sales values are calculated."""
        df = pd.DataFrame({
            'product': ['A', 'B'],
            'quantity': [2, 3],
            'price': [100, 200],
            'sales': [np.nan, np.nan]
        })

        cleaned = clean_sales_data(df)

        assert cleaned['sales'].iloc[0] == 200
        assert cleaned['sales'].iloc[1] == 600

    def test_invalid_sales_recalculation(self):
        """Test invalid sales values are recalculated."""
        df = pd.DataFrame({
            'product': ['A', 'B', 'C'],
            'quantity': [2, 3, 4],
            'price': [100, 200, 300],
            'sales': [-200, 0, 1200]  # Invalid, invalid, valid
        })

        cleaned = clean_sales_data(df)

        assert cleaned['sales'].iloc[0] == 200  # Recalculated
        assert cleaned['sales'].iloc[1] == 600  # Recalculated
        assert cleaned['sales'].iloc[2] == 1200  # Kept original

    def test_essential_rows_dropped(self):
        """Test rows with missing essential data are removed."""
        df = pd.DataFrame({
            'product': ['A', None, 'C'],
            'quantity': [1, 2, 3],
            'price': [10, 20, 30],
            'sales': [10, 40, 90]
        })

        cleaned = clean_sales_data(df)

        # Row with null product should be removed
        assert len(cleaned) == 2
        assert 'A' in cleaned['product'].values
        assert 'C' in cleaned['product'].values


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
