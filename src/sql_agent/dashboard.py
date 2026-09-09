def render_dashboard() -> str:
    import os
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SQL-Agent | Analysis & Review</title>
<style>
:root{font:15px system-ui;color:#152f3e;background:#f1f5f7}body{max-width:1200px;margin:2rem auto;padding:0 1rem}h1{margin-bottom:.3rem}h2{font-size:1.1rem}p{line-height:1.5}.grid{display:grid;grid-template-columns:320px 1fr;gap:1.3rem}.card{background:white;border:1px solid #dbe4e9;border-radius:12px;padding:1.2rem;margin:1rem 0}label{display:block;margin:.8rem 0 .3rem}input,select,textarea,button{font:inherit;padding:.65rem;box-sizing:border-box;width:100%;border:1px solid #c5d3db;border-radius:6px}button{cursor:pointer;margin-top:.7rem;background:#155766;color:white}button:disabled{opacity:.5;cursor:default}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto;font-size:.85rem}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #e5ecef;padding:.5rem;vertical-align:top;overflow-wrap:anywhere}.muted{color:#617680}.actions{display:flex;gap:.6rem}.alert{border-left:4px solid #c27822;padding:.7rem;background:#fff7e8}.scroll{overflow:auto}@media(max-width:800px){.grid{display:block}}
[hidden]{display:none!important}#login-panel{max-width:480px}#session-panel{display:flex;align-items:center;justify-content:space-between;gap:1rem}#logout{width:auto;margin:0}
#feedback{position:sticky;top:8px;z-index:2;border:1px solid #b8d5dc;padding:.8rem;background:#eef8fb;border-radius:8px}#feedback[data-error="true"]{background:#fff0ef;border-color:#c25d53}button[aria-busy="true"]{cursor:wait}
#definitions th:first-child{width:18%}#definitions th:last-child{width:21%}#health th:first-child{width:22%}
</style><h1>SQL-Agent</h1><p class="muted">Business definitions, source health, and reviewable SQL analysis.</p>
<p><a href="/database">Database console: query and approved changes</a></p>
<p id="feedback" role="status" aria-live="polite">Sign in to begin.</p>
<section id="login-panel" class="card"><h2>Sign in</h2><p>Use your configured access key to sign in to this workspace.</p><label>Access key<input id="key" type="password" autocomplete="off" placeholder="Enter your access key"></label><button id="login">Sign in</button><div id="demo-access"></div></section>
<section id="session-panel" class="card" hidden><span id="identity"></span><button id="logout">Sign out</button></section><noscript>This application requires JavaScript. Enable it and reload this page.</noscript><div id="workspace" hidden><div class="grid"><aside><div class="card"><h2>Analysis request</h2>
<button id="load">Load registered tasks</button>
<label>Task<select id="task"><option value="">Load tasks first</option></select></label>
<div id="examples" hidden><label>Example question<select id="example-question"></select></label></div><label>Question<textarea id="question" rows="5" aria-describedby="question-help" placeholder="Type your analysis question here"></textarea></label><p id="question-help" class="muted">Load a task, then type your question.</p><button id="custom-question" hidden>Switch to an editable task</button>
<label>Initial SQL / corrected SQL (optional)<textarea id="sql" rows="4"></textarea></label>
<button id="submit" disabled>Submit analysis</button><button id="refresh">Refresh current job</button>
<p class="muted">A corrected question or SQL creates a new job. Original evidence remains in the previous job.</p></div>
<div class="card"><h2>Open existing job</h2><input id="existing" placeholder="Job ID"><button id="open">Open job</button></div></aside>
<main><div class="card"><h2 id="status">Ready</h2><p id="progress" class="muted">Submit an analysis or open an existing job.</p><p id="jobid" class="muted"></p><p id="release" class="alert">Generic queries require review. Model agreement is not proof of correctness.</p></div>
<div class="card"><h2>Candidate result</h2><div id="output" class="scroll"></div><h2>Executed / proposed SQL</h2><pre id="queries"></pre></div>
<div class="card"><h2>Run performance</h2><div id="performance">Submit an analysis to see measured runtime and model usage.</div><p id="cost" class="muted"></p></div>
<details class="card"><summary>Business definitions</summary><div id="definitions">No task result loaded.</div></details>
<details class="card"><summary>Source health</summary><div id="health">No checks loaded.</div></details>
<div class="card"><h2>Human review</h2><p class="muted">Record your decision and rationale. Approval records a human decision; it does not turn model agreement into a correctness guarantee.</p><p id="review-help" class="muted">Review becomes available when a job needs review.</p><textarea id="notes" rows="3" placeholder="Review rationale, issues found, or corrections required"></textarea><div class="actions"><button id="approve" disabled>Approve review</button><button id="reject" disabled>Reject / request correction</button></div></div>
<details class="card"><summary>Full evidence and audit history</summary><pre id="result"></pre><pre id="events"></pre></details></main></div></div>
<script>
let jobId;const el=id=>document.getElementById(id);let tasks=[];
const submittedAt=new Map(),observedLatency=new Map();let authEpoch=0;let editingTaskId=null;const taskDrafts=new Map();
let latestJob=null,pollTimer=null,selection=0,refreshSequence=0,pendingSubmission=null;
function feedback(message,isError=false){text('feedback',message);el('feedback').dataset.error=String(isError);}
function requestKey(){const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');}
async function call(path,options={}){
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),15000);
 try{
  const r=await fetch(path,{...options,signal:controller.signal,headers:{'content-type':'application/json',...options.headers}});
  const data=await r.json();
  if(!r.ok){if(r.status===401&&!path.startsWith('/v1/auth/'))clearLocalSession();const detail=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data);const error=Error('Request failed ('+r.status+'): '+detail);error.status=r.status;throw error;}
  return data;
 }catch(e){if(e.name==='AbortError')throw Error('Server response timed out. Try again; a repeated submission reuses the same request key.');throw e;}
 finally{clearTimeout(timer);}
}
function text(id,value){el(id).textContent=value;}
function table(id,headers,rows){const target=el(id);target.replaceChildren();const t=document.createElement('table');const head=document.createElement('tr');headers.forEach(h=>{const c=document.createElement('th');c.textContent=h;head.append(c)});t.append(head);rows.forEach(row=>{const tr=document.createElement('tr');row.forEach(v=>{const td=document.createElement('td');td.textContent=v===null?'NULL':String(v);tr.append(td)});t.append(tr)});target.append(t);}
function show(job){if(!['queued','running'].includes(job.status)&&submittedAt.has(job.job_id)&&!observedLatency.has(job.job_id))observedLatency.set(job.job_id,Math.round(performance.now()-submittedAt.get(job.job_id)));if(el('jobid').textContent!==job.job_id){el('notes').value='';text('events','');}const r=job.result||{};text('status',job.status);text('jobid',job.job_id);text('result',JSON.stringify(job,null,2));text('release',r.release?('Automatic release: '+r.release.approved+' · '+r.release.reason+' · Check: '+(r.validation_scope==='registered_business_query_comparison'?'Registered business reference matched':r.semantic_review?.status||r.validation_scope)):'Waiting for execution.');
const m=r.telemetry;if(m){table('performance',['Measure','Observed value'],[['Observed submit-to-result (this page)',observedLatency.has(job.job_id)?observedLatency.get(job.job_id)+' ms':'Not measured on this page'],['Processing time (excludes queue)',m.pipeline_elapsed_ms+' ms'],['Model requests / retries',m.calls+' / '+m.retries],['Failed model requests',m.failed_calls],['Input / output tokens observed',m.prompt_tokens_observed+' / '+m.completion_tokens_observed],['Requests missing full token usage',m.calls_without_complete_usage]]);text('cost',m.token_cost?.complete?'Token cost: '+m.token_cost.total_tokens+' input + output tokens, including recorded retries.':'Token cost incomplete: '+(m.prompt_tokens_observed+m.completion_tokens_observed)+' tokens observed; total unknown.');}else{text('performance','No runtime measurements available for this job.');text('cost','');}
const defs=r.business_context?.definitions||[];if(defs.length)table('definitions',['Metric','Definition','Source / version'],defs.map(d=>[d.metric_id,d.definition,d.source+' / '+d.version]));else text('definitions',['queued','running'].includes(job.status)?'Business definitions will appear when execution finishes.':'No matching registered definitions.');
const h=r.source_health;if(h?.checks?.length)table('health',['Check','Status','Observation','Policy'],h.checks.map(c=>[c.check_id,c.status+' ('+c.severity+')',c.status==='unknown'?c.error:JSON.stringify(c.value),c.policy_reason+'; maximum '+c.maximum]));else text('health',['queued','running'].includes(job.status)?'Source-check results are pending.':'No source checks configured. This does not mean data quality passed.');
const out=r.output||r.candidate_output;if(out)table('output',out.columns,out.rows.slice(0,100));else text('output','No candidate result.');
text('queries',(r.agent_trajectory||[]).filter(t=>t.step==='propose').map(t=>t.proposal?.arguments?.sql||t.proposal?.action).join('\\n\\n'));text('progress',job.status==='queued'?'Queued — waiting for a worker. This page updates automatically.':job.status==='running'?'Running — the model is generating and checking SQL. This can take over a minute; this page updates automatically.':job.status==='needs_review'?'Finished — inspect the result and record a review decision.':'Job finished. You can inspect its evidence or submit another analysis.');const reviewable=job.status==='needs_review';el('approve').disabled=!reviewable||!out;el('reject').disabled=!reviewable;text('review-help',reviewable?(out?'Enter a rationale, then approve or reject this result.':'No candidate result to approve. You can reject with an explanation.'):'Review buttons become available only for a job that needs review.');
}
function pending(){return latestJob && ['queued','running'].includes(latestJob.status);}
function schedulePoll(){
 clearTimeout(pollTimer);if(!pending())return;
 const expected=selection;
 pollTimer=setTimeout(async()=>{if(selection!==expected)return;try{await refresh();}catch(e){if(selection===expected)feedback('Could not update the job: '+e.message+' Retrying automatically.',true);}},1500);
}
function selectJob(job){clearTimeout(pollTimer);selection++;jobId=job.job_id;latestJob=job;show(job);schedulePoll();}
async function refresh(){
 if(!jobId)throw Error('Submit an analysis or open a job before refreshing.');
 const requested=jobId,version=selection,sequence=++refreshSequence;clearTimeout(pollTimer);
 const current=()=>selection===version && jobId===requested && sequence===refreshSequence;
 try{
  const job=await call('/v1/jobs/'+encodeURIComponent(requested));if(!current())return;
  latestJob=job;show(job);
  const events=await call('/v1/jobs/'+encodeURIComponent(requested)+'/events');
  if(current())text('events',JSON.stringify(events,null,2));
 }finally{if(current())schedulePoll();}
}
function act(label,fn){return async(event)=>{
 const button=event.currentTarget;if(button.dataset.busy==='true')return;
 const original=button.textContent;button.dataset.busy='true';button.disabled=true;button.setAttribute('aria-busy','true');button.textContent=label+'…';feedback(label+'…');
 try{await fn();}catch(e){feedback(e.message||'Request failed. Check the server connection and try again.',true);}
 finally{button.dataset.busy='false';button.removeAttribute('aria-busy');button.textContent=original;
  if(button.id==='submit')button.disabled=!tasks.length;
  else if(button.id==='approve'||button.id==='reject'){const out=latestJob?.result?.output||latestJob?.result?.candidate_output;button.disabled=latestJob?.status!=='needs_review'||(button.id==='approve'&&!out);}
  else button.disabled=false;
 }
};}
function fixedQuestion(task){return Boolean(task?.contract?.specification?.verification_sql);}
function saveDraft(){if(editingTaskId)taskDrafts.set(editingTaskId,{question:el('question').value,sql:el('sql').value});}
function editSelectedTask(){
 saveDraft();const task=tasks.find(t=>t.task_id===el('task').value);editingTaskId=task?.task_id||null;
 if(!task){el('question').value='';el('sql').value='';el('question').readOnly=false;el('custom-question').hidden=true;return;}
 const draft=taskDrafts.get(task.task_id),locked=fixedQuestion(task);
 el('question').value=locked?task.question:(draft?.question??task.question);el('sql').value=draft?.sql??'';el('question').readOnly=locked;
 const columns=task.contract?.specification?.columns||[];
 el('examples').hidden=!(task.example_questions?.length);el('example-question').replaceChildren();
 const placeholder=document.createElement('option');placeholder.value='';placeholder.textContent='Choose an example, or type your own question';el('example-question').append(placeholder);
 for(const question of task.example_questions||[]){const o=document.createElement('option');o.value=question;o.textContent=question;el('example-question').append(o);}
 el('example-question').onchange=()=>{if(el('example-question').value){el('question').value=el('example-question').value;el('question').focus();}};
 text('question-help',task.contract?.specification?.dynamic_columns?'Ask for a total, a list, or a grouped summary from this data source. Results have flexible columns and remain read-only and reviewable.':locked?'Fixed metric: this question is locked to its registered check. Select an editable task to write your own question.':'Editable question — type here. This task uses its registered data source and output contract'+(columns.length?' ('+columns.join(', ')+')':'')+'.');
 el('custom-question').hidden=!locked||!tasks.some(t=>!fixedQuestion(t));
}
function signedIn(principal){
 el('login-panel').hidden=false;el('session-panel').hidden=true;el('workspace').hidden=true;
 if(principal){el('login-panel').hidden=true;el('session-panel').hidden=false;el('workspace').hidden=false;text('identity','Signed in as '+principal.name+' · '+principal.role);el('key').value='';}
}
async function loginWithKey(){
 authEpoch++;const key=el('key').value.trim();if(!key)throw Error('Enter your access key, or use the local demo sign-in button.');
 const principal=await call('/v1/auth/login',{method:'POST',body:JSON.stringify({api_key:key})});
 signedIn(principal);feedback('Signed in as '+principal.name+'.');el('load').click();
}
el('login').onclick=act('Signing in',loginWithKey);
el('key').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();el('login').click();}});
function clearLocalSession(){
 authEpoch++;clearTimeout(pollTimer);selection++;jobId=null;latestJob=null;pendingSubmission=null;tasks=[];editingTaskId=null;taskDrafts.clear();
 for(const id of ['question','sql','existing','notes','key'])el(id).value='';
 for(const id of ['jobid','result','events','output','queries','definitions','health','performance','cost'])text(id,'');
 text('status','Ready');signedIn(null);
}
el('logout').onclick=act('Signing out',async()=>{
 await call('/v1/auth/logout',{method:'POST'});clearLocalSession();feedback('Signed out. Sign in to use the workspace again.');
});
async function restoreSession(){
 const epoch=authEpoch;
 try{const principal=await call('/v1/auth/session');if(epoch!==authEpoch)return;signedIn(principal);el('load').click();}
 catch(e){if(epoch!==authEpoch)return;signedIn(null);if(e.status!==401)feedback('Cannot reach the sign-in service: '+e.message,true);}
}
el('load').onclick=act('Loading tasks',async()=>{
 const previous=el('task').value;tasks=(await call('/v1/tasks')).tasks;el('task').replaceChildren();
 for(const t of tasks){const o=document.createElement('option');o.value=t.task_id;o.textContent=t.task_id+(fixedQuestion(t)?' — fixed metric':' — editable');el('task').append(o);}
 const selected=tasks.find(t=>t.task_id===previous)||tasks.find(t=>t.contract?.specification?.dynamic_columns)||tasks.find(t=>!fixedQuestion(t))||tasks[0];
 if(selected)el('task').value=selected.task_id;
 el('submit').disabled=!tasks.length;editSelectedTask();feedback(tasks.length?'Loaded '+tasks.length+' task'+(tasks.length===1?'':'s')+'. '+(fixedQuestion(selected)?'Fixed metric selected; see the question instructions.':'You can type your question and submit an analysis.'):'No registered tasks are available.');
});
el('task').onchange=editSelectedTask;
el('custom-question').onclick=()=>{
 const task=tasks.find(t=>t.contract?.specification?.dynamic_columns)||tasks.find(t=>!fixedQuestion(t));if(!task)return;
 el('task').value=task.task_id;editSelectedTask();el('question').focus();feedback('Editable task selected. Type your question in the Question box.');
};
el('submit').onclick=act('Submitting analysis',async()=>{
 if(!tasks.length)throw Error('Load registered tasks first.');
 const clickedAt=performance.now();const body=JSON.stringify({task_id:el('task').value,question:el('question').value,initial_sql:el('sql').value});
 if(!pendingSubmission||pendingSubmission.body!==body)pendingSubmission={body,key:requestKey()};
 const data=await call('/v1/jobs',{method:'POST',headers:{'idempotency-key':pendingSubmission.key},body});pendingSubmission=null;
 submittedAt.set(data.job.job_id,clickedAt);selectJob(data.job);feedback('Submitted job '+jobId+'. Progress updates automatically; you do not need to submit again.');
});
el('refresh').onclick=act('Refreshing job',async()=>{await refresh();feedback('Job refreshed. Current status: '+latestJob.status+'.');});
el('open').onclick=act('Opening job',async()=>{
 const requested=el('existing').value.trim();if(!requested)throw Error('Enter a job ID before opening it.');
 const job=await call('/v1/jobs/'+encodeURIComponent(requested));selectJob(job);await refresh();feedback('Opened job '+requested+'.'+(pending()?' Progress updates automatically.':''));
});
for(const decision of ['approve','reject'])el(decision).onclick=act(decision==='approve'?'Approving review':'Rejecting review',async()=>{
 if(!el('notes').value.trim())throw Error('Please record a review rationale.');
 const requested=jobId;
 await call('/v1/jobs/'+encodeURIComponent(requested)+'/review',{method:'POST',body:JSON.stringify({decision,notes:el('notes').value})});
 if(jobId===requested)await refresh();feedback('Review '+(decision==='approve'?'approved':'rejected')+' for job '+requested+'.');
});
restoreSession();
</script></html>'''

    if os.environ.get('SQL_AGENT_LOCAL_DEMO') == '1':
        page = page.replace('<div class="grid">', '<p><a href="/benchmark">Evaluation: results, methods and runtime costs</a></p><div class="grid">')
        page = page.replace('<div id="demo-access"></div>', '<div id="demo-access"><p class="muted">Local demo: sign in below without registering. This access is for the local demonstration only.</p><button id="demo-login">Enter local demo</button></div>')
        page = page.replace('<h1>SQL-Agent</h1>', '<h1>SQL-Agent · Local demo</h1><p class="alert">Synthetic commerce data · local-only demo credentials · real Ollama inference.</p>')
        page = page.replace('</script>', "el('demo-login').onclick=act('Signing in to local demo',async()=>{el('key').value='123';await loginWithKey();});</script>")
    return page
