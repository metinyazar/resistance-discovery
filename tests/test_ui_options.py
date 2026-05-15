from src.ui_options import build_small_variant, load_cancer_type_options, load_drug_options, load_gene_options


def test_gene_options_include_expected_hgnc_symbols():
    genes = load_gene_options()

    assert "EGFR" in genes
    assert "BRAF" in genes
    assert len(genes) > 19000


def test_drug_options_include_other_supported_examples():
    drugs = load_drug_options()

    assert "Gefitinib" in drugs
    assert "Vemurafenib" in drugs
    assert "Alectinib" in drugs
    assert "Dabrafenib" in drugs
    assert "Pyrimethamine" in drugs
    assert "Plx-4720" in drugs
    assert "BRAF inhibitor" in drugs
    assert "MEK inhibitor" in drugs


def test_cancer_type_options_include_demo_contexts():
    cancers = load_cancer_type_options()

    assert "NSCLC" in cancers
    assert "Melanoma" in cancers
    assert "Non-Small Cell Lung Cancer" in cancers
    assert "Colorectal Adenocarcinoma" in cancers
    assert "Mature B-Cell Neoplasms" in cancers


def test_build_small_variant_from_amino_acid_widgets():
    assert build_small_variant("V - Valine", 600, "E - Glutamic acid") == "V600E"
