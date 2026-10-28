"""
Database initialization utilities.

This module is responsible for initializing the database schema and
seeding initial lab history data on first application startup.
"""

import csv
import logging
from pathlib import Path

from db.db_manager import get_connection

logger = logging.getLogger(__name__)

# Absolute path to the database file
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = Path("/state/hospital.db")
HISTORY_PATH = Path("/data/history.csv")


def init_db(db_path: Path = DB_PATH, history_path: Path = HISTORY_PATH) -> None:
    """
    Initialize the database schema and seed historical lab data.

    This function is safe to call multiple times. If the database file
    already exists, initialization is skipped.

    Args:
        db_path: Path to the SQLite database file.

    Raises:
        RuntimeError: If database initialization fails.
    """
    if db_path.exists():
        logger.info("Database already exists, skipping initialization")
        return

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = get_connection(db_path)

        logger.info("Initializing database schema")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=OFF;")

        schema_path = BASE_DIR / "db" / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

        inserts = _load_history_data(history_path)

        conn.executemany(
            """
            INSERT INTO lab_results (mrn, test_name, test_time, value)
            VALUES (?, ?, ?, ?)
            """,
            inserts,
        )

        conn.commit()
        logger.info(
            "Database initialized successfully",
            extra={"rows_inserted": len(inserts)},
        )
    
    except FileNotFoundError as exc:
        logger.exception("Database initialization failed")
        raise RuntimeError("Failed to initialize database") from exc

    finally:
        try:
            conn.close()
        except Exception:
            pass

def _load_history_data(history_path: Path = HISTORY_PATH) -> list[tuple]:
    """
    Load historical lab results from CSV.

    Returns:
        List of tuples ready for bulk insertion.
    """
    if not history_path.exists():
        raise FileNotFoundError(f"History file not found: {history_path}")

    inserts = []

    with open(history_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row_idx, row in enumerate(reader, start=1):
            mrn = row.get("mrn")
            if not mrn:
                logger.warning("Row missing MRN, skipping", extra={"row": row_idx})
                continue

            i = 0
            while True:
                date_key = f"creatinine_date_{i}"
                value_key = f"creatinine_result_{i}"

                if date_key not in row or value_key not in row:
                    break

                raw_date = row.get(date_key, "").strip()
                raw_value = row.get(value_key, "").strip()

                if not raw_date or not raw_value:
                    i += 1
                    continue

                try:
                    value = float(raw_value)
                except ValueError:
                    logger.warning(
                        "Invalid creatinine value",
                        extra={"row": row_idx, "mrn": mrn, "value": raw_value},
                    )
                    i += 1
                    continue

                inserts.append((mrn, "CREATININE", raw_date, value))
                i += 1

    return inserts
