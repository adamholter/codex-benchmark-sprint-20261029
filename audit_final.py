"""Offline audit of retained responses, model identity and observable conditions."""
from collections import defaultdict, Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import runner

ROOT=Path(__file__).resolve().parent

def clean_ids(value):
    if isinstance(value,dict):return {re.sub(r'uuid \d+','uuid ID',k):clean_ids(v) for k,v in value.items() if k!='uuid'}
    if isinstance(value,list):return sorted((clean_ids(v) for v in value),key=lambda v:json.dumps(v,sort_keys=True))
    if isinstance(value,str):return re.sub(r'uuid[: ]+\d+','uuid ID',value)
    return value

def main():
    areas=[ROOT/'runtime/trials',ROOT/'discoveryworld/results',ROOT/'discoveryworld/advanced/results',ROOT/'discoveryworld/expanded/results']
    group=defaultdict(list);complete=[]
    for area in areas:
        for p in area.glob('*/status.json'):
            d=json.loads(p.read_text())
            if d['status']!='complete':continue
            complete.append((p,d));group[(d['benchmark'],d['id'])].append((p,d))
            for f in ('prompt.txt','response.txt','events.jsonl','resolved-thread.json'):assert p.with_name(f).is_file(),(p,f)
            x=json.loads(p.with_name('resolved-thread.json').read_text())
            assert x['model']==d['model'] and x['reasoningEffort']=='high' and x['modelProvider']=='sprint_subscription' and x.get('serviceTier') in (None,'default'),p
            assert not d.get('errors') and d['turn']['status']=='completed',p
    matched={k:v for k,v in group.items() if {d['model'] for p,d in v}==set(runner.MODELS)}
    variants=[]
    for k,vs in matched.items():
        hashes={hashlib.sha256(p.with_name('prompt.txt').read_bytes()).hexdigest() for p,d in vs}
        if len(hashes)==1:continue
        assert k[0]=='discoveryworld_advanced' and k[1] in ('space-sick-normal-seed0','space-sick-normal-seed1'),k
        canonical=set();preambles=set();hypotheses=set()
        for p,d in vs:
            before,initial=p.with_name('prompt.txt').read_text().split('Initial state: ',1)
            preambles.add(before);canonical.add(json.dumps(clean_ids(json.loads(initial)),sort_keys=True))
            hypotheses.add(json.dumps([{f:c.get(f) for f in ('taskDescription','criticalHypotheses','criticalQuestions')} for c in d['score']['official_scorecards']],sort_keys=True))
        assert len(canonical)==len(preambles)==len(hypotheses)==1,k
        variants.append(list(k))
    cases,sc=runner.discover();lookup={(c['benchmark'],c['id']):c for c in cases};sample=[]
    for bench in sorted({c['benchmark'] for c in cases}):
        for model in runner.MODELS:
            for outcome in (True,False):
                candidates=[(p,d) for p,d in complete if d['benchmark']==bench and d['model']==model and d['score']['correct']==outcome]
                if candidates:sample.append(candidates[len(candidates)//2])
    for p,d in sample:
        c=lookup[(d['benchmark'],d['id'])]
        assert sc[(c['benchmark'],c['id'])](c,p.with_name('response.txt').read_text())==d['score'],(d['benchmark'],d['model'],d['id'])
    science=[];seeds=Counter()
    for k,vs in matched.items():
        if k[0]=='discoveryworld_advanced':seeds[str(vs[0][1]['score']['seed'])]+=1
    for p,d in complete:
        if not d['benchmark'].startswith('discoveryworld'):continue
        science.append((p,d));calls=[json.loads(line) for line in p.with_name('toolcalls.jsonl').read_text().splitlines()]
        assert len(calls)==d['tool_calls'] and calls
        for c in calls:
            assert c['request']['params']['tool'] in {'discoveryworld_act','discoveryworld_observe'}
            assert not any(w in json.dumps(c['result']) for w in ('official_scorecards','criticalHypotheses','criticalQuestions','scoreNormalized'))
    workers=[]
    for line in subprocess.check_output(['ps','-axo','pid=,comm=,args='],text=True).splitlines():
        parts=line.split(None,2)
        if len(parts)==3 and parts[1].split('/')[-1]=='codex' and 'model_providers.sprint_subscription=' in parts[2]:workers.append(parts[0])
    assert not workers,workers
    audit={'checked_at':time.time(),'valid_complete_trials':len(complete),'matched_cases':len(matched),'byte_identical_prompt_cases':len(matched)-len(variants),'runtime_id_variant_cases':variants,'runtime_id_variants_normalized_public_observation_preamble_and_task_hypotheses_match':True,'exact_models_high_default_all_complete':True,'representative_scores_recomputed':len(sample),'science_tool_boundaries_audited':len(science),'advanced_matched_seed_counts':dict(seeds),'owned_model_workers_remaining':workers,'errors':[]}
    runner.save(ROOT/'runtime/final-parent-audit.json',audit);print(json.dumps(audit),flush=True)

if __name__=='__main__':main()
