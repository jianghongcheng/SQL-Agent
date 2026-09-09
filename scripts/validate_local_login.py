"""Real local browser sign-in, session restoration and server-side sign-out."""
from datetime import datetime, timezone
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1] / 'runtime/local-demo'


def main():
    started = datetime.now(timezone.utc)
    run = ROOT / 'login-runs' / started.strftime('%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True, exist_ok=False)
    report = {'passed': False, 'started_at': started.isoformat(), 'checks': [], 'page_errors': []}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
            try:
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                page = context.new_page()
                page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
                page.goto('http://127.0.0.1:8765/?ui=login')
                page.wait_for_function("!document.querySelector('#login-panel').hidden")
                assert not page.locator('#workspace').is_visible()
                assert context.request.get('http://127.0.0.1:8765/v1/tasks').status == 401
                page.fill('#key', 'invalid-acceptance-key'); page.click('#login')
                page.wait_for_function("document.querySelector('#feedback').textContent.includes('401')")
                assert not page.locator('#workspace').is_visible()
                report['checks'].append('Signed-out access and invalid credentials rejected')
                page.screenshot(path=str(run/'login.png'))
                page.click('#demo-login')
                page.wait_for_function("document.querySelectorAll('#task option').length===8")
                assert page.locator('#workspace').is_visible()
                assert 'local-presenter' in page.locator('#identity').inner_text()
                assert context.request.get('http://127.0.0.1:8765/v1/tasks').status == 200
                cookies = context.cookies()
                cookie = next(c for c in cookies if c['name'] == 'sql_agent_session')
                assert cookie['httpOnly'] and cookie['sameSite'] == 'Strict'
                assert 'sql_agent_session' not in page.evaluate('document.cookie')
                report['checks'].append('Demo login creates an authenticated HttpOnly session')
                page.reload()
                page.wait_for_function("document.querySelectorAll('#task option').length===8")
                assert page.locator('#workspace').is_visible()
                page.fill('#question', 'Calculate net revenue in cents.')
                assert page.locator('#question').input_value() == 'Calculate net revenue in cents.'
                report['checks'].append('Refresh restores session and editable workspace')
                page.screenshot(path=str(run/'signed-in.png'))
                page.click('#logout')
                page.wait_for_function("document.querySelector('#workspace').hidden")
                assert context.request.get('http://127.0.0.1:8765/v1/tasks').status == 401
                replay_response = context.request.get('http://127.0.0.1:8765/v1/tasks', headers={'cookie':'sql_agent_session='+cookie['value']})
                assert replay_response.status == 401
                report['checks'].append('Sign out revokes the old session on the server')
                page.reload()
                page.wait_for_function("!document.querySelector('#login-panel').hidden")
                assert not page.locator('#workspace').is_visible()
                report['checks'].append('Refresh after sign out stays signed out')
                assert not report['page_errors']
                report['passed'] = True
            finally:
                browser.close()
    except Exception as exc:
        report['error'] = {'type':type(exc).__name__, 'message':str(exc)[:1500]}
        raise
    finally:
        report['completed_at'] = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(report, indent=2)
        (run/'acceptance.json').write_text(payload)
        (ROOT/'login-acceptance.json').write_text(payload)
        print(payload, flush=True)


if __name__ == '__main__':
    main()
