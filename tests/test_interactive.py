import importlib.util,json,unittest,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('interactive',ROOT/'interactive_runner.py')
i=importlib.util.module_from_spec(spec);spec.loader.exec_module(i)
class InteractiveTests(unittest.TestCase):
 def test_models_and_terminal_resume(self):
  self.assertEqual(i.MODELS,i.r.MODELS)
  for status in ['complete','model_error','timeout','quota_stop','protocol_violation']:self.assertFalse(i.resumable(status))
 def test_public_boundary_and_budget(self):
  if Path(sys.prefix)!=ROOT/'.venv':
   subprocess.run([str(ROOT/'.venv/bin/python'),str(Path(__file__).resolve()),'InteractiveTests.test_public_boundary_and_budget'],check=True);return
  case=json.loads((ROOT/'discoveryworld/scenarios.json').read_text())[0]
  s=i.make_session(case);a=s.call('discoveryworld_observe',{})
  self.assertEqual(a,s.call('discoveryworld_observe',{}))
  text=json.dumps(a)+s.initial_prompt()
  for forbidden in ['official_scorecards','criticalHypotheses','criticalQuestions','scoreNormalized']:self.assertNotIn(forbidden,text)
  self.assertEqual({t['name'] for t in s.tools},{'discoveryworld_observe','discoveryworld_act'})
  self.assertEqual(s.call('score',{}),{'error':'unknown_tool'})
  while s.actions<100 and not s.call('discoveryworld_observe',{})['done']:s.call('discoveryworld_act',{'action':'INVALID'})
  n=s.actions;s.call('discoveryworld_act',{'action':'INVALID'});self.assertEqual(s.actions,n)
  score=s.score();self.assertIn('official_scorecards',score);self.assertLessEqual(score['score'],1)
 def test_guard_and_native_retry(self):
  b=i.BASE
  self.assertIsNone(i.r.guard(b,b,1793301000))
  bad=json.loads(json.dumps(b));bad['credit_balance']='changed'
  self.assertEqual(i.r.guard(b,bad,1793301000),'credit balance changed')
  self.assertTrue(i.native_retry_notice({'method':'error','params':{'willRetry':True,'error':{'message':'429 transient reconnect'}}}))
  self.assertFalse(i.native_retry_notice({'method':'error','params':{'willRetry':True,'error':{'message':'usage limit'}}}))
if __name__=='__main__':unittest.main()
