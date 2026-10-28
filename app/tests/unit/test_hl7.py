import unittest
from hl7.handler import MessageHandler
from hl7.hl7_exceptions import HL7ValidationError

# -------------------------------
# HL7 Sample Messages
# -------------------------------

# Standard messages
HL7_ADT_A01_STANDARD = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240101155700||ADT^A01|||2.5\r"
    "PID|1||115749348||ADRIANA EDWARDS||19750629|F\r"
    "NK1|1|NEXT OF KIN|RELATION\r"
)

HL7_ADT_A03_STANDARD = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240331062100||ADT^A03|||2.5\r"
    "PID|1||131052901\r"
)

HL7_ORU_R01_STANDARD = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240331062800||ORU^R01|||2.5\r"
    "PID|1||126533838\r"
    "OBR|1||||||20240331062800\r"
    "OBX|1|SN|CREATININE||210.07698836081133\r"
)

HL7_ADT_A01_SIYA_BARRY = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240603114800||ADT^A01|||2.5\r"
    "PID|1||100894132||SIYA BARRY||20200929|F\r"
)

HL7_ORU_R01_SIYA_BARRY = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240603114900||ORU^R01|||2.5\r"
    "PID|1||142962210\r"
    "OBR|1||||||20240603114900\r"
    "OBX|1|SN|CREATININE||60.30820041696642\r"
)

HL7_ADT_A01_EVERLEIGH_SHAW = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240603120600||ADT^A01|||2.5\r"
    "PID|1||133148196||EVERLEIGH SHAW||19581023|F\r"
)

HL7_ORU_R01_EVERLEIGH_SHAW = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240603120600||ORU^R01|||2.5\r"
    "PID|1||176106723\r"
    "OBR|1||||||20240603120600\r"
    "OBX|1|SN|CREATININE||71.40432183982323\r"
)

HL7_ADT_A03_DISCHARGE = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240603121200||ADT^A03|||2.5\r"
    "PID|1||154068082\r"
)

HL7_ADT_A01_MULTIPLE_NK1 = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240604100000||ADT^A01|||2.5\r"
    "PID|1||200123456||JANE DOE||19950515|F\r"
    "NK1|1|JOHN DOE|BROTHER\r"
    "NK1|2|JILL DOE|MOTHER\r"
)

# Invalid / malformed messages
HL7_EMPTY_MESSAGE = ""
HL7_BAD_SEGMENT = "MS|1||BAD\r"
HL7_MISSING_MRN = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240101155700||ADT^A01|||2.5\r"
    "PID|1||\r"
)
HL7_NON_NUMERIC_MRN = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240101155700||ADT^A01|||2.5\r"
    "PID|1||ABC123||ADRIANA EDWARDS||19750629|F\r"
)
HL7_NON_NUMERIC_LAB_VALUE = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240603143200||ORU^R01|||2.5\r"
    "PID|1||129282777\r"
    "OBR|1||||||20240603143200\r"
    "OBX|1|SN|CREATININE||NOTANUMBER\r"
)
HL7_INVALID_DATE = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||BADDATE||ADT^A01|||2.5\r"
    "PID|1||115749348||ADRIANA EDWARDS||19750629|F\r"
)
HL7_MISSING_OBR = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240603122000||ORU^R01|||2.5\r"
    "PID|1||178899001\r"
    "OBX|1|SN|GLUCOSE||99.0\r"  # Missing OBR
)
HL7_OBX_NON_NUMERIC_VALUE = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240603123000||ORU^R01|||2.5\r"
    "PID|1||178899002\r"
    "OBR|1||||||20240603123000\r"
    "OBX|1|SN|GLUCOSE||ABC\r"
)
HL7_PID_EMPTY_NAME = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240603124000||ADT^A01|||2.5\r"
    "PID|1||178899003|||||F\r"
)
HL7_PID_INVALID_DOB = (
    "MSH|^~\\&|SIMULATION|SOUTH RIVERSIDE|||20240603125000||ADT^A01|||2.5\r"
    "PID|1||178899004||JOHN DOE||INVALIDDOB|M\r"
)


# ===============================
# Test Cases
# ===============================

class TestMessageParsing(unittest.TestCase):

    # ---------------------------
    # Setup
    # ---------------------------
    def setUp(self):
        self.handler = MessageHandler(controller=None)

    # ---------------------------
    # parse_segments Tests
    # ---------------------------
    def test_parse_segments_success(self):
        segments = self.handler.parse_segments(HL7_ADT_A01_STANDARD)
        self.assertIn("MSH", segments)
        self.assertIn("PID", segments)
        self.assertTrue(segments["MSH"][0][8].startswith("ADT"))

    def test_parse_segments_empty_message(self):
        with self.assertRaises(HL7ValidationError):
            self.handler.parse_segments(HL7_EMPTY_MESSAGE)

    def test_parse_segments_bad_segment(self):
        with self.assertRaises(HL7ValidationError):
            self.handler.parse_segments(HL7_BAD_SEGMENT)

    # ---------------------------
    # require_field Tests
    # ---------------------------
    def test_require_field_success(self):
        segments = self.handler.parse_segments(HL7_ADT_A01_STANDARD)
        mrn = self.handler.require_field(segments, "PID", 3, "PID.3", numeric=True)
        self.assertEqual(mrn, "115749348")

    def test_require_field_missing(self):
        segments = self.handler.parse_segments(HL7_MISSING_MRN)
        with self.assertRaises(HL7ValidationError):
            self.handler.require_field(segments, "PID", 3, "PID.3")

    def test_require_field_invalid_numeric(self):
        segments = self.handler.parse_segments(HL7_NON_NUMERIC_MRN)
        with self.assertRaises(HL7ValidationError):
            self.handler.require_field(segments, "PID", 3, "PID.3", numeric=True)

    def test_require_field_invalid_date_format(self):
        segments = self.handler.parse_segments(HL7_INVALID_DATE)
        with self.assertRaises(HL7ValidationError):
            self.handler.require_field(segments, "MSH", 6, "MSH.7", fmt="%Y%m%d%H%M%S")

    # ---------------------------
    # Message Parser Tests – Valid Messages
    # ---------------------------
    def test_parse_admit_message_standard(self):
        segments = self.handler.parse_segments(HL7_ADT_A01_STANDARD)
        data = self.handler.parse_admit_message(segments)
        self.assertEqual(data["mrn"], "115749348")
        self.assertEqual(data["name"], "ADRIANA EDWARDS")
        self.assertEqual(data["dob"], "19750629")
        self.assertEqual(data["sex"], "F")
        self.assertEqual(data["admission_status"], "ADMITTED")
        self.assertEqual(data["message_type"], "ADT^A01")
        self.assertEqual(data["message_time"], "20240101155700")

    def test_parse_discharge_message_standard(self):
        segments = self.handler.parse_segments(HL7_ADT_A03_STANDARD)
        data = self.handler.parse_discharge_message(segments)
        self.assertEqual(data["mrn"], "131052901")
        self.assertEqual(data["admission_status"], "DISCHARGED")
        self.assertEqual(data["message_type"], "ADT^A03")
        self.assertEqual(data["message_time"], "20240331062100")

    def test_parse_lab_result_message_standard(self):
        segments = self.handler.parse_segments(HL7_ORU_R01_STANDARD)
        data = self.handler.parse_lab_result_message(segments)
        self.assertEqual(data["mrn"], "126533838")
        self.assertEqual(data["test_name"], "CREATININE")
        self.assertEqual(float(data["value"]), 210.07698836081133)
        self.assertEqual(data["test_time"], "20240331062800")
        self.assertEqual(data["message_type"], "ORU^R01")
        self.assertEqual(data["message_time"], "20240331062800")


    def test_new_adt_a01_siya_barry(self):
        segments = self.handler.parse_segments(HL7_ADT_A01_SIYA_BARRY)
        data = self.handler.parse_admit_message(segments)
        self.assertEqual(data["mrn"], "100894132")
        self.assertEqual(data["name"], "SIYA BARRY")
        self.assertEqual(data["dob"], "20200929")
        self.assertEqual(data["sex"], "F")
        self.assertEqual(data["admission_status"], "ADMITTED")
        self.assertEqual(data["message_type"], "ADT^A01")
        self.assertEqual(data["message_time"], "20240603114800")

    def test_new_oru_r01_siya_barry(self):
        segments = self.handler.parse_segments(HL7_ORU_R01_SIYA_BARRY)
        data = self.handler.parse_lab_result_message(segments)
        self.assertEqual(data["mrn"], "142962210")
        self.assertEqual(data["test_name"], "CREATININE")
        self.assertEqual(float(data["value"]), 60.30820041696642)
        self.assertEqual(data["test_time"], "20240603114900")
        self.assertEqual(data["message_type"], "ORU^R01")
        self.assertEqual(data["message_time"], "20240603114900")

    def test_adt_multiple_nk1(self):
        segments = self.handler.parse_segments(HL7_ADT_A01_MULTIPLE_NK1)
        data = self.handler.parse_admit_message(segments)
        self.assertEqual(data["mrn"], "200123456")
        self.assertEqual(data["name"], "JANE DOE")
        self.assertEqual(data["dob"], "19950515")
        self.assertEqual(data["sex"], "F")
        self.assertEqual(data["admission_status"], "ADMITTED")
        self.assertEqual(data["message_type"], "ADT^A01")
        self.assertEqual(data["message_time"], "20240604100000")

    # ---------------------------
    # Message Parser Tests – Failure Cases / Edge Cases
    # ---------------------------
    def test_parse_lab_result_missing_obr(self):
        segments = self.handler.parse_segments(HL7_MISSING_OBR)
        with self.assertRaises(HL7ValidationError):
            self.handler.parse_lab_result_message(segments)

    def test_parse_lab_result_obx_non_numeric(self):
        segments = self.handler.parse_segments(HL7_OBX_NON_NUMERIC_VALUE)
        with self.assertRaises(HL7ValidationError):
            self.handler.parse_lab_result_message(segments)

    def test_parse_admit_pid_empty_name(self):
        segments = self.handler.parse_segments(HL7_PID_EMPTY_NAME)
        with self.assertRaises(HL7ValidationError):
            self.handler.parse_admit_message(segments)

    def test_parse_admit_pid_invalid_dob(self):
        segments = self.handler.parse_segments(HL7_PID_INVALID_DOB)
        with self.assertRaises(HL7ValidationError):
            self.handler.parse_admit_message(segments)


if __name__ == "__main__":
    unittest.main()
