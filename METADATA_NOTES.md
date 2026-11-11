# Laboratory metadata and cohort eligibility

All 771 laboratory fields use reference-interval linear standardization and have standardized dimensionless units. The variable dictionary preserves each released analyte label and records its standardization method, reference basis, sign convention, observation counts and quantiles.

Zero denotes the reference lower limit and one denotes the reference upper limit. Negative values lie below the lower limit; values above one exceed the upper limit. Reference intervals are specific to the analyte and use sex-specific limits where applicable. Numerical conversion parameters are supplied in the confidential editor materials.

`source_quantity_category` describes the physical quantity indicated by the analyte label. Empty entries indicate that no label-based category is assigned. The released unit and standardization method are documented for every field.

The laboratory table contains 530,450 rows and 771 laboratory fields: 408,976,950 cells in total, including 384,077,273 empty cells and 24,899,677 finite numeric values. Every cell matched the source extract.

`lab_relationship_validation.csv` reports ten blood-count and protein consistency checks, with all co-observed records included. `lab_field_validation.csv` gives the contributing counts by released label. The formula, reference limits and tolerances used in these checks are included in the confidential editor attachment. `laboratory_validation_summary.json` summarizes the completed checks.

The eligibility dictionary records the eight cardiovascular categories, ICD-10 use and Chinese terms used for hospital cohort selection. Adults aged at least 18 years qualify when at least one category is present; other diseases are permitted. Heart failure qualifies independently of cardiomyopathy. Eligibility was applied before research extraction. The four released diagnosis fields describe outpatient/emergency, primary discharge, pathology and previous diagnoses.
