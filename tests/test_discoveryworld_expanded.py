import importlib.util,os,unittest,json,tempfile,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(expanded):
 with patch.dict(os.environ,{'DISCOVERYWORLD_EXPANDED':'1' if expanded else '0'}):
  spec=importlib.util.spec_from_file_location('expanded_test_runner',ROOT/'advanced_runner.py')
  a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a);return a
class ExpandedTests(unittest.TestCase):
 def test_expanded_plan(self):
  a=load(True);old=load(False)
  cases=a.cases();plan=a.plan()
  self.assertEqual((len(cases),len(plan)),(62,248))
  self.assertEqual(len({c['id'] for c in cases}),62)
  self.assertFalse({c['id'] for c in cases}&{c['id'] for c in old.cases()})
  self.assertEqual([c['scenario'] for c in cases[:6]],['Plant Nutrients']*2+['Space Sick']*2+['Lost in Translation']*2)
  self.assertEqual({c['seed'] for c in cases},set(range(5)))
  self.assertEqual(len({c['scenario'] for c in cases}),7)
  self.assertTrue(all(c['benchmark']=='discoveryworld_advanced' and c['action_budget']==1000 for c in cases))
  self.assertEqual(a.i.MODELS,old.i.MODELS)
  self.assertEqual(a.AREA,ROOT/'discoveryworld/expanded')
  for n,c in enumerate(cases):
   self.assertEqual([m for m,_ in plan[n*4:n*4+4]],a.i.MODELS[n%4:]+a.i.MODELS[:n%4])
 def test_shared_safety_stop(self):
  a=load(True)
  with tempfile.TemporaryDirectory() as tmp,patch.object(a,'AREA',Path(tmp)):
   a.save(a.AREA/'controller-process.json',{'started_at':time.time()-1})
   with patch.object(a,'_original_guard',return_value='subscription headroom cutoff'):
    self.assertEqual(a.guarded(time.time()+60),'subscription headroom cutoff')
   self.assertEqual(a.shared_stop_reason(),'subscription headroom cutoff')
   a.save(a.AREA/'controller-process.json',{'started_at':time.time()+1})
   self.assertIsNone(a.shared_stop_reason())
 def test_default_unchanged(self):
  a=load(False)
  self.assertEqual((len(a.cases()),len(a.plan())),(8,32))
  self.assertEqual(a.AREA,ROOT/'discoveryworld/advanced')
if __name__=='__main__':unittest.main()
