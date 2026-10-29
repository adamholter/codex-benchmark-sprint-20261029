"""Generate a self-contained, timestamped sprint overview without a web server."""
from collections import Counter
from datetime import datetime
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODELS = ['gpt-6.1-sol', 'gpt-6-astra', 'gpt-6.1-terra', 'gpt-6-luna']
BENCHES = [
    ('BBEH Mini', 'https://github.com/google-deepmind/bbeh', '23 difficult reasoning tasks', 'May 2025', '460'),
    ('KOR-Bench', 'https://github.com/KOR-Bench/KOR-Bench', 'New rules, ciphers and puzzles', 'Oct 2024', '1,250 + 7,000 mixed'),
    ('LingOly', 'https://github.com/am-bean/lingOly', 'Linguistic pattern inference', 'Oct 2024', '204 groups + diagnostic'),
    ('FANToM', 'https://github.com/skywalker023/fantom', 'Who knows what in a conversation', 'May 2024', '6,725 subset questions'),
    ('PlanBench hard', 'https://github.com/harshakokel/PlanBench', 'Executable planning sequences', 'Apr 2025', '110'),
]


def build():
    rows = []
    for p in (ROOT/'runtime/trials').glob('*/status.json'):
        try:
            rows.append(json.loads(p.read_text()))
        except (ValueError, OSError):
            pass
    ready = json.loads((ROOT/'runtime/runner-ready.json').read_text())
    status = Counter(r['status'] for r in rows)
    snapshot = datetime.now().astimezone().strftime('%b %d, %I:%M %p %Z')
    models = ''.join('<div class="model"><div>'+escape(m)+'</div><strong>'+str(sum(r['status']=='complete' and r['model']==m for r in rows))+'</strong><span>completed</span></div>' for m in MODELS)
    benches = ''.join('<tr><td><a href="'+url+'">'+name+'</a><small>'+topic+'</small></td><td>'+date+'</td><td>'+scope+'</td></tr>' for name,url,topic,date,scope in BENCHES)
    run_state = 'Running' if ready['state']=='running' else ready['state'].replace('_',' ').title()
    html = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Codex benchmark sprint</title><style>
    :root{color-scheme:light dark}body{font-family:var(--font-sans,system-ui);color:var(--foreground,#ddd);margin:0;font-size:14px;line-height:1.5}p{margin:0 0 16px}.status{display:flex;gap:12px;flex-wrap:wrap;align-items:center}.dot{background:var(--success,#3a8);width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:6px}.muted,small,.model span{color:var(--muted-foreground,#888)}.models{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:18px 0 24px}.model{padding:16px;border:1px solid var(--border,#555);border-radius:var(--radius,10px)}.model div{font-size:12px;overflow-wrap:anywhere}.model strong{display:block;font-size:28px;margin-top:8px}.model span{font-size:12px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:12px 10px 12px 0;border-bottom:1px solid var(--border,#444);vertical-align:top}th{font-size:11px;color:var(--muted-foreground,#999);font-weight:500}small{display:block;font-size:12px;margin-top:3px}a{color:var(--accent-foreground,#7bbcff);text-decoration:none}footer{font-size:12px;color:var(--muted-foreground,#888);margin-top:16px}@media(max-width:500px){.models{grid-template-columns:repeat(2,minmax(0,1fr))}td,th{font-size:12px}}
    </style></head><body>
    <p class="status"><span><i class="dot"></i><b>STATE</b></span><span>4 workers</span><span>Cutoff 3:10 PM Eastern</span></p>
    <p class="muted">High reasoning · Codex subscription · 28/28 pilot trials completed</p>
    <div class="models">MODELS</div>
    <table><thead><tr><th>BENCHMARK</th><th>LAST RESULTS FOUND</th><th>AVAILABLE CASES</th></tr></thead><tbody>BENCHES</tbody></table>
    <footer>Completed trials are scored and saved as they finish. Old scores are leads for retesting; current saturation is still being measured. Snapshot SNAPSHOT. This embedded view does not refresh.</footer>
    </body></html>'''.replace('STATE',escape(run_state)).replace('MODELS',models).replace('BENCHES',benches).replace('SNAPSHOT',snapshot)
    (ROOT/'overview.html').write_text(html)
    return html


if __name__ == '__main__':
    build()
