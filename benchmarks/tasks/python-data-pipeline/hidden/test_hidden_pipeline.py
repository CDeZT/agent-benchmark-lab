"""
Hidden test suite for the data processing pipeline.

Tests edge cases, performance, and robustness that the agent
must handle correctly. These tests use data that is NOT in the
workspace directory to ensure the solution generalizes.

Environment variables:
    AGENT_BENCH_WORKSPACE: Path to the workspace directory containing pipeline.py
"""

import os
import sys
import time
import tempfile
import pandas as pd
import numpy as np

# Get workspace path from environment
workspace = os.environ.get('AGENT_BENCH_WORKSPACE', os.path.dirname(os.path.abspath(__file__)))
if workspace not in sys.path:
    sys.path.insert(0, workspace)

from pipeline import (
    load_csv,
    clean_data,
    detect_outliers,
    transform_features,
    aggregate_metrics,
    run_pipeline,
    DataPipeline,
)


def get_hidden_data_path(filename):
    """Get the path to a hidden test data file."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_data', filename)


# === Edge Case Tests ===

def test_empty_csv_header_only():
    """Pipeline should handle a CSV with headers but no data rows."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("id,name,value\n")
        f.flush()
        try:
            df = load_csv(f.name)
            assert isinstance(df, pd.DataFrame), "Should return DataFrame for header-only CSV"
            assert len(df) == 0, "Should have 0 rows"
            assert set(df.columns) == {'id', 'name', 'value'}, "Should preserve all columns"

            # clean_data should handle empty DataFrame
            cleaned = clean_data(df)
            assert len(cleaned) == 0, "Cleaning empty DataFrame should return empty DataFrame"

            # detect_outliers should handle empty DataFrame
            outliers = detect_outliers(df, columns=['value'])
            assert len(outliers) == 0, "Outlier detection on empty DataFrame should return empty"
        finally:
            os.unlink(f.name)


def test_all_null_column():
    """Pipeline should handle columns where every value is NaN."""
    df = pd.DataFrame({
        'a': [1, 2, 3, 4, 5],
        'b': [np.nan, np.nan, np.nan, np.nan, np.nan],
        'c': ['x', 'y', 'z', 'x', 'y'],
    })

    cleaned = clean_data(df)
    # Column 'b' should be handled, not cause a crash
    assert len(cleaned) > 0, "Should not lose all rows due to all-null column"

    # Transform should handle all-null column
    result = transform_features(cleaned, numeric_cols=['a', 'b'])
    assert 'a_normalized' in result.columns, "Should normalize non-null column"
    assert 'b_normalized' in result.columns, "Should handle all-null column"


def test_single_row():
    """Pipeline should work with a single data row."""
    df = pd.DataFrame({
        'x': [5.0],
        'category': ['A'],
    })

    # clean_data should not crash
    cleaned = clean_data(df)
    assert len(cleaned) >= 0, "Single row should be handled"

    # detect_outliers should not crash (too few points)
    outliers = detect_outliers(df, columns=['x'])
    assert isinstance(outliers, pd.DataFrame), "Should return DataFrame for single row"

    # transform_features should handle single row
    result = transform_features(df, numeric_cols=['x'])
    assert 'x_normalized' in result.columns, "Should normalize single row"


def test_unicode_data():
    """Pipeline should handle Unicode characters in data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write("id,product,region\n")
        f.write("1,Électronique,Nord\n")       # French
        f.write("2,Übertüber,Süd\n")  # German
        f.write("3,電子商品,東京\n")  # CJK
        f.write("4,Техника,Москва\n")  # Cyrillic
        f.flush()
        try:
            df = load_csv(f.name)
            assert len(df) == 4, f"Should load all 4 rows, got {len(df)}"
            assert '電子商品' in df['product'].values, "Should preserve CJK characters"
        finally:
            os.unlink(f.name)


def test_malformed_csv():
    """Pipeline should handle malformed CSV lines gracefully."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("id,name,value\n")
        f.write("1,good,10\n")
        f.write("2,extra,cols,here\n")  # Extra columns
        f.write("3,good,30\n")
        f.flush()
        try:
            # Should not raise an exception
            df = load_csv(f.name)
            assert isinstance(df, pd.DataFrame), "Should return DataFrame for malformed CSV"
            # Should at least load the well-formed rows
            assert len(df) >= 2, "Should load at least the well-formed rows"
        finally:
            os.unlink(f.name)


# === Outlier Detection Edge Cases ===

def test_no_outliers():
    """Should correctly report zero outliers in uniform data."""
    df = pd.DataFrame({'x': [10.0] * 100})
    outliers = detect_outliers(df, columns=['x'])
    # With IQR=0, handling constant data should not flag everything as outlier
    outlier_count = outliers['x'].sum()
    assert outlier_count == 0, f"Constant data should have 0 outliers, got {outlier_count}"


def test_all_outliers():
    """Should handle data where many points are outliers."""
    # Data with a clear cluster and extreme outliers
    # Most values around 10, but some are 100x larger
    df = pd.DataFrame({'x': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 500, 1000]})
    outliers = detect_outliers(df, columns=['x'])
    # Should detect the extreme values
    assert outliers['x'].sum() > 0, "Should detect outliers in data with extreme values"


# === Normalization Edge Cases ===

def test_constant_column_normalization():
    """Normalization of a constant column should not produce NaN or inf."""
    df = pd.DataFrame({'x': [5.0, 5.0, 5.0, 5.0, 5.0]})
    result = transform_features(df, numeric_cols=['x'])
    assert 'x_normalized' in result.columns, "Should create normalized column"
    # Should not contain NaN or inf
    assert not result['x_normalized'].isna().any(), "Constant column normalization should not produce NaN"
    assert not np.isinf(result['x_normalized']).any(), "Constant column normalization should not produce inf"


def test_single_value_column():
    """Normalization with a single numeric value should not crash."""
    df = pd.DataFrame({'x': [42.0]})
    result = transform_features(df, numeric_cols=['x'])
    assert 'x_normalized' in result.columns


# === Aggregation Edge Cases ===

def test_aggregate_single_group():
    """Aggregation with only one group should work."""
    df = pd.DataFrame({
        'group': ['A', 'A', 'A'],
        'value': [10, 20, 30],
    })
    result = aggregate_metrics(df, 'group', ['value'])
    assert len(result) == 1, "Should have exactly one group"
    assert 'A' in result.index, "Group A should exist"
    assert result.loc['A', ('value', 'mean')] == 20.0, "Mean should be 20"


def test_aggregate_many_small_groups():
    """Aggregation with many groups of size 1 should work."""
    df = pd.DataFrame({
        'group': [f'G{i}' for i in range(100)],
        'value': range(100),
    })
    result = aggregate_metrics(df, 'group', ['value'])
    assert len(result) == 100, "Should have 100 groups"
    # std should be NaN for single-element groups
    assert result[('value', 'std')].isna().all(), "Single-element groups should have NaN std"


def test_aggregate_with_nan_values():
    """Aggregation should handle NaN values in metric columns."""
    df = pd.DataFrame({
        'group': ['A', 'A', 'B', 'B'],
        'value': [10, np.nan, 30, 40],
    })
    result = aggregate_metrics(df, 'group', ['value'])
    assert result.loc['A', ('value', 'mean')] == 10.0, "Mean should ignore NaN"
    assert result.loc['A', ('value', 'count')] == 1, "Count should count non-null"


# === Performance Test ===

def test_large_dataset_performance():
    """Pipeline should process 10,000 rows within reasonable time."""
    np.random.seed(42)
    n = 10000
    df = pd.DataFrame({
        'id': range(n),
        'category': np.random.choice(['A', 'B', 'C', 'D', 'E'], n),
        'value1': np.random.randn(n) * 100,
        'value2': np.random.randn(n) * 50 + 200,
        'value3': np.random.exponential(10, n),
    })

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f.name, index=False)
        try:
            start = time.time()
            result = run_pipeline(f.name)
            elapsed = time.time() - start

            assert elapsed < 30.0, f"Pipeline too slow: {elapsed:.2f}s for {n} rows (limit: 30s)"
            assert result['data'] is not None, "Should return cleaned data"
            assert len(result['data']) > 0, "Should have cleaned rows"
        finally:
            os.unlink(f.name)


# === DataPipeline Class Edge Cases ===

def test_pipeline_transform_before_fit():
    """Transform before fit should raise RuntimeError."""
    pipe = DataPipeline()
    df = pd.DataFrame({'x': [1, 2, 3]})
    try:
        pipe.transform(df)
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass  # Expected


def test_pipeline_with_unknown_categories():
    """Pipeline should handle unknown categories at transform time."""
    train = pd.DataFrame({
        'cat': ['A', 'B', 'A', 'B'],
        'x': [1.0, 2.0, 3.0, 4.0],
    })
    test = pd.DataFrame({
        'cat': ['A', 'C', 'D'],  # C and D are unknown
        'x': [5.0, 6.0, 7.0],
    })

    pipe = DataPipeline()
    pipe.fit(train, numeric_cols=['x'], categorical_cols=['cat'])
    result = pipe.transform(test)

    assert 'cat_A' in result.columns, "Should have cat_A column"
    assert 'cat_B' in result.columns, "Should have cat_B column"
    assert 'cat_other' in result.columns, "Should have cat_other column"
    assert result['cat_other'].iloc[1] == 1, "Unknown 'C' should be marked as other"
    assert result['cat_other'].iloc[2] == 1, "Unknown 'D' should be marked as other"
    assert result['cat_other'].iloc[0] == 0, "Known 'A' should not be other"


def test_pipeline_constant_numeric_column():
    """Pipeline fit_transform with constant numeric column should not crash."""
    df = pd.DataFrame({
        'x': [5.0, 5.0, 5.0],
        'cat': ['A', 'B', 'A'],
    })

    pipe = DataPipeline()
    result = pipe.fit_transform(df, numeric_cols=['x'], categorical_cols=['cat'])

    assert 'x_normalized' in result.columns
    assert not result['x_normalized'].isna().any(), "Should not produce NaN for constant column"


# === Integration: Hidden Data ===

def test_hidden_edge_case_data():
    """Test with the hidden edge_cases.csv file."""
    path = get_hidden_data_path('edge_cases.csv')
    if not os.path.exists(path):
        print("  SKIP: edge_cases.csv not found")
        return

    # Should not crash
    df = load_csv(path)
    assert isinstance(df, pd.DataFrame), "Should load edge case data"

    # If there's data, clean and transform should work
    if len(df) > 0:
        cleaned = clean_data(df)
        assert isinstance(cleaned, pd.DataFrame)


# === Run All Tests ===

if __name__ == '__main__':
    tests = [
        test_empty_csv_header_only,
        test_all_null_column,
        test_single_row,
        test_unicode_data,
        test_malformed_csv,
        test_no_outliers,
        test_all_outliers,
        test_constant_column_normalization,
        test_single_value_column,
        test_aggregate_single_group,
        test_aggregate_many_small_groups,
        test_aggregate_with_nan_values,
        test_large_dataset_performance,
        test_pipeline_transform_before_fit,
        test_pipeline_with_unknown_categories,
        test_pipeline_constant_numeric_column,
        test_hidden_edge_case_data,
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
