# Laboratory metadata and cohort eligibility

All 771 laboratory fields use reference-interval linear standardization and have standardized dimensionless units. The variable dictionary preserves each released analyte label and records its standardization method, reference basis, sign convention, observation counts and quantiles.

The conversion is `z = (x − L)/(U − L)`, where `x` is the original measurement, `z` is the released dimensionless score, and `L` and `U` are the applicable lower and upper reference limits (`U > L`). The measurement and both limits use the same original unit. Reference intervals are specific to the analyte and use sex-specific limits where applicable. Zero denotes the lower limit and one denotes the upper limit. Negative values lie below the lower limit; values above one exceed the upper limit. The corresponding original-scale expression is `x = L + z(U − L)`.

With illustrative limits of `L = 10` and `U = 20`, measurements of 5, 10, 15, 20 and 25 yield standardized scores of −0.5, 0, 0.5, 1 and 1.5, respectively. These values are not patient data or clinical reference limits. `reference_interval_standardization.py` implements both expressions and reproduces this example.

`source_quantity_category` describes the physical quantity indicated by the analyte label. Empty entries indicate that no label-based category is assigned. The released unit and standardization method are documented for every field.

The laboratory table contains 530,450 rows and 771 laboratory fields: 408,976,950 cells in total, including 384,077,273 empty cells and 24,899,677 finite numeric values. Every cell matched the source extract.

`lab_relationship_validation.csv` reports ten blood-count and protein consistency checks, with all co-observed records included, and gives the tolerance and validation unit for each check. `lab_field_validation.csv` gives the contributing counts by released label. The public `laboratory_validation_rules.json` documents the 21 analyte groups, 29 released labels, record-selection rule, check definitions, tolerances and units. The public `validate_laboratory_relationships.py` script reproduces these results using the released CSVs and the numerical reference limits in `CWC_EHR_Laboratory_Validation_Reviewer.zip`, supplied as a confidential reviewer attachment. Pass its `validation_parameters.json` file with the script's `--parameters` option. `laboratory_validation_summary.json` summarizes the completed checks.

The eligibility dictionary records the eight cardiovascular categories, ICD-10 use and Chinese terms used for hospital cohort selection. Adults aged at least 18 years qualify when at least one category is present; other diseases are permitted. Heart failure qualifies independently of cardiomyopathy. Eligibility was applied before research extraction. The four released diagnosis fields describe outpatient/emergency, primary discharge, pathology and previous diagnoses.
