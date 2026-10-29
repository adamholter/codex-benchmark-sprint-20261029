"""Subscription-only, resumable benchmark sprint. No metered API fallback."""
import argparse, concurrent.futures, fcntl, hashlib, importlib.util, json, os, queue, random, re, shutil, signal, subprocess, threading, time
from collections import defaultdict, deque
from pathlib import Path
ROOT=Path(__file__).resolve().parent
RUNTIME=ROOT/'runtime'
MODELS=['gpt-6.1-sol','gpt-6-astra','gpt-6.1-terra','gpt-6-luna']
STOP=threading.Event()
USAGE_CUTOFF=95
DISABLE=['shell_tool','unified_exec','view_image','apps','plugins','browser_use','browser_use_external','computer_use','image_generation','multi_agent','multi_agent_v2','goals','memories','hooks','skill_search','skill_mcp_dependency_install','code_mode','code_mode_only','code_mode_host','sleep_tool','workspace_dependencies','tool_suggest','chronicle','realtime_conversation']
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.pending');tmp.write_text(json.dumps(data,indent=2,default=str)+'\n');tmp.replace(path)
def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def quota():
    m=load_module('quota_guard.py','sprint_quota')
    try:return m.read_quota_with_retry()
    finally:
        if m.RPC:
            m.RPC.terminate()
            try:m.RPC.wait(timeout=3)
            except subprocess.TimeoutExpired:m.RPC.kill();m.RPC.wait()
def billing_safety():
    # Read account spend controls without exposing OAuth tokens to argv/logs.
    auth=json.loads((Path.home()/'.codex/auth.json').read_text())['tokens']
    config='url = "https://chatgpt.com/backend-api/wham/usage"\nheader = '+json.dumps('Authorization: Bearer '+auth['access_token'])+'\nheader = '+json.dumps('ChatGPT-Account-Id: '+auth['account_id'])+'\n'
    r=subprocess.run(['curl','--silent','--show-error','--fail','--max-time','10','--config','-'],input=config,text=True,capture_output=True,timeout=12)
    if r.returncode:raise RuntimeError('Billing safety check unavailable')
    d=json.loads(r.stdout);credits=d.get('credits') or {};spend=d.get('spend_control') or {}
    overage_disabled=spend.get('reached') is True or spend.get('individual_limit')==0 or (credits.get('has_credits') is False and credits.get('unlimited') is False)
    limits=d.get('rate_limit') or {}
    windows=[limits[k] for k in ('primary_window','secondary_window') if limits.get(k)]
    ordinary_headroom=limits.get('allowed') is True and bool(windows) and all(w.get('used_percent',100)<USAGE_CUTOFF for w in windows)
    return {'safe':overage_disabled or ordinary_headroom,'overage_disabled':overage_disabled,
            'ordinary_subscription_headroom':ordinary_headroom,'usage_cutoff_percent':USAGE_CUTOFF,
            'credits':credits,'spend_control':spend,'checked_at':time.time()}
def guard(base,current,deadline):
    if time.time()>=deadline:return 'deadline'
    if not current.get('allowed'):return 'ordinary usage unavailable'
    if current.get('credit_balance') is None:return 'credit balance unknown'
    if current['account']!=base['account']:return 'account changed'
    if current['credit_balance']!=base['credit_balance']:return 'credit balance changed'
    if set(current['windows'])!=set(base['windows']):return 'quota schema changed'
    for k,w in current['windows'].items():
        if w['usedPercent']>=100:return 'quota exhausted'
        if w['usedPercent']>=USAGE_CUTOFF:return 'subscription headroom cutoff'
        if abs(w.get('resetsAt',0)-base['windows'][k].get('resetsAt',0))>60:return 'quota reset'
        if time.time()>=w.get('resetsAt',0):return 'quota reset'
    return None
def discover():
    cases=[];scorers={};seen=set()
    for path in sorted((ROOT/'adapters').glob('*.py')):
        if path.name.startswith('_'):continue
        m=load_module(path,'adapter_'+path.stem)
        if not hasattr(m,'load_cases'):continue
        for case in m.load_cases():
            if not all(k in case for k in ['benchmark','id','category','prompt','gold']):raise ValueError('Invalid case in '+str(path))
            case=dict(case);case['id']=str(case['id']);key=(case['benchmark'],case['id'])
            if key in seen:raise ValueError('Duplicate case '+str(key))
            seen.add(key);cases.append(case);scorers[key]=m.score
    return cases,scorers
def schedule(cases,seed=20261029):
    buckets=defaultdict(list)
    for c in cases:buckets[(c['benchmark'],c['category'])].append(c)
    rng=random.Random(seed);groups=defaultdict(deque)
    for key in sorted(buckets):
        values=sorted(buckets[key],key=lambda c:c['id']);rng.shuffle(values);groups[key[0]].append(deque(values))
    ordered=[]
    while groups:
        for benchmark in list(sorted(groups)):
            cats=groups[benchmark];bucket=cats.popleft();ordered.append(bucket.popleft())
            if bucket:cats.append(bucket)
            if not cats:del groups[benchmark]
    return [(m,c) for n,c in enumerate(ordered) for m in MODELS[n%4:]+MODELS[:n%4]]
def trial_id(model,case):return hashlib.sha256(json.dumps([model,case['benchmark'],case['id'],case['prompt']],ensure_ascii=False).encode()).hexdigest()[:24]
def prepare():
    RUNTIME.mkdir(exist_ok=True)
    external=Path('/private/tmp/codex-sprint-runtime-20261029');external.mkdir(mode=0o700,exist_ok=True)
    catalog=json.loads((Path.home()/'.codex/models_cache.json').read_text());catalog['models']=[m for m in catalog['models'] if m['slug'] in MODELS]
    if {m['slug'] for m in catalog['models']}!=set(MODELS):raise RuntimeError('Exact models missing from catalog')
    # Remove model-specific injected agent instructions. The case prompt owns the task.
    for m in catalog['models']:
        m['model_messages']={'instructions_template':'You answer the supplied task directly. No tools are available.'};m['experimental_supported_tools']=[]
    save(external/'model-catalog.json',catalog)
    profile='''(version 1)
(allow default)
(deny file-read* (subpath "%s") (literal "%s/AGENTS.md") (literal "%s/.codex/AGENTS.md") (subpath "%s/.codex/memories") (subpath "%s/.codex/sessions") (subpath "%s/.codex/archived_sessions") (regex #"^/private/tmp/codex-sprint-trial-"))
(allow file-read* (subpath (param "WORK_DIR")))
'''%(ROOT,*([Path.home()]*5))
    (external/'isolation.sb').write_text(profile);(RUNTIME/'isolation.sb').write_text(profile)
    return external
def command(model,work,external):
    cfg={'model_catalog_json':str(external/'model-catalog.json'),'model_reasoning_effort':'high','model_provider':'sprint_subscription','project_doc_max_bytes':0,'skills.include_instructions':False,'skills.bundled.enabled':False,'tools.update_plan.enabled':False,'tools.experimental_request_user_input.enabled':False,'web_search':'disabled','service_tier':'default','suppress_unstable_features_warning':True,'features.skip_host_skill_discovery':True}
    for name in DISABLE:cfg['features.'+name]=False
    config=(Path.home()/'.codex/config.toml').read_text()
    for name in re.findall(r'^\[mcp_servers\.([^\].]+)\]',config,re.M):cfg['mcp_servers.'+name+'.enabled']=False
    cmd=['/usr/bin/sandbox-exec','-D',f'WORK_DIR={work}','-f',str(external/'isolation.sb'),shutil.which('codex') or '/opt/homebrew/bin/codex']
    for k,v in cfg.items():cmd+=['-c',k+'='+json.dumps(v)]
    cmd+=['-c','model_providers.sprint_subscription={name="ChatGPT subscription HTTPS",base_url="https://chatgpt.com/backend-api/codex",wire_api="responses",requires_openai_auth=true,supports_websockets=false}','app-server']
    return cmd
LIMIT_WORDS=('429','usage limit','usage_limit','rate limit','rate_limit','quota exceeded','insufficient_quota','credits exhausted')
def quota_error(msg):
    params=msg.get('params') or {}
    error=msg.get('error') or (params if msg.get('method')=='error' else (params.get('turn') or {}).get('error'))
    return bool(error) and any(word in json.dumps(error).lower() for word in LIMIT_WORDS)
def native_retry_notice(msg):
    params=msg.get('params') or {}
    if msg.get('method')!='error' or params.get('willRetry') is not True:return False
    error=json.dumps(params.get('error') or {}).lower()
    return not any(word in error for word in ('usage limit','usage_limit','insufficient_quota','quota exceeded','credits exhausted'))
def trial(model,case,scorer,external,deadline,area='trials'):
    dest=RUNTIME/area/trial_id(model,case);dest.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();work=Path('/private/tmp')/('codex-sprint-trial-'+dest.name);work.mkdir(mode=0o700,exist_ok=True)
    result={'model':model,'benchmark':case['benchmark'],'id':case['id'],'category':case['category'],'effort':'high','service_tier':'default','status':'interrupted','started_at':time.time()}
    previous=dest/'status.json'
    if previous.exists() and resumable(json.loads(previous.read_text()).get('status')):
        archive=dest/'attempts'/str(time.time_ns());archive.mkdir(parents=True)
        for old in list(dest.iterdir()):
            if old.is_file():old.rename(archive/old.name)
    save(dest/'status.json',dict(result,status='running'));(dest/'prompt.txt').write_text(case['prompt'])
    inbox=queue.Queue();p=None;reader=None;errors=[];retry_notices=[];response='';usage=None;tool_violation=False
    events=(dest/'events.jsonl').open('w');err=(dest/'stderr.txt').open('w')
    try:
        env={k:os.environ[k] for k in ['PATH','USER','LANG'] if k in os.environ};env.update(TMPDIR=str(work),RUST_LOG='error')
        p=subprocess.Popen(command(model,work,external),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,env=env,cwd=work,start_new_session=True,bufsize=1)
        def read():
            for line in p.stdout:
                events.write(line);events.flush()
                try:inbox.put(json.loads(line))
                except ValueError:pass
            inbox.put({'_closed':True})
        reader=threading.Thread(target=read,daemon=True);reader.start()
        def send(d):p.stdin.write(json.dumps(d)+'\n');p.stdin.flush()
        def receive():
            while True:
                if STOP.is_set() or time.time()>=deadline:raise InterruptedError('global stop or deadline')
                if time.monotonic()-started>=900:raise TimeoutError('900 second trial maximum')
                try:msg=inbox.get(timeout=.25)
                except queue.Empty:continue
                if quota_error(msg) and not native_retry_notice(msg):
                    STOP.set();raise RuntimeError('subscription quota/limit failure: '+json.dumps(msg))
                if msg.get('_closed'):raise RuntimeError('app-server closed')
                return msg
        def request(i,method,params):
            send({'id':i,'method':method,'params':params})
            while True:
                msg=receive()
                if msg.get('id')==i:
                    if 'error' in msg:raise RuntimeError(json.dumps(msg['error']))
                    return msg['result']
                if 'id' in msg:raise RuntimeError('Unexpected server request during setup')
        request(1,'initialize',{'clientInfo':{'name':'benchmark-sprint','version':'1'},'capabilities':{'experimentalApi':True}});send({'method':'initialized','params':{}})
        reply=request(2,'thread/start',{'model':model,'modelProvider':'sprint_subscription','cwd':str(work),'ephemeral':True,'approvalPolicy':'never','sandbox':'read-only','environments':[],'allowProviderModelFallback':False,'baseInstructions':'Answer the supplied task. Follow its requested formatting. No tools are available.','developerInstructions':'Work only from the supplied prompt. Do not seek files, benchmark answers, or external sources.','dynamicTools':[],'serviceTier':'default','experimentalRawEvents':True})
        save(dest/'resolved-thread.json',reply)
        if not(reply['model']==model and reply['reasoningEffort']=='high' and reply['modelProvider']=='sprint_subscription' and reply.get('serviceTier') in (None,'default')):raise RuntimeError('Resolved model/effort/provider/tier mismatch')
        request(3,'turn/start',{'threadId':reply['thread']['id'],'model':model,'effort':'high','serviceTierForTurn':'default','environments':[],'input':[{'type':'text','text':case['prompt']}]})
        while True:
            msg=receive();method=msg.get('method','');params=msg.get('params',{})
            if 'id' in msg:
                tool_violation=True;send({'id':msg['id'],'error':{'code':-32601,'message':'No tools allowed'}})
            if method=='item/completed':
                item=params.get('item',{})
                if item.get('type')=='agentMessage':response=item.get('text','')
                elif item.get('type') not in ['reasoning','plan','userMessage']:tool_violation=True
            if method=='thread/tokenUsage/updated':usage=params.get('tokenUsage')
            if method=='error':
                if native_retry_notice(msg):retry_notices.append(params)
                else:errors.append(params)
            if method=='turn/completed':
                result['turn']=params.get('turn',{});break
        result['status']='complete' if response and result['turn'].get('status')=='completed' and not errors else 'model_error'
        if tool_violation:result['status']='protocol_violation'
        if result['status']=='complete':
            try:result['score']=scorer(case,response)
            except Exception as e:result['status']='scoring_error';errors.append(str(e))
    except TimeoutError as e:result['status']='timeout';errors.append(str(e))
    except InterruptedError as e:errors.append(str(e))
    except Exception as e:
        result['status']='quota_stop' if STOP.is_set() else 'infrastructure_error';errors.append(str(e))
    finally:
        if p and p.poll() is None:
            os.killpg(p.pid,signal.SIGTERM)
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        if reader:reader.join(timeout=3)
        events.close();err.close()
    (dest/'response.txt').write_text(response)
    result.update(seconds=time.monotonic()-started,usage=usage,errors=errors,native_retry_notices=retry_notices,finished_at=time.time())
    save(dest/'status.json',result);return result

def resumable(status):
    return status in ('running','interrupted')
def resource_workers(requested):
    p=subprocess.run(['memory_pressure','-Q'],capture_output=True,text=True,timeout=5)
    match=re.search(r'free percentage: (\d+)%',p.stdout)
    if not match:raise RuntimeError('Cannot establish memory headroom')
    free=int(match.group(1))
    if free<10:raise RuntimeError('Insufficient memory headroom')
    return min(requested,2 if free<20 else 4 if free<30 else 8),free
def main(argv=None):
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--pilot',action='store_true');mode.add_argument('--run',action='store_true');parser.add_argument('--workers',type=int,default=8);parser.add_argument('--deadline',type=float,default=time.time()+5*3600);parser.add_argument('--seed',type=int,default=20261029);a=parser.parse_args(argv)
    if not 1<=a.workers<=8:parser.error('workers must be 1..8')
    RUNTIME.mkdir(exist_ok=True);lock=(RUNTIME/'runner.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    STOP.clear()
    for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,lambda *_:STOP.set())
    auth=json.loads((Path.home()/'.codex/auth.json').read_text())
    if auth.get('auth_mode')!='chatgpt' or not auth.get('tokens') or auth.get('OPENAI_API_KEY'):raise RuntimeError('ChatGPT-only authentication required')
    baseline=quota();billing=billing_safety();save(RUNTIME/'billing-safety.json',billing)
    if not billing['safe']:raise RuntimeError('Ordinary subscription headroom unavailable; no inference dispatched')
    reason=guard(baseline,baseline,a.deadline)
    if reason:raise RuntimeError(reason)
    # Stop below exhaustion to keep concurrent requests within subscription usage.
    deadline=min(a.deadline,*[w['resetsAt']-5 for w in baseline['windows'].values()])
    workers,free=resource_workers(a.workers);save(RUNTIME/'resources.json',{'requested_workers':a.workers,'effective_workers':workers,'memory_free_percent':free})
    external=prepare();cases,scorers=discover();smoke=False
    if a.pilot:
        if cases:
            first={}
            for _,case in schedule(cases,a.seed):
                first.setdefault(case['benchmark'],case)
            cases=list(first.values())
        else:
            smoke=True;cases=[{'benchmark':'smoke','id':'inference','category':'smoke','prompt':'Reply with exactly SUBSCRIPTION_OK','gold':'SUBSCRIPTION_OK'}];scorers[('smoke','inference')]=lambda c,r:{'correct':r.strip()=='SUBSCRIPTION_OK','extracted':r.strip()}
    elif not cases:raise RuntimeError('No adapter cases; long run prohibited')
    plan=schedule(cases,a.seed);area='smoke' if smoke else ('pilot' if a.pilot else 'trials')
    fingerprint=hashlib.sha256()
    for m,c in plan:
        fingerprint.update(json.dumps([m,c],sort_keys=True).encode())
    fingerprint=fingerprint.hexdigest();manifest=RUNTIME/(area+'-manifest.json')
    if manifest.exists():
        previous=json.loads(manifest.read_text())
        if previous['fingerprint']!=fingerprint:raise RuntimeError('Dataset/protocol changed; preserve results and use new runtime')
        mismatch=guard(previous['baseline'],baseline,deadline)
        if mismatch:raise RuntimeError('Resume rejected: '+mismatch)
        baseline=previous['baseline']
    save(manifest,{'fingerprint':fingerprint,'planned':len(plan),'seed':a.seed,'deadline':deadline,'baseline':baseline})
    save(RUNTIME/'runner-ready.json',{'state':'pilot_running' if a.pilot else 'running','command':'python3 runner.py --run --workers 8 --deadline '+str(int(deadline)),'quota':baseline,'models':MODELS,'effort':'high','service_tier':'default','route_verified_by_inference':False,'smoke':smoke})
    pending=deque()
    for m,c in plan:
        status=RUNTIME/area/trial_id(m,c)/'status.json'
        if status.exists() and not resumable(json.loads(status.read_text()).get('status')):continue
        pending.append((m,c))
    from reporting import report
    reason=None;last_check=0;last_dispatch=0;active={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        while (pending or active) and not STOP.is_set():
            if time.time()-last_check>=10:
                try:
                    current=quota();reason=guard(baseline,current,deadline);save(RUNTIME/'quota-latest.json',current)
                    if not billing_safety()['safe']:reason='paid credit spillover possible'
                except Exception as e:reason='quota check failed: '+str(e)
                last_check=time.time()
                if reason:STOP.set();break
            if time.time()>=deadline:reason='deadline';STOP.set();break
            while pending and len(active)<workers and not STOP.is_set():
                if time.monotonic()-last_dispatch<2:break
                counts=defaultdict(int)
                for model,_ in active.values():counts[model]+=1
                eligible=next((i for i,(model,_) in enumerate(pending) if counts[model]<2),None)
                if eligible is None:break
                pending.rotate(-eligible);m,c=pending.popleft();pending.rotate(eligible)
                f=pool.submit(trial,m,c,scorers[(c['benchmark'],c['id'])],external,deadline,area);active[f]=(m,c)
                last_dispatch=time.monotonic()
            done,_=concurrent.futures.wait(active,timeout=.5,return_when=concurrent.futures.FIRST_COMPLETED)
            for f in done:f.result();del active[f]
            if done:report(RUNTIME,area,MODELS,plan)
    final=quota();final_reason=guard(baseline,final,deadline);report(RUNTIME,area,MODELS,plan)
    verified=[]
    for path in (RUNTIME/area).glob('*/status.json'):
        r=json.loads(path.read_text())
        if r['status']=='complete':verified.append(r['model'])
    ready={'state':'finished','stop_reason':reason or final_reason or ('global stop' if STOP.is_set() else None),'quota':final,'credit_baseline':baseline['credit_balance'],'credit_unchanged':baseline['credit_balance']==final['credit_balance'],'models':MODELS,'effort':'high','service_tier':'default','route_verified_by_inference':sorted(set(verified)),'smoke':smoke,'area':area,'planned':len(plan),'command':'python3 runner.py --run --workers 8 --deadline '+str(int(deadline))}
    save(RUNTIME/'runner-ready.json',ready);print(json.dumps(ready));return 0 if len(verified)==len(plan) else 1
if __name__=='__main__':raise SystemExit(main())
