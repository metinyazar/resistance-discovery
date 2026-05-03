import re

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

    for term, weight in (
        (query.gene_symbol, 2),
        (query.alteration, 3),
        (query.therapy, 2),
        (query.cancer_type, 1),
    ):
        if term and term.lower() in lowered:
            matched_terms.append(term)
            score += weight

    response_class = _response_class(lowered)
    if response_class == "INSUFFICIENT":
        return None

    score += 4
    if score < 6:
        return None

    return ExtractedClaim(
        paper_id=ranked.paper.pmid or ranked.paper.doi or ranked.paper.title,
        claim_sentence=" ".join(sentence.split()),
        response_class=response_class,
        matched_terms=tuple(matched_terms),
        match_score=score,
    )


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
