import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

from db.connection import get_connection
from db.db_manager import DBManager
from controller.controller import Controller
from inference.engine import AKIInferenceEngine

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
    test_time TIMESTAMP,
    value REAL,
    processing_status TEXT DEFAULT 'PROCESSED',
    UNIQUE(mrn , test_time)
);
"""

class TestControllerIntegration(unittest.TestCase):

    def setUp(self):
        # Temporary directory & database
        self.tmpdir = TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"

        # Initialize real database
        conn = get_connection(self.db_path)
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

        # Real DBManager and InferenceEngine
        self.db_manager = DBManager(db_path=self.db_path)
        self.inference_engine = AKIInferenceEngine()
        self.controller = Controller(
            db_manager=self.db_manager,
            inference_engine=self.inference_engine,
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    # ---------- Happy Path ----------

    def test_full_lab_result_flow(self):
        # Add patient
        self.controller.upsert_patient({
            "mrn": 123,
            "name": "Alice",
            "dob": "19900101",  # YYYYMMDD format
            "sex": "F",
            "admission_status": "ADMITTED",
        })

        # Lab result
        lab_result = {
            "mrn": 123,
            "test_name": "CREATININE",
            "value": 2.0,
            "test_time": "20240101120000",  # YYYYMMDDHHMMSS
        }

        prediction, timestamp = self.controller.process_lab_result(lab_result)

        # Check types and expected prediction values
        self.assertIsInstance(prediction, int)
        self.assertIsInstance(timestamp, datetime)

    # ---------- Invalid / Failure Paths ----------

    def test_invalid_mrn_raises(self):
        lab_result = {
            "mrn": "bad",  # invalid
            "test_name": "CREATININE",
            "value": 2.0,
            "test_time": "20240101120000",
        }

        prediction, test_time = self.controller.process_lab_result(lab_result)
        
        self.assertEqual(prediction, -1)
        self.assertEqual(test_time, "")
        

    def test_invalid_dob_raises(self):
        # Add patient with invalid DOB format
        self.controller.upsert_patient({
            "mrn": 124,
            "name": "Bob",
            "dob": "01-1990-01",  # wrong format for engine
            "sex": "M",
            "admission_status": "ADMITTED",
        })

        lab_result = {
            "mrn": 124,
            "test_name": "CREATININE",
            "value": 1.5,
            "test_time": "20240101120000",
        }

        prediction, test_time = self.controller.process_lab_result(lab_result)
        
        self.assertEqual(test_time, "")
        self.assertEqual(prediction, -1)

    def test_invalid_test_time_format_raises(self):
        self.controller.upsert_patient({
            "mrn": 125,
            "name": "Charlie",
            "dob": "19900101",
            "sex": "M",
            "admission_status": "ADMITTED",
        })

        lab_result = {
            "mrn": 125,
            "test_name": "CREATININE",
            "value": 1.5,
            "test_time": "badtime",  # invalid
        }

        prediction, test_time = self.controller.process_lab_result(lab_result)
        
        self.assertEqual(prediction, -1)
        self.assertEqual(test_time, "")

if __name__ == "__main__":
    unittest.main()
