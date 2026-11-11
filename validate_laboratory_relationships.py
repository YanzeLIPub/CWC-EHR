"""Validate blood-count and protein consistency using reference-interval standardization.

Analyte groups and check definitions are documented in the public
laboratory_validation_rules.json. The --parameters file supplies the numerical
reference limits and matching analyte labels for confidential peer review.
"""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd

def errors(x):
 r={
  'Hb_Hct_MCHC':(x.Hb-x.Hct*x.MCHC,1.,'g/L',['Hb','Hct','MCHC']),
  'Hct_RBC_MCV':(x.Hct-x.RBC*x.MCV/1000,.005,'L/L',['Hct','RBC','MCV']),
  'MCH_Hb_RBC':(x.MCH-x.Hb/x.RBC,.6,'pg',['MCH','Hb','RBC']),
  'TP_ALB_GLOB':(x.TP-x.ALB-x.GLOB,.2,'g/L',['TP','ALB','GLOB']),
  'AGR_ALB_GLOB':(x.AGR-x.ALB/x.GLOB,.02,'ratio',['AGR','ALB','GLOB'])}
 for k in ['NEUT','LYMPH','MONO','EOS','BASO']:
  r[k+'_WBC_pct']=(x[k]-x.WBC*x[k+'pct']/100,.02,'10^9/L',[k,'WBC',k+'pct'])
 return r

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--release-dir',type=Path,required=True)
 parser.add_argument('--parameters',type=Path,required=True,help='Reference limits and analyte labels in validation_parameters.json, supplied in the confidential reviewer attachment.')
 parser.add_argument('--output-dir',type=Path,required=True)
 args=parser.parse_args()
 parameters=json.loads(args.parameters.read_text())
 groups=parameters['analyte_labels'];limits=parameters['reference_limits']
 fields=list(dict.fromkeys(f for fs in groups.values() for f in fs))
 data=pd.read_csv(args.release_dir/'lab_test.csv',usecols=['patient_pseudo_id',*fields],dtype={'patient_pseudo_id':str})
 patients=pd.read_csv(args.release_dir/'patient_info.csv',usecols=['patient_pseudo_id','sex_source_code'],dtype=str).set_index('patient_pseudo_id')
 sex=data.patient_pseudo_id.map(patients.sex_source_code)
 z=pd.DataFrame({k:data[fs].bfill(axis=1).iloc[:,0] for k,fs in groups.items()})
 x=pd.DataFrame(index=z.index)
 for k,bounds in limits.items():
  if isinstance(bounds,dict):
   lower=sex.map({code:v[0] for code,v in bounds.items()});upper=sex.map({code:v[1] for code,v in bounds.items()})
  else:lower,upper=bounds
  x[k]=lower+(upper-lower)*z[k]
 results=[];field_results=[]
 for name,(difference,tolerance,unit,required) in errors(x).items():
  selected=z[required].notna().all(axis=1)
  error=np.abs(difference[selected].to_numpy());finite=error[np.isfinite(error)]
  results.append({'relationship':name,'n':len(error),'within_tolerance_n':int((error<=tolerance).sum()),'within_tolerance_fraction':float(np.mean(error<=tolerance)),'median_absolute_error':float(np.median(finite)),'p95_absolute_error':float(np.quantile(finite,.95)),'tolerance':tolerance,'validation_unit':unit})
  for group in required:
   for field in groups[group]:
    included=selected & data[field].notna();e=np.abs(difference[included].to_numpy())
    field_results.append({'field':field,'group':group,'relationship':name,'coobserved_n':len(e),'within_tolerance_fraction':float(np.mean(e<=tolerance))})
 args.output_dir.mkdir(parents=True,exist_ok=True)
 pd.DataFrame(results).to_csv(args.output_dir/'laboratory_consistency_results.csv',index=False)
 pd.DataFrame(field_results).to_csv(args.output_dir/'lab_field_validation.csv',index=False)
 print(pd.DataFrame(results)[['relationship','n','within_tolerance_n','within_tolerance_fraction']].to_string(index=False))

if __name__=='__main__':main()
