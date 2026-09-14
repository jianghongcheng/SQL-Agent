#!/usr/bin/env python3
"""Render the repository's architecture diagram without external dependencies."""

from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "workflow.svg"


def card(x, y, w, h, title, lines, *, fill="#FFFFFF", stroke="#CBD5E1", accent="#2563EB"):
    body = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/>',
        f'<rect x="{x}" y="{y}" width="6" height="{h}" rx="3" fill="{accent}"/>',
        f'<text x="{x + 22}" y="{y + 29}" class="card-title">{escape(title)}</text>',
    ]
    for index, line in enumerate(lines):
        body.append(f'<text x="{x + 22}" y="{y + 55 + index * 20}" class="card-text">{escape(line)}</text>')
    return "\n".join(body)


def arrow(x1, y1, x2, y2, *, dashed=False, label=None):
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    parts = [f'<path d="M{x1} {y1} L{x2} {y2}" class="arrow"{dash}/>' ]
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        parts.append(f'<text x="{mx}" y="{my - 8}" text-anchor="middle" class="arrow-label">{escape(label)}</text>')
    return "\n".join(parts)


def main():
    cards = []
    arrows = []

    # Request and delivery.
    cards.append(card(70, 120, 260, 90, "Clients", ["Browser · FastAPI · MCP"], fill="#EFF6FF"))
    cards.append(card(430, 120, 280, 90, "Durable request layer", ["Persistent jobs · checkpoints", "worker leases · retries"], fill="#EFF6FF"))
    cards.append(card(810, 120, 280, 90, "Grounding", ["Allowlisted schema linking", "optional scoped hybrid RAG"], fill="#EFF6FF"))
    cards.append(card(1190, 120, 180, 90, "Planner", ["SQL · clarify · stop"], fill="#EFF6FF"))
    arrows += [arrow(330,165,430,165), arrow(710,165,810,165), arrow(1090,165,1190,165)]

    # Read graph.
    cards.append(card(105, 330, 260, 105, "Policy gate", ["Database and table scope", "read-only SQL · limits"], fill="#F8FAFC", accent="#0F766E"))
    cards.append(card(455, 330, 260, 105, "Read executor", ["Bounded database call", "result and timeout limits"], fill="#F8FAFC", accent="#0F766E"))
    cards.append(card(805, 330, 260, 105, "Advisory Verifier", ["Independent comparison SQL", "result-agreement signal"], fill="#F8FAFC", accent="#0F766E"))
    cards.append(card(1155, 330, 260, 105, "Human review", ["Inspect SQL, result and trace", "accept · reject"], fill="#F8FAFC", accent="#0F766E"))
    arrows += [arrow(1280,210,235,330), arrow(365,382,455,382), arrow(715,382,805,382), arrow(1065,382,1155,382)]

    cards.append(card(455, 510, 260, 90, "Execution repair", ["Eligible database errors only", "bounded attempt budget"], fill="#FFF7ED", stroke="#FDBA74", accent="#EA580C"))
    cards.append(card(805, 510, 260, 90, "Semantic repair", ["Optional verifier-guided retry", "never treated as proof"], fill="#FFF7ED", stroke="#FDBA74", accent="#EA580C"))
    cards.append(card(1155, 240, 260, 70, "Clarification", ["Checkpoint · response · resume"], fill="#FFF7ED", stroke="#FDBA74", accent="#EA580C"))
    arrows += [arrow(585,435,585,510, dashed=True, label="execution error"), arrow(455,555,300,435, dashed=True, label="retry"), arrow(935,435,935,510, dashed=True, label="disagreement"), arrow(1065,555,1285,435, dashed=True, label="review"), arrow(1280,210,1280,240, dashed=True, label="clarify")]

    # Approved mutation path.
    cards.append(card(190, 735, 280, 100, "Impact preview", ["Proposed change and scope", "no mutation executed"], fill="#FAF5FF", stroke="#D8B4FE", accent="#7E22CE"))
    cards.append(card(580, 735, 280, 100, "Explicit approval", ["Authorized reviewer decision", "approval bound to request"], fill="#FAF5FF", stroke="#D8B4FE", accent="#7E22CE"))
    cards.append(card(970, 735, 280, 100, "Transactional write", ["Idempotency · stale-worker guard", "commit receipt or rollback"], fill="#FAF5FF", stroke="#D8B4FE", accent="#7E22CE"))
    arrows += [arrow(330,435,330,735, dashed=True, label="mutation request"), arrow(470,785,580,785), arrow(860,785,970,785)]

    # Offline evaluation path.
    cards.append(card(70, 1020, 265, 110, "Official Mini-Dev input", ["500 questions · evidence", "schema · SQLite database"], fill="#F0FDF4", stroke="#86EFAC", accent="#15803D"))
    cards.append(card(415, 1020, 265, 110, "SQL-Agent inference", ["Same guarded read graph", "gold SQL remains isolated"], fill="#F0FDF4", stroke="#86EFAC", accent="#15803D"))
    cards.append(card(760, 1020, 265, 110, "Execution scorer", ["Candidate result vs gold result", "gold used only after inference"], fill="#F0FDF4", stroke="#86EFAC", accent="#15803D"))
    cards.append(card(1105, 1020, 265, 110, "Reported evidence", ["accuracy · paired gains/losses", "tokens/correct · p95 latency"], fill="#F0FDF4", stroke="#86EFAC", accent="#15803D"))
    arrows += [arrow(335,1075,415,1075), arrow(680,1075,760,1075), arrow(1025,1075,1105,1075)]

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1220" viewBox="0 0 1440 1220" role="img" aria-labelledby="title desc">
<title id="title">SQL-Agent architecture</title>
<desc id="desc">Production-oriented LangGraph SQL agent showing durable request handling, grounding, policy-gated reads, bounded execution and semantic repair, advisory verification, human review, approved transactional writes, and isolated BIRD Mini-Dev evaluation.</desc>
<defs>
  <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#64748B"/></marker>
  <style>
    .title {{ font: 700 34px Arial, sans-serif; fill: #0F172A; }}
    .subtitle {{ font: 16px Arial, sans-serif; fill: #475569; }}
    .lane {{ font: 700 18px Arial, sans-serif; letter-spacing: 1px; fill: #334155; }}
    .card-title {{ font: 700 17px Arial, sans-serif; fill: #0F172A; }}
    .card-text {{ font: 14px Arial, sans-serif; fill: #475569; }}
    .arrow {{ fill: none; stroke: #64748B; stroke-width: 2.2; marker-end: url(#arrowhead); }}
    .arrow-label {{ font: 12px Arial, sans-serif; fill: #64748B; paint-order: stroke; stroke: #FFFFFF; stroke-width: 4px; }}
  </style>
</defs>
<rect width="1440" height="1220" fill="#FFFFFF"/>
<text x="70" y="55" class="title">SQL-Agent system architecture</text>
<text x="70" y="84" class="subtitle">Grounded planning, programmatic execution controls, bounded recovery, and evaluation with isolated gold answers</text>
<text x="70" y="108" class="lane">ONLINE READ WORKFLOW</text>
<rect x="45" y="95" width="1350" height="545" rx="20" fill="none" stroke="#DBEAFE" stroke-width="2"/>
<text x="70" y="700" class="lane">HUMAN-APPROVED MUTATION WORKFLOW</text>
<rect x="45" y="675" width="1350" height="200" rx="20" fill="none" stroke="#E9D5FF" stroke-width="2"/>
<text x="70" y="985" class="lane">OFFLINE BIRD MINI-DEV EVALUATION</text>
<rect x="45" y="960" width="1350" height="210" rx="20" fill="none" stroke="#BBF7D0" stroke-width="2"/>
{''.join(arrows)}
{''.join(cards)}
<text x="70" y="1197" class="subtitle">Dashed arrows denote interrupts, bounded retries, or branch transitions. The Verifier supplies evidence; it does not certify correctness.</text>
</svg>'''
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
