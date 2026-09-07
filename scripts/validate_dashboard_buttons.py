"""Click every dashboard button against the real local API and worker.

Uses explicit initial SQL to isolate UI behavior, not to measure model accuracy.
Creates only its own synthetic jobs and retains all acceptance attempts.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1] / 'runtime/local-demo'
SQL = "SELECT (SELECT SUM(amount_cents) FROM orders) - COALESCE((SELECT SUM(amount_cents) FROM refunds WHERE status='approved'), 0) AS net_revenue_cents"


def main():
    started = datetime.now(timezone.utc)
    run = ROOT / 'button-runs' / started.strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True, exist_ok=False)
    report = {'passed': False, 'started_at': started.isoformat(), 'checks': [], 'jobs': [],
              'page_errors': [], 'scope': 'UI acceptance with explicit SQL; not model accuracy'}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
            try:
                page = browser.new_page(viewport={'width': 1440, 'height': 1100})
                page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
                page.goto('http://127.0.0.1:8765')
                page.wait_for_function("!document.querySelector('#login-panel').hidden || !document.querySelector('#workspace').hidden")
                if page.locator('#login-panel').is_visible():
                    page.click('#demo-login')
                page.wait_for_function("!document.querySelector('#workspace').hidden")
                page.wait_for_function("document.querySelectorAll('#task option').length===8")
                page.click('#load')
                page.wait_for_function("document.querySelector('#feedback').textContent.includes('Loaded 8 tasks')")
                report['checks'].append('Load tasks gives success feedback')
                page.click('#refresh')
                assert 'Submit an analysis or open a job' in page.locator('#feedback').inner_text()
                page.click('#open')
                assert 'Enter a job ID' in page.locator('#feedback').inner_text()
                report['checks'].append('Refresh and Open explain missing input')
                page.select_option('#task', 'free_analysis_review')
                page.fill('#sql', SQL)
                page.evaluate("Object.defineProperty(crypto,'randomUUID',{value:undefined,configurable:true})")
                page.click('#submit')
                page.wait_for_function("document.querySelector('#jobid').textContent.length>0")
                job = page.locator('#jobid').inner_text(); report['jobs'].append(job)
                page.wait_for_function("document.querySelector('#status').textContent==='needs_review'", timeout=180000)
                assert '17000' in page.locator('#output').inner_text()
                report['checks'].append('Submit works without randomUUID and polls real worker to result')
                page.click('#refresh')
                page.wait_for_function("document.querySelector('#feedback').textContent.startsWith('Job refreshed')")
                page.click('#approve')
                assert 'Please record a review rationale' in page.locator('#feedback').inner_text()
                page.fill('#notes', 'Button acceptance: checked the synthetic 17000-cent result.')
                page.click('#approve')
                page.wait_for_function("document.querySelector('#status').textContent==='review_approved'")
                report['checks'].append('Approve requires notes and persists the review')
                page.select_option('#task', 'blocked_stale'); page.fill('#sql', '')
                page.click('#submit')
                page.wait_for_function('(old)=>document.querySelector("#jobid").textContent!==old', arg=job)
                report['jobs'].append(page.locator('#jobid').inner_text())
                page.wait_for_function("document.querySelector('#status').textContent==='needs_review'", timeout=180000)
                assert page.locator('#notes').input_value() == ''
                assert page.locator('#approve').is_disabled()
                assert 'No candidate result to approve' in page.locator('#review-help').inner_text()
                page.fill('#notes', 'Button acceptance: reject the stale source.')
                page.click('#reject')
                page.wait_for_function("document.querySelector('#status').textContent==='review_rejected'")
                report['checks'].append('Reject persists; unavailable approval explains why')
                page.fill('#existing', job); page.click('#open')
                page.wait_for_function("document.querySelector('#status').textContent==='review_approved'")
                assert page.locator('#jobid').inner_text() == job
                report['checks'].append('Open retrieves the previously approved job')
                page.screenshot(path=str(run / 'buttons.png'), full_page=True)
                assert not report['page_errors']
                report['passed'] = True
            finally:
                browser.close()
    except Exception as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)[:1500]}
        raise
    finally:
        report['completed_at'] = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(report, indent=2)
        (run / 'acceptance.json').write_text(payload)
        (ROOT / 'button-acceptance.json').write_text(payload)
        print(payload, flush=True)


if __name__ == '__main__':
    main()
