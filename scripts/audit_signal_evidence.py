"""Audit complete local engineering evidence; never authorize production release.

Recompute live summaries and paired statistics from every planned record. Missing,
partial or inconsistent evidence fails the audit; negative model outcomes remain.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from sql_agent.acceptance_report import paired_comparison, summarize


def audit(root):
    checks = {}
    hashes = {}
    def read(relative):
        path = root/relative
        value = path.read_bytes()
        hashes[relative] = hashlib.sha256(value).hexdigest()
        return json.loads(value)
    def check(name, function):
        try:
            details = function()
            checks[name] = {'passed':True, 'details':details}
        except (OSError, ValueError, KeyError, AssertionError) as exc:
            checks[name] = {'passed':False, 'error':str(exc) or type(exc).__name__}

    def regression():
        path = root/'regression-final/regression.xml'
        hashes['regression-final/regression.xml'] = hashlib.sha256(path.read_bytes()).hexdigest()
        tree = ET.parse(path)
        cases = list(tree.iter('testcase'))
        assert cases and not any(list(tree.iter(tag)) for tag in ('failure','error','skipped')), 'regression incomplete'
        assert read('regression-final/evidence.json')['temporary_container_and_tmpfs_removed']
        return {'passed_tests':len(cases)}
    check('regression',regression)

    def retrieval():
        result = {}
        for chunking in ('window','structure'):
            manifest = read(f'retrieval/{chunking}/manifest.json')
            assert manifest['sources_unchanged']
            assert manifest['chunking'] == chunking and manifest['reranker_enabled']
            summary = read(f'retrieval/{chunking}/summary.json')
            for mode in ('bm25','hybrid','hybrid_reranked'):
                for phase in ('first_pass','warm_cache'):
                    name = mode+'_'+phase
                    rows = read(f'retrieval/{chunking}/{name}.json')
                    assert len(rows) == summary[name]['queries'] == 16
                    assert sum(r['rank']==1 for r in rows)/len(rows) == summary[name]['hit_at_1']
            result[chunking] = summary
        return result
    check('rag',retrieval)

    def live():
        frozen = read('frozen-commerce/evaluation.json')
        manifest = read('live/trial/manifest.json')
        assert manifest['dataset_sha256'] == hashes['frozen-commerce/evaluation.json']
        assert manifest['image_source_verified']
        assert manifest['cases'] == len(frozen['cases']) == 48
        modes = ['bm25','hybrid','hybrid_reranked']
        assert manifest['modes'] == modes
        summary = read('live/trial/summary.json')
        records = {}
        oracle = {c['case_id']:c for c in frozen['cases']}
        for mode in modes:
            rows = [read(str(f.relative_to(root))) for f in sorted((root/'live/trial'/mode).glob('eval-*.json'))]
            assert {r['case_id'] for r in rows} == set(oracle), f'{mode}: missing cases'
            for r in rows:
                candidate = (r.get('job',{}).get('result') or {}).get('candidate_output')
                expected = oracle[r['case_id']]['expected']
                correct = bool(candidate and candidate['columns']==expected['columns'] and candidate['rows']==expected['rows'])
                assert correct == r['correct'], 'saved correctness differs from frozen oracle'
                assert r.get('telemetry',{}).get('token_cost'), 'missing token accounting'
            recalculated = summarize(rows)
            assert recalculated == summary[mode]['summary'], 'saved summary differs from raw records'
            evidence = read(f'live/trial/{mode}/evidence.json')
            for key in ('run_complete','business_unchanged','result_survives_restart','containers_removed'):
                assert evidence[key], mode+': '+key
            records[mode] = rows
        comparisons = read('live/trial/paired.json')
        for a,b in zip(modes,modes[1:]):
            assert paired_comparison(records[a],records[b]) == comparisons[a+'__vs__'+b]
        inference = read('live/inference.json')
        assert inference['temporary_inference_stopped'] and inference['original_model_manifests_unchanged']
        browser = read('live-browser/evidence.json')
        assert browser['passed'] and not browser['browser_errors'] and browser['no_new_query_or_approval']
        return {mode:summary[mode]['summary'] for mode in modes}
    check('live_agent_and_evaluation',live)

    def finetuning():
        data = read('qlora-dataset.json')
        manifest = read('qlora-replay/manifest.json')
        assert manifest['dataset_sha256'] == hashes['qlora-dataset.json']
        domains = [{r['domain'] for r in data['splits'][s]} for s in ('train','dev','test')]
        assert not any(domains[a] & domains[b] for a,b in ((0,1),(0,2),(1,2))), 'domain leakage'
        assert [len(data['splits'][s]) for s in ('train','dev','test')] == [512,64,100]
        scored = read('qlora-replay/runtime_aligned_scores.json')
        report = read('qlora-replay/paired.json')
        for name in ('baseline','adapter'):
            rows = read('qlora-replay/'+name+'.json')
            assert hashes['qlora-replay/'+name+'.json'] == scored['raw_sha256'][name]
            assert len(rows) == 100
        assert report['deployment_decision'] == 'not_promoted'
        weights = read('qlora-replay/weights.json')
        assert 'adapter_model.safetensors' in weights
        for name,digest in weights.items():
            path = Path(__file__).resolve().parents[1]/'runtime/models/nl2sql-qlora'/name
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'adapter bytes changed'
        stress = read('qlora-fixture-stress.json')
        assert stress['planned'] == stress['scorable']+stress['unscorable'] == 100
        return {'summary':report['summary'], 'paired':report['paired'],
                'fixture_stress':stress['counts'], 'promoted':False}
    check('finetuning',finetuning)

    def deployment():
        deployed = read('deployment/evidence.json')
        gateway = read('gateway-fixed/evidence.json')
        assert deployed['passed'] and len(deployed['checks']) == 7 and all(deployed['checks'].values())
        assert deployed['load']['jobs'] == deployed['load']['successes'] == 100
        assert deployed['load']['failures'] == 0 and deployed['containers_removed']
        for key in ('passed','worker_direct_write_denied','worker_has_no_gateway_or_admin_token',
                    'approved_gateway_write_once','containers_removed'):
            assert gateway[key]
        serving = read('serving-reference/comparison.json')
        assert serving['summary']['before']['n_matched'] == serving['summary']['after']['n_matched'] > 0
        for phase in ('before','after'):
            for name,digest in serving['raw_sha256'][phase].items():
                read(f'serving-reference/{phase}/bm25/{name}')
                assert hashes[f'serving-reference/{phase}/bm25/{name}'] == digest
        return {'checks':deployed['checks'], 'load':{k:v for k,v in deployed['load'].items() if k!='trials'},
                'gateway_passed':True, 'historical_serving_comparison':serving['summary'],
                'serving_scope':serving['scope']}
    check('deployment',deployment)
    return {'local_engineering_complete':all(v['passed'] for v in checks.values()),
            'scope':'Five-signal local engineering protocol; model improvement and production SLO are separate, unproven claims.',
            'general_query_auto_release':False,'finetuned_model_promoted':False,
            'checks':checks,'evidence_sha256':hashes}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    report = audit(args.evidence.resolve())
    with args.output.open('x') as f:
        json.dump(report,f,indent=2)
    print(json.dumps({'local_engineering_complete':report['local_engineering_complete'],
                      'checks':{k:v['passed'] for k,v in report['checks'].items()}},indent=2))
    raise SystemExit(0 if report['local_engineering_complete'] else 1)


if __name__ == '__main__':
    main()
