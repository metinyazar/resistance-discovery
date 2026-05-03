from src.skills.evidence_synthesizer import synthesize_literature_first
from src.types import EvidenceRecord, ExtractedClaim


def _claim(response_class="RESISTANT"):
    return ExtractedClaim(
        paper_id="1",
        claim_sentence="Example claim.",
        response_class=response_class,
        matched_terms=("EGFR", "T790M"),
        match_score=10,
    )


def _record(response_class="RESISTANT", source="civic_evidence"):
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
        is_direct=True,
    )


def test_literature_claim_with_database_agreement_increases_confidence():
    conclusion = synthesize_literature_first([_claim("RESISTANT"), _claim("RESISTANT")], [_record("RESISTANT")], [], [])

    assert conclusion.verdict == "RESISTANT"
    assert conclusion.confidence_band == "high"
    assert conclusion.supporting_database_count == 1


def test_literature_claim_with_database_disagreement_is_conflicting():
    conclusion = synthesize_literature_first([_claim("RESISTANT")], [_record("SENSITIVE")], [], [])

    assert conclusion.verdict == "CONFLICTING"
    assert conclusion.confidence_band == "low"


def test_database_only_is_insufficient_in_literature_first_mode():
    conclusion = synthesize_literature_first([], [_record("RESISTANT")], [], [])

    assert conclusion.verdict == "INSUFFICIENT"
    assert conclusion.supporting_database_count == 1
    assert conclusion.limitations
