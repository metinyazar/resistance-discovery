from src.skills.claim_extractor import direct_claims, extract_claim_from_sentence, extract_claims, related_claims
from src.skills.paper_ranker import score_paper
from src.types import BiomarkerQuery, LiteratureRecord


def _ranked(query, title="", abstract=""):
    paper = LiteratureRecord(
        source="fixture",
        pmid="1",
        doi="",
        title=title,
        journal="Fixture",
        year="2026",
        authors="Tester",
        abstract=abstract,
        url="",
    )
    return score_paper(query, paper)


def test_resistance_sentence_detected():
    query = BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    sentence = "EGFR T790M is associated with resistance to gefitinib in NSCLC."

    claim = extract_claim_from_sentence(query, _ranked(query, abstract=sentence), sentence)

    assert claim.response_class == "RESISTANT"
    assert claim.claim_match_level == "direct_claim"


def test_sensitivity_sentence_detected():
    query = BiomarkerQuery("BRAF", "small_variant", "V600E", "BRAF inhibitor", "Melanoma")
    sentence = "BRAF V600E melanoma showed sensitivity and response to vemurafenib."

    claim = extract_claim_from_sentence(query, _ranked(query, abstract=sentence), sentence)

    assert claim.response_class == "SENSITIVE"
    assert "vemurafenib" in {term.lower() for term in claim.matched_terms}
    assert claim.claim_match_level == "direct_claim"


def test_conflicting_sentence_detected():
    query = BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    sentence = "EGFR T790M NSCLC had mixed sensitivity and resistance to gefitinib."

    claim = extract_claim_from_sentence(query, _ranked(query, abstract=sentence), sentence)

    assert claim.response_class == "CONFLICTING"
    assert claim.claim_match_level == "direct_claim"


def test_no_direct_response_returns_none():
    query = BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    sentence = "EGFR T790M was detected in NSCLC samples treated with gefitinib."

    claim = extract_claim_from_sentence(query, _ranked(query, abstract=sentence), sentence)

    assert claim is None


def test_gene_level_sensitivity_without_exact_small_variant_is_related():
    query = BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    sentence = "EGFR-mutant NSCLC showed sensitivity and response to gefitinib."

    claim = extract_claim_from_sentence(query, _ranked(query, abstract=sentence), sentence)

    assert claim.response_class == "SENSITIVE"
    assert claim.claim_match_level == "related_claim"
    assert "missing_exact_alteration" in claim.review_flags
    assert "gene_level_only" in claim.review_flags


def test_alk_positive_language_is_direct_for_fusion_query():
    query = BiomarkerQuery("ALK", "fusion", "ALK fusion", "Alectinib", "NSCLC")
    sentence = "ALK-positive NSCLC showed response to alectinib."

    claim = extract_claim_from_sentence(query, _ranked(query, abstract=sentence), sentence)

    assert claim.response_class == "SENSITIVE"
    assert claim.claim_match_level == "direct_claim"


def test_direct_and_related_claim_helpers_split_claims():
    query = BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    ranked = _ranked(
        query,
        abstract=(
            "EGFR T790M is associated with resistance to gefitinib in NSCLC. "
            "EGFR-mutant NSCLC showed sensitivity to gefitinib."
        ),
    )

    claims = extract_claims(query, [ranked])

    assert len(direct_claims(claims)) == 1
    assert len(related_claims(claims)) == 1
