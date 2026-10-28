import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

from db.connection import get_connection
from db.db_manager import DBManager

import logging
logging.disable(logging.CRITICAL)


SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    mrn TEXT PRIMARY KEY,
    name TEXT,
    dob TEXT,
    sex TEXT,
    admission_status TEXT,
    last_updated TEXT
);

CREATE TABLE IF NOT EXISTS lab_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mrn TEXT,
    test_name TEXT,
    test_time TEXT,
    value REAL,
    processing_status TEXT,
    UNIQUE(mrn , test_time)
);
"""

class TestDBManager(unittest.TestCase):

    def setUp(self):
        self.tmpdir = TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"

        conn = get_connection(self.db_path)
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

        self.manager = DBManager(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_upsert_patient(self):
        self.manager.upsert_patient(
            "123", "Alice", "1990-01-01", "F", "ADMITTED"
        )

        conn = get_connection(self.db_path)
        row = conn.execute(
            "SELECT name FROM patients WHERE mrn = ?", ("123",)
        ).fetchone()
        conn.close()

        self.assertEqual(row["name"], "Alice")

    def test_insert_lab_result_returns_id(self):
        result_id = self.manager.insert_lab_result(
            "123", "CREATININE", "2024-01-01", 1.5, "PROCESSED"
        )

        self.assertIsInstance(result_id, int)

    def test_get_patient_details_and_history(self):
        self.manager.upsert_patient(
            "123", "Alice", "1990-01-01", "F", "ADMITTED"
        )

        self.manager.insert_lab_result(
            "123", "CREATININE", "2024-01-01", 1.0, "PROCESSED"
        )
        result_id = self.manager.insert_lab_result(
            "123", "CREATININE", "2024-02-01", 2.0, "PROCESSED"
        )

        lab_result = {
            "result_id": result_id,
            "value": 2.0,
            "test_time": "2024-02-01 08:30",
        }

        data = self.manager.get_patient_details_and_history("123", lab_result)

        # ---- Patient ----
        patient = data["patient"]
        self.assertEqual(patient["mrn"], "123")
        self.assertEqual(patient["sex"], "F")
        self.assertEqual(patient["dob"], "1990-01-01")

        # ---- Current result ----
        current = data["current_result"]
        self.assertEqual(current["result_id"], result_id)
        self.assertEqual(current["value"], 2.0)
        self.assertEqual(current["test_time"], "2024-02-01 08:30")

        # ---- History values (flattened) ----
        history_values = data["history_values"]

        self.assertIsInstance(history_values, list)
        self.assertTrue(all(isinstance(v, float) for v in history_values))
        
        # ---- Structure ----
        self.assertIn("patient", data)
        self.assertIn("current_result", data)
        self.assertIn("history_values", data)

