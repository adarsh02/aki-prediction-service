"""
Database connection utilities for the Hospital application.

This module provides a factory function for creating SQLite connections
with consistent configuration (row factory, foreign key enforcement).
"""

import logging
import sqlite3
from pathlib import Path
from datetime import datetime

sqlite3.register_adapter(
    datetime,
    lambda dt: dt.isoformat(sep=" ", timespec="seconds"),
)

logger = logging.getLogger(__name__)

# Absolute path to the database file
DB_PATH = Path("/state/hospital.db")


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """
    Create and return a new SQLite database connection.

    The returned connection:
    - Uses `sqlite3.Row` for dict-like access to rows
    - Enforces foreign key constraints

    Each caller is responsible for closing the connection.

    Returns:
        sqlite3.Connection: An open SQLite database connection.

    Raises:
        sqlite3.OperationalError: If the database file cannot be opened.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        logger.debug("SQLite connection established", extra={"db_path": str(DB_PATH)})
        return conn
    except sqlite3.Error as exc:
        logger.exception(
            "Failed to create SQLite connection",
            extra={"db_path": str(DB_PATH)}
        )
        raise
