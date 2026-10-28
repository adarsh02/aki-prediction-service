import logging
from datetime import datetime
from typing import Dict, Tuple, Any, Optional
import requests
import time

from db.db_manager import DBManager
from db.db_excpetions import *
from inference.engine import AKIInferenceEngine
from inference.inference_exceptions import *
from metrics import *

logger = logging.getLogger(__name__)


class Controller:
    """
    Central application controller.
    """

    def __init__(
        self,
        db_manager: DBManager,
        inference_engine: AKIInferenceEngine,
        pager_address: str = "localhost:8441",
    ):
        """
        Initialize the controller.

        Args:
            db_manager: Database manager instance.
            inference_engine: Inference engine instance.
        """
        self.db_manager = db_manager
        self.inference_engine = inference_engine
        
        pager_host, pager_port = pager_address.split(":")
        self.pager_host = pager_host
        self.pager_port = int(pager_port)


    # ---------------- Patients ----------------

    def upsert_patient(self, patient_data: Dict[str, Any]) -> None:
        """
        Insert or update a patient record.

        Args:
            patient_data: Dictionary containing patient attributes.
        """
        try:
            self.db_manager.upsert_patient(
            mrn=patient_data.get("mrn", 0),
            name=patient_data.get("name", ""),
            dob=patient_data.get("dob", ""),
            sex=patient_data.get("sex", ""),
            status=patient_data.get("admission_status", ""),
        )

            if patient_data.get("admission_status") == "ADMITTED":
                self.process_pending_labs(patient_data.get("mrn",0))
            
        except DBExecError as e:
            db_operations_errors_total.labels(operation_type="upsert").inc()

    # ---------------- Lab Results ----------------

    def _normalize_lab_result(
        self, lab_result: Dict[str, Any]
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Validate and normalize incoming lab result payload.

        Args:
            lab_result: Raw lab result dictionary.

        Returns:
            Tuple of MRN and normalized lab result dictionary.

        Raises:
            TypeError: If input is not a dict.
            ValueError: If required fields are invalid.
        """
        if not isinstance(lab_result, dict):
            raise TypeError("Input must be a dictionary")

        try:
            mrn = int(lab_result.get("mrn"))
        except (TypeError, ValueError):
            raise ValueError("mrn is required and must be an integer")

        test_name = str(lab_result.get("test_name", "")).strip()
        if not test_name:
            raise ValueError("test_name is required")

        try:
            value = float(lab_result.get("value"))
        except (TypeError, ValueError):
            raise ValueError("value is required and must be a number")

        raw_time = lab_result.get("test_time")
        if raw_time is None:
            raise ValueError("test_time is required")

        if isinstance(raw_time, str):
            try:
                test_time = datetime.strptime(raw_time, "%Y%m%d%H%M%S")
            except ValueError:
                raise ValueError("test_time must be in 'YYYYMMDDHHMMSS' format")
        elif isinstance(raw_time, datetime):
            test_time = raw_time
        else:
            raise ValueError("test_time must be a string or datetime")

        return mrn, {
            "mrn": mrn,
            "test_name": test_name,
            "value": value,
            "test_time": test_time,
        }

    def process_lab_result(
        self, lab_result: Dict[str, Any]
    ) -> Tuple[Any, datetime]:
        """
        Process a lab result end-to-end.

        Steps:
        - normalize input
        - persist lab result
        - fetch patient history
        - run inference

        Args:
            lab_result: Raw lab result payload.

        Returns:
            Tuple of prediction and test timestamp.

        Raises:
            Exception: If any processing step fails.
        """
        try:
            mrn, normalized = self._normalize_lab_result(lab_result)

            blood_test_value_distribution.observe(normalized.get("value"))
            
            patient = self.db_manager.get_patient(mrn)
            is_admitted = patient and patient.get("admission_status") == "ADMITTED"

            normalized["processing_status"] = "PROCESSED" if is_admitted else "PENDING_ADMIT"

            # UNIQUENESS CONSTRAINT on (mrn, test_time) ?
            result_id = self._insert_lab_result(mrn, normalized)
            normalized["result_id"] = result_id

            #Defer processing if patient not admitted yet
            if not is_admitted:
                logger.info(f"Deferred lab result {result_id} for MRN {mrn} (Awaiting ADT)")
                return 0, normalized["test_time"]

            patient_data = self._fetch_patient_details(mrn, normalized)

            prediction = self._run_inference(patient_data)

            return prediction, normalized["test_time"]

        except ValueError as e:
            logger.warning(f"Error processing lab result due to ValueError: {e}")
            return -1, ""         
        
        except DBExecError as e:
            logger.warning(f"Error processing lab result due to DBExec Error: {e}")
            db_operations_errors_total.labels(operation_type="process_lab_result").inc()
            return -1, ""         
        
        except InferenceEngineError as e:
            logger.warning(f"Error processing lab result due to InferenceEgnine Error: {e}")
            inference_errors_total.inc()
            return -1, ""         
        
        except Exception as e:
            logger.exception("Failed to process lab result due to unknown reason: {e}")
            return -1, ""

    # ---------------- Internal Helpers ----------------

    def _insert_lab_result(self, mrn: int, lab_result: Dict[str, Any]) -> int:
        """Persist a lab result and return its ID."""
        return self.db_manager.insert_lab_result(
            mrn=mrn,
            test_name=lab_result["test_name"],
            test_time=lab_result["test_time"],
            value=lab_result["value"],
            processing_status=lab_result["processing_status"],
        )

    def _fetch_patient_details(
        self, mrn: int, lab_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch patient details and lab history."""
        return self.db_manager.get_patient_details_and_history(mrn, lab_result)

    def _run_inference(self, patient_details: Dict[str, Any]):
        """Run inference on patient payload."""
        prediction, _prob = self.inference_engine.predict_from_payload(
            patient_details
        )
        return prediction
    

    # ---------------- Paging ----------------
    def page_aki(self, mrn, test_time):
        try:
            self._send_pager_alert(payload=f"{mrn},{test_time}")
            logger.info(f"[AKI DETECTED] {datetime.now().isoformat()} \n- MRN={mrn}, TestTime={test_time}")
            logger.debug(f"{mrn},{test_time}")
        except Exception as e:
            logger.error(f"Exception sending page alert: {e}")

    def _send_pager_alert(
        self,
        payload: str,
        timeout: float = 2.0,
        max_retries: int = 3,
        retx_timeout: int = 5,
    ) -> str:
        """
        Send a pager alert with retry and backoff logic.

        Performs synchronous HTTP POST requests to the pager service.
        Retries on network errors and server-side failures.

        Args:
            payload (str): Pager message payload
            timeout (float): HTTP request timeout in seconds
            max_retries (int): Maximum number of retry attempts
            backoff_seconds (list[float]): Sleep durations between retries
        """

        # Base pager service URL
        base_url = f"http://{self.pager_host}:{self.pager_port}"

        # HTTP request headers
        headers = {
            "Content-Type": "text/plain"
        }

        # Retry loop with backoff
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{base_url}/page",
                    data=payload,
                    headers=headers,
                    timeout=timeout,
                )

                # Successful delivery
                if 200 <= response.status_code < 300:
                    pager_requests_total.labels(status_code=response.status_code).inc()
                    return
                pager_retries_total.labels(status_code=response.status_code).inc()

                # Retry on server-side errors
                if response.status_code >= 500:
                    raise RuntimeError(
                        f"Pager server error {response.status_code}"
                    )
            except (requests.Timeout, requests.ConnectionError, RuntimeError) as exc:
                logger.warning(
                    "Pager attempt %d/%d failed for AKI: %s",
                    attempt + 1,
                    max_retries,
                    exc,
                )
                last_exception = exc
                time.sleep(retx_timeout)
        
        logger.critical(
                        "Pager failed after %d attempts for AKI. \nSkipping paging. Last error: %s",
                        max_retries,
                        repr(last_exception),
                    )


    def process_pending_labs(self, mrn: int) -> None:
        """Processes any deferred lab results once a patient is admitted."""
        pending_labs = self.db_manager.get_pending_labs(mrn)
        
        try:
            for lab in pending_labs:
                patient_data = self._fetch_patient_details(mrn, lab)
                prediction = self._run_inference(patient_data)
                
                # Page if AKI is detected
                if prediction:
                    self.page_aki(mrn, lab["test_time"])
                
                # Mark as processed
                self.db_manager.mark_lab_processed(lab["result_id"])
                logger.info(f"Processed deferred lab {lab['result_id']} for MRN {mrn}")
        
        except ValueError as ve:
            logger.warning(f"Error occurred due to value error in inference engine: {e}")
        
        except InferenceEngineError as e:
            logger.warning(f"Error occurred due to inference engine while processing pending labs: {e}")
            inference_errors_total.inc()
        
        except DBExecError as e:
            logger.warning(f"Error occurred due to inference engine while processing pending labs: {e}")
            db_operations_errors_total.labels(operation_type="pending_labs").inc()
        
        except Exception as e:
            logger.error(f"Failed to process pending lab {lab['result_id']}: {e}")