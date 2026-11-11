# Source provenance and laboratory scale evidence

The source-to-release processing is documented for all 771 retained laboratory variables. The available earlier code begins with already preprocessed data. It does not contain the hospital query or the original numerical conversion. The evidence inventory records the materials checked and the conclusion supported by each.

## Cohort selection

The clinical criteria are age at least 18 years and at least one of eight cardiovascular comorbidity categories, in the hospital oncology sampling frame. Other diseases are permitted. Heart failure qualifies independently of cardiomyopathy. The eight categories and Chinese labels are in `outputs/eligibility_rule_dictionary.csv`.

SCH has confirmed the eight categories, use of ICD-10, and the Chinese terms recorded in `outputs/eligibility_rule_dictionary.csv`, as relayed by the authors on 11 November 2026. Heart failure includes 心力衰竭 and 心衰 and qualifies independently of cardiomyopathy. The patterns compactly represent the confirmed terms; they are not an exported SQL query.

The 939-column extract contains outpatient/emergency, primary discharge, pathology and previous diagnosis fields, but no upstream complication-screen field. The earliest preparation scripts read an already preprocessed table. The actual executable query, itemized ICD-10 list, exact field, lookback and record-frequency threshold are not retained in this extract. The released diagnosis fields therefore cannot independently reconstruct the upstream selection.

## Laboratory values

The providers confirm that the extract contains standardized dimensionless values. The release removes 137 wholly empty laboratory columns and copies the remaining 771 columns unchanged. All 408,976,950 source-to-release cells, including empty cells, agree. Of these, 24,899,677 are nonempty finite values. This establishes the release operation for every retained variable.

`outputs/lab_scale_diagnostics.csv` adds the observed mean, population standard deviation, range and count outside [0,1] for every field. There are 305 fields containing negative values and 466 fields containing values outside [0,1]. No field simultaneously has mean zero and population standard deviation one within 0.000001 over the released observations. These results describe the provided extract; they cannot identify an upstream transformation fitted on a different population or reference interval. A distribution alone does not recover the original measurement unit or transformation parameters.

The extended assessment covers all 771 fields, including the 769 fields beyond the two hemoglobin labels. Reference-interval linear validation models have cross-variable support for 27 well-observed fields and are consistent with two sparse protein label variants. Ten blood-count and protein identities were evaluated using a patient-level training/holdout partition. In held-out records, agreement was 99.95% for the hemoglobin/hematocrit/MCHC check and 99.76% for the total-protein/albumin/globulin check. All comparison counts, including nonmatching records, are retained in the aggregate outputs.

The same analysis compares linear reference-interval, centered-reference, reference-midpoint SD and logarithmic reference-interval models. The midpoint SD comparator uses an explicit normal-reference assumption disclosed confidentially; it is not a test of every possible external-population z-score. Of all 771 fields, 269 are constant in the released observations. Such fields do not identify a numerical conversion. Other fields have spacing-compatible or undetermined results, recorded individually. No unique transformation is imputed solely from an analyte name or a plausible clinical range.

`outputs/lab_transformation_assessment.csv` provides all-field conclusions; `lab_field_relationship_evidence.csv`, `lab_relationship_validation.csv`, `lab_model_comparison_aggregate.csv` and `lab_transformation_summary.json` give aggregate supporting evidence. Numerical reconstruction parameters and inverse scripts are supplied only in the confidential editor materials. These are validation models and do not independently verify the original hospital implementation.

## Reproduction

With approved access to version 1.0.0, run:

```sh
python profile_standardized_scale.py --release-dir /approved/path/to/release_v1 --output-dir regenerated_scale
```

The output contains aggregate statistics only. The script checks each field's finite count against the existing numerical profile. Figure reproduction from the supplied aggregates requires no patient-level files; see `README.md`.
