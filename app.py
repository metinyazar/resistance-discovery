import base64
import html
import re
from pathlib import Path

import streamlit as st

from src.engine import analyze_variant_response, run_variant_analysis
from src.llm import llm_enabled
from src.query_parser import parse_variant_query
from src.ui_options import (
    amino_acid_options,
    build_small_variant,
    load_cancer_type_options,
    load_drug_options,
    load_gene_options,
)


BIOMARKER_TYPES = [
    "small_variant",
    "fusion",
    "copy_number",
    "expression",
    "grouped_biomarker",
]

DRUG_OTHER_OPTION = "Other"
CANCER_OTHER_OPTION = "Other"
ASSET_DIR = Path(__file__).parent / "assets"
TRACE_BANNER_PATH = ASSET_DIR / "trace_banner.png"


TRACE_CSS = """
<style>
:root {
    --trace-ink: #172033;
    --trace-muted: #64748b;
    --trace-page: #eef3f8;
    --trace-panel: rgba(248, 251, 255, 0.92);
    --trace-blue: #2563eb;
    --trace-navy: #0f2747;
    --trace-sky: #8ec5ff;
    --trace-cyan: #19a7ce;
    --trace-line: rgba(42, 63, 95, 0.16);
    --trace-shadow: 0 20px 60px rgba(15, 39, 71, 0.12);
}

html, body, [data-testid="stAppViewContainer"] {
    color: var(--trace-ink);
    background:
        radial-gradient(circle at 8% 8%, rgba(37, 99, 235, 0.16), transparent 25rem),
        radial-gradient(circle at 94% 4%, rgba(25, 167, 206, 0.14), transparent 26rem),
        linear-gradient(135deg, #f3f7fb 0%, #e8eef5 54%, #f7f9fc 100%) !important;
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
}

[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    max-width: 1240px;
    padding-top: 2.4rem;
    padding-bottom: 4rem;
}

h1, h2, h3, [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2 {
    color: var(--trace-ink);
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    letter-spacing: -0.035em;
}

.trace-hero {
    position: relative;
    margin: 0 0 1.8rem;
    padding: clamp(0.8rem, 2vw, 1.2rem);
    border: 1px solid var(--trace-line);
    border-radius: 28px;
    background:
        linear-gradient(135deg, rgba(248, 251, 255, 0.97), rgba(224, 234, 247, 0.9)),
        radial-gradient(circle at 90% 16%, rgba(37, 99, 235, 0.14), transparent 20rem);
    box-shadow: var(--trace-shadow);
    overflow: hidden;
}

.trace-hero::after {
    content: none;
}

.trace-hero-content {
    position: relative;
    z-index: 1;
    max-width: none;
}

.trace-banner-img {
    display: block;
    width: min(100%, 760px);
    margin: 0 auto;
    border-radius: 20px;
    border: 1px solid rgba(37, 99, 235, 0.12);
    box-shadow: 0 18px 48px rgba(15, 39, 71, 0.12);
}

.trace-eyebrow,
.trace-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    width: fit-content;
    border: 1px solid rgba(37, 99, 235, 0.18);
    border-radius: 999px;
    background: rgba(239, 246, 255, 0.78);
    color: var(--trace-navy);
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
}

.trace-eyebrow {
    padding: 0.48rem 0.72rem;
}

.trace-title {
    margin: 1rem 0 0.55rem;
    color: var(--trace-ink);
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: clamp(3.2rem, 8vw, 6.6rem);
    font-weight: 850;
    line-height: 0.9;
    letter-spacing: -0.075em;
}

.trace-subtitle {
    margin: 0.95rem 0 0;
    max-width: 900px;
    color: #475569;
    font-size: clamp(0.98rem, 1.6vw, 1.18rem);
    line-height: 1.45;
}

.trace-hero-grid {
    display: none;
}

.trace-chip {
    padding: 0.5rem 0.68rem;
}

.trace-section {
    margin: 1.25rem 0 0.75rem;
    padding: 1rem 1.15rem;
    border: 1px solid var(--trace-line);
    border-left: 6px solid var(--trace-blue);
    border-radius: 22px;
    background: rgba(248, 251, 255, 0.78);
}

.trace-section h2 {
    margin: 0;
    font-size: 1.62rem;
    line-height: 1.05;
}

.trace-section p {
    margin: 0.3rem 0 0;
    color: var(--trace-muted);
}

.trace-summary-card {
    margin: 0.3rem 0 1.1rem;
    padding: 1.25rem;
    border: 1px solid rgba(37, 99, 235, 0.18);
    border-radius: 26px;
    background: linear-gradient(135deg, #0f2747, #1d4ed8);
    color: #f8fbff;
    box-shadow: var(--trace-shadow);
}

.trace-summary-card .trace-chip {
    margin-bottom: 0.9rem;
    border-color: rgba(248, 251, 255, 0.24);
    background: rgba(248, 251, 255, 0.1);
    color: #bfdbfe;
}

.trace-summary-card h3 {
    margin: 0 0 0.45rem;
    color: #f8fbff;
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-size: clamp(1.55rem, 3vw, 2.4rem);
    letter-spacing: -0.045em;
}

.trace-summary-card p {
    margin: 0;
    color: rgba(248, 251, 255, 0.82);
    font-size: 1.02rem;
    line-height: 1.55;
}

div[data-testid="stMetric"] {
    padding: 1rem;
    border: 1px solid var(--trace-line);
    border-radius: 22px;
    background: rgba(248, 251, 255, 0.88);
    box-shadow: 0 12px 34px rgba(23, 35, 31, 0.08);
}

div[data-testid="stMetric"] label {
    color: var(--trace-muted) !important;
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

div[data-testid="stMetricValue"] {
    color: var(--trace-blue);
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
}

.stButton > button,
[data-testid="stFormSubmitButton"] button {
    border: 1px solid rgba(37, 99, 235, 0.34);
    border-radius: 999px;
    background: var(--trace-blue);
    color: #f8fbff;
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Helvetica, sans-serif;
    font-weight: 800;
    letter-spacing: 0.03em;
    box-shadow: 0 10px 22px rgba(37, 99, 235, 0.18);
}

.stButton > button:hover,
[data-testid="stFormSubmitButton"] button:hover {
    border-color: var(--trace-navy);
    background: #1d4ed8;
    color: #f8fbff;
}

.stButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"] {
    background: var(--trace-navy);
    border-color: var(--trace-navy);
}

div[data-testid="stAlert"] {
    border-radius: 20px;
    border: 1px solid rgba(37, 99, 235, 0.16);
    background: rgba(248, 251, 255, 0.82);
}

div[data-testid="stDataFrame"],
div[data-testid="stJson"] {
    border-radius: 20px;
    overflow: hidden;
    border: 1px solid var(--trace-line);
    box-shadow: 0 12px 34px rgba(23, 35, 31, 0.07);
}

[data-baseweb="select"] > div,
input,
textarea {
    border-radius: 14px !important;
}

section[data-testid="stSidebar"] {
    background: rgba(238, 243, 248, 0.94);
}

@media (max-width: 760px) {
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .trace-hero {
        border-radius: 24px;
    }

    .trace-title {
        font-size: 4rem;
    }
}
</style>
"""

EXAMPLE_QUERIES = [
    {
        "label": "Example 1",
        "title": "DepMap support",
        "gene_symbol": "BRAF",
        "biomarker_type": "small_variant",
        "alteration": "V600E",
        "therapy": "Dabrafenib",
        "cancer_type": "Melanoma",
        "description": "BRAF V600E melanoma models show HIGH DepMap/GDSC sensitivity evidence for dabrafenib.",
    },
    {
        "label": "Example 2",
        "title": "Resistance literature/CIViC",
        "gene_symbol": "EGFR",
        "biomarker_type": "small_variant",
        "alteration": "T790M",
        "therapy": "Gefitinib",
        "cancer_type": "NSCLC",
        "description": "Classic EGFR T790M resistance example in non-small-cell lung cancer.",
    },
    {
        "label": "Example 3",
        "title": "Literature-first sensitivity",
        "gene_symbol": "KRAS",
        "biomarker_type": "small_variant",
        "alteration": "G12C",
        "therapy": "Sotorasib",
        "cancer_type": "NSCLC",
        "description": "KRAS G12C targeted therapy example for testing literature/direct-claim behavior.",
    },
    {
        "label": "Example 4",
        "title": "Copy-number DepMap support",
        "gene_symbol": "ERBB2",
        "biomarker_type": "copy_number",
        "alteration": "amplification",
        "therapy": "Lapatinib",
        "cancer_type": "Invasive Breast Carcinoma",
        "description": "ERBB2 amplification example for testing copy-number DepMap/GDSC support.",
    },
    {
        "label": "Example 5",
        "title": "Expression DepMap support",
        "gene_symbol": "ERBB2",
        "biomarker_type": "expression",
        "alteration": "high expression",
        "therapy": "CP-724714",
        "cancer_type": "Invasive Breast Carcinoma",
        "description": "ERBB2 high-expression example for testing expression-level DepMap/GDSC support.",
    },
    {
        "label": "Example 6",
        "title": "Fusion DepMap support",
        "gene_symbol": "ALK",
        "biomarker_type": "fusion",
        "alteration": "ALK fusion",
        "therapy": "Alectinib",
        "cancer_type": "NSCLC",
        "description": "ALK fusion example for testing fusion-level DepMap/GDSC support.",
    },
]


def init_state():
    defaults = {
        "phase": "input",
        "description": "",
        "parsed_query": None,
        "confirmed_query": None,
        "result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_state()


def _records_to_frame(records):
    rows = []
    for record in records:
        raw = record.raw or {}
        row = {
            "Source": record.source,
            "Profile": record.profile_label,
            "Therapy": record.therapy,
            "Cancer": record.disease,
            "Response": record.response_class,
            "Level": record.evidence_level,
            "Match": f"{record.profile_match_level}/{record.therapy_match_level}/{record.cancer_match_level}",
            "Citation": record.citation,
            "Statement": record.statement,
        }
        if record.evidence_kind == "experimental_support":
            row.update(
                {
                    "Quality": raw.get("quality_band", ""),
                    "Mutant n": raw.get("mutant_count", ""),
                    "Control n": raw.get("control_count", ""),
                    "Effect": raw.get("effect_size", ""),
                    "P value": raw.get("p_value", ""),
                    "Metric": raw.get("response_metric", ""),
                    "Quality flags": raw.get("quality_flags", ""),
                }
            )
        rows.append(row)
    return rows


def _claims_to_frame(claims):
    return [
        {
            "Paper": claim.paper_id,
            "Response": claim.response_class,
            "Match level": claim.claim_match_level,
            "Score": claim.match_score,
            "Matched terms": ", ".join(claim.matched_terms),
            "Review flags": ", ".join(claim.review_flags),
            "Claim sentence": claim.claim_sentence,
        }
        for claim in claims
    ]


def _ranked_papers_to_frame(ranked_papers):
    return [
        {
            "Score": ranked.score,
            "PMID": ranked.paper.pmid,
            "Title": ranked.paper.title,
            "Year": ranked.paper.year,
            "Source": ranked.paper.source,
            "Gene": ranked.mentions_gene,
            "Alteration": ranked.mentions_alteration,
            "Therapy": ranked.mentions_therapy,
            "Cancer": ranked.mentions_cancer,
            "Resistance": ranked.mentions_resistance,
            "Sensitivity": ranked.mentions_sensitivity,
            "Direct claim": ranked.has_direct_claim,
            "CRISPR screen": ranked.functional_screen_support,
            "Manual review": ranked.needs_manual_review,
            "Review flags": ", ".join(ranked.review_flags),
            "Snippet": ranked.snippet,
            "URL": ranked.paper.url,
        }
        for ranked in ranked_papers
    ]


def _option_index(options, value, default=0):
    try:
        return options.index(value)
    except ValueError:
        return default


def _small_variant_parts(alteration: str):
    match = re.fullmatch(r"([A-Z])([0-9]+)([A-Z*])", alteration.strip().upper())
    if not match:
        return None
    return match.group(1), int(match.group(2)), match.group(3)


def _amino_acid_label(code: str, aa_options: list[str]) -> str:
    for option in aa_options:
        if option.startswith(f"{code} - "):
            return option
    return aa_options[0]


def _inject_trace_theme():
    st.markdown(TRACE_CSS, unsafe_allow_html=True)


def _image_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _render_trace_hero():
    banner_uri = _image_data_uri(TRACE_BANNER_PATH)
    st.markdown(
        f"""
        <section class="trace-hero">
          <div class="trace-hero-content">
            <img class="trace-banner-img" src="{banner_uri}" alt="TRACE: Therapy Response And Cancer Evidence" />
            <p class="trace-subtitle">
              TRACE helps explore whether a cancer biomarker is linked to drug sensitivity
              or resistance by combining curated databases, literature evidence, and DepMap
              experimental support.
            </p>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _section(title: str, subtitle: str = ""):
    safe_title = html.escape(title)
    safe_subtitle = html.escape(subtitle)
    subtitle_html = f"<p>{safe_subtitle}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class="trace-section">
          <h2>{safe_title}</h2>
          {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _summary_card(verdict: str, confidence: str, rationale: str):
    safe_verdict = html.escape(verdict)
    safe_confidence = html.escape(confidence.upper())
    safe_rationale = html.escape(rationale)
    st.markdown(
        f"""
        <div class="trace-summary-card">
          <div class="trace-chip">Final interpretation</div>
          <h3>{safe_verdict} · {safe_confidence}</h3>
          <p>{safe_rationale}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _apply_example_to_manual_form(example, gene_options, drug_choices, cancer_choices, aa_options):
    st.session_state["manual_gene_symbol"] = example["gene_symbol"] if example["gene_symbol"] in gene_options else gene_options[0]
    st.session_state["manual_biomarker_type"] = example["biomarker_type"]

    if example["biomarker_type"] == "small_variant":
        parts = _small_variant_parts(example["alteration"])
        if parts:
            ref_aa, position, alt_aa = parts
            st.session_state["manual_ref_aa"] = _amino_acid_label(ref_aa, aa_options)
            st.session_state["manual_aa_position"] = position
            st.session_state["manual_alt_aa"] = _amino_acid_label(alt_aa, aa_options)
    else:
        st.session_state["manual_alteration"] = example["alteration"]

    if example["therapy"] in drug_choices:
        st.session_state["manual_drug_choice"] = example["therapy"]
        st.session_state["manual_custom_therapy"] = ""
    else:
        st.session_state["manual_drug_choice"] = DRUG_OTHER_OPTION
        st.session_state["manual_custom_therapy"] = example["therapy"]

    if example["cancer_type"] in cancer_choices:
        st.session_state["manual_cancer_choice"] = example["cancer_type"]
        st.session_state["manual_custom_cancer_type"] = ""
    else:
        st.session_state["manual_cancer_choice"] = CANCER_OTHER_OPTION
        st.session_state["manual_custom_cancer_type"] = example["cancer_type"]


def _init_manual_form_state(gene_options, drug_choices, cancer_choices, aa_options):
    defaults = {
        "manual_gene_symbol": "EGFR" if "EGFR" in gene_options else gene_options[0],
        "manual_biomarker_type": "small_variant",
        "manual_ref_aa": _amino_acid_label("T", aa_options),
        "manual_aa_position": 790,
        "manual_alt_aa": _amino_acid_label("M", aa_options),
        "manual_alteration": "",
        "manual_drug_choice": "Gefitinib" if "Gefitinib" in drug_choices else drug_choices[0],
        "manual_custom_therapy": "",
        "manual_cancer_choice": "NSCLC" if "NSCLC" in cancer_choices else cancer_choices[0],
        "manual_custom_cancer_type": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_results(result):
    summary = result["summary"]
    interpretation = result.get("interpretation") or {}
    query = result["query"]
    profile = result["profile"]
    normalization = result["normalization"]
    literature_search = result.get("literature_search") or {}
    evidence_conclusion = result.get("evidence_conclusion") or result.get("literature_conclusion")

    final_verdict = interpretation.get("verdict", summary.verdict)
    final_confidence = interpretation.get("confidence_band", summary.confidence_band)
    final_rationale = interpretation.get("rationale", summary.top_rationale)

    _section(
        "Final Answer",
        "Primary verdict uses curated evidence when available; literature validates and DepMap remains experimental support.",
    )
    _summary_card(final_verdict, final_confidence, final_rationale)
    a, b, c, d = st.columns(4)
    a.metric("Verdict", final_verdict)
    b.metric("Confidence", final_confidence.upper())
    c.metric("Evidence basis", getattr(evidence_conclusion, "evidence_basis", "unknown"))
    d.metric("Confidence score", getattr(evidence_conclusion, "confidence_score", 0))

    if evidence_conclusion:
        st.caption(
            f"Database verdict: {evidence_conclusion.database_verdict} | "
            f"Literature verdict: {evidence_conclusion.literature_verdict} | "
            f"Database support: {evidence_conclusion.database_support_count} | "
            f"Literature support: {evidence_conclusion.literature_support_count} | "
            f"Experimental support: {evidence_conclusion.experimental_support_count} | "
            f"Conflicts: {evidence_conclusion.conflicting_count}"
        )
        for limitation in evidence_conclusion.limitations:
            st.caption(f"Limitation: {limitation}")

    if result.get("agent_steps"):
        _section(
            "Analysis Pipeline",
            "Steps are grouped by type. Deterministic modules run without an LLM; optional LLM modules are inactive unless an API key is configured.",
        )
        st.dataframe(result["agent_steps"], use_container_width=True, hide_index=True)

    source_plan = result.get("source_plan") or {}
    if source_plan:
        with st.expander("Source Plan"):
            st.json(source_plan)

    if interpretation.get("key_evidence"):
        _section("Key Evidence")
        for line in interpretation["key_evidence"]:
            st.write(f"- {line}")
    if interpretation.get("cautions"):
        _section("Interpretation Cautions")
        for line in interpretation["cautions"]:
            st.write(f"- {line}")

    database_summary = result.get("database_summary")
    if database_summary:
        _section("Database Evidence", "CIViC evidence drives the database verdict; DepMap/GDSC is shown separately as support.")
        a, b, c = st.columns(3)
        a.metric("Database-only verdict", database_summary.verdict)
        b.metric("Curated direct", database_summary.direct_evidence_count)
        c.metric("Experimental support", database_summary.supporting_experimental_count)
        st.caption(database_summary.top_rationale)
        for error in (result.get("database_support") or {}).get("diagnostics", {}).get("errors", []):
            st.warning(error)

    for title, records in [
        ("Direct curated", result["direct_curated"]),
        ("Related curated", result["related_curated"]),
    ]:
        _section(title)
        if not records:
            st.caption("No records matched this section.")
            continue
        st.dataframe(_records_to_frame(records), use_container_width=True, hide_index=True)

    _section("Supporting Experimental", "DepMap/GDSC associations are preclinical and do not drive the primary verdict.")
    supporting_records = result["supporting_experimental"]
    if not supporting_records:
        st.caption("No records matched this section.")
    else:
        st.caption("DepMap/GDSC evidence is preclinical. Use the Quality column to distinguish HIGH, MEDIUM, and LOW confidence associations.")
        st.dataframe(_records_to_frame(supporting_records), use_container_width=True, hide_index=True)

    _section("Literature Validation", "Only exact biomarker/profile claim sentences count toward the literature verdict.")
    diagnostics = literature_search.get("diagnostics") or {}
    st.caption(
        f"Query: {literature_search.get('query', 'not available')} | "
        f"Retrieved: {len(literature_search.get('records', []))} | "
        f"Europe PMC: {diagnostics.get('europe_pmc_records', 0)} | "
        f"PubMed enabled: {diagnostics.get('pubmed_enabled', False)} | "
        f"Seed fallback: {diagnostics.get('seed_records', 0)}"
    )
    for error in diagnostics.get("errors", []):
        st.warning(error)

    st.caption("Only direct claims with exact biomarker/profile evidence are counted in the literature verdict.")
    direct_literature_claims = result.get("direct_literature_claims") or []
    related_literature_claims = result.get("related_literature_claims") or []
    if direct_literature_claims:
        st.markdown("**Direct Literature Claims**")
        st.dataframe(_claims_to_frame(direct_literature_claims), use_container_width=True, hide_index=True)
    else:
        st.caption("No direct biomarker-specific resistance or sensitivity claim sentence was extracted from titles/abstracts.")

    if related_literature_claims:
        st.markdown("**Related Literature / Manual Review**")
        st.dataframe(_claims_to_frame(related_literature_claims), use_container_width=True, hide_index=True)

    ranked_papers = result.get("ranked_papers") or []
    if ranked_papers:
        with st.expander("Ranked Literature Hits", expanded=True):
            st.dataframe(_ranked_papers_to_frame(ranked_papers[:25]), use_container_width=True, hide_index=True)

    digest = result.get("evidence_digest") or {}
    if digest.get("highlights"):
        _section("Highlights")
        for line in digest["highlights"]:
            st.write(f"- {line}")
    if digest.get("cautions"):
        _section("Cautions")
        for line in digest["cautions"]:
            st.write(f"- {line}")

    _section("Normalized Query", "Canonicalized query fields used for matching evidence.")
    st.json(
        {
            "gene_symbol": query.gene_symbol,
            "biomarker_type": query.biomarker_type,
            "alteration": query.alteration,
            "profile_label": profile.label,
            "therapy": normalization["therapy"]["canonical"],
            "therapy_aliases": normalization["therapy"]["aliases"],
            "cancer_type": normalization["cancer"]["canonical"],
            "cancer_aliases": normalization["cancer"]["aliases"],
            "cancer_lineages": normalization["cancer"]["lineages"],
        }
    )

    if result.get("literature_context"):
        with st.expander("LLM Biological Context"):
            st.markdown(result["literature_context"])

    if result.get("report_text"):
        _section("Narrative Report")
        st.markdown(result["report_text"])



def _manual_query_form():
    gene_options = load_gene_options()
    drug_options = load_drug_options()
    cancer_options = load_cancer_type_options()
    aa_options = amino_acid_options()
    drug_choices = [*drug_options, DRUG_OTHER_OPTION]
    cancer_choices = [*cancer_options, CANCER_OTHER_OPTION]
    _init_manual_form_state(gene_options, drug_choices, cancer_choices, aa_options)

    _section("Ready Examples", "Use a preset to quickly test small variant, copy-number, expression, and fusion workflows.")
    example_cols = st.columns(len(EXAMPLE_QUERIES))
    for col, example in zip(example_cols, EXAMPLE_QUERIES):
        with col:
            if st.button(example["label"], use_container_width=True):
                _apply_example_to_manual_form(example, gene_options, drug_choices, cancer_choices, aa_options)
            st.caption(example["description"])

    col1, col2 = st.columns(2)
    with col1:
        gene_symbol = st.selectbox(
            "Gene symbol",
            gene_options,
            help="Approved HGNC protein-coding gene symbols.",
            key="manual_gene_symbol",
        )
        biomarker_type = st.selectbox("Biomarker type", BIOMARKER_TYPES, key="manual_biomarker_type")

        if biomarker_type == "small_variant":
            st.caption("Build an amino-acid substitution, e.g. V600E or T790M.")
            aa_col1, aa_col2, aa_col3 = st.columns([2, 1, 2])
            with aa_col1:
                ref_aa = st.selectbox(
                    "Reference amino acid",
                    aa_options,
                    key="manual_ref_aa",
                )
            with aa_col2:
                aa_position = st.number_input(
                    "Position",
                    min_value=1,
                    max_value=10000,
                    step=1,
                    key="manual_aa_position",
                )
            with aa_col3:
                alt_aa = st.selectbox(
                    "Altered amino acid",
                    aa_options,
                    key="manual_alt_aa",
                )
            alteration = build_small_variant(ref_aa, aa_position, alt_aa)
            st.caption(f"Alteration: `{alteration}`")
        else:
            alteration = st.text_input(
                "Alteration",
                placeholder="e.g. EML4-ALK fusion, amplification, high expression",
                key="manual_alteration",
            )

    with col2:
        drug_choice = st.selectbox(
            "Therapy / drug suggestion",
            drug_choices,
            key="manual_drug_choice",
        )
        custom_therapy = st.text_input(
            "Type drug name",
            placeholder="Optional override, e.g. Pyrimethamine",
            help="Use this when the drug is not in the suggestion list or when you want an exact DepMap/GDSC drug label.",
            key="manual_custom_therapy",
        )
        therapy = custom_therapy.strip() or ("" if drug_choice == DRUG_OTHER_OPTION else drug_choice)

        cancer_choice = st.selectbox(
            "Cancer type suggestion",
            cancer_choices,
            key="manual_cancer_choice",
        )
        custom_cancer_type = st.text_input(
            "Type cancer type",
            placeholder="Optional override, e.g. Non-Small Cell Lung Cancer",
            help="Use this when the cancer label is not in the suggestion list or you want the exact DepMap/CIViC wording.",
            key="manual_custom_cancer_type",
        )
        cancer_type = custom_cancer_type.strip() or ("" if cancer_choice == CANCER_OTHER_OPTION else cancer_choice)

    submitted = st.button("Analyze", type="primary")

    if submitted:
        if not therapy.strip():
            st.error("Please enter a drug name.")
            return
        if not cancer_type.strip():
            st.error("Please enter a cancer type.")
            return
        if not alteration.strip():
            st.error("Please enter an alteration.")
            return

        description = f"{gene_symbol} {alteration} with {therapy} in {cancer_type}"
        with st.spinner("Searching literature first, then attaching database support..."):
            result = analyze_variant_response(
                gene_symbol=gene_symbol,
                biomarker_type=biomarker_type,
                alteration=alteration,
                therapy=therapy,
                cancer_type=cancer_type,
            )
            result["report_text"] = ""
            result["literature_context"] = ""
            result["evidence_digest"] = {}
            result["source_plan"] = {}
            result["interpretation"] = {
                "verdict": result["summary"].verdict,
                "confidence_band": result["summary"].confidence_band,
                "rationale": result["summary"].top_rationale,
                "key_evidence": [],
                "cautions": [],
            }
            result["agent_steps"] = [
                {"type": "Deterministic", "step": "structured_query", "status": "done", "summary": "Used the structured form instead of LLM parsing."},
                {"type": "Deterministic", "step": "literature_search", "status": "done", "summary": f"Retrieved {len(result['literature_search']['records'])} literature records."},
                {"type": "Deterministic", "step": "claim_extractor", "status": "done", "summary": f"Extracted {len(result['direct_literature_claims'])} direct and {len(result['related_literature_claims'])} related claim sentences."},
                {"type": "Deterministic", "step": "database_support", "status": "done", "summary": f"Attached {len(result['direct_curated']) + len(result['related_curated'])} curated and {len(result['supporting_experimental'])} experimental support records."},
                {"type": "Deterministic", "step": "evidence_synthesizer", "status": "done", "summary": f"Called {result['summary'].verdict} from {result['evidence_conclusion'].evidence_basis} evidence."},
                {"type": "Optional LLM", "step": "llm_query_parser", "status": "inactive", "summary": "Inactive in structured mode; set ANTHROPIC_API_KEY to enable free-text parsing."},
                {"type": "Optional LLM", "step": "llm_biological_context", "status": "inactive", "summary": "Inactive because no LLM report/context generation is used in structured mode."},
                {"type": "Optional LLM", "step": "llm_report_writer", "status": "inactive", "summary": "Inactive because no LLM narrative report is generated in structured mode."},
            ]
        st.session_state.description = description
        st.session_state.result = result
        st.session_state.phase = "results"
        st.rerun()


def main():
    st.set_page_config(page_title="TRACE", layout="wide")
    _inject_trace_theme()
    init_state()
    phase = st.session_state.phase
    llm_ready = llm_enabled()

    _render_trace_hero()

    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("Restart", use_container_width=True):
            reset_state()
            st.rerun()

    if phase == "input":
        if llm_ready:
            st.info("LLM mode is enabled. Describe the biomarker-response question in free text, then confirm the parsed fields.")
            description = st.text_area(
                "Describe the query",
                value=st.session_state.description,
                placeholder="e.g. EGFR T790M mutation is associated with resistance to gefitinib in NSCLC",
                height=110,
            )
            if st.button("Parse with LLM", type="primary"):
                st.session_state.description = description.strip()
                st.session_state.phase = "parsing"
                st.rerun()
            with st.expander("Manual structured query"):
                _manual_query_form()
        else:
            st.info("LLM mode is disabled. Structured database-primary analysis still works; set `ANTHROPIC_API_KEY` to enable free-text parsing, biological context, and narrative reporting.")
            _manual_query_form()
        return

    if phase == "parsing":
        with st.spinner("Parsing query with LLM..."):
            st.session_state.parsed_query = parse_variant_query(st.session_state.description)
            st.session_state.phase = "confirm"
            st.rerun()

    if phase == "confirm":
        parsed = st.session_state.parsed_query
        st.subheader("Confirm Parsed Query")
        with st.form("confirm_form"):
            col1, col2 = st.columns(2)
            with col1:
                gene_symbol = st.text_input("Gene symbol", value=parsed.gene_symbol)
                biomarker_type = st.selectbox(
                    "Biomarker type",
                    BIOMARKER_TYPES,
                    index=BIOMARKER_TYPES.index(parsed.biomarker_type) if parsed.biomarker_type in BIOMARKER_TYPES else 0,
                )
                alteration = st.text_input("Alteration", value=parsed.alteration)
            with col2:
                therapy = st.text_input("Therapy / drug", value=parsed.therapy)
                cancer_type = st.text_input("Cancer type", value=parsed.cancer_type)
                st.caption(f"Confidence: {parsed.confidence}%")
            st.caption(parsed.reasoning or "No parser reasoning returned.")
            confirmed = st.form_submit_button("Confirm & Analyze", type="primary")

        if confirmed:
            st.session_state.confirmed_query = {
                "gene_symbol": gene_symbol,
                "biomarker_type": biomarker_type,
                "alteration": alteration,
                "therapy": therapy,
                "cancer_type": cancer_type,
            }
            st.session_state.phase = "running"
            st.rerun()
        return

    if phase == "running":
        with st.spinner("Running TRACE analysis..."):
            st.session_state.result = run_variant_analysis(
                st.session_state.description,
                st.session_state.confirmed_query,
            )
            st.session_state.phase = "results"
            st.rerun()

    if phase == "results" and st.session_state.result:
        _render_results(st.session_state.result)


if __name__ == "__main__":
    main()
