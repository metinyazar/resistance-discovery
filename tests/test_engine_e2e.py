import json
from pathlib import Path

from src.engine import analyze_variant_response
from src.types import LiteratureRecord


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _fixture(name):
    return json.loads((FIXTURES / name).read_text())


def _fake_post_factory(evidence_payload):
    def _fake_post(*args, **kwargs):
        query = kwargs["json"]["query"]
        if "assertions(" in query:
            return DummyResponse(_fixture("civic_assertions_empty.json"))
        return DummyResponse(evidence_payload)

    return _fake_post


def _paper(title, abstract, pmid="1"):
    return LiteratureRecord(
        source="fixture",
        pmid=pmid,
        doi="",
        title=title,
        journal="Fixture Journal",
        year="2026",
        authors="Fixture A",
        abstract=abstract,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    )


def _fake_literature(records):
    return {
        "query": "fixture query",
        "records": records,
        "diagnostics": {
            "europe_pmc_records": len(records),
            "pubmed_enabled": False,
            "pubmed_records": 0,
            "max_hits": 50,
        },
    }


def test_egfr_t790m_resistance(monkeypatch):
    monkeypatch.setattr("src.civic.requests.post", _fake_post_factory(_fixture("civic_egfr.json")))
    monkeypatch.setattr(
        "src.engine.search_literature",
        lambda query: _fake_literature(
            [
                _paper(
                    "EGFR T790M resistance to gefitinib in NSCLC",
                    "EGFR T790M is associated with resistance to gefitinib in NSCLC.",
                    "1001",
                )
            ]
        ),
    )
    result = analyze_variant_response("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    assert result["summary"].verdict == "RESISTANT"
    assert result["evidence_conclusion"].evidence_basis == "direct_curated"
    assert result["direct_curated"]
    assert result["direct_literature_claims"]


def test_egfr_t790m_ignores_related_sensitivity_literature(monkeypatch):
    monkeypatch.setattr("src.civic.requests.post", _fake_post_factory(_fixture("civic_egfr.json")))
    monkeypatch.setattr(
        "src.engine.search_literature",
        lambda query: _fake_literature(
            [
                _paper(
                    "EGFR-mutant NSCLC sensitivity to gefitinib",
                    "EGFR-mutant NSCLC showed sensitivity and response to gefitinib.",
                    "1009",
                )
            ]
        ),
    )
    result = analyze_variant_response("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    assert result["summary"].verdict == "RESISTANT"
    assert result["evidence_conclusion"].literature_verdict == "INSUFFICIENT"
    assert result["direct_literature_claims"] == []
    assert result["related_literature_claims"]


def test_braf_v600e_sensitivity(monkeypatch):
    monkeypatch.setattr("src.civic.requests.post", _fake_post_factory(_fixture("civic_braf.json")))
    monkeypatch.setattr(
        "src.engine.search_literature",
        lambda query: _fake_literature(
            [
                _paper(
                    "BRAF V600E melanoma sensitivity to vemurafenib",
                    "BRAF V600E melanoma shows sensitivity and response to vemurafenib.",
                    "1002",
                )
            ]
        ),
    )
    result = analyze_variant_response("BRAF", "small_variant", "V600E", "Vemurafenib", "melanoma")
    assert result["summary"].verdict == "SENSITIVE"
    assert result["evidence_conclusion"].database_verdict == "SENSITIVE"
    assert result["direct_literature_claims"]


def test_alk_fusion_sensitivity(monkeypatch):
    monkeypatch.setattr("src.civic.requests.post", _fake_post_factory(_fixture("civic_alk.json")))
    monkeypatch.setattr(
        "src.engine.search_literature",
        lambda query: _fake_literature(
            [
                _paper(
                    "ALK fusion NSCLC response to alectinib",
                    "ALK fusion in NSCLC is associated with sensitivity and response to alectinib.",
                    "1003",
                )
            ]
        ),
    )
    result = analyze_variant_response("ALK", "fusion", "ALK fusion", "Alectinib", "NSCLC")
    assert result["summary"].verdict == "SENSITIVE"
    assert result["direct_literature_claims"]


def test_supporting_only_is_insufficient(monkeypatch):
    monkeypatch.setattr("src.civic.requests.post", _fake_post_factory(_fixture("civic_empty.json")))
    monkeypatch.setattr("src.engine.search_literature", lambda query: _fake_literature([]))
    result = analyze_variant_response("ERBB2", "copy_number", "amplification", "Lapatinib", "breast cancer")
    assert result["summary"].verdict == "INSUFFICIENT"
    assert result["evidence_conclusion"].evidence_basis == "experimental_only"
    assert result["supporting_experimental"]


def test_unmatched_query_is_clean(monkeypatch):
    monkeypatch.setattr("src.civic.requests.post", _fake_post_factory(_fixture("civic_empty.json")))
    monkeypatch.setattr("src.engine.search_literature", lambda query: _fake_literature([]))
    result = analyze_variant_response("TP53", "small_variant", "R175H", "DrugX", "sarcoma")
    assert result["summary"].verdict == "INSUFFICIENT"
    assert result["direct_curated"] == []
    assert result["related_curated"] == []


def test_kras_g12c_sotorasib_literature_only_gold_standard(monkeypatch):
    monkeypatch.setattr("src.civic.requests.post", _fake_post_factory(_fixture("civic_empty.json")))
    monkeypatch.setattr(
        "src.engine.search_literature",
        lambda query: _fake_literature(
            [
                _paper(
                    "Sotorasib for lung cancers with KRAS p.G12C mutation",
                    "In patients with KRAS G12C-mutated NSCLC, sotorasib therapy led to objective response and durable clinical benefit.",
                    "34903582",
                )
            ]
        ),
    )
    result = analyze_variant_response("KRAS", "small_variant", "G12C", "Sotorasib", "NSCLC")
    assert result["summary"].verdict == "SENSITIVE"
    assert result["evidence_conclusion"].evidence_basis == "literature_only"
    assert result["direct_literature_claims"]


def test_esr1_mutation_aromatase_inhibitor_resistance_gold_standard(monkeypatch):
    monkeypatch.setattr("src.civic.requests.post", _fake_post_factory(_fixture("civic_empty.json")))
    monkeypatch.setattr(
        "src.engine.search_literature",
        lambda query: _fake_literature(
            [
                _paper(
                    "ESR1 mutation as a biomarker of aromatase inhibitor resistance in breast cancer",
                    "ESR1 mutation in metastatic breast cancer is a common mechanism of resistance to aromatase inhibitor therapy.",
                    "2001",
                )
            ]
        ),
    )
    result = analyze_variant_response("ESR1", "grouped_biomarker", "mutation", "aromatase inhibitor", "breast cancer")
    assert result["summary"].verdict == "RESISTANT"
    assert result["evidence_conclusion"].evidence_basis == "literature_only"
    assert result["direct_literature_claims"]
