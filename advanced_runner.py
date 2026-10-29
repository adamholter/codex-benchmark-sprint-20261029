"""Predeclared harder DiscoveryWorld subscription trials, isolated two-process pool."""
import argparse, collections, fcntl, importlib.util, json, os, signal, subprocess, sys, time, traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('advanced_interactive',ROOT/'interactive_runner.py')
i=importlib.util.module_from_spec(spec);spec.loader.exec_module(i)
EXPANDED=os.environ.get('DISCOVERYWORLD_EXPANDED')=='1'
AREA=ROOT/('discoveryworld/expanded' if EXPANDED else 'discoveryworld/advanced');i.AREA=AREA/'results';i.TRIAL_SECONDS=1800;i.TOOL_CALL_LIMIT=3000
DEADLINE=1793301000
EXTERNAL=Path('/private/tmp/codex-sprint-runtime-20261029')
save=i.save
_original_guard=i.check_guard
def guarded(deadline):
    AREA.mkdir(parents=True,exist_ok=True)
    with (AREA/'guard.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for attempt in range(3):
            if time.time()>=deadline:return 'deadline'
            try:
                reason=_original_guard(deadline)
                if reason:save(AREA/'guard-stop.json',dict(reason=reason,observed_at=time.time(),pid=os.getpid()))
                return reason
            except Exception:
                if attempt==2:raise
                time.sleep(1)
i.check_guard=guarded

def shared_stop_reason():
    path=AREA/'guard-stop.json';controller=AREA/'controller-process.json'
    if not path.exists() or not controller.exists():return None
    stop=json.loads(path.read_text());started=json.loads(controller.read_text())['started_at']
    return stop['reason'] if stop['observed_at']>=started else None

def cases():
    scenarios=json.loads((ROOT/'discoveryworld/scenarios.json').read_text())
    selected=[(s,0) for s in scenarios[4:]]+[(s,seed) for seed in range(1,5) for s in scenarios] if EXPANDED else [(s,0) for s in scenarios[:4]]
    return [dict(s,difficulty=d,seed=seed,action_budget=1000,id=s['scenario'].lower().replace(' ','-')+'-'+d.lower()+'-seed'+str(seed),benchmark='discoveryworld_advanced',category=s['scenario']+'/'+d) for s,seed in selected for d in ('Normal','Challenge')]
def plan():
    return [(m,c) for n,c in enumerate(cases()) for m in i.MODELS[n%4:]+i.MODELS[:n%4]]
def status_path(m,c):return i.AREA/i.trial_key(m,c)/'status.json'
def placeholder(m,c,status,reason):
    save(status_path(m,c),dict(model=m,benchmark=c['benchmark'],id=c['id'],category=c['category'],effort='high',service_tier='default',status=status,errors=[reason],seconds=0,tool_calls=0,score=None,finished_at=time.time()))
def validate_case(c):
    s=i.make_session(c);public=json.dumps(s.call('discoveryworld_observe',{}))+s.initial_prompt()
    for key in ('official_scorecards','criticalHypotheses','criticalQuestions','scoreNormalized'):
        assert key not in public,key
    score=s.score();assert 0<=score['score']<=1 and score['action_budget']==1000
    assert 'official_scorecards' in score and score['knowledge_score'] is None
    assert s.call('score',{})=={'error':'unknown_tool'}
    return dict(id=c['id'],status='loaded',score_boundary_verified=True,score_type=score['score_type'])
def normalize_compaction(path):
    """The shared helper flags native context compaction as an unknown tool item."""
    x=json.loads(path.read_text())
    if x.get('status')!='protocol_violation' or x.get('errors') or not x.get('tool_calls') or x.get('turn',{}).get('status')!='completed':return
    allowed={'reasoning','plan','userMessage','dynamicToolCall','agentMessage','contextCompaction'}
    compacted=False
    events=path.with_name('events.jsonl')
    if not events.exists():return
    for line in events.read_text().splitlines():
        try:d=json.loads(line)
        except ValueError:continue
        params=d.get('params',{})
        if 'id' in d and 'method' in d and d['method']!='item/tool/call':return
        if 'id' in d and 'method' in d and params.get('tool') not in {'discoveryworld_act','discoveryworld_observe'}:return
        if d.get('method')=='item/completed':
            kind=params.get('item',{}).get('type')
            if kind not in allowed:return
            compacted=compacted or kind=='contextCompaction'
    if compacted and path.with_name('response.txt').read_text():
        x.update(status='complete',raw_helper_status='protocol_violation',status_correction='Native contextCompaction is not an agent tool or protocol violation; audited event stream contains only permitted tools and items.')
        save(path,x)

def report(state,active,reason=None):
    import reporting
    rows=[]
    for m,c in plan():
        p=status_path(m,c)
        if p.exists():
            normalize_compaction(p)
            rows.append(json.loads(p.read_text()))
    counts=dict(collections.Counter(x['status'] for x in rows))
    data=dict(pid=os.getpid(),state=state,deadline=DEADLINE,workers=2,planned=len(plan()),finished=sum(x['status']!='running' for x in rows),status_counts=counts,active=[dict(pid=p.pid,model=m,id=c['id']) for p,m,c in active],stop_reason=reason,updated_at=time.time())
    save(AREA/'launcher.json',data)
    reporting.report(AREA,'results',i.MODELS,plan())
    lines=['# Advanced DiscoveryWorld results','',f'State: {state}. Planned: {len(plan())}. Statuses: {counts}.','', ('Seven runnable official scenarios, Normal and Challenge, seeds 0 through 4, excluding the eight first-four-theme seed-0 cases already completed. Rocket Science excluded. ' if EXPANDED else 'First four official scenarios, Normal and Challenge, seed 0. ')+'1000 action attempts per case. Official procedural progress and completion only. No external knowledge judge. Compare matched completed cases.','', '| Model | Case | Status | Procedure | Success | Actions |','|---|---|---|---|---|---|']
    for x in rows:
        s=x.get('score') or {};lines.append(f"| {x['model']} | {x['id']} | {x['status']} | {s.get('score')} | {s.get('correct')} | {s.get('actions')} |")
    if reason:lines+=['',f'Stop reason: {reason}']
    (AREA/'RESULTS.md').write_text('\n'.join(lines)+'\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--child',type=int);ap.add_argument('--validate',type=int);a=ap.parse_args()
    if a.validate is not None:
        try:save(AREA/'validation'/f'{a.validate}.json',validate_case(cases()[a.validate]))
        except Exception:save(AREA/'validation'/f'{a.validate}.json',dict(id=cases()[a.validate]['id'],status='not_run',reason=traceback.format_exc()));sys.exit(1)
        return
    if a.child is not None:
        for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:i.STOP.set())
        m,c=plan()[a.child]
        try:
            i.trial(m,c,EXTERNAL,DEADLINE)
            normalize_compaction(status_path(m,c))
        except Exception:placeholder(m,c,'infrastructure_error',traceback.format_exc())
        return
    AREA.mkdir(parents=True,exist_ok=True)
    lock=(AREA/'controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    save(AREA/'controller-process.json',dict(pid=os.getpid(),pgid=os.getpgrp(),started_at=time.time(),deadline=DEADLINE,command=[sys.executable,str(Path(__file__).resolve())],expanded=EXPANDED))
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:i.STOP.set())
    auth=json.loads((Path.home()/'.codex/auth.json').read_text());assert auth.get('auth_mode')=='chatgpt' and not auth.get('OPENAI_API_KEY')
    save(AREA/'protocol.json',dict(benchmark='discoveryworld_advanced',models=i.MODELS,effort='high',service_tier='default',cases=cases(),planned=len(plan()),concurrency=2,action_budget=1000,max_trial_seconds=1800,max_tool_calls=3000,deadline=DEADLINE,baseline=i.BASE,route='OAuth ChatGPT subscription, no API',knowledge_judge=False,metrics='Official procedural progress and completion; full scorecards evaluator-only',queue='Normal/Challenge interleaved, four models per case, model ordering rotated',isolation='Independent simulator process and fresh isolated app-server per trial; fixed interactive_runner command bridge',terminal_failures_retried=False))
    save(AREA/'plan.json',[dict(index=n,model=m,case=c) for n,(m,c) in enumerate(plan())])
    report('validating',[])
    # Validate every simulator in a fresh process before any model inference.
    invalid={}
    validation_stop=None
    for n,c in enumerate(cases()):
        if time.time()>=DEADLINE or i.STOP.is_set():
            validation_stop='deadline' if time.time()>=DEADLINE else 'global stop'
            break
        try:
            p=subprocess.run([sys.executable,__file__,'--validate',str(n)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=min(180,max(1,DEADLINE-time.time())))
            v=json.loads((AREA/'validation'/f'{n}.json').read_text())
            if p.returncode:invalid[c['id']]=v.get('reason',p.stderr)
        except Exception:
            invalid[c['id']]=traceback.format_exc()
            save(AREA/'validation'/f'{n}.json',dict(id=c['id'],status='not_run',reason=invalid[c['id']]))
    save(AREA/'validation.json',dict(cases=[json.loads(p.read_text()) for p in sorted((AREA/'validation').glob('*.json'))],invalid=invalid))
    for m,c in plan():
        if c['id'] in invalid:placeholder(m,c,'not_run','source compatibility: '+invalid[c['id']])
    pending=collections.deque()
    for n,(m,c) in enumerate(plan()):
        path=status_path(m,c)
        if not path.exists():pending.append((n,m,c));continue
        prior=json.loads(path.read_text())
        if prior['status']!='not_run' and i.resumable(prior['status']):pending.append((n,m,c))
        elif prior['status']=='not_run' and any('guard unavailable:' in e for e in prior.get('errors',[])):
            archive=path.parent/'attempts'/str(time.time_ns());archive.mkdir(parents=True)
            path.rename(archive/'status.json');pending.append((n,m,c))
    active=[];reason=validation_stop;last_guard=0;last_report=0
    try:
        while pending or active:
            now=time.time()
            reason=reason or shared_stop_reason()
            if now>=DEADLINE:reason='deadline'
            if i.STOP.is_set():reason=reason or 'global stop'
            if not reason and now-last_guard>=10:
                try:reason=i.check_guard(DEADLINE)
                except Exception as exc:reason='guard unavailable: '+str(exc)
                last_guard=time.time()
            if reason:
                for p,m,c in active:
                    if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
                for p,m,c in active:
                    try:p.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        # Never signal another job; this is exclusively our own child group.
                        os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=20)
                break
            remaining=[]
            for p,m,c in active:
                if p.poll() is None:remaining.append((p,m,c));continue
                path=status_path(m,c)
                if not path.exists():placeholder(m,c,'infrastructure_error','child exited without status')
                result=json.loads(path.read_text())
                if result['status']=='quota_stop':reason='terminal subscription limit'
            active=remaining
            if reason:continue
            while pending and len(active)<2:
                reason=shared_stop_reason()
                if not reason:
                    try:reason=i.check_guard(DEADLINE)
                    except Exception as exc:reason='guard unavailable: '+str(exc)
                if reason:break
                n,m,c=pending.popleft();p=subprocess.Popen([sys.executable,__file__,'--child',str(n)],start_new_session=True);active.append((p,m,c))
            if now-last_report>=30:report('running',active);last_report=now
            time.sleep(1)
    finally:
        for m,c in plan():
            path=status_path(m,c)
            if not path.exists():placeholder(m,c,'not_run',reason or 'not launched')
            elif json.loads(path.read_text()).get('status')=='running':placeholder(m,c,'interrupted',reason or 'child interrupted')
        try:save(AREA/'quota-final.json',i.r.quota())
        except Exception as exc:save(AREA/'quota-final.json',dict(error=str(exc)))
        report('finished',[],reason)
if __name__=='__main__':main()
