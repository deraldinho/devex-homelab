import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path
from sqlite_uri_safety import readonly_uri

class SQLiteUriSafetyTests(unittest.TestCase):
    def test_reserved_chars_remain_filename(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"ledger #%& space.db"
            with closing(sqlite3.connect(str(p))) as con:
                con.execute("CREATE TABLE marker(n INTEGER)")
                con.execute("INSERT INTO marker VALUES (7)")
                con.commit()
            uri=readonly_uri(p)
            self.assertIn("%23%25%26%20",uri)
            with closing(sqlite3.connect(uri,uri=True)) as con:
                self.assertEqual(con.execute("SELECT n FROM marker").fetchone()[0],7)
                with self.assertRaises(sqlite3.OperationalError):
                    con.execute("INSERT INTO marker VALUES (8)")
    def test_missing_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(FileNotFoundError):
                readonly_uri(Path(root)/"absent.db")
    def test_direct_symlink_fails_closed_when_supported(self):
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/"target.db"
            sqlite3.connect(str(target)).close()
            link=Path(root)/"link.db"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("symlink not available on this Windows host")
            with self.assertRaises(ValueError):
                readonly_uri(link)
