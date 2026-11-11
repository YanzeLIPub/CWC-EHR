# Source provenance and laboratory scale evidence

The source-to-release processing is documented for all 771 retained laboratory variables. The available earlier code begins with already preprocessed data. It does not contain the hospital query or the original numerical conversion. The evidence inventory records the materials checked and the conclusion supported by each.

## Cohort selection

The clinical criteria are age at least 18 years and at least one of eight cardiovascular comorbidity categories, in the hospital oncology sampling frame. Other diseases are permitted. Heart failure qualifies independently of cardiomyopathy. The eight categories and Chinese labels are in `outputs/eligibility_rule_dictionary.csv`.

The 939-column institutional extract contains outpatient/emergency, primary discharge, pathology and previous diagnosis fields. It has no explicit upstream complication-screen field. The initial CancerEHR revision (1 December 2025) reads an already preprocessed table, and the version 1.0.0 rebuild retains the supplied cohort. Neither implements the hospital inclusion query. The actual ICD-10 use, synonym expansion, source field, lookback and record-frequency threshold cannot be established from these materials. Historical descriptive text patterns are identified as such in the dictionary and must not be treated as an executed eligibility query.

## Laboratory values

The providers confirm that the extract contains standardized dimensionless values. The release removes 137 wholly empty laboratory columns and copies the remaining 771 columns unchanged. All 408,976,950 source-to-release cells, including empty cells, agree. Of these, 24,899,677 are nonempty finite values. This establishes the release operation for every retained variable.

`outputs/lab_scale_diagnostics.csv` adds the observed mean, population standard deviation, range and count outside [0,1] for every field. There are 305 fields containing negative values and 466 fields containing values outside [0,1]. No field simultaneously has mean zero and population standard deviation one within 0.000001 over the released observations. These results describe the provided extract; they cannot identify an upstream transformation fitted on a different population or reference interval. A distribution alone does not recover the original measurement unit or transformation parameters.

For hemoglobin, the aggregate blood-count consistency evidence supports a reference-relative interpretation and the inference that negative scores likely reflect measurements below the reference lower limit. The original hospital implementation has not been independently verified. Parameters and reconstruction scripts are omitted from this public deposit. The evidence for hemoglobin is not extended to all other fields.

## Reproduction

With approved access to version 1.0.0, run:

```sh
python profile_standardized_scale.py --release-dir /approved/path/to/release_v1 --output-dir regenerated_scale
```

The output contains aggregate statistics only. The script checks each field's finite count against the existing numerical profile. Figure reproduction from the supplied aggregates requires no patient-level files; see `README.md`.
