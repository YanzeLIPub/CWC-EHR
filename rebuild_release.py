#!/usr/bin/env python3
"""Rebuild the CWC EHR controlled-access release from the restricted source CSV.

The script is deliberately narrow.  It implements only the corrections needed
for the data-release contradictions identified by Reviewers 2 and 4:

* one global, non-sequential HMAC-SHA-256 patient pseudonym;
* one deterministic patient-level date offset in the inclusive range [-30, 30];
* one patient row and one hospital-encounter row;
* diagnosis-source preservation with technical duplicate removal;
* a laboratory table containing only keys, shifted examination date, and
  observed laboratory columns;
* socioeconomic values carried forward only after validating their original
  region/year alignment, with genuine missing values preserved.

The raw source is opened read-only.  No source identifier, address, province,
city, secret, or source-to-release mapping is written to the release package or
QC report.  The program refuses to overwrite an existing output directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple


PIPELINE_VERSION = "1.0.0"
HMAC_NAMESPACE_VERSION = "1.0.0-candidate"
KEY_ENVIRONMENT_VARIABLE = "CWC_EHR_HMAC_KEY"
MISSING_VALUE_CONVENTION = "empty CSV field"
CONFIRMED_UPSTREAM_CARDIOVASCULAR_RULE = 'Adults aged at least 18 years receiving cancer care with at least one of coronary heart disease, hypertension, heart failure, arrhythmia, valvular heart disease, cardiomyopathy, congenital heart disease, or vascular disease; OR across the eight cardiovascular categories and AND with the adult oncology sampling frame. Other coexisting diseases were permitted. Heart failure was a separate qualifying condition.'

SOURCE_PATIENT_ID = "病案号"
SOURCE_EXAM_DATE = "检查时间"
SOURCE_BIRTH_DATE = "出生日期"
SOURCE_VISIT_NUMBER = "住院次数"
SOURCE_PAYER = "费别"
SOURCE_SEX = "性别"
SOURCE_PROCEDURE = "主要手术操作名称"
SOURCE_ADMISSION_DATE = "入院时间"
SOURCE_ADMISSION_DEPARTMENT = "入院科别(首页)"
SOURCE_DISCHARGE_DEPARTMENT = "出院科别(首页)"
SOURCE_DISCHARGE_DATE = "出院时间"
SOURCE_ADDRESS = "现住址"
SOURCE_PROVINCE = "province"
SOURCE_CITY = "city"
SOURCE_YEAR = "年份"

DIAGNOSIS_SOURCES: Tuple[Tuple[str, str], ...] = (
    ("outpatient_or_emergency", "门（急）诊诊断"),
    ("discharge_primary", "出院主要诊断名称1"),
    ("pathology", "病理诊断"),
    ("previous_diagnosis", "上次诊断"),
)

SOCIOECONOMIC_COLUMNS: Tuple[str, ...] = (
    "人均地区生产总值(元)",
    "职工平均工资(元)",
    "医院、卫生院数(个)",
    "医院、卫生院床位数(张)",
    "医生数(人)",
)

REQUIRED_SOURCE_COLUMNS: Tuple[str, ...] = (
    SOURCE_PATIENT_ID,
    SOURCE_EXAM_DATE,
    SOURCE_BIRTH_DATE,
    SOURCE_VISIT_NUMBER,
    SOURCE_PAYER,
    SOURCE_SEX,
    SOURCE_PROCEDURE,
    SOURCE_ADMISSION_DATE,
    SOURCE_ADMISSION_DEPARTMENT,
    SOURCE_DISCHARGE_DEPARTMENT,
    SOURCE_DISCHARGE_DATE,
    SOURCE_ADDRESS,
    SOURCE_PROVINCE,
    SOURCE_CITY,
    SOURCE_YEAR,
    *(column for _, column in DIAGNOSIS_SOURCES),
    *SOCIOECONOMIC_COLUMNS,
)

FORBIDDEN_RELEASE_HEADERS: Set[str] = {
    "",
    SOURCE_PATIENT_ID,
    "Medical record number",
    SOURCE_BIRTH_DATE,
    "现住址",
    SOURCE_PROVINCE,
    SOURCE_CITY,
    SOURCE_YEAR,
    SOURCE_ADMISSION_DEPARTMENT,
    SOURCE_DISCHARGE_DEPARTMENT,
}


class ReleaseBuildError(RuntimeError):
    """A source-contract or release-gate failure with no row-level disclosure."""


def is_missing(value: str) -> bool:
    """Treat only empty or whitespace-only source fields as missing."""

    return value.strip() == ""


def normalize_text(value: str) -> str:
    """Normalize whitespace only; do not map, translate, or infer content."""

    return " ".join(value.strip().split())


def parse_iso_date(value: str, field_name: str) -> date:
    """Parse the source's YYYY-MM-DD dates without including values in errors."""

    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ReleaseBuildError(f"Unparseable non-missing date in source field {field_name!r}.") from exc


def shift_iso_date(value: str, offset_days: int, field_name: str) -> str:
    if is_missing(value):
        return ""
    return (parse_iso_date(value, field_name) + timedelta(days=offset_days)).isoformat()


def calculate_age(index_date: date, birth_date: date) -> int:
    return index_date.year - birth_date.year - (
        (index_date.month, index_date.day) < (birth_date.month, birth_date.day)
    )


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def json_write(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)


def csv_writer(path: Path, header: Sequence[str]):
    handle = path.open("x", encoding="utf-8", newline="")
    os.chmod(path, 0o600)
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(header)
    return handle, writer


def validate_release_header(header: Sequence[str], filename: str) -> None:
    duplicates = [name for name, count in Counter(header).items() if count > 1]
    if duplicates:
        raise ReleaseBuildError(f"Duplicate output columns detected in {filename}.")
    forbidden = FORBIDDEN_RELEASE_HEADERS.intersection(header)
    if forbidden:
        raise ReleaseBuildError(f"Forbidden source/geographic columns detected in {filename}.")


class HmacTransformer:
    """Domain-separated HMAC identifiers and a patient-consistent date offset."""

    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise ReleaseBuildError(
                f"{KEY_ENVIRONMENT_VARIABLE} must contain at least 32 UTF-8 bytes."
            )
        self._secret = secret

    def _digest(self, domain: str, parts: Sequence[str]) -> bytes:
        payload = json.dumps(
            ["CWC-EHR", HMAC_NAMESPACE_VERSION, domain, *parts],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hmac.new(self._secret, payload, hashlib.sha256).digest()

    def identifier(self, prefix: str, domain: str, *parts: str) -> str:
        return f"{prefix}_{self._digest(domain, parts).hex()}"

    def patient_id(self, source_patient_id: str) -> str:
        return self.identifier("P", "patient-pseudonym", source_patient_id)

    def encounter_id(self, encounter_key: "EncounterKey") -> str:
        return self.identifier("E", "encounter", *encounter_key.as_parts())

    def lab_record_id(self, source_patient_id: str, examination_date: str) -> str:
        return self.identifier("L", "laboratory-record", source_patient_id, examination_date)

    def department_code(self, source_department: str) -> str:
        if is_missing(source_department):
            return ""
        return self.identifier("D", "department", source_department.strip())

    def date_offset(self, source_patient_id: str) -> int:
        raw = int.from_bytes(self._digest("patient-date-offset", [source_patient_id])[:8], "big")
        return raw % 61 - 30


@dataclass(frozen=True, order=True)
class EncounterKey:
    source_patient_id: str
    visit_number: str
    admission_date: str
    discharge_date: str

    def as_parts(self) -> Tuple[str, str, str, str]:
        return (
            self.source_patient_id,
            self.visit_number,
            self.admission_date,
            self.discharge_date,
        )


@dataclass
class PatientRecord:
    birth_date: str
    sex_source_code: str
    index_admission_date: str


@dataclass
class EncounterRecord:
    key: EncounterKey
    payer_source_code: str = ""
    primary_procedure_text: str = ""
    admission_department: str = ""
    discharge_department: str = ""


@dataclass
class ScanState:
    source_rows: int = 0
    patients: Dict[str, PatientRecord] = field(default_factory=dict)
    encounters: Dict[EncounterKey, EncounterRecord] = field(default_factory=dict)
    diagnosis_records: MutableMapping[Tuple[str, EncounterKey, str, str], str] = field(
        default_factory=dict
    )
    diagnosis_unique_hashes: Set[str] = field(default_factory=set)
    diagnosis_nonmissing_rows: Counter = field(default_factory=Counter)
    lab_nonmissing_counts: Counter = field(default_factory=Counter)
    lab_rows_with_any_value: int = 0
    lab_patients_with_any_value: Set[str] = field(default_factory=set)
    explicit_complication_field_nonmissing_counts: Counter = field(default_factory=Counter)
    source_addresses: Set[str] = field(default_factory=set)
    releasable_free_text_values: Set[str] = field(default_factory=set)
    socioeconomic_missing_counts: Counter = field(default_factory=Counter)
    socioeconomic_all_missing_rows: int = 0
    original_year_mismatch_rows: int = 0
    region_or_year_missing_rows: int = 0
    region_or_year_missing_with_nonmissing_values: int = 0
    socioeconomic_region_year_values: Dict[Tuple[str, str, str], List[str]] = field(
        default_factory=dict
    )
    invalid_age_count: int = 0
    min_age_at_index: Optional[int] = None
    max_age_at_index: Optional[int] = None
    min_raw_admission: Optional[date] = None
    max_raw_admission: Optional[date] = None
    min_raw_discharge: Optional[date] = None
    max_raw_discharge: Optional[date] = None
    min_raw_exam: Optional[date] = None
    max_raw_exam: Optional[date] = None
    patient_exam_date_ranges: Dict[str, Tuple[date, date]] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceLayout:
    header: Tuple[str, ...]
    index: Mapping[str, int]
    lab_columns: Tuple[str, ...]
    lab_indices: Tuple[int, ...]
    explicit_complication_columns: Tuple[str, ...]


def read_source_layout(source: Path) -> SourceLayout:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = tuple(next(reader))
        except StopIteration as exc:
            raise ReleaseBuildError("The source CSV is empty.") from exc

    duplicate_headers = [name for name, count in Counter(header).items() if count > 1]
    if duplicate_headers:
        raise ReleaseBuildError("The source CSV has duplicate column names.")

    index = {name: position for position, name in enumerate(header)}
    missing = [name for name in REQUIRED_SOURCE_COLUMNS if name not in index]
    if missing:
        raise ReleaseBuildError(
            "The source CSV is missing required columns: " + ", ".join(repr(name) for name in missing)
        )

    exam_position = index[SOURCE_EXAM_DATE]
    birth_position = index[SOURCE_BIRTH_DATE]
    if birth_position <= exam_position + 1:
        raise ReleaseBuildError("The laboratory-column block cannot be resolved from the source header.")
    lab_indices = tuple(range(exam_position + 1, birth_position))
    lab_columns = tuple(header[position] for position in lab_indices)
    if not lab_columns:
        raise ReleaseBuildError("No laboratory-value columns were found.")

    return SourceLayout(
        header=header,
        index=index,
        lab_columns=lab_columns,
        lab_indices=lab_indices,
        explicit_complication_columns=tuple(
            name for name in header if "并发症" in name or "合并症" in name
        ),
    )


def row_value(row: Sequence[str], layout: SourceLayout, column: str) -> str:
    return row[layout.index[column]]


def update_minimum(current: Optional[date], candidate: date) -> date:
    return candidate if current is None or candidate < current else current


def update_maximum(current: Optional[date], candidate: date) -> date:
    return candidate if current is None or candidate > current else current


def set_consistent(existing: str, candidate: str, field_name: str) -> str:
    if is_missing(candidate):
        return existing
    normalized = candidate.strip()
    if is_missing(existing):
        return normalized
    if existing != normalized:
        raise ReleaseBuildError(f"Conflicting non-missing values detected for {field_name!r}.")
    return existing


def add_or_validate_patient(
    state: ScanState,
    source_patient_id: str,
    birth_date: str,
    sex_source_code: str,
    admission_date: str,
) -> None:
    existing = state.patients.get(source_patient_id)
    if existing is None:
        state.patients[source_patient_id] = PatientRecord(
            birth_date=birth_date.strip(),
            sex_source_code=sex_source_code.strip(),
            index_admission_date=admission_date.strip(),
        )
        return

    existing.birth_date = set_consistent(existing.birth_date, birth_date, SOURCE_BIRTH_DATE)
    existing.sex_source_code = set_consistent(existing.sex_source_code, sex_source_code, SOURCE_SEX)
    candidate_date = parse_iso_date(admission_date, SOURCE_ADMISSION_DATE)
    current_date = parse_iso_date(existing.index_admission_date, SOURCE_ADMISSION_DATE)
    if candidate_date < current_date:
        existing.index_admission_date = admission_date.strip()


def add_or_validate_encounter(
    state: ScanState,
    encounter_key: EncounterKey,
    payer: str,
    procedure: str,
    admission_department: str,
    discharge_department: str,
) -> None:
    existing = state.encounters.get(encounter_key)
    if existing is None:
        state.encounters[encounter_key] = EncounterRecord(
            key=encounter_key,
            payer_source_code=payer.strip(),
            primary_procedure_text=normalize_text(procedure) if not is_missing(procedure) else "",
            admission_department=admission_department.strip(),
            discharge_department=discharge_department.strip(),
        )
        return

    existing.payer_source_code = set_consistent(existing.payer_source_code, payer, SOURCE_PAYER)
    existing.primary_procedure_text = set_consistent(
        existing.primary_procedure_text,
        normalize_text(procedure) if not is_missing(procedure) else "",
        SOURCE_PROCEDURE,
    )
    existing.admission_department = set_consistent(
        existing.admission_department, admission_department, SOURCE_ADMISSION_DEPARTMENT
    )
    existing.discharge_department = set_consistent(
        existing.discharge_department, discharge_department, SOURCE_DISCHARGE_DEPARTMENT
    )


def diagnostic_key_hash(
    source_patient_id: str,
    encounter_key: EncounterKey,
    diagnosis_source: str,
    normalized_text: str,
) -> str:
    payload = json.dumps(
        [source_patient_id, *encounter_key.as_parts()[1:], diagnosis_source, normalized_text],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def scan_source(
    source: Path,
    layout: SourceLayout,
    max_rows: Optional[int],
    retain_diagnosis_text: bool,
) -> ScanState:
    state = ScanState(
        lab_nonmissing_counts=Counter({column: 0 for column in layout.lab_columns}),
        explicit_complication_field_nonmissing_counts=Counter(
            {column: 0 for column in layout.explicit_complication_columns}
        ),
        socioeconomic_missing_counts=Counter({column: 0 for column in SOCIOECONOMIC_COLUMNS}),
    )

    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for row_number, row in enumerate(reader, start=1):
            if max_rows is not None and row_number > max_rows:
                break
            if len(row) != len(layout.header):
                raise ReleaseBuildError("A source row has a column count that differs from the header.")

            state.source_rows += 1
            source_patient_id = row_value(row, layout, SOURCE_PATIENT_ID).strip()
            if not source_patient_id:
                raise ReleaseBuildError("A source row has a missing patient identifier.")

            birth_date = row_value(row, layout, SOURCE_BIRTH_DATE)
            sex = row_value(row, layout, SOURCE_SEX)
            exam_date_text = row_value(row, layout, SOURCE_EXAM_DATE)
            admission_date_text = row_value(row, layout, SOURCE_ADMISSION_DATE)
            discharge_date_text = row_value(row, layout, SOURCE_DISCHARGE_DATE)
            visit_number = row_value(row, layout, SOURCE_VISIT_NUMBER).strip()
            if any(
                is_missing(value)
                for value in (
                    birth_date,
                    sex,
                    exam_date_text,
                    admission_date_text,
                    discharge_date_text,
                    visit_number,
                )
            ):
                raise ReleaseBuildError("A required patient, encounter, or date field is missing.")

            exam_date = parse_iso_date(exam_date_text, SOURCE_EXAM_DATE)
            admission_date = parse_iso_date(admission_date_text, SOURCE_ADMISSION_DATE)
            discharge_date = parse_iso_date(discharge_date_text, SOURCE_DISCHARGE_DATE)
            parse_iso_date(birth_date, SOURCE_BIRTH_DATE)
            if discharge_date < admission_date:
                raise ReleaseBuildError("A source encounter has discharge before admission.")

            state.min_raw_exam = update_minimum(state.min_raw_exam, exam_date)
            state.max_raw_exam = update_maximum(state.max_raw_exam, exam_date)
            patient_exam_range = state.patient_exam_date_ranges.get(source_patient_id)
            if patient_exam_range is None:
                state.patient_exam_date_ranges[source_patient_id] = (exam_date, exam_date)
            else:
                state.patient_exam_date_ranges[source_patient_id] = (
                    min(patient_exam_range[0], exam_date),
                    max(patient_exam_range[1], exam_date),
                )
            state.min_raw_admission = update_minimum(state.min_raw_admission, admission_date)
            state.max_raw_admission = update_maximum(state.max_raw_admission, admission_date)
            state.min_raw_discharge = update_minimum(state.min_raw_discharge, discharge_date)
            state.max_raw_discharge = update_maximum(state.max_raw_discharge, discharge_date)

            add_or_validate_patient(state, source_patient_id, birth_date, sex, admission_date_text)

            encounter_key = EncounterKey(
                source_patient_id=source_patient_id,
                visit_number=visit_number,
                admission_date=admission_date_text.strip(),
                discharge_date=discharge_date_text.strip(),
            )
            add_or_validate_encounter(
                state=state,
                encounter_key=encounter_key,
                payer=row_value(row, layout, SOURCE_PAYER),
                procedure=row_value(row, layout, SOURCE_PROCEDURE),
                admission_department=row_value(row, layout, SOURCE_ADMISSION_DEPARTMENT),
                discharge_department=row_value(row, layout, SOURCE_DISCHARGE_DEPARTMENT),
            )

            address = row_value(row, layout, SOURCE_ADDRESS).strip()
            if address:
                state.source_addresses.add(address)
            procedure_text = row_value(row, layout, SOURCE_PROCEDURE)
            if not is_missing(procedure_text):
                state.releasable_free_text_values.add(normalize_text(procedure_text))

            for diagnosis_source, source_column in DIAGNOSIS_SOURCES:
                raw_text = row_value(row, layout, source_column)
                if is_missing(raw_text):
                    continue
                normalized = normalize_text(raw_text)
                state.releasable_free_text_values.add(normalized)
                state.diagnosis_nonmissing_rows[diagnosis_source] += 1
                key_hash = diagnostic_key_hash(
                    source_patient_id, encounter_key, diagnosis_source, normalized
                )
                if retain_diagnosis_text:
                    key = (source_patient_id, encounter_key, diagnosis_source, normalized)
                    state.diagnosis_records.setdefault(key, normalized)
                else:
                    state.diagnosis_unique_hashes.add(key_hash)

            row_has_lab_value = False
            for column, position in zip(layout.lab_columns, layout.lab_indices):
                if not is_missing(row[position]):
                    state.lab_nonmissing_counts[column] += 1
                    row_has_lab_value = True
            if row_has_lab_value:
                state.lab_rows_with_any_value += 1
                state.lab_patients_with_any_value.add(source_patient_id)

            for column in layout.explicit_complication_columns:
                if not is_missing(row_value(row, layout, column)):
                    state.explicit_complication_field_nonmissing_counts[column] += 1

            source_year_text = row_value(row, layout, SOURCE_YEAR)
            if is_missing(source_year_text):
                state.original_year_mismatch_rows += 1
            else:
                try:
                    source_year = int(source_year_text)
                except ValueError as exc:
                    raise ReleaseBuildError("A non-missing source socioeconomic year is not an integer.") from exc
                if source_year != exam_date.year:
                    state.original_year_mismatch_rows += 1

            region_year_values = [
                row_value(row, layout, column)
                for column in (SOURCE_PROVINCE, SOURCE_CITY, SOURCE_YEAR)
            ]
            socioeconomic_values = [
                row_value(row, layout, column) for column in SOCIOECONOMIC_COLUMNS
            ]
            if any(is_missing(value) for value in region_year_values):
                state.region_or_year_missing_rows += 1
                if any(not is_missing(value) for value in socioeconomic_values):
                    state.region_or_year_missing_with_nonmissing_values += 1
            else:
                region_year_key = tuple(value.strip() for value in region_year_values)
                existing_values = state.socioeconomic_region_year_values.get(region_year_key)
                if existing_values is None:
                    state.socioeconomic_region_year_values[region_year_key] = [
                        value.strip() for value in socioeconomic_values
                    ]
                else:
                    for position, (existing_value, candidate_value) in enumerate(
                        zip(existing_values, socioeconomic_values)
                    ):
                        existing_values[position] = set_consistent(
                            existing_value,
                            candidate_value,
                            f"socioeconomic metric {SOCIOECONOMIC_COLUMNS[position]}",
                        )

            if all(is_missing(value) for value in socioeconomic_values):
                state.socioeconomic_all_missing_rows += 1
            for column, value in zip(SOCIOECONOMIC_COLUMNS, socioeconomic_values):
                if is_missing(value):
                    state.socioeconomic_missing_counts[column] += 1

    for record in state.patients.values():
        index_date = parse_iso_date(record.index_admission_date, SOURCE_ADMISSION_DATE)
        birth_date = parse_iso_date(record.birth_date, SOURCE_BIRTH_DATE)
        age = calculate_age(index_date, birth_date)
        if age < 0 or age > 120:
            state.invalid_age_count += 1
        state.min_age_at_index = age if state.min_age_at_index is None else min(state.min_age_at_index, age)
        state.max_age_at_index = age if state.max_age_at_index is None else max(state.max_age_at_index, age)

    return state


def date_range_payload(minimum: Optional[date], maximum: Optional[date]) -> Mapping[str, Optional[str]]:
    return {
        "minimum": minimum.isoformat() if minimum else None,
        "maximum": maximum.isoformat() if maximum else None,
    }


def build_qc_payload(
    source: Path,
    layout: SourceLayout,
    state: ScanState,
    transformer: HmacTransformer,
    max_rows: Optional[int],
    source_sha256: str,
) -> Dict[str, object]:
    patient_ids = [transformer.patient_id(source_id) for source_id in state.patients]
    offsets = [transformer.date_offset(source_id) for source_id in state.patients]
    encounter_ids = [transformer.encounter_id(key) for key in state.encounters]
    pseudonym_pattern = re.compile(r"^P_[0-9a-f]{64}$")

    shifted_admissions: List[date] = []
    shifted_discharges: List[date] = []
    shifted_examination_minima: List[date] = []
    shifted_examination_maxima: List[date] = []
    interval_mismatch_count = 0
    for key in state.encounters:
        offset = transformer.date_offset(key.source_patient_id)
        raw_admission = parse_iso_date(key.admission_date, SOURCE_ADMISSION_DATE)
        raw_discharge = parse_iso_date(key.discharge_date, SOURCE_DISCHARGE_DATE)
        shifted_admission = raw_admission + timedelta(days=offset)
        shifted_discharge = raw_discharge + timedelta(days=offset)
        shifted_admissions.append(shifted_admission)
        shifted_discharges.append(shifted_discharge)
        if (shifted_discharge - shifted_admission) != (raw_discharge - raw_admission):
            interval_mismatch_count += 1

    for source_patient_id, (minimum_exam, maximum_exam) in state.patient_exam_date_ranges.items():
        offset = timedelta(days=transformer.date_offset(source_patient_id))
        shifted_examination_minima.append(minimum_exam + offset)
        shifted_examination_maxima.append(maximum_exam + offset)

    observed_lab_columns = [
        column for column in layout.lab_columns if state.lab_nonmissing_counts[column] > 0
    ]
    diagnosis_input_rows = int(sum(state.diagnosis_nonmissing_rows.values()))
    diagnosis_unique_records = max(
        len(state.diagnosis_unique_hashes), len(state.diagnosis_records)
    )
    exact_source_identifier_matches = sum(
        value in state.patients for value in state.releasable_free_text_values
    )
    exact_source_address_matches = sum(
        value in state.source_addresses for value in state.releasable_free_text_values
    )
    phone_pattern = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
    national_id_pattern = re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")
    direct_identifier_labels = (
        "姓名",
        "身份证",
        "手机号",
        "联系电话",
        "现住址",
        "家庭住址",
        "病案号",
    )

    return {
        "pipeline_version": PIPELINE_VERSION,
        "report_contains_row_level_data": False,
        "cohort_provenance": {
            "author_confirmed_upstream_rule": CONFIRMED_UPSTREAM_CARDIOVASCULAR_RULE,
            "author_confirmed_upstream_pass_count": 38509,
            "cohort_reselected_from_released_diagnosis_text": False,
            "pipeline_retains_the_supplied_cohort_without_reclassification": True,
            "upstream_historical_diagnosis_selection_records_in_current_extract": False,
            "explicit_eligibility_fields_found_in_current_source_header": list(
                layout.explicit_complication_columns
            ),
            "nonmissing_rows_by_explicit_eligibility_field": dict(
                state.explicit_complication_field_nonmissing_counts
            ),
        },
        "scan_scope": {
            "kind": "first_n_physical_rows" if max_rows is not None else "complete_source",
            "max_rows_requested": max_rows,
            "rows_scanned": state.source_rows,
            "warning": (
                "Counts in this report are a test sample and are not cohort totals."
                if max_rows is not None
                else None
            ),
        },
        "source_integrity": {
            "source_file_name": source.name,
            "source_size_bytes": source.stat().st_size,
            "source_sha256": source_sha256,
            "source_opened_read_only": True,
            "source_column_count": len(layout.header),
        },
        "patient_pseudonymization": {
            "method": "HMAC-SHA-256 with domain separation",
            "secret_written_to_release": False,
            "source_to_release_mapping_written": False,
            "patients": len(state.patients),
            "unique_release_patient_ids": len(set(patient_ids)),
            "collisions": len(patient_ids) - len(set(patient_ids)),
            "all_ids_match_nonsequential_hex_format": all(
                pseudonym_pattern.fullmatch(value) is not None for value in patient_ids
            ),
        },
        "date_shifting": {
            "method": "one deterministic HMAC-derived offset per patient",
            "minimum_offset_days": min(offsets) if offsets else None,
            "maximum_offset_days": max(offsets) if offsets else None,
            "unique_offsets_observed": len(set(offsets)),
            "all_offsets_within_inclusive_bounds": all(-30 <= value <= 30 for value in offsets),
            "encounter_interval_mismatches": interval_mismatch_count,
            "raw_admission_date_range": date_range_payload(
                state.min_raw_admission, state.max_raw_admission
            ),
            "raw_discharge_date_range": date_range_payload(
                state.min_raw_discharge, state.max_raw_discharge
            ),
            "raw_examination_date_range": date_range_payload(state.min_raw_exam, state.max_raw_exam),
            "shifted_admission_date_range": date_range_payload(
                min(shifted_admissions) if shifted_admissions else None,
                max(shifted_admissions) if shifted_admissions else None,
            ),
            "shifted_discharge_date_range": date_range_payload(
                min(shifted_discharges) if shifted_discharges else None,
                max(shifted_discharges) if shifted_discharges else None,
            ),
            "shifted_examination_date_range": date_range_payload(
                min(shifted_examination_minima) if shifted_examination_minima else None,
                max(shifted_examination_maxima) if shifted_examination_maxima else None,
            ),
        },
        "table_grain": {
            "patient_info_rows": len(state.patients),
            "unique_patient_ids_expected": len(state.patients),
            "visit_record_rows": len(state.encounters),
            "unique_encounter_ids_expected": len(set(encounter_ids)),
            "encounter_id_collisions": len(encounter_ids) - len(set(encounter_ids)),
            "age_definition": "age at earliest admission in the scanned source",
            "minimum_age_at_index": state.min_age_at_index,
            "maximum_age_at_index": state.max_age_at_index,
            "age_outside_0_to_120": state.invalid_age_count,
        },
        "diagnosis": {
            "source_fields": [label for label, _ in DIAGNOSIS_SOURCES],
            "input_nonmissing_records_by_source": dict(state.diagnosis_nonmissing_rows),
            "input_nonmissing_records_total": diagnosis_input_rows,
            "unique_records_after_whitespace_only_deduplication": diagnosis_unique_records,
            "technical_duplicates_removed": diagnosis_input_rows
            - diagnosis_unique_records,
            "icd10_mapping_performed": False,
        },
        "laboratory": {
            "source_candidate_value_columns": len(layout.lab_columns),
            "all_missing_columns_removed": len(layout.lab_columns) - len(observed_lab_columns),
            "released_value_columns_expected": len(observed_lab_columns),
            "rows_expected": state.source_rows,
            "rows_with_at_least_one_observed_value": state.lab_rows_with_any_value,
            "patients_with_at_least_one_observed_value": len(
                state.lab_patients_with_any_value
            ),
            "cohort_patients_in_scan": len(state.patients),
            "non_lab_fields_in_value_block": 0,
            "unit_assignment_performed": False,
            "released_unit": 'Standardized (dimensionless)',
            "upstream_transformation_status": 'Standardization confirmed by the data providers; conversion rules and parameters not publicly disclosed',
            "release_transformation": 'Standardized source values copied unchanged',
            "missing_value_imputation_performed": False,
        },
        "socioeconomic": {
            "internal_alignment_check": "source year equals unshifted examination year",
            "original_year_mismatch_rows": state.original_year_mismatch_rows,
            "internally_validated_region_year_keys": len(
                state.socioeconomic_region_year_values
            ),
            "rows_with_missing_internal_region_or_year": state.region_or_year_missing_rows,
            "rows_with_missing_internal_region_or_year_but_nonmissing_values": (
                state.region_or_year_missing_with_nonmissing_values
            ),
            "all_five_values_missing_rows": state.socioeconomic_all_missing_rows,
            "missing_rows_by_variable": dict(state.socioeconomic_missing_counts),
            "imputation_performed": False,
            "direct_geography_released": False,
        },
        "release_exclusions": {
            "source_patient_identifier": True,
            "date_of_birth": True,
            "address": True,
            "province": True,
            "city": True,
            "source_socioeconomic_year": True,
            "raw_department_names": True,
        },
        "free_text_direct_identifier_scan": {
            "unique_diagnosis_or_procedure_values_scanned": len(
                state.releasable_free_text_values
            ),
            "exact_source_identifier_matches": exact_source_identifier_matches,
            "exact_source_address_matches": exact_source_address_matches,
            "values_with_mobile_phone_pattern": sum(
                phone_pattern.search(value) is not None
                for value in state.releasable_free_text_values
            ),
            "values_with_national_id_pattern": sum(
                national_id_pattern.search(value) is not None
                for value in state.releasable_free_text_values
            ),
            "values_with_direct_identifier_labels": sum(
                any(label in value for label in direct_identifier_labels)
                for value in state.releasable_free_text_values
            ),
        },
    }


def write_release(
    source: Path,
    layout: SourceLayout,
    state: ScanState,
    transformer: HmacTransformer,
    output_dir: Path,
    qc_payload: MutableMapping[str, object],
) -> None:
    free_text_scan = qc_payload["free_text_direct_identifier_scan"]
    blocking_scan_fields = (
        "exact_source_identifier_matches",
        "exact_source_address_matches",
        "values_with_mobile_phone_pattern",
        "values_with_national_id_pattern",
        "values_with_direct_identifier_labels",
    )
    if any(int(free_text_scan[field]) != 0 for field in blocking_scan_fields):
        raise ReleaseBuildError(
            "The free-text direct-identifier release gate failed; no output was created."
        )
    if output_dir.exists():
        raise ReleaseBuildError(
            "The requested output directory already exists; refusing to overwrite it."
        )
    state.source_addresses.clear()
    state.releasable_free_text_values.clear()
    output_dir.mkdir(parents=True, mode=0o700)
    os.chmod(output_dir, 0o700)

    patient_header = ("patient_pseudo_id", "sex_source_code", "age_at_first_admission_years")
    visit_header = (
        "patient_pseudo_id",
        "encounter_id",
        "visit_number",
        "admission_date_shifted",
        "discharge_date_shifted",
        "payer_source_code",
        "primary_procedure_text",
        "admission_department_code",
        "discharge_department_code",
    )
    diagnosis_header = (
        "patient_pseudo_id",
        "encounter_id",
        "diagnosis_source",
        "diagnosis_text",
    )
    observed_lab_columns = tuple(
        column for column in layout.lab_columns if state.lab_nonmissing_counts[column] > 0
    )
    observed_lab_indices = tuple(layout.index[column] for column in observed_lab_columns)
    lab_header = (
        "patient_pseudo_id",
        "lab_record_id",
        "encounter_id",
        "examination_date_shifted",
        *observed_lab_columns,
    )
    socioeconomic_header = (
        "patient_pseudo_id",
        "lab_record_id",
        "examination_date_shifted",
        *SOCIOECONOMIC_COLUMNS,
    )

    for filename, header in (
        ("patient_info.csv", patient_header),
        ("visit_record.csv", visit_header),
        ("diagnosis.csv", diagnosis_header),
        ("lab_test.csv", lab_header),
        ("socioeconomic_index.csv", socioeconomic_header),
    ):
        validate_release_header(header, filename)

    output_counts: Counter = Counter()

    patient_handle, patient_writer = csv_writer(output_dir / "patient_info.csv", patient_header)
    try:
        patient_rows = []
        for source_patient_id, record in state.patients.items():
            patient_id = transformer.patient_id(source_patient_id)
            age = calculate_age(
                parse_iso_date(record.index_admission_date, SOURCE_ADMISSION_DATE),
                parse_iso_date(record.birth_date, SOURCE_BIRTH_DATE),
            )
            patient_rows.append((patient_id, record.sex_source_code, age))
        for row in sorted(patient_rows):
            patient_writer.writerow(row)
            output_counts["patient_info.csv"] += 1
    finally:
        patient_handle.close()
    del patient_rows

    visit_handle, visit_writer = csv_writer(output_dir / "visit_record.csv", visit_header)
    try:
        visit_rows = []
        for key, record in state.encounters.items():
            offset = transformer.date_offset(key.source_patient_id)
            visit_rows.append(
                (
                    transformer.patient_id(key.source_patient_id),
                    transformer.encounter_id(key),
                    key.visit_number,
                    shift_iso_date(key.admission_date, offset, SOURCE_ADMISSION_DATE),
                    shift_iso_date(key.discharge_date, offset, SOURCE_DISCHARGE_DATE),
                    record.payer_source_code,
                    record.primary_procedure_text,
                    transformer.department_code(record.admission_department),
                    transformer.department_code(record.discharge_department),
                )
            )
        for row in sorted(visit_rows, key=lambda value: value[1]):
            visit_writer.writerow(row)
            output_counts["visit_record.csv"] += 1
    finally:
        visit_handle.close()
    del visit_rows

    diagnosis_handle, diagnosis_writer = csv_writer(output_dir / "diagnosis.csv", diagnosis_header)
    diagnosis_output_count = len(state.diagnosis_records)
    try:
        for (source_patient_id, encounter_key, diagnosis_source, normalized_text), output_text in (
            state.diagnosis_records.items()
        ):
            diagnosis_writer.writerow(
                (
                    transformer.patient_id(source_patient_id),
                    transformer.encounter_id(encounter_key),
                    diagnosis_source,
                    output_text,
                )
            )
            output_counts["diagnosis.csv"] += 1
    finally:
        diagnosis_handle.close()
    state.diagnosis_records.clear()
    state.diagnosis_unique_hashes.clear()

    lab_handle, lab_writer = csv_writer(output_dir / "lab_test.csv", lab_header)
    socioeconomic_handle, socioeconomic_writer = csv_writer(
        output_dir / "socioeconomic_index.csv", socioeconomic_header
    )
    try:
        seen_lab_record_ids: Set[str] = set()
        with source.open("r", encoding="utf-8-sig", newline="") as source_handle:
            reader = csv.reader(source_handle)
            next(reader)
            for row in reader:
                if len(row) != len(layout.header):
                    raise ReleaseBuildError(
                        "A source row has a column count that differs from the header."
                    )
                source_patient_id = row_value(row, layout, SOURCE_PATIENT_ID).strip()
                examination_date = row_value(row, layout, SOURCE_EXAM_DATE).strip()
                encounter_key = EncounterKey(
                    source_patient_id=source_patient_id,
                    visit_number=row_value(row, layout, SOURCE_VISIT_NUMBER).strip(),
                    admission_date=row_value(row, layout, SOURCE_ADMISSION_DATE).strip(),
                    discharge_date=row_value(row, layout, SOURCE_DISCHARGE_DATE).strip(),
                )
                patient_id = transformer.patient_id(source_patient_id)
                lab_record_id = transformer.lab_record_id(source_patient_id, examination_date)
                if lab_record_id in seen_lab_record_ids:
                    raise ReleaseBuildError(
                        "The source contains duplicate patient/examination-date laboratory keys."
                    )
                seen_lab_record_ids.add(lab_record_id)
                offset = transformer.date_offset(source_patient_id)
                shifted_examination_date = shift_iso_date(
                    examination_date, offset, SOURCE_EXAM_DATE
                )
                lab_writer.writerow(
                    (
                        patient_id,
                        lab_record_id,
                        transformer.encounter_id(encounter_key),
                        shifted_examination_date,
                        *(row[position] for position in observed_lab_indices),
                    )
                )
                output_counts["lab_test.csv"] += 1
                socioeconomic_writer.writerow(
                    (
                        patient_id,
                        lab_record_id,
                        shifted_examination_date,
                        *(row_value(row, layout, column) for column in SOCIOECONOMIC_COLUMNS),
                    )
                )
                output_counts["socioeconomic_index.csv"] += 1
    finally:
        lab_handle.close()
        socioeconomic_handle.close()

    source_sha256_after_write = sha256_file(source)
    if not hmac.compare_digest(
        source_sha256_after_write, str(qc_payload["source_integrity"]["source_sha256"])
    ):
        raise ReleaseBuildError("The restricted source changed during the release build.")
    qc_payload["source_integrity"]["source_sha256_rechecked_after_write"] = True

    expected_counts = {
        "patient_info.csv": len(state.patients),
        "visit_record.csv": len(state.encounters),
        "diagnosis.csv": diagnosis_output_count,
        "lab_test.csv": state.source_rows,
        "socioeconomic_index.csv": state.source_rows,
    }
    if dict(output_counts) != expected_counts:
        raise ReleaseBuildError("Output row counts did not reconcile with the scan state.")

    manifest_files: Dict[str, object] = {}
    for filename, header in (
        ("patient_info.csv", patient_header),
        ("visit_record.csv", visit_header),
        ("diagnosis.csv", diagnosis_header),
        ("lab_test.csv", lab_header),
        ("socioeconomic_index.csv", socioeconomic_header),
    ):
        path = output_dir / filename
        manifest_files[filename] = {
            "rows_excluding_header": output_counts[filename],
            "columns": len(header),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }

    manifest = {
        "pipeline_version": PIPELINE_VERSION,
        "restricted_source_sha256": qc_payload["source_integrity"]["source_sha256"],
        "missing_value_convention": MISSING_VALUE_CONVENTION,
        "files": manifest_files,
        "secret_included": False,
        "mapping_table_included": False,
    }
    json_write(output_dir / "release_manifest.json", manifest)
    qc_payload["release_build"] = {
        "completed": True,
        "output_directory": str(output_dir),
        "row_counts_reconciled": True,
        "files": manifest_files,
    }
    json_write(output_dir / "quality_control_report.json", qc_payload)


def parse_arguments(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("restricted_source.csv"),
        help="Read-only restricted source CSV.",
    )
    parser.add_argument(
        "--mode",
        choices=("audit", "build"),
        default="audit",
        help="Audit emits aggregate QC only; build emits the controlled-access release.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Audit only: scan the first N physical rows for a fast pipeline test.",
    )
    parser.add_argument(
        "--qc-report",
        type=Path,
        default=Path("qa_report.json"),
        help="Aggregate-only audit report path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("release_output"),
        help="New directory for a full controlled-access release.",
    )
    parser.add_argument(
        "--expected-source-sha256",
        default=None,
        help="Optional source digest lock; the build aborts on a mismatch.",
    )
    parser.add_argument(
        "--confirm-full-run",
        action="store_true",
        help="Required together with --mode build. Build mode never accepts --max-rows.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_arguments(argv)
    if args.max_rows is not None and args.max_rows <= 0:
        raise ReleaseBuildError("--max-rows must be a positive integer.")
    if args.mode == "build" and (not args.confirm_full_run or args.max_rows is not None):
        raise ReleaseBuildError(
            "Build mode requires --confirm-full-run and does not permit --max-rows."
        )

    source = args.source.resolve()
    if not source.is_file():
        raise ReleaseBuildError("The restricted source CSV does not exist.")

    secret_text = os.environ.get(KEY_ENVIRONMENT_VARIABLE)
    if secret_text is None:
        raise ReleaseBuildError(
            f"Set {KEY_ENVIRONMENT_VARIABLE} in the process environment; it is never written."
        )
    transformer = HmacTransformer(secret_text.encode("utf-8"))

    layout = read_source_layout(source)
    source_sha256 = sha256_file(source)
    if (
        args.expected_source_sha256 is not None
        and not hmac.compare_digest(source_sha256, args.expected_source_sha256.lower())
    ):
        raise ReleaseBuildError("The restricted source SHA-256 does not match the locked value.")

    state = scan_source(
        source=source,
        layout=layout,
        max_rows=args.max_rows,
        retain_diagnosis_text=args.mode == "build",
    )
    qc_payload = build_qc_payload(
        source=source,
        layout=layout,
        state=state,
        transformer=transformer,
        max_rows=args.max_rows,
        source_sha256=source_sha256,
    )

    if args.mode == "audit":
        report_path = args.qc_report.resolve()
        if report_path.exists():
            raise ReleaseBuildError("The requested QC report already exists; refusing to overwrite it.")
        json_write(report_path, qc_payload)
        print(f"Aggregate-only QC completed: {report_path}")
        return 0

    output_dir = args.output_dir.resolve()
    if source == output_dir or output_dir in source.parents:
        raise ReleaseBuildError("The output directory cannot contain or overwrite the source CSV.")
    write_release(
        source=source,
        layout=layout,
        state=state,
        transformer=transformer,
        output_dir=output_dir,
        qc_payload=qc_payload,
    )
    print(f"Controlled-access release completed: {output_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
