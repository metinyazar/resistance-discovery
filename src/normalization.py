import re

from src.types import BiomarkerQuery, MolecularProfile


THERAPY_GROUPS = {
    "egfr tki": {
        "canonical": "EGFR inhibitor",
        "aliases": {
            "egfr tki",
            "egfr inhibitor",
            "gefitinib",
            "erlotinib",
            "afatinib",
            "osimertinib",
            "dacomitinib",
        },
    },
    "egfr antibody": {
        "canonical": "EGFR antibody",
        "aliases": {
            "egfr antibody",
            "cetuximab",
            "cetuximab, erbitux",
            "erbitux",
            "panitumumab",
        },
    },
    "braf inhibitor": {
        "canonical": "BRAF inhibitor",
        "aliases": {
            "braf inhibitor",
            "raf inhibitor",
            "vemurafenib",
            "dabrafenib",
            "encorafenib",
            "plx-4720",
            "sb-590885",
        },
    },
    "mek inhibitor": {
        "canonical": "MEK inhibitor",
        "aliases": {
            "mek inhibitor",
            "trametinib",
            "binimetinib",
            "cobimetinib",
            "selumetinib",
            "pd-0325901",
            "pd-184352",
        },
    },
    "alk inhibitor": {
        "canonical": "ALK inhibitor",
        "aliases": {
            "alk inhibitor",
            "crizotinib",
            "ceritinib",
            "alectinib",
            "brigatinib",
            "lorlatinib",
        },
    },
    "erbb2 inhibitor": {
        "canonical": "ERBB2 inhibitor",
        "aliases": {
            "erbb2 inhibitor",
            "her2 inhibitor",
            "lapatinib",
            "neratinib",
            "tucatinib",
            "trastuzumab",
            "pertuzumab",
            "t-dm1",
            "trastuzumab deruxtecan",
        },
    },
    "pi3k inhibitor": {
        "canonical": "PI3K inhibitor",
        "aliases": {
            "pi3k inhibitor",
            "alpelisib",
            "taselisib",
            "buparlisib",
            "pictilisib",
            "gdc-0941",
            "zstk-474",
            "gsk2126458",
            "idelalisib",
        },
    },
    "akt inhibitor": {
        "canonical": "AKT inhibitor",
        "aliases": {
            "akt inhibitor",
            "mk-2206",
            "uprosertib",
            "capivasertib",
            "ipatasertib",
        },
    },
    "mtor inhibitor": {
        "canonical": "mTOR inhibitor",
        "aliases": {
            "mtor inhibitor",
            "everolimus",
            "temsirolimus",
            "azd8055",
        },
    },
    "parp inhibitor": {
        "canonical": "PARP inhibitor",
        "aliases": {
            "parp inhibitor",
            "olaparib",
            "rucaparib",
            "niraparib",
            "talazoparib",
            "veliparib",
        },
    },
    "kras g12c inhibitor": {
        "canonical": "KRAS G12C inhibitor",
        "aliases": {
            "kras g12c inhibitor",
            "kras inhibitor",
            "sotorasib",
            "adagrasib",
        },
    },
    "cdk4/6 inhibitor": {
        "canonical": "CDK4/6 inhibitor",
        "aliases": {
            "cdk4/6 inhibitor",
            "cdk4 inhibitor",
            "cdk6 inhibitor",
            "palbociclib",
            "ribociclib",
            "abemaciclib",
        },
    },
    "met inhibitor": {
        "canonical": "MET inhibitor",
        "aliases": {
            "met inhibitor",
            "capmatinib",
            "tepotinib",
            "savolitinib",
            "crizotinib",
        },
    },
    "ret inhibitor": {
        "canonical": "RET inhibitor",
        "aliases": {
            "ret inhibitor",
            "selpercatinib",
            "pralsetinib",
        },
    },
    "ntrk inhibitor": {
        "canonical": "NTRK inhibitor",
        "aliases": {
            "ntrk inhibitor",
            "trk inhibitor",
            "larotrectinib",
            "entrectinib",
        },
    },
}

CANCER_SYNONYMS = {
    "nsclc": "Lung Non-small Cell Carcinoma",
    "non small cell lung cancer": "Lung Non-small Cell Carcinoma",
    "non-small cell lung cancer": "Lung Non-small Cell Carcinoma",
    "lung adenocarcinoma": "Lung Adenocarcinoma",
    "melanoma": "Melanoma",
    "breast cancer": "Breast Carcinoma",
    "breast carcinoma": "Breast Carcinoma",
}

CANCER_LINEAGES = {
    "Lung Non-small Cell Carcinoma": {"lung", "thoracic"},
    "Lung Adenocarcinoma": {"lung", "thoracic"},
    "Melanoma": {"skin", "melanoma"},
    "Breast Carcinoma": {"breast"},
}


def normalize_query(
    gene_symbol: str,
    biomarker_type: str,
    alteration: str,
    therapy: str,
    cancer_type: str,
) -> tuple[BiomarkerQuery, MolecularProfile, dict[str, object]]:
    gene = _normalize_gene_symbol(gene_symbol)
    biomarker = biomarker_type.strip().lower()
    canonical_alteration = _normalize_alteration(gene, biomarker, alteration)
    therapy_info = normalize_therapy(therapy)
    cancer_info = normalize_cancer_type(cancer_type)

    query = BiomarkerQuery(
        gene_symbol=gene,
        biomarker_type=biomarker,
        alteration=canonical_alteration,
        therapy=therapy_info["canonical"],
        cancer_type=cancer_info["canonical"],
    )
    profile = build_molecular_profile(query)

    return query, profile, {
        "therapy": therapy_info,
        "cancer": cancer_info,
    }


def build_molecular_profile(query: BiomarkerQuery) -> MolecularProfile:
    alteration = query.alteration
    gene = query.gene_symbol
    biomarker = query.biomarker_type

    if biomarker == "small_variant":
        label = f"{gene} {alteration}".strip()
        aliases = (alteration, label)
        profile_class = "small_variant"
    elif biomarker == "fusion":
        label = alteration if "fusion" in alteration.lower() else f"{alteration} fusion"
        aliases = (label, f"{gene} fusion")
        profile_class = "fusion"
    elif biomarker == "copy_number":
        label = f"{gene} {alteration}".strip()
        aliases = (label, f"{gene} copy number")
        profile_class = "copy_number"
    elif biomarker == "expression":
        label = f"{gene} {alteration}".strip()
        aliases = (label, f"{gene} expression")
        profile_class = "expression"
    else:
        label = f"{gene} {alteration}".strip()
        aliases = (label, gene)
        profile_class = "grouped_biomarker"

    deduped = tuple(dict.fromkeys(a for a in aliases if a))
    return MolecularProfile(
        gene_symbol=gene,
        biomarker_type=biomarker,
        alteration=alteration,
        label=label,
        aliases=deduped,
        profile_class=profile_class,
    )


def normalize_therapy(value: str) -> dict[str, object]:
    cleaned = _clean_spaces(value).lower()
    for group in THERAPY_GROUPS.values():
        aliases = group["aliases"]
        if cleaned in aliases:
            return {
                "canonical": group["canonical"],
                "query": cleaned,
                "aliases": sorted(aliases | {group["canonical"].lower()}),
                "class_name": group["canonical"],
            }

    title = _smart_title(cleaned)
    return {
        "canonical": title,
        "query": cleaned,
        "aliases": [cleaned, title.lower()],
        "class_name": title,
    }


def normalize_cancer_type(value: str) -> dict[str, object]:
    cleaned = _clean_spaces(value).lower()
    canonical = CANCER_SYNONYMS.get(cleaned, _smart_title(cleaned))
    lineage = sorted(CANCER_LINEAGES.get(canonical, {cleaned.split()[0] if cleaned else "unknown"}))
    aliases = {cleaned, canonical.lower()}
    for synonym, mapped in CANCER_SYNONYMS.items():
        if mapped == canonical:
            aliases.add(synonym)

    return {
        "canonical": canonical,
        "query": cleaned,
        "aliases": sorted(a for a in aliases if a),
        "lineages": lineage,
    }


def classify_profile_match(profile: MolecularProfile, candidate_label: str) -> str:
    normalized_candidate = _clean_spaces(candidate_label).lower()
    if normalized_candidate == profile.label.lower():
        return "exact"
    if normalized_candidate in {alias.lower() for alias in profile.aliases}:
        return "grouped"
    if profile.gene_symbol.lower() in normalized_candidate:
        return "gene_only"
    return "none"


def classify_therapy_match(therapy_info: dict[str, object], candidate_name: str, candidate_aliases: list[str] | None = None) -> str:
    candidate_tokens = {_clean_spaces(candidate_name).lower()}
    for alias in candidate_aliases or []:
        candidate_tokens.add(_clean_spaces(alias).lower())

    if therapy_info["query"] in candidate_tokens or therapy_info["canonical"].lower() in candidate_tokens:
        return "exact"

    aliases = set(therapy_info["aliases"])
    if candidate_tokens & aliases:
        return "class"

    candidate_blob = " ".join(sorted(candidate_tokens))
    therapy_blob = therapy_info["canonical"].lower()
    if therapy_blob in candidate_blob or any(token in candidate_blob for token in aliases):
        return "partial"
    return "none"


def classify_cancer_match(cancer_info: dict[str, object], candidate_name: str) -> str:
    candidate = _clean_spaces(candidate_name).lower()
    aliases = set(cancer_info["aliases"])

    if candidate in aliases:
        return "exact"

    candidate_words = set(candidate.split())
    for lineage in cancer_info["lineages"]:
        if lineage in candidate_words:
            return "related"

    broad_terms = {"cancer", "carcinoma", "tumor", "tumour", "neoplasm"}
    if candidate_words & broad_terms:
        return "broad"

    return "none"


def _normalize_gene_symbol(value: str) -> str:
    return _clean_spaces(value).upper()


def _normalize_alteration(gene: str, biomarker_type: str, alteration: str) -> str:
    text = _clean_spaces(alteration)
    if biomarker_type == "small_variant":
        text = text.upper().replace(gene.upper(), "").strip()
        return re.sub(r"\s+", "", text)
    if biomarker_type == "fusion":
        text = text.upper().replace("FUSION", "").strip()
        text = text.replace("/", "-")
        parts = [part for part in re.split(r"-+", text) if part]
        if len(parts) >= 2:
            return f"{parts[0]}-{parts[1]} fusion"
        return f"{gene} fusion"
    if biomarker_type == "copy_number":
        lowered = text.lower()
        if "amp" in lowered:
            return "amplification"
        if "del" in lowered or "loss" in lowered:
            return "deletion"
        return lowered
    if biomarker_type == "expression":
        lowered = text.lower()
        if "over" in lowered or "high" in lowered:
            return "high expression"
        if "low" in lowered or "under" in lowered:
            return "low expression"
        return lowered
    return text.lower()


def _clean_spaces(value: str) -> str:
    return " ".join((value or "").strip().split())


def _smart_title(value: str) -> str:
    words = []
    for word in value.split():
        words.append(word.upper() if word.isupper() else word.capitalize())
    return " ".join(words)
