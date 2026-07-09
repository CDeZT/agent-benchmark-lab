"""
Public test suite for the data processing pipeline.

Tests the core functionality of each pipeline function with
standard inputs. These tests verify basic correctness and
are safe to run during development.
"""

import os
import sys
import pandas as pd
import numpy as np

# Ensure the workspace directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import (
    load_csv,
    clean_data,
    detect_outliers,
    transform_features,
    aggregate_metrics,
    run_pipeline,
    DataPipeline,
)


def get_data_path(filename):
    """Get the path to a data file in the data directory."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', filename)


# --- load_csv tests ---

def test_load_csv_valid_file():
    """Test loading a valid CSV file."""
    path = get_data_path('sales.csv')
    df = load_csv(path)
    assert df is not None, "load_csv should return a DataFrame"
    assert isinstance(df, pd.DataFrame), "Result should be a pandas DataFrame"
    assert len(df) > 0, "DataFrame should have rows"
    assert 'id' in df.columns, "DataFrame should have 'id' column"
    assert 'product' in df.columns, "DataFrame should have 'product' column"


def test_load_csv_column_count():
    """Test that all expected columns are present."""
    path = get_data_path('sales.csv')
    df = load_csv(path)
    expected_cols = ['id', 'date', 'product', 'quantity', 'unit_price', 'customer_id', 'region']
    for col in expected_cols:
        assert col in df.columns, f"Missing column: {col}"


# --- clean_data tests ---

def test_clean_data_removes_duplicates():
    """Test that clean_data removes duplicate rows."""
    df = pd.DataFrame({
        'a': [1, 1, 2, 3],
        'b': ['x', 'x', 'y', 'z'],
    })
    cleaned = clean_data(df)
    assert len(cleaned) < len(df), "Should remove duplicate rows"


def test_clean_data_handles_missing_values():
    """Test that clean_data handles NaN values."""
    df = pd.DataFrame({
        'quantity': [1, np.nan, 3, 4],
        'price': [10.0, 20.0, np.nan, 40.0],
    })
    cleaned = clean_data(df)
    assert len(cleaned) > 0, "Should not remove all rows"
    # After cleaning, there should be no NaN in the result
    assert cleaned.isnull().sum().sum() == 0, "Cleaned data should have no NaN values"


def test_clean_data_removes_negative_quantities():
    """Test that rows with negative quantities are removed."""
    df = pd.DataFrame({
        'quantity': [5, -3, 10, -1],
        'price': [10.0, 20.0, 30.0, 40.0],
    })
    cleaned = clean_data(df)
    assert all(cleaned['quantity'] >= 0), "All quantities should be non-negative"


# --- detect_outliers tests ---

def test_detect_outliers_finds_obvious_outliers():
    """Test that detect_outliers identifies clear outliers."""
    df = pd.DataFrame({
        'value': [1, 2, 3, 4, 5, 100],  # 100 is an obvious outlier
    })
    outliers = detect_outliers(df, columns=['value'])
    assert outliers is not None, "Should return outlier mask"
    # 100 should be detected as an outlier
    assert outliers['value'].iloc[-1] == True, "100 should be detected as an outlier"
    # Normal values should not be outliers
    assert outliers['value'].iloc[0] == False, "1 should not be an outlier"


def test_detect_outliers_no_outliers():
    """Test with data that has no outliers."""
    df = pd.DataFrame({
        'value': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
    })
    outliers = detect_outliers(df, columns=['value'])
    assert outliers['value'].sum() == 0, "Should find no outliers in uniform data"


def test_detect_outliers_custom_multiplier():
    """Test that custom multiplier affects outlier detection."""
    df = pd.DataFrame({
        'value': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 50],
    })
    # With larger multiplier, fewer outliers
    outliers_strict = detect_outliers(df, columns=['value'], multiplier=1.0)
    outliers_relaxed = detect_outliers(df, columns=['value'], multiplier=3.0)
    assert outliers_strict['value'].sum() >= outliers_relaxed['value'].sum(), \
        "Stricter multiplier should find more or equal outliers"


# --- transform_features tests ---

def test_transform_features_normalization():
    """Test that numeric normalization produces z-scores."""
    df = pd.DataFrame({
        'x': [1, 2, 3, 4, 5],
        'y': [10, 20, 30, 40, 50],
    })
    result = transform_features(df, numeric_cols=['x', 'y'])
    assert 'x_normalized' in result.columns, "Should create x_normalized column"
    assert 'y_normalized' in result.columns, "Should create y_normalized column"
    # Z-score normalized data should have mean ~0
    assert abs(result['x_normalized'].mean()) < 1e-10, "Normalized x should have mean ~0"


def test_transform_features_one_hot_encoding():
    """Test that categorical columns are one-hot encoded."""
    df = pd.DataFrame({
        'category': ['A', 'B', 'A', 'C'],
        'value': [1, 2, 3, 4],
    })
    result = transform_features(df, numeric_cols=[], categorical_cols=['category'])
    assert 'category_A' in result.columns, "Should create category_A column"
    assert 'category_B' in result.columns, "Should create category_B column"
    assert 'category_C' in result.columns, "Should create category_C column"


# --- aggregate_metrics tests ---

def test_aggregate_metrics_basic():
    """Test basic groupby aggregation."""
    df = pd.DataFrame({
        'group': ['A', 'A', 'B', 'B'],
        'value': [10, 20, 30, 40],
    })
    result = aggregate_metrics(df, 'group', ['value'])
    assert result is not None, "Should return aggregation result"
    assert 'A' in result.index, "Should have group A"
    assert 'B' in result.index, "Should have group B"
    # Check that A mean is 15
    assert result.loc['A', ('value', 'mean')] == 15.0, "Group A mean should be 15"


def test_aggregate_metrics_multiple_columns():
    """Test aggregation on multiple metric columns."""
    df = pd.DataFrame({
        'region': ['N', 'N', 'S', 'S'],
        'sales': [100, 200, 150, 250],
        'quantity': [10, 20, 15, 25],
    })
    result = aggregate_metrics(df, 'region', ['sales', 'quantity'])
    assert ('sales', 'mean') in result.columns, "Should have sales mean"
    assert ('quantity', 'sum') in result.columns, "Should have quantity sum"


# --- Integration tests ---

def test_run_pipeline():
    """Test the full pipeline execution."""
    path = get_data_path('sales.csv')
    result = run_pipeline(path)

    assert 'data' in result, "Result should contain 'data'"
    assert 'outliers' in result, "Result should contain 'outliers'"
    assert 'transformed' in result, "Result should contain 'transformed'"
    assert 'aggregated' in result, "Result should contain 'aggregated'"

    assert isinstance(result['data'], pd.DataFrame), "data should be a DataFrame"
    assert len(result['data']) > 0, "Pipeline should produce non-empty output"


def test_data_pipeline_fit_transform():
    """Test the DataPipeline class."""
    df = pd.DataFrame({
        'x': [1.0, 2.0, 3.0, 4.0, 5.0],
        'category': ['A', 'B', 'A', 'B', 'A'],
    })

    pipeline = DataPipeline()
    result = pipeline.fit_transform(df, numeric_cols=['x'], categorical_cols=['category'])

    assert pipeline.fitted, "Pipeline should be fitted after fit_transform"
    assert 'x_normalized' in result.columns, "Should create normalized column"
    assert 'category_A' in result.columns, "Should create one-hot columns"


def test_data_pipeline_transform_new_data():
    """Test transforming new data with fitted pipeline."""
    train = pd.DataFrame({
        'x': [1.0, 2.0, 3.0, 4.0, 5.0],
        'category': ['A', 'B', 'A', 'B', 'A'],
    })
    test = pd.DataFrame({
        'x': [6.0, 7.0],
        'category': ['A', 'C'],  # C is unknown
    })

    pipeline = DataPipeline()
    pipeline.fit(train, numeric_cols=['x'], categorical_cols=['category'])
    result = pipeline.transform(test)

    assert 'x_normalized' in result.columns, "Should normalize test data"
    assert 'category_other' in result.columns, "Should handle unknown categories"
    # 'C' should be marked as 'other'
    assert result['category_other'].iloc[1] == 1, "Unknown category should be marked as other"


# --- Run all tests ---

if __name__ == '__main__':
    tests = [
        test_load_csv_valid_file,
        test_load_csv_column_count,
        test_clean_data_removes_duplicates,
        test_clean_data_handles_missing_values,
        test_clean_data_removes_negative_quantities,
        test_detect_outliers_finds_obvious_outliers,
        test_detect_outliers_no_outliers,
        test_detect_outliers_custom_multiplier,
        test_transform_features_normalization,
        test_transform_features_one_hot_encoding,
        test_aggregate_metrics_basic,
        test_aggregate_metrics_multiple_columns,
        test_run_pipeline,
        test_data_pipeline_fit_transform,
        test_data_pipeline_transform_new_data,
    ]

    passed = 0
    failed = 0
    errors = 0

    for test_func in tests:
        try:
            test_func()
            print(f"  PASS: {test_func.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {test_func.__name__}: {type(e).__name__}: {e}")
            errors += 1

    total = passed + failed + errors
    print(f"\nResults: {passed}/{total} passed, {failed} failed, {errors} errors")
    sys.exit(0 if failed == 0 and errors == 0 else 1)
