"""Publish separate acceptance studies alongside historical model evidence."""
import html
import json
from pathlib import Path

from scripts.render_model_comparison import render as model_report
from scripts.render_product_acceptance import render as acceptance_report

ROOT = Path(__file__).resolve().parents[1]


def main():
    sections = [
        '<section id="product-acceptance"><h1>Product acceptance</h1>',
        '<p>First-run synthetic evaluation: <b>11/12 correct</b> (6 questions, '
        '2 datasets). The original run later failed concurrent polling. '
        'After the queue fix: 4 concurrent jobs completed, <b>3/4 correct</b>; '
        'all five fault drills passed. These are separate studies, not a '
        'combined accuracy score or production certification.</p>',
    ]
    for name, label in (
        ('product_acceptance_v1', 'Original frozen run: evaluation completed, concurrency failed'),
        ('product_operations_v2', 'Operational regression: reused questions, recorded fault fixtures'),
    ):
        directory = ROOT / 'outputs/validation' / name
        page = acceptance_report(directory)
        (directory / 'report.html').write_text(page)
        sections.append('<details><summary>' + label + '</summary>'
                        + page[page.index('<h1>'):].removesuffix('</html>') + '</details>')
    browser = ROOT / 'runtime/local-demo/flexible-acceptance.json'
    if browser.exists():
        sections.append('<details><summary>Live browser workflow evidence</summary><pre>'
                        + html.escape(json.dumps(json.loads(browser.read_text()), indent=2))
                        + '</pre></details>')
    sections.append('</section><hr>')
    history = model_report()
    insertion = history.index('</style>') + len('</style>')
    combined = history[:insertion] + ''.join(sections) + history[insertion:]
    for target in ('runtime/local-demo/benchmark.html',
                   'outputs/validation/product_acceptance_overview.html'):
        (ROOT / target).write_text(combined)


if __name__ == '__main__':
    main()
