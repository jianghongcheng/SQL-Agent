"""Read an existing live acceptance result in Chrome; no query or approval submitted."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode-directory',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    from playwright.sync_api import sync_playwright
    config = json.loads((args.mode_directory/'compose.json').read_text())['services']['api']
    key = next(iter(json.loads(config['environment']['SQL_AGENT_API_KEYS'])))
    port = config['command'][config['command'].index('--port')+1]
    base = 'http://127.0.0.1:'+port
    raw = next(f for f in sorted(args.mode_directory.glob('eval-*.json'))
               if json.loads(f.read_text()).get('job',{}).get('status') == 'needs_review')
    record = json.loads(raw.read_text())
    args.output.mkdir(parents=True,exist_ok=False)
    expected = record['telemetry']['token_cost']
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=shutil.which('google-chrome'),
                                    headless=True,args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1200,'height':900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.goto(base)
            page.fill('#key',key)
            page.click('#login')
            page.wait_for_selector('#workspace',state='visible')
            page.fill('#request-id',record['job_id'])
            page.click('#load')
            page.wait_for_function("document.querySelector('#status').textContent === 'needs_review'")
            text = page.locator('#token-cost').inner_text()
            assert str(expected['total_tokens'] if expected['complete'] else expected['observed_total_tokens']) in text
            assert not errors, errors
            # Do not place the password field or session cookie in evidence.
            assert page.locator('#key').input_value() == ''
            page.screenshot(path=str(args.output/'dashboard.png'),full_page=True)
            result = {'passed':True,'scope':__doc__,'case_id':record['case_id'],
                'raw_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),
                'token_cost_text':text,'expected':expected,'browser_errors':errors,
                'no_new_query_or_approval':True}
            (args.output/'evidence.json').write_text(json.dumps(result,indent=2))
            print(json.dumps(result,indent=2))
        finally:
            browser.close()


if __name__ == '__main__':
    main()
