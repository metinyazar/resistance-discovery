from prompts import QUERY_PARSER
from src.llm import json_completion
from src.types import ParsedQuery

ALLOWED_BIOMARKER_TYPES = {
    "small_variant",
    "fusion",
    "copy_number",
    "expression",
    "grouped_biomarker",
}


def parse_variant_query(description: str) -> ParsedQuery:
    payload = json_completion(
        QUERY_PARSER,
        f"Parse this oncology biomarker-response query:\n\n{description}",
        max_tokens=800,
        temperature=0.0,
    )
    return coerce_parsed_query(payload)


def coerce_parsed_query(payload: dict) -> ParsedQuery:
    biomarker_type = str(payload.get("biomarker_type", "")).strip().lower()
    if biomarker_type not in ALLOWED_BIOMARKER_TYPES:
        biomarker_type = "grouped_biomarker"

    confidence = int(payload.get("confidence", 0) or 0)
    confidence = max(0, min(100, confidence))

    return ParsedQuery(
        gene_symbol=str(payload.get("gene_symbol", "")).strip().upper(),
        biomarker_type=biomarker_type,
        alteration=str(payload.get("alteration", "")).strip(),
        therapy=str(payload.get("therapy", "")).strip(),
        cancer_type=str(payload.get("cancer_type", "")).strip(),
        confidence=confidence,
        reasoning=str(payload.get("reasoning", "")).strip(),
    )
