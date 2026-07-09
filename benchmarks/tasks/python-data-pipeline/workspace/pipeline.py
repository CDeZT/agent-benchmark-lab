"""
Data Cleaning and Transformation Pipeline

This module provides a robust data processing pipeline for cleaning,
transforming, and aggregating tabular data. It handles common data
quality issues including missing values, duplicates, outliers, and
type inconsistencies.

Key concepts:
- Data cleaning: fixing or removing corrupt, duplicate, or incomplete records
- Outlier detection: identifying data points that deviate significantly from the norm
- Feature transformation: normalizing numeric data and encoding categorical variables
- Aggregation: computing summary statistics over grouped data

Dependencies:
    pandas >= 1.3.0
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd
import numpy as np


def load_csv(filepath: str) -> pd.DataFrame:
    """
    Load a CSV file and perform basic type inference.

    Reads the CSV file at the given path and attempts to parse dates
    and numeric columns automatically. Returns a pandas DataFrame.

    Args:
        filepath: Path to the CSV file.

    Returns:
        DataFrame with inferred column types.

    Raises:
        FileNotFoundError: If the file does not exist.
        pd.errors.EmptyDataError: If the file is empty.
    """
    # BUG: No encoding parameter specified - will fail on Unicode files
    # BUG: No error handling for malformed CSV
    df = pd.read_csv(filepath, parse_dates=True)
    return df


def clean_data(df: pd.DataFrame, strategy: str = 'median') -> pd.DataFrame:
    """
    Clean a DataFrame by handling missing values, duplicates, and type issues.

    Applies the following cleaning steps:
    1. Remove duplicate rows
    2. Handle missing values using the specified strategy
    3. Remove rows with obviously invalid data (e.g., negative quantities)

    Args:
        df: Input DataFrame to clean.
        strategy: How to fill missing numeric values.
            Options: 'mean', 'median', 'mode', 'drop'.

    Returns:
        Cleaned DataFrame.
    """
    # Step 1: Remove duplicates
    df = df.drop_duplicates()

    # BUG: Just drops rows with any NaN instead of filling them
    # This loses too much data in real-world scenarios
    df = df.dropna()

    # Remove negative quantities if the column exists
    if 'quantity' in df.columns:
        df = df[df['quantity'] >= 0]

    return df


def detect_outliers(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    multiplier: float = 1.5
) -> pd.DataFrame:
    """
    Detect outliers using the Interquartile Range (IQR) method.

    For each specified numeric column, calculates Q1 (25th percentile)
    and Q3 (75th percentile). Data points outside the range
    [Q1 - multiplier*IQR, Q3 + multiplier*IQR] are marked as outliers.

    Args:
        df: Input DataFrame.
        columns: List of column names to check. If None, uses all numeric columns.
        multiplier: IQR multiplier for outlier bounds (default 1.5).

    Returns:
        Boolean DataFrame where True indicates an outlier.
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    outlier_mask = pd.DataFrame(False, index=df.index, columns=columns)

    for col in columns:
        if col not in df.columns:
            continue
        values = df[col].dropna()
        if len(values) == 0:
            continue

        # BUG: Using mean instead of median for quartile calculation
        # This makes the outlier detection incorrect
        q1 = values.mean() - 0.5 * values.std()
        q3 = values.mean() + 0.5 * values.std()
        iqr = q3 - q1

        lower_bound = q1 - multiplier * iqr
        upper_bound = q3 + multiplier * iqr

        outlier_mask[col] = (df[col] < lower_bound) | (df[col] > upper_bound)

    return outlier_mask


def transform_features(
    df: pd.DataFrame,
    numeric_cols: Optional[List[str]] = None,
    categorical_cols: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Transform features by normalizing numeric columns and encoding categorical.

    Applies Z-score normalization to numeric columns:
        normalized = (x - mean) / std

    Applies one-hot encoding to categorical columns, creating binary
    indicator columns for each unique value.

    Args:
        df: Input DataFrame.
        numeric_cols: Columns to normalize. If None, auto-detects numeric columns.
        categorical_cols: Columns to one-hot encode. If None, auto-detects object columns.

    Returns:
        Transformed DataFrame with new feature columns.
    """
    result = df.copy()

    if numeric_cols is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if categorical_cols is None:
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

    # Z-score normalization
    for col in numeric_cols:
        if col in result.columns:
            mean_val = result[col].mean()
            std_val = result[col].std()
            # BUG: Doesn't handle constant columns where std=0
            # Will produce NaN or inf values
            result[f'{col}_normalized'] = (result[col] - mean_val) / std_val

    # One-hot encoding
    for col in categorical_cols:
        if col in result.columns:
            dummies = pd.get_dummies(result[col], prefix=col, dummy_na=False)
            result = pd.concat([result, dummies], axis=1)

    return result


def aggregate_metrics(
    df: pd.DataFrame,
    group_col: str,
    metric_cols: List[str]
) -> pd.DataFrame:
    """
    Compute aggregate statistics grouped by a column.

    For each group, calculates:
    - mean: average value
    - sum: total value
    - count: number of observations
    - std: standard deviation

    Args:
        df: Input DataFrame.
        group_col: Column to group by.
        metric_cols: Columns to compute statistics for.

    Returns:
        DataFrame with one row per group and multi-level column index.

    Raises:
        KeyError: If group_col or metric_cols not in DataFrame.
    """
    # BUG: Doesn't handle empty groups or groups with single values
    # Will raise an error on edge cases
    result = df.groupby(group_col)[metric_cols].agg(['mean', 'sum', 'count', 'std'])
    return result


def run_pipeline(csv_path: str) -> Dict[str, Any]:
    """
    Execute the full data processing pipeline.

    Runs the following steps in order:
    1. Load data from CSV
    2. Clean the data
    3. Detect outliers
    4. Transform features
    5. Aggregate by region

    Args:
        csv_path: Path to the input CSV file.

    Returns:
        Dictionary containing:
        - 'data': cleaned DataFrame
        - 'outliers': outlier mask DataFrame
        - 'transformed': transformed DataFrame
        - 'aggregated': aggregated statistics
    """
    # Load
    df = load_csv(csv_path)

    # Clean
    cleaned = clean_data(df)

    # Detect outliers on numeric columns
    numeric_cols = cleaned.select_dtypes(include=[np.number]).columns.tolist()
    outliers = detect_outliers(cleaned, columns=numeric_cols)

    # Transform
    transformed = transform_features(cleaned)

    # Aggregate by region if it exists
    agg_result = None
    if 'region' in cleaned.columns:
        metric_cols = [c for c in numeric_cols if c != 'id']
        if metric_cols:
            agg_result = aggregate_metrics(cleaned, 'region', metric_cols)

    return {
        'data': cleaned,
        'outliers': outliers,
        'transformed': transformed,
        'aggregated': agg_result,
    }


class DataPipeline:
    """
    A pipeline class that follows the fit/transform pattern.

    Similar to scikit-learn transformers, this class learns parameters
    from training data (fit) and applies transformations to new data (transform).

    Attributes:
        numeric_stats: Dictionary of learned statistics for numeric columns.
        categories: Dictionary of known categories for categorical columns.
        fitted: Whether the pipeline has been fitted.
    """

    def __init__(self):
        self.numeric_stats: Dict[str, Dict[str, float]] = {}
        self.categories: Dict[str, List[str]] = {}
        self.fitted: bool = False

    def fit(self, df: pd.DataFrame, numeric_cols: Optional[List[str]] = None,
            categorical_cols: Optional[List[str]] = None) -> 'DataPipeline':
        """
        Learn transformation parameters from the training data.

        Computes mean and std for numeric columns, and unique values
        for categorical columns.

        Args:
            df: Training DataFrame.
            numeric_cols: Numeric columns to learn parameters for.
            categorical_cols: Categorical columns to learn parameters for.

        Returns:
            self, for method chaining.
        """
        if numeric_cols is None:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if categorical_cols is None:
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

        for col in numeric_cols:
            if col in df.columns:
                self.numeric_stats[col] = {
                    'mean': df[col].mean(),
                    'std': df[col].std(),
                }

        for col in categorical_cols:
            if col in df.columns:
                self.categories[col] = df[col].dropna().unique().tolist()

        self.fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply learned transformations to new data.

        Normalizes numeric columns using the learned mean/std, and
        one-hot encodes categorical columns using the learned categories.

        Args:
            df: DataFrame to transform.

        Returns:
            Transformed DataFrame.

        Raises:
            RuntimeError: If the pipeline has not been fitted.
        """
        if not self.fitted:
            raise RuntimeError("Pipeline must be fitted before transform")

        result = df.copy()

        # Normalize numeric columns using learned stats
        for col, stats in self.numeric_stats.items():
            if col in result.columns:
                mean_val = stats['mean']
                std_val = stats['std']
                # BUG: Same division by zero issue as transform_features
                result[f'{col}_normalized'] = (result[col] - mean_val) / std_val

        # One-hot encode using learned categories
        for col, cats in self.categories.items():
            if col in result.columns:
                for cat in cats:
                    result[f'{col}_{cat}'] = (result[col] == cat).astype(int)
                # Handle unknown categories
                result[f'{col}_other'] = (~result[col].isin(cats) & result[col].notna()).astype(int)

        return result

    def fit_transform(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        Fit to data, then transform it.

        Equivalent to calling fit(df, **kwargs) followed by transform(df).

        Args:
            df: Training DataFrame.
            **kwargs: Additional arguments passed to fit().

        Returns:
            Transformed DataFrame.
        """
        return self.fit(df, **kwargs).transform(df)
