#!/usr/bin/env python3
"""Self-contained release lock regression tests; standard library only."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED
from release_lock import ReleaseError, check

RID="demo_science_v4_20261105"

def make_payload(variant=None):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["case_id", "prediction"])
    for i in range(40):
        w.writerow([f"P{i:04d}", ""])
    if variant == "unicode_alias":
        out = io.StringIO()
        w=csv.writer(out)
        w.writerow(["case_id", "prediction"])
        for i in range(40): w.writerow([("P００００" if i==0 else f"P{i:04d}"), ""])
    if variant == "extra_cell":
        out = io.StringIO()
        out.write("case_id,prediction\n")
        for i in range(40): out.write(f"P{i:04d},,secret\n" if i==8 else f"P{i:04d},\n")
    return out.getvalue().encode('utf-8')

def zip_write(path, payloads):
    with ZipFile(path,'w',ZIP_DEFLATED) as z:
        for k,v in payloads.items(): z.writestr(k,v)

def fixture(td, mutation=None):
    public={
        'README_AGENT.md': (f'Bundle {RID}\nAnswer file prediction_template.csv\n').encode(),
        'calibration.csv': b'case_id,observed\nC0000,0.1\n',
        'blind.csv': b'case_id,observed\nP0000,0.1\n',
        'prediction_template.csv': make_payload(mutation),
    }
    if mutation == 'missing_blind': public.pop('blind.csv')
    if mutation == 'secret': public['private/truth.csv']=b'secret\n'
    manifest = {
      'bundle_id': RID if mutation!='wrong_version' else 'fp_selection_response_v1',
      'schema_version':'4.0',
      'public_artifacts':[{'filename':name,'bytes':len(data),
         'sha256':hashlib.sha256(data).hexdigest()} for name,data in public.items()]
    }
    if mutation=='bad_sha': manifest['public_artifacts'][0]['sha256']='0'*64
    public['benchmark_manifest.json']=json.dumps(manifest).encode()
    private={
      'private/README_REVIEWER.md':f'Hidden {RID}'.encode(),
      'private/generate.py':b'# generator', 'private/truth.npz':b'npz stub',
      'private/grader.py':b'# grader','private/reference_solver.py':b'# public only',
      'private/audit.py':b'# audit'
    }
    if mutation == 'missing_grader': private.pop('private/grader.py')
    p=td/'public.zip';q=td/'private.zip';task=td/'task.md'
    zip_write(p,public);zip_write(q,private)
    task.write_text(f'Release {RID}: 40 rows prediction_template.csv',encoding='utf-8')
    if mutation=='wrong_task':task.write_text('old V1 task 40 rows',encoding='utf-8')
    contract={
       'release_id':RID,'schema_version':'4.0',
       'public':{'file_count':5,'manifest':'benchmark_manifest.json',
                 'readme':'README_AGENT.md',
                 'required_members':['README_AGENT.md','blind.csv','prediction_template.csv'],
                 'csv_templates':[{'member':'prediction_template.csv','header':['case_id','prediction'],
                      'id_column':'case_id','rows':40,'id_regex':r'P[0-9]{4}'}]},
       'private':{'min_file_count':6,'reviewer_readme':'private/README_REVIEWER.md',
                 'required_members':['private/generate.py','private/grader.py','private/truth.npz',
                    'private/audit.py','private/reference_solver.py']},
       'task_text_required_tokens':['40','prediction_template.csv']
    }
    return contract,p,q,task

def main():
    count=0
    with tempfile.TemporaryDirectory() as root:
        for variant, should_pass in [
           (None,True),('missing_blind',False),('wrong_version',False),
           ('bad_sha',False),('secret',False),('unicode_alias',False),
           ('extra_cell',False),('missing_grader',False),('wrong_task',False)
        ]:
            td=Path(root)/(variant or 'valid');td.mkdir()
            cfg,p,q,t=fixture(td,variant)
            try:
                result=check(cfg,p,q,t)
                ok=result['status'].startswith('STRUCTURAL_PASS')
            except ReleaseError:
                ok=False
            assert ok==should_pass, (variant,ok,should_pass)
            count+=1
    print(f'PASS: {count} release-lock assertions, including old-version, missing-file, hash, private leak, ID, CSV and task mismatch')
if __name__=='__main__':main()
