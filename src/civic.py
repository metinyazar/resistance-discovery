import hashlib
import json

import requests

from src.config import CIVIC_GRAPHQL_URL, DEFAULT_PAGE_SIZE
from src.db import get_civic_cache, put_civic_cache
from src.normalization import (
    classify_cancer_match,
    classify_profile_match,
    classify_therapy_match,
)
from src.types import EvidenceRecord, MolecularProfile


EVIDENCE_QUERY = """
query($molecularProfileName:String,$therapyName:String,$diseaseName:String,$first:Int!){
  evidenceItems(
    first:$first,
    evidenceType:PREDICTIVE,
    status:ACCEPTED,
    molecularProfileName:$molecularProfileName,
    therapyName:$therapyName,
    diseaseName:$diseaseName
  ){
    totalCount
    nodes{
      id
      name
      significance
      evidenceDirection
      evidenceLevel
      evidenceRating
      status
      description
      variantOrigin
      molecularProfile{ name }
      disease{ name displayName }
      therapies{ name therapyAliases }
    }
  }
}
"""

ASSERTION_QUERY = """
query($molecularProfileName:String,$therapyName:String,$diseaseName:String,$first:Int!){
  assertions(
    first:$first,
    assertionType:PREDICTIVE,
    status:ACCEPTED,
    molecularProfileName:$molecularProfileName,
    therapyName:$therapyName,
    diseaseName:$diseaseName
  ){
    totalCount
    nodes{
      id
      name
      description
      significance
      assertionDirection
      ampLevel
      molecularProfile{ name }
      disease{ name displayName }
      therapies{ name therapyAliases }
    }
  }
}
"""


def fetch_curated_evidence(query, profile: MolecularProfile, therapy_info, cancer_info) -> list[EvidenceRecord]:
    nodes = []
    seen = set()

    profile_terms = list(dict.fromkeys([profile.label, *profile.aliases, query.gene_symbol]))
    therapy_terms = list(dict.fromkeys([query.therapy, therapy_info["query"], therapy_info["class_name"]]))
    disease_terms = list(dict.fromkeys([query.cancer_type, cancer_info["query"]]))

    for profile_term in profile_terms[:3]:
        payload = _graphql(
            EVIDENCE_QUERY,
            {
                "molecularProfileName": profile_term,
                "therapyName": None,
                "diseaseName": None,
                "first": DEFAULT_PAGE_SIZE,
            },
        )
        for node in payload["evidenceItems"]["nodes"]:
            key = ("evidence", node["id"])
            if key not in seen:
                seen.add(key)
                nodes.append(_map_evidence_node(node, profile, therapy_info, cancer_info))

    for profile_term in profile_terms[:2]:
        for therapy_term in therapy_terms[:2]:
            payload = _graphql(
                ASSERTION_QUERY,
                {
                    "molecularProfileName": profile_term,
                    "therapyName": therapy_term,
                    "diseaseName": disease_terms[0] if disease_terms else None,
                    "first": DEFAULT_PAGE_SIZE,
                },
            )
            for node in payload["assertions"]["nodes"]:
                key = ("assertion", node["id"])
                if key not in seen:
                    seen.add(key)
                    nodes.append(_map_assertion_node(node, profile, therapy_info, cancer_info))

    filtered = [
        record
        for record in nodes
        if record.profile_match_level != "none"
        and record.therapy_match_level != "none"
        and record.cancer_match_level != "none"
    ]

    return sorted(filtered, key=_sort_key, reverse=True)


def _graphql(query: str, variables: dict) -> dict:
    cache_key = _cache_key(query, variables)
    cached = get_civic_cache(cache_key)
    if cached is not None:
        return cached["data"]

    response = requests.post(
        CIVIC_GRAPHQL_URL,
        json={"query": query, "variables": variables},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(f"CIViC GraphQL error: {payload['errors']}")
    put_civic_cache(cache_key, payload)
    return payload["data"]


def _map_evidence_node(node, profile, therapy_info, cancer_info) -> EvidenceRecord:
    therapy = (node.get("therapies") or [{}])[0]
    therapy_name = therapy.get("name", "")
    disease = node.get("disease") or {}
    profile_name = (node.get("molecularProfile") or {}).get("name", "")

    response_class = _map_civic_response(node.get("significance"), node.get("evidenceDirection"))
    profile_match = classify_profile_match(profile, profile_name)
    therapy_match = classify_therapy_match(therapy_info, therapy_name, therapy.get("therapyAliases"))
    cancer_match = classify_cancer_match(cancer_info, disease.get("displayName") or disease.get("name") or "")
    is_direct = profile_match == "exact" and therapy_match in {"exact", "class"} and cancer_match == "exact"

    return EvidenceRecord(
        source="civic_evidence",
        evidence_kind="curated_predictive",
        profile_label=profile_name,
        disease=disease.get("displayName") or disease.get("name") or "",
        therapy=therapy_name,
        therapy_aliases=therapy.get("therapyAliases") or [],
        response_class=response_class,
        evidence_level=node.get("evidenceLevel") or "",
        rating=float(node["evidenceRating"]) if node.get("evidenceRating") is not None else None,
        citation=node.get("name") or "",
        statement=node.get("description") or "",
        profile_match_level=profile_match,
        therapy_match_level=therapy_match,
        cancer_match_level=cancer_match,
        is_direct=is_direct,
        variant_origin=node.get("variantOrigin"),
        raw_id=str(node.get("id")),
        raw=node,
    )


def _map_assertion_node(node, profile, therapy_info, cancer_info) -> EvidenceRecord:
    therapy = (node.get("therapies") or [{}])[0]
    therapy_name = therapy.get("name", "")
    disease = node.get("disease") or {}
    profile_name = (node.get("molecularProfile") or {}).get("name", "")

    response_class = _map_civic_response(node.get("significance"), node.get("assertionDirection"))
    profile_match = classify_profile_match(profile, profile_name)
    therapy_match = classify_therapy_match(therapy_info, therapy_name, therapy.get("therapyAliases"))
    cancer_match = classify_cancer_match(cancer_info, disease.get("displayName") or disease.get("name") or "")
    is_direct = profile_match == "exact" and therapy_match in {"exact", "class"} and cancer_match == "exact"

    return EvidenceRecord(
        source="civic_assertion",
        evidence_kind="curated_predictive",
        profile_label=profile_name,
        disease=disease.get("displayName") or disease.get("name") or "",
        therapy=therapy_name,
        therapy_aliases=therapy.get("therapyAliases") or [],
        response_class=response_class,
        evidence_level=node.get("ampLevel") or "",
        rating=None,
        citation=node.get("name") or "",
        statement=node.get("description") or "",
        profile_match_level=profile_match,
        therapy_match_level=therapy_match,
        cancer_match_level=cancer_match,
        is_direct=is_direct,
        raw_id=str(node.get("id")),
        raw=node,
    )


def _map_civic_response(significance: str | None, direction: str | None) -> str:
    significance_value = (significance or "").upper()
    direction_value = (direction or "").upper()

    if significance_value in {"RESISTANCE", "REDUCED SENSITIVITY", "REDUCED_SENSITIVITY"}:
        return "RESISTANT"
    if significance_value in {"SENSITIVITY", "SENSITIVITY/RESPONSE", "SENSITIVITY_RESPONSE", "BETTER OUTCOME"}:
        return "SENSITIVE"
    if significance_value in {"ADVERSE RESPONSE", "ADVERSE_RESPONSE", "TOXICITY"}:
        return "ADVERSE"
    if significance_value == "NEGATIVE":
        return "ADVERSE" if direction_value == "SUPPORTS" else "INSUFFICIENT"
    return "INSUFFICIENT"


def _sort_key(record: EvidenceRecord):
    source_rank = 2 if record.source == "civic_assertion" else 1
    level = record.evidence_level or ""
    level_rank = {"A": 4, "B": 3, "C": 2, "D": 1}.get(level, 0)
    rating_rank = record.rating or 0
    return (
        int(record.is_direct),
        source_rank,
        level_rank,
        rating_rank,
    )


def _cache_key(query: str, variables: dict) -> str:
    raw = json.dumps({"query": query, "variables": variables}, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
