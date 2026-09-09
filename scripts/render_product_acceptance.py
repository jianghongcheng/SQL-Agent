"""Render recorded product acceptance, including failures, without rerunning it."""
import argparse
import html
import json
import math
from pathlib import Path


def render(path):
    summary=json.loads((path/'summary.json').read_text());manifest=json.loads((path/'manifest.json').read_text())
    esc=lambda v:html.escape(str(v))
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><title>SQL-Agent Product Acceptance</title><style>body{font:16px system-ui;max-width:1150px;margin:30px auto;padding:20px;color:#183343}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}table{width:100%;border-collapse:collapse}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{padding:12px;background:#f4f7f8;margin:12px 0}.notice{background:#fff2d9;padding:15px}</style><h1>SQL-Agent: small-scale product acceptance</h1>',
           '<p class="notice">Local synthetic evaluation, not production certification or external-user validation. All outcomes are retained. Fault drills replay recorded provider responses; normal evaluation and concurrency use real Ollama.</p>',
           '<p>Frozen: '+esc(manifest['frozen_at'])+' · Completed: '+esc(summary.get('completed_at'))+'</p>',
           '<p>Run completed: '+esc(summary['completed'])+' · Source integrity: '+esc(summary['sources_unchanged'])+' · Input integrity: '+esc(summary['inputs_unchanged'])+' · Model unchanged: '+esc(summary['model_unchanged'])+'</p>']
    records=[json.loads(p.read_text()) for p in sorted(path.glob('evaluation_*.json'))]
    if records:
        times=sorted(r['client_submit_to_result_ms']/1000 for r in records)
        parts+=['<h2>Frozen questions: first runs</h2><p>6 questions × 2 new datasets. Completed episodes: '+str(len(records))+'; correct: '+str(sum(r['correct'] for r in records))+'. Client submit-to-result p50: '+f'{times[math.ceil(.5*len(times))-1]:.2f}'+' s; p95: '+f'{times[math.ceil(.95*len(times))-1]:.2f}'+' s. Percentiles use nearest rank.</p>',
                '<table><tr><th>Question / data</th><th>Correct</th><th>Client seconds</th><th>Worker seconds</th><th>Model requests</th></tr>']
        for r in records:
            usage=(r['job'].get('result') or {}).get('telemetry',{})
            cells=[r['case']['case_id'],r['correct'],round(r['client_submit_to_result_ms']/1000,2),round(usage.get('pipeline_elapsed_ms',0)/1000,2),usage.get('calls')]
            parts.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in cells)+'</tr>')
        parts.append('</table>')
    parts.append('<h2>Three result forms on one database</h2><pre>'+esc(json.dumps(summary.get('three_output_forms',[]),indent=2))+'</pre>')
    parts.append('<h2>Four concurrent requests, one SQL worker</h2><p>This short burst does not establish sustained throughput or an SLO.</p><pre>'+esc(json.dumps(summary.get('concurrency',{}),indent=2))+'</pre>')
    fault_file=path/'faults.json'
    if fault_file.exists():
        faults=json.loads(fault_file.read_text());parts.append('<h2>Fault drills</h2><table><tr><th>Drill</th><th>Passed</th></tr>')
        for name,row in faults.items():parts.append('<tr><td>'+esc(name)+'</td><td>'+esc(row['passed'])+'</td></tr>')
        parts.append('</table><p>The worker was killed during an in-flight model HTTP request. Recovery repeats the whole read-only job. Persistent timeouts stop without publishing a candidate; they are not counted as successful answer recovery.</p>')
    resource_file=path/'resources.json'
    if resource_file.exists():
        samples=json.loads(resource_file.read_text());peaks={}
        for sample in samples:
            for name,r in sample['processes'].items():peaks[name]=max(peaks.get(name,0),r['rss_kib'])
        gpu=[]
        for sample in samples:
            try:gpu.append(int(sample['gpu_device_wide'].split(',')[0]))
            except (KeyError,ValueError):pass
        parts.append('<h2>Observed resources</h2><p>'+str(len(samples))+' samples; API/worker peak RSS in KiB: '+esc(peaks)+'. Peak device-wide GPU memory in MiB: '+esc(max(gpu) if gpu else 'unavailable')+'. GPU use includes other activity on the device. CPU seconds per process are preserved in resources.json.</p>')
    parts.append('<h2>Recorded answers and errors</h2>')
    records += [json.loads(p.read_text()) for p in sorted(path.glob('concurrent_*.json'))]
    for r in records:
        result=r['job'].get('result') or {}
        evidence={'question':r['case']['question'],'expected':r['case']['expected'],'actual':result.get('candidate_output') or result.get('output'),'status':r['job']['status'],'error':r['job']['error'],'trajectory':result.get('agent_trajectory')}
        parts.append('<details><summary>'+esc(r['case']['case_id'])+' — correct='+esc(r['correct'])+'</summary><pre>'+esc(json.dumps(evidence,indent=2))+'</pre></details>')
    if summary.get('error'):parts.append('<h2>Incomplete-run error</h2><pre>'+esc(summary['error'])+'</pre>')
    return ''.join(parts)+'</html>'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run',type=Path);args=parser.parse_args()
    (args.run/'report.html').write_text(render(args.run))
