"""Durable fail-closed session journal; one outstanding dispatch per job."""
import json
import os
import sqlite3
from pathlib import Path

class SessionLedger:
    def __init__(self,path):
        self.path=Path(path)
    def read(self):
        try:
            value=json.loads(self.path.read_text(encoding="utf-8"))
            if value.get("state") not in ("creating","created","dispatch_uncertain","completed"):
                raise ValueError("invalid journal")
            return value
        except FileNotFoundError:
            return None
    def save(self,record):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix(".tmp")
        with open(temp,"w",encoding="utf-8") as output:
            json.dump(record,output,sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp,self.path)
    def acquire(self):
        """Crash-safe cross-process lock released when SQLite connection closes."""
        lock=self.path.with_suffix(self.path.suffix+".lock.sqlite3")
        lock.parent.mkdir(parents=True,exist_ok=True)
        conn=sqlite3.connect(str(lock),timeout=0,isolation_level=None)
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            conn.close()
            raise TimeoutError("session journal busy; retry read-only later") from exc
        return conn
    @staticmethod
    def release(conn):
        try:
            conn.rollback()
        finally:
            conn.close()
