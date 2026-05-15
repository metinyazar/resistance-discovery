# TRACE

**Therapy Response And Cancer Evidence**

Database-primary research agent for questions of the form:

`mutation X in gene Y leads to resistance/sensitivity to therapy Z in cancer W`

## Scope

- Primary source: accepted predictive CIViC evidence and assertions
- Literature validation: published paper titles and abstracts from Europe PMC, with optional PubMed/NCBI E-utilities when `NCBI_EMAIL` is configured
- Experimental support: local GDSC-style cell-line snapshot
- Cache/storage: DuckDB at `data/variant_response.duckdb`
- Literature API cache: SQLite at `data/literature_cache.sqlite`
- Prompt-driven LLM skills live in `prompts/`
- Skill modules live in `src/skills/`
- `src/engine.py` orchestrates normalization, database retrieval, literature retrieval, paper ranking, claim extraction, synthesis, and optional report writing
- Research use only, not clinical decision support

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Evidence Flow

The default workflow does not require Claude or ChatGPT:

1. Normalize gene, biomarker type, alteration, therapy, and cancer context.
2. Retrieve curated CIViC database evidence and GDSC experimental support.
3. Search Europe PMC broadly, and PubMed when `NCBI_EMAIL` is configured.
4. Rank papers by transparent flags: gene, alteration, therapy, cancer, resistance/sensitivity language, direct claim, abstract availability, and CRISPR screen support.
5. Extract candidate claim sentences from titles and abstracts.
6. Synthesize a database-primary verdict. Literature validates, weakens, contradicts, or fills gaps when curated evidence is absent.

The structured Streamlit form includes:

- Gene symbol selector built from approved HGNC protein-coding genes in `data/hgnc_protein_coding_genes.csv`
- Drug selector from `data/drug_options.csv`, with an `Other` option for manual drug entry
- Small-variant builder for amino-acid substitution inputs such as `V600E`
- Cancer-type selector from `data/cancer_type_options.csv`

## Optional LLM Mode

The app mirrors the `knockout-discovery` structure but keeps LLM calls optional:

- `prompts/*.md` store reusable LLM instructions
- `src/skills/query_parser.py` parses free-text biomarker questions
- `src/skills/literature_search.py` retrieves titles and abstracts
- `src/skills/paper_ranker.py` scores literature hits
- `src/skills/claim_extractor.py` extracts candidate resistance/sensitivity sentences
- `src/skills/database_support.py` attaches CIViC and GDSC records
- `src/skills/evidence_interpreter.py` interprets resistance/sensitivity/adverse/conflicting evidence
- `src/skills/literature_context.py` generates biological context
- `src/skills/report_writer.py` writes the final narrative report

Set `ANTHROPIC_API_KEY` in a local `.env` file or shell environment to enable free-text parsing and narrative reporting. Without it, the structured manual form still works.

To enable optional PubMed/NCBI E-utilities, create `.env` from `.env.example` and set:

```bash
NCBI_EMAIL=your.email@example.com
```

Do not commit `.env`; it is ignored by git.

## GDSC Snapshot

The app seeds a small bundled experimental snapshot from `data/gdsc_seed.csv` so the UI works immediately.

Downloaded DepMap/Sanger files should be placed in:

```text
data/depmap_raw/
```

For small-variant support, the required files are:

- `sanger-dose-response.csv`
- `Model.csv`
- `OmicsSomaticMutations.csv`

For copy-number support, also add:

- `OmicsCNGeneWGS.csv`

Build a normalized DepMap/GDSC support snapshot:

```bash
python scripts/build_depmap_gdsc_snapshot.py \
  --output data/depmap_processed/gdsc_variant_response_snapshot.csv
```

For a faster targeted build:

```bash
python scripts/build_depmap_gdsc_snapshot.py \
  --genes BRAF \
  --therapies DABRAFENIB \
  --cancers Melanoma \
  --output data/depmap_processed/gdsc_braf_dabrafenib_smoke.csv
```

Load a normalized snapshot into DuckDB:

```bash
python scripts/load_gdsc_snapshot.py data/depmap_processed/gdsc_variant_response_snapshot.csv
```

Expected CSV columns:

`profile_label,gene_symbol,biomarker_type,alteration,therapy,therapy_class,cancer_type,lineage,response_class,sample_count,effect_size,p_value,statement,citation,source`

Newer DepMap/GDSC snapshots also include quality metadata:

- `mutant_count`, `control_count`: model counts behind the comparison
- `mutant_mean_response`, `control_mean_response`: mean `Z_SCORE_PUBLISHED` values
- `effect_direction`: lower z-score is interpreted as greater sensitivity
- `quality_band`: `HIGH`, `MEDIUM`, or `LOW`
- `quality_flags`: transparent reasons such as `hotspot`, `civic_annotated`, `hess_driver`, `copy_number_driver`, `expression_profile`, `small_mutant_n`, or `weak_p_value`

Quality thresholds:

- `HIGH`: requires biological annotation plus strong statistics.
- Biological annotation means at least one of `hotspot`, `civic_annotated`, `hess_driver`, `oncogene_high_impact`, `tumor_suppressor_high_impact`, or `copy_number_driver`.
- Strong statistics means `abs(effect_size) >= 1.0`, `p_value <= 0.05`, `mutant_count >= 5`, and `control_count >= 10`.
- `MEDIUM`: assigned when there is biological annotation, strong statistics, or moderate statistics.
- Moderate statistics means `abs(effect_size) >= 0.75`, `mutant_count >= 3`, and `control_count >= 8`.
- `LOW`: assigned to all remaining rows.

Quality flags:

- `small_mutant_n`: `mutant_count < 5`
- `small_control_n`: `control_count < 10`
- `weak_p_value`: `p_value > 0.05`
- `no_driver_annotation`: no biological annotation flag was found

These bands are pragmatic interpretation aids for preclinical evidence, not clinical evidence grades.

Copy-number support:

- The v1 builder uses `OmicsCNGeneWGS.csv`.
- Amplification threshold: linear copy number `>= 6.0`.
- Deletion threshold: linear copy number `<= 0.5`.
- The default v1 copy-number panel includes common actionable genes such as `ERBB2`, `MET`, `MYC`, `MYCN`, `CCNE1`, `CDK4`, `MDM2`, `EGFR`, `FGFR1`, `FGFR2`, `CCND1`, `MCL1`, `CDKN2A`, `PTEN`, `RB1`, `NF1`, `SMAD4`, and `APC`.
- Copy-number evidence is labeled as `copy_number` and remains preclinical experimental support.

Expression support:

- The v1 builder uses `OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv` when present.
- `high expression` means models in the top quartile for that gene within the same cancer type.
- `low expression` means models in the bottom quartile for that gene within the same cancer type.
- The default v1 expression panel includes selected actionable/context genes such as `ESR1`, `CD274`, `ERBB2`, `EGFR`, `MET`, `ALK`, `RET`, `NTRK1`, `NTRK2`, `NTRK3`, `AR`, `PGR`, `AXL`, `FGFR1`, `FGFR2`, `FGFR3`, `KIT`, `VEGFA`, and `FOLR1`.
- Expression evidence is labeled as `expression`, usually conservative/low-confidence, and remains preclinical experimental support.

Fusion support:

- The v1 builder uses `OmicsFusionFilteredSupplementary.csv` when present, otherwise `OmicsFusionFiltered.csv`.
- Fusion rows are gene-level events. For example, any qualifying fusion with `ALK` as either partner is summarized as `ALK fusion`.
- Supplementary fields add transparent flags such as `fusion_high_confidence` and `fusion_in_frame`.
- The default v1 fusion panel includes common actionable fusion genes such as `ALK`, `RET`, `ROS1`, `NTRK1`, `NTRK2`, `NTRK3`, `FGFR2`, `FGFR3`, `BRAF`, `RAF1`, `NRG1`, `NUTM1`, `MET`, and `ERBB2`.
- Fusion evidence is labeled as `fusion` and remains preclinical experimental support unless supported by curated/literature evidence.

## Tests

```bash
pytest
```
