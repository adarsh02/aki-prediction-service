from typing import Dict, List, Tuple
import datetime
import logging

from hl7.hl7_exceptions import HL7ValidationError
from metrics import *

logger = logging.getLogger(__name__)


class MessageHandler:
    """
    HL7 message handler.

    - Parse HL7 segments
    - Validate required fields (with format and numeric checks)
    - Routes domain logic via Controller
    - Return HL7 ACK codes (AA / AE)
    """

    def __init__(self, controller):
        """
        Initialize the MessageHandler.

        Args:
            controller: Controller object to handle business logic (upsert patient, lab processing)
        """
        self.controller = controller

    # ==========================================================
    # Parsing Utilities
    # ==========================================================

    def parse_segments(self, raw_message: str) -> Dict[str, List[List[str]]]:
        """
        Split an HL7 raw message string into segments and their fields.

        Args:
            raw_message (str): Raw HL7 message text.

        Returns:
            Dict[str, List[List[str]]]: Dictionary mapping segment names (e.g., 'MSH', 'PID') 
                                        to lists of field lists.

        Raises:
            HL7ValidationError: If the message is empty or contains invalid segment IDs.
        """
        if not raw_message or not raw_message.strip():
            raise HL7ValidationError("Empty HL7 message received")

        segments: Dict[str, List[List[str]]] = {}
        for line in raw_message.strip().split("\r"):
            fields = line.split("|")
            if len(fields[0]) != 3:
                raise HL7ValidationError(f"Invalid segment ID: {fields[0]}")
            segments.setdefault(fields[0], []).append(fields)

        return segments

    def require_field(
        self,
        segments: Dict[str, List[List[str]]],
        segment: str,
        index: int,
        label: str,
        fmt: str | None = None,
        numeric: bool = False
    ) -> str:
        """
        Retrieve a required field from a segment, validating format and numeric constraints.

        Args:
            segments (dict): Parsed HL7 segments.
            segment (str): Segment name (e.g., 'PID').
            index (int): Field index within the segment.
            label (str): Field name for error messages.
            fmt (str | None): Optional datetime format string to validate.
            numeric (bool): If True, ensure the value is numeric.

        Returns:
            str: The field value as a string.

        Raises:
            HL7ValidationError: If the field is missing, empty, incorrectly formatted, or non-numeric.
        """
        try:
            value = segments[segment][0][index].strip()
        except (KeyError, IndexError):
            raise HL7ValidationError(f"Missing required field {label}", segment, label)

        if not value:
            raise HL7ValidationError(f"Empty required field {label}", segment, label)

        if fmt:
            try:
                datetime.datetime.strptime(value, fmt)
            except ValueError:
                raise HL7ValidationError(f"{label} must match format {fmt}", segment, label)

        if numeric:
            try:
                float(value)
            except ValueError:
                raise HL7ValidationError(f"{label} must be numeric", segment, label)

        return value
    
    def get_raw_timestamp(self, test_time_str: str):
        """
        Convert a datetime string in '%Y-%m-%d %H:%M:%S' format to HL7-style 'YYYYMMDDHHMMSS'.

        Args:
            test_time_str (str): Datetime string in '%Y-%m-%d %H:%M:%S' format.

        Returns:
            str: Timestamp in 'YYYYMMDDHHMMSS' format.

        Raises:
            ValueError: If the input string does not match the expected datetime format.
            TypeError: If the input is None or not convertible to string.
        """
        try:
            test_time = datetime.datetime.strptime(
                str(test_time_str).strip(),
                "%Y-%m-%d %H:%M:%S"
            )
            raw_timestamp = test_time.strftime("%Y%m%d%H%M%S")
            return raw_timestamp

        except ValueError as e:
            raise ValueError(
                f"Invalid datetime format: '{test_time_str}'. "
                "Expected format: 'YYYY-MM-DD HH:MM:SS'."
            ) from e

        except TypeError as e:
            raise TypeError(
                f"Invalid type for test_time_str: {type(test_time_str)}. "
                "Expected a string."
            ) from e


    # ==========================================================
    # Common Header Parsing
    # ==========================================================

    def parse_common_header(self, segments: Dict) -> Dict:
        """
        Extract common fields from MSH and PID segments for all message types.

        Args:
            segments (dict): Parsed HL7 segments.

        Returns:
            dict: Dictionary containing:
                  - 'message_time' (str): HL7 timestamp from MSH.7
                  - 'message_type' (str): HL7 message type from MSH.9
                  - 'mrn' (str): Patient MRN from PID.3
        """
        return {
            "message_time": self.require_field(segments, "MSH", 6, "MSH.7", fmt="%Y%m%d%H%M%S"),
            "message_type": self.require_field(segments, "MSH", 8, "MSH.9"),
            "mrn": self.require_field(segments, "PID", 3, "PID.3", numeric=True),
        }


    # ==========================================================
    # Message Parsers
    # ==========================================================

    def parse_admit_message(self, segments: Dict) -> Dict:
        """
        Parse ADT^A01 admission message.

        Args:
            segments (dict): Parsed HL7 segments.

        Returns:
            dict: Dictionary containing patient info and admission status:
                  - 'name', 'dob', 'sex', 'admission_status'
        """
        return {
            **self.parse_common_header(segments),
            "name": self.require_field(segments, "PID", 5, "PID.5"),
            "dob": self.require_field(segments, "PID", 7, "PID.7", fmt="%Y%m%d"),
            "sex": self.require_field(segments, "PID", 8, "PID.8"),
            "admission_status": "ADMITTED",
        }

    def parse_discharge_message(self, segments: Dict) -> Dict:
        """
        Parse ADT^A03 discharge message.

        Args:
            segments (dict): Parsed HL7 segments.

        Returns:
            dict: Dictionary containing common header fields and discharge status.
        """
        return {
            **self.parse_common_header(segments),
            "admission_status": "DISCHARGED",
        }


    def parse_lab_result_message(self, segments: Dict) -> Dict:
        """
        Parse an ORU^R01 lab result message.

        Args:
            segments (dict): Parsed HL7 segments.

        Returns:
            dict: Dictionary containing common header fields plus:
                  - 'test_time' (str): Lab test datetime from OBR.7
                  - 'test_name' (str): Test name from OBX.3
                  - 'value' (str): Test result value from OBX.5
        """
        return {
            **self.parse_common_header(segments,),
            "test_time": self.require_field(segments, "OBR", 7, "OBR.7", fmt="%Y%m%d%H%M%S"),
            "test_name": self.require_field(segments, "OBX", 3, "OBX.3"),
            "value": self.require_field(segments, "OBX", 5, "OBX.5", numeric=True),
        }


    # ==========================================================
    # Main Handler
    # ==========================================================

    def handle(self, raw_message: str) -> Tuple[str, int, int, str]:
        """
        Main entry point for processing HL7 messages.

        Parses HL7 message, validates required fields, and calls the controller 
        for domain logic (patient upsert or lab result processing). Returns an HL7 ACK code.

        Args:
            raw_message (str): HL7 raw message string.

        Returns:
            Tuple[str, int, int, str]: HL7 ACK tuple
                                        (code, prediction, mrn, test_time)
                                        code = 'AA' for success, 'AE' for failure
        """
        try:

            logger.debug("Received HL7 message: %s", raw_message)          

            segments = self.parse_segments(raw_message)
            msg_type = self.require_field(segments, "MSH", 8, "MSH.9")

            logger.debug("Message type identified: %s", msg_type)

            if msg_type == "ADT^A01":
                data = self.parse_admit_message(segments)

                logger.debug("Parsed admit message data: %s", data)
                messages_total.labels(message_type="ADT^A01").inc()
                
                self.controller.upsert_patient(data)

                return "AA", False, data.get("mrn", -1), ""

            elif msg_type == "ADT^A03":
                data = self.parse_discharge_message(segments)

                logger.debug("Parsed discharge message data: %s", data)
                messages_total.labels(message_type="ADT^A03").inc()

                self.controller.upsert_patient(data)

                return "AA", False, data.get("mrn", -1), ""

            elif msg_type == "ORU^R01":
                data = self.parse_lab_result_message(segments)

                logger.debug("Parsed lab result message data: %s", data)
                messages_total.labels(message_type="ORU^R01").inc()
                blood_tests_total.inc()                
                
                prediction, test_time = self.controller.process_lab_result(data)

                logger.debug("Lab result processed with prediction and test_time: %s, %s", prediction, test_time)

                if (prediction==1):
                    aki_predictions_total.inc()
                
                test_time = self.get_raw_timestamp(test_time)
                
                if (prediction == -1):
                    return "AA", False, data.get("mrn", -1), ""
                
                return "AA", prediction, int(data["mrn"]), test_time

            else:
                raise HL7ValidationError(f"Unsupported HL7 message type {msg_type}")

        except (ValueError, TypeError) as e:
            logger.error(f"Value/ Type error while handling the messgage: {e}")
            return "AA", False, -1, ""
    
        except HL7ValidationError as e:
            logger.error("HL7 validation failed", extra={"error": str(e)})
            malformed_messages_total.inc()
            return "AA", False, -1, ""

        except Exception as e:
            logger.error("Unexpected error processing HL7 message", extra={"error": str(e)}, exc_info=True)
            return "AA", False, -1, ""
