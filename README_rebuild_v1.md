# Rebuild CWC EHR version 1.0.0

The institutional rebuild uses the approved source extract and the production key for version 1.0.0. It preserves the supplied cohort of adults aged at least 18 years receiving cancer care with at least one of eight cardiovascular comorbidities. Other coexisting diseases were permitted. The clinical eligibility criteria confirmed by the cohort builders are in `rules.json`. Laboratory values were standardized before extraction and are copied unchanged by the rebuild.

The rebuild writes the five linked CSV tables. It uses one patient code across tables and one consistent date shift per patient. The encounter and laboratory keys support table joins. The diagnosis table preserves the source field and removes repeated text entries within each encounter and source. The laboratory table carries forward the observed fields as supplied, and the socioeconomic table retains the five linked area-level measures.

## Build and validate

Run the rebuild in the institutional environment. Supply the production key through `CWC_EHR_HMAC_KEY` and choose a new output directory.

```sh
python rebuild_release.py --source /approved/path/to/restricted_source.csv --mode build --confirm-full-run --output-dir release_output_v1
python finalize_release_metadata.py --release-dir release_output_v1 --output-dir final_metadata
```

The finalizer reconciles the row counts and cross-table keys. Use the finalized `release_manifest.json` and `quality_control_report.json` with the five CSVs. See `README.md` for laboratory validation and figure reproduction.
