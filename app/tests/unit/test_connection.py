import unittest
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from db.connection import get_connection

import logging
logging.disable(logging.CRITICAL)

class TestDatabaseConnection(unittest.TestCase):
    def setUp(self):
        
        self.tmpdir = TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"
        self.conn = get_connection(self.db_path)

    def tearDown(self):
        
        if self.conn:
            self.conn.close()
        
        self.tmpdir.cleanup()

    def test_connection_returns_connection_object(self):
        """get_connection should return an open sqlite3.Connection."""
        
        self.assertIsInstance(self.conn, sqlite3.Connection)

    def test_foreign_keys_are_enabled(self):
        """Foreign key enforcement should be enabled for each connection."""
        
        result = self.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(result, 1)

    def test_row_factory_is_sqlite_row(self):
        """Row factory should allow dict-like access to rows."""
        
        self.conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")
        self.conn.execute("DELETE FROM test")
        self.conn.execute("INSERT INTO test (id) VALUES (1)")
        row = self.conn.execute("SELECT id FROM test").fetchone()
        
        self.assertEqual(row["id"], 1)
