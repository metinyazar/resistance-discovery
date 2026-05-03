from collections import Counter

from src.types import ExtractedClaim, LiteratureFirstConclusion


def synthesize_literature_first(
    claims: list[ExtractedClaim],
    direct_curated,
    related_curated,
    supporting_experimental,
) -> LiteratureFirstConclusion:
    literature_counts = Counter(claim.response_class for claim in claims if claim.response_class != "INSUFFICIENT")
    database_records = direct_curated + related_curated + supporting_experimental
    database_counts = Counter(record.response_class for record in database_records if record.response_class != "INSUFFICIENT")

    if not literature_counts:
        return LiteratureFirstConclusion(
            verdict="INSUFFICIENT",
            confidence_band="low",
            primary_literature_count=0,
            supporting_database_count=len(database_records),
            conflicting_count=0,
            rationale="No direct resistance or sensitivity claim was extracted from the retrieved literature.",
            limitations=["Database-only evidence is supporting context in literature-first mode."],
        )

    top_response, top_count = literature_counts.most_common(1)[0]
    conflicting_lit = sum(count for response, count in literature_counts.items() if response != top_response)
    database_disagreement = sum(count for response, count in database_counts.items() if response != top_response)

    if conflicting_lit or database_disagreement:
        verdict = "CONFLICTING"
    else:
        verdict = top_response

    supporting_database_count = database_counts.get(top_response, 0)
    confidence = _confidence(top_count, supporting_database_count, conflicting_lit, database_disagreement)
    rationale = _rationale(verdict, top_response, top_count, supporting_database_count, conflicting_lit, database_disagreement)

    limitations = []
    if not supporting_database_count:
        limitations.append("No database support matched the dominant literature claim.")
    if database_disagreement:
        limitations.append("Database evidence includes response classes that disagree with the dominant literature claim.")
    if conflicting_lit:
        limitations.append("Retrieved literature includes mixed response language.")

    return LiteratureFirstConclusion(
        verdict=verdict,
        confidence_band=confidence,
        primary_literature_count=len(claims),
        supporting_database_count=supporting_database_count,
        conflicting_count=conflicting_lit + database_disagreement,
        rationale=rationale,
        limitations=limitations,
    )


def _confidence(top_count: int, database_support: int, conflicting_lit: int, database_disagreement: int) -> str:
    if conflicting_lit or database_disagreement:
        return "low"
    if top_count >= 2 and database_support >= 1:
        return "high"
    if top_count >= 1:
        return "moderate" if database_support else "low"
    return "low"


def _rationale(verdict: str, top_response: str, top_count: int, database_support: int, conflicting_lit: int, database_disagreement: int) -> str:
    if verdict == "CONFLICTING":
        return (
            f"Literature extraction found {top_count} {top_response.lower()} claim(s), "
            f"but {conflicting_lit + database_disagreement} conflicting literature/database signal(s) were also found."
        )
    return (
        f"Literature extraction found {top_count} {top_response.lower()} claim(s); "
        f"{database_support} database record(s) support the same response class."
    )
