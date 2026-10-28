import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from inference.engine import AKIInferenceEngine


class TestAKIInferenceEngine(unittest.TestCase):

    @patch("inference.engine.get_model")
    @patch("inference.engine.build_features")
    def test_predict_aki_positive(self, mock_build_features, mock_get_model):
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9]
        mock_get_model.return_value = mock_model

        engine = AKIInferenceEngine(threshold=0.5)

        prediction, prob = engine.predict_aki(
            age=60,
            sex="F",
            creatinine_values=[1.0, 1.6, 2.2],
        )

        self.assertEqual(prediction, 1)
        self.assertEqual(prob, 0.9)
        mock_build_features.assert_called_once()

    @patch("inference.engine.get_model")
    @patch("inference.engine.build_features")
    def test_predict_aki_negative(self, mock_build_features, mock_get_model):
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.2]
        mock_get_model.return_value = mock_model

        engine = AKIInferenceEngine(threshold=0.5)

        prediction, prob = engine.predict_aki(
            age=35,
            sex="M",
            creatinine_values=[1.0],
        )

        self.assertEqual(prediction, 0)
        self.assertEqual(prob, 0.2)

    @patch("inference.engine.get_model")
    @patch("inference.engine.build_features")
    def test_predict_from_payload(self, mock_build_features, mock_get_model):
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.7]
        mock_get_model.return_value = mock_model

        engine = AKIInferenceEngine(threshold=0.5)

        payload = {
            "patient": {
                "mrn": "123",
                "sex": "M",
                "dob": "1980-01-01",
            },
            "current_result": {
                "value": 2.0,
                "test_time": "20240101120000",
            },
            "history_values": [1.1, 1.4],
        }

        prediction, prob = engine.predict_from_payload(payload)

        self.assertEqual(prediction, 1)
        self.assertEqual(prob, 0.7)

        mock_build_features.assert_called_once_with(
            44, "M", [1.1, 1.4, 2.0]
        )

    def test_parse_dob_valid_formats(self):
        engine = AKIInferenceEngine()

        self.assertEqual(
            engine._parse_dob("19900101"),
            datetime(1990, 1, 1),
        )
        self.assertEqual(
            engine._parse_dob("1990-01-01"),
            datetime(1990, 1, 1),
        )

    def test_parse_dob_invalid_format(self):
        engine = AKIInferenceEngine()

        with self.assertRaises(ValueError):
            engine._parse_dob("01/01/1990")
            
    def test_calculate_age_missing_values(self):
        engine = AKIInferenceEngine()
        self.assertEqual(engine._calculate_age(None, None), 0)


if __name__ == "__main__":
    unittest.main()
