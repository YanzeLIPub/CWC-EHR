#!/usr/bin/env python3
"""Produce an aggregate-only quasi-identifier risk audit for the revised release."""

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def group_summary(rows, columns):
    groups = Counter(tuple(row[column] for column in columns) for row in rows)
    sizes = Counter(groups.values())
    patient_count = len(rows)
    singleton_patients = sizes.get(1, 0)
    below_five = sum(size * count for size, count in sizes.items() if size < 5)
    return {
        "variables": columns,
        "equivalence_class_count": len(groups),
        "minimum_class_size": min(groups.values()),
        "maximum_class_size": max(groups.values()),
        "singleton_patient_count": singleton_patients,
        "singleton_patient_percent": round(100 * singleton_patients / patient_count, 4),
        "patients_in_classes_smaller_than_5": below_five,
        "patients_in_classes_smaller_than_5_percent": round(100 * below_five / patient_count, 4),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--qc", type=Path, default=ROOT / "outputs" / "quality_control_report.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    patients = {}
    with (args.release_dir / "patient_info.csv").open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            patients[row["patient_pseudo_id"]] = {
                "sex_source_code": row["sex_source_code"],
                "age_at_first_admission_years": row["age_at_first_admission_years"],
                "first_admission_date_shifted": "",
                "first_admission_department_code": "",
                "first_payer_source_code": "",
                "last_discharge_date_shifted": "",
                "encounter_count": 0,
            }

    with (args.release_dir / "visit_record.csv").open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            patient = patients[row["patient_pseudo_id"]]
            patient["encounter_count"] += 1
            admission = row["admission_date_shifted"]
            if not patient["first_admission_date_shifted"] or admission < patient["first_admission_date_shifted"]:
                patient["first_admission_date_shifted"] = admission
                patient["first_admission_department_code"] = row["admission_department_code"]
                patient["first_payer_source_code"] = row["payer_source_code"]
            discharge = row["discharge_date_shifted"]
            if discharge > patient["last_discharge_date_shifted"]:
                patient["last_discharge_date_shifted"] = discharge

    patient_rows = list(patients.values())
    combinations = [
        ["sex_source_code", "age_at_first_admission_years"],
        ["sex_source_code", "age_at_first_admission_years", "first_admission_date_shifted"],
        [
            "sex_source_code",
            "age_at_first_admission_years",
            "first_admission_date_shifted",
            "first_admission_department_code",
            "first_payer_source_code",
        ],
        [
            "sex_source_code",
            "age_at_first_admission_years",
            "first_admission_date_shifted",
            "first_admission_department_code",
            "first_payer_source_code",
            "encounter_count",
            "last_discharge_date_shifted",
        ],
    ]

    qc = json.loads(args.qc.read_text(encoding="utf-8"))
    direct_scans = qc["free_text_direct_identifier_scan"]
    report = {
        "audit_generated_utc": datetime.now(timezone.utc).isoformat(),
        "release_version": "1.0.0",
        "patient_count": len(patient_rows),
        "scope": (
            "Aggregate-only equivalence-class analysis of selected structured quasi-identifiers. "
            "No patient pseudonyms, attribute values, or row-level records are written to this report."
        ),
        "direct_identifier_scan_results_from_release_qc": direct_scans,
        "quasi_identifier_equivalence_classes": [
            group_summary(patient_rows, columns) for columns in combinations
        ],
        "interpretation": (
            "Residual re-identification risk is present because longitudinal shifted dates, age, sex, "
            "coded care attributes, payer information, diagnoses, procedures, laboratory trajectories, "
            "and area-level socioeconomic measures can form distinctive combinations. Patient-specific "
            "date shifting and removal of direct identifiers reduce risk but do not make the release "
            "anonymous. Controlled access, the project-specific Data Use Agreement, secure analysis, "
            "and prohibition of linkage or re-identification remain required."
        ),
        "limitations": (
            "This structured quasi-identifier analysis does not model external auxiliary datasets and "
            "does not enumerate high-dimensional diagnosis, procedure-text, laboratory, or socioeconomic "
            "combinations. It therefore supports governance review rather than a claim of anonymity."
        ),
    }
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
