#!/usr/bin/env python3
"""Profile the laboratory block and shifted admission dates in release 1.0.0."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

from finalize_release_metadata import sha256_file


PATIENT = "patient_pseudo_id"
LAB_KEYS = (PATIENT, "lab_record_id", "encounter_id", "examination_date_shifted")
SCOPE = Path(__file__).resolve().parent
CSV_OPTIONS = {"dtype": str, "na_filter": False, "encoding": "utf-8-sig"}
COVERAGE_BINS = (
    ("≤1", 1),
    (">1–5", 5),
    (">5–25", 25),
    (">25–50", 50),
    (">50–100", 100),
)
UNIT_STATUS = "Standardized (dimensionless)"
REFERENCE_INTERVAL_STATUS = "Original hospital reference interval not recorded in the available extract"
UPSTREAM_TRANSFORMATION_STATUS = "Standardization confirmed by the data providers; conversion rules and parameters not publicly disclosed"
RELEASE_TRANSFORMATION = "Standardized source values copied unchanged"


def header(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        fields = next(csv.reader(handle))
    if len(fields) != len(set(fields)):
        raise ValueError(f"Duplicate field name in {path.name}.")
    return fields


def numeric(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Parse numeric tokens without removing qualifiers or punctuation."""
    try:
        parsed = values.astype(np.float64)
        return parsed, np.ones(len(values), dtype=bool)
    except ValueError:
        parsed = np.empty(len(values), dtype=np.float64)
        success = np.ones(len(values), dtype=bool)
        for index, value in enumerate(values):
            try:
                parsed[index] = float(value)
            except ValueError:
                parsed[index] = np.nan
                success[index] = False
        return parsed, success


def summarize(arrays: list[np.ndarray]) -> dict:
    values = np.concatenate(arrays) if arrays else np.empty(0)
    n = len(values)
    negative = int(np.count_nonzero(values < 0))
    zero = int(np.count_nonzero(values == 0))
    unit_interval = int(np.count_nonzero((values >= 0) & (values <= 1)))
    quantiles = (
        np.quantile(values, [0.01, 0.25, 0.5, 0.75, 0.99], method="linear").tolist()
        if n else [None] * 5
    )
    return {
        "finite_numeric_n": n,
        "negative_n": negative,
        "zero_n": zero,
        "positive_n": n - negative - zero,
        "negative_percent_of_finite": 100 * negative / n if n else None,
        "zero_to_one_inclusive_n": unit_interval,
        "above_one_n": n - negative - unit_interval,
        "minimum": float(values.min()) if n else None,
        **dict(zip(("p01", "q1", "median", "q3", "p99"), quantiles)),
        "maximum": float(values.max()) if n else None,
    }


def profile_labs(
    lab_file: Path,
    patient_keys: pd.Index,
    field_names: list[str],
    variants: dict[str, list[str]],
    source_file: Path | None,
    chunk_rows: int,
) -> tuple[list[dict], list[dict], dict]:
    n_fields = len(field_names)
    n_patients = len(patient_keys)
    nonempty = np.zeros(n_fields, dtype=np.int64)
    invalid = np.zeros(n_fields, dtype=np.int64)
    nonfinite = np.zeros(n_fields, dtype=np.int64)
    mismatch = np.zeros(n_fields, dtype=np.int64)
    covered = np.zeros((n_fields, n_patients), dtype=bool)
    column_values: list[list[np.ndarray]] = [[] for _ in field_names]
    selected_values: dict[str, list[np.ndarray]] = {name: [] for name in variants}
    selected_coverage = {name: np.zeros(n_patients, dtype=bool) for name in variants}
    selected_fields = {field for fields in variants.values() for field in fields}
    overlaps = dict.fromkeys(variants, 0)
    rows = rows_without_values = 0
    lab_chunks = pd.read_csv(lab_file, chunksize=chunk_rows, **CSV_OPTIONS)
    source_chunks = None
    if source_file is not None:
        missing_fields = set(field_names) - set(header(source_file))
        if missing_fields:
            raise ValueError("The restricted source is missing one or more release fields.")
        source_chunks = pd.read_csv(
            source_file, usecols=field_names, chunksize=chunk_rows, **CSV_OPTIONS
        )

    try:
        for frame in lab_chunks:
            rows += len(frame)
            patient_index = patient_keys.get_indexer(frame[PATIENT])
            if (patient_index < 0).any():
                raise ValueError("The laboratory table contains an unknown patient key.")
            block = frame[field_names].to_numpy()
            present = block != ""
            rows_without_values += int(np.count_nonzero(~present.any(axis=1)))
            if source_chunks is not None:
                source = next(source_chunks, None)
                if source is None or len(source) != len(frame):
                    raise ValueError("Restricted source and release row counts differ.")
                mismatch += np.count_nonzero(block != source[field_names].to_numpy(), axis=0)
            numeric_columns: dict[str, np.ndarray] = {}
            for i, field in enumerate(field_names):
                observed = present[:, i]
                if not observed.any():
                    continue
                values, parsed = numeric(block[observed, i])
                finite = parsed & np.isfinite(values)
                nonempty[i] += len(values)
                invalid[i] += np.count_nonzero(~parsed)
                nonfinite[i] += np.count_nonzero(parsed & ~np.isfinite(values))
                covered[i, patient_index[observed]] = True
                if finite.any():
                    column_values[i].append(values[finite])
                if field in selected_fields:
                    column = np.full(len(frame), np.nan)
                    column[np.flatnonzero(observed)[finite]] = values[finite]
                    numeric_columns[field] = column

            for name, fields in variants.items():
                overlaps[name] += int(np.count_nonzero(frame[fields].ne("").sum(axis=1) > 1))
                pooled = np.full(len(frame), np.nan)
                for field in fields:
                    if field in numeric_columns:
                        empty = np.isnan(pooled)
                        pooled[empty] = numeric_columns[field][empty]
                available = np.isfinite(pooled)
                if available.any():
                    selected_values[name].append(pooled[available])
                    selected_coverage[name][patient_index[available]] = True
        if source_chunks is not None and next(source_chunks, None) is not None:
            raise ValueError("Restricted source contains extra rows.")
    finally:
        lab_chunks.close()
        if source_chunks is not None:
            source_chunks.close()

    field_profiles = [
        {
            "field": field,
            "lab_rows": rows,
            "nonempty_n": int(nonempty[i]),
            "missing_n": rows - int(nonempty[i]),
            "nonempty_percent_of_lab_rows": 100 * int(nonempty[i]) / rows,
            "patients_with_nonempty_value_n": int(np.count_nonzero(covered[i])),
            "nonnumeric_nonempty_n": int(invalid[i]),
            "nonfinite_numeric_n": int(nonfinite[i]),
            **summarize(column_values[i]),
            "source_unit_status": "Original hospital unit not recorded in the available extract",
            "released_unit": UNIT_STATUS,
            "source_reference_interval_status": REFERENCE_INTERVAL_STATUS,
            "upstream_transformation_status": UPSTREAM_TRANSFORMATION_STATUS,
            "release_transformation": RELEASE_TRANSFORMATION,
            "source_cell_mismatches_n": int(mismatch[i]) if source_file is not None else None,
        }
        for i, field in enumerate(field_names)
    ]
    selected_profiles = [
        {
            "analyte": name,
            "released_unit": UNIT_STATUS,
            "source_labels_in_priority_order": " | ".join(variants[name]),
            "patients_with_finite_value_n": int(np.count_nonzero(selected_coverage[name])),
            "rows_with_multiple_nonempty_variants": overlaps[name],
            **summarize(selected_values[name]),
        }
        for name in variants
    ]
    totals = {
        "laboratory_rows": rows,
        "laboratory_fields_profiled": n_fields,
        "rows_with_any_nonempty_laboratory_field": rows - rows_without_values,
        "patients_with_any_nonempty_laboratory_field": int(np.count_nonzero(covered.any(axis=0))),
        "nonempty_laboratory_cells": int(nonempty.sum()),
        "missing_laboratory_cells": int(rows * n_fields - nonempty.sum()),
        "nonnumeric_nonempty_cells": int(invalid.sum()),
        "nonfinite_numeric_cells": int(nonfinite.sum()),
        "fields_with_negative_values": sum(p["negative_n"] > 0 for p in field_profiles),
        "negative_numeric_cells": sum(p["negative_n"] for p in field_profiles),
        "source_to_release_comparison_performed": source_file is not None,
        "source_to_release_compared_cells": rows * n_fields if source_file is not None else None,
        "source_to_release_cell_mismatches": int(mismatch.sum()) if source_file is not None else None,
        "released_laboratory_unit": UNIT_STATUS,
        "source_reference_interval_status": REFERENCE_INTERVAL_STATUS,
        "upstream_transformation_status": UPSTREAM_TRANSFORMATION_STATUS,
    }
    return field_profiles, selected_profiles, totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=SCOPE / "outputs" / "release_manifest.json")
    parser.add_argument("--restricted-source", type=Path, help="Optional, approved institutional use only.")
    parser.add_argument("--chunk-rows", type=int, default=8000)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rules = json.loads((SCOPE / "rules.json").read_text(encoding="utf-8"))

    patients_path = args.release_dir / "patient_info.csv"
    visits_path = args.release_dir / "visit_record.csv"
    lab_path = args.release_dir / "lab_test.csv"
    for path in (patients_path, visits_path, lab_path):
        if sha256_file(path) != manifest["files"][path.name]["sha256"]:
            raise ValueError(f"Release digest mismatch for {path.name}.")
    if args.restricted_source is not None:
        if sha256_file(args.restricted_source) != manifest["restricted_source_sha256"]:
            raise ValueError("Restricted source digest mismatch.")

    patients = pd.Index(pd.read_csv(patients_path, usecols=[PATIENT], **CSV_OPTIONS)[PATIENT])
    if not patients.is_unique or "" in patients:
        raise ValueError("Empty or duplicated patient key.")
    shifted_dates = pd.to_datetime(
        pd.read_csv(visits_path, usecols=["admission_date_shifted"], **CSV_OPTIONS)["admission_date_shifted"],
        format="%Y-%m-%d",
        errors="raise",
    )
    if shifted_dates.isna().any():
        raise ValueError("Missing shifted admission date.")
    figure1 = shifted_dates.dt.year.value_counts().sort_index().rename_axis("shifted_admission_year")
    figure1 = figure1.rename("encounters").reset_index()
    lab_header = header(lab_path)
    if tuple(lab_header[:len(LAB_KEYS)]) != LAB_KEYS:
        raise ValueError("Laboratory key fields differ from the expected release schema.")
    field_profiles, selected_profiles, qc = profile_labs(
        lab_path,
        patients,
        lab_header[len(LAB_KEYS):],
        rules["selected_laboratory_label_variants"],
        args.restricted_source,
        args.chunk_rows,
    )
    for path, rows in ((patients_path, len(patients)), (visits_path, len(shifted_dates)),
                       (lab_path, qc["laboratory_rows"])):
        if manifest["files"][path.name]["rows_excluding_header"] != rows:
            raise ValueError(f"Row-count mismatch for {path.name}.")
    qc.update(
        release_version=manifest["release_version"],
        shifted_admission_date_min=shifted_dates.min().date().isoformat(),
        shifted_admission_date_max=shifted_dates.max().date().isoformat(),
        encounters_in_figure1=int(figure1["encounters"].sum()),
    )
    coverage = np.array([row["nonempty_n"] for row in field_profiles])
    # Integer comparisons make the right-closed boundaries exact.
    bins = np.searchsorted(
        qc["laboratory_rows"] * np.array([limit for _, limit in COVERAGE_BINS]),
        100 * coverage,
        side="left",
    )
    figure2 = pd.DataFrame(
        {"nonempty_percent_bin": [label for label, _ in COVERAGE_BINS],
         "laboratory_fields": np.bincount(bins, minlength=len(COVERAGE_BINS))}
    )
    args.output_dir.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(field_profiles).to_csv(args.output_dir / "lab_variable_qc.csv", index=False)
    pd.DataFrame(selected_profiles).to_csv(args.output_dir / "selected_lab_qc.csv", index=False)
    figure1.to_csv(args.output_dir / "figure1_source.csv", index=False)
    figure2.to_csv(args.output_dir / "figure2_source.csv", index=False)
    (args.output_dir / "quality_control_round3.json").write_text(
        json.dumps(qc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(qc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
