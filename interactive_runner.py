"""Subscription-only isolated interactive DiscoveryWorld diagnostic."""
import argparse, fcntl, hashlib, importlib.util, json, os, queue, signal, subprocess, sys, threading, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('static_helpers',ROOT/'runner.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
MODELS=r.MODELS;STOP=r.STOP;save=r.save;quota_error=r.quota_error;native_retry_notice=r.native_retry_notice;resumable=r.resumable
TRIAL_SECONDS=1800
TOOL_CALL_LIMIT=300
def command(model,work,external):
    # Dynamic tools are relayed through Codex's JS host. This enables only that
    # host; every built-in tool, MCP, file route and external source stays disabled.
    cmd=r.command(model,work,external)
    cmd[-1:-1]=['-c','features.code_mode_host=true']
    return cmd
AREA=ROOT/'discoveryworld/results'
BASE=json.loads((ROOT/'runtime/trials-manifest.json').read_text())['baseline']
def trial_key(model,case):return hashlib.sha256(json.dumps([model,case['id'],'discoveryworld-v1']).encode()).hexdigest()[:24]
def make_session(case):
    sys.path.insert(0,str(ROOT/'sources/discoveryworld'))
    spec=importlib.util.spec_from_file_location('dw_session',ROOT/'discoveryworld/session.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.Session(**{k:case[k] for k in ('scenario','difficulty','seed','action_budget')})
def check_guard(deadline):
    current=r.quota();save(AREA/'quota-latest.json',current)
    reason=r.guard(BASE,current,deadline)
    if not r.billing_safety()['safe']:return 'paid credit spillover possible'
    return reason
def trial(model,case,external,deadline):
    session=make_session(case)
    case=dict(case,prompt=session.initial_prompt())
    dest=AREA/trial_key(model,case);dest.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();work=Path('/private/tmp')/('codex-sprint-trial-'+dest.name);work.mkdir(mode=0o700,exist_ok=True)
    result={'model':model,'benchmark':case['benchmark'],'id':case['id'],'category':case['category'],'effort':'high','service_tier':'default','status':'interrupted','started_at':time.time()}
    previous=dest/'status.json'
    if previous.exists() and resumable(json.loads(previous.read_text()).get('status')):
        archive=dest/'attempts'/str(time.time_ns());archive.mkdir(parents=True)
        for old in list(dest.iterdir()):
            if old.is_file():old.rename(archive/old.name)
    save(dest/'status.json',dict(result,status='running'));(dest/'prompt.txt').write_text(case['prompt'])
    inbox=queue.Queue();p=None;reader=None;errors=[];retry_notices=[];tool_calls=[];response='';usage=None;tool_violation=False
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
        def send(d):
            with (dest/'requests.jsonl').open('a') as log:log.write(json.dumps(d)+'\n')
            p.stdin.write(json.dumps(d)+'\n');p.stdin.flush()
        last_guard=[time.time()]
        def receive():
            while True:
                if time.time()-last_guard[0]>=10:
                    reason=check_guard(deadline);last_guard[0]=time.time()
                    if reason: STOP.set();raise InterruptedError(reason)
                if STOP.is_set() or time.time()>=deadline:raise InterruptedError('global stop or deadline')
                if time.monotonic()-started>=TRIAL_SECONDS:raise TimeoutError(str(TRIAL_SECONDS)+' second trial maximum')
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
        reply=request(2,'thread/start',{'model':model,'modelProvider':'sprint_subscription','cwd':str(work),'ephemeral':True,'approvalPolicy':'never','sandbox':'read-only','environments':[],'allowProviderModelFallback':False,'baseInstructions':'Complete the supplied DiscoveryWorld task using only the two supplied game tools.','developerInstructions':'Use only supplied game observations and tools. Never seek files, hidden state, scorecards or external sources.','dynamicTools':session.tools,'serviceTier':'default','experimentalRawEvents':True})
        save(dest/'resolved-thread.json',reply)
        if not(reply['model']==model and reply['reasoningEffort']=='high' and reply['modelProvider']=='sprint_subscription' and reply.get('serviceTier') in (None,'default')):raise RuntimeError('Resolved model/effort/provider/tier mismatch')
        request(3,'turn/start',{'threadId':reply['thread']['id'],'model':model,'effort':'high','serviceTierForTurn':'default','environments':[],'input':[{'type':'text','text':case['prompt']}]})
        while True:
            msg=receive();method=msg.get('method','');params=msg.get('params',{})
            if 'id' in msg:
                if method!='item/tool/call' or params.get('tool') not in {t['name'] for t in session.tools}:
                    tool_violation=True;send({'id':msg['id'],'error':{'code':-32601,'message':'Only supplied game tools allowed'}})
                else:
                    if len(tool_calls)>=TOOL_CALL_LIMIT:raise RuntimeError(str(TOOL_CALL_LIMIT)+' total tool-call cap')
                    output=session.call(params['tool'],params.get('arguments',{}))
                    entry={'request':msg,'result':output};tool_calls.append(entry)
                    with (dest/'toolcalls.jsonl').open('a') as log:log.write(json.dumps(entry)+'\n')
                    send({'id':msg['id'],'result':{'contentItems':[{'type':'inputText','text':json.dumps(output)}],'success':True}})
                    save(dest/'checkpoint.json',{'actions':session.actions,'tool_calls':len(tool_calls),'score':session.score()})
            if method=='item/completed':
                item=params.get('item',{})
                if item.get('type')=='agentMessage':response=item.get('text','')
                elif item.get('type') not in ['reasoning','plan','userMessage','dynamicToolCall']:tool_violation=True
            if method=='thread/tokenUsage/updated':usage=params.get('tokenUsage')
            if method=='error':
                if native_retry_notice(msg):
                    retry_notices.append(params)
                    if len(retry_notices)>12:raise RuntimeError('Native recovery bound exceeded')
                else:errors.append(params)
            if method=='turn/completed':
                result['turn']=params.get('turn',{});break
        result['status']='complete' if response and result['turn'].get('status')=='completed' and not errors else 'model_error'
        if tool_violation or not tool_calls:result['status']='protocol_violation'
        if result['status']=='complete':
            try:result['score']=session.score()
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
    result['score']=session.score()
    result['tool_calls']=len(tool_calls)
    result['tools_used']=sorted({t['request']['params']['tool'] for t in tool_calls})
    result.update(seconds=time.monotonic()-started,usage=usage,errors=errors,native_retry_notices=retry_notices,finished_at=time.time())
    save(dest/'status.json',result);return result

def write_report(plan,state,reason=None):
    statuses=[]
    for model,case in plan:
        p=AREA/trial_key(model,case)/'status.json'
        if p.exists():statuses.append(json.loads(p.read_text()))
    pilot=[x for x in statuses if x['id']=='proteomics']
    save(ROOT/'discoveryworld/launcher.json',{'pilot_valid':all(x['status']=='complete' and x.get('tool_calls',0)>0 for x in pilot) if len(pilot)==4 else None,'pid':os.getpid(),'state':state,'deadline':1793301000,'workers':1,'planned':16,'finished':sum(x['status']!='running' for x in statuses),'pilot':pilot,'stop_reason':reason,'updated_at':time.time()})
    lines=['# DiscoveryWorld diagnostic','',f'State: {state}. Planned: 16. Finished: {sum(x["status"]!="running" for x in statuses)}.', '', 'Four preselected Easy seed-0 scenarios, 100 actions. Official procedural and completion metrics only. Not a full published DiscoveryWorld reproduction. No knowledge judge. Comparisons must use matched completed cases.', '', '| Model | Scenario | Status | Procedure | Completed successfully |', '|---|---|---|---|---|']
    for x in statuses:lines.append(f"| {x['model']} | {x['category']} | {x['status']} | {(x.get('score') or {}).get('score')} | {(x.get('score') or {}).get('correct')} |")
    if reason:lines+=['',f'Stop reason: {reason}']
    (ROOT/'discoveryworld/RESULTS.md').write_text('\n'.join(lines)+'\n')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--child',type=int);parser.add_argument('--model');args=parser.parse_args()
    scenarios=json.loads((ROOT/'discoveryworld/scenarios.json').read_text())[:4]
    cases=[dict(c,id=c['scenario'].lower().replace(' ','-'),benchmark='discoveryworld',category=c['scenario']) for c in scenarios]
    external=Path('/private/tmp/codex-sprint-runtime-20261029')
    if args.child is not None:
        for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:STOP.set())
        trial(args.model,cases[args.child],external,1793301000);return
    AREA.mkdir(parents=True,exist_ok=True)
    lock=(AREA/'controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:STOP.set())
    auth=json.loads((Path.home()/'.codex/auth.json').read_text())
    if auth.get('auth_mode')!='chatgpt' or auth.get('OPENAI_API_KEY'):raise RuntimeError('ChatGPT OAuth required')
    plan=[(m,c) for c in cases for m in MODELS]
    save(ROOT/'discoveryworld/protocol.json',{'models':MODELS,'effort':'high','service_tier':'default','planned':16,'scenarios':scenarios,'concurrency':1,'max_trial_seconds':1800,'deadline':1793301000,'max_tool_calls':300,'baseline':BASE,'isolation_profile':str(external/'isolation.sb'),'route':'OAuth ChatGPT HTTPS','pilot':'first scenario each model, counted within 16','knowledge_judge':False,'dynamic_tool_transport':'Codex JS host enabled only to relay supplied dynamic tools. Built-in tools and MCPs remain disabled.'})
    reason=None;write_report(plan,'running')
    for index,(model,case) in enumerate(plan):
        reason=check_guard(1793301000)
        if reason or STOP.is_set():break
        path=AREA/trial_key(model,case)/'status.json'
        if path.exists() and not resumable(json.loads(path.read_text()).get('status')):
            result=json.loads(path.read_text())
        else:
            p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--child',str(index//4),'--model',model],start_new_session=True)
            while p.poll() is None:
                if STOP.is_set() or time.time()>=1793301000:
                    os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=20);reason='global stop or deadline';break
                time.sleep(.5)
            if not path.exists():reason='child failed without status';break
            result=json.loads(path.read_text())
        write_report(plan,'running')
        if result['status']=='quota_stop':reason='terminal subscription limit';break
        if index==3:
            pilot_results=[json.loads((AREA/trial_key(m,cases[0])/'status.json').read_text()) for m in MODELS]
            invalid=[x for x in pilot_results if x['status']!='complete' or not x.get('tool_calls') or not x.get('tools_used')]
            if invalid:reason='pilot validation failed: '+', '.join(x['model']+' '+x['status'] for x in invalid);break
    final_reason=check_guard(1793301000)
    write_report(plan,'finished',reason or final_reason)
if __name__=='__main__':main()
