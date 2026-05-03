import duckdb

from src import db


def test_fetch_gdsc_rows_falls_back_to_seed_when_duckdb_is_locked(monkeypatch):
    def _locked_connection():
        raise duckdb.IOException("Conflicting lock is held")

    monkeypatch.setattr(db, "get_connection", _locked_connection)

    rows = db.fetch_gdsc_rows()

    assert rows
    assert any(row["profile_label"] == "BRAF V600E" for row in rows)


def test_civic_cache_returns_none_when_duckdb_is_locked(monkeypatch):
    def _locked_connection():
        raise duckdb.IOException("Conflicting lock is held")

    monkeypatch.setattr(db, "get_connection", _locked_connection)

    assert db.get_civic_cache("key") is None
    assert db.put_civic_cache("key", {"ok": True}) is None
