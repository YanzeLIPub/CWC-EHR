# CWC EHR validation and reproduction

This archive accompanies the third revision of *A longitudinal electronic health record dataset of 38,509 cancer patients from a tertiary hospital in China*. It contains the code, variable documentation, completed validation reports and aggregate inputs for the two manuscript figures.

## Contents

- `outputs/release_manifest.json`: five released CSVs, dimensions and file sizes.
- `outputs/quality_control_report.json`: table construction and linkage checks.
- `outputs/quality_control_round3.json`: laboratory completeness, numeric values, source agreement and shifted admission dates.
- `outputs/lab_variable_qc.csv` and `outputs/lab_variable_metadata.csv`: numerical profiles and reference-interval standardization documentation for all 771 fields.
- `outputs/Laboratory_Metadata_and_Eligibility.xlsx` and `outputs/CWC_EHR_Data_Dictionary_v1.0.0.xlsx`: laboratory metadata, cohort criteria and table definitions.
- `outputs/eligibility_rule_dictionary.csv` and `rules.json`: eight cardiovascular categories, ICD-10 classification, Chinese terms and analyte label groups.
- `outputs/lab_relationship_validation.csv`, `outputs/lab_field_validation.csv` and `outputs/laboratory_validation_summary.json`: completed blood-count and protein consistency checks.
- `outputs/selected_lab_qc.csv` and `outputs/hemoglobin_interpretation_summary.json`: results for the analytes discussed in the manuscript.
- `outputs/figure1_source.csv` and `outputs/figure2_source.csv`: inputs for Figures 1 and 2.
- `reference_interval_standardization.py`: the reference-interval conversion and its original-scale expression, with an illustrative numerical example.
- `validate_laboratory_relationships.py`: ten blood-count and protein consistency checks using the released CSVs and a separately supplied reference-limit parameter file.
- `laboratory_validation_rules.json`: 21 analyte groups and 29 released labels, record-selection rules, and the ten check definitions, tolerances and validation units.
- `outputs/omix_file_inventory.csv`: the current OMIX entries and file sizes.
- `DATA_USE_AGREEMENT.md` and `METADATA_NOTES.md`: access conditions and variable definitions.

## Reproduce the figures and laboratory profiles

Use Python 3.12 and the packages listed in `requirements.txt`.

```sh
python -m pip install -r requirements.txt
python plot_round3.py --analysis-dir outputs --output-dir figures
python validate_round3.py --release-dir /approved/path/to/release_v1 --output-dir regenerated
python document_metadata.py --profiles regenerated/lab_variable_qc.csv --output regenerated/lab_variable_metadata.csv
python finalize_release_metadata.py --release-dir /approved/path/to/release_v1 --output-dir table_checks
```

The figure command uses the supplied aggregates. The remaining commands use approved access to the released CSVs. To repeat the source-cell comparison, add `--restricted-source /approved/path/to/source.csv` to the validation command. Empty CSV fields represent missing values. Completeness uses all 530,450 laboratory rows as its denominator; quantiles use linear interpolation among finite values. Figure 1 uses shifted admission year. Figure 2 groups the 771 fields by completeness.

Laboratory values use reference-interval linear standardization:

`z = (x − L)/(U − L)`

Here `x` is the original measurement, `z` is the released dimensionless score, and `L` and `U` are the applicable lower and upper reference limits (`U > L`). The measurement and both limits use the same original unit. Select the analyte-specific limits, using sex-specific limits where applicable, subtract the lower limit from the measurement, and divide by the reference-interval width. Zero denotes the lower limit and one the upper limit. Negative scores lie below the lower limit; scores above one exceed the upper limit. The corresponding original-scale expression is `x = L + z(U − L)`.

For an illustrative interval with `L = 10` and `U = 20`, measurements of 5, 10, 15, 20 and 25 yield scores of −0.5, 0, 0.5, 1 and 1.5, respectively. These values illustrate the calculation and are not patient measurements or clinical reference limits. Run `python reference_interval_standardization.py` to reproduce this example. The public materials provide the mathematical definition, illustrative implementation and clinical-scale validation script. `outputs/lab_relationship_validation.csv` reports each consistency check's sample size, agreement count, absolute differences, tolerance and validation unit.

The numerical reference limits used for these checks are supplied to reviewers in `CWC_EHR_Laboratory_Validation_Reviewer.zip`. After extracting that attachment, reproduce the ten checks with:

```sh
python validate_laboratory_relationships.py --release-dir /approved/path/to/release_v1 --parameters /path/to/reviewer_attachment/validation_parameters.json --output-dir clinical_validation
```

The script writes `laboratory_consistency_results.csv` and `lab_field_validation.csv`. The first contains the same ten results as the public `outputs/lab_relationship_validation.csv`; the second gives the contributing counts by released label. The analyte labels supplied with the confidential parameters match the mapping in the public `laboratory_validation_rules.json`.

## Repository and review access

The materials are available at https://github.com/YanzeLIPub/CWC-EHR, with the dated version at https://github.com/YanzeLIPub/CWC-EHR/tree/round3-2026-11-11 and a ZIP download at https://github.com/YanzeLIPub/CWC-EHR/archive/refs/heads/round3-2026-11-11.zip. Public reproduction materials can be downloaded without registration. The five released CSVs and anonymous download instructions are supplied separately to the journal for peer review.

Controlled access implements Chinese requirements for authorized use, electronic real-name verification and data access control for health and medical big data, as set out in Articles 22–23 of the [National Health Commission management measures](https://www.nhc.gov.cn/guihuaxxs/c100133/201809/c5e3e58313a24fdeb26d3dc07003d56e.shtml). OMIX registration and acceptance of the uniform DUA implement these requirements.

## Data Availability

CWC EHR version 1.0.0 is released through the Open Archive for Miscellaneous Data (OMIX013035, BioProject PRJCA051263, https://ngdc.cncb.ac.cn/omix/release/OMIX013035) under controlled access. To obtain the five patient-level CSV files, users register with verifiable identity information, submit an OMIX access request and accept the CWC EHR Data Use Agreement (DUA). The data providers will approve access for every user who completes these steps. The same requirements apply to all applicants, irrespective of research question, nationality, institutional affiliation or type, and commercial or non-commercial status. Submitter authorization confirms completion of these uniform requirements and enables download. The DUA prohibits participant identification, linkage for re-identification and redistribution of patient-level data.
