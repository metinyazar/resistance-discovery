from src.normalization import normalize_query


def test_normalizes_small_variant():
    query, profile, context = normalize_query("egfr", "small_variant", "EGFR T790M", "Gefitinib", "NSCLC")
    assert query.gene_symbol == "EGFR"
    assert query.alteration == "T790M"
    assert profile.label == "EGFR T790M"
    assert context["cancer"]["canonical"] == "Lung Non-small Cell Carcinoma"


def test_normalizes_fusion():
    query, profile, _ = normalize_query("ALK", "fusion", "EML4/ALK fusion", "Alectinib", "NSCLC")
    assert query.alteration == "EML4-ALK fusion"
    assert profile.label == "EML4-ALK fusion"


def test_normalizes_copy_number():
    query, profile, _ = normalize_query("ERBB2", "copy_number", "HER2 amp", "Lapatinib", "breast cancer")
    assert query.alteration == "amplification"
    assert profile.label == "ERBB2 amplification"


def test_normalizes_expression():
    query, profile, _ = normalize_query("ESR1", "expression", "overexpression", "Fulvestrant", "breast carcinoma")
    assert query.alteration == "high expression"
    assert profile.label == "ESR1 high expression"


def test_normalizes_grouped_biomarker():
    query, profile, _ = normalize_query("EGFR", "grouped_biomarker", "activating mutation", "EGFR TKI", "NSCLC")
    assert query.alteration == "activating mutation"
    assert profile.label == "EGFR activating mutation"


def test_normalizes_targeted_therapy_classes():
    _, _, context = normalize_query("BRAF", "small_variant", "V600E", "PLX-4720", "Melanoma")
    assert context["therapy"]["canonical"] == "BRAF inhibitor"
    assert "dabrafenib" in context["therapy"]["aliases"]
    assert "plx-4720" in context["therapy"]["aliases"]
