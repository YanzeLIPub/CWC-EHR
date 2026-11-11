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
- `outputs/reidentification_risk_audit.json`: aggregate assessment of the retained indirect identifiers.
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

Laboratory values use reference-interval linear standardization. Zero and one correspond to the lower and upper reference limits, respectively. Negative values are below the lower limit. The public documentation provides the method and aggregate validation results; numerical conversion parameters and the corresponding clinical-scale validation script are supplied confidentially to the editor.

## Repository and review access

The materials are available at https://github.com/YanzeLIPub/CWC-EHR, with the dated version at https://github.com/YanzeLIPub/CWC-EHR/tree/round3-2026-11-11 and a ZIP download at https://github.com/YanzeLIPub/CWC-EHR/archive/refs/heads/round3-2026-11-11.zip. Public reproduction materials can be downloaded without registration. The five released CSVs and anonymous download instructions are supplied separately to the journal for peer review.

## Data Availability

CWC EHR version 1.0.0 is released through the Open Archive for Miscellaneous Data (OMIX013035, BioProject PRJCA051263, https://ngdc.cncb.ac.cn/omix/release/OMIX013035) under controlled access. To obtain the five patient-level CSV files, users register with verifiable identity information, submit an OMIX access request and accept the CWC EHR Data Use Agreement (DUA). The data providers will approve access for every user who completes these steps. The same requirements apply to all applicants, irrespective of research question, nationality, institutional affiliation or type, and commercial or non-commercial status. Submitter authorization confirms completion of these uniform requirements and enables download. The DUA prohibits participant identification, linkage for re-identification and redistribution of patient-level data. Controlled access protects the sensitive longitudinal information retained after de-identification.
