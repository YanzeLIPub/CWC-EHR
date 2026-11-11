"""Calculate aggregate scale diagnostics for every released laboratory field."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-dir', type=Path, required=True)
    parser.add_argument('--profiles', type=Path, default=Path('outputs/lab_variable_qc.csv'))
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    with args.profiles.open(encoding='utf-8-sig', newline='') as handle:
        profiles = list(csv.DictReader(handle))
    names = [row['field'] for row in profiles]
    n = np.zeros(len(names), dtype=np.int64)
    mean = np.zeros(len(names))
    m2 = np.zeros(len(names))
    outside = np.zeros(len(names), dtype=np.int64)
    rows = 0
    for chunk in pd.read_csv(args.release_dir / 'lab_test.csv', usecols=names,
                             dtype=float, encoding='utf-8-sig', chunksize=8000):
        x = chunk[names].to_numpy()
        rows += len(x)
        valid = np.isfinite(x)
        if np.isinf(x).any():
            raise ValueError('Infinite laboratory values are not supported.')
        k = valid.sum(axis=0)
        chunk_mean = np.divide(np.where(valid, x, 0).sum(axis=0), k,
                               out=np.zeros(len(names)), where=k > 0)
        chunk_m2 = np.where(valid, x - chunk_mean, 0)
        chunk_m2 = (chunk_m2 * chunk_m2).sum(axis=0)
        total = n + k
        delta = chunk_mean - mean
        m2 += chunk_m2 + np.divide(delta * delta * n * k, total,
                                   out=np.zeros(len(names)), where=total > 0)
        mean += np.divide(delta * k, total, out=np.zeros(len(names)), where=total > 0)
        n = total
        outside += ((x < 0) | (x > 1)).sum(axis=0)
    sd = np.sqrt(m2 / n)
    results = []
    for i, p in enumerate(profiles):
        if int(p['finite_numeric_n']) != n[i]:
            raise ValueError('Finite counts disagree with the numerical profile: ' + names[i])
        results.append({
            'field': names[i],
            'finite_n': int(n[i]),
            'mean_on_released_scale': float(mean[i]),
            'population_sd_on_released_scale': float(sd[i]),
            'outside_zero_one_n': int(outside[i]),
            'minimum': float(p['minimum']),
            'maximum': float(p['maximum']),
            'negative_n': int(p['negative_n']),
            'zero_n': int(p['zero_n']),
            'complete_extract_zero_mean_unit_sd_at_1e_minus6': bool(
                abs(mean[i]) <= 1e-6 and abs(sd[i] - 1) <= 1e-6),
            'entirely_within_zero_one': bool(outside[i] == 0),
            'original_transform_identified_by_distribution': False,
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / 'lab_scale_diagnostics.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    summary = {
        'release_version': '1.0.0',
        'laboratory_rows': rows,
        'laboratory_fields': len(names),
        'finite_cells': int(n.sum()),
        'fields_with_negative_values': sum(r['negative_n'] > 0 for r in results),
        'fields_with_values_outside_zero_one': sum(r['outside_zero_one_n'] > 0 for r in results),
        'fields_entirely_within_zero_one': sum(r['entirely_within_zero_one'] for r in results),
        'fields_matching_complete_extract_zero_mean_unit_sd_at_1e_minus6': sum(
            r['complete_extract_zero_mean_unit_sd_at_1e_minus6'] for r in results),
        'scope': 'Moments and ranges describe the released observations. They do not identify an original transformation fitted on another population or reference interval.',
        'provenance': 'All field counts reconciled with outputs/lab_variable_qc.csv. Original clinical-scale measurements were not supplied.',
    }
    (args.output_dir / 'lab_scale_summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
