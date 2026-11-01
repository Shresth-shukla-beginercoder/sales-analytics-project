"""
Application Configuration
Loads settings from environment variables with fallback defaults.
"""

import os
import tempfile
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration class."""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()

    # File Upload Limits
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
    MAX_ROWS = int(os.environ.get('MAX_ROWS', 100000))  # 100K rows default

    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No time limit for CSRF tokens

    # Session Configuration
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False') == 'True'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 7200  # 2 hours in seconds

    # Allowed File Extensions
    ALLOWED_EXTENSIONS = {'csv', 'xlsx'}

    # Required Columns for Sales Data
    REQUIRED_COLUMNS = ['product', 'quantity', 'price']

    # Optional but recommended columns
    RECOMMENDED_COLUMNS = ['order_date', 'city', 'category', 'sales']

    # Directories
    UPLOAD_FOLDER = 'data/raw'
    CLEANED_FOLDER = 'data/cleaned'

    # DuckDB Configuration
    DUCKDB_BASE_DIR = os.environ.get(
        'DUCKDB_BASE_DIR',
        os.path.join(tempfile.gettempdir(), 'sales_analytics_dbs')
    )
    DUCKDB_TABLE_NAME = 'sales'

    # Session Management
    SESSION_MAX_AGE_HOURS = int(os.environ.get('SESSION_MAX_AGE_HOURS', 2))
    DATABASE_MAX_AGE_HOURS = int(os.environ.get('DATABASE_MAX_AGE_HOURS', 24))

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # Gemini API
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    # Primary model tried first
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-flash-latest')
    # Fallback models: tried in order when the primary is unavailable
    # (404/retired) or under load (503). Comma-separated env override.
    GEMINI_MODEL_FALLBACKS = [
        m.strip()
        for m in os.environ.get(
            'GEMINI_MODEL_FALLBACKS',
            'gemini-flash-latest,gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,'
            'gemini-3.5-flash,gemini-3.5-flash-lite,gemini-2.5-flash-lite,gemini-pro-latest'
        ).split(',')
        if m.strip()
    ]

    @staticmethod
    def validate():
        """Validate critical configuration."""
        if not Config.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set")

        # Create required directories
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.CLEANED_FOLDER, exist_ok=True)
        os.makedirs(Config.DUCKDB_BASE_DIR, exist_ok=True)
