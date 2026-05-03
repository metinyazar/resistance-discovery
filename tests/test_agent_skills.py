from src.engine import synthesize_verdict
from src.skills.evidence_interpreter import interpret_evidence
from src.skills.source_planner import plan_sources
from src.types import BiomarkerQuery, EvidenceRecord


def _record(response_class="RESISTANT", is_direct=True, source="civic_evidence"):
    return EvidenceRecord(
        source=source,
        evidence_kind="curated_predictive",
        profile_label="EGFR T790M",
        disease="Lung Non-small Cell Carcinoma",
        therapy="Gefitinib",
        therapy_aliases=[],
        response_class=response_class,
        evidence_level="B",
        rating=3,
        citation="EID239",
        statement="EGFR T790M is associated with gefitinib resistance.",
        profile_match_level="exact",
        therapy_match_level="exact",
        cancer_match_level="exact",
        is_direct=is_direct,
    )


def test_source_planner_fallback_has_expected_sources(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    plan = plan_sources(
        "EGFR T790M resistance to gefitinib in NSCLC",
        {
            "gene_symbol": "EGFR",
            "biomarker_type": "small_variant",
            "alteration": "T790M",
            "therapy": "Gefitinib",
            "cancer_type": "NSCLC",
        },
    )
    assert [source["name"] for source in plan["sources"]] == ["literature", "civic", "gdsc"]
    assert plan["sources"][0]["priority"] == "primary"


def test_evidence_interpreter_fallback_uses_deterministic_summary(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    direct = [_record()]
    summary = synthesize_verdict(direct, [], [])
    query = BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    interpretation = interpret_evidence(query, direct, [], [], summary)
    assert interpretation["verdict"] == "RESISTANT"
    assert interpretation["key_evidence"]
