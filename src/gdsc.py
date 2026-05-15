import csv
from pathlib import Path

from src.db import fetch_gdsc_rows, gdsc_tuple_from_row, replace_gdsc_snapshot
from src.normalization import classify_cancer_match, classify_profile_match, classify_therapy_match
from src.types import EvidenceRecord, MolecularProfile


def fetch_supporting_evidence(query, profile: MolecularProfile, therapy_info, cancer_info) -> list[EvidenceRecord]:
    results = []
    for row in fetch_gdsc_rows():
        profile_match = classify_profile_match(profile, row["profile_label"])
        therapy_match = classify_therapy_match(
            therapy_info,
            row["therapy"],
            [row["therapy_class"]] if row.get("therapy_class") else [],
        )
        cancer_match = classify_cancer_match(cancer_info, row["cancer_type"])

        if profile_match == "none" or therapy_match == "none" or cancer_match == "none":
            continue

        results.append(
            EvidenceRecord(
                source=row["source"] or "gdsc",
                evidence_kind="experimental_support",
                profile_label=row["profile_label"],
                disease=row["cancer_type"],
                therapy=row["therapy"],
                therapy_aliases=[row["therapy_class"]] if row.get("therapy_class") else [],
                response_class=row["response_class"],
                evidence_level="preclinical",
                rating=None,
                citation=row["citation"] or "",
                statement=row["statement"] or "",
                profile_match_level=profile_match,
                therapy_match_level=therapy_match,
                cancer_match_level=cancer_match,
                is_direct=False,
                raw=row,
            )
        )

    return sorted(
        results,
        key=lambda item: (
            item.profile_match_level == "exact",
            item.therapy_match_level == "exact",
            item.cancer_match_level == "exact",
            item.raw.get("quality_band") == "HIGH",
            item.raw.get("quality_band") == "MEDIUM",
            abs(item.raw.get("effect_size", 0)),
            item.raw.get("sample_count", 0),
        ),
        reverse=True,
    )


def load_gdsc_snapshot(csv_path: str | Path):
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = [gdsc_tuple_from_row(row) for row in reader]
    replace_gdsc_snapshot(rows)
