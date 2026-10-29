import json,tempfile,time,unittest
from pathlib import Path
import runner
from reporting import aggregate
class Tests(unittest.TestCase):
 def cases(self):return [dict(benchmark=b,id=str(i),category=c,prompt='task',gold='secret') for b in ['a','b'] for c in ['x','y'] for i in range(3)]
 def test_schedule(self):
  plan=runner.schedule(self.cases());self.assertEqual(plan,runner.schedule(self.cases()));self.assertEqual(len(plan),48)
  for i in range(0,len(plan),4):self.assertEqual({m for m,c in plan[i:i+4]},set(runner.MODELS))
  self.assertEqual([c['benchmark'] for m,c in plan[::4]][:4],['a','b','a','b'])
 def test_protocol(self):
  with tempfile.TemporaryDirectory() as d:
   cmd=runner.command(runner.MODELS[0],Path(d),Path(d));text=' '.join(cmd)
   self.assertIn('supports_websockets=false',text);self.assertIn('requires_openai_auth=true',text)
   self.assertIn('features.shell_tool=false',text);self.assertIn('features.unified_exec=false',text);self.assertNotIn('priority',text)
 def test_guard(self):
  q={'allowed':True,'account':'x','credit_balance':'2','windows':{'p':{'usedPercent':94,'resetsAt':time.time()+100}}}
  self.assertIsNone(runner.guard(q,q,time.time()+50))
  other=json.loads(json.dumps(q));other['credit_balance']='1';self.assertEqual(runner.guard(q,other,time.time()+50),'credit balance changed')
  other=json.loads(json.dumps(q));other['windows']['p']['usedPercent']=100;self.assertEqual(runner.guard(q,other,time.time()+50),'quota exhausted')
  other=json.loads(json.dumps(q));other['windows']['p']['usedPercent']=95;self.assertEqual(runner.guard(q,other,time.time()+50),'subscription headroom cutoff')
  other=json.loads(json.dumps(q));other['windows']['p']['resetsAt']+=1;self.assertIsNone(runner.guard(q,other,time.time()+50))
  other['windows']['p']['resetsAt']+=100;self.assertEqual(runner.guard(q,other,time.time()+50),'quota reset')
 def test_aggregation(self):
  c=self.cases()[0];plan=[(m,c) for m in runner.MODELS];rows=[dict(model=m,benchmark=c['benchmark'],id=c['id'],category=c['category'],status='complete',score={'correct':True}) for m in runner.MODELS[:3]]
  a=aggregate(rows,runner.MODELS,plan);self.assertEqual(a['matched_cases'],0);self.assertEqual(sum(r['missing'] for r in a['metrics']),1)
  rows.append(dict(rows[0],model=runner.MODELS[3]));self.assertEqual(aggregate(rows,runner.MODELS,plan)['matched_cases'],1)
 def test_atomic_checkpoint(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'status.json';runner.save(p,{'status':'running'});runner.save(p,{'status':'interrupted'});self.assertEqual(json.loads(p.read_text())['status'],'interrupted');self.assertFalse(p.with_name('status.json.pending').exists())
 def test_quota_detection_ignores_ids_and_answers(self):
  self.assertFalse(runner.quota_error({'method':'turn/completed','params':{'turn':{'id':'abc429','error':None,'status':'completed'}}}))
  self.assertTrue(runner.quota_error({'method':'error','params':{'message':'429 rate limit'}}))
  self.assertTrue(runner.quota_error({'method':'turn/completed','params':{'turn':{'error':{'message':'usage limit reached'}}}}))
 def test_native_transient_retry_is_not_exhaustion(self):
  retry={'method':'error','params':{'willRetry':True,'error':{'message':'Reconnecting...1/5','codexErrorInfo':{'responseStreamDisconnected':{'httpStatusCode':429}}}}}
  self.assertTrue(runner.native_retry_notice(retry))
  retry['params']['willRetry']=False;self.assertFalse(runner.native_retry_notice(retry))
  retry['params'].update(willRetry=True,error={'message':'usage limit reached'});self.assertFalse(runner.native_retry_notice(retry))
if __name__=='__main__':unittest.main()

class CheckpointTests(unittest.TestCase):
 def test_resume_only_interrupted(self):
  self.assertTrue(runner.resumable('running'));self.assertTrue(runner.resumable('interrupted'))
  for status in ['complete','quota_stop','timeout','model_error']:self.assertFalse(runner.resumable(status))
 def test_overlap_lock(self):
  import fcntl
  with tempfile.TemporaryDirectory() as d:
   with open(Path(d)/'lock','a') as a,open(Path(d)/'lock','a') as b:
    fcntl.flock(a,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with self.assertRaises(BlockingIOError):fcntl.flock(b,fcntl.LOCK_EX|fcntl.LOCK_NB)
 def test_os_gold_isolation(self):
  import subprocess
  external=runner.prepare()
  with tempfile.TemporaryDirectory(prefix='codex-sprint-trial-',dir='/private/tmp') as d:
   r=subprocess.run(['/usr/bin/sandbox-exec','-D','WORK_DIR='+d,'-f',str(external/'isolation.sb'),'/bin/cat',str(runner.ROOT/'protocol.json')],capture_output=True)
   self.assertNotEqual(r.returncode,0);self.assertNotIn(b'gpt-6',r.stdout)
 def test_billing_guard(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  for data,safe in [({'credits':{'has_credits':True},'spend_control':{'individual_limit':None}},False),({'credits':{'has_credits':True},'spend_control':{'individual_limit':0}},True),({'credits':{'has_credits':True},'rate_limit':{'allowed':True,'primary_window':{'used_percent':10}}},True),({'rate_limit':{'allowed':True,'primary_window':{'used_percent':95}}},False),({},False)]:
   with patch('runner.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(data))):self.assertEqual(runner.billing_safety()['safe'],safe)
