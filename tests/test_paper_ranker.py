from src.skills.paper_ranker import score_paper
from src.types import BiomarkerQuery, LiteratureRecord


def _paper(title, abstract):
    return LiteratureRecord(
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


def test_exact_gene_alteration_therapy_cancer_response_ranks_high():
    query = BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    ranked = score_paper(
        query,
        _paper(
            "EGFR T790M resistance to gefitinib in NSCLC",
            "EGFR T790M is associated with resistance to gefitinib in NSCLC.",
        ),
    )

    assert ranked.score >= 20
    assert ranked.has_direct_claim
    assert not ranked.needs_manual_review


def test_missing_alteration_ranks_lower():
    query = BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "NSCLC")
    exact = score_paper(
        query,
        _paper(
            "EGFR T790M resistance to gefitinib in NSCLC",
            "EGFR T790M is associated with resistance to gefitinib in NSCLC.",
        ),
    )
    missing = score_paper(
        query,
        _paper(
            "EGFR resistance to gefitinib in lung cancer",
            "EGFR-mutant NSCLC can be resistant to gefitinib.",
        ),
    )

    assert missing.score < exact.score
    assert not missing.mentions_alteration
    assert missing.needs_manual_review


def test_crispr_screen_is_flagged_but_not_required():
    query = BiomarkerQuery("BRAF", "small_variant", "V600E", "Vemurafenib", "melanoma")
    ranked = score_paper(
        query,
        _paper(
            "CRISPR screen identifies vemurafenib resistance mechanisms",
            "A genome-wide CRISPR screen in BRAF V600E melanoma models found resistance to vemurafenib.",
        ),
    )

    assert ranked.functional_screen_support
    assert ranked.has_direct_claim
