import json

from prompts import SOURCE_PLANNER
from src.llm import json_completion, llm_enabled


DEFAULT_PLAN = {
    "sources": [
        {
            "name": "literature",
            "priority": "primary",
            "reason": "Published abstracts are the primary source for biomarker-therapy response claims in v1.",
        },
        {
            "name": "civic",
            "priority": "supporting",
            "reason": "Accepted predictive CIViC evidence supports, replicates, or contradicts literature-derived claims.",
        },
        {
            "name": "gdsc",
            "priority": "supporting",
            "reason": "GDSC-style cell-line evidence can support but should not determine the clinical-style verdict.",
        },
    ],
    "search_strategy": [
        "Normalize the biomarker, therapy, and cancer context.",
        "Search literature broadly using Europe PMC and optional PubMed.",
        "Rank papers by gene, alteration, therapy, cancer, and response-language matches.",
        "Extract direct claim sentences from titles and abstracts.",
        "Attach curated and experimental database support after the literature claim is identified.",
    ],
    "limitations": [
        "This research workflow does not provide clinical decision support.",
    ],
}


def plan_sources(description: str, confirmed_query: dict) -> dict:
    if not llm_enabled():
        return DEFAULT_PLAN

    payload = json_completion(
        SOURCE_PLANNER,
        "Plan evidence retrieval for this biomarker-response question:\n\n"
        f"User question: {description}\n\n"
        f"Parsed query:\n{json.dumps(confirmed_query, indent=2)}",
        max_tokens=900,
        temperature=0.1,
    )
    return _coerce_plan(payload)


def _coerce_plan(payload: dict) -> dict:
    sources = payload.get("sources") or DEFAULT_PLAN["sources"]
    strategy = payload.get("search_strategy") or DEFAULT_PLAN["search_strategy"]
    limitations = payload.get("limitations") or DEFAULT_PLAN["limitations"]
    return {
        "sources": sources,
        "search_strategy": strategy,
        "limitations": limitations,
    }
