"""Compare complete configurations on matched regression questions; no causal attribution."""
import json
from pathlib import Path
from scripts import run_paired_sql_benchmark as runner
from scripts.render_model_comparison import load_run


def main():
    baseline=[]
    for name in ('guided_coder14_dev_v2','guided_coder14_billing_v2','manufacturing_transfer_v2'):
        _,_,rows=load_run(name)
        baseline.extend(r for r in rows if r['method']=='native_sql_guided')
    manifest,summary,quality=load_run('quality_regression_v1')
    key=lambda r:(r['case_id'],r['variant'],r['trial'])
    old={key(r):r for r in baseline};new={key(r):r for r in quality}
    assert len(old)==len(baseline)==len(new)==len(quality)==156
    assert old.keys()==new.keys()
    assert all(old[k]['calls'][0]['prompt_sha256']==new[k]['calls'][0]['prompt_sha256'] for k in old)
    records=[{**r,'method':'coder_guided'} for r in baseline]+[{**r,'method':'thinking_repair'} for r in quality]
    out={'scope':'Matched known regression set: 26 questions, 2 instances, 3 repeats. Configuration comparison changes model, thinking, sampling, token budget and repair together; not an ablation of thinking. Runs sequential, not randomized latency comparison.',
         'matched_episodes_per_configuration':156,'identical_first_prompt_hashes':156,
         'baseline':runner.summarize(baseline,3),'quality':summary['all'],
         'paired_difference':runner.paired_difference(records,'thinking_repair','coder_guided'),
         'regressions':[list(k) for k in old if old[k]['accepted_correct'] and not new[k]['accepted_correct']],
         'gains':[list(k) for k in old if not old[k]['accepted_correct'] and new[k]['accepted_correct']],
         'failures':[{'case_id':r['case_id'],'variant':r['variant'],'trial':r['trial'],
                      'reason':r['pipeline']['result']['routing'],'calls':len(r['calls'])} for r in quality if not r['accepted_correct']]}
    fast_manifest,fast_summary,fast=load_run('fast_sql_regression_v1')
    fast_by_key={key(r):r for r in fast}
    assert len(fast_by_key)==len(fast)==156 and fast_by_key.keys()==new.keys()
    assert fast_manifest['model']['digest']==manifest['model']['digest']
    assert all(fast_by_key[k]['calls'][0]['prompt_sha256']==new[k]['calls'][0]['prompt_sha256'] for k in new)
    assert all(fast_manifest['source_sha256'][p]==h for p,h in manifest['source_sha256'].items() if p.startswith('src/'))
    assert fast_manifest['database_sha256']==manifest['database_sha256']
    fast_records=[{**r,'method':'fast_repair'} for r in fast]
    out.update(fast=fast_summary['all'],qwen_profiles_same_runtime_model_and_first_prompt=True,
        fast_vs_thinking=runner.paired_difference(records+fast_records,'fast_repair','thinking_repair'),
        fast_vs_coder=runner.paired_difference(records+fast_records,'fast_repair','coder_guided'),
        fast_failures=[{'case_id':r['case_id'],'variant':r['variant'],'trial':r['trial'],
                       'reason':r['pipeline']['result']['routing'],'calls':len(r['calls'])} for r in fast if not r['accepted_correct']])
    out['qwen_profile_scope']='Same runtime source, model digest, database bytes and first prompt; thinking, sampling, context setting and request timeout differ. This compares deployable profiles rather than isolating thinking as a cause.'
    path=runner.ROOT/'outputs/validation/quality_regression_v1/comparison.json'
    runner.write_json(path,out);print(json.dumps(out,indent=2))

if __name__=='__main__':main()
