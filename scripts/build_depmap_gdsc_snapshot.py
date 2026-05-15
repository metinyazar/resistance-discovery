import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import duckdb


RAW_DIR = Path("data/depmap_raw")
DEFAULT_OUTPUT = Path("data/depmap_processed/gdsc_variant_response_snapshot.csv")
HIGH_IMPACT_FLAGS = (
    "hotspot",
    "civic_annotated",
    "hess_driver",
    "oncogene_high_impact",
    "tumor_suppressor_high_impact",
    "copy_number_driver",
    "fusion_detected",
    "fusion_high_confidence",
    "fusion_in_frame",
)
DEFAULT_COPY_NUMBER_GENES = (
    "ERBB2",
    "MET",
    "MYC",
    "MYCN",
    "CCNE1",
    "CDK4",
    "MDM2",
    "EGFR",
    "FGFR1",
    "FGFR2",
    "CCND1",
    "MCL1",
    "CDKN2A",
    "PTEN",
    "RB1",
    "NF1",
    "SMAD4",
    "APC",
)
DEFAULT_EXPRESSION_GENES = (
    "ESR1",
    "CD274",
    "ERBB2",
    "EGFR",
    "MET",
    "ALK",
    "RET",
    "NTRK1",
    "NTRK2",
    "NTRK3",
    "AR",
    "PGR",
    "AXL",
    "FGFR1",
    "FGFR2",
    "FGFR3",
    "KIT",
    "VEGFA",
    "FOLR1",
)
DEFAULT_FUSION_GENES = (
    "ALK",
    "RET",
    "ROS1",
    "NTRK1",
    "NTRK2",
    "NTRK3",
    "FGFR2",
    "FGFR3",
    "BRAF",
    "RAF1",
    "NRG1",
    "NUTM1",
    "MET",
    "ERBB2",
)
AMPLIFICATION_DRIVER_GENES = {
    "ERBB2",
    "MET",
    "MYC",
    "MYCN",
    "CCNE1",
    "CDK4",
    "MDM2",
    "EGFR",
    "FGFR1",
    "FGFR2",
    "CCND1",
    "MCL1",
}
DELETION_DRIVER_GENES = {"CDKN2A", "PTEN", "RB1", "NF1", "SMAD4", "APC"}


@dataclass(frozen=True)
class BuildConfig:
    dose_response_path: Path
    model_path: Path
    mutations_path: Path
    output_path: Path
    min_mutant_models: int = 3
    min_control_models: int = 5
    min_abs_effect: float = 0.5
    genes: tuple[str, ...] = ()
    therapies: tuple[str, ...] = ()
    cancers: tuple[str, ...] = ()
    limit: int | None = None
    memory_limit: str = "3GB"
    copy_number_path: Path | None = None
    copy_number_genes: tuple[str, ...] = DEFAULT_COPY_NUMBER_GENES
    amplification_threshold: float = 6.0
    deletion_threshold: float = 0.5
    min_copy_number_models: int = 3
    expression_path: Path | None = None
    expression_genes: tuple[str, ...] = DEFAULT_EXPRESSION_GENES
    high_expression_quantile: float = 0.75
    low_expression_quantile: float = 0.25
    min_expression_models: int = 3
    fusion_path: Path | None = None
    fusion_supplementary_path: Path | None = None
    fusion_genes: tuple[str, ...] = DEFAULT_FUSION_GENES
    min_fusion_models: int = 2


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _normalize_terms(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value.strip().upper() for value in values if value.strip())


def _in_filter(column: str, values: tuple[str, ...]) -> str:
    terms = _normalize_terms(values)
    if not terms:
        return ""
    escaped_terms = [term.replace("'", "''") for term in terms]
    quoted = ", ".join("'" + term + "'" for term in escaped_terms)
    return f" AND upper({column}) IN ({quoted})"


def _approx_welch_p_value(
    mean_mutant: float,
    mean_control: float,
    var_mutant: float | None,
    var_control: float | None,
    mutant_count: int,
    control_count: int,
) -> float:
    if (
        var_mutant is None
        or var_control is None
        or mutant_count < 2
        or control_count < 2
        or var_mutant < 0
        or var_control < 0
    ):
        return 1.0

    stderr = math.sqrt((var_mutant / mutant_count) + (var_control / control_count))
    if stderr == 0:
        return 1.0

    # Normal approximation to a two-sided Welch test. This keeps the builder
    # dependency-light; effect size and counts remain the primary signal.
    z_score = abs((mean_mutant - mean_control) / stderr)
    return max(0.0, min(1.0, math.erfc(z_score / math.sqrt(2))))


def _response_class(effect_size: float, threshold: float) -> str:
    if effect_size <= -threshold:
        return "SENSITIVE"
    if effect_size >= threshold:
        return "RESISTANT"
    return "INSUFFICIENT"


def _quality_band(
    *,
    effect_size: float,
    p_value: float,
    mutant_count: int,
    control_count: int,
    variant_flags: str,
) -> str:
    flags = set(_split_flags(variant_flags))
    has_biology_flag = bool(flags.intersection(HIGH_IMPACT_FLAGS))
    strong_stats = abs(effect_size) >= 1.0 and p_value <= 0.05 and mutant_count >= 5 and control_count >= 10
    moderate_stats = abs(effect_size) >= 0.75 and mutant_count >= 3 and control_count >= 8

    if has_biology_flag and strong_stats:
        return "HIGH"
    if has_biology_flag or strong_stats or moderate_stats:
        return "MEDIUM"
    return "LOW"


def _quality_flags(
    *,
    p_value: float,
    mutant_count: int,
    control_count: int,
    variant_flags: str,
) -> str:
    flags = list(_split_flags(variant_flags))
    if mutant_count < 5:
        flags.append("small_mutant_n")
    if control_count < 10:
        flags.append("small_control_n")
    if p_value > 0.05:
        flags.append("weak_p_value")
    if not set(flags).intersection(HIGH_IMPACT_FLAGS):
        flags.append("no_driver_annotation")
    return ";".join(dict.fromkeys(flags))


def _copy_number_event_flags(gene_symbol: str, alteration: str, threshold: float) -> str:
    flags = [f"{alteration}_threshold_{threshold:g}"]
    if (
        alteration == "amplification"
        and gene_symbol in AMPLIFICATION_DRIVER_GENES
        or alteration == "deletion"
        and gene_symbol in DELETION_DRIVER_GENES
    ):
        flags.append("copy_number_driver")
    return ";".join(flags)


def _expression_event_flags(alteration: str, quantile: float) -> str:
    label = "high_expression" if alteration == "high expression" else "low_expression"
    return f"expression_profile;{label}_q{int(quantile * 100)}"


def _fusion_flags(confidence: str | None, reading_frame: str | None) -> str:
    flags = ["fusion_detected"]
    if str(confidence or "").lower() == "high":
        flags.append("fusion_high_confidence")
    if str(reading_frame or "").lower() == "in-frame":
        flags.append("fusion_in_frame")
    return ";".join(flags)


def _split_flags(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(flag.strip() for flag in value.split(";") if flag.strip())


def build_snapshot(config: BuildConfig) -> int:
    config.output_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(database=":memory:")
    con.execute("PRAGMA threads=2")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"PRAGMA memory_limit='{config.memory_limit}'")

    con.execute(
        f"""
        CREATE TEMP TABLE models AS
        SELECT
            ModelID,
            COALESCE(NULLIF(OncotreePrimaryDisease, ''), NULLIF(OncotreeLineage, ''), 'Unknown') AS cancer_type,
            COALESCE(NULLIF(OncotreeLineage, ''), 'unknown') AS lineage
        FROM read_csv_auto('{_sql_path(config.model_path)}', sample_size=20000)
        WHERE ModelID IS NOT NULL
        """
    )

    therapy_filter = _in_filter("DRUG_NAME", config.therapies)
    con.execute(
        f"""
        CREATE TEMP TABLE dose_response AS
        SELECT
            ARXSPAN_ID AS ModelID,
            DRUG_NAME AS therapy,
            DATASET AS dataset,
            TRY_CAST(Z_SCORE_PUBLISHED AS DOUBLE) AS response_metric
        FROM read_csv_auto('{_sql_path(config.dose_response_path)}', sample_size=20000)
        WHERE ARXSPAN_ID IS NOT NULL
          AND DRUG_NAME IS NOT NULL
          AND TRY_CAST(Z_SCORE_PUBLISHED AS DOUBLE) IS NOT NULL
          {therapy_filter}
        """
    )

    gene_filter = _in_filter("HugoSymbol", config.genes)
    con.execute(
        f"""
        CREATE TEMP TABLE mutation_models AS
        WITH source AS (
            SELECT
                ModelID,
                upper(HugoSymbol) AS gene_symbol,
                regexp_extract(ProteinChange, '^p\\.([A-Z][0-9]+[A-Z*])$', 1) AS alteration,
                bool_or(coalesce(TRY_CAST(Hotspot AS BOOLEAN), false)) AS is_hotspot,
                bool_or(CivicID IS NOT NULL AND TRIM(CAST(CivicID AS VARCHAR)) NOT IN ('', '0')) AS has_civic,
                bool_or(coalesce(TRY_CAST(HessDriver AS BOOLEAN), false)) AS is_hess_driver,
                bool_or(coalesce(TRY_CAST(OncogeneHighImpact AS BOOLEAN), false)) AS oncogene_high_impact,
                bool_or(coalesce(TRY_CAST(TumorSuppressorHighImpact AS BOOLEAN), false)) AS tumor_suppressor_high_impact,
                bool_or(coalesce(TRY_CAST(LikelyLoF AS BOOLEAN), false)) AS likely_lof
            FROM read_csv_auto(
                '{_sql_path(config.mutations_path)}',
                sample_size=20000,
                ignore_errors=true
            )
            WHERE ModelID IS NOT NULL
              AND HugoSymbol IS NOT NULL
              AND ProteinChange IS NOT NULL
              AND regexp_matches(ProteinChange, '^p\\.[A-Z][0-9]+[A-Z*]$')
              AND (IsDefaultEntryForModel IS NULL OR IsDefaultEntryForModel = 'Yes')
              {gene_filter}
            GROUP BY 1, 2, 3
        )
        SELECT
            ModelID,
            gene_symbol,
            alteration,
            concat_ws(
                ';',
                CASE WHEN is_hotspot THEN 'hotspot' END,
                CASE WHEN has_civic THEN 'civic_annotated' END,
                CASE WHEN is_hess_driver THEN 'hess_driver' END,
                CASE WHEN oncogene_high_impact THEN 'oncogene_high_impact' END,
                CASE WHEN tumor_suppressor_high_impact THEN 'tumor_suppressor_high_impact' END,
                CASE WHEN likely_lof THEN 'likely_lof' END
            ) AS variant_flags
        FROM source
        """
    )

    cancer_filter = _in_filter("m.cancer_type", config.cancers)
    con.execute(
        f"""
        CREATE TEMP TABLE profile_contexts AS
        SELECT
            mm.gene_symbol,
            mm.alteration,
            m.cancer_type,
            m.lineage,
            COUNT(DISTINCT mm.ModelID) AS mutant_model_count
        FROM mutation_models mm
        JOIN models m ON m.ModelID = mm.ModelID
        WHERE 1 = 1
          {cancer_filter}
        GROUP BY 1, 2, 3, 4
        HAVING COUNT(DISTINCT mm.ModelID) >= ?
        """,
        [config.min_mutant_models],
    )

    rows = []
    profile_context_rows = con.execute(
        """
        SELECT gene_symbol, alteration, cancer_type, lineage
        FROM profile_contexts
        ORDER BY cancer_type, gene_symbol, alteration
        """
    ).fetchall()

    for gene_symbol, alteration, cancer_type, lineage in profile_context_rows:
        rows.extend(
            con.execute(
                """
                WITH context_dose AS (
                    SELECT
                        d.ModelID,
                        d.therapy,
                        d.dataset,
                        d.response_metric,
                        m.cancer_type,
                        m.lineage
                    FROM dose_response d
                    JOIN models m ON m.ModelID = d.ModelID
                    WHERE m.cancer_type = ?
                ),
                stats AS (
                    SELECT
                        'small_variant' AS biomarker_type,
                        ? AS gene_symbol,
                        ? AS alteration,
                        ? AS cancer_type,
                        ? AS lineage,
                        cd.therapy,
                        string_agg(DISTINCT cd.dataset, '/') AS datasets,
                        COUNT(DISTINCT CASE WHEN mm.ModelID IS NOT NULL THEN cd.ModelID END) AS mutant_count,
                        COUNT(DISTINCT CASE WHEN mm.ModelID IS NULL THEN cd.ModelID END) AS control_count,
                        AVG(CASE WHEN mm.ModelID IS NOT NULL THEN cd.response_metric END) AS mutant_mean,
                        AVG(CASE WHEN mm.ModelID IS NULL THEN cd.response_metric END) AS control_mean,
                        VAR_SAMP(CASE WHEN mm.ModelID IS NOT NULL THEN cd.response_metric END) AS mutant_var,
                        VAR_SAMP(CASE WHEN mm.ModelID IS NULL THEN cd.response_metric END) AS control_var,
                        string_agg(DISTINCT NULLIF(mm.variant_flags, ''), ';') AS variant_flags
                    FROM context_dose cd
                    LEFT JOIN mutation_models mm
                      ON mm.ModelID = cd.ModelID
                     AND mm.gene_symbol = ?
                     AND mm.alteration = ?
                    GROUP BY cd.therapy
                )
                SELECT
                    biomarker_type,
                    gene_symbol,
                    alteration,
                    cancer_type,
                    lineage,
                    therapy,
                    datasets,
                    mutant_count,
                    control_count,
                    mutant_mean,
                    control_mean,
                    mutant_var,
                    control_var,
                    variant_flags,
                    mutant_mean - control_mean AS effect_size
                FROM stats
                WHERE mutant_count >= ?
                  AND control_count >= ?
                  AND ABS(mutant_mean - control_mean) >= ?
                """,
                [
                    cancer_type,
                    gene_symbol,
                    alteration,
                    cancer_type,
                    lineage,
                    gene_symbol,
                    alteration,
                    config.min_mutant_models,
                    config.min_control_models,
                    config.min_abs_effect,
                ],
            ).fetchall()
        )

    if config.copy_number_path and config.copy_number_path.exists():
        rows.extend(_build_copy_number_rows(con, config))

    if config.expression_path and config.expression_path.exists():
        rows.extend(_build_expression_rows(con, config))

    fusion_source = _fusion_source_path(config)
    if fusion_source:
        rows.extend(_build_fusion_rows(con, config, fusion_source))

    rows.sort(key=lambda row: (abs(row[14]), row[7], row[8]), reverse=True)
    if config.limit:
        rows = rows[: config.limit]

    fieldnames = [
        "profile_label",
        "gene_symbol",
        "biomarker_type",
        "alteration",
        "therapy",
        "therapy_class",
        "cancer_type",
        "lineage",
        "response_class",
        "sample_count",
        "mutant_count",
        "control_count",
        "mutant_mean_response",
        "control_mean_response",
        "response_metric",
        "effect_direction",
        "effect_size",
        "p_value",
        "quality_band",
        "quality_flags",
        "statement",
        "citation",
        "source",
    ]
    with config.output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            (
                biomarker_type,
                gene_symbol,
                alteration,
                cancer_type,
                lineage,
                therapy,
                datasets,
                mutant_count,
                control_count,
                mutant_mean,
                control_mean,
                mutant_var,
                control_var,
                variant_flags,
                effect_size,
            ) = row
            response_class = _response_class(effect_size, config.min_abs_effect)
            p_value = _approx_welch_p_value(
                mutant_mean,
                control_mean,
                mutant_var,
                control_var,
                mutant_count,
                control_count,
            )
            quality_band = _quality_band(
                effect_size=effect_size,
                p_value=p_value,
                mutant_count=mutant_count,
                control_count=control_count,
                variant_flags=variant_flags or "",
            )
            quality_flags = _quality_flags(
                p_value=p_value,
                mutant_count=mutant_count,
                control_count=control_count,
                variant_flags=variant_flags or "",
            )
            profile_label = alteration if biomarker_type == "fusion" else f"{gene_symbol} {alteration}"
            direction = "more sensitive" if response_class == "SENSITIVE" else "more resistant"
            effect_direction = "lower_z_score_more_sensitive" if effect_size < 0 else "higher_z_score_more_resistant"
            source_prefix = _source_prefix(biomarker_type)
            citation = _citation(biomarker_type)
            writer.writerow(
                {
                    "profile_label": profile_label,
                    "gene_symbol": gene_symbol,
                    "biomarker_type": biomarker_type,
                    "alteration": alteration,
                    "therapy": therapy.title(),
                    "therapy_class": "",
                    "cancer_type": cancer_type,
                    "lineage": str(lineage).lower(),
                    "response_class": response_class,
                    "sample_count": mutant_count + control_count,
                    "mutant_count": mutant_count,
                    "control_count": control_count,
                    "mutant_mean_response": round(mutant_mean, 6),
                    "control_mean_response": round(control_mean, 6),
                    "response_metric": "Z_SCORE_PUBLISHED",
                    "effect_direction": effect_direction,
                    "effect_size": round(effect_size, 6),
                    "p_value": round(p_value, 8),
                    "quality_band": quality_band,
                    "quality_flags": quality_flags,
                    "statement": (
                        f"{profile_label} {cancer_type} models were {direction} to {therapy.title()} "
                        f"than same-cancer non-mutant controls in DepMap/Sanger GDSC "
                        f"(mean z-score difference {effect_size:+.2f}; "
                        f"{mutant_count} mutant vs {control_count} control models; "
                        f"quality {quality_band})."
                    ),
                    "citation": citation,
                    "source": f"{source_prefix}_{datasets}",
                }
            )

    return len(rows)


def _source_prefix(biomarker_type: str) -> str:
    if biomarker_type == "copy_number":
        return "DepMap_GDSC_CN_WGS"
    if biomarker_type == "expression":
        return "DepMap_GDSC_EXPRESSION"
    if biomarker_type == "fusion":
        return "DepMap_GDSC_FUSION"
    return "DepMap_GDSC"


def _citation(biomarker_type: str) -> str:
    if biomarker_type == "copy_number":
        return "DepMap Public 26Q1 Model/Copy-number WGS files with Sanger GDSC1/GDSC2 dose response"
    if biomarker_type == "expression":
        return "DepMap Public 26Q1 Model/RNA expression TPM log2+1 files with Sanger GDSC1/GDSC2 dose response"
    if biomarker_type == "fusion":
        return "DepMap Public 26Q1 Model/Fusion files with Sanger GDSC1/GDSC2 dose response"
    return "DepMap Public 26Q1 Model/Mutation files with Sanger GDSC1/GDSC2 dose response"


def _build_copy_number_rows(con, config: BuildConfig) -> list[tuple]:
    gene_columns = _gene_columns(config.copy_number_path, config.copy_number_genes)
    if not gene_columns:
        return []

    selected_columns = [
        f'TRY_CAST("{column}" AS DOUBLE) AS "{gene}"'
        for gene, column in gene_columns.items()
    ]
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE cn_wide AS
        SELECT
            ModelID,
            {", ".join(selected_columns)}
        FROM read_csv_auto('{_sql_path(config.copy_number_path)}', sample_size=20000)
        WHERE ModelID IS NOT NULL
          AND (IsDefaultEntryForModel IS NULL OR IsDefaultEntryForModel = 'Yes')
        """
    )

    long_selects = [
        f"""
        SELECT ModelID, '{gene}' AS gene_symbol, "{gene}" AS copy_number
        FROM cn_wide
        WHERE "{gene}" IS NOT NULL
        """
        for gene in gene_columns
    ]
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE cn_gene_values AS
        {" UNION ALL ".join(long_selects)}
        """
    )

    event_selects = []
    for gene in gene_columns:
        amp_flags = _copy_number_event_flags(gene, "amplification", config.amplification_threshold)
        del_flags = _copy_number_event_flags(gene, "deletion", config.deletion_threshold)
        event_selects.extend(
            [
                f"""
                SELECT ModelID, gene_symbol, 'amplification' AS alteration, copy_number, '{amp_flags}' AS variant_flags
                FROM cn_gene_values
                WHERE gene_symbol = '{gene}' AND copy_number >= {config.amplification_threshold}
                """,
                f"""
                SELECT ModelID, gene_symbol, 'deletion' AS alteration, copy_number, '{del_flags}' AS variant_flags
                FROM cn_gene_values
                WHERE gene_symbol = '{gene}' AND copy_number <= {config.deletion_threshold}
                """,
            ]
        )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE copy_number_events AS
        {" UNION ALL ".join(event_selects)}
        """
    )

    cancer_filter = _in_filter("m.cancer_type", config.cancers)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE copy_number_contexts AS
        SELECT
            cne.gene_symbol,
            cne.alteration,
            m.cancer_type,
            m.lineage,
            string_agg(DISTINCT cne.variant_flags, ';') AS variant_flags,
            COUNT(DISTINCT cne.ModelID) AS event_model_count
        FROM copy_number_events cne
        JOIN models m ON m.ModelID = cne.ModelID
        WHERE 1 = 1
          {cancer_filter}
        GROUP BY 1, 2, 3, 4
        HAVING COUNT(DISTINCT cne.ModelID) >= ?
        """,
        [config.min_copy_number_models],
    )

    contexts = con.execute(
        """
        SELECT gene_symbol, alteration, cancer_type, lineage, variant_flags
        FROM copy_number_contexts
        ORDER BY cancer_type, gene_symbol, alteration
        """
    ).fetchall()

    rows = []
    for gene_symbol, alteration, cancer_type, lineage, variant_flags in contexts:
        rows.extend(
            con.execute(
                """
                WITH context_dose AS (
                    SELECT
                        d.ModelID,
                        d.therapy,
                        d.dataset,
                        d.response_metric,
                        m.cancer_type,
                        m.lineage
                    FROM dose_response d
                    JOIN models m ON m.ModelID = d.ModelID
                    WHERE m.cancer_type = ?
                ),
                stats AS (
                    SELECT
                        'copy_number' AS biomarker_type,
                        ? AS gene_symbol,
                        ? AS alteration,
                        ? AS cancer_type,
                        ? AS lineage,
                        cd.therapy,
                        string_agg(DISTINCT cd.dataset, '/') AS datasets,
                        COUNT(DISTINCT CASE WHEN cne.ModelID IS NOT NULL THEN cd.ModelID END) AS mutant_count,
                        COUNT(DISTINCT CASE WHEN cne.ModelID IS NULL THEN cd.ModelID END) AS control_count,
                        AVG(CASE WHEN cne.ModelID IS NOT NULL THEN cd.response_metric END) AS mutant_mean,
                        AVG(CASE WHEN cne.ModelID IS NULL THEN cd.response_metric END) AS control_mean,
                        VAR_SAMP(CASE WHEN cne.ModelID IS NOT NULL THEN cd.response_metric END) AS mutant_var,
                        VAR_SAMP(CASE WHEN cne.ModelID IS NULL THEN cd.response_metric END) AS control_var,
                        ? AS variant_flags
                    FROM context_dose cd
                    JOIN cn_gene_values cng
                      ON cng.ModelID = cd.ModelID
                     AND cng.gene_symbol = ?
                    LEFT JOIN copy_number_events cne
                      ON cne.ModelID = cd.ModelID
                     AND cne.gene_symbol = ?
                     AND cne.alteration = ?
                    GROUP BY cd.therapy
                )
                SELECT
                    biomarker_type,
                    gene_symbol,
                    alteration,
                    cancer_type,
                    lineage,
                    therapy,
                    datasets,
                    mutant_count,
                    control_count,
                    mutant_mean,
                    control_mean,
                    mutant_var,
                    control_var,
                    variant_flags,
                    mutant_mean - control_mean AS effect_size
                FROM stats
                WHERE mutant_count >= ?
                  AND control_count >= ?
                  AND ABS(mutant_mean - control_mean) >= ?
                """,
                [
                    cancer_type,
                    gene_symbol,
                    alteration,
                    cancer_type,
                    lineage,
                    variant_flags or "",
                    gene_symbol,
                    gene_symbol,
                    alteration,
                    config.min_copy_number_models,
                    config.min_control_models,
                    config.min_abs_effect,
                ],
            ).fetchall()
        )
    return rows


def _build_expression_rows(con, config: BuildConfig) -> list[tuple]:
    gene_columns = _gene_columns(config.expression_path, config.expression_genes)
    if not gene_columns:
        return []

    selected_columns = [
        f'TRY_CAST("{column}" AS DOUBLE) AS "{gene}"'
        for gene, column in gene_columns.items()
    ]
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE expression_wide AS
        SELECT
            ModelID,
            {", ".join(selected_columns)}
        FROM read_csv_auto('{_sql_path(config.expression_path)}', sample_size=20000)
        WHERE ModelID IS NOT NULL
          AND (IsDefaultEntryForModel IS NULL OR IsDefaultEntryForModel = 'Yes')
        """
    )

    long_selects = [
        f"""
        SELECT ModelID, '{gene}' AS gene_symbol, "{gene}" AS expression_value
        FROM expression_wide
        WHERE "{gene}" IS NOT NULL
        """
        for gene in gene_columns
    ]
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE expression_gene_values AS
        {" UNION ALL ".join(long_selects)}
        """
    )

    cancer_filter = _in_filter("m.cancer_type", config.cancers)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE expression_thresholds AS
        SELECT
            egv.gene_symbol,
            m.cancer_type,
            m.lineage,
            quantile_cont(egv.expression_value, ?) AS high_threshold,
            quantile_cont(egv.expression_value, ?) AS low_threshold,
            COUNT(DISTINCT egv.ModelID) AS expression_model_count
        FROM expression_gene_values egv
        JOIN models m ON m.ModelID = egv.ModelID
        WHERE 1 = 1
          {cancer_filter}
        GROUP BY 1, 2, 3
        HAVING COUNT(DISTINCT egv.ModelID) >= ?
        """,
        [
            config.high_expression_quantile,
            config.low_expression_quantile,
            config.min_expression_models + config.min_control_models,
        ],
    )

    high_flags = _expression_event_flags("high expression", config.high_expression_quantile)
    low_flags = _expression_event_flags("low expression", config.low_expression_quantile)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE expression_events AS
        SELECT
            egv.ModelID,
            egv.gene_symbol,
            et.cancer_type,
            et.lineage,
            'high expression' AS alteration,
            egv.expression_value,
            et.high_threshold AS threshold_value,
            '{high_flags}' AS variant_flags
        FROM expression_gene_values egv
        JOIN models m ON m.ModelID = egv.ModelID
        JOIN expression_thresholds et
          ON et.gene_symbol = egv.gene_symbol
         AND et.cancer_type = m.cancer_type
        WHERE egv.expression_value >= et.high_threshold

        UNION ALL

        SELECT
            egv.ModelID,
            egv.gene_symbol,
            et.cancer_type,
            et.lineage,
            'low expression' AS alteration,
            egv.expression_value,
            et.low_threshold AS threshold_value,
            '{low_flags}' AS variant_flags
        FROM expression_gene_values egv
        JOIN models m ON m.ModelID = egv.ModelID
        JOIN expression_thresholds et
          ON et.gene_symbol = egv.gene_symbol
         AND et.cancer_type = m.cancer_type
        WHERE egv.expression_value <= et.low_threshold
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE expression_contexts AS
        SELECT
            gene_symbol,
            alteration,
            cancer_type,
            lineage,
            string_agg(DISTINCT variant_flags, ';') AS variant_flags,
            COUNT(DISTINCT ModelID) AS event_model_count
        FROM expression_events
        GROUP BY 1, 2, 3, 4
        HAVING COUNT(DISTINCT ModelID) >= ?
        """,
        [config.min_expression_models],
    )

    contexts = con.execute(
        """
        SELECT gene_symbol, alteration, cancer_type, lineage, variant_flags
        FROM expression_contexts
        ORDER BY cancer_type, gene_symbol, alteration
        """
    ).fetchall()

    rows = []
    for gene_symbol, alteration, cancer_type, lineage, variant_flags in contexts:
        rows.extend(
            con.execute(
                """
                WITH context_dose AS (
                    SELECT
                        d.ModelID,
                        d.therapy,
                        d.dataset,
                        d.response_metric,
                        m.cancer_type,
                        m.lineage
                    FROM dose_response d
                    JOIN models m ON m.ModelID = d.ModelID
                    WHERE m.cancer_type = ?
                ),
                stats AS (
                    SELECT
                        'expression' AS biomarker_type,
                        ? AS gene_symbol,
                        ? AS alteration,
                        ? AS cancer_type,
                        ? AS lineage,
                        cd.therapy,
                        string_agg(DISTINCT cd.dataset, '/') AS datasets,
                        COUNT(DISTINCT CASE WHEN ee.ModelID IS NOT NULL THEN cd.ModelID END) AS mutant_count,
                        COUNT(DISTINCT CASE WHEN ee.ModelID IS NULL THEN cd.ModelID END) AS control_count,
                        AVG(CASE WHEN ee.ModelID IS NOT NULL THEN cd.response_metric END) AS mutant_mean,
                        AVG(CASE WHEN ee.ModelID IS NULL THEN cd.response_metric END) AS control_mean,
                        VAR_SAMP(CASE WHEN ee.ModelID IS NOT NULL THEN cd.response_metric END) AS mutant_var,
                        VAR_SAMP(CASE WHEN ee.ModelID IS NULL THEN cd.response_metric END) AS control_var,
                        ? AS variant_flags
                    FROM context_dose cd
                    JOIN expression_gene_values egv
                      ON egv.ModelID = cd.ModelID
                     AND egv.gene_symbol = ?
                    LEFT JOIN expression_events ee
                      ON ee.ModelID = cd.ModelID
                     AND ee.gene_symbol = ?
                     AND ee.alteration = ?
                     AND ee.cancer_type = cd.cancer_type
                    GROUP BY cd.therapy
                )
                SELECT
                    biomarker_type,
                    gene_symbol,
                    alteration,
                    cancer_type,
                    lineage,
                    therapy,
                    datasets,
                    mutant_count,
                    control_count,
                    mutant_mean,
                    control_mean,
                    mutant_var,
                    control_var,
                    variant_flags,
                    mutant_mean - control_mean AS effect_size
                FROM stats
                WHERE mutant_count >= ?
                  AND control_count >= ?
                  AND ABS(mutant_mean - control_mean) >= ?
                """,
                [
                    cancer_type,
                    gene_symbol,
                    alteration,
                    cancer_type,
                    lineage,
                    variant_flags or "",
                    gene_symbol,
                    gene_symbol,
                    alteration,
                    config.min_expression_models,
                    config.min_control_models,
                    config.min_abs_effect,
                ],
            ).fetchall()
        )
    return rows


def _fusion_source_path(config: BuildConfig) -> Path | None:
    if config.fusion_supplementary_path and config.fusion_supplementary_path.exists():
        return config.fusion_supplementary_path
    if config.fusion_path and config.fusion_path.exists():
        return config.fusion_path
    return None


def _build_fusion_rows(con, config: BuildConfig, fusion_source: Path) -> list[tuple]:
    columns = _csv_header(fusion_source)
    has_supplementary_fields = "Confidence" in columns and "ReadingFrame" in columns
    confidence_expr = "Confidence" if has_supplementary_fields else "'unknown' AS Confidence"
    reading_frame_expr = "ReadingFrame" if has_supplementary_fields else "'unknown' AS ReadingFrame"

    gene_filter = _fusion_gene_filter(config.fusion_genes)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE fusion_source AS
        SELECT
            ModelID,
            CanonicalFusionName,
            upper(regexp_extract(Gene1, '^([^ ]+)', 1)) AS gene1_symbol,
            upper(regexp_extract(Gene2, '^([^ ]+)', 1)) AS gene2_symbol,
            TRY_CAST(TotalReadsSupportingFusion AS DOUBLE) AS supporting_reads,
            TRY_CAST(FFPM AS DOUBLE) AS ffpm,
            {confidence_expr},
            {reading_frame_expr}
        FROM read_csv_auto('{_sql_path(fusion_source)}', sample_size=20000)
        WHERE ModelID IS NOT NULL
          AND CanonicalFusionName IS NOT NULL
          AND Gene1 IS NOT NULL
          AND Gene2 IS NOT NULL
          AND (IsDefaultEntryForModel IS NULL OR IsDefaultEntryForModel = 'Yes')
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE fusion_events AS
        WITH gene_events AS (
            SELECT
                ModelID,
                gene1_symbol AS gene_symbol,
                CanonicalFusionName,
                supporting_reads,
                ffpm,
                Confidence,
                ReadingFrame
            FROM fusion_source
            WHERE gene1_symbol IS NOT NULL

            UNION ALL

            SELECT
                ModelID,
                gene2_symbol AS gene_symbol,
                CanonicalFusionName,
                supporting_reads,
                ffpm,
                Confidence,
                ReadingFrame
            FROM fusion_source
            WHERE gene2_symbol IS NOT NULL
        )
        SELECT
            ModelID,
            gene_symbol,
            gene_symbol || ' fusion' AS alteration,
            string_agg(DISTINCT CanonicalFusionName, ';') AS fusion_names,
            MAX(supporting_reads) AS max_supporting_reads,
            MAX(ffpm) AS max_ffpm,
            bool_or(lower(CAST(Confidence AS VARCHAR)) = 'high') AS has_high_confidence,
            bool_or(lower(CAST(ReadingFrame AS VARCHAR)) = 'in-frame') AS has_in_frame
        FROM gene_events
        WHERE gene_symbol IS NOT NULL
          AND gene_symbol != ''
          {gene_filter}
        GROUP BY 1, 2, 3
        """
    )

    cancer_filter = _in_filter("m.cancer_type", config.cancers)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE fusion_contexts AS
        SELECT
            fe.gene_symbol,
            fe.alteration,
            m.cancer_type,
            m.lineage,
            string_agg(
                DISTINCT concat_ws(
                    ';',
                    'fusion_detected',
                    CASE WHEN fe.has_high_confidence THEN 'fusion_high_confidence' END,
                    CASE WHEN fe.has_in_frame THEN 'fusion_in_frame' END
                ),
                ';'
            ) AS variant_flags,
            COUNT(DISTINCT fe.ModelID) AS event_model_count
        FROM fusion_events fe
        JOIN models m ON m.ModelID = fe.ModelID
        WHERE 1 = 1
          {cancer_filter}
        GROUP BY 1, 2, 3, 4
        HAVING COUNT(DISTINCT fe.ModelID) >= ?
        """,
        [config.min_fusion_models],
    )

    contexts = con.execute(
        """
        SELECT gene_symbol, alteration, cancer_type, lineage, variant_flags
        FROM fusion_contexts
        ORDER BY cancer_type, gene_symbol, alteration
        """
    ).fetchall()

    rows = []
    for gene_symbol, alteration, cancer_type, lineage, variant_flags in contexts:
        rows.extend(
            con.execute(
                """
                WITH context_dose AS (
                    SELECT
                        d.ModelID,
                        d.therapy,
                        d.dataset,
                        d.response_metric,
                        m.cancer_type,
                        m.lineage
                    FROM dose_response d
                    JOIN models m ON m.ModelID = d.ModelID
                    WHERE m.cancer_type = ?
                ),
                stats AS (
                    SELECT
                        'fusion' AS biomarker_type,
                        ? AS gene_symbol,
                        ? AS alteration,
                        ? AS cancer_type,
                        ? AS lineage,
                        cd.therapy,
                        string_agg(DISTINCT cd.dataset, '/') AS datasets,
                        COUNT(DISTINCT CASE WHEN fe.ModelID IS NOT NULL THEN cd.ModelID END) AS mutant_count,
                        COUNT(DISTINCT CASE WHEN fe.ModelID IS NULL THEN cd.ModelID END) AS control_count,
                        AVG(CASE WHEN fe.ModelID IS NOT NULL THEN cd.response_metric END) AS mutant_mean,
                        AVG(CASE WHEN fe.ModelID IS NULL THEN cd.response_metric END) AS control_mean,
                        VAR_SAMP(CASE WHEN fe.ModelID IS NOT NULL THEN cd.response_metric END) AS mutant_var,
                        VAR_SAMP(CASE WHEN fe.ModelID IS NULL THEN cd.response_metric END) AS control_var,
                        ? AS variant_flags
                    FROM context_dose cd
                    LEFT JOIN fusion_events fe
                      ON fe.ModelID = cd.ModelID
                     AND fe.gene_symbol = ?
                    GROUP BY cd.therapy
                )
                SELECT
                    biomarker_type,
                    gene_symbol,
                    alteration,
                    cancer_type,
                    lineage,
                    therapy,
                    datasets,
                    mutant_count,
                    control_count,
                    mutant_mean,
                    control_mean,
                    mutant_var,
                    control_var,
                    variant_flags,
                    mutant_mean - control_mean AS effect_size
                FROM stats
                WHERE mutant_count >= ?
                  AND control_count >= ?
                  AND ABS(mutant_mean - control_mean) >= ?
                """,
                [
                    cancer_type,
                    gene_symbol,
                    alteration,
                    cancer_type,
                    lineage,
                    variant_flags or "",
                    gene_symbol,
                    config.min_fusion_models,
                    config.min_control_models,
                    config.min_abs_effect,
                ],
            ).fetchall()
        )
    return rows


def _fusion_gene_filter(genes: tuple[str, ...]) -> str:
    terms = _normalize_terms(genes)
    if not terms:
        return ""
    escaped_terms = [term.replace("'", "''") for term in terms]
    quoted = ", ".join("'" + term + "'" for term in escaped_terms)
    return f" AND gene_symbol IN ({quoted})"


def _csv_header(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return set(next(csv.reader(handle)))


def _gene_columns(path: Path, genes: tuple[str, ...]) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    requested = {gene.upper() for gene in genes}
    columns = {}
    for column in header:
        gene = column.split(" (", 1)[0].strip().upper()
        if gene in requested and gene not in columns:
            columns[gene] = column
    return columns


def _split_csv_arg(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a normalized small-variant drug-response support snapshot from DepMap/Sanger GDSC files."
    )
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--dose-response", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--mutations", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-mutant-models", type=int, default=3)
    parser.add_argument("--min-control-models", type=int, default=5)
    parser.add_argument("--min-abs-effect", type=float, default=0.5)
    parser.add_argument("--genes", help="Comma-separated HGNC symbols to include, e.g. BRAF,EGFR")
    parser.add_argument("--therapies", help="Comma-separated drug names to include, e.g. VEMURAFENIB")
    parser.add_argument("--cancers", help="Comma-separated cancer labels from Model.csv, e.g. Melanoma")
    parser.add_argument("--limit", type=int, help="Optional maximum number of output rows")
    parser.add_argument("--memory-limit", default="3GB", help="DuckDB memory limit, e.g. 3GB or 8GB")
    parser.add_argument("--copy-number", type=Path, help="Optional OmicsCNGeneWGS.csv path for copy-number support")
    parser.add_argument(
        "--copy-number-genes",
        default=",".join(DEFAULT_COPY_NUMBER_GENES),
        help="Comma-separated copy-number genes to include in the v1 panel",
    )
    parser.add_argument("--amplification-threshold", type=float, default=6.0)
    parser.add_argument("--deletion-threshold", type=float, default=0.5)
    parser.add_argument("--min-copy-number-models", type=int, default=3)
    parser.add_argument(
        "--expression",
        type=Path,
        help="Optional OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv path for expression support",
    )
    parser.add_argument(
        "--expression-genes",
        default=",".join(DEFAULT_EXPRESSION_GENES),
        help="Comma-separated expression genes to include in the v1 panel",
    )
    parser.add_argument("--high-expression-quantile", type=float, default=0.75)
    parser.add_argument("--low-expression-quantile", type=float, default=0.25)
    parser.add_argument("--min-expression-models", type=int, default=3)
    parser.add_argument("--fusion", type=Path, help="Optional OmicsFusionFiltered.csv path for fusion support")
    parser.add_argument(
        "--fusion-supplementary",
        type=Path,
        help="Optional OmicsFusionFilteredSupplementary.csv path for confidence/breakpoint-aware fusion support",
    )
    parser.add_argument(
        "--fusion-genes",
        default=",".join(DEFAULT_FUSION_GENES),
        help="Comma-separated fusion genes to include in the v1 panel",
    )
    parser.add_argument("--min-fusion-models", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = BuildConfig(
        dose_response_path=args.dose_response or args.raw_dir / "sanger-dose-response.csv",
        model_path=args.model or args.raw_dir / "Model.csv",
        mutations_path=args.mutations or args.raw_dir / "OmicsSomaticMutations.csv",
        output_path=args.output,
        min_mutant_models=args.min_mutant_models,
        min_control_models=args.min_control_models,
        min_abs_effect=args.min_abs_effect,
        genes=_split_csv_arg(args.genes),
        therapies=_split_csv_arg(args.therapies),
        cancers=_split_csv_arg(args.cancers),
        limit=args.limit,
        memory_limit=args.memory_limit,
        copy_number_path=args.copy_number or args.raw_dir / "OmicsCNGeneWGS.csv",
        copy_number_genes=_split_csv_arg(args.copy_number_genes),
        amplification_threshold=args.amplification_threshold,
        deletion_threshold=args.deletion_threshold,
        min_copy_number_models=args.min_copy_number_models,
        expression_path=args.expression or args.raw_dir / "OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv",
        expression_genes=_split_csv_arg(args.expression_genes),
        high_expression_quantile=args.high_expression_quantile,
        low_expression_quantile=args.low_expression_quantile,
        min_expression_models=args.min_expression_models,
        fusion_path=args.fusion or args.raw_dir / "OmicsFusionFiltered.csv",
        fusion_supplementary_path=args.fusion_supplementary or args.raw_dir / "OmicsFusionFilteredSupplementary.csv",
        fusion_genes=_split_csv_arg(args.fusion_genes),
        min_fusion_models=args.min_fusion_models,
    )
    for path in (config.dose_response_path, config.model_path, config.mutations_path):
        if not path.exists():
            raise FileNotFoundError(f"Required input file not found: {path}")

    count = build_snapshot(config)
    print(f"Wrote {count} GDSC support rows to {config.output_path}")


if __name__ == "__main__":
    main()
