# Variant-Response Discovery Engine

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

To replace it with a larger normalized public snapshot:

```bash
python scripts/load_gdsc_snapshot.py /path/to/gdsc_snapshot.csv
```

Expected CSV columns:

`profile_label,gene_symbol,biomarker_type,alteration,therapy,therapy_class,cancer_type,lineage,response_class,sample_count,effect_size,p_value,statement,citation,source`

## Tests

```bash
pytest
```
