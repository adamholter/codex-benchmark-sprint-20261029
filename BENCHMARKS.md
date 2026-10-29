Completed at the 95% subscription cutoff. See [RESULTS.md](RESULTS.md) for the final comparison.

# Benchmarks selected for this sprint

All source snapshots were checked on October 29, 2026. Older scores explain why these were worth retesting. They do not establish how difficult the tasks remain for current models.

| Benchmark | What it tests | Last results update found | Historical result | Run scope |
|---|---|---|---|---|
| [BBEH](https://github.com/google-deepmind/bbeh) | 23 difficult reasoning tasks, including spatial reasoning, unreliable tables, causality and zebra puzzles | May 6, 2025 leaderboard commit | o3-mini high, 56.7% on Mini | Official 460-case Mini, official scorer |
| [KOR-Bench](https://github.com/KOR-Bench/KOR-Bench) | Applying unfamiliar rules, ciphers and puzzle constraints | October 15, 2024 leaderboard submission | o1-preview, 72.88% core; 36.8% puzzles | 1,250 core cases and 7,000 mixed-rule cases, separate tracks |
| [LingOly](https://github.com/am-bean/lingOly) | Inferring language rules from linguistics olympiad problems | October 31, 2024 paper revision | Claude Opus, 46.3% overall; 38.7% on harder problems | 204 question groups, 1,133 answer parts, plus paired no-context diagnostic |
| [FANToM](https://github.com/skywalker023/fantom) | Tracking who knows what during a conversation | May 31, 2024 repository results commit | GPT-4o, 2.0% All score | 6,725 deterministic questions about inaccessible information; subset accuracy is a different metric from All |
| [PlanBench](https://github.com/harshakokel/PlanBench) | Generating long executable action sequences | April 24, 2025 leaderboard edit | DeepSeek R1, 53.6% on hard PDDL | All 110 Blocksworld Hard PDDL instances; simulator accepts any valid goal-reaching plan |

The four requested models use identical prompts, high reasoning and the default service tier through signed-in Codex. Each trial starts a fresh session. Workers cannot read the benchmark files, gold labels or other trials, and have no shell or web tools.

The queue rotates benchmarks, categories and models. It stops at 3:10 PM Eastern, or sooner at a subscription limit, 95% usage, a changed credit balance or failed usage check. The full queue contains 63,812 available model trials. This is capacity for the time window, not a promise to finish every item.

Model comparisons use cases completed by all four models. Reports also show unfinished work, errors, tokens and latency. LingOly reports answer-part accuracy separately from exact question-group accuracy. Its no-context diagnostic is separate from the main benchmark.

Source quirks remain visible. KOR-Bench's scoring rules reject 12 supplied puzzle answers. LingOly's repository scorer awards credit to empty gold answers, including 12 groups containing only empty answers. PlanBench uses a local STRIPS simulator instead of VAL; all 110 official reference plans pass it. These choices and hashes are recorded in protocol.json and research manifests.

The broader [candidate inventory](research-candidates.md) includes DiscoveryWorld, MuSR, corrected high-hop StepGame, SciBench, AbductionRules, CLUTRR, EntailmentBank, SpaRTQA and FOLIO. DiscoveryWorld added 125 completed model trials across Easy, Normal and Challenge diagnostics. See the final report for completed seed coverage and exclusions. The others remain researched candidates, not completed evaluations.
