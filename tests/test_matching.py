from src.normalization import (
    build_molecular_profile,
    classify_cancer_match,
    classify_profile_match,
    classify_therapy_match,
    normalize_cancer_type,
    normalize_therapy,
)
from src.types import BiomarkerQuery


def test_profile_match_levels():
    profile = build_molecular_profile(
        BiomarkerQuery("EGFR", "small_variant", "T790M", "Gefitinib", "Lung Non-small Cell Carcinoma")
    )
    assert classify_profile_match(profile, "EGFR T790M") == "exact"
    assert classify_profile_match(profile, "T790M") == "grouped"
    assert classify_profile_match(profile, "EGFR exon 19 deletion") == "gene_only"


def test_therapy_match_levels():
    therapy_info = normalize_therapy("EGFR TKI")
    assert classify_therapy_match(therapy_info, "Gefitinib", ["Iressa"]) == "class"
    assert classify_therapy_match(therapy_info, "EGFR inhibitor", []) == "exact"


def test_cancer_match_levels():
    cancer_info = normalize_cancer_type("NSCLC")
    assert classify_cancer_match(cancer_info, "Lung Non-small Cell Carcinoma") == "exact"
    assert classify_cancer_match(cancer_info, "Lung Adenocarcinoma") == "related"
    assert classify_cancer_match(cancer_info, "Solid Tumor") == "broad"
