"""Freeze exact matched metrics and a readable report after all model jobs stop."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import statistics
import time
import combined_report
import runner

ROOT = Path(__file__).resolve().parent
MODELS = runner.MODELS
LABELS = {'gpt-6.1-sol':'Sol','gpt-6-astra':'Astra','gpt-6.1-terra':'Terra','gpt-6-luna':'Luna'}
BENCHMARKS = [
    ('bbeh','BBEH Mini','https://github.com/google-deepmind/bbeh','Exact answer'),
    ('korbench','KOR-Bench core','https://github.com/KOR-Bench/KOR-Bench','Exact answer'),
    ('korbench_mixed','KOR-Bench mixed','https://github.com/KOR-Bench/KOR-Bench','All questions correct'),
    ('lingoly','LingOly','https://github.com/am-bean/lingOly','Answer parts correct'),
    ('fantom','FANToM subset','https://github.com/skywalker023/fantom','Question accuracy'),
    ('PlanBench Blocksworld Hard - PDDL','PlanBench hard','https://github.com/harshakokel/PlanBench','Executable plan succeeds'),
    ('discoveryworld_advanced','DiscoveryWorld Normal + Challenge','https://github.com/allenai/discoveryworld','Official task success'),
    ('discoveryworld','DiscoveryWorld Easy','https://github.com/allenai/discoveryworld','Official task success'),
    ('lingoly_no_context','LingOly no-context diagnostic','https://github.com/am-bean/lingOly','Answer parts correct'),
]


def pct(x):
    return 'n/a' if x is None else f'{100*x:.1f}%'


def tokens(rows):
    counts=Counter()
    for row in rows:
        counts.update({k:v for k,v in ((row.get('usage') or {}).get('total') or {}).items() if isinstance(v,(int,float))})
    return dict(counts)


def main():
    combined=combined_report.build()
    rows=combined['trials']
    index=defaultdict(dict)
    for row in rows:
        if row['status']=='complete':index[(row['benchmark'],row['id'])][row['model']]=row
    matched={key:value for key,value in index.items() if set(MODELS)<=set(value)}
    metrics=[]
    for benchmark,title,url,metric in BENCHMARKS:
        keys=sorted(key for key in matched if key[0]==benchmark)
        for model in MODELS:
            chosen=[matched[key][model] for key in keys]
            correct=sum(bool(row['score']['correct']) for row in chosen)
            parts_total=sum(row['score'].get('parts_total',0) for row in chosen)
            parts_correct=sum(row['score'].get('parts_correct',0) for row in chosen)
            primary_correct=parts_correct if parts_total else correct
            primary_total=parts_total if parts_total else len(chosen)
            metrics.append({'benchmark':benchmark,'title':title,'source':url,'metric':metric,'model':model,
                            'matched_cases':len(chosen),'correct_cases':correct,
                            'case_accuracy':correct/len(chosen) if chosen else None,
                            'primary_correct':primary_correct,'primary_total':primary_total,
                            'primary_accuracy':primary_correct/primary_total if primary_total else None,
                            'parts_correct':parts_correct,'parts_total':parts_total,
                            'mean_score':statistics.mean(row['score'].get('score',row['score'].get('pass_rate',float(row['score']['correct']))) for row in chosen) if chosen else None,
                            'mean_seconds':statistics.mean(row['seconds'] for row in chosen) if chosen else None,
                            'median_seconds':statistics.median(row['seconds'] for row in chosen) if chosen else None,
                            'tokens':tokens(chosen)})
    # A no-context delta is valid only on identical question groups in BOTH conditions.
    full={key[1].rsplit(':',1)[0]:value for key,value in matched.items() if key[0]=='lingoly'}
    no_context={key[1].rsplit(':',1)[0]:value for key,value in matched.items() if key[0]=='lingoly_no_context'}
    paired_keys=sorted(set(full)&set(no_context))
    paired=[]
    for model in MODELS:
        a=[full[key][model] for key in paired_keys];b=[no_context[key][model] for key in paired_keys]
        total=sum(row['score']['parts_total'] for row in a)
        with_context=sum(row['score']['parts_correct'] for row in a)
        without_context=sum(row['score']['parts_correct'] for row in b)
        assert total==sum(row['score']['parts_total'] for row in b)
        paired.append({'model':model,'groups':len(paired_keys),'parts':total,'full_correct':with_context,'no_context_correct':without_context,
                       'full_accuracy':with_context/total if total else None,'no_context_accuracy':without_context/total if total else None,
                       'delta':(with_context-without_context)/total if total else None})
    # Preserve repository scoring as primary, and expose its empty-label sensitivity.
    cases,_=runner.discover();case_map={(c['benchmark'],c['id']):c for c in cases}
    sensitivity=[]
    for model in MODELS:
        for benchmark in ('lingoly','lingoly_no_context'):
            parts=correct=groups=0
            for key,values in matched.items():
                if key[0]!=benchmark:continue
                gold=case_map[key]['gold'];scores=values[model]['score']['part_scores'];used=0
                for part,label in gold.items():
                    if label in ('',None,[]):continue
                    parts+=1;used+=1;correct+=scores[str(part)]
                groups+=bool(used)
            sensitivity.append({'benchmark':benchmark,'model':model,'nonempty_groups':groups,'nonempty_parts':parts,'correct':correct,'accuracy':correct/parts if parts else None})
    ready=json.loads((ROOT/'runtime/runner-ready.json').read_text())
    audit=json.loads((ROOT/'runtime/final-parent-audit.json').read_text())
    summary={'generated_at':time.time(),'valid_completed_trials':sum(row['status']=='complete' for row in rows),
             'matched_cases':len(matched),'matched_model_trials':len(matched)*len(MODELS),
             'valid_unmatched_completed_trials':sum(row['status']=='complete' for row in rows)-len(matched)*len(MODELS),
             'status_counts':dict(Counter(row['status'] for row in rows)),
             'completed_by_model':dict(Counter(row['model'] for row in rows if row['status']=='complete')),
             'completed_by_benchmark':dict(Counter(row['benchmark'] for row in rows if row['status']=='complete')),
             'models':MODELS,'effort':'high','service_tier':'default','credit_balance_at_stop':ready['quota']['credit_balance'],
             'credit_unchanged':ready['credit_unchanged'],'usage_percent_at_stop':95,
             'stop_reason':'95 percent subscription headroom cutoff','raw_stop_reason':ready['stop_reason'],
             'subscription_transport':'ChatGPT OAuth via Codex app-server; no API-key route or paid fallback',
             'integrated_pilot_trials_separate_from_primary_results':28,
             'available_queue_model_trials':63812+16+32+248,
             'primary_metrics':metrics,'lingoly_paired_context':paired,'lingoly_nonempty_label_sensitivity':sensitivity,
             'tokens_all_persisted_trials':tokens(rows),'tokens_all_complete_trials':tokens([row for row in rows if row['status']=='complete']),
             'audit':audit,'comparability':'Single-attempt time-bounded subsets, matched complete cases only. No overall composite score. DiscoveryWorld uses a custom agent and no knowledge judge.'}
    runtime_id_cases={tuple(key) for key in audit.get('runtime_id_variant_cases',[])}
    science_sensitivity=[]
    for model in MODELS:
        chosen=[value[model] for key,value in matched.items() if key[0]=='discoveryworld_advanced' and key not in runtime_id_cases]
        correct=sum(row['score']['correct'] for row in chosen)
        science_sensitivity.append({'model':model,'cases':len(chosen),'correct':correct,'accuracy':correct/len(chosen) if chosen else None})
    summary['science_byte_identical_prompt_sensitivity']=science_sensitivity
    runner.save(ROOT/'final-results.json',summary)
    fields=['benchmark','title','metric','model','matched_cases','correct_cases','case_accuracy','primary_correct','primary_total','primary_accuracy','parts_correct','parts_total','mean_score','mean_seconds','median_seconds','tokens','source']
    with (ROOT/'results.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        writer.writerows(dict(row,tokens=json.dumps(row['tokens'])) for row in metrics)
    lines=['# Codex benchmark sprint results','',
           '2,283 valid completed trials. Six benchmark families, plus separate task variants and diagnostics. All four requested models ran at high reasoning and the default service tier through the Codex subscription. 569 cases completed by all four models, giving 2,276 matched model trials. Seven other valid completions stay in the raw results and outside the comparison.',
           '', 'The batch stopped at 95% account usage at about 1:38 PM Eastern on October 29, before the 3:10 PM cutoff. Credits remained unchanged. The account was shared with other active work, so the change in account usage cannot all be attributed to this sprint.',
           '', '## Matched results','', '| Benchmark | Matched sample | Sol | Astra | Terra | Luna |','|---|---:|---:|---:|---:|---:|']
    for benchmark,title,url,metric in BENCHMARKS:
        selected=[next(row for row in metrics if row['benchmark']==benchmark and row['model']==model) for model in MODELS]
        sample=str(selected[0]['matched_cases'])
        if selected[0]['parts_total']:sample+=f" groups / {selected[0]['parts_total']} parts"
        cells=[f"{pct(row['primary_accuracy'])} ({row['primary_correct']}/{row['primary_total']})" for row in selected]
        lines.append('| ['+title+']('+url+') | '+sample+' | '+' | '.join(cells)+' |')
    lines+=['', 'Percentages are rounded for reading. results.csv and final-results.json retain full numeric precision. LingOly uses answer-part accuracy in this table; exact group accuracy is separate in the files. Mixed KOR requires every question in a prompt to be correct. FANToM is a deterministic question subset, not its published All or All* metric.',
            '', '## What separated the models','',
            'Astra completed all 27 matched Normal and Challenge science tasks. Sol completed 25, Terra 24, and Luna 10. These cover seven themes across completed seeds 0 and 1. Five seeds were predeclared, but the usage stop left later seeds unrun. This is a custom game-tool agent using official procedural and task-success scores, not a reproduction of the paper leaderboard.',
            '', 'BBEH remained difficult for every model. Mixed KOR and LingOly also separated them. Sol and Astra were close on several static subsets; the small differences do not establish a general winner. Sol, Astra and Terra each solved all 78 tested PlanBench hard instances; Luna solved 61.',
            '', '## Paired LingOly context diagnostic','',
            f"The full-context and no-context queues sampled different prefixes. The valid paired diagnostic uses only their {len(paired_keys)} shared question groups, with {paired[0]['parts']} answer parts.",
            '', '| Model | With context | Without context | Difference |','|---|---:|---:|---:|']
    for row in paired:lines.append(f"| {LABELS[row['model']]} | {pct(row['full_accuracy'])} | {pct(row['no_context_accuracy'])} | {100*row['delta']:.1f} percentage points |")
    lines+=['', 'This measures dependence on the supplied context; it does not prove absence of training contamination.',
            '', '## Scope and exclusions','',
            'The queue held more work than the time window could finish. The main batch completed 2,158 trials. Science completed 125: 16 Easy and 109 Normal/Challenge. There were seven interrupted trials, one retained early request-rate failure, and 168 science trials explicitly marked not run. Other unstarted static items remain only in the available queue. Wrong answers and unsuccessful science goals count as completed model trials, not infrastructure errors. The 28 integrated pilot trials and earlier setup attempts are outside the primary comparison.',
            '', 'Gold labels were hidden from model processes. Of 569 matched groups, 567 have byte-identical prompts. Two Space Sick groups vary in runtime object IDs and observation-list order; their normalized initial observations, prompt preambles and official task hypotheses match. The JSON includes science sensitivity excluding these two groups. Exact model, high effort and default tier were checked in resolved sessions. Game tools expose official observations and allowed actions; full scorecards stay evaluator-only. Source snapshots, prompts, raw event streams, responses, tool calls and scores are preserved.',
            '', 'KOR scoring preserves 12 supplied puzzle answers rejected by the pinned scorer. LingOly preserves the repository scorer, including credit for empty gold answers; the JSON includes a sensitivity excluding those parts. PlanBench replaces VAL with a local STRIPS simulator checked against all 110 source reference plans. Initial broken tool connections were archived and excluded. Native context compaction was audited and distinguished from forbidden tool activity.',
            '', '## Files','',
            '- final-results.json: exact summary, paired diagnostics, token counts and audit.',
            '- results.csv: exact matched metrics, observed latency and token components.',
            '- runtime/combined-results.json: unified category metrics and every persisted primary trial status.',
            '- protocol.json, research-*.json and BENCHMARKS.md: selection, source commits, dates, historical results and scoring limits.',
            '- runtime/trials and discoveryworld/*/results: raw per-trial evidence.',
            '- research-candidates.md: broader candidates researched but not all evaluated.',
            '', 'Validation: 21 tests passed. Parent audit checked all 2,283 complete session resolutions, all 569 matched initial conditions, representative score recomputation, all 125 science tool boundaries and no remaining owned model workers.']
    (ROOT/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'completed':summary['valid_completed_trials'],'matched_cases':summary['matched_cases'],'paired_lingoly':paired}))


if __name__=='__main__':
    main()
