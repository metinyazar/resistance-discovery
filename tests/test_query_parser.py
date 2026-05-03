from src.query_parser import coerce_parsed_query


def test_coerce_parsed_query_clamps_and_normalizes():
    parsed = coerce_parsed_query(
        {
            "gene_symbol": "egfr",
            "biomarker_type": "unknown_type",
            "alteration": "T790M",
            "therapy": "Gefitinib",
            "cancer_type": "NSCLC",
            "confidence": 120,
            "reasoning": "best guess",
        }
    )
    assert parsed.gene_symbol == "EGFR"
    assert parsed.biomarker_type == "grouped_biomarker"
    assert parsed.confidence == 100
