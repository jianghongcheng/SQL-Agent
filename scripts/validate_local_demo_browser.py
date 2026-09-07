"""Live browser acceptance; retain each run, including failures.

Requires Playwright, Chrome, and the local API/worker/Ollama stack.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]/'runtime/local-demo'


def main():
    started=datetime.now(timezone.utc)
    run=ROOT/'browser-runs'/started.strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True,exist_ok=False)
    report={'passed':False,'started_at':started.isoformat(),'checks':[],'jobs':{},
            'page_errors':[],'artifacts':str(run.relative_to(ROOT)),'stage':'startup'}
    if (ROOT/'processes.json').exists():
        state=json.loads((ROOT/'processes.json').read_text())
        report['service']={k:state.get(k) for k in ('model','generation_format','thinking','max_tokens','started_at')}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
            try:
                page=browser.new_page(viewport={'width':1440,'height':1100})
                page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
                def screenshot(name):
                    page.screenshot(path=str(run/name),full_page=True)
                    shutil.copyfile(run/name,ROOT/name)
                page.goto('http://127.0.0.1:8765')
                page.wait_for_function("!document.querySelector('#login-panel').hidden || !document.querySelector('#workspace').hidden")
                if page.locator('#login-panel').is_visible():
                    page.click('#demo-login')
                page.wait_for_function("!document.querySelector('#workspace').hidden")
                page.wait_for_function("document.querySelector('#task option[value=invoice_balance]') !== null")
                report['checks'].append('registered billing task loaded')
                report['stage']='verified metric'
                page.select_option('#task','net_revenue')
                assert page.locator('#question').evaluate('(e)=>e.readOnly')
                page.click('#submit')
                page.wait_for_function("document.querySelector('#status').textContent === 'completed'",timeout=180000)
                report['jobs']['net_revenue']=page.locator('#jobid').inner_text()
                assert '17000' in page.locator('#output').inner_text()
                assert 'Input / output tokens observed' in page.locator('#performance').inner_text()
                assert 'Dollar cost: unavailable' in page.locator('#cost').inner_text()
                report['checks'].extend(['net revenue 17000 cents','runtime and token usage displayed','unknown cost labeled'])
                screenshot('demo.png')
                report['stage']='source health and review'
                page.select_option('#task','blocked_stale');page.click('#submit')
                page.wait_for_function("document.querySelector('#status').textContent === 'needs_review'",timeout=30000)
                report['jobs']['blocked_stale']=page.locator('#jobid').inner_text()
                assert 'data_quality_blocked' in page.locator('#release').inner_text()
                page.fill('#notes','Browser acceptance: stale data requires refresh before analysis.')
                page.click('#reject')
                page.wait_for_function("document.querySelector('#status').textContent === 'review_rejected'",timeout=10000)
                report['checks'].extend(['stale source blocked','review rejection persisted'])
                screenshot('demo-blocked.png')
                report['stage']='general billing with visible dictionary'
                page.select_option('#task','invoice_balance');page.click('#submit')
                page.wait_for_function("document.querySelector('#status').textContent === 'needs_review'",timeout=180000)
                assert page.locator('#notes').input_value()==''
                report['checks'].append('review notes cleared between jobs')
                billing=json.loads(page.locator('#result').text_content())
                report['jobs']['invoice_balance']=billing['job_id']
                (run/'billing-job.json').write_text(json.dumps(billing,indent=2))
                screenshot('demo-billing.png')
                assert 'synthetic billing dictionary' in page.locator('#definitions').inner_text()
                assert billing['result']['candidate_output']['rows']==[[11,38],[12,100],[13,-70],[14,0],[15,50]]
                assert billing['result']['release']['approved'] is False
                report['checks'].extend(['visible billing dictionary','billing balances match independent arithmetic','general result requires review'])
                assert not report['page_errors'],report['page_errors']
                report.update(passed=True,stage='completed')
            finally:
                browser.close()
    except Exception as exc:
        report['error']={'type':type(exc).__name__,'message':str(exc)[:2000]}
        raise
    finally:
        report['completed_at']=datetime.now(timezone.utc).isoformat()
        payload=json.dumps(report,indent=2)
        (run/'acceptance.json').write_text(payload)
        (ROOT/'browser-acceptance.json').write_text(payload)
        print(payload,flush=True)


if __name__=='__main__':main()
