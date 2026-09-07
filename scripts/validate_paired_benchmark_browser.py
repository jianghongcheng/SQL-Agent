"""Optional Chrome acceptance for the recorded 432-episode v1 report."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path(__file__).resolve().parents[1]/'runtime/local-demo'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1440,'height':1050})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8765')
 page.wait_for_function("document.querySelectorAll('#task option').length === 6")
 page.click('a[href="/benchmark"]')
 page.wait_for_url('**/benchmark')
 assert '432 episodes' in page.inner_text('body')
 assert '39/72' in page.inner_text('body') and '30/72' in page.inner_text('body')
 assert 'Cross-instance checks and model usage' in page.inner_text('body')
 assert '216085/23593' in page.inner_text('body')
 page.locator('summary',has_text='open_by_team').click()
 assert page.locator('details[open]').count()==1
 page.screenshot(path=str(out/'benchmark.png'),full_page=True)
 assert not errors,errors
 (out/'benchmark-browser-acceptance.json').write_text(json.dumps({'passed':True,'checks':['homepage link','432 completed episodes','comparison values match report','token totals visible','per-question details expand'],'page_errors':errors},indent=2))
 print('Benchmark browser acceptance passed')
 browser.close()
