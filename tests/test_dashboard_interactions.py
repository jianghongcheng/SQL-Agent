"""Real browser clicks against the dashboard with a deterministic API transport.

No model calls: these tests isolate browser state and HTTP interaction semantics.
"""
import json
import shutil
import pytest
from contractsql.dashboard import render_dashboard


@pytest.fixture
def ui(monkeypatch):
    playwright = pytest.importorskip('playwright.sync_api')
    chrome = shutil.which('google-chrome')
    if not chrome:
        pytest.skip('Chrome is required for browser interaction tests')
    monkeypatch.delenv('CONTRACTSQL_LOCAL_DEMO', raising=False)
    state = {'signed_in': True, 'posts': [], 'reads': 0, 'hold_submit': False, 'pending': [], 'task_error': False, 'reviews': [],
             'tasks': [{'task_id': 'sample', 'question': 'List names', 'contract': {'specification': {}}}],
             'job': {'job_id': 'job-1', 'status': 'queued', 'result': None}}
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome, headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        def route(request):
            path = request.request.url.split('127.0.0.1:49999', 1)[-1]
            payload = {}
            if path == '/':
                request.fulfill(content_type='text/html', body=render_dashboard()); return
            if path == '/v1/auth/login':
                if request.request.post_data_json['api_key'] != 'valid-test-access':
                    request.fulfill(status=401,json={'detail':'invalid or missing API key'});return
                state['signed_in']=True
                payload={'name':'tester','role':'admin'}
            elif path == '/v1/auth/logout':
                state['signed_in']=False;payload={'signed_out':True}
            elif path == '/v1/auth/session':
                if not state['signed_in']:
                    request.fulfill(status=401,json={'detail':'invalid or missing browser session'});return
                payload={'name':'tester','role':'admin'}
            elif not state['signed_in']:
                request.fulfill(status=401,json={'detail':'invalid or missing browser session'});return
            elif path == '/v1/tasks':
                if state['task_error']:
                    request.fulfill(status=401, json={'detail': 'Invalid API key'}); return
                payload = {'tasks': state['tasks']}
            elif path == '/v1/jobs' and request.request.method == 'POST':
                state['posts'].append(request.request.post_data_json)
                if state['hold_submit']:
                    state['pending'].append(request); return
                payload = {'job': state['job']}
            elif path.endswith('/events'):
                payload = {'events': []}
            elif path == '/v1/jobs/job-1':
                state['reads'] += 1
                if state['reads'] >= 3 and not state['job']['status'].startswith('review_'):
                    state['job'] = {'job_id': 'job-1', 'status': 'needs_review',
                                    'result': {'candidate_output': {'columns': ['name'], 'rows': [['Ada']]}}}
                payload = state['job']
            elif path.endswith('/review'):
                state['reviews'].append(request.request.post_data_json)
                state['job']['status'] = 'review_' + ('approved' if request.request.post_data_json['decision'] == 'approve' else 'rejected')
                payload = state['job']
            request.fulfill(content_type='application/json', body=json.dumps(payload))
        page.route('**/*', route)
        page.goto('http://127.0.0.1:49999/')
        page.wait_for_function("document.querySelector('#task').value === 'sample'")
        yield page, state
        assert not errors
        browser.close()


def test_refresh_without_job_explains_next_action(ui):
    page, _ = ui
    page.click('#refresh')
    page.wait_for_function("document.body.innerText.includes('Submit an analysis or open a job')", timeout=1500)


def test_loading_tasks_gives_feedback_and_auth_failure_is_visible(ui):
    page, state = ui
    page.click('#load')
    page.wait_for_function("document.querySelector('#task').value === 'sample'")
    page.wait_for_function("document.querySelector('#feedback').textContent.includes('Loaded 1 task')")
    state['task_error'] = True
    page.click('#load')
    page.wait_for_function("document.querySelector('#feedback').textContent.includes('Invalid API key')")
    assert page.locator('#load').is_enabled()


def test_open_queued_job_keeps_polling_until_review(ui):
    page, state = ui
    page.fill('#existing', 'job-1'); page.click('#open')
    page.wait_for_function("document.querySelector('#status').textContent === 'needs_review'", timeout=4000)
    assert state['reads'] >= 2
    assert page.locator('#approve').is_enabled()


def test_submit_disables_duplicate_clicks_and_works_without_random_uuid(ui):
    page, state = ui
    page.click('#load')
    page.wait_for_function("document.querySelector('#task').value === 'sample'")
    page.evaluate("Object.defineProperty(crypto, 'randomUUID', {value: undefined, configurable: true})")
    state['hold_submit'] = True
    page.click('#submit')
    page.wait_for_function("document.querySelector('#submit').disabled", timeout=1500)
    page.evaluate("document.querySelector('#submit').click(); document.querySelector('#submit').click()")
    assert len(state['posts']) == 1
    assert 'Submitting' in page.locator('#feedback').inner_text()
    state['pending'][0].fulfill(json={'job': state['job']})
    page.wait_for_function("document.querySelector('#jobid').textContent === 'job-1'")
    assert 'queued' in page.locator('#status').inner_text()


@pytest.mark.parametrize('decision,status', [('approve','review_approved'), ('reject','review_rejected')])
def test_review_buttons_validate_notes_and_persist_decision(ui, decision, status):
    page, state = ui
    page.fill('#existing', 'job-1'); page.click('#open')
    page.wait_for_function("document.querySelector('#status').textContent === 'needs_review'", timeout=5000)
    page.click('#'+decision)
    assert 'Please record a review rationale' in page.locator('#feedback').inner_text()
    assert state['reviews'] == []
    page.fill('#notes', 'Checked this candidate against its source.')
    page.click('#'+decision)
    page.wait_for_function('(status)=>document.querySelector("#status").textContent === status', arg=status)
    assert state['reviews'] == [{'decision': decision, 'notes': 'Checked this candidate against its source.'}]
    assert page.locator('#'+decision).is_disabled()


def test_open_empty_id_reports_validation_without_request(ui):
    page, state = ui
    page.click('#open')
    assert 'Enter a job ID' in page.locator('#feedback').inner_text()
    assert state['reads'] == 0



def fixed_and_editable_tasks(state):
    state['tasks'] = [
        {'task_id': 'fixed', 'question': 'Registered metric',
         'contract': {'specification': {'verification_sql': 'SELECT 1'}}},
        {'task_id': 'custom', 'question': 'Ask a question',
         'contract': {'specification': {}}},
    ]


def test_default_question_is_editable_and_all_text_fields_accept_typing(ui):
    page, state = ui
    fixed_and_editable_tasks(state)
    page.click('#load')
    page.wait_for_function("document.querySelector('#task').value === 'custom'", timeout=1500)
    assert page.locator('#question').is_editable()
    for field, value in [('question','计算净收入'), ('sql','SELECT 1'), ('existing','job-123'), ('notes','核对金额')]:
        page.locator('#'+field).click()
        page.locator('#'+field).fill('')
        page.keyboard.insert_text(value)
        assert page.locator('#'+field).input_value() == value


def test_fixed_question_explains_lock_and_offers_editable_task(ui):
    page, state = ui
    fixed_and_editable_tasks(state)
    page.click('#load')
    page.wait_for_function("document.querySelectorAll('#task option').length === 2")
    page.select_option('#task', 'fixed')
    assert not page.locator('#question').is_editable()
    assert 'Fixed metric' in page.locator('#question-help').inner_text(timeout=1500)
    page.click('#custom-question')
    assert page.locator('#task').input_value() == 'custom'
    page.fill('#question','New analysis question')
    assert page.locator('#question').input_value() == 'New analysis question'


def test_loading_and_switching_tasks_preserve_typed_drafts(ui):
    page, state = ui
    fixed_and_editable_tasks(state)
    page.click('#load')
    page.wait_for_function("document.querySelector('#task').value === 'custom'", timeout=1500)
    page.fill('#question','My draft question'); page.fill('#sql','SELECT 2')
    page.click('#load')
    page.wait_for_function("document.querySelector('#feedback').textContent.startsWith('Loaded 2 tasks')")
    assert page.locator('#question').input_value() == 'My draft question'
    page.select_option('#task','fixed'); page.select_option('#task','custom')
    assert page.locator('#question').input_value() == 'My draft question'
    assert page.locator('#sql').input_value() == 'SELECT 2'



def test_login_rejects_wrong_key_restores_on_reload_and_signs_out(ui):
    page, state=ui
    state['signed_in']=False;page.reload()
    page.wait_for_function("!document.querySelector('#login-panel').hidden")
    assert not page.locator('#workspace').is_visible()
    page.fill('#key','wrong');page.click('#login')
    page.wait_for_function("document.querySelector('#feedback').textContent.includes('401')")
    assert not page.locator('#workspace').is_visible()
    page.fill('#key','valid-test-access');page.click('#login')
    page.wait_for_function("!document.querySelector('#workspace').hidden")
    assert 'tester' in page.locator('#identity').inner_text()
    assert page.locator('#key').input_value()==''
    page.reload()
    page.wait_for_function("!document.querySelector('#workspace').hidden")
    page.click('#logout')
    page.wait_for_function("document.querySelector('#workspace').hidden")
    assert state['signed_in'] is False
    assert 'Signed out' in page.locator('#feedback').inner_text()


def test_expired_session_returns_to_sign_in(ui):
    page,state=ui
    state['signed_in']=False
    page.click('#load')
    page.wait_for_function("document.querySelector('#workspace').hidden")
    assert page.locator('#login-panel').is_visible()
