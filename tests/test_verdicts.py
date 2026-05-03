from src.engine import synthesize_verdict
from src.types import EvidenceRecord


def _record(response_class, is_direct=True, source="civic_evidence"):
    return EvidenceRecord(
        source=source,
        evidence_kind="curated_predictive",
        profile_label="EGFR T790M",
        disease="Lung Non-small Cell Carcinoma",
        therapy="Gefitinib",
        therapy_aliases=[],
        response_class=response_class,
        evidence_level="A",
        rating=4,
        citation="EID1",
        statement="Example",
        profile_match_level="exact",
        therapy_match_level="exact",
        cancer_match_level="exact",
        is_direct=is_direct,
    )


def test_resistant_verdict():
    summary = synthesize_verdict([_record("RESISTANT"), _record("RESISTANT")], [], [])
    assert summary.verdict == "RESISTANT"
    assert summary.confidence_band == "high"


def test_conflicting_verdict():
    summary = synthesize_verdict([_record("RESISTANT"), _record("SENSITIVE")], [], [])
    assert summary.verdict == "CONFLICTING"


def test_insufficient_with_only_supporting():
    supporting = [_record("SENSITIVE", is_direct=False, source="GDSC_seed")]
    summary = synthesize_verdict([], [], supporting)
    assert summary.verdict == "INSUFFICIENT"
    assert summary.supporting_experimental_count == 1
