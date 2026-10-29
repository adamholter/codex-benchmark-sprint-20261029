import importlib.util,unittest,subprocess,sys,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('advanced',ROOT/'advanced_runner.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class AdvancedTests(unittest.TestCase):
 def test_protocol(self):
  self.assertEqual(len(a.cases()),8);self.assertEqual(len(a.plan()),32)
  self.assertEqual(a.i.MODELS,a.i.r.MODELS)
  self.assertEqual(len({c['id'] for c in a.cases()}),8)
  self.assertEqual([c['difficulty'] for c in a.cases()],['Normal','Challenge']*4)
  self.assertTrue(all(c['action_budget']==1000 and c['seed']==0 for c in a.cases()))
  self.assertEqual(a.i.TOOL_CALL_LIMIT,3000);self.assertEqual(a.i.TRIAL_SECONDS,1800)
  for n,c in enumerate(a.cases()):self.assertEqual([m for m,_ in a.plan()[n*4:n*4+4]],a.i.MODELS[n%4:]+a.i.MODELS[:n%4])
 def test_simulator_loads_and_score_boundary(self):
  for n,c in enumerate(a.cases()):
   with self.subTest(case=c['id']):
    result=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'advanced_runner.py'),'--validate',str(n)],capture_output=True,text=True,timeout=180)
    record=json.loads((a.AREA/'validation'/f'{n}.json').read_text())
    # Source failures are recorded explicitly, never assigned as model errors.
    self.assertIn(record['status'],['loaded','not_run'])
    if record['status']=='loaded':self.assertTrue(record['score_boundary_verified'])
    else:self.assertIn('reason',record)
 def test_compaction_classification(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'status.json'
   original=dict(status='protocol_violation',errors=[],tool_calls=1,turn={'status':'completed'})
   p.write_text(json.dumps(original));p.with_name('response.txt').write_text('finished')
   events=[{'id':1,'result':{}},{'method':'item/completed','params':{'item':{'type':'contextCompaction'}}},{'id':5,'method':'item/tool/call','params':{'tool':'discoveryworld_observe'}}]
   p.with_name('events.jsonl').write_text('\n'.join(map(json.dumps,events)))
   a.normalize_compaction(p);self.assertEqual(json.loads(p.read_text())['status'],'complete')
   p.write_text(json.dumps(original));events[-1]['params']['tool']='shell'
   p.with_name('events.jsonl').write_text('\n'.join(map(json.dumps,events)))
   a.normalize_compaction(p);self.assertEqual(json.loads(p.read_text())['status'],'protocol_violation')
 def test_bridge(self):
  cmd=a.i.command(a.i.MODELS[0],Path('/private/tmp'),a.EXTERNAL)
  self.assertIn('features.code_mode_host=true',cmd)
if __name__=='__main__':unittest.main()
