"""
Test suite for sales analysis functionality.
"""

import pytest
import pandas as pd
from src.analysis import analyze_sales_data


class TestSalesAnalysis:
    """Test analytical calculations."""

    @pytest.fixture
    def sample_data(self):
        """Create sample sales data for testing."""
        return pd.DataFrame({
            'product': ['Laptop', 'Mouse', 'Laptop', 'Keyboard'],
            'category': ['Electronics', 'Electronics', 'Electronics', 'Electronics'],
            'city': ['Delhi', 'Mumbai', 'Delhi', 'Mumbai'],
            'quantity': [2, 10, 1, 5],
            'price': [50000, 500, 55000, 1200],
            'sales': [100000, 5000, 55000, 6000],
            'order_date': pd.to_datetime(['2026-01-15', '2026-01-20', '2026-02-10', '2026-02-15'])
        })

    def test_total_sales(self, sample_data):
        """Test total sales calculation."""
        results = analyze_sales_data(sample_data)

        expected_total = 100000 + 5000 + 55000 + 6000
        assert results['total_sales'] == expected_total

    def test_average_sales(self, sample_data):
        """Test average sales calculation."""
        results = analyze_sales_data(sample_data)

        expected_avg = (100000 + 5000 + 55000 + 6000) / 4
        assert results['average_sales'] == expected_avg

    def test_total_quantity(self, sample_data):
        """Test total quantity calculation."""
        results = analyze_sales_data(sample_data)

        expected_qty = 2 + 10 + 1 + 5
        assert results['total_quantity'] == expected_qty

    def test_product_sales(self, sample_data):
        """Test product-wise sales aggregation."""
        results = analyze_sales_data(sample_data)

        assert 'Laptop' in results['product_sales']
        assert 'Mouse' in results['product_sales']
        assert 'Keyboard' in results['product_sales']

        # Laptop appears twice
        assert results['product_sales']['Laptop'] == 155000
        assert results['product_sales']['Mouse'] == 5000

    def test_best_product(self, sample_data):
        """Test best-performing product identification."""
        results = analyze_sales_data(sample_data)

        assert results['best_product'] == 'Laptop'

    def test_city_sales(self, sample_data):
        """Test city-wise sales aggregation."""
        results = analyze_sales_data(sample_data)

        assert 'Delhi' in results['city_sales']
        assert 'Mumbai' in results['city_sales']

        assert results['city_sales']['Delhi'] == 155000
        assert results['city_sales']['Mumbai'] == 11000

    def test_top_city(self, sample_data):
        """Test top city identification."""
        results = analyze_sales_data(sample_data)

        assert results['top_city'] == 'Delhi'

    def test_category_sales(self, sample_data):
        """Test category-wise sales aggregation."""
        results = analyze_sales_data(sample_data)

        assert 'Electronics' in results['category_sales']
        assert results['category_sales']['Electronics'] == 166000

    def test_monthly_sales(self, sample_data):
        """Test monthly sales trend."""
        results = analyze_sales_data(sample_data)

        assert '2026-01' in results['monthly_sales']
        assert '2026-02' in results['monthly_sales']

        assert results['monthly_sales']['2026-01'] == 105000
        assert results['monthly_sales']['2026-02'] == 61000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
