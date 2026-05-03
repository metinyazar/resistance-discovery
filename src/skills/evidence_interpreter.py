import json

from prompts import EVIDENCE_INTERPRETER
from src.llm import json_completion, llm_enabled
from src.types import VerdictSummary


def interpret_evidence(
    query,
    direct_curated,
    related_curated,
    supporting,
    deterministic_summary: VerdictSummary,
    literature_claims=None,
    ranked_papers=None,
) -> dict:
    literature_claims = literature_claims or []
    ranked_papers = ranked_papers or []
    if not llm_enabled():
        return _fallback_interpretation(
            deterministic_summary,
            direct_curated,
            related_curated,
            supporting,
            literature_claims,
        )

    payload = json_completion(
        EVIDENCE_INTERPRETER,
        "Interpret this biomarker-response evidence:\n\n"
        + json.dumps(
            {
                "query": {
                    "gene_symbol": query.gene_symbol,
                    "biomarker_type": query.biomarker_type,
                    "alteration": query.alteration,
                    "therapy": query.therapy,
                    "cancer_type": query.cancer_type,
                },
                "deterministic_summary": deterministic_summary.to_dict(),
                "literature_claims": [claim.to_dict() for claim in literature_claims],
                "top_ranked_papers": [_paper_digest(ranked) for ranked in ranked_papers[:10]],
                "direct_curated": [_record_digest(record) for record in direct_curated],
                "related_curated": [_record_digest(record) for record in related_curated],
                "supporting_experimental": [_record_digest(record) for record in supporting],
            },
            indent=2,
        ),
        max_tokens=1300,
        temperature=0.1,
    )
    return _coerce_interpretation(payload, deterministic_summary)


def _fallback_interpretation(summary, direct_curated, related_curated, supporting, literature_claims=None) -> dict:
    literature_claims = literature_claims or []
    key_evidence = []
    for claim in literature_claims[:5]:
        key_evidence.append(f"{claim.response_class}: {claim.claim_sentence}")

    for record in (direct_curated + related_curated + supporting)[:5]:
        key_evidence.append(
            f"{record.response_class}: {record.profile_label} with {record.therapy} in {record.disease} ({record.source})."
        )

    cautions = []
    if not literature_claims:
        cautions.append("No direct literature claim sentence was extracted from titles or abstracts.")
    if supporting and not direct_curated:
        cautions.append("Experimental support is present but cannot determine the primary verdict.")

    return {
        "verdict": summary.verdict,
        "confidence_band": summary.confidence_band,
        "rationale": summary.top_rationale,
        "key_evidence": key_evidence,
        "cautions": cautions,
    }


def _coerce_interpretation(payload: dict, fallback: VerdictSummary) -> dict:
    verdict = payload.get("verdict") or fallback.verdict
    confidence = payload.get("confidence_band") or fallback.confidence_band
    return {
        "verdict": verdict,
        "confidence_band": confidence,
        "rationale": payload.get("rationale") or fallback.top_rationale,
        "key_evidence": payload.get("key_evidence") or [],
        "cautions": payload.get("cautions") or [],
    }


def _record_digest(record) -> dict:
    return {
        "source": record.source,
        "profile": record.profile_label,
        "therapy": record.therapy,
        "disease": record.disease,
        "response_class": record.response_class,
        "evidence_level": record.evidence_level,
        "rating": record.rating,
        "match": {
            "profile": record.profile_match_level,
            "therapy": record.therapy_match_level,
            "cancer": record.cancer_match_level,
            "is_direct": record.is_direct,
        },
        "statement": record.statement,
    }


def _paper_digest(ranked) -> dict:
    return {
        "pmid": ranked.paper.pmid,
        "doi": ranked.paper.doi,
        "title": ranked.paper.title,
        "year": ranked.paper.year,
        "source": ranked.paper.source,
        "score": ranked.score,
        "flags": {
            "mentions_gene": ranked.mentions_gene,
            "mentions_alteration": ranked.mentions_alteration,
            "mentions_therapy": ranked.mentions_therapy,
            "mentions_cancer": ranked.mentions_cancer,
            "mentions_resistance": ranked.mentions_resistance,
            "mentions_sensitivity": ranked.mentions_sensitivity,
            "has_direct_claim": ranked.has_direct_claim,
            "functional_screen_support": ranked.functional_screen_support,
            "needs_manual_review": ranked.needs_manual_review,
            "review_flags": ranked.review_flags,
        },
        "snippet": ranked.snippet,
    }
