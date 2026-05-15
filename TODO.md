# TODO

## Guiding Rule

DepMap/GDSC evidence should remain supporting experimental evidence. CIViC and direct biomarker-specific literature should drive the main verdict when available.

## DepMap/GDSC

### Small-Variant Evidence Quality

Status: mostly implemented.

- [x] Build normalized small-variant response summaries from `sanger-dose-response.csv`, `Model.csv`, and `OmicsSomaticMutations.csv`.
- [x] Add filters/labels to reduce noisy passenger-mutation interpretation.
- [x] Prioritize known cancer genes / hotspot-like mutations using available DepMap mutation annotations.
- [x] Show mutant/control counts, effect size, p-value, response metric, and metric direction.
- [x] Add a `DepMap evidence quality` label so weak associations do not look clinical.
- [x] Document `HIGH`, `MEDIUM`, and `LOW` thresholds in `README.md`.
- [x] Show all DepMap rows together with explicit `HIGH`/`MEDIUM`/`LOW` quality labels.
- [ ] Consider multiple-testing correction or false-discovery-rate filtering for large snapshot builds.

### Drug Coverage

Status: next recommended DepMap step.

- [x] Populate the app drug list from `sanger-dose-response.csv` or the normalized DepMap/GDSC snapshot.
- [x] Merge DepMap drugs with the existing curated drug list.
- [x] Keep manual drug typing available.
- [x] Include aliases/classes where possible, e.g. `PLX-4720` vs `BRAF inhibitor`.
- [x] Add tests that verify DepMap-only drugs such as `Pyrimethamine`, `PLX-4720`, and `Dabrafenib` are available.

### Copy-Number Evidence

Status: implemented baseline.

- [x] Use `OmicsCNGeneWGS.csv` for v1 copy-number support.
- [x] Define amplification/deletion thresholds.
- [x] Generate normalized copy-number response summaries.
- [x] Support queries such as `ERBB2 amplification`, `MYC amplification`, and `CDKN2A deletion` for the default v1 panel when enough models/drugs exist.
- [x] Label copy-number evidence as preclinical experimental support.
- [ ] Consider expanding beyond the default v1 copy-number gene panel.
- [ ] Consider adding `PortalOmicsCNGeneLog2.csv` support for portal-style display/threshold comparisons.

### Expression Evidence

Status: implemented baseline.

- [x] Use `OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv`.
- [x] Define careful high/low expression thresholds.
- [x] Generate normalized expression response summaries.
- [x] Support queries such as `ESR1 high expression` and other expression-level biomarkers in the default v1 expression panel.
- [x] Avoid overclaiming expression evidence because thresholds can be context-dependent.
- [ ] Consider expanding beyond the default v1 expression gene panel.
- [ ] Consider context-specific expression thresholds beyond quartiles for selected biomarkers.

### Fusion Evidence

Status: implemented baseline.

- [x] Use `OmicsFusionFiltered.csv`.
- [x] Optionally use `OmicsFusionFilteredSupplementary.csv` for breakpoint-level detail.
- [x] Generate normalized fusion response summaries.
- [x] Support queries such as `ALK fusion`, `NTRK fusion`, and `RET fusion` when enough models/drugs exist.
- [x] Keep fusion evidence separate from clinical curated evidence unless CIViC/literature supports it.
- [ ] Consider expanding beyond the default v1 fusion gene panel.
- [ ] Consider displaying fusion partner names and breakpoint details in the UI.

## CIViC / Curated Database Evidence

Status: implemented baseline, needs refinement.

- [x] Query CIViC predictive evidence/assertions.
- [x] Separate direct curated evidence from related curated evidence.
- [x] Use database evidence as the primary verdict source when direct curated evidence exists.
- [ ] Improve CIViC therapy alias handling for drug classes and combination therapies.
- [ ] Improve CIViC cancer-context alias handling beyond local synonym maps.
- [ ] Add clearer display of CIViC evidence level, rating, assertion status, and variant origin.

## Literature Evidence

Status: implemented baseline, needs refinement.

- [x] Retrieve literature from Europe PMC by default.
- [x] Optionally retrieve PubMed/NCBI records when `NCBI_EMAIL` is configured.
- [x] Extract direct biomarker-specific claim sentences.
- [x] Keep related/non-specific literature visible but excluded from literature verdict counts.
- [ ] Improve query expansion for drug aliases and cancer synonyms.
- [ ] Add more gold-standard literature fixtures for resistance and sensitivity cases.
- [ ] Add optional LLM-assisted claim extraction/reporting behind an API-key gate.

## UI / UX

Status: active.

- [x] Add structured form for gene, biomarker type, alteration, therapy, and cancer type.
- [x] Add HGNC protein-coding gene selector.
- [x] Add manual drug and cancer-type override fields.
- [x] Add ready examples for quick testing.
- [x] Show DepMap quality labels and supporting statistics in the evidence table.
- [x] Populate drug suggestions from DepMap/GDSC and curated sources.
- [x] Populate cancer suggestions from DepMap/GDSC and curated sources.
- [ ] Add export/download for evidence table and final report.
- [ ] Add compact help text explaining verdict, confidence, and evidence source roles.

### Website Design

Status: planned.

- [ ] Redesign the landing/header area so the app purpose is immediately clear: biomarker + therapy + cancer context -> response evidence.
- [ ] Improve visual hierarchy between query input, final verdict, curated evidence, literature validation, and DepMap support.
- [ ] Convert ready examples into cleaner example cards or compact action buttons with consistent spacing.
- [ ] Add color-coded badges for verdict, confidence, evidence source, and DepMap evidence quality.
- [ ] Reorganize the result page into clearer sections or tabs: Final Answer, Curated Evidence, Literature, and Experimental Support.
- [ ] Improve evidence table readability with better column ordering, shorter labels, and expandable long statements.
- [ ] Add a persistent but non-intrusive research-use limitation notice.
- [ ] Check responsive layout so the app remains usable on smaller laptop screens.

## Testing / Maintenance

Status: active.

- [x] Add offline tests for normalization, matching, verdict synthesis, literature specificity, and DepMap builder logic.
- [x] Add fixture-based DepMap snapshot builder tests.
- [ ] Add regression tests for Streamlit example presets.
- [ ] Add a lightweight smoke command for rebuilding/loading DepMap snapshots.
- [x] Add documentation and ignore rules for refreshing DepMap releases safely without committing raw data.
