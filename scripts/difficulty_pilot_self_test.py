#!/usr/bin/env python3
"""Self-contained semantic-pilot declaration regression tests."""
from pathlib import Path
import tempfile
from copy import deepcopy
from difficulty_pilot import audit

def manifest():
    return {'release_id':'science_v4','unified_science_question':'Is the additional statistic genuinely informative?',
       'contract_frozen_before_final_blind':True,'blind_split_independent_units':True,
       'development_seed_count':3,
       'mandatory_science_gates':['A_null','B_causal','C_clean_gain','C_contaminated_safe'],
       'public_only_reference':{'reads_only_public':True,'passed':True,
          'all_mandatory_gates_passed':True,'log_path':'strong.log'},
       'ordinary_baselines':[
           {'name':'fixed_template','science_assumption':'Known nuisance response is sufficient',
            'reads_only_public':True,'failed_mandatory_gates':['A_null','B_causal'],
            'overall_passed':False,'log_path':'fixed.log'},
           {'name':'GG_only','science_assumption':'Never include the extra statistic',
            'reads_only_public':True,'failed_mandatory_gates':['C_clean_gain'],
            'overall_passed':False,'log_path':'gg.log'},
           {'name':'unconditional','science_assumption':'Always include the extra statistic',
            'reads_only_public':True,'failed_mandatory_gates':['C_contaminated_safe'],
            'overall_passed':False,'log_path':'always.log'}]}

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        for n in ('strong.log','fixed.log','gg.log','always.log'):(root/n).write_text('executed test log\n')
        base=manifest()
        assert audit(base,root)['status'].startswith('STRUCTURAL_PASS')
        count=1
        for variant in ('ordinary_pass','wrong_gate','no_reference','late_freeze',
                        'one_seed','missing_log','not_independent','no_assumption'):
            m=deepcopy(base)
            if variant=='ordinary_pass':
                m['ordinary_baselines'][1]['failed_mandatory_gates']=[]
                m['ordinary_baselines'][1]['overall_passed']=True
            elif variant=='wrong_gate':m['ordinary_baselines'][0]['failed_mandatory_gates']=['secret_gate']
            elif variant=='no_reference':m['public_only_reference']['passed']=False
            elif variant=='late_freeze':m['contract_frozen_before_final_blind']=False
            elif variant=='one_seed':m['development_seed_count']=1
            elif variant=='missing_log':m['ordinary_baselines'][2]['log_path']='missing.log'
            elif variant=='not_independent':m['blind_split_independent_units']=False
            elif variant=='no_assumption':m['ordinary_baselines'][0]['science_assumption']=''
            assert audit(m,root)['status']=='FAIL_OR_UNVERIFIED',variant
            count+=1
    print(f'PASS: {count} difficulty-pilot logic assertions; expert assessment still mandatory')
if __name__=='__main__':main()
