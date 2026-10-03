"""Local persistence. Printer credentials never appear in API responses."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from cryptography.fernet import Fernet


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        key = self.directory / 'credentials.key'
        if not key.exists():
            fd = os.open(key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(Fernet.generate_key())
        self.cipher = Fernet(key.read_bytes())
        self.path = self.directory / 'monitor.db'
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS printers (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, host TEXT NOT NULL,
                serial TEXT UNIQUE NOT NULL, model TEXT NOT NULL DEFAULT '',
                access_code TEXT NOT NULL, camera TEXT NOT NULL DEFAULT 'off');
            CREATE TABLE IF NOT EXISTS spools (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, brand TEXT NOT NULL DEFAULT '',
                material TEXT NOT NULL DEFAULT 'PLA', color TEXT NOT NULL DEFAULT '#22c55e',
                initial_g REAL NOT NULL, remaining_g REAL NOT NULL,
                location TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
                printer_id INTEGER REFERENCES printers(id) ON DELETE SET NULL,
                slot TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, printer_id INTEGER REFERENCES printers(id) ON DELETE CASCADE,
                name TEXT, state TEXT, observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY, printer_id INTEGER REFERENCES printers(id) ON DELETE CASCADE,
                bed REAL, nozzle REAL, progress REAL, observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS samples_printer_time ON samples(printer_id, observed_at);
            ''')
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def rows(self, sql, args=()):
        with self.connect() as db:
            return [dict(r) for r in db.execute(sql, args)]

    def secret(self, row):
        return self.cipher.decrypt(row['access_code'].encode()).decode()

    def encrypt(self, value):
        return self.cipher.encrypt(value.encode()).decode()
