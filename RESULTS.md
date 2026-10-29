# Codex benchmark sprint results

2,283 valid completed trials. Six benchmark families, plus separate task variants and diagnostics. All four requested models ran at high reasoning and the default service tier through the Codex subscription. 569 cases completed by all four models, giving 2,276 matched model trials. Seven other valid completions stay in the raw results and outside the comparison.

The batch stopped at 95% account usage at about 1:38 PM Eastern on October 29, before the 3:10 PM cutoff. Credits remained unchanged. The account was shared with other active work, so the change in account usage cannot all be attributed to this sprint.

## Matched results

| Benchmark | Matched sample | Sol | Astra | Terra | Luna |
|---|---:|---:|---:|---:|---:|
| [BBEH Mini](https://github.com/google-deepmind/bbeh) | 76 | 46.1% (35/76) | 47.4% (36/76) | 32.9% (25/76) | 25.0% (19/76) |
| [KOR-Bench core](https://github.com/KOR-Bench/KOR-Bench) | 77 | 88.3% (68/77) | 87.0% (67/77) | 81.8% (63/77) | 71.4% (55/77) |
| [KOR-Bench mixed](https://github.com/KOR-Bench/KOR-Bench) | 77 | 64.9% (50/77) | 67.5% (52/77) | 57.1% (44/77) | 51.9% (40/77) |
| [LingOly](https://github.com/am-bean/lingOly) | 76 groups / 490 parts | 89.2% (437/490) | 90.2% (442/490) | 80.0% (392/490) | 56.3% (276/490) |
| [FANToM subset](https://github.com/skywalker023/fantom) | 77 | 94.8% (73/77) | 92.2% (71/77) | 88.3% (68/77) | 83.1% (64/77) |
| [PlanBench hard](https://github.com/harshakokel/PlanBench) | 78 | 100.0% (78/78) | 100.0% (78/78) | 100.0% (78/78) | 78.2% (61/78) |
| [DiscoveryWorld Normal + Challenge](https://github.com/allenai/discoveryworld) | 27 | 92.6% (25/27) | 100.0% (27/27) | 88.9% (24/27) | 37.0% (10/27) |
| [DiscoveryWorld Easy](https://github.com/allenai/discoveryworld) | 4 | 100.0% (4/4) | 100.0% (4/4) | 100.0% (4/4) | 100.0% (4/4) |
| [LingOly no-context diagnostic](https://github.com/am-bean/lingOly) | 77 groups / 536 parts | 17.5% (94/536) | 19.2% (103/536) | 11.6% (62/536) | 16.2% (87/536) |

Percentages are rounded for reading. results.csv and final-results.json retain full numeric precision. LingOly uses answer-part accuracy in this table; exact group accuracy is separate in the files. Mixed KOR requires every question in a prompt to be correct. FANToM is a deterministic question subset, not its published All or All* metric.

## What separated the models

Astra completed all 27 matched Normal and Challenge science tasks. Sol completed 25, Terra 24, and Luna 10. These cover seven themes across completed seeds 0 and 1. Five seeds were predeclared, but the usage stop left later seeds unrun. This is a custom game-tool agent using official procedural and task-success scores, not a reproduction of the paper leaderboard.

BBEH remained difficult for every model. Mixed KOR and LingOly also separated them. Sol and Astra were close on several static subsets; the small differences do not establish a general winner. Sol, Astra and Terra each solved all 78 tested PlanBench hard instances; Luna solved 61.

## Paired LingOly context diagnostic

The full-context and no-context queues sampled different prefixes. The valid paired diagnostic uses only their 46 shared question groups, with 333 answer parts.

| Model | With context | Without context | Difference |
|---|---:|---:|---:|
| Sol | 90.4% | 22.8% | 67.6 percentage points |
| Astra | 91.0% | 21.9% | 69.1 percentage points |
| Terra | 80.5% | 11.1% | 69.4 percentage points |
| Luna | 54.7% | 17.4% | 37.2 percentage points |

This measures dependence on the supplied context; it does not prove absence of training contamination.

## Scope and exclusions

The queue held more work than the time window could finish. The main batch completed 2,158 trials. Science completed 125: 16 Easy and 109 Normal/Challenge. There were seven interrupted trials, one retained early request-rate failure, and 168 science trials explicitly marked not run. Other unstarted static items remain only in the available queue. Wrong answers and unsuccessful science goals count as completed model trials, not infrastructure errors. The 28 integrated pilot trials and earlier setup attempts are outside the primary comparison.

Gold labels were hidden from model processes. Of 569 matched groups, 567 have byte-identical prompts. Two Space Sick groups vary in runtime object IDs and observation-list order; their normalized initial observations, prompt preambles and official task hypotheses match. The JSON includes science sensitivity excluding these two groups. Exact model, high effort and default tier were checked in resolved sessions. Game tools expose official observations and allowed actions; full scorecards stay evaluator-only. Source snapshots, prompts, raw event streams, responses, tool calls and scores are preserved.

KOR scoring preserves 12 supplied puzzle answers rejected by the pinned scorer. LingOly preserves the repository scorer, including credit for empty gold answers; the JSON includes a sensitivity excluding those parts. PlanBench replaces VAL with a local STRIPS simulator checked against all 110 source reference plans. Initial broken tool connections were archived and excluded. Native context compaction was audited and distinguished from forbidden tool activity.

## Files

- final-results.json: exact summary, paired diagnostics, token counts and audit.
- results.csv: exact matched metrics, observed latency and token components.
- runtime/combined-results.json: unified category metrics and every persisted primary trial status.
- protocol.json, research-*.json and BENCHMARKS.md: selection, source commits, dates, historical results and scoring limits.
- runtime/trials and discoveryworld/*/results: raw per-trial evidence.
- research-candidates.md: broader candidates researched but not all evaluated.

Validation: 21 tests passed. Parent audit checked all 2,283 complete session resolutions, all 569 matched initial conditions, representative score recomputation, all 125 science tool boundaries and no remaining owned model workers.
