from app import EXAMPLE_QUERIES, _small_variant_parts


def test_small_variant_parts_parses_example_alterations():
    assert _small_variant_parts("V600E") == ("V", 600, "E")
    assert _small_variant_parts("T790M") == ("T", 790, "M")
    assert _small_variant_parts("not-a-variant") is None


def test_examples_include_copy_number_case():
    assert any(
        example["gene_symbol"] == "ERBB2"
        and example["biomarker_type"] == "copy_number"
        and example["alteration"] == "amplification"
        for example in EXAMPLE_QUERIES
    )


def test_examples_include_expression_case():
    assert any(
        example["gene_symbol"] == "ERBB2"
        and example["biomarker_type"] == "expression"
        and example["alteration"] == "high expression"
        for example in EXAMPLE_QUERIES
    )


def test_examples_include_fusion_case():
    assert any(
        example["gene_symbol"] == "ALK"
        and example["biomarker_type"] == "fusion"
        and example["alteration"] == "ALK fusion"
        for example in EXAMPLE_QUERIES
    )
