import csv
from pathlib import Path

from scripts.build_depmap_gdsc_snapshot import BuildConfig, build_snapshot


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "depmap"


def test_build_snapshot_outputs_sensitive_braf_v600e(tmp_path):
    output = tmp_path / "gdsc_snapshot.csv"
    count = build_snapshot(
        BuildConfig(
            dose_response_path=FIXTURE_DIR / "dose_response.csv",
            model_path=FIXTURE_DIR / "model.csv",
            mutations_path=FIXTURE_DIR / "mutations.csv",
            output_path=output,
            min_mutant_models=2,
            min_control_models=3,
            min_abs_effect=0.5,
            genes=("BRAF",),
            therapies=("VEMURAFENIB",),
        )
    )

    assert count == 1
    rows = list(csv.DictReader(output.open()))
    assert rows[0]["profile_label"] == "BRAF V600E"
    assert rows[0]["therapy"] == "Vemurafenib"
    assert rows[0]["cancer_type"] == "Melanoma"
    assert rows[0]["response_class"] == "SENSITIVE"
    assert float(rows[0]["effect_size"]) < 0
    assert int(rows[0]["sample_count"]) == 6
    assert int(rows[0]["mutant_count"]) == 2
    assert int(rows[0]["control_count"]) == 4
    assert rows[0]["response_metric"] == "Z_SCORE_PUBLISHED"
    assert rows[0]["effect_direction"] == "lower_z_score_more_sensitive"
    assert rows[0]["quality_band"] == "MEDIUM"
    assert "hotspot" in rows[0]["quality_flags"]
    assert "civic_annotated" in rows[0]["quality_flags"]


def test_build_snapshot_respects_effect_threshold(tmp_path):
    output = tmp_path / "gdsc_snapshot.csv"
    count = build_snapshot(
        BuildConfig(
            dose_response_path=FIXTURE_DIR / "dose_response.csv",
            model_path=FIXTURE_DIR / "model.csv",
            mutations_path=FIXTURE_DIR / "mutations.csv",
            output_path=output,
            min_mutant_models=2,
            min_control_models=3,
            min_abs_effect=2.0,
            genes=("BRAF",),
            therapies=("VEMURAFENIB",),
        )
    )

    assert count == 0
    assert list(csv.DictReader(output.open())) == []


def test_build_snapshot_outputs_copy_number_amplification(tmp_path):
    output = tmp_path / "gdsc_snapshot.csv"
    count = build_snapshot(
        BuildConfig(
            dose_response_path=FIXTURE_DIR / "dose_response.csv",
            model_path=FIXTURE_DIR / "model.csv",
            mutations_path=FIXTURE_DIR / "mutations.csv",
            copy_number_path=FIXTURE_DIR / "copy_number.csv",
            copy_number_genes=("ERBB2",),
            output_path=output,
            min_mutant_models=3,
            min_copy_number_models=2,
            min_control_models=3,
            min_abs_effect=0.5,
            genes=("BRAF",),
            therapies=("LAPATINIB",),
        )
    )

    rows = list(csv.DictReader(output.open()))
    cn_rows = [row for row in rows if row["biomarker_type"] == "copy_number"]

    assert count == 1
    assert cn_rows[0]["profile_label"] == "ERBB2 amplification"
    assert cn_rows[0]["therapy"] == "Lapatinib"
    assert cn_rows[0]["response_class"] == "SENSITIVE"
    assert int(cn_rows[0]["mutant_count"]) == 2
    assert int(cn_rows[0]["control_count"]) == 4
    assert cn_rows[0]["quality_band"] == "MEDIUM"
    assert "copy_number_driver" in cn_rows[0]["quality_flags"]


def test_build_snapshot_outputs_expression_support(tmp_path):
    output = tmp_path / "gdsc_snapshot.csv"
    count = build_snapshot(
        BuildConfig(
            dose_response_path=FIXTURE_DIR / "dose_response.csv",
            model_path=FIXTURE_DIR / "model.csv",
            mutations_path=FIXTURE_DIR / "mutations.csv",
            expression_path=FIXTURE_DIR / "expression.csv",
            expression_genes=("ESR1",),
            output_path=output,
            min_mutant_models=3,
            min_expression_models=2,
            min_control_models=3,
            min_abs_effect=0.5,
            genes=("BRAF",),
            therapies=("FULVESTRANT",),
        )
    )

    rows = list(csv.DictReader(output.open()))
    expression_rows = [row for row in rows if row["biomarker_type"] == "expression"]

    assert count == 2
    high_row = next(row for row in expression_rows if row["profile_label"] == "ESR1 high expression")
    assert high_row["therapy"] == "Fulvestrant"
    assert high_row["response_class"] == "SENSITIVE"
    assert int(high_row["mutant_count"]) == 2
    assert int(high_row["control_count"]) == 4
    assert high_row["quality_band"] == "LOW"
    assert "expression_profile" in high_row["quality_flags"]
    assert "high_expression_q75" in high_row["quality_flags"]


def test_build_snapshot_outputs_fusion_support(tmp_path):
    output = tmp_path / "gdsc_snapshot.csv"
    count = build_snapshot(
        BuildConfig(
            dose_response_path=FIXTURE_DIR / "dose_response.csv",
            model_path=FIXTURE_DIR / "model.csv",
            mutations_path=FIXTURE_DIR / "mutations.csv",
            fusion_supplementary_path=FIXTURE_DIR / "fusion.csv",
            fusion_genes=("BRAF",),
            output_path=output,
            min_mutant_models=3,
            min_fusion_models=2,
            min_control_models=3,
            min_abs_effect=0.5,
            genes=("EGFR",),
            therapies=("VEMURAFENIB",),
        )
    )

    rows = list(csv.DictReader(output.open()))
    fusion_rows = [row for row in rows if row["biomarker_type"] == "fusion"]

    assert count == 1
    assert fusion_rows[0]["profile_label"] == "BRAF fusion"
    assert fusion_rows[0]["therapy"] == "Vemurafenib"
    assert fusion_rows[0]["response_class"] == "SENSITIVE"
    assert int(fusion_rows[0]["mutant_count"]) == 2
    assert int(fusion_rows[0]["control_count"]) == 4
    assert "fusion_detected" in fusion_rows[0]["quality_flags"]
    assert "fusion_high_confidence" in fusion_rows[0]["quality_flags"]
    assert "fusion_in_frame" in fusion_rows[0]["quality_flags"]
