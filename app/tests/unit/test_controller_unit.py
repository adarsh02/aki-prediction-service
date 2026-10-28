import unittest
from unittest.mock import MagicMock, Mock, patch

from datetime import datetime

from controller.controller import Controller

import logging
logging.disable(logging.CRITICAL)


class TestControllerUnit(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_engine = MagicMock()

        self.controller = Controller(
            db_manager=self.mock_db,
            inference_engine=self.mock_engine,
        )

    # ---------- upsert_patient ----------

    def test_upsert_patient_calls_db_manager(self):
        patient_data = {
            "mrn": 123,
            "name": "Alice",
            "dob": "1990-01-01",
            "sex": "F",
            "admission_status": "ADMITTED",
        }

        self.controller.upsert_patient(patient_data)

        self.mock_db.upsert_patient.assert_called_once_with(
            mrn=123,
            name="Alice",
            dob="1990-01-01",
            sex="F",
            status="ADMITTED",
        )

    # ---------- _normalize_lab_result ----------

    def test_normalize_lab_result_valid(self):
        lab_result = {
            "mrn": "123",
            "test_name": "CREATININE",
            "value": "1.5",
            "test_time": "20240101120000",
        }

        mrn, normalized = self.controller._normalize_lab_result(lab_result)

        self.assertEqual(mrn, 123)
        self.assertEqual(normalized["test_name"], "CREATININE")
        self.assertEqual(normalized["value"], 1.5)
        self.assertIsInstance(normalized["test_time"], datetime)
        self.assertEqual(normalized["test_time"], datetime(2024, 1, 1, 12, 0, 0))
        self.assertEqual(normalized.get("mrn"), 123)

    def test_normalize_lab_result_invalid_type(self):
        with self.assertRaises(TypeError):
            self.controller._normalize_lab_result("not a dict")

    def test_normalize_lab_result_missing_mrn(self):
        with self.assertRaises(ValueError):
            self.controller._normalize_lab_result(
                {"test_name": "CR", "value": 1.0, "test_time": "20240101120000"}
            )

    def test_normalize_lab_result_bad_time_format(self):
        with self.assertRaises(ValueError):
            self.controller._normalize_lab_result(
                {
                    "mrn": 1,
                    "test_name": "CR",
                    "value": 1.0,
                    "test_time": "bad-time",
                }
            )

    # ---------- helpers ----------

    def test_insert_lab_result_delegates(self):
        self.mock_db.insert_lab_result.return_value = 42

        lab_result = {
            "test_name": "CR",
            "value": 1.2,
            "test_time": datetime.now(),
            "processing_status": "PROCESSED",
        }

        result_id = self.controller._insert_lab_result(123, lab_result)

        self.assertEqual(result_id, 42)
        self.mock_db.insert_lab_result.assert_called_once()

    def test_fetch_patient_details_delegates(self):
        self.mock_db.get_patient_details_and_history.return_value = {"patient": {}}

        result = self.controller._fetch_patient_details(
            123, {"test_time": datetime.now()}
        )

        self.assertIn("patient", result)
        self.mock_db.get_patient_details_and_history.assert_called_once()

    def test_run_inference_returns_prediction(self):
        self.mock_engine.predict_from_payload.return_value = ("AKI", 0.9)

        prediction = self.controller._run_inference({"patient": {}})

        self.assertEqual(prediction, "AKI")
        self.mock_engine.predict_from_payload.assert_called_once()

    # ---------- process_lab_result ----------

    def test_process_lab_result_happy_path(self):
        self.mock_db.insert_lab_result.return_value = 99
        self.mock_db.get_patient_details_and_history.return_value = {
            "patient": {"mrn": 123, "dob": "1990-01-01", "sex": "F", "admission_status": "ADMITTED"},
            "history_values": [],
            "current_result": {},
        }
        self.mock_db.get_patient.return_value = {
            "mrn": 123,
            "dob": "1990-01-01",
            "sex": "F",
            "admission_status": "ADMITTED",
        }
        self.mock_engine.predict_from_payload.return_value = (1, 0.8)

        lab_result = {
            "mrn": 123,
            "test_name": "CREATININE",
            "value": 2.0,
            "test_time": "20240101120000",
        }

        prediction, timestamp = self.controller.process_lab_result(lab_result)

        self.assertEqual(prediction, 1)
        self.assertIsInstance(timestamp, datetime)

    def test_process_lab_result_normalization_failure(self):

        self.controller.process_lab_result(
            {
                "mrn": "bad",
                "test_name": "CR",
                "value": 1.0,
                "test_time": "20240101120000",
            }
        )

    # -------------------------
    # send_pager_alert()
    # -------------------------

    @patch("controller.controller.requests.post")
    def test_send_pager_alert_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        self.controller.page_aki("payload", 0)

        mock_post.assert_called_once()

    @patch("controller.controller.requests.post")
    @patch("time.sleep")
    def test_send_pager_alert_retries_on_failure(self, mock_sleep, mock_post):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        self.controller.page_aki("payload", 0)

        self.assertEqual(mock_post.call_count, 3)


if __name__ == "__main__":
    unittest.main()
