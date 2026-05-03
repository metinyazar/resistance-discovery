from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class BiomarkerQuery:
    gene_symbol: str
    biomarker_type: str
    alteration: str
    therapy: str
    cancer_type: str


@dataclass(frozen=True)
class ParsedQuery:
    gene_symbol: str
    biomarker_type: str
    alteration: str
    therapy: str
    cancer_type: str
    confidence: int
    reasoning: str

    def to_biomarker_query(self) -> BiomarkerQuery:
        return BiomarkerQuery(
            gene_symbol=self.gene_symbol,
            biomarker_type=self.biomarker_type,
            alteration=self.alteration,
            therapy=self.therapy,
            cancer_type=self.cancer_type,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MolecularProfile:
    gene_symbol: str
    biomarker_type: str
    alteration: str
    label: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    profile_class: str = ""


@dataclass
class EvidenceRecord:
    source: str
    evidence_kind: str
    profile_label: str
    disease: str
    therapy: str
    therapy_aliases: list[str]
    response_class: str
    evidence_level: str
    rating: float | None
    citation: str
    statement: str
    profile_match_level: str
    therapy_match_level: str
    cancer_match_level: str
    is_direct: bool
    variant_origin: str | None = None
    raw_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if "raw" in data and data["raw"] is None:
            data["raw"] = {}
        return data


@dataclass(frozen=True)
class LiteratureRecord:
    source: str
    pmid: str
    doi: str
    title: str
    journal: str
    year: str
    authors: str
    abstract: str
    url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RankedPaper:
    paper: LiteratureRecord
    score: int
    mentions_gene: bool
    mentions_alteration: bool
    mentions_therapy: bool
    mentions_cancer: bool
    mentions_resistance: bool
    mentions_sensitivity: bool
    has_direct_claim: bool
    has_abstract: bool
    functional_screen_support: bool
    needs_manual_review: bool
    review_flags: list[str]
    matched_terms: list[str]
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["paper"] = self.paper.to_dict()
        return data


@dataclass(frozen=True)
class ExtractedClaim:
    paper_id: str
    claim_sentence: str
    response_class: str
    matched_terms: tuple[str, ...]
    match_score: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LiteratureFirstConclusion:
    verdict: str
    confidence_band: str
    primary_literature_count: int
    supporting_database_count: int
    conflicting_count: int
    rationale: str
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerdictSummary:
    verdict: str
    confidence_band: str
    top_rationale: str
    direct_evidence_count: int
    conflicting_evidence_count: int
    supporting_experimental_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
