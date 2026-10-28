import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from db.bootstrap import init_db


class TestInitDB(unittest.TestCase):

    def test_init_db_creates_database_file(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "hospital.db"
            history_path = Path("./data/history.csv")

            init_db(db_path, history_path)

            self.assertTrue(db_path.exists())

    def test_init_db_is_idempotent(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "hospital.db"
            history_path = Path("./data/history.csv")

            init_db(db_path, history_path)
            init_db(db_path, history_path)  # should not crash

            self.assertTrue(db_path.exists())
