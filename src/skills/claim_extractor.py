import re

from src.normalization import normalize_cancer_type, normalize_therapy
from src.types import BiomarkerQuery, ExtractedClaim, RankedPaper

RESISTANCE_PATTERNS = [
    r"\bresistan(?:t|ce)\b",
    r"\brefractory\b",
    r"\bnon[- ]?response\b",
    r"\bprogression\b",
]
SENSITIVITY_PATTERNS = [
    r"\bsensitiv(?:e|ity)\b",
    r"\brespond(?:er|ed|s|ing)?\b",
    r"(?<!non[- ])\bresponse\b",
]


def extract_claims(query: BiomarkerQuery, ranked_papers: list[RankedPaper], max_claims: int = 20) -> list[ExtractedClaim]:
    claims = []
    for ranked in ranked_papers:
        if not ranked.has_abstract and not ranked.paper.title:
            continue
        text = " ".join([ranked.paper.title, ranked.paper.abstract])
        for sentence in split_sentences(text):
            claim = extract_claim_from_sentence(query, ranked, sentence)
            if claim:
                claims.append(claim)
                if len(claims) >= max_claims:
                    return claims
    return claims


def extract_claim_from_sentence(query: BiomarkerQuery, ranked: RankedPaper, sentence: str) -> ExtractedClaim | None:
    lowered = sentence.lower()
    matched_terms = []
    score = 0

    therapy_info = normalize_therapy(query.therapy)
    cancer_info = normalize_cancer_type(query.cancer_type)

    profile_terms = _profile_terms(query)
    term_groups = {
        "gene": ([query.gene_symbol], 2),
        "profile": (profile_terms, 3),
        "therapy": ([query.therapy, therapy_info["canonical"], *therapy_info["aliases"]], 2),
        "cancer": ([query.cancer_type, cancer_info["canonical"], *cancer_info["aliases"]], 1),
    }
    group_matches = {}
    for group, (terms, weight) in term_groups.items():
        matched = _first_match(lowered, terms)
        if matched:
            group_matches[group] = matched
            matched_terms.append(matched)
            score += weight

    response_class = _response_class(lowered)
    if response_class == "INSUFFICIENT":
        return None

    score += 4
    if score < 6:
        return None

    claim_match_level, review_flags = _claim_specificity(query, ranked, group_matches)

    return ExtractedClaim(
        paper_id=ranked.paper.pmid or ranked.paper.doi or ranked.paper.title,
        claim_sentence=" ".join(sentence.split()),
        response_class=response_class,
        matched_terms=tuple(matched_terms),
        match_score=score,
        claim_match_level=claim_match_level,
        review_flags=tuple(review_flags),
    )


def direct_claims(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    return [claim for claim in claims if claim.claim_match_level == "direct_claim"]


def related_claims(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    return [claim for claim in claims if claim.claim_match_level == "related_claim"]


def _profile_terms(query: BiomarkerQuery) -> list[str]:
    if query.biomarker_type == "small_variant":
        return [query.alteration, f"{query.gene_symbol} {query.alteration}"]
    if query.biomarker_type == "fusion":
        return [
            query.alteration,
            f"{query.gene_symbol} fusion",
            f"{query.gene_symbol} rearrangement",
            f"{query.gene_symbol}-positive",
            f"{query.gene_symbol} positive",
        ]
    if query.biomarker_type == "copy_number":
        return [
            query.alteration,
            f"{query.gene_symbol} {query.alteration}",
            f"{query.gene_symbol} amplification",
            f"{query.gene_symbol} amplified",
            f"{query.gene_symbol} copy number",
        ]
    if query.biomarker_type == "expression":
        return [
            query.alteration,
            f"{query.gene_symbol} {query.alteration}",
            f"{query.gene_symbol} expression",
        ]
    return [
        query.alteration,
        f"{query.gene_symbol} {query.alteration}",
        f"{query.gene_symbol} mutation",
        f"{query.gene_symbol}-mutant",
        f"{query.gene_symbol} mutant",
    ]


def _claim_specificity(query: BiomarkerQuery, ranked: RankedPaper, group_matches: dict[str, str]) -> tuple[str, list[str]]:
    flags = []
    has_profile = bool(group_matches.get("profile"))
    has_therapy = bool(group_matches.get("therapy"))

    if not has_profile:
        flags.append("missing_exact_alteration" if query.biomarker_type == "small_variant" else "missing_profile_term")
    if group_matches.get("gene") and not has_profile:
        flags.append("gene_level_only")
    if not has_therapy:
        flags.append("therapy_response_without_profile")
    if not group_matches.get("cancer") and ranked.mentions_cancer:
        flags.append("paper_level_cancer_match")
    flags.extend(ranked.review_flags)

    if has_profile and has_therapy:
        return "direct_claim", _dedupe(flags)
    return "related_claim", _dedupe(flags)


def _first_match(lowered_sentence: str, terms: list[str]) -> str:
    for term in terms:
        if term and term.lower() in lowered_sentence:
            return term
    return ""


def _dedupe(items: list[str]) -> list[str]:
    out = []
    seen = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def split_sentences(text: str) -> list[str]:
    clean = " ".join((text or "").split())
    if not clean:
        return []
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", clean) if sentence.strip()]


def _response_class(lowered_sentence: str) -> str:
    has_resistance = any(re.search(pattern, lowered_sentence) for pattern in RESISTANCE_PATTERNS)
    has_sensitivity = any(re.search(pattern, lowered_sentence) for pattern in SENSITIVITY_PATTERNS)
    if has_resistance and has_sensitivity:
        return "CONFLICTING"
    if has_resistance:
        return "RESISTANT"
    if has_sensitivity:
        return "SENSITIVE"
    return "INSUFFICIENT"
