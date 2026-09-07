"""Browser acceptance for the complete configuration and robustness report."""
from datetime import datetime, timezone
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]/'runtime/local-demo'


def main():
    report={'passed':False,'started_at':datetime.now(timezone.utc).isoformat(),'page_errors':[]}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
            try:
                page=browser.new_page(viewport={'width':1440,'height':1050})
                page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
                page.goto('http://127.0.0.1:8765')
                page.wait_for_function("!document.querySelector('#login-panel').hidden || !document.querySelector('#workspace').hidden")
                if page.locator('#login-panel').is_visible():
                    page.click('#demo-login')
                page.wait_for_function("!document.querySelector('#workspace').hidden")
                page.click('a[href="/benchmark"]')
                page.wait_for_url('**/benchmark')
                assert page.locator('.episode').count()==864
                assert '864' in page.locator('#total').inner_text()
                body=page.inner_text('body')
                assert all(value in body for value in ('142/156','108/156','102/156','35/48','24 additional instances'))
                page.locator('.episode').first.evaluate('(e)=>{let p=e.parentElement;while(p){if(p.tagName==="DETAILS")p.open=true;p=p.parentElement;}}')
                page.locator('.episode').first.locator('summary').click()
                assert page.locator('.episode').first.evaluate('(e)=>e.open')
                assert '11/12' in body and '3/4' in body
                assert page.locator('#product-acceptance').count()==1
                assert not report['page_errors']
                page.screenshot(path=str(ROOT/'benchmark.png'))
                report.update(passed=True,episodes=864,checks=['homepage link','all trajectories present','matched comparison counts','data replay section','SQL details expand'])
            finally:
                browser.close()
    finally:
        report['completed_at']=datetime.now(timezone.utc).isoformat()
        (ROOT/'benchmark-browser-acceptance.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report))


if __name__=='__main__':main()
