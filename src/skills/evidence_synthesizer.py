from collections import Counter

from src.types import EvidenceConclusion, ExtractedClaim

RESPONSE_CLASSES = {"SENSITIVE", "RESISTANT", "ADVERSE"}


def synthesize_database_primary(
    claims: list[ExtractedClaim],
    direct_curated,
    related_curated,
    supporting_experimental,
) -> EvidenceConclusion:
    direct_counts = _record_counts(direct_curated)
    related_counts = _record_counts(related_curated)
    experimental_counts = _record_counts(supporting_experimental)
    literature_counts = _claim_counts(claims)

    database_verdict, database_conflicts = _database_verdict(direct_counts, related_counts)
    literature_verdict, literature_conflicts = _dominant_verdict(literature_counts)

    if database_verdict != "INSUFFICIENT":
        final_verdict = database_verdict
        evidence_basis = "direct_curated" if direct_counts else "related_curated"
        database_support = direct_counts.get(database_verdict, 0) + related_counts.get(database_verdict, 0)
        literature_support = literature_counts.get(database_verdict, 0)
        experimental_support = experimental_counts.get(database_verdict, 0)

        conflicts = (
            database_conflicts
            + literature_conflicts
            + _opposing_count(literature_counts, database_verdict)
        )
        if conflicts:
            final_verdict = "CONFLICTING"
    elif literature_verdict != "INSUFFICIENT":
        final_verdict = literature_verdict
        evidence_basis = "literature_only"
        database_support = 0
        literature_support = literature_counts.get(literature_verdict, 0)
        experimental_support = experimental_counts.get(literature_verdict, 0)
        conflicts = literature_conflicts
        if conflicts:
            final_verdict = "CONFLICTING"
    else:
        experimental_verdict, experimental_conflicts = _dominant_verdict(experimental_counts)
        if experimental_verdict != "INSUFFICIENT":
            final_verdict = "INSUFFICIENT"
            evidence_basis = "experimental_only"
            database_support = 0
            literature_support = 0
            experimental_support = experimental_counts.get(experimental_verdict, 0)
            conflicts = experimental_conflicts
        else:
            final_verdict = "INSUFFICIENT"
            evidence_basis = "no_evidence"
            database_support = 0
            literature_support = 0
            experimental_support = 0
            conflicts = 0

    score = _confidence_score(
        evidence_basis=evidence_basis,
        final_verdict=final_verdict,
        direct_counts=direct_counts,
        related_counts=related_counts,
        literature_support=literature_support,
        experimental_support=experimental_support,
        conflicts=conflicts,
    )
    confidence = _confidence_band(score, final_verdict)
    limitations = _limitations(
        evidence_basis,
        final_verdict,
        database_verdict,
        literature_verdict,
        literature_support,
        experimental_support,
        conflicts,
        claims,
    )

    return EvidenceConclusion(
        verdict=final_verdict,
        confidence_band=confidence,
        evidence_basis=evidence_basis,
        rationale=_rationale(
            final_verdict,
            evidence_basis,
            database_verdict,
            literature_verdict,
            database_support,
            literature_support,
            experimental_support,
            conflicts,
        ),
        database_verdict=database_verdict,
        literature_verdict=literature_verdict,
        database_support_count=database_support,
        literature_support_count=literature_support,
        experimental_support_count=experimental_support,
        conflicting_count=conflicts,
        confidence_score=score,
        limitations=limitations,
    )


def synthesize_literature_first(
    claims: list[ExtractedClaim],
    direct_curated,
    related_curated,
    supporting_experimental,
) -> EvidenceConclusion:
    return synthesize_database_primary(claims, direct_curated, related_curated, supporting_experimental)


def _record_counts(records) -> Counter:
    return Counter(record.response_class for record in records if record.response_class in RESPONSE_CLASSES)


def _claim_counts(claims: list[ExtractedClaim]) -> Counter:
    return Counter(claim.response_class for claim in claims if claim.response_class in RESPONSE_CLASSES)


def _database_verdict(direct_counts: Counter, related_counts: Counter) -> tuple[str, int]:
    if direct_counts:
        return _dominant_verdict(direct_counts)
    if related_counts:
        return _dominant_verdict(related_counts)
    return "INSUFFICIENT", 0


def _dominant_verdict(counts: Counter) -> tuple[str, int]:
    if not counts:
        return "INSUFFICIENT", 0
    top_response, top_count = counts.most_common(1)[0]
    conflicts = sum(count for response, count in counts.items() if response != top_response)
    if conflicts and counts.most_common()[1][1] == top_count:
        return "CONFLICTING", conflicts
    return top_response, conflicts


def _opposing_count(counts: Counter, verdict: str) -> int:
    if verdict not in RESPONSE_CLASSES:
        return sum(counts.values())
    return sum(count for response, count in counts.items() if response != verdict)


def _confidence_score(
    evidence_basis: str,
    final_verdict: str,
    direct_counts: Counter,
    related_counts: Counter,
    literature_support: int,
    experimental_support: int,
    conflicts: int,
) -> int:
    if final_verdict in {"CONFLICTING", "INSUFFICIENT"} and evidence_basis in {"no_evidence", "experimental_only"}:
        base = 0
    elif evidence_basis == "direct_curated":
        base = 6
    elif evidence_basis == "related_curated":
        base = 4
    elif evidence_basis == "literature_only":
        base = 3
    else:
        base = 1

    direct_strength = min(sum(direct_counts.values()), 2)
    related_strength = 1 if related_counts else 0
    literature_strength = min(literature_support, 2)
    experimental_strength = 1 if experimental_support else 0
    conflict_penalty = min(conflicts * 3, 6)
    score = base + direct_strength + related_strength + literature_strength + experimental_strength - conflict_penalty
    return max(score, 0)


def _confidence_band(score: int, final_verdict: str) -> str:
    if final_verdict == "CONFLICTING":
        return "low"
    if score >= 8:
        return "high"
    if score >= 4:
        return "moderate"
    return "low"


def _limitations(
    evidence_basis: str,
    final_verdict: str,
    database_verdict: str,
    literature_verdict: str,
    literature_support: int,
    experimental_support: int,
    conflicts: int,
    claims: list[ExtractedClaim],
) -> list[str]:
    limitations = []
    if evidence_basis == "literature_only":
        limitations.append("No direct or related curated database evidence matched; verdict is literature-only.")
    if evidence_basis == "experimental_only":
        limitations.append("Only experimental support matched; this is not enough for a primary response verdict.")
    if evidence_basis == "no_evidence":
        limitations.append("No curated, literature, or experimental response evidence matched this query.")
    if database_verdict != "INSUFFICIENT" and not literature_support:
        limitations.append("Curated database evidence was not validated by extracted literature claims.")
    if literature_verdict != "INSUFFICIENT" and database_verdict == "INSUFFICIENT":
        limitations.append("Literature claim was found without curated database support.")
    if experimental_support and evidence_basis != "experimental_only":
        limitations.append("Experimental evidence is supportive only and does not drive the primary verdict.")
    if conflicts or final_verdict == "CONFLICTING":
        limitations.append("Evidence sources contain opposing response classes and require manual review.")
    if claims and any("review" in " ".join(claim.matched_terms).lower() for claim in claims):
        limitations.append("Some literature evidence may be review-level rather than primary study evidence.")
    return limitations


def _rationale(
    final_verdict: str,
    evidence_basis: str,
    database_verdict: str,
    literature_verdict: str,
    database_support: int,
    literature_support: int,
    experimental_support: int,
    conflicts: int,
) -> str:
    if final_verdict == "CONFLICTING":
        return (
            f"Primary database verdict was {database_verdict}, literature verdict was {literature_verdict}, "
            f"and {conflicts} opposing signal(s) were detected."
        )
    if evidence_basis in {"direct_curated", "related_curated"}:
        return (
            f"Database evidence drives the {final_verdict.lower()} verdict "
            f"({database_support} curated record(s)); literature adds {literature_support} matching claim(s), "
            f"and experimental evidence adds {experimental_support} supporting record(s)."
        )
    if evidence_basis == "literature_only":
        return (
            f"No curated database evidence matched, but literature extraction found "
            f"{literature_support} {final_verdict.lower()} claim(s)."
        )
    if evidence_basis == "experimental_only":
        return "Only experimental support matched; database and literature evidence were insufficient for a primary verdict."
    return "No response evidence was strong enough to support a verdict."
