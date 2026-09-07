"""Real English UI workflow for three query shapes on the same registered task."""
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from playwright.sync_api import sync_playwright
from scripts.commerce_acceptance_cases import fixture,DEMO_QUESTIONS

ROOT=Path(__file__).resolve().parents[1]/'runtime/local-demo'


def main():
    run=ROOT/'flexible-runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');run.mkdir(parents=True,exist_ok=False)
    report={'passed':False,'started_at':datetime.now(timezone.utc).isoformat(),'episodes':[],'page_errors':[],'scope':'Repeated demo questions; browser acceptance, not additional held-out accuracy'}
    data=fixture(17);months={}
    for o in data['orders']:months[o[2][:7]]=months.get(o[2][:7],0)+o[3]
    expected=[[[sum(o[3] for o in data['orders'])]],[[o[0],o[2],o[3]] for o in data['orders']],[[m,v] for m,v in sorted(months.items())]]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
            try:
                page=browser.new_page(viewport={'width':1440,'height':1100});page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
                page.goto('http://127.0.0.1:8765');page.click('#demo-login')
                page.wait_for_function("document.querySelector('#task').value==='commerce_analysis'")
                assert page.locator('#question').is_editable()
                previous=''
                for i,question in enumerate(DEMO_QUESTIONS):
                    page.select_option('#example-question',question);assert page.locator('#question').input_value()==question
                    started=time.monotonic();page.click('#submit')
                    page.wait_for_function('(old)=>document.querySelector("#jobid").textContent!==old',arg=previous)
                    page.wait_for_function("document.querySelector('#status').textContent==='needs_review'",timeout=450000)
                    elapsed=(time.monotonic()-started)*1000
                    job=json.loads(page.locator('#result').text_content());previous=job['job_id']
                    (run/f'job_{i}.json').write_text(json.dumps(job,indent=2))
                    candidate=job['result']['candidate_output']
                    record={'question':question,'job_id':previous,'browser_click_to_result_ms':elapsed,'correct':bool(candidate and candidate['rows']==expected[i]),'columns':candidate['columns'] if candidate else None}
                    report['episodes'].append(record)
                    assert record['correct']
                    assert 'Observed submit-to-result (this page)' in page.locator('#performance').inner_text()
                    assert job['result']['release']['approved'] is False
                    page.fill('#notes','Browser acceptance: independently checked the synthetic result; recording a review decision.')
                    page.click('#approve')
                    page.wait_for_function("document.querySelector('#status').textContent==='review_approved'")
                    page.screenshot(path=str(run/f'query_{i}.png'),full_page=True)
                first=report['episodes'][0]['job_id'];page.fill('#existing',first);page.click('#open')
                page.wait_for_function('(j)=>document.querySelector("#jobid").textContent===j',arg=first)
                page.wait_for_function("document.querySelector('#status').textContent==='review_approved'")
                assert '58250' in page.locator('#output').inner_text()
                assert not report['page_errors'];report['passed']=True
            finally:browser.close()
    except Exception as exc:
        report['error']={'type':type(exc).__name__,'message':str(exc)[:1500]};raise
    finally:
        report['completed_at']=datetime.now(timezone.utc).isoformat();payload=json.dumps(report,indent=2)
        (run/'acceptance.json').write_text(payload);(ROOT/'flexible-acceptance.json').write_text(payload);print(payload,flush=True)


if __name__=='__main__':main()
