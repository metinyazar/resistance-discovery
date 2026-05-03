from src.skills.claim_extractor import extract_claim_from_sentence
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


def test_sensitivity_sentence_detected():
    query = BiomarkerQuery("BRAF", "small_variant", "V600E", "Vemurafenib", "melanoma")
    sentence = "BRAF V600E melanoma showed sensitivity and response to vemurafenib."

    claim = extract_claim_from_sentence(query, _ranked(query, abstract=sentence), sentence)

    assert claim.response_class == "SENSITIVE"


def test_conflicting_sentence_detected():
    query = BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    sentence = "EGFR T790M NSCLC had mixed sensitivity and resistance to gefitinib."

    claim = extract_claim_from_sentence(query, _ranked(query, abstract=sentence), sentence)

    assert claim.response_class == "CONFLICTING"


def test_no_direct_response_returns_none():
    query = BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    sentence = "EGFR T790M was detected in NSCLC samples treated with gefitinib."

    claim = extract_claim_from_sentence(query, _ranked(query, abstract=sentence), sentence)

    assert claim is None
