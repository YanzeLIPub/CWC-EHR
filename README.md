# CWC EHR version 1.0.0 validation and reproduction

This archive supports the third revision of *A longitudinal electronic health record dataset of 38,509 cancer patients from a tertiary hospital in China*. The analyses use the five version 1.0.0 CSV tables listed in `outputs/release_manifest.json`. The archive contains code, a field dictionary, and aggregate results. The five patient-level CSVs are under controlled access at OMIX013035.

## Files

| File | Purpose |
| --- | --- |
| `outputs/release_manifest.json` | Completed version 1.0.0 inventory with file sizes and dimensions |
| `outputs/quality_control_report.json` | Completed build and finalization report for version 1.0.0, including documented cohort provenance |
| `outputs/quality_control_round3.json` | Full laboratory audit, source-to-release agreement, and shifted admission coverage |
| `outputs/lab_variable_qc.csv` | One row per exact laboratory field name with completeness, numerical checks, sign, quantiles, and measurement metadata status |
| `outputs/lab_variable_metadata.csv` | Unit category, transformation evidence, sign convention and reference-interval status for all 771 variables, with the numerical profiles |
| `outputs/Laboratory_Metadata_and_Eligibility.xlsx` | Readable laboratory metadata, numerical profiles and eight-category eligibility dictionary |
| `outputs/eligibility_rule_dictionary.csv` | Confirmed inclusion categories and documented limits of the upstream query specification |
| `outputs/reidentification_risk_audit.json` | Aggregate structured disclosure assessment |
| `outputs/omix_file_inventory.csv` | Five current archived entries and displayed versus exact local sizes |
| `DATA_USE_AGREEMENT.md` | Conditions of access and reuse |
| `METADATA_NOTES.md` and `metadata/laboratory_annotations.csv` | Definitions and evidence sources for the curated annotations |
| `outputs/lab_scale_diagnostics.csv` and `outputs/lab_scale_summary.json` | Mean, population SD and range checks for all 771 variables |
| `PROVENANCE.md` and `outputs/source_evidence_inventory.csv` | Findings from the source, early scripts and current processing code |
| `outputs/selected_lab_qc.csv` | Validation of the five analytes summarized in manuscript Table 3 |
| `outputs/hemoglobin_interpretation_summary.json` | Aggregate evidence and interpretation of negative standardized hemoglobin values |
| `outputs/figure1_source.csv` and `outputs/figure2_source.csv` | Aggregate inputs for the revised figures |
| `outputs/CWC_EHR_Data_Dictionary_v1.0.0.xlsx` | File inventory, field definitions, standardized laboratory units, codebooks, relationships, and QC summary |
| `rules.json` | Laboratory label variants, standardized-value disclosure, historical analysis patterns, and the confirmed clinical eligibility criteria |
| `legacy_inputs/` | Verified aggregate inputs for former Supplementary Tables S3 and S4 and former Figures 1 and 2 |

## Reproduce the current validation

Use Python 3.12 and the package versions in `requirements.txt`. Run the commands from the extracted archive. Choose new output directories for the metadata finalizer and validation profiler.

```sh
python -m pip install -r requirements.txt
python self_test.py
python validate_round3.py --release-dir /approved/path/to/release_v1 --output-dir regenerated
python profile_standardized_scale.py --release-dir /approved/path/to/release_v1 --output-dir regenerated
python document_metadata.py --profiles regenerated/lab_variable_qc.csv --output regenerated/lab_variable_metadata.csv
python plot_round3.py --analysis-dir regenerated --output-dir figures
```

`validate_round3.py` profiles `patient_info.csv`, `visit_record.csv`, and `lab_test.csv`. Figure 1 counts encounter records by the shifted admission year. Figure 2 counts laboratory fields within right-closed completeness bins. An empty CSV field counts as missing. Numerical checks parse nonempty values without removing operators or thousands separators. Quantiles use linear interpolation among finite values. The denominator for each field's completeness is the full set of laboratory rows. In the selected-analyte check, the first finite value in the documented label order contributes one value per examination row. The script also counts rows with multiple nonempty variants.

To regenerate both figures with only the supplied aggregate inputs, run `python plot_round3.py --analysis-dir outputs --output-dir figures_from_aggregates`.

Laboratory results use standardized, dimensionless units, as confirmed by the data providers. The public scripts reproduce validation on the released scale. The aggregate hemoglobin summary records a data-supported inference from internal consistency checks. Conversion rules, parameters, and reconstruction scripts are retained internally to limit reconstruction of original clinical measurements; they are not part of this public archive.

```sh
python finalize_release_metadata.py --release-dir /approved/path/to/release_v1 --output-dir rechecked_metadata
```

The metadata finalizer reads the five CSV files and the build-stage manifest and QC report from the version directory. It reconciles the five row counts and checks cross-table key membership. The completed report in this archive also records the authors' final description of the upstream eligibility rule.

## Reproduce the source-dependent checks

The locked source extract and institutional pseudonymization key remain under institutional governance. See `README_rebuild_v1.md` for the approved rebuild workflow. The package also includes a synthetic self-test.

```sh
python validate_round3.py --release-dir /approved/path/to/release_v1 \
  --restricted-source /approved/path/to/locked_source.csv --output-dir regenerated_with_source
```

With the optional source argument, the profiler compares the contents of all retained laboratory cells in source row order, including blanks. This matches the order written by the rebuild script. The comparison tests the source-to-release step. The extract already contains standardized laboratory values, which the release pipeline copies unchanged. `rules.json` records the cohort builders’ confirmed clinical eligibility criteria: age at least 18 years in the oncology sampling frame and at least one of eight cardiovascular comorbidities. Other coexisting diseases were permitted, and heart failure independently qualified. These are clinical criteria; the archive does not claim to reproduce the original hospital query.

## Reproduce the prior revision's analyses

The previous admission-year figure used unshifted dates. The previous procedure comparison used text rules on the original diagnosis and procedure fields and matched terms on the same source row before counting unique patients. The earlier exploratory cardiovascular text patterns apply only to the four extract diagnosis fields.

```sh
python analyze_round2.py --source /approved/path/to/locked_source.csv --output-dir legacy_recomputed
python plot_round2.py --analysis-dir legacy_recomputed --output-dir legacy_figures
```

`legacy_inputs/selected_lab_summary.csv` underlies former Table S3. `legacy_inputs/tumor_procedure_summary.csv` underlies former Table S4 and former Figure 2. `legacy_inputs/annual_encounters_by_sex_code.csv` underlies former Figure 1. The three aggregate files were reproduced from the locked source. For plotting the earlier figures directly, pass `--analysis-dir legacy_inputs` to `plot_round2.py`.

## Release status

The repository identifier for CWC EHR is OMIX013035, BioProject PRJCA051263. The signed-in OMIX inventory showed five archived CSV entries on 10 November 2026. File titles and displayed sizes correspond to the locally verified version 1.0.0. The OMIX submission record shows version 1.0.0 as released under controlled access. The data providers will approve access for every user who completes OMIX registration with verifiable identity information, submits an access request and accepts the CWC EHR DUA. The same requirements apply irrespective of research question, nationality, institutional affiliation or type, and commercial or non-commercial status. Submitter authorization confirms these uniform requirements and enables download. [OMIX public accession](https://ngdc.cncb.ac.cn/omix/release/OMIX013035)

## Third revision delivery and access

The five exact version 1.0.0 CSV tables are also supplied to the journal in the separate confidential reviewer archive CWC_EHR_v1.0.0_Reviewer_Data.zip. No separate anonymous OMIX download link has been issued. Public reuse continues through OMIX controlled access and the project-specific DUA.

The expanded round-three reproducibility materials are publicly deposited at [https://github.com/YanzeLIPub/CWC-EHR](https://github.com/YanzeLIPub/CWC-EHR). The dated version is [round3-2026-11-11](https://github.com/YanzeLIPub/CWC-EHR/tree/round3-2026-11-11), with a [ZIP download](https://github.com/YanzeLIPub/CWC-EHR/archive/refs/heads/round3-2026-11-11.zip). This deposit includes code, metadata, completed reports and aggregate figure inputs. It contains no patient-level CSV tables, institutional source extract, identifier mappings, private key, laboratory conversion parameters or confidential cover-letter disclosure. No repository login is needed to download these public materials.

## Data Availability

CWC EHR version 1.0.0 is released through the Open Archive for Miscellaneous Data (OMIX013035, BioProject PRJCA051263, https://ngdc.cncb.ac.cn/omix/release/OMIX013035) under controlled access. To obtain the five patient-level CSV files, users register with verifiable identity information, submit an OMIX access request and accept the CWC EHR Data Use Agreement (DUA). The data providers will approve access for every user who completes these steps. The same requirements apply to all applicants, irrespective of research question, nationality, institutional affiliation or type, and commercial or non-commercial status. Submitter authorization confirms completion of these uniform requirements and enables download. The DUA prohibits participant identification, linkage for re-identification and redistribution of patient-level data. Controlled access protects the sensitive longitudinal information retained after de-identification.
