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
            mutant_count INTEGER,
            control_count INTEGER,
            mutant_mean_response REAL,
            control_mean_response REAL,
            response_metric TEXT,
            effect_direction TEXT,
            effect_size REAL,
            p_value REAL,
            quality_band TEXT,
            quality_flags TEXT,
            statement TEXT,
            citation TEXT,
            source TEXT
        )
        """
    )
    _ensure_gdsc_columns(con)


def _ensure_gdsc_columns(con):
    existing = {
        row[1] for row in con.execute("PRAGMA table_info('gdsc_response_summary')").fetchall()
    }
    columns = {
        "mutant_count": "INTEGER",
        "control_count": "INTEGER",
        "mutant_mean_response": "REAL",
        "control_mean_response": "REAL",
        "response_metric": "TEXT",
        "effect_direction": "TEXT",
        "quality_band": "TEXT",
        "quality_flags": "TEXT",
    }
    for column, column_type in columns.items():
        if column not in existing:
            con.execute(f"ALTER TABLE gdsc_response_summary ADD COLUMN {column} {column_type}")


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
                sample_count, mutant_count, control_count, mutant_mean_response,
                control_mean_response, response_metric, effect_direction, effect_size,
                p_value, quality_band, quality_flags, statement, citation, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                   mutant_count, control_count, mutant_mean_response, control_mean_response,
                   response_metric, effect_direction, effect_size, p_value, quality_band,
                   quality_flags, statement, citation, source
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
        "mutant_count": row[10],
        "control_count": row[11],
        "mutant_mean_response": row[12],
        "control_mean_response": row[13],
        "response_metric": row[14],
        "effect_direction": row[15],
        "effect_size": row[16],
        "p_value": row[17],
        "quality_band": row[18] or "LOW",
        "quality_flags": row[19] or "",
        "statement": row[20],
        "citation": row[21],
        "source": row[22],
    }


def gdsc_tuple_from_row(row):
    sample_count = int(row["sample_count"])
    mutant_count = int(row.get("mutant_count") or 0)
    control_count = int(row.get("control_count") or max(sample_count - mutant_count, 0))
    return (
        row["profile_label"],
        row["gene_symbol"],
        row["biomarker_type"],
        row["alteration"],
        row["therapy"],
        row.get("therapy_class", ""),
        row["cancer_type"],
        row.get("lineage", ""),
        row["response_class"],
        sample_count,
        mutant_count,
        control_count,
        _optional_float(row.get("mutant_mean_response")),
        _optional_float(row.get("control_mean_response")),
        row.get("response_metric") or "",
        row.get("effect_direction") or "",
        float(row["effect_size"]),
        float(row["p_value"]),
        row.get("quality_band") or "LOW",
        row.get("quality_flags") or "",
        row["statement"],
        row["citation"],
        row["source"],
    )


def _optional_float(value):
    if value in (None, ""):
        return None
    return float(value)


def _seed_gdsc_rows():
    if not GDSC_SEED_PATH.exists():
        return []

    with GDSC_SEED_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [_gdsc_row_from_dict(row) for row in reader]


def _gdsc_row_from_dict(row):
    sample_count = int(row["sample_count"])
    mutant_count = int(row.get("mutant_count") or 0)
    control_count = int(row.get("control_count") or max(sample_count - mutant_count, 0))
    return {
        "profile_label": row["profile_label"],
        "gene_symbol": row["gene_symbol"],
        "biomarker_type": row["biomarker_type"],
        "alteration": row["alteration"],
        "therapy": row["therapy"],
        "therapy_class": row.get("therapy_class", ""),
        "cancer_type": row["cancer_type"],
        "lineage": row.get("lineage", ""),
        "response_class": row["response_class"],
        "sample_count": sample_count,
        "mutant_count": mutant_count,
        "control_count": control_count,
        "mutant_mean_response": _optional_float(row.get("mutant_mean_response")),
        "control_mean_response": _optional_float(row.get("control_mean_response")),
        "response_metric": row.get("response_metric", ""),
        "effect_direction": row.get("effect_direction", ""),
        "effect_size": float(row["effect_size"]),
        "p_value": float(row["p_value"]),
        "quality_band": row.get("quality_band", "LOW"),
        "quality_flags": row.get("quality_flags", ""),
        "statement": row["statement"],
        "citation": row["citation"],
        "source": row["source"],
    }


def _seed_gdsc_tuples():
    if not GDSC_SEED_PATH.exists():
        return []

    with GDSC_SEED_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            gdsc_tuple_from_row(row) for row in reader
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
            sample_count, mutant_count, control_count, mutant_mean_response,
            control_mean_response, response_metric, effect_direction, effect_size,
            p_value, quality_band, quality_flags, statement, citation, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
