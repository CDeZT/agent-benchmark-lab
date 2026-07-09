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
    Load a CSV file with robust error handling and type inference.

    Reads the CSV file at the given path with UTF-8 encoding (with fallback),
    attempts to parse date columns, and handles common CSV issues like
    mixed quoting styles and extra whitespace.

    Args:
        filepath: Path to the CSV file.

    Returns:
        DataFrame with inferred column types. Date-like columns are parsed
        as datetime, numeric columns as int/float, and the rest as strings.

    Raises:
        FileNotFoundError: If the file does not exist.
        pd.errors.EmptyDataError: If the file is completely empty (no headers).
    """
    try:
        df = pd.read_csv(
            filepath,
            encoding='utf-8',
            parse_dates=False,  # We'll handle date parsing manually for robustness
            skipinitialspace=True,  # Handle spaces after commas
            on_bad_lines='warn',  # Warn on malformed lines instead of crashing
        )
    except UnicodeDecodeError:
        # Fallback to latin-1 for files with non-UTF-8 characters
        df = pd.read_csv(
            filepath,
            encoding='latin-1',
            parse_dates=False,
            skipinitialspace=True,
            on_bad_lines='warn',
        )
    except pd.errors.ParserError:
        # Fallback for severe CSV issues (unclosed quotes, etc.)
        # Use Python engine which is more lenient
        try:
            df = pd.read_csv(
                filepath,
                encoding='utf-8',
                parse_dates=False,
                skipinitialspace=True,
                on_bad_lines='warn',
                engine='python',
            )
        except pd.errors.ParserError:
            df = pd.read_csv(
                filepath,
                encoding='latin-1',
                parse_dates=False,
                skipinitialspace=True,
                on_bad_lines='skip',
                engine='python',
            )

    if df.empty and len(df.columns) > 0:
        # Header-only file: return empty DataFrame with correct columns
        return df

    # Attempt to parse date columns
    for col in df.columns:
        if df[col].dtype == object:
            # Try to parse as datetime
            try:
                parsed = pd.to_datetime(df[col], format='mixed', errors='coerce')
                # Only convert if at least 50% of non-null values parsed successfully
                non_null = df[col].notna().sum()
                if non_null > 0 and parsed.notna().sum() / non_null >= 0.5:
                    df[col] = parsed
            except (ValueError, TypeError):
                pass

    # Attempt numeric conversion for remaining object columns
    for col in df.columns:
        if df[col].dtype == object:
            try:
                numeric = pd.to_numeric(df[col], errors='coerce')
                # Only convert if at least 50% of non-null values are numeric
                non_null = df[col].notna().sum()
                if non_null > 0 and numeric.notna().sum() / non_null >= 0.5:
                    df[col] = numeric
            except (ValueError, TypeError):
                pass

    # Strip whitespace from string columns
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].str.strip() if hasattr(df[col], 'str') else df[col]

    return df


def clean_data(df: pd.DataFrame, strategy: str = 'median') -> pd.DataFrame:
    """
    Clean a DataFrame by handling missing values, duplicates, and type issues.

    Applies the following cleaning steps in order:
    1. Remove duplicate rows (keeping first occurrence)
    2. Fill missing numeric values using the specified strategy
    3. Drop rows where critical categorical columns are missing
    4. Remove rows with obviously invalid data (e.g., negative quantities)
    5. Coerce mixed-type columns to consistent types

    Args:
        df: Input DataFrame to clean.
        strategy: How to fill missing numeric values.
            - 'mean': fill with column mean
            - 'median': fill with column median (default, robust to outliers)
            - 'mode': fill with column mode
            - 'drop': drop rows with any NaN

    Returns:
        Cleaned DataFrame with reset index.

    Examples:
        >>> df = pd.DataFrame({'x': [1, np.nan, 3], 'y': [4, 5, 6]})
        >>> cleaned = clean_data(df, strategy='median')
        >>> cleaned['x'].isna().sum()
        0
    """
    result = df.copy()

    # Step 1: Remove duplicate rows
    result = result.drop_duplicates()

    # Step 2: Handle missing values based on strategy
    if strategy == 'drop':
        result = result.dropna()
    else:
        # Separate numeric and non-numeric columns
        numeric_cols = result.select_dtypes(include=[np.number]).columns.tolist()
        non_numeric_cols = result.select_dtypes(exclude=[np.number]).columns.tolist()

        # Fill numeric columns
        for col in numeric_cols:
            if result[col].isna().any():
                if strategy == 'mean':
                    fill_value = result[col].mean()
                elif strategy == 'median':
                    fill_value = result[col].median()
                elif strategy == 'mode':
                    mode_vals = result[col].mode()
                    fill_value = mode_vals[0] if len(mode_vals) > 0 else 0
                else:
                    fill_value = result[col].median()
                result[col] = result[col].fillna(fill_value)

        # For non-numeric columns, fill with mode or 'unknown'
        for col in non_numeric_cols:
            if result[col].isna().any():
                mode_vals = result[col].mode()
                fill_value = mode_vals[0] if len(mode_vals) > 0 else 'unknown'
                result[col] = result[col].fillna(fill_value)

    # Step 3: Remove rows with negative quantities (if applicable)
    if 'quantity' in result.columns:
        result = result[result['quantity'] >= 0]

    # Step 4: Coerce mixed-type numeric columns
    for col in result.columns:
        if result[col].dtype == object:
            # Try to convert to numeric, keeping as-is if it fails for most values
            numeric = pd.to_numeric(result[col], errors='coerce')
            non_null_count = result[col].notna().sum()
            if non_null_count > 0 and numeric.notna().sum() / non_null_count > 0.8:
                result[col] = numeric

    # Reset index after all filtering
    result = result.reset_index(drop=True)

    return result


def detect_outliers(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    multiplier: float = 1.5
) -> pd.DataFrame:
    """
    Detect outliers using the Interquartile Range (IQR) method.

    The IQR method is robust to skewed data and doesn't assume a normal
    distribution. For each specified numeric column:
    1. Calculate Q1 (25th percentile) and Q3 (75th percentile)
    2. Compute IQR = Q3 - Q1
    3. Define bounds: [Q1 - multiplier*IQR, Q3 + multiplier*IQR]
    4. Mark values outside these bounds as outliers

    The standard multiplier of 1.5 identifies "mild" outliers.
    A multiplier of 3.0 identifies "extreme" outliers.

    Args:
        df: Input DataFrame.
        columns: List of column names to check. If None, uses all numeric columns.
        multiplier: IQR multiplier for outlier bounds (default 1.5).

    Returns:
        Boolean DataFrame where True indicates an outlier. Same shape as
        df[columns]. NaN values in the input are preserved as NaN in the output
        (not flagged as outliers).

    Examples:
        >>> df = pd.DataFrame({'x': [1, 2, 3, 4, 100]})
        >>> outliers = detect_outliers(df, columns=['x'])
        >>> outliers['x'].iloc[-1]
        True
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    # Filter to only columns that exist and are numeric
    valid_columns = [c for c in columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]

    outlier_mask = pd.DataFrame(False, index=df.index, columns=valid_columns)

    for col in valid_columns:
        values = df[col].dropna()
        if len(values) < 4:
            # Need at least 4 points for meaningful quartile calculation
            continue

        # Use actual quartiles (percentiles), not mean-based approximation
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            # All values in the middle 50% are the same
            # Fall back to detecting values that differ from the median
            median = values.median()
            # Only flag if there are actual differences
            if (values != median).any():
                outlier_mask[col] = (df[col] != median) & df[col].notna()
            continue

        lower_bound = q1 - multiplier * iqr
        upper_bound = q3 + multiplier * iqr

        outlier_mask[col] = ((df[col] < lower_bound) | (df[col] > upper_bound)) & df[col].notna()

    return outlier_mask


def transform_features(
    df: pd.DataFrame,
    numeric_cols: Optional[List[str]] = None,
    categorical_cols: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Transform features by normalizing numeric columns and encoding categorical.

    Numeric transformation (Z-score normalization):
        normalized = (x - mean) / std
    For constant columns (std=0), the normalized value is set to 0.

    Categorical transformation:
        One-hot encoding creates binary indicator columns for each unique value.
        NaN values produce all-zeros in the encoded columns.

    Args:
        df: Input DataFrame.
        numeric_cols: Columns to normalize. If None, auto-detects numeric columns.
        categorical_cols: Columns to one-hot encode. If None, auto-detects object columns.

    Returns:
        Transformed DataFrame with original columns plus new feature columns.
        New columns follow the naming pattern: {col}_normalized for numeric,
        {col}_{value} for categorical.

    Examples:
        >>> df = pd.DataFrame({'x': [1, 2, 3], 'cat': ['a', 'b', 'a']})
        >>> result = transform_features(df)
        >>> 'x_normalized' in result.columns
        True
        >>> 'cat_a' in result.columns
        True
    """
    result = df.copy()

    if numeric_cols is None:
        numeric_cols = result.select_dtypes(include=[np.number]).columns.tolist()
    if categorical_cols is None:
        categorical_cols = result.select_dtypes(include=['object', 'category']).columns.tolist()

    # Z-score normalization for numeric columns
    for col in numeric_cols:
        if col not in result.columns:
            continue
        mean_val = result[col].mean()
        std_val = result[col].std()

        if pd.isna(std_val) or std_val == 0:
            # Constant column or all NaN: normalized value is 0
            result[f'{col}_normalized'] = 0.0
        else:
            result[f'{col}_normalized'] = (result[col] - mean_val) / std_val

    # One-hot encoding for categorical columns
    for col in categorical_cols:
        if col not in result.columns:
            continue
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
    - mean: average value (ignores NaN)
    - sum: total value (ignores NaN)
    - count: number of non-null observations
    - std: standard deviation (NaN for groups with < 2 values)

    Args:
        df: Input DataFrame.
        group_col: Column to group by.
        metric_cols: Columns to compute statistics for.

    Returns:
        DataFrame with one row per group and multi-level column index.
        Each metric column gets four sub-columns: mean, sum, count, std.

    Raises:
        KeyError: If group_col or metric_cols not in DataFrame.

    Examples:
        >>> df = pd.DataFrame({'g': ['A','A','B'], 'v': [1, 2, 3]})
        >>> result = aggregate_metrics(df, 'g', ['v'])
        >>> result.loc['A', ('v', 'mean')]
        1.5
    """
    if group_col not in df.columns:
        raise KeyError(f"Group column '{group_col}' not found in DataFrame")

    missing = [c for c in metric_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Metric columns not found: {missing}")

    # Filter to only numeric metric columns
    numeric_metrics = [c for c in metric_cols if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_metrics:
        # Return empty result with correct structure
        return pd.DataFrame()

    # Handle empty DataFrame
    if df.empty:
        idx = pd.Index([], name=group_col)
        cols = pd.MultiIndex.from_product([numeric_metrics, ['mean', 'sum', 'count', 'std']])
        return pd.DataFrame(index=idx, columns=cols)

    result = df.groupby(group_col, observed=True)[numeric_metrics].agg(
        ['mean', 'sum', 'count', 'std']
    )

    return result


def run_pipeline(csv_path: str) -> Dict[str, Any]:
    """
    Execute the full data processing pipeline.

    Orchestrates the data processing steps in the correct order:
    1. Load data from CSV with error handling
    2. Clean the data (fill NaN, remove duplicates, fix types)
    3. Detect outliers on numeric columns
    4. Transform features (normalize + encode)
    5. Aggregate by region (if present)

    Args:
        csv_path: Path to the input CSV file.

    Returns:
        Dictionary containing:
        - 'data': cleaned DataFrame
        - 'outliers': boolean outlier mask DataFrame
        - 'transformed': DataFrame with normalized/encoded features
        - 'aggregated': DataFrame with group statistics (or None)
        - 'summary': dict with basic pipeline stats

    Examples:
        >>> result = run_pipeline('data/sales.csv')
        >>> 'data' in result
        True
    """
    # Step 1: Load
    df = load_csv(csv_path)

    # Handle empty DataFrame
    if df.empty:
        return {
            'data': df,
            'outliers': pd.DataFrame(),
            'transformed': df,
            'aggregated': None,
            'summary': {'rows_loaded': 0, 'rows_cleaned': 0},
        }

    # Step 2: Clean
    cleaned = clean_data(df)

    # Step 3: Detect outliers on numeric columns
    numeric_cols = cleaned.select_dtypes(include=[np.number]).columns.tolist()
    # Exclude id-like columns from outlier detection
    outlier_cols = [c for c in numeric_cols if not c.startswith('id')]
    outliers = detect_outliers(cleaned, columns=outlier_cols)

    # Step 4: Transform
    transformed = transform_features(cleaned)

    # Step 5: Aggregate by region if it exists
    agg_result = None
    if 'region' in cleaned.columns:
        metric_cols = [c for c in numeric_cols if c not in ('id',)]
        if metric_cols:
            agg_result = aggregate_metrics(cleaned, 'region', metric_cols)

    summary = {
        'rows_loaded': len(df),
        'rows_cleaned': len(cleaned),
        'outlier_count': int(outliers.sum().sum()),
        'columns_transformed': len(transformed.columns),
    }

    return {
        'data': cleaned,
        'outliers': outliers,
        'transformed': transformed,
        'aggregated': agg_result,
        'summary': summary,
    }


class DataPipeline:
    """
    A pipeline class that follows the fit/transform pattern.

    Similar to scikit-learn transformers, this class learns parameters
    from training data (fit) and applies transformations to new data (transform).
    This ensures consistent feature engineering between training and inference.

    The pipeline supports:
    - Z-score normalization with learned mean/std
    - One-hot encoding with fixed category vocabulary
    - Handling of unknown categories at transform time

    Attributes:
        numeric_stats: Learned mean/std for each numeric column.
        categories: Known categories for each categorical column.
        fitted: Whether fit() has been called.

    Examples:
        >>> pipe = DataPipeline()
        >>> train = pd.DataFrame({'x': [1,2,3], 'cat': ['a','b','a']})
        >>> pipe.fit(train, numeric_cols=['x'], categorical_cols=['cat'])
        >>> test = pd.DataFrame({'x': [4], 'cat': ['a']})
        >>> result = pipe.transform(test)
    """

    def __init__(self):
        """Initialize an unfitted pipeline."""
        self.numeric_stats: Dict[str, Dict[str, float]] = {}
        self.categories: Dict[str, List[str]] = {}
        self.fitted: bool = False

    def fit(self, df: pd.DataFrame, numeric_cols: Optional[List[str]] = None,
            categorical_cols: Optional[List[str]] = None) -> 'DataPipeline':
        """
        Learn transformation parameters from the training data.

        For numeric columns: computes and stores mean and std.
        For categorical columns: stores the list of unique values.

        Args:
            df: Training DataFrame.
            numeric_cols: Numeric columns to learn parameters for.
                If None, auto-detects numeric columns.
            categorical_cols: Categorical columns to learn parameters for.
                If None, auto-detects object/category columns.

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
                    'mean': float(df[col].mean()) if not pd.isna(df[col].mean()) else 0.0,
                    'std': float(df[col].std()) if not pd.isna(df[col].std()) else 0.0,
                }

        for col in categorical_cols:
            if col in df.columns:
                self.categories[col] = sorted(df[col].dropna().unique().tolist())

        self.fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply learned transformations to new data.

        Uses the statistics learned during fit() to normalize numeric columns
        and create one-hot encoded columns for categorical features. Unknown
        categories at transform time are captured in an '{col}_other' column.

        Args:
            df: DataFrame to transform.

        Returns:
            Transformed DataFrame with new feature columns added.

        Raises:
            RuntimeError: If fit() has not been called yet.
        """
        if not self.fitted:
            raise RuntimeError("Pipeline must be fitted before calling transform()")

        result = df.copy()

        # Normalize numeric columns using learned statistics
        for col, stats in self.numeric_stats.items():
            if col not in result.columns:
                continue
            mean_val = stats['mean']
            std_val = stats['std']
            if std_val == 0:
                result[f'{col}_normalized'] = 0.0
            else:
                result[f'{col}_normalized'] = (result[col] - mean_val) / std_val

        # One-hot encode categorical columns using learned categories
        for col, cats in self.categories.items():
            if col not in result.columns:
                continue
            # Create binary column for each known category
            for cat in cats:
                result[f'{col}_{cat}'] = (result[col] == cat).astype(int)
            # Handle unknown categories
            result[f'{col}_other'] = (
                (~result[col].isin(cats)) & result[col].notna()
            ).astype(int)

        return result

    def fit_transform(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        Fit to data, then transform it.

        Convenience method equivalent to fit(df, **kwargs).transform(df).

        Args:
            df: Training DataFrame.
            **kwargs: Additional arguments passed to fit() (numeric_cols, categorical_cols).

        Returns:
            Transformed DataFrame.
        """
        return self.fit(df, **kwargs).transform(df)
