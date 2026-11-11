#!/usr/bin/env python3
"""Synthetic end-to-end test for the candidate release writer.

No source patient data are read.  The test creates a minimal artificial source
inside a temporary directory, runs the gated full-build path, checks the five
CSV outputs and aggregate QC invariants, and then removes the temporary files.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("rebuild_release.py")
TEST_SECRET = "SYNTHETIC-TEST-ONLY-CWC-EHR-KEY-00000001"


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def main() -> int:
    header = [
        "",
        "病案号",
        "检查时间",
        "检验项目A",
        "检验项目全空",
        "出生日期",
        "住院次数",
        "费别",
        "性别",
        "主要手术操作名称",
        "入院时间",
        "入院科别(首页)",
        "门（急）诊诊断",
        "现住址",
        "出院科别(首页)",
        "出院时间",
        "出院主要诊断名称1",
        "病理诊断",
        "上次诊断",
        "province",
        "city",
        "年份",
        "人均地区生产总值(元)",
        "职工平均工资(元)",
        "医院、卫生院数(个)",
        "医院、卫生院床位数(张)",
        "医生数(人)",
    ]
    rows = [
        [
            "1",
            "SYNTHETIC-A",
            "2022-01-03",
            "7.1",
            "",
            "1960-06-01",
            "1",
            "A",
            "1",
            "procedure one",
            "2022-01-01",
            "ward one",
            "diagnosis alpha",
            "synthetic address",
            "ward two",
            "2022-01-05",
            "diagnosis beta",
            "",
            "diagnosis prior",
            "synthetic province",
            "synthetic city",
            "2022",
            "100",
            "",
            "2",
            "300",
            "40",
        ],
        [
            "2",
            "SYNTHETIC-A",
            "2022-01-04",
            "",
            "",
            "1960-06-01",
            "1",
            "A",
            "1",
            "procedure one",
            "2022-01-01",
            "ward one",
            "diagnosis alpha",
            "synthetic address",
            "ward two",
            "2022-01-05",
            "diagnosis beta",
            "",
            "diagnosis prior",
            "synthetic province",
            "synthetic city",
            "2022",
            "100",
            "",
            "2",
            "300",
            "40",
        ],
        [
            "3",
            "SYNTHETIC-B",
            "2023-02-11",
            "8.2",
            "",
            "1975-12-31",
            "2",
            "B",
            "2",
            "",
            "2023-02-10",
            "ward three",
            "diagnosis gamma",
            "",
            "ward three",
            "2023-02-12",
            "diagnosis delta",
            "pathology epsilon",
            "",
            "",
            "",
            "2023",
            "",
            "",
            "",
            "",
            "",
        ],
    ]

    with tempfile.TemporaryDirectory(prefix="cwc_release_self_test_") as temporary:
        temp = Path(temporary)
        source = temp / "synthetic_source.csv"
        output = temp / "release"
        with source.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)

        environment = os.environ.copy()
        environment["CWC_EHR_HMAC_KEY"] = TEST_SECRET
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source",
                str(source),
                "--mode",
                "build",
                "--confirm-full-run",
                "--output-dir",
                str(output),
            ],
            check=True,
            env=environment,
            capture_output=True,
            text=True,
        )

        patient = read_csv(output / "patient_info.csv")
        visit = read_csv(output / "visit_record.csv")
        diagnosis = read_csv(output / "diagnosis.csv")
        lab = read_csv(output / "lab_test.csv")
        socioeconomic = read_csv(output / "socioeconomic_index.csv")
        qc = json.loads((output / "quality_control_report.json").read_text(encoding="utf-8"))

        assert len(patient) - 1 == 2
        assert len(visit) - 1 == 2
        assert len(diagnosis) - 1 == 6
        assert len(lab) - 1 == 3
        assert len(socioeconomic) - 1 == 3
        assert "检验项目A" in lab[0]
        assert "检验项目全空" not in lab[0]
        assert "主要手术操作名称" not in lab[0]
        assert "入院科别(首页)" not in lab[0]
        assert qc["patient_pseudonymization"]["collisions"] == 0
        assert qc["date_shifting"]["all_offsets_within_inclusive_bounds"] is True
        assert qc["date_shifting"]["encounter_interval_mismatches"] == 0
        assert qc["diagnosis"]["technical_duplicates_removed"] == 3
        assert qc["laboratory"]["all_missing_columns_removed"] == 1
        assert qc["socioeconomic"]["original_year_mismatch_rows"] == 0

        released_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                output / "patient_info.csv",
                output / "visit_record.csv",
                output / "diagnosis.csv",
                output / "lab_test.csv",
                output / "socioeconomic_index.csv",
            )
        )
        for forbidden_value in (
            "SYNTHETIC-A",
            "SYNTHETIC-B",
            "synthetic address",
            "synthetic province",
            "synthetic city",
            "ward one",
            "ward two",
            "ward three",
        ):
            assert forbidden_value not in released_text

    print("Synthetic end-to-end release self-test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
