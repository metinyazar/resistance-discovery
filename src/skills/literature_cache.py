import json
import sqlite3
import time
from pathlib import Path

from src.config import DATA_DIR

DEFAULT_LITERATURE_CACHE = DATA_DIR / "literature_cache.sqlite"


class LiteratureCache:
    def __init__(self, db_path: str | Path = DEFAULT_LITERATURE_CACHE):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv_cache (
                source TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                ts INTEGER NOT NULL,
                PRIMARY KEY (source, key)
            )
            """
        )
        self.conn.commit()

    def get(self, source: str, key: str, max_age_seconds: int = 60 * 60 * 24 * 14):
        row = self.conn.execute(
            "SELECT value, ts FROM kv_cache WHERE source = ? AND key = ?",
            [source, key],
        ).fetchone()
        if not row:
            return None
        value, ts = row
        if int(time.time()) - int(ts) > max_age_seconds:
            return None
        return value

    def set(self, source: str, key: str, value: str):
        self.conn.execute(
            """
            INSERT INTO kv_cache(source, key, value, ts)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source, key) DO UPDATE SET value = excluded.value, ts = excluded.ts
            """,
            [source, key, value, int(time.time())],
        )
        self.conn.commit()

    def get_json(self, source: str, key: str):
        value = self.get(source, key)
        return json.loads(value) if value else None

    def set_json(self, source: str, key: str, value):
        self.set(source, key, json.dumps(value))

    def close(self):
        self.conn.close()

