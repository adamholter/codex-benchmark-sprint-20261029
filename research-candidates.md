# Benchmark research candidates

Researched 2026-10-29 from GitHub repositories and linked papers. Public pages were checked through web search/open; no interactive browser session, paid API, or model inference was used. Setup and five-hour estimates are unverified estimates for small local-model pilots.

Old scores below are historical context. They do not show that current models remain unsaturated.

## Top four to carry forward

1. **[PlanBench](https://github.com/harshakokel/PlanBench)** — best practical planning test. The README's April 2025 static table gives DeepSeek R1 25.8% on randomized Mystery Blocksworld and 53.6% on Blocksworld Hard PDDL. Start with 100 to 200 instances; keep natural-language and PDDL conditions separate.
2. **[DiscoveryWorld](https://github.com/allenai/discoveryworld)** — unusual scientific discovery cycle with simulator scorecards for completion, procedure, and knowledge. Its 2024 GPT-4o ReAct baseline completed 18% of challenge tasks. Start with four to eight fixed-seed scenarios; the full 120-task run may exceed five hours.
3. **[MuSR](https://github.com/Zayne-sprague/MuSR)** — 750 narrative problems split across murder mysteries, object placement, and team allocation. The 2024 paper's best GPT-4 one-shot CoT+ scores were 86.0%, 72.3%, and 86.8%. A balanced local-model pilot is straightforward.
4. **[StepGame](https://github.com/ShiZhengyan/StepGame)** — cheap text-spatial reasoning slice with exact labels. Use the corrected 2024 data and stratify by hop count. Historical paper scores are neural baselines, not current LLM results.

## Candidate inventory

| Candidate | Last substantive repo activity | Separate results update | Historical best found | Five-hour pilot / main caveat |
|---|---|---|---|---|
| [PlanBench](https://github.com/harshakokel/PlanBench) | May 5, 2025 merge; leaderboard README edit April 24 | Static README leaderboard, April 24, 2025 | DeepSeek R1: 25.8% randomized Mystery Blocksworld; 53.6% hard PDDL. [Scores](https://github.com/harshakokel/PlanBench#planbench-static-test-set-leaderboard) | 100–200 local instances plausible; planner setup and output format need pinning. MIT. |
| [MuSR](https://github.com/Zayne-sprague/MuSR) | Code/data circa Oct. 24, 2023; README Jan. 24, 2024; MIT license added Aug. 10, 2024 | No repo leaderboard; [2024 paper](https://arxiv.org/abs/2310.16049) | GPT-4 one-shot CoT+: 86.0% / 72.3% / 86.8% over the three domains | 100–200 local HF items plausible; exact answer scoring. MIT. |
| [StepGame](https://github.com/ShiZhengyan/StepGame) | Corrected data regenerated Feb. 4, 2024; HF release Mar. 4; README Mar. 20 | No official current board; [2024 corrected-data LLM repo](https://github.com/Fangjun-Li/SpatialLM-StepGame) | TP-MANN: 52.99% mean across noisy k=1–5; 31.25% at k=5. [Paper](https://arxiv.org/abs/2204.08292) | 200–500 corrected noisy items plausible; use k=6–10 for generalization. MIT code; data terms not separately stated. |
| [SciBench](https://github.com/mandyyyyii/scibench) | July 8, 2024 | Official site dates GPT evaluations to Mar. 15, 2024 and displays 48.96% overall. [Site](https://scibench-ucla.github.io/) | 48.96% current site aggregate; model name not exposed in the static text. 2023 paper: 43.22% text / 13.8% multimodal / 51.57% closed exam. [Paper](https://arxiv.org/abs/2307.10635) | 50–100 text problems plausible; dataset versions differ and it overlaps quantitative reasoning. MIT. |
| [DiscoveryWorld](https://github.com/allenai/discoveryworld) | Core data release June 2024; non-README cleanup Jan. 21, 2025; README Mar. 10, 2025 | No live board; [NeurIPS 2024 paper](https://openreview.net/forum?id=cDYqckEt6d) | GPT-4o ReAct: 18% challenge completion; Hypothesizer: 8% challenge knowledge score | Install takes minutes; use 4–8 fixed-seed tasks. Full protocol may exceed five hours. Apache-2.0 code; bundled art has separate terms. |
| [AbductionRules](https://github.com/Strong-AI-Lab/AbductionRules) | March 16, 2022 | Results files March 14, 2022; [final paper](https://arxiv.org/abs/2203.12186) | Fine-tuned Transformers reach 100% exact match in some in-domain settings and 0% in some cross-domain settings | 100 items per condition plausible; exact string match is format-sensitive. MIT. |
| [CLUTRR](https://github.com/facebookresearch/clutrr) | Aug. 4, 2021 | No official LLM leaderboard; [2022 follow-up](https://arxiv.org/abs/2201.01787) reports 88.8% for an entity-abstraction model vs. 62.9% baseline | 88.8% is not an LLM score | 200–500 generated held-out cases plausible; synthetic/template leakage risk. CC-BY-NC 4.0 per README; GitHub detector says NOASSERTION. |
| [EntailmentBank](https://github.com/allenai/entailment_bank) | Nov. 5, 2022 scorer update | No leaderboard; [2021 paper](https://aclanthology.org/2021.emnlp-main.585/) | EntailmentWriter AllCorrect: 35.6% Task 1, 25.6% Task 2, 2.9% Task 3 | Small Task 1 pilot plausible, but Python 3.7 and BLEURT checkpoint make fresh setup borderline. Apache-2.0 code; separate data terms not in README. |
| [SpaRTQA](https://github.com/HLR/SpartQA-baselines) | Code May 6, 2021; README March 27, 2023; MIT license added April 2023 | No maintained board; task-specific papers vary in split and metric | A directly comparable top LLM score for the original splits was not established. Do not mix in ReSQ scores. | 100–200 item slice plausible; Drive data and Transformers 4.0.1 are friction. Data license unknown. |
| [FOLIO](https://github.com/Yale-LILY/FOLIO) | Dec. 22, 2023 | No leaderboard; paper results 2022; GitHub README says test set unreleased | RoBERTa-large 62.11%; Codex 8-shot 56.04%. [Paper](https://arxiv.org/abs/2209.00840) | 100–200 labeled dev examples are easy to score, but a held-out test path was not established from GitHub. CC-BY-SA-4.0. |

## Reading the stale-score evidence

- “Last repo activity” and “last score update” are separate. A README, license, or cleanup commit is not automatically a benchmark result.
- **Modern saturation remains unknown** for every candidate here. Several have 2024–2025 results; none of those old results is evidence about a 2026 frontier model.
- Best immediate low-cost slices: PlanBench randomized Mystery Blocksworld, corrected StepGame high-hop noisy examples, and MuSR balanced across all three domains.
- DiscoveryWorld is the most distinctive scientific-discovery task, but use a small fixed-seed pilot before considering the full suite.
- FOLIO and SpaRTQA are lower priority because the public test/data licensing path is unclear. EntailmentBank has more setup friction.

