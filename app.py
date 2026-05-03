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
    return [
        {
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
        for record in records
    ]


def _claims_to_frame(claims):
    return [
        {
            "Paper": claim.paper_id,
            "Response": claim.response_class,
            "Score": claim.match_score,
            "Matched terms": ", ".join(claim.matched_terms),
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


def _render_results(result):
    summary = result["summary"]
    interpretation = result.get("interpretation") or {}
    query = result["query"]
    profile = result["profile"]
    normalization = result["normalization"]
    literature_search = result.get("literature_search") or {}
    literature_conclusion = result.get("literature_conclusion")

    st.subheader("Verdict")
    a, b, c = st.columns(3)
    a.metric("Verdict", interpretation.get("verdict", summary.verdict))
    b.metric("Confidence", interpretation.get("confidence_band", summary.confidence_band).upper())
    c.metric("Literature claims", summary.direct_evidence_count)
    st.write(interpretation.get("rationale", summary.top_rationale))
    if literature_conclusion and literature_conclusion.limitations:
        for limitation in literature_conclusion.limitations:
            st.caption(f"Limitation: {limitation}")

    if result.get("agent_steps"):
        st.subheader("Agent Steps")
        st.dataframe(result["agent_steps"], use_container_width=True, hide_index=True)

    source_plan = result.get("source_plan") or {}
    if source_plan:
        with st.expander("Source Plan"):
            st.json(source_plan)

    if interpretation.get("key_evidence"):
        st.subheader("Key Evidence")
        for line in interpretation["key_evidence"]:
            st.write(f"- {line}")
    if interpretation.get("cautions"):
        st.subheader("Interpretation Cautions")
        for line in interpretation["cautions"]:
            st.write(f"- {line}")

    st.subheader("Literature Evidence")
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

    claims = result.get("literature_claims") or []
    if claims:
        st.markdown("**Extracted Claim Sentences**")
        st.dataframe(_claims_to_frame(claims), use_container_width=True, hide_index=True)
    else:
        st.caption("No direct resistance or sensitivity claim sentence was extracted from titles/abstracts.")

    ranked_papers = result.get("ranked_papers") or []
    if ranked_papers:
        with st.expander("Ranked Literature Hits", expanded=True):
            st.dataframe(_ranked_papers_to_frame(ranked_papers[:25]), use_container_width=True, hide_index=True)

    digest = result.get("evidence_digest") or {}
    if digest.get("highlights"):
        st.subheader("Highlights")
        for line in digest["highlights"]:
            st.write(f"- {line}")
    if digest.get("cautions"):
        st.subheader("Cautions")
        for line in digest["cautions"]:
            st.write(f"- {line}")

    st.subheader("Normalized Query")
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
        st.subheader("Narrative Report")
        st.markdown(result["report_text"])

    database_summary = result.get("database_summary")
    if database_summary:
        st.subheader("Database Support")
        a, b, c = st.columns(3)
        a.metric("Database-only verdict", database_summary.verdict)
        b.metric("Curated direct", database_summary.direct_evidence_count)
        c.metric("Experimental support", database_summary.supporting_experimental_count)
        st.caption(database_summary.top_rationale)
        for error in (result.get("database_support") or {}).get("diagnostics", {}).get("errors", []):
            st.warning(error)

    sections = [
        ("Direct curated", result["direct_curated"]),
        ("Related curated", result["related_curated"]),
        ("Supporting experimental", result["supporting_experimental"]),
    ]

    for title, records in sections:
        st.subheader(title)
        if not records:
            st.caption("No records matched this section.")
            continue
        st.dataframe(_records_to_frame(records), use_container_width=True, hide_index=True)


def _manual_query_form():
    gene_options = load_gene_options()
    drug_options = load_drug_options()
    cancer_options = load_cancer_type_options()
    aa_options = amino_acid_options()

    col1, col2 = st.columns(2)
    with col1:
        gene_symbol = st.selectbox(
            "Gene symbol",
            gene_options,
            index=_option_index(gene_options, "EGFR"),
            help="Approved HGNC protein-coding gene symbols.",
        )
        biomarker_type = st.selectbox("Biomarker type", BIOMARKER_TYPES)

        if biomarker_type == "small_variant":
            st.caption("Build an amino-acid substitution, e.g. V600E or T790M.")
            aa_col1, aa_col2, aa_col3 = st.columns([2, 1, 2])
            with aa_col1:
                ref_aa = st.selectbox("Reference amino acid", aa_options, index=_option_index(aa_options, "T - Threonine"))
            with aa_col2:
                aa_position = st.number_input("Position", min_value=1, max_value=10000, value=790, step=1)
            with aa_col3:
                alt_aa = st.selectbox("Altered amino acid", aa_options, index=_option_index(aa_options, "M - Methionine"))
            alteration = build_small_variant(ref_aa, aa_position, alt_aa)
            st.caption(f"Alteration: `{alteration}`")
        else:
            alteration = st.text_input(
                "Alteration",
                value="EML4-ALK fusion" if biomarker_type == "fusion" else "",
                placeholder="e.g. EML4-ALK fusion, amplification, high expression",
            )

    with col2:
        drug_choices = [*drug_options, DRUG_OTHER_OPTION]
        drug_choice = st.selectbox(
            "Therapy / drug",
            drug_choices,
            index=_option_index(drug_choices, "Gefitinib"),
        )
        if drug_choice == DRUG_OTHER_OPTION:
            therapy = st.text_input("Other drug name", value="", placeholder="Type drug or therapy name")
        else:
            therapy = drug_choice

        cancer_type = st.selectbox(
            "Cancer type",
            cancer_options,
            index=_option_index(cancer_options, "NSCLC"),
        )

    submitted = st.button("Analyze", type="primary")

    if submitted:
        if not therapy.strip():
            st.error("Please enter a drug name when `Other` is selected.")
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
                {"skill": "manual_query", "status": "done", "summary": "Used the structured form instead of LLM parsing."},
                {"skill": "literature_search", "status": "done", "summary": f"Retrieved {len(result['literature_search']['records'])} literature records."},
                {"skill": "claim_extractor", "status": "done", "summary": f"Extracted {len(result['literature_claims'])} candidate claim sentences."},
                {"skill": "database_support", "status": "done", "summary": f"Attached {len(result['direct_curated']) + len(result['related_curated'])} curated and {len(result['supporting_experimental'])} experimental support records."},
            ]
        st.session_state.description = description
        st.session_state.result = result
        st.session_state.phase = "results"
        st.rerun()


def main():
    st.set_page_config(page_title="Variant-Response Discovery Engine", layout="wide")
    init_state()
    phase = st.session_state.phase
    llm_ready = llm_enabled()

    st.title("Variant-Response Discovery Engine")
    st.caption("Research-use discovery tool for variant, therapy, and cancer-context response evidence.")

    col1, col2 = st.columns([5, 1])
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
            st.info("LLM mode is disabled. Structured literature-first search still works; set `ANTHROPIC_API_KEY` to enable free-text parsing, biological context, and narrative reporting.")
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
        with st.spinner("Running variant-response analysis..."):
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
