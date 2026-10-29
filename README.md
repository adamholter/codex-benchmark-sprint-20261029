Completed at the 95% subscription cutoff. See [RESULTS.md](RESULTS.md) for the final comparison.

# Benchmark sprint

Python standard library, installed Codex CLI, macOS sandbox-exec, existing ChatGPT OAuth login. No API keys or API fallback. Own outputs live under runtime/. Adapters and sources are read only to the controller, denied to child model processes.

Run `npm run validate`, then `python3 runner.py --pilot --workers 4`. The pilot uses one deterministic dataset case across all four models, or an explicitly labeled smoke inference if no adapters exist.

Start the background sprint after adapter integration with `nohup python3 runner.py --run --workers 8 --deadline EPOCH > runtime/launcher.log 2>&1 &`. Replace EPOCH with the agreed absolute Unix deadline. Nothing starts a long run automatically. Same command resumes interrupted cases. Terminal failures and quota stops are never retried. Stop with SIGTERM to the controller. Its signal handler stops dispatch and terminates task-owned process groups. The overlap flock prevents a second runner.

Exact models are gpt-6.1-sol, gpt-6-astra, gpt-6.1-terra, gpt-6-luna. High reasoning, default service, no fast mode. Fresh ephemeral thread for every case, plain prompt and plain response, no JSON output schema. Thread resolution is checked before inference. A custom catalog supplies model metadata but does not establish route availability. Saved successful pilot inference establishes that separately.

Adapters expose `load_cases()` and `score(case, response)`. Cases require benchmark, id, category, prompt, gold, with optional metadata. Case IDs must be unique within each benchmark. Deterministic scheduling cycles benchmarks, categories and all four models. Queue order is reconstructed from a fingerprinted manifest. Running/interrupted entries resume; completed and terminal failed entries remain final. A changed dataset manifest fails closed.

Each trial saves prompt.txt, response.txt, events.jsonl, stderr.txt, resolved-thread.json, status.json. Gold stays only in the controller. Built-in tools, shell, web, apps, MCP and skills are disabled. Unexpected tool activity invalidates the trial. OS isolation denies reading this project, memories, sessions and other trial folders. Child environment includes no API credentials. Each trial lasts at most 900 seconds and is labeled timeout if exceeded. The controller checks deadline throughout inference and stops before a quota reset.

The runner caps concurrency at eight and reduces it when macOS memory headroom is low. It starts no browser or Docker. Quota is checked every ten seconds, and stops at 95% usage, leaving headroom for concurrent requests. A terminal429, usage limit, failed quota check, reset, deadline or changed credits globally stops dispatch and active inference. Native bounded reconnects with willRetry=true are retained as diagnostics. Usage exhaustion and terminal rate limits stop the batch. No failed terminal attempt is retried. Incomplete interrupted attempts are archived before resumption. The current run uses four workers, at most two per model, and a two-second gap between starts.

The account has credits available, so the controller requires active ordinary subscription usage below 95%. It stops all owned requests at that cutoff and compares the credit balance throughout. No API key or paid fallback is available to workers. Account billing settings stay unchanged. The four-model pilot completed through the subscription route with an unchanged credit balance.

runtime/runner-ready.json contains the parent handoff, chosen CLI, quota, billing blocker and actual inference verification. runtime/pilot-results.json and pilot metrics/trials CSV retain the pilot. Unified trial JSON/CSV and grouped model, benchmark, category metrics report full planned-denominator accuracy, completed accuracy, missing/error/timeout counts, tokens and latency. Matched accuracy uses only cases completed by all four models and is separate. Missing means no persisted status, while interrupted/running records count as noncomplete. These are adapter-defined scores, not an assertion of official benchmark reproduction.


See [BENCHMARK-OWNERS.md](BENCHMARK-OWNERS.md) for benchmark maintainers. Raw event streams and session files were left out; prompts, responses and scores per trial are in runtime/trials.
