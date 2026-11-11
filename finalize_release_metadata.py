#!/usr/bin/env python3
"""Check table dimensions and relationships and write aggregate metadata."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


RELEASE_VERSION = "1.0.0"
DATA_FILES = (
    "patient_info.csv",
    "visit_record.csv",
    "diagnosis.csv",
    "lab_test.csv",
    "socioeconomic_index.csv",
)



def read_csv_keys(path: Path, indexes: tuple[int, ...]) -> tuple[list[set[str]], int]:
    values = [set() for _ in indexes]
    row_count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for row in reader:
            row_count += 1
            for target, index in zip(values, indexes):
                target.add(row[index])
    return values, row_count


def read_prefix_keys(path: Path, key_count: int) -> tuple[list[set[str]], int]:
    """Read leading comma-free release keys without parsing the wide value block."""

    values = [set() for _ in range(key_count)]
    row_count = 0
    with path.open("rb") as handle:
        next(handle)
        for line in handle:
            row_count += 1
            parts = line.split(b",", key_count)
            if len(parts) <= key_count:
                raise ValueError(f"Malformed leading keys in {path.name}.")
            for index in range(key_count):
                values[index].add(parts[index].decode("ascii"))
    return values, row_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    release_dir = args.release_dir.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")

    manifest = json.loads((Path(__file__).resolve().parent / "outputs/release_manifest.json").read_text(encoding="utf-8"))
    qc = json.loads((Path(__file__).resolve().parent / "outputs/quality_control_report.json").read_text(encoding="utf-8"))

    (patient_keys,), patient_rows = read_csv_keys(release_dir / "patient_info.csv", (0,))
    (visit_patient_keys, encounter_keys), visit_rows = read_csv_keys(
        release_dir / "visit_record.csv", (0, 1)
    )
    (diagnosis_patient_keys, diagnosis_encounter_keys), diagnosis_rows = read_csv_keys(
        release_dir / "diagnosis.csv", (0, 1)
    )
    (lab_patient_keys, lab_record_keys, lab_encounter_keys), lab_rows = read_prefix_keys(
        release_dir / "lab_test.csv", 3
    )
    (socioeconomic_patient_keys, socioeconomic_lab_keys), socioeconomic_rows = read_prefix_keys(
        release_dir / "socioeconomic_index.csv", 2
    )

    observed_rows = {
        "patient_info.csv": patient_rows,
        "visit_record.csv": visit_rows,
        "diagnosis.csv": diagnosis_rows,
        "lab_test.csv": lab_rows,
        "socioeconomic_index.csv": socioeconomic_rows,
    }
    for filename, count in observed_rows.items():
        if count != manifest["files"][filename]["rows_excluding_header"]:
            raise ValueError(f"Row-count mismatch for {filename}.")

    patient_orphans = {
        "visit_record.csv": len(visit_patient_keys - patient_keys),
        "diagnosis.csv": len(diagnosis_patient_keys - patient_keys),
        "lab_test.csv": len(lab_patient_keys - patient_keys),
        "socioeconomic_index.csv": len(socioeconomic_patient_keys - patient_keys),
    }
    encounter_orphans = {
        "diagnosis.csv": len(diagnosis_encounter_keys - encounter_keys),
        "lab_test.csv": len(lab_encounter_keys - encounter_keys),
    }
    laboratory_orphans = {
        "socioeconomic_index.csv": len(socioeconomic_lab_keys - lab_record_keys),
    }
    if any(patient_orphans.values()) or any(encounter_orphans.values()) or any(
        laboratory_orphans.values()
    ):
        raise ValueError("Cross-table key-integrity validation failed.")

    manifest["release_version"] = RELEASE_VERSION
    manifest["final_validation"] = {
        "row_counts_reconciled": True,
        "cross_table_key_integrity_confirmed": True,
        "row_files_rewritten_during_finalization": False,
    }

    qc["release_version"] = RELEASE_VERSION
    qc["cross_table_integrity"] = {
        "patient_foreign_key_orphans_by_file": patient_orphans,
        "encounter_foreign_key_orphans_by_file": encounter_orphans,
        "laboratory_record_foreign_key_orphans_by_file": laboratory_orphans,
        "total_patient_foreign_key_orphans": sum(patient_orphans.values()),
        "total_encounter_foreign_key_orphans": sum(encounter_orphans.values()),
        "total_laboratory_record_foreign_key_orphans": sum(laboratory_orphans.values()),
    }
    qc["release_build"] = {
        "completed": True,
        "release_files_directory": ".",
        "row_counts_reconciled": True,
        "files": manifest["files"],
    }

    output_dir.mkdir(parents=True, mode=0o700)
    (output_dir / "release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "quality_control_report.json").write_text(
        json.dumps(qc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(qc["cross_table_integrity"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
