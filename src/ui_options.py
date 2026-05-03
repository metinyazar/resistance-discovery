import csv
from functools import lru_cache

from src.config import CANCER_OPTIONS_PATH, DRUG_OPTIONS_PATH, HGNC_PROTEIN_CODING_PATH

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
    rows = _read_csv(DRUG_OPTIONS_PATH, "drug_name")
    return rows or ["Gefitinib", "Vemurafenib", "Alectinib", "Lapatinib"]


@lru_cache(maxsize=1)
def load_cancer_type_options() -> list[str]:
    rows = _read_csv(CANCER_OPTIONS_PATH, "cancer_type")
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
