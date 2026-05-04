from prompts import REPORT_GENERATOR
from src.llm import create_message, llm_enabled


def generate_narrative(description: str, analysis_result: dict) -> str:
    if not llm_enabled():
        return ""

    query = analysis_result["query"]
    summary = analysis_result["summary"]
    evidence_digest = analysis_result.get("evidence_digest", {})
    interpretation = analysis_result.get("interpretation", {})
    source_plan = analysis_result.get("source_plan", {})
    literature_context = analysis_result.get("literature_context", "")
    evidence_conclusion = analysis_result.get("evidence_conclusion") or analysis_result.get("literature_conclusion")
    literature_claims = analysis_result.get("literature_claims", [])
    ranked_papers = analysis_result.get("ranked_papers", [])

    data_block = "\n".join(_format_section(name, records) for name, records in (
        ("Direct Curated", analysis_result.get("direct_curated", [])),
        ("Related Curated", analysis_result.get("related_curated", [])),
        ("Supporting Experimental", analysis_result.get("supporting_experimental", [])),
    ))

    user_prompt = (
        f"USER QUERY: {description}\n\n"
        f"NORMALIZED QUERY:\n"
        f"- Gene: {query.gene_symbol}\n"
        f"- Biomarker type: {query.biomarker_type}\n"
        f"- Alteration: {query.alteration}\n"
        f"- Therapy: {query.therapy}\n"
        f"- Cancer type: {query.cancer_type}\n\n"
        f"CURRENT VERDICT:\n"
        f"- Deterministic verdict: {summary.verdict}\n"
        f"- Agent verdict: {interpretation.get('verdict', summary.verdict)}\n"
        f"- Agent confidence: {interpretation.get('confidence_band', summary.confidence_band)}\n"
        f"- Rationale: {interpretation.get('rationale', summary.top_rationale)}\n\n"
        f"SOURCE PLAN:\n{source_plan}\n\n"
        f"EVIDENCE DIGEST:\n"
        f"- Highlights: {evidence_digest.get('highlights', [])}\n"
        f"- Cautions: {evidence_digest.get('cautions', [])}\n\n"
        f"DATABASE-PRIMARY CONCLUSION:\n"
        f"{evidence_conclusion.to_dict() if evidence_conclusion else 'No database-primary conclusion available.'}\n\n"
        f"EXTRACTED CLAIM SENTENCES:\n"
        f"{_format_claims(literature_claims)}\n\n"
        f"TOP RANKED PAPERS:\n"
        f"{_format_ranked_papers(ranked_papers[:10])}\n\n"
        f"INTERPRETATION:\n"
        f"- Key evidence: {interpretation.get('key_evidence', [])}\n"
        f"- Cautions: {interpretation.get('cautions', [])}\n\n"
        f"BIOLOGICAL CONTEXT:\n{literature_context or 'No additional biological context generated.'}\n\n"
        f"EVIDENCE RECORDS:\n{data_block}"
    )

    return create_message(REPORT_GENERATOR, user_prompt, max_tokens=2200, temperature=0.2)


def _format_claims(claims: list) -> str:
    if not claims:
        return "- none"
    return "\n".join(
        f"- {claim.response_class} | score={claim.match_score} | {claim.paper_id}: {claim.claim_sentence}"
        for claim in claims
    )


def _format_ranked_papers(ranked_papers: list) -> str:
    if not ranked_papers:
        return "- none"
    lines = []
    for ranked in ranked_papers:
        flags = ", ".join(ranked.review_flags) if ranked.review_flags else "none"
        lines.append(
            f"- score={ranked.score} | pmid={ranked.paper.pmid} | {ranked.paper.title} | "
            f"direct_claim={ranked.has_direct_claim} | manual_review={ranked.needs_manual_review} | flags={flags}"
        )
    return "\n".join(lines)


def _format_section(title: str, records: list) -> str:
    lines = [title.upper()]
    if not records:
        lines.append("- none")
        return "\n".join(lines)

    for record in records:
        lines.append(
            f"- {record.response_class} | {record.therapy} | {record.disease} | "
            f"{record.evidence_level or record.source} | {record.statement}"
        )
    return "\n".join(lines)
