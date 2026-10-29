"""One registry and one result table for static and interactive benchmark tracks."""
from collections import defaultdict
import json
from pathlib import Path
import time
import reporting
import runner

ROOT = Path(__file__).resolve().parent


def build():
    cases,_ = runner.discover()
    planned = [(model,case) for model in runner.MODELS for case in cases]
    for case in json.loads((ROOT/'discoveryworld/scenarios.json').read_text())[:4]:
        c = {'benchmark':'discoveryworld','category':case['scenario'],
             'id':case['scenario'].lower().replace(' ','-')}
        planned.extend((model,c) for model in runner.MODELS)
    areas=[ROOT/'runtime/trials',ROOT/'discoveryworld/results']
    for folder in ('advanced','expanded'):
        area=ROOT/'discoveryworld'/folder
        protocol=area/'protocol.json'
        if protocol.exists():
            cases=json.loads(protocol.read_text())['cases']
            planned.extend((model,case) for model in runner.MODELS for case in cases)
            areas.append(area/'results')
    keys=[(model,case['benchmark'],case['id']) for model,case in planned]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate planned model/case in combined registry')
    rows = []
    seen=set()
    for area in areas:
        for path in area.glob('*/status.json'):
            row=json.loads(path.read_text());key=(row['model'],row['benchmark'],row['id'])
            if key in seen:raise ValueError('Duplicate trial in combined reports: '+str(key))
            seen.add(key);rows.append(row)
    result = reporting.aggregate(rows,runner.MODELS,planned)
    groups = defaultdict(list)
    for row in result['metrics']:
        groups[(row['benchmark'],row['model'])].append(row)
    summary = []
    for (benchmark,model),metrics in sorted(groups.items()):
        matched_n = sum(m['matched_n'] for m in metrics)
        parts = sum(m['matched_parts_total'] for m in metrics)
        completed = sum(m['completed'] for m in metrics)
        summary.append({'benchmark':benchmark,'model':model,
                        'completed':completed,'planned':sum(m['planned'] for m in metrics),
                        'matched_n':matched_n,
                        'matched_accuracy':sum(m['matched_correct'] for m in metrics)/matched_n if matched_n else None,
                        'matched_mean_score':sum((m['matched_mean_score'] or 0)*m['matched_n'] for m in metrics)/matched_n if matched_n else None,
                        'matched_parts':parts,
                        'matched_part_accuracy':sum(m['matched_parts_correct'] for m in metrics)/parts if parts else None,
                        'errors':sum(m['errors'] for m in metrics),
                        'missing':sum(m['missing'] for m in metrics)})
    result['benchmark_summary'] = summary
    result['generated_at'] = time.time()
    result['scope'] = 'Main static trials and valid interactive attempts. Pilots in separate runtime/pilot evidence; invalid pre-fix DiscoveryWorld attempt archived and excluded.'
    runner.save(ROOT/'runtime/combined-results.json',result)
    return result


if __name__ == '__main__':
    result = build()
    print(json.dumps({'trials':len(result['trials']),'matched_cases':result['matched_cases']}))
