from prompts import LITERATURE
from src.llm import create_message, llm_enabled


def get_literature_context(query, analysis_result: dict) -> str:
    if not llm_enabled():
        return ""

    summary = analysis_result["summary"]
    prompt = (
        f"Gene: {query.gene_symbol}\n"
        f"Biomarker type: {query.biomarker_type}\n"
        f"Alteration: {query.alteration}\n"
        f"Therapy: {query.therapy}\n"
        f"Cancer type: {query.cancer_type}\n"
        f"Current verdict: {summary.verdict}\n"
        f"Confidence: {summary.confidence_band}\n"
    )
    return create_message(LITERATURE, prompt, max_tokens=1200, temperature=0.2)
