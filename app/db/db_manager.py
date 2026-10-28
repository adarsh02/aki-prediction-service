import logging
from contextlib import contextmanager
from typing import Any, Dict
from pathlib import Path
import sqlite3

from db.connection import get_connection
from db.db_excpetions import *

from metrics import *

logger = logging.getLogger(__name__)


class DBManager:
    """
    High-level database manager for patient and lab result persistence.

    All write operations are executed inside transactions.
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path
    
    @contextmanager
    def transaction(self):
        """
        Context manager that provides a database transaction.

        Commits on success, rolls back on failure.

        Yields:
            sqlite3.Connection: Active database connection.

        Raises:
            Exception: Re-raises any exception after rollback.
        """
        try:
            if self.db_path:
                conn = get_connection(db_path=self.db_path)
            else:
                conn = get_connection()
        except Exception as e:
            logger.exception("Failed to connect to DB")
            raise DBConnectionError(f"DB connection failed: {e}")

        try:
            yield conn
            conn.commit()
            logger.debug("Transaction committed")
        except Exception as e:
            conn.rollback()
            logger.exception("Transaction rolled back due to error")
            raise DBTransactionError(f"Transaction failed: {e}")
        finally:
            conn.close()

    # ---------- Patients ----------

    def upsert_patient(self, mrn, name, dob, sex, status) -> None:
        """
        Insert or update a patient record.

        Args:
            mrn: Medical record number.
            name: Patient name.
            dob: Date of birth.
            sex: Patient sex.
            status: Admission status.

        Raises:
            Exception: If database operation fails.
        """
        try:
            with self.transaction() as conn:
                if status == "ADMITTED":
                    conn.execute(
                        """
                        INSERT INTO patients (mrn, name, dob, sex, admission_status)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(mrn) DO UPDATE SET
                            name = excluded.name,
                            dob = excluded.dob,
                            sex = excluded.sex,
                            admission_status = excluded.admission_status,
                            last_updated = CURRENT_TIMESTAMP
                        """,
                        (mrn, name, dob, sex, status),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE patients SET
                            admission_status = ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE mrn = ?
                        """,
                        (status, mrn),
                    )
        except sqlite3.Error as e:
            logger.critical(f"Failed to upsert patient due to sqlite.Error: {e}", extra={"mrn": mrn})
            raise DBExecError("Failed to upsert patient")
            
        except Exception as e:
            logger.critical(f"Failed to upsert patient due to unknown error: {e}", extra={"mrn": mrn})
            raise DBExecError("Failed to upsert patient")

    # ---------- Lab Results ----------

    def insert_lab_result(self, mrn, test_name, test_time, value, processing_status) -> int:
        """
        Insert a lab result for a patient.

        Args:
            mrn: Medical record number.
            test_name: Name of the lab test.
            test_time: Timestamp of the test.
            value: Test result value.
            processing_status: Status of processing.

        Returns:
            int: ID of the inserted lab result.

        Raises:
            Exception: If insert fails.
        """
        try:
            with self.transaction() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO lab_results
                        (mrn, test_name, test_time, value, processing_status)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(mrn, test_time)
                    DO UPDATE SET
                        value = excluded.value
                    """,
                    (mrn, test_name, test_time, value, processing_status),
                )

            return cursor.lastrowid
        except Exception as e:
            logger.exception(
                "Failed to insert lab result",
                extra={"mrn": mrn, "test_name": test_name},
            )
            raise DBExecError(f"Failed to insert lab result: {e}", mrn=mrn, test_name=test_name)

    def get_patient_details_and_history(
        self, mrn: str, lab_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve patient details and lab history prior to a given lab result.

        Args:
            mrn: Medical record number.
            lab_result: Current lab result record.

        Returns:
            dict: Patient details, current result, and historical values.

        Raises:
            Exception: If query fails.
        """
        try:
            if self.db_path:
                conn = get_connection(db_path=self.db_path)
            else:
                conn = get_connection()

            patient_row = conn.execute(
                "SELECT mrn, dob, sex FROM patients WHERE mrn = ?", (mrn,)
            ).fetchone()

            patient_info = {
                "mrn": mrn,
                "dob": patient_row["dob"] if patient_row else None,
                "sex": patient_row["sex"] if patient_row else None,
            }

            history_rows = conn.execute(
                """
                SELECT value
                FROM lab_results
                WHERE mrn = ? AND test_time < ?
                ORDER BY test_time ASC
                """,
                (mrn, lab_result["test_time"]),
            ).fetchall()

            history_values = [r["value"] for r in history_rows]

            return {
                "patient": patient_info,
                "current_result": {
                    "result_id": lab_result["result_id"],
                    "value": lab_result["value"],
                    "test_time": lab_result["test_time"],
                },
                "history_values": history_values,
            }
        except Exception as e:
            logger.exception(
                "Failed to fetch patient details and history",
                extra={"mrn": mrn},
            )
            raise DBExecError(f"Failed to fetch patient details and history: {e}", mrn=mrn)
        finally:
            conn.close()

    def get_patient(self, mrn: int) -> Dict[str, Any] | None:
        """
        Retrieve a patient record by MRN.

        Args:
            mrn: Medical record number.

        Returns:
            dict | None: Dictionary containing patient attributes if found, else None.

        Raises:
            Exception: If the query fails.
        """
        if self.db_path:
            conn = get_connection(db_path=self.db_path)
        else:
            conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM patients WHERE mrn = ?", (mrn,)
            ).fetchone()
            
            return dict(row) if row else None
            
        except Exception as e:
            logger.exception(
                f"Failed to fetch patient: {e}", 
                extra={"mrn": mrn}
            )
            raise DBExecError("Failed to get patient")
        finally:
            conn.close()

    def get_pending_labs(self, mrn: int) -> list[Dict[str, Any]]:
        """
        Retrieve all pending lab results for a given patient.

        Args:
            mrn: Medical record number.

        Returns:
            list[dict]: List of dictionaries containing pending lab results ordered by time.

        Raises:
            Exception: If the query fails.
        """
        if self.db_path:
            conn = get_connection(db_path=self.db_path)
        else:
            conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT * FROM lab_results 
                WHERE mrn = ? AND processing_status = 'PENDING_ADMIT' 
                ORDER BY test_time ASC
                """, 
                (mrn,)
            ).fetchall()
            
            return [dict(row) for row in rows]
            
        except Exception:
            logger.exception(
                "Failed to fetch pending labs", 
                extra={"mrn": mrn}
            )
            raise
        finally:
            conn.close()
            
    def mark_lab_processed(self, result_id: int) -> None:
        """
        Update the processing status of a lab result to 'PROCESSED'.

        Args:
            result_id: The ID of the lab result.

        Raises:
            Exception: If the database update fails.
        """
        try:
            with self.transaction() as conn:
                conn.execute(
                    """
                    UPDATE lab_results 
                    SET processing_status = 'PROCESSED' 
                    WHERE result_id = ?
                    """,
                    (result_id,)
                )
        except Exception as e:
            logger.exception(
                f"Failed to mark lab as processed: {e}", 
                extra={"result_id": result_id}
            )
            raise DBExecError("Failed to mark lab processed")
