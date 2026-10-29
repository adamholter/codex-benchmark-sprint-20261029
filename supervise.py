"""Read-only run supervision; controller owns all worker cleanup and limits."""
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import time
import runner

ROOT = Path(__file__).resolve().parent


def snapshot(pid):
    proc = subprocess.run(['ps','-p',str(pid),'-o','stat=,command='],capture_output=True,text=True).stdout.strip()
    alive = bool(proc) and not proc.startswith('Z') and str(ROOT/'runner.py') in proc
    rows = []
    for path in (ROOT/'runtime/trials').glob('*/status.json'):
        try:
            rows.append(json.loads(path.read_text()))
        except (OSError, ValueError):
            continue
    ready = json.loads((ROOT/'runtime/runner-ready.json').read_text())
    latest = json.loads((ROOT/'runtime/quota-latest.json').read_text())
    latest.pop('account',None)
    return {'pid':pid,'alive':alive,'controller_state':ready['state'],
            'checked_at':time.time(),'deadline':1793301000,
            'status_counts':dict(Counter(r['status'] for r in rows)),
            'completed_by_model':dict(Counter(r['model'] for r in rows if r['status']=='complete')),
            'completed_by_benchmark':dict(Counter(r['benchmark'] for r in rows if r['status']=='complete')),
            'last_completion':max((r.get('finished_at',0) for r in rows),default=0),
            'quota':latest,'stop_reason':ready.get('stop_reason')}


def main():
    launch = json.loads((ROOT/'runtime/launcher.json').read_text())
    pid = launch['pid']
    while True:
        state = snapshot(pid)
        runner.save(ROOT/'runtime/supervisor.json',state)
        try:
            import make_overview
            make_overview.build()
        except Exception:
            pass
        if not state['alive']:
            runner.save(ROOT/'runtime/static-finished.json',state)
            print(json.dumps(state),flush=True)
            return
        time.sleep(30)


if __name__ == '__main__':
    main()
