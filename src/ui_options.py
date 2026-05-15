import csv
from functools import lru_cache

from src.config import (
    CANCER_OPTIONS_PATH,
    DEPMAP_GDSC_SNAPSHOT_PATH,
    DEPMAP_SANGER_DOSE_RESPONSE_PATH,
    DRUG_OPTIONS_PATH,
    HGNC_PROTEIN_CODING_PATH,
)
from src.normalization import THERAPY_GROUPS

AMINO_ACIDS = [
    ("A", "Alanine"),
    ("R", "Arginine"),
    ("N", "Asparagine"),
    ("D", "Aspartic acid"),
    ("C", "Cysteine"),
    ("Q", "Glutamine"),
    ("E", "Glutamic acid"),
    ("G", "Glycine"),
    ("H", "Histidine"),
    ("I", "Isoleucine"),
    ("L", "Leucine"),
    ("K", "Lysine"),
    ("M", "Methionine"),
    ("F", "Phenylalanine"),
    ("P", "Proline"),
    ("S", "Serine"),
    ("T", "Threonine"),
    ("W", "Tryptophan"),
    ("Y", "Tyrosine"),
    ("V", "Valine"),
]


@lru_cache(maxsize=1)
def load_gene_options() -> list[str]:
    rows = _read_csv(HGNC_PROTEIN_CODING_PATH, "symbol")
    return rows or ["EGFR", "BRAF", "ALK", "ERBB2", "ESR1", "KRAS", "NRAS", "PIK3CA"]


@lru_cache(maxsize=1)
def load_drug_options() -> list[str]:
    curated = _read_csv(DRUG_OPTIONS_PATH, "drug_name")
    therapy_classes = [group["canonical"] for group in THERAPY_GROUPS.values()]
    depmap_snapshot = _read_csv(DEPMAP_GDSC_SNAPSHOT_PATH, "therapy")
    depmap_raw = _read_csv(DEPMAP_SANGER_DOSE_RESPONSE_PATH, "DRUG_NAME")
    rows = _dedupe_preserve_order([*curated, *therapy_classes, *depmap_snapshot, *[_title_case_drug(value) for value in depmap_raw]])
    return rows or ["Gefitinib", "Vemurafenib", "Alectinib", "Lapatinib"]


@lru_cache(maxsize=1)
def load_cancer_type_options() -> list[str]:
    curated = _read_csv(CANCER_OPTIONS_PATH, "cancer_type")
    depmap_snapshot = _read_csv(DEPMAP_GDSC_SNAPSHOT_PATH, "cancer_type")
    rows = _dedupe_preserve_order([*curated, *depmap_snapshot])
    return rows or ["NSCLC", "Melanoma", "Breast Cancer", "Sarcoma"]


def amino_acid_options() -> list[str]:
    return [f"{code} - {name}" for code, name in AMINO_ACIDS]


def amino_acid_code(label: str) -> str:
    return label.split(" - ", 1)[0].strip()


def build_small_variant(ref_label: str, position: int, alt_label: str) -> str:
    return f"{amino_acid_code(ref_label)}{int(position)}{amino_acid_code(alt_label)}"


def _read_csv(path, column: str) -> list[str]:
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        values = [" ".join((row.get(column) or "").split()) for row in reader]
    return [value for value in values if value]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _title_case_drug(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        return ""
    if value.upper() == value:
        return value.title()
    return value
