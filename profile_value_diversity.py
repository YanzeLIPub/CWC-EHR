"""Reproduce aggregate distinct-value and constant-field counts on the released scale."""
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--release-dir',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
 a=p.parse_args();root=Path(__file__).resolve().parent
 expected=pd.read_csv(root/'outputs/lab_transformation_assessment.csv').set_index('field')
 fields=list(expected.index);distinct={f:set() for f in fields};counts={f:0 for f in fields}
 for chunk in pd.read_csv(a.release_dir/'lab_test.csv',usecols=fields,chunksize=12000):
  for f in fields:
   v=chunk[f].to_numpy(dtype=float);v=v[np.isfinite(v)];counts[f]+=len(v);distinct[f].update(np.unique(v).tolist())
 rows=[{'field':f,'finite_n':counts[f],'distinct_n':len(distinct[f]),'constant_in_release':len(distinct[f])==1} for f in fields]
 result=pd.DataFrame(rows).set_index('field')
 if not np.array_equal(result[['finite_n','distinct_n']].to_numpy(),expected[['finite_n','distinct_n']].to_numpy()):
  raise ValueError('Finite or distinct-value counts differ from the deposited aggregate assessment.')
 a.output_dir.mkdir(parents=True,exist_ok=True);result.to_csv(a.output_dir/'lab_value_diversity.csv')
 print(f'{len(fields)} fields checked; {int(result.constant_in_release.sum())} constant fields.')

if __name__=='__main__':main()
