from src.skills.evidence_synthesizer import synthesize_database_primary
from src.types import EvidenceRecord, ExtractedClaim


def _claim(response_class="RESISTANT"):
    return ExtractedClaim(
        paper_id="1",
        claim_sentence="Example claim.",
        response_class=response_class,
        matched_terms=("EGFR", "T790M"),
        match_score=10,
    )


def _related_claim(response_class="SENSITIVE"):
    return ExtractedClaim(
        paper_id="2",
        claim_sentence="Related example claim.",
        response_class=response_class,
        matched_terms=("EGFR", "Gefitinib"),
        match_score=8,
        claim_match_level="related_claim",
        review_flags=("missing_exact_alteration",),
    )


def _record(response_class="RESISTANT", is_direct=True, source="civic_evidence"):
    return EvidenceRecord(
        source=source,
        evidence_kind="curated_predictive" if source != "GDSC_seed" else "experimental_support",
        profile_label="EGFR T790M",
        disease="Lung Non-small Cell Carcinoma",
        therapy="Gefitinib",
        therapy_aliases=[],
        response_class=response_class,
        evidence_level="A" if source != "GDSC_seed" else "preclinical",
        rating=4 if source != "GDSC_seed" else None,
        citation="EID1",
        statement="Example",
        profile_match_level="exact",
        therapy_match_level="exact",
        cancer_match_level="exact",
        is_direct=is_direct,
    )


def test_direct_database_evidence_drives_verdict_and_literature_raises_confidence():
    conclusion = synthesize_database_primary([_claim("RESISTANT"), _claim("RESISTANT")], [_record("RESISTANT")], [], [])

    assert conclusion.verdict == "RESISTANT"
    assert conclusion.confidence_band == "high"
    assert conclusion.evidence_basis == "direct_curated"
    assert conclusion.database_support_count == 1
    assert conclusion.literature_support_count == 2


def test_database_literature_disagreement_is_conflicting():
    conclusion = synthesize_database_primary([_claim("RESISTANT")], [_record("SENSITIVE")], [], [])

    assert conclusion.verdict == "CONFLICTING"
    assert conclusion.confidence_band == "low"
    assert conclusion.conflicting_count == 1


def test_database_only_can_still_drive_low_or_moderate_verdict():
    conclusion = synthesize_database_primary([], [_record("RESISTANT")], [], [])

    assert conclusion.verdict == "RESISTANT"
    assert conclusion.evidence_basis == "direct_curated"
    assert conclusion.literature_support_count == 0
    assert conclusion.limitations


def test_literature_only_gets_verdict_with_literature_basis():
    conclusion = synthesize_database_primary([_claim("SENSITIVE")], [], [], [])

    assert conclusion.verdict == "SENSITIVE"
    assert conclusion.evidence_basis == "literature_only"
    assert conclusion.confidence_band in {"low", "moderate"}


def test_experimental_only_is_insufficient():
    conclusion = synthesize_database_primary([], [], [], [_record("SENSITIVE", is_direct=False, source="GDSC_seed")])

    assert conclusion.verdict == "INSUFFICIENT"
    assert conclusion.evidence_basis == "experimental_only"
    assert conclusion.experimental_support_count == 1


def test_related_literature_does_not_contradict_database_when_excluded_from_synthesis():
    direct_claims_only = []

    conclusion = synthesize_database_primary(direct_claims_only, [_record("RESISTANT")], [], [])

    assert conclusion.verdict == "RESISTANT"
    assert conclusion.literature_verdict == "INSUFFICIENT"
    assert conclusion.conflicting_count == 0


def test_direct_contradictory_literature_creates_conflict():
    conclusion = synthesize_database_primary([_claim("SENSITIVE")], [_record("RESISTANT")], [], [])

    assert conclusion.verdict == "CONFLICTING"
    assert conclusion.conflicting_count == 1
