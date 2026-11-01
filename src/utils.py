"""
Utility functions for file validation and sanitization.
"""

import os
from werkzeug.utils import secure_filename
from config.settings import Config


def allowed_file(filename):
    """
    Check if file extension is allowed.

    Args:
        filename (str): Name of the file to check

    Returns:
        bool: True if extension is allowed, False otherwise
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal attacks.

    Args:
        filename (str): Original filename

    Returns:
        str: Secure filename
    """
    return secure_filename(filename)


def validate_dataframe_size(df):
    """
    Validate DataFrame size constraints.

    Args:
        df (pd.DataFrame): DataFrame to validate

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    row_count = len(df)

    if row_count == 0:
        return False, "The uploaded file is empty. Please upload a file with data."

    if row_count > Config.MAX_ROWS:
        return False, f"The file contains {row_count:,} rows, which exceeds the maximum allowed {Config.MAX_ROWS:,} rows. Please reduce the dataset size."

    return True, None


def validate_required_columns(df):
    """
    Validate that DataFrame contains required columns.

    Args:
        df (pd.DataFrame): DataFrame to validate

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    # Normalize column names to lowercase for comparison
    df_columns = [col.strip().lower().replace(' ', '_') for col in df.columns]

    missing_columns = []
    for required_col in Config.REQUIRED_COLUMNS:
        if required_col.lower() not in df_columns:
            missing_columns.append(required_col)

    if missing_columns:
        return False, f"The uploaded file is missing required columns: {', '.join(missing_columns)}. Required columns are: {', '.join(Config.REQUIRED_COLUMNS)}."

    return True, None


def get_file_size_mb(file_path):
    """
    Get file size in megabytes.

    Args:
        file_path (str): Path to file

    Returns:
        float: File size in MB
    """
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)
