import json
import pytest


def test_failed_browser_run_replaces_stale_success_and_retains_failure(tmp_path,monkeypatch):
    pytest.importorskip('playwright.sync_api')
    from scripts import validate_local_demo_browser as validation
    monkeypatch.setattr(validation,'ROOT',tmp_path)
    (tmp_path/'browser-acceptance.json').write_text('{"passed": true}')
    def unavailable():
        raise RuntimeError('browser unavailable')
    monkeypatch.setattr(validation,'sync_playwright',unavailable)
    with pytest.raises(RuntimeError,match='browser unavailable'):
        validation.main()
    latest=json.loads((tmp_path/'browser-acceptance.json').read_text())
    assert latest['passed'] is False and latest['error']['type']=='RuntimeError'
    assert latest['stage']=='startup' and latest['completed_at']
    saved=list((tmp_path/'browser-runs').glob('*/acceptance.json'))
    assert len(saved)==1 and json.loads(saved[0].read_text())==latest
