import re

from src.normalization import normalize_cancer_type, normalize_therapy
from src.types import BiomarkerQuery, LiteratureRecord, RankedPaper

RESISTANCE_PATTERNS = [
    r"\bresistan(?:t|ce)\b",
    r"\brefractory\b",
    r"\bnon[- ]?response\b",
    r"\bprogression\b",
    r"\breduced sensitivity\b",
    r"\bincreased IC50\b",
]

SENSITIVITY_PATTERNS = [
    r"\bsensitiv(?:e|ity)\b",
    r"\brespond(?:er|ed|s|ing)?\b",
    r"(?<!non[- ])\bresponse\b",
    r"\bdecreased IC50\b",
    r"\bsynthetic lethal\b",
]

FUNCTIONAL_SCREEN_PATTERNS = [
    r"\bCRISPR\b",
    r"\bCas9\b",
    r"\bknockout\b",
    r"\bgenome[- ]wide\b",
    r"\bscreen(?:ing)?\b",
]

REVIEW_PATTERNS = {
    "review_article_language": [r"\breview\b", r"\bmeta-analysis\b"],
    "preclinical_only_language": [r"\bcell line\b", r"\bin vitro\b", r"\bxenograft\b"],
    "combination_therapy_language": [r"\bcombination\b", r"\bcombined with\b", r"\bplus\b"],
}


def rank_papers(query: BiomarkerQuery, records: list[LiteratureRecord]) -> list[RankedPaper]:
    ranked = [score_paper(query, record) for record in records]
    return sorted(ranked, key=lambda item: item.score, reverse=True)


def score_paper(query: BiomarkerQuery, paper: LiteratureRecord) -> RankedPaper:
    text = _combined_text(paper)
    therapy_info = normalize_therapy(query.therapy)
    cancer_info = normalize_cancer_type(query.cancer_type)

    gene_terms = [query.gene_symbol]
    alteration_terms = [query.alteration, f"{query.gene_symbol} {query.alteration}"]
    therapy_terms = [query.therapy, therapy_info["canonical"], *therapy_info["aliases"]]
    cancer_terms = [query.cancer_type, cancer_info["canonical"], *cancer_info["aliases"]]

    mentions_gene = _has_any(text, gene_terms)
    mentions_alteration = _has_any(text, alteration_terms)
    mentions_therapy = _has_any(text, therapy_terms)
    mentions_cancer = _has_any(text, cancer_terms)
    mentions_resistance = _has_pattern(text, RESISTANCE_PATTERNS)
    mentions_sensitivity = _has_pattern(text, SENSITIVITY_PATTERNS)
    has_abstract = bool(paper.abstract and len(paper.abstract) > 40)
    functional_screen_support = _has_pattern(text, FUNCTIONAL_SCREEN_PATTERNS)
    has_direct_claim = (
        mentions_gene
        and mentions_alteration
        and mentions_therapy
        and mentions_cancer
        and (mentions_resistance or mentions_sensitivity)
    )

    score = 0
    score += 4 if mentions_gene else 0
    score += 5 if mentions_alteration else 0
    score += 4 if mentions_therapy else 0
    score += 3 if mentions_cancer else 0
    score += 4 if mentions_resistance or mentions_sensitivity else 0
    score += 4 if has_direct_claim else 0
    score += 1 if functional_screen_support else 0
    score += 1 if has_abstract else -2

    review_flags = _review_flags(text)
    if mentions_resistance and mentions_sensitivity:
        review_flags.append("mixed_response_language")
        score -= 1
    needs_manual_review = bool(review_flags) or not has_direct_claim

    matched_terms = _matched_terms(
        text,
        gene_terms + alteration_terms + therapy_terms + cancer_terms,
        RESISTANCE_PATTERNS + SENSITIVITY_PATTERNS,
    )

    return RankedPaper(
        paper=paper,
        score=score,
        mentions_gene=mentions_gene,
        mentions_alteration=mentions_alteration,
        mentions_therapy=mentions_therapy,
        mentions_cancer=mentions_cancer,
        mentions_resistance=mentions_resistance,
        mentions_sensitivity=mentions_sensitivity,
        has_direct_claim=has_direct_claim,
        has_abstract=has_abstract,
        functional_screen_support=functional_screen_support,
        needs_manual_review=needs_manual_review,
        review_flags=review_flags,
        matched_terms=matched_terms,
        snippet=_snippet(text, matched_terms),
    )


def _combined_text(paper: LiteratureRecord) -> str:
    return " ".join([paper.title or "", paper.abstract or ""]).strip()


def _has_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term and term.lower() in lowered for term in terms)


def _has_pattern(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _review_flags(text: str) -> list[str]:
    flags = []
    for label, patterns in REVIEW_PATTERNS.items():
        if _has_pattern(text, patterns):
            flags.append(label)
    return flags


def _matched_terms(text: str, literal_terms: list[str], patterns: list[str]) -> list[str]:
    found = []
    lowered = text.lower()
    for term in literal_terms:
        if term and term.lower() in lowered:
            found.append(term)
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            found.append(match.group(0))
    return _dedupe(found)


def _snippet(text: str, terms: list[str], max_len: int = 320) -> str:
    clean = " ".join(text.split())
    if not clean:
        return ""
    positions = [clean.lower().find(term.lower()) for term in terms if term and clean.lower().find(term.lower()) >= 0]
    if not positions:
        return clean[:max_len] + ("..." if len(clean) > max_len else "")
    start = max(0, min(positions) - max_len // 3)
    end = min(len(clean), start + max_len)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean) else ""
    return prefix + clean[start:end] + suffix


def _dedupe(items: list[str]) -> list[str]:
    out = []
    seen = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
