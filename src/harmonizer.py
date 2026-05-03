import json

from prompts import HARMONIZER
from src.llm import json_completion, llm_enabled


def harmonize_evidence(analysis_result: dict) -> dict:
    records = []
    for section_key, section_name in (
        ("direct_curated", "Direct Curated"),
        ("related_curated", "Related Curated"),
        ("supporting_experimental", "Supporting Experimental"),
    ):
        for index, record in enumerate(analysis_result.get(section_key, []), start=1):
            records.append(
                {
                    "record_id": f"{section_key}:{index}",
                    "section": section_name,
                    "response_class": record.response_class,
                    "therapy": record.therapy,
                    "disease": record.disease,
                    "evidence_level": record.evidence_level,
                    "statement": record.statement,
                    "source": record.source,
                }
            )

    if not records:
        return {"highlights": [], "cautions": [], "groups": {}}

    if not llm_enabled() or len(records) <= 2:
        return _fallback_harmonization(records)

    payload = json_completion(
        HARMONIZER,
        "Summarize these matched oncology response-evidence records:\n\n" + json.dumps(records, indent=2),
        max_tokens=1200,
        temperature=0.1,
    )
    return {
        "highlights": payload.get("highlights", []),
        "cautions": payload.get("cautions", []),
        "groups": payload.get("groups", {}),
    }


def _fallback_harmonization(records: list[dict]) -> dict:
    highlights = []
    cautions = []
    groups = {}

    if records:
        strongest = records[0]
        highlights.append(
            f"{strongest['section']}: {strongest['response_class']} evidence for {strongest['therapy']} in {strongest['disease']}."
        )

    seen_responses = {record["response_class"] for record in records}
    if len(seen_responses) > 1:
        cautions.append("Matched evidence spans more than one response class and should be reviewed manually.")

    for record in records:
        theme = record["section"]
        groups.setdefault(theme, {"record_ids": [], "summary": f"{theme} evidence records."})
        groups[theme]["record_ids"].append(record["record_id"])

    return {"highlights": highlights, "cautions": cautions, "groups": groups}
