"""Render the repository's native SVG architecture, without external fonts or images."""
from html import escape
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/'docs/assets/workflow.svg'
parts=['''<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1190" viewBox="0 0 1440 1190" role="img" aria-labelledby="title desc">
<title id="title">SQL-Agent system architecture</title>
<desc id="desc">Browser and MCP requests enter an authenticated API and durable workers. A checkpointed LangGraph workflow retrieves scoped knowledge, selects authorized schema and plans SQL. Reads execute within database limits and receive advisory independent verification before human review. Changes require an impact preview and administrator approval before transactional execution. Clarification pauses and resumes the workflow. Durable state, token accounting and offline evaluation support the system. Reference answers do not enter runtime.</desc>
<defs>
 <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M 1 1 L 9 5 L 1 9 Z" fill="#64748b"/></marker>
 <marker id="amber-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M 1 1 L 9 5 L 1 9 Z" fill="#b7791f"/></marker>
</defs>
<style>
 text {font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;fill:#172b4d}
 .title {font-size:40px;font-weight:750;letter-spacing:-1px}
 .section {font-size:24px;font-weight:700;letter-spacing:-.25px}
 .body {font-size:20px;fill:#52627a}
 .eyebrow {font-size:15px;font-weight:700;letter-spacing:1.8px;fill:#52627a}
 .card-title {font-size:24px;font-weight:650;letter-spacing:-.35px}
 .edge {fill:none;stroke:#64748b;stroke-width:2.3;stroke-linecap:round;stroke-linejoin:round;marker-end:url(#arrow)}
 .change {fill:none;stroke:#b7791f;stroke-width:2.3;stroke-linecap:round;stroke-linejoin:round;marker-end:url(#amber-arrow)}
</style>
<rect width="1440" height="1190" rx="24" fill="#f8fafc"/>
''']

def rect(x,y,w,h,fill='#ffffff',stroke='#d9e2ed',radius=14):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')

def text(x,y,value,cls='body',fill=None):
    color=f' style="fill:{fill}"' if fill else ''
    parts.append(f'<text x="{x}" y="{y}" class="{cls}"{color}>{escape(value)}</text>')

def line(d,kind='edge',dashed=False):
    dash=' stroke-dasharray="6 6"' if dashed else ''
    parts.append(f'<path d="{d}" class="{kind}"{dash}/>')

def card(x,y,w,h,title,lines,accent='#3b82f6',fill='#ffffff'):
    rect(x,y,w,h,fill=fill)
    parts.append(f'<rect x="{x}" y="{y+19}" width="4" height="28" rx="2" fill="{accent}"/>')
    text(x+22,y+39,title,'card-title')
    for i,value in enumerate(lines):text(x+22,y+70+i*27,value)

text(40,66,'SQL-Agent','title')
text(267,65,'System architecture','section','#52627a')
text(40,104,'A checkpointed workflow for SQL generation, bounded execution and explicit review.')
text(40,147,'01   REQUEST & DELIVERY','eyebrow')
card(40,164,280,106,'Browser / MCP',['Question, SQL, review'],accent='#64748b')
card(365,164,445,106,'FastAPI request boundary',['Identity · source policy · idempotency'],accent='#64748b')
card(855,164,545,106,'Durable queue + workers',['Persist jobs · claim leases · recover work'],accent='#64748b')
line('M 320 216 H 365');line('M 810 216 H 855')
line('M 1128 270 V 307')
rect(40,307,1360,650,fill='#eff5ff',stroke='#c4d5f0',radius=20)
text(66,344,'02   LANGGRAPH ORCHESTRATION','eyebrow','#315d98')
text(827,344,'Durable checkpoints · resumable interrupts','body','#315d98')
card(70,373,280,104,'Scoped knowledge',['Business definitions'],accent='#3b82f6')
card(410,373,600,104,'Retrieval',['Chunking · BM25 · optional vectors + reranking'],accent='#3b82f6')
card(1070,373,300,104,'Schema linking',['Authorized tables · budget'],accent='#3b82f6')
line('M 350 425 H 410');line('M 1010 425 H 1070')
line('M 1220 477 V 518 H 210 V 557')
rect(492,494,413,34,fill='#eff5ff',stroke='#eff5ff',radius=0)
text(505,518,'Bounded context + current schema','body','#315d98')
card(70,557,280,136,'Planner',['SQL or clarification','Classify read / change'],accent='#3b82f6')
card(410,557,280,136,'Read execution',['Read-only database access','Query limits · ≤3 attempts'],accent='#0f766e',fill='#f5fbf9')
card(750,557,280,136,'Independent Verifier',['Generate + execute SQL','Compare rows · advisory'],accent='#0f766e',fill='#f5fbf9')
card(1090,557,280,136,'Human review',['Candidate + SQL + trace','Required for general SQL'],accent='#0f766e',fill='#f5fbf9')
line('M 350 605 H 410');line('M 690 605 H 750');line('M 1030 605 H 1090')
text(356,587,'READ','eyebrow','#0f766e')
line('M 350 658 H 380 V 828 H 410','change')
text(418,760,'CHANGE · EXPLICIT APPROVAL REQUIRED','eyebrow','#96601b')
card(410,778,280,136,'Impact preview',['Rows + exact change hash','Persist exact proposal'],accent='#b7791f',fill='#fffbf3')
card(750,778,280,136,'Admin approval',['Approve matching proposal','Reject → no write'],accent='#b7791f',fill='#fffbf3')
card(1090,778,280,136,'Transaction executor',['Optional isolated gateway','Commit + atomic receipt'],accent='#b7791f',fill='#fffbf3')
line('M 690 828 H 750','change');line('M 1030 828 H 1090','change')
card(70,778,280,136,'Clarification',['Ask owner · persist answer','Resume checkpointed flow'],accent='#64748b')
line('M 210 693 V 778',dashed=True)
text(225,738,'PAUSE','eyebrow')
text(66,940,'Explicit SQL skips generation. Registered contracted tasks use a separate analysis node.','body','#52627a')
text(40,997,'03   STATE, MEASUREMENT & EVALUATION','eyebrow')
card(40,1017,430,120,'Data & durable state',['SQLite / PostgreSQL sources','Jobs · checkpoints · receipts'],accent='#64748b')
card(505,1017,430,120,'Token accounting',['Planner + Verifier + retries','Input / output · missing = unknown'],accent='#64748b')
card(970,1017,430,120,'Offline evaluation',['Oracle · accuracy · false accepts','p95 · tokens per correct task'],accent='#64748b')
text(40,1171,'Single-host architecture. Offline reference answers never enter the Agent runtime.','body')
parts.append('</svg>')
OUT.write_text('\n'.join(parts)+'\n')
print(OUT)
