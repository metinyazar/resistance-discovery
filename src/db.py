import csv
import json
from datetime import datetime, timedelta, timezone

import duckdb

from src.config import CIVIC_CACHE_TTL_HOURS, DB_PATH, GDSC_SEED_PATH

_CON = None


def get_connection():
    global _CON
    if _CON is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CON = duckdb.connect(str(DB_PATH))
        _init_tables(_CON)
        _seed_gdsc_if_empty(_CON)
    return _CON


def _init_tables(con):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS civic_query_cache (
            cache_key TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            queried_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS gdsc_response_summary (
            profile_label TEXT,
            gene_symbol TEXT,
            biomarker_type TEXT,
            alteration TEXT,
            therapy TEXT,
            therapy_class TEXT,
            cancer_type TEXT,
            lineage TEXT,
            response_class TEXT,
            sample_count INTEGER,
            effect_size REAL,
            p_value REAL,
            statement TEXT,
            citation TEXT,
            source TEXT
        )
        """
    )


def get_civic_cache(cache_key: str):
    try:
        con = get_connection()
        row = con.execute(
            "SELECT payload_json, queried_at FROM civic_query_cache WHERE cache_key = ?",
            [cache_key],
        ).fetchone()
    except duckdb.Error:
        return None

    if not row:
        return None

    queried_at = datetime.fromisoformat(row[1])
    if queried_at.tzinfo is None:
        queried_at = queried_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - queried_at > timedelta(hours=CIVIC_CACHE_TTL_HOURS):
        return None
    return json.loads(row[0])


def put_civic_cache(cache_key: str, payload: dict):
    try:
        con = get_connection()
        con.execute("DELETE FROM civic_query_cache WHERE cache_key = ?", [cache_key])
        con.execute(
            """
            INSERT INTO civic_query_cache(cache_key, payload_json, queried_at)
            VALUES (?, ?, ?)
            """,
            [cache_key, json.dumps(payload), datetime.now(timezone.utc).isoformat()],
        )
    except duckdb.Error:
        return


def replace_gdsc_snapshot(rows: list[tuple]):
    con = get_connection()
    con.execute("DELETE FROM gdsc_response_summary")
    if rows:
        con.executemany(
            """
            INSERT INTO gdsc_response_summary (
                profile_label, gene_symbol, biomarker_type, alteration,
                therapy, therapy_class, cancer_type, lineage, response_class,
                sample_count, effect_size, p_value, statement, citation, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def fetch_gdsc_rows():
    try:
        con = get_connection()
        rows = con.execute(
            """
            SELECT profile_label, gene_symbol, biomarker_type, alteration, therapy,
                   therapy_class, cancer_type, lineage, response_class, sample_count,
                   effect_size, p_value, statement, citation, source
            FROM gdsc_response_summary
            """
        ).fetchall()
        return [_gdsc_row_from_tuple(row) for row in rows]
    except duckdb.Error:
        return _seed_gdsc_rows()


def _gdsc_row_from_tuple(row):
    return {
        "profile_label": row[0],
        "gene_symbol": row[1],
        "biomarker_type": row[2],
        "alteration": row[3],
        "therapy": row[4],
        "therapy_class": row[5],
        "cancer_type": row[6],
        "lineage": row[7],
        "response_class": row[8],
        "sample_count": row[9],
        "effect_size": row[10],
        "p_value": row[11],
        "statement": row[12],
        "citation": row[13],
        "source": row[14],
    }


def _seed_gdsc_rows():
    if not GDSC_SEED_PATH.exists():
        return []

    with GDSC_SEED_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            {
                "profile_label": row["profile_label"],
                "gene_symbol": row["gene_symbol"],
                "biomarker_type": row["biomarker_type"],
                "alteration": row["alteration"],
                "therapy": row["therapy"],
                "therapy_class": row["therapy_class"],
                "cancer_type": row["cancer_type"],
                "lineage": row["lineage"],
                "response_class": row["response_class"],
                "sample_count": int(row["sample_count"]),
                "effect_size": float(row["effect_size"]),
                "p_value": float(row["p_value"]),
                "statement": row["statement"],
                "citation": row["citation"],
                "source": row["source"],
            }
            for row in reader
        ]


def _seed_gdsc_tuples():
    if not GDSC_SEED_PATH.exists():
        return []

    with GDSC_SEED_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            (
                row["profile_label"],
                row["gene_symbol"],
                row["biomarker_type"],
                row["alteration"],
                row["therapy"],
                row["therapy_class"],
                row["cancer_type"],
                row["lineage"],
                row["response_class"],
                int(row["sample_count"]),
                float(row["effect_size"]),
                float(row["p_value"]),
                row["statement"],
                row["citation"],
                row["source"],
            )
            for row in reader
        ]


def _seed_gdsc_if_empty(con):
    row = con.execute("SELECT COUNT(*) FROM gdsc_response_summary").fetchone()
    if row[0] > 0 or not GDSC_SEED_PATH.exists():
        return

    rows = _seed_gdsc_tuples()

    con.executemany(
        """
        INSERT INTO gdsc_response_summary (
            profile_label, gene_symbol, biomarker_type, alteration,
            therapy, therapy_class, cancer_type, lineage, response_class,
            sample_count, effect_size, p_value, statement, citation, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
