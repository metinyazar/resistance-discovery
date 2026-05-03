# Variant-Response Discovery Engine

Literature-first research agent for questions of the form:

`mutation X in gene Y leads to resistance/sensitivity to therapy Z in cancer W`

## Scope

- Primary source: published paper titles and abstracts from Europe PMC, with optional PubMed/NCBI E-utilities when `NCBI_EMAIL` is configured
- Supporting source: accepted predictive CIViC evidence and assertions
- Experimental support: local GDSC-style cell-line snapshot
- Cache/storage: DuckDB at `data/variant_response.duckdb`
- Literature API cache: SQLite at `data/literature_cache.sqlite`
- Prompt-driven LLM skills live in `prompts/`
- Skill modules live in `src/skills/`
- `src/engine.py` orchestrates normalization, literature retrieval, paper ranking, claim extraction, database support, synthesis, and optional report writing
- Research use only, not clinical decision support

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Evidence Flow

The default workflow does not require Claude or ChatGPT:

1. Normalize gene, biomarker type, alteration, therapy, and cancer context.
2. Search Europe PMC broadly, and PubMed when `NCBI_EMAIL` is configured.
3. Rank papers by transparent flags: gene, alteration, therapy, cancer, resistance/sensitivity language, direct claim, abstract availability, and CRISPR screen support.
4. Extract candidate claim sentences from titles and abstracts.
5. Attach CIViC and GDSC support after literature claims are found.
6. Synthesize a literature-first verdict. Database-only evidence remains supporting context, not the primary verdict.

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
