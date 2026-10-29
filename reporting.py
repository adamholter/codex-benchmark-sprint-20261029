"""Unified full-denominator and matched-completion benchmark reporting."""
import csv,json
from collections import defaultdict
from pathlib import Path

def aggregate(rows,models,planned):
    groups=defaultdict(list);completed=defaultdict(set)
    for r in rows:
        groups[(r['model'],r['benchmark'],r['category'])].append(r)
        if r['status']=='complete':completed[(r['benchmark'],r['id'])].add(r['model'])
    matched={k for k,v in completed.items() if set(models)<=v}
    expected=defaultdict(int)
    for m,c in planned:expected[(m,c['benchmark'],c['category'])]+=1
    metrics=[]
    for key,total in sorted(expected.items()):
        records=groups[key];done=[r for r in records if r['status']=='complete'];subset=[r for r in done if (r['benchmark'],r['id']) in matched]
        correct=sum(bool(r.get('score',{}).get('correct',False)) for r in done)
        counts={s:sum(r['status']==s for r in records) for s in sorted({r['status'] for r in records})}
        tokens=defaultdict(int)
        for r in records:
            for k,v in ((r.get('usage') or {}).get('total') or {}).items():
                if isinstance(v,(int,float)):tokens[k]+=v
        metrics.append(dict(model=key[0],benchmark=key[1],category=key[2],planned=total,completed=len(done),correct=correct,accuracy=correct/total if total else None,completed_accuracy=correct/len(done) if done else None,missing=total-len(records),timeouts=counts.get('timeout',0),errors=sum(v for k,v in counts.items() if k!='complete'),status_counts=counts,matched_n=len(subset),matched_correct=sum(bool(r.get('score',{}).get('correct')) for r in subset),matched_accuracy=sum(bool(r.get('score',{}).get('correct')) for r in subset)/len(subset) if subset else None,total_seconds=sum(r.get('seconds',0) for r in records),tokens=dict(tokens)))
        for label,selected in [('completed',done),('matched',subset)]:
            numeric=[r['score'].get('score',r['score'].get('pass_rate',float(r['score']['correct']))) for r in selected]
            metrics[-1][label+'_mean_score']=sum(numeric)/len(numeric) if numeric else None
            parts=[r['score'] for r in selected if 'parts_total' in r.get('score',{})]
            parts_total=sum(p['parts_total'] for p in parts)
            metrics[-1][label+'_parts_total']=parts_total
            metrics[-1][label+'_parts_correct']=sum(p['parts_correct'] for p in parts)
            metrics[-1][label+'_part_accuracy']=sum(p['parts_correct'] for p in parts)/parts_total if parts_total else None
    return {'metrics':metrics,'matched_cases':len(matched),'trials':rows}
def report(runtime,area,models,planned):
    from runner import save
    rows=[json.loads(p.read_text()) for p in sorted((runtime/area).glob('*/status.json'))]
    result=aggregate(rows,models,planned)
    for scope in ['benchmark','model']:
        rolled_rows=[dict(r,category='__all__',**({'benchmark':'__all__'} if scope=='model' else {})) for r in rows]
        rolled_plan=[(m,dict(c,category='__all__',**({'benchmark':'__all__'} if scope=='model' else {}))) for m,c in planned]
        # IDs include the original benchmark for cross-benchmark rollups.
        if scope=='model':
            for original,rolled in zip(rows,rolled_rows):rolled['id']=original['benchmark']+'::'+str(original['id'])
            for (_,original),(_,rolled) in zip(planned,rolled_plan):rolled['id']=original['benchmark']+'::'+str(original['id'])
        result['metrics'].extend(aggregate(rolled_rows,models,rolled_plan)['metrics'])
    save(runtime/(area+'-results.json'),result)
    for suffix,records in [('metrics',result['metrics']),('trials',rows)]:
        path=runtime/(area+'-'+suffix+'.csv');tmp=path.with_suffix('.pending')
        fields=sorted({k for r in records for k in r})
        with tmp.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
            for r in records:writer.writerow({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()})
        tmp.replace(path)
    return result
