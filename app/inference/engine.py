# inference/engine.py
import logging
from typing import Optional
from datetime import datetime

from .features import build_features
from .model import get_model

from .inference_exceptions import *

AKI_THRESHOLD = 0.5

logger = logging.getLogger(__name__)

class AKIInferenceEngine:
    """
    Inference engine for predicting Acute Kidney Injury (AKI).

    Responsibilities:
    - Feature construction
    - Model inference
    - Threshold-based classification
    - Payload parsing and age calculation
    """

    def __init__(self, threshold: float = AKI_THRESHOLD):
        """
        Initialize the AKI inference engine.

        Args:
            threshold (float): Probability threshold for AKI prediction.
        """
        self.model = get_model()
        self.threshold = threshold

    def predict_aki(
        self,
        age: int,
        sex: str,
        creatinine_values: list[float],
        mrn: Optional[str] = None,
        timestamp: Optional[str] = None,
        ):
        """
        Predict AKI using explicit input features.

        Args:
            age (int): Patient age in years.
            sex (str): Patient sex.
            creatinine_values (list[float]): Creatinine history values.
            mrn (Optional[str]): Medical record number (metadata only).
            timestamp (Optional[str]): Timestamp of the lab test (metadata only).

        Returns:
            tuple[int, float]: Binary AKI prediction (0 or 1) and probability score.

        Raises:
            ValueError: If required features are missing or invalid.
            Exception: If model inference fails.
        """

        try:
            if age < 0:
                raise ValueError("age must be non-negative")

            if not sex:
                raise ValueError("sex is required for inference")

            if not creatinine_values:
                raise ValueError("creatinine_values must not be empty")
            x = build_features(age, sex, creatinine_values)
            prob = self.model.predict(x)[0]
        except ValueError:
            logger.exception(
                "Model inference failed",
                extra={
                    "mrn": mrn,
                    "age": age,
                    "sex": sex,
                    "values_count": len(creatinine_values),
                },
            )
            raise

        prediction = int(prob >= self.threshold)
        return prediction, float(prob)

    def predict_from_payload(self, payload: dict):
        """
        Predict AKI from a structured payload.

        Expected payload format:
        {
            "patient": {
                "mrn": str,
                "sex": str,
                "dob": str | datetime
            },
            "current_result": {
                "value": float,
                "test_time": str | datetime
            },
            "history_values": list[float]
        }

        Args:
            payload (dict): Patient and lab data.

        Returns:
            tuple[int, float]: Binary AKI prediction and probability score.

        Raises:
            ValueError: If payload is malformed.
            Exception: If inference fails.
        """

        try:
            if not isinstance(payload, dict):
                raise TypeError("payload must be a dictionary")
            patient = payload.get("patient", {})
            current_result = payload.get("current_result", {})
            history = payload.get("history_values", [])

            mrn = patient.get("mrn")
            sex = patient.get("sex")
            dob = patient.get("dob")

            current_value = current_result.get("value")
            test_time = current_result.get("test_time")

            if current_value is None:
                raise ValueError("current_result.value is required")

            creatinine_values = history + [current_value]
            age = self._calculate_age(dob, test_time)

            return self.predict_aki(
                age,
                sex,
                creatinine_values,
                mrn=mrn,
                timestamp=test_time,
            )

        except (ValueError, TypeError) as ve:
            logger.error(f"Value/ Type error while predicting from payload: {ve}")
            raise ve

        except Exception as e:
            logger.exception(
                "Failed to run inference from payload",
                extra={"mrn": payload.get("patient", {}).get("mrn")},
            )
            raise InferenceEngineError("AKI inference failed from payload") from e

    def _parse_dob(self, dob):
        """
        Parse date of birth into a datetime object.

        Accepted formats:
            - YYYYMMDD
            - YYYY-MM-DD

        Args:
            dob (str | datetime): Date of birth.

        Returns:
            datetime: Parsed date of birth.

        Raises:
            ValueError: If the date format is invalid.
        """
        if isinstance(dob, datetime):
            return dob

        if not isinstance(dob, str):
            raise ValueError("dob must be a string or datetime")

        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(dob, fmt)
            except ValueError:
                continue

        raise ValueError(f"Invalid date format for dob: {dob}")

    def _calculate_age(self, dob, test_time):
        """
        Calculate age in years at the time of the lab test.

        Args:
            dob (str | datetime): Date of birth.
            test_time (str | datetime): Lab test timestamp.

        Returns:
            int: Age in years.

        Raises:
            ValueError: If date parsing fails.
        """
        if not dob or not test_time:
            return 0

        dob = self._parse_dob(dob)

        if isinstance(test_time, str):
            try:
                test_time = datetime.strptime(test_time, "%Y%m%d%H%M%S")
            except ValueError:
                raise ValueError("test_time must be in 'YYYYMMDDHHMMSS' format")

        age = test_time.year - dob.year
        if (test_time.month, test_time.day) < (dob.month, dob.day):
            age -= 1

        return age

_engine = AKIInferenceEngine()

def predict_aki(age, sex, creatinine_values):
    return _engine.predict_aki(age, sex, creatinine_values)

def predict_from_payload(payload: dict):
    return _engine.predict_from_payload(payload)