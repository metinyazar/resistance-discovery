from src.skills.civic_search import fetch_curated_evidence
from src.skills.gdsc_search import fetch_supporting_evidence


def fetch_database_support(query, profile, context) -> dict:
    try:
        curated = fetch_curated_evidence(query, profile, context["therapy"], context["cancer"])
        errors = []
    except Exception as exc:
        curated = []
        errors = [f"CIViC support lookup failed: {exc}"]

    supporting = fetch_supporting_evidence(query, profile, context["therapy"], context["cancer"])
    return {
        "direct_curated": [record for record in curated if record.is_direct],
        "related_curated": [record for record in curated if not record.is_direct],
        "supporting_experimental": supporting,
        "diagnostics": {"errors": errors},
    }
