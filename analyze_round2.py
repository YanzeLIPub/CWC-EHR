#!/usr/bin/env python3
"""Aggregate-only analysis for the second-round manuscript revision.

The source file contains direct identifiers. This script never writes patient-level
records and never prints identifiers, addresses, or row-level clinical values.
Only aggregate JSON/CSV summaries needed for the reviewer-requested tables and
figures are written.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent

ID = "病案号"
TEST_DATE = "检查时间"
DOB = "出生日期"
SEX = "性别"
ADMIT = "入院时间"
DISCHARGE = "出院时间"
PROCEDURE = "主要手术操作名称"
DIAGNOSIS_FIELDS = ["门（急）诊诊断", "出院主要诊断名称1", "病理诊断", "上次诊断"]


RULES = json.loads((ROOT / "rules.json").read_text(encoding="utf-8"))
LEGACY = RULES["legacy_round2_descriptive_text_rules"]
CANCER_PATTERNS = LEGACY["cancer_diagnosis_patterns"]
CVD_PATTERNS = LEGACY["exploratory_cardiovascular_patterns"]
PROCEDURE_PATTERNS = LEGACY["procedure_patterns"]
LAB_VARIANTS = RULES["selected_laboratory_label_variants"]


def clean_text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def first_numeric(row: pd.Series, columns: list[str]) -> float:
    for col in columns:
        value = row.get(col, "")
        if pd.isna(value) or str(value).strip() == "":
            continue
        try:
            return float(str(value).replace(",", "").lstrip("<>≤≥"))
        except ValueError:
            continue
    return math.nan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    usecols = [ID, TEST_DATE, DOB, SEX, ADMIT, DISCHARGE, PROCEDURE, *DIAGNOSIS_FIELDS]
    for cols in LAB_VARIANTS.values():
        usecols.extend(cols)
    usecols = list(dict.fromkeys(usecols))

    first_patient: dict[str, dict[str, str]] = {}
    encounters: set[tuple[str, str, str]] = set()
    cancer_patients = {name: set() for name in CANCER_PATTERNS}
    cvd_patients = {name: set() for name in CVD_PATTERNS}
    procedure_patients = {name: set() for name in PROCEDURE_PATTERNS}
    tumor_procedure_patients = {
        tumor: {proc: set() for proc in PROCEDURE_PATTERNS}
        for tumor in CANCER_PATTERNS
    }
    lab_values = {name: [] for name in LAB_VARIANTS}
    lab_patients = {name: set() for name in LAB_VARIANTS}
    lab_nonblank = Counter()
    lab_variant_overlap = Counter()
    sex_values: dict[str, set[str]] = defaultdict(set)

    for chunk in pd.read_csv(
        args.source,
        usecols=usecols,
        dtype=str,
        chunksize=20_000,
        encoding="utf-8-sig",
        low_memory=False,
    ):
        for col in usecols:
            chunk[col] = clean_text(chunk[col])
        chunk = chunk[chunk[ID] != ""].copy()

        for row in chunk[[ID, DOB, SEX, ADMIT, DISCHARGE]].itertuples(index=False, name=None):
            patient, dob, sex, admit, discharge = row
            sex_values[patient].add(sex)
            prior = first_patient.get(patient)
            if prior is None or (admit and admit < prior[ADMIT]):
                first_patient[patient] = {DOB: dob, SEX: sex, ADMIT: admit, DISCHARGE: discharge}
            encounters.add((patient, admit, discharge))

        diagnosis_text = chunk[DIAGNOSIS_FIELDS].agg(" | ".join, axis=1)
        for category, pattern in CANCER_PATTERNS.items():
            matched = diagnosis_text.str.contains(pattern, regex=True, na=False)
            ids = set(chunk.loc[matched, ID])
            cancer_patients[category].update(ids)
        for category, pattern in CVD_PATTERNS.items():
            matched = diagnosis_text.str.contains(pattern, regex=True, na=False)
            cvd_patients[category].update(chunk.loc[matched, ID])

        procedure_text = chunk[PROCEDURE]
        row_tumor = {
            category: diagnosis_text.str.contains(pattern, regex=True, na=False)
            for category, pattern in CANCER_PATTERNS.items()
        }
        for proc_category, pattern in PROCEDURE_PATTERNS.items():
            proc_match = procedure_text.str.contains(pattern, regex=True, na=False)
            procedure_patients[proc_category].update(chunk.loc[proc_match, ID])
            for tumor, tumor_match in row_tumor.items():
                ids = set(chunk.loc[proc_match & tumor_match, ID])
                tumor_procedure_patients[tumor][proc_category].update(ids)

        for analyte, variants in LAB_VARIANTS.items():
            nonblank_counts = chunk[variants].ne("").sum(axis=1)
            lab_variant_overlap[analyte] += int((nonblank_counts > 1).sum())
            values = chunk[variants].apply(lambda row: first_numeric(row, variants), axis=1)
            numeric = pd.to_numeric(values, errors="coerce")
            keep = numeric.notna() & np.isfinite(numeric.to_numpy(dtype=float, na_value=np.nan))
            vals = numeric[keep].to_numpy(dtype=float)
            lab_values[analyte].append(vals)
            lab_patients[analyte].update(chunk.loc[keep, ID])
            lab_nonblank[analyte] += int(keep.sum())

    # Baseline age at earliest admission.
    baseline_rows = []
    for patient, row in first_patient.items():
        dob = pd.to_datetime(row[DOB], errors="coerce")
        admit = pd.to_datetime(row[ADMIT], errors="coerce")
        age = math.nan
        if not pd.isna(dob) and not pd.isna(admit):
            age = (admit - dob).days / 365.2425
        baseline_rows.append((patient, row[SEX], age))
    baseline = pd.DataFrame(baseline_rows, columns=[ID, SEX, "age"])

    encounter_df = pd.DataFrame(encounters, columns=[ID, ADMIT, DISCHARGE])
    encounter_df[ADMIT] = pd.to_datetime(encounter_df[ADMIT], errors="coerce")
    encounter_df["year"] = encounter_df[ADMIT].dt.year
    sex_map = baseline.set_index(ID)[SEX]
    encounter_df[SEX] = encounter_df[ID].map(sex_map)

    n_patients = len(first_patient)
    age = baseline["age"].dropna().to_numpy()
    baseline_summary = {
        "patients": n_patients,
        "age_n": int(len(age)),
        "age_mean": float(np.mean(age)),
        "age_sd": float(np.std(age, ddof=1)),
        "age_median": float(np.median(age)),
        "age_q1": float(np.quantile(age, 0.25)),
        "age_q3": float(np.quantile(age, 0.75)),
        "age_min": float(np.min(age)),
        "age_max": float(np.max(age)),
        "sex_counts": {str(k): int(v) for k, v in baseline[SEX].value_counts(dropna=False).items()},
        "patients_with_conflicting_sex_codes": int(sum(len(v - {""}) > 1 for v in sex_values.values())),
    }

    cancer_counts = sorted(
        ({"category": k, "patients": len(v), "percent": 100 * len(v) / n_patients} for k, v in cancer_patients.items()),
        key=lambda x: (-x["patients"], x["category"]),
    )
    cvd_counts = sorted(
        ({"category": k, "patients": len(v), "percent": 100 * len(v) / n_patients} for k, v in cvd_patients.items()),
        key=lambda x: (-x["patients"], x["category"]),
    )

    lab_summary = []
    for analyte, arrays in lab_values.items():
        vals = np.concatenate(arrays) if arrays else np.array([], dtype=float)
        if len(vals):
            q = np.quantile(vals, [0.01, 0.25, 0.5, 0.75, 0.99])
            below = int((vals < 0).sum())
            within = int(((vals >= 0) & (vals <= 1)).sum())
            above = int((vals > 1).sum())
        else:
            q = [math.nan] * 5
            below = within = above = 0
        lab_summary.append(
            {
                "analyte": analyte,
                "measurements": int(len(vals)),
                "patients": len(lab_patients[analyte]),
                "patient_coverage_percent": 100 * len(lab_patients[analyte]) / n_patients,
                "p01": float(q[0]),
                "q1": float(q[1]),
                "median": float(q[2]),
                "q3": float(q[3]),
                "p99": float(q[4]),
                "below_zero_n": below,
                "zero_to_one_n": within,
                "above_one_n": above,
                "below_zero_percent": 100 * below / len(vals) if len(vals) else math.nan,
                "zero_to_one_percent": 100 * within / len(vals) if len(vals) else math.nan,
                "above_one_percent": 100 * above / len(vals) if len(vals) else math.nan,
                "rows_with_multiple_nonblank_variants": int(lab_variant_overlap[analyte]),
            }
        )

    annual = (
        encounter_df.dropna(subset=["year"])
        .groupby(["year", SEX], dropna=False)
        .size()
        .reset_index(name="encounters")
        .sort_values(["year", SEX])
    )
    annual["year"] = annual["year"].astype(int)

    visits = encounter_df.groupby(ID).size()
    visit_summary = {
        "encounters": int(len(encounter_df)),
        "patients": int(visits.size),
        "mean_per_patient": float(visits.mean()),
        "median_per_patient": float(visits.median()),
        "q1_per_patient": float(visits.quantile(0.25)),
        "q3_per_patient": float(visits.quantile(0.75)),
        "min_per_patient": int(visits.min()),
        "max_per_patient": int(visits.max()),
    }

    top_tumors = [row["category"] for row in cancer_counts[:6]]
    tumor_proc_rows = []
    for tumor in top_tumors:
        denominator = len(cancer_patients[tumor])
        for proc in PROCEDURE_PATTERNS:
            n = len(tumor_procedure_patients[tumor][proc])
            tumor_proc_rows.append(
                {
                    "tumor_category": tumor,
                    "procedure_category": proc,
                    "patients": n,
                    "tumor_patients": denominator,
                    "percent": 100 * n / denominator if denominator else math.nan,
                }
            )

    summary = {
        "baseline": baseline_summary,
        "visit_summary": visit_summary,
        "cancer_categories_note": "Categories are non-mutually exclusive text-rule summaries across the four supplied diagnosis fields.",
        "cancer_categories": cancer_counts,
        "cvd_categories_note": "These are documented terms in the supplied diagnosis fields, not a reconstruction or validation of the author-confirmed upstream cardiovascular cohort.",
        "cvd_categories": cvd_counts,
        "lab_scale_note": "The extract supplies numeric values. Clinical units, reference intervals and the upstream transformation are unverified.",
        "laboratory": lab_summary,
    }
    (args.output_dir / "revision_aggregate_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    annual.to_csv(args.output_dir / "annual_encounters_by_sex_code.csv", index=False)
    pd.DataFrame(tumor_proc_rows).to_csv(args.output_dir / "tumor_procedure_summary.csv", index=False)
    pd.DataFrame(cancer_counts).to_csv(args.output_dir / "cancer_category_summary.csv", index=False)
    pd.DataFrame(cvd_counts).to_csv(args.output_dir / "documented_cvd_term_summary.csv", index=False)
    pd.DataFrame(lab_summary).to_csv(args.output_dir / "selected_lab_summary.csv", index=False)

    print(json.dumps({
        "patients": n_patients,
        "encounters": len(encounter_df),
        "top_cancer_categories": cancer_counts[:10],
        "documented_cvd_categories": cvd_counts,
        "lab_measurement_counts": {row["analyte"]: row["measurements"] for row in lab_summary},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
