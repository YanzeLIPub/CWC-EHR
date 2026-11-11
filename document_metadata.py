"""Join curated metadata annotations to the regenerated laboratory profiles."""
from pathlib import Path
import csv
import argparse

ROOT = Path(__file__).resolve().parent

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profiles',type=Path,default=ROOT/'outputs/lab_variable_qc.csv')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/lab_variable_metadata.csv')
    args=parser.parse_args()
    annotations = read(ROOT / 'metadata/laboratory_annotations.csv')
    profiles = {r['field']: r for r in read(args.profiles)}
    fields = ['lab_rows','nonempty_n','missing_n','finite_numeric_n','nonnumeric_nonempty_n','nonfinite_numeric_n','negative_n','zero_n','positive_n','patients_with_nonempty_value_n','source_cell_mismatches_n','nonempty_percent_of_lab_rows','negative_percent_of_finite','minimum','p01','q1','median','q3','p99','maximum']
    if set(profiles) != {r['field'] for r in annotations}:
        raise ValueError('Profile fields and annotation fields differ.')
    rows = [{**a, **{k: profiles[a['field']][k] for k in fields}} for a in annotations]
    with args.output.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'Documented {len(rows)} laboratory fields.')

if __name__ == '__main__':
    main()
