# Static benchmark results

Controller 72700 exited. State finished, stop reason `global stop`. No restart.

52 main trials completed. Astra 12, Sol 13, Terra 14, Luna 13. 1 quota_stop and 4 interrupted records. 28 prior pilots excluded.

Credit balance unchanged at 62500.0000000000. Subscription usage 9%.

Matched accuracy below uses shared completed cases, 11 cases across benchmarks. Sample is incomplete.

| Benchmark | Model | Matched correct/n | Accuracy | Completed | Missing | Errors | Seconds | Total tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PlanBench Blocksworld Hard - PDDL | gpt-6-astra | 4/4 | 1.0 | 4 | 216 | 0 | 92.92488924995996 | 18828 |
| PlanBench Blocksworld Hard - PDDL | gpt-6-luna | 2/4 | 0.5 | 4 | 216 | 0 | 67.80252150003798 | 21626 |
| PlanBench Blocksworld Hard - PDDL | gpt-6.1-sol | 4/4 | 1.0 | 4 | 216 | 0 | 96.52745066629723 | 20000 |
| PlanBench Blocksworld Hard - PDDL | gpt-6.1-terra | 4/4 | 1.0 | 4 | 214 | 2 | 32.76428891601972 | 18432 |
| __all__ | gpt-6-astra | 9/11 | 0.8181818181818182 | 12 | 15939 | 2 | 222.20687350002117 | 55527 |
| __all__ | gpt-6-luna | 8/11 | 0.7272727272727273 | 13 | 15939 | 1 | 161.57323816628195 | 67834 |
| __all__ | gpt-6.1-sol | 8/11 | 0.7272727272727273 | 13 | 15939 | 1 | 217.85733187524602 | 61690 |
| __all__ | gpt-6.1-terra | 9/11 | 0.8181818181818182 | 14 | 15938 | 1 | 108.96436570968945 | 66473 |
| bbeh | gpt-6-astra | 2/2 | 1.0 | 2 | 916 | 2 | 23.070445416262373 | 10070 |
| bbeh | gpt-6-luna | 2/2 | 1.0 | 4 | 916 | 0 | 42.957524500088766 | 22528 |
| bbeh | gpt-6.1-sol | 2/2 | 1.0 | 4 | 916 | 0 | 49.64037849986926 | 20762 |
| bbeh | gpt-6.1-terra | 2/2 | 1.0 | 4 | 916 | 0 | 28.22938341787085 | 20704 |
| fantom | gpt-6-astra | 4/4 | 1.0 | 4 | 13446 | 0 | 40.001793500036 | 19740 |
| fantom | gpt-6-luna | 4/4 | 1.0 | 4 | 13446 | 0 | 22.90024183411151 | 20286 |
| fantom | gpt-6.1-sol | 4/4 | 1.0 | 4 | 13446 | 0 | 28.866910584038123 | 19776 |
| fantom | gpt-6.1-terra | 4/4 | 1.0 | 4 | 13446 | 0 | 26.264290833845735 | 19924 |
| korbench | gpt-6-astra | 4/4 | 1.0 | 4 | 2496 | 0 | 19.79522566590458 | 17160 |
| korbench | gpt-6-luna | 4/4 | 1.0 | 4 | 2496 | 0 | 17.41209174809046 | 17260 |
| korbench | gpt-6.1-sol | 4/4 | 1.0 | 4 | 2496 | 0 | 15.966027000220492 | 17196 |
| korbench | gpt-6.1-terra | 4/4 | 1.0 | 4 | 2496 | 0 | 18.10869299992919 | 17160 |
| korbench_mixed | gpt-6-astra | 4/4 | 1.0 | 4 | 13996 | 0 | 41.913412583991885 | 19184 |
| korbench_mixed | gpt-6-luna | 4/4 | 1.0 | 4 | 13996 | 0 | 13.839745500124991 | 19010 |
| korbench_mixed | gpt-6.1-sol | 2/4 | 0.5 | 4 | 13996 | 0 | 22.858235999941826 | 19052 |
| korbench_mixed | gpt-6.1-terra | 4/4 | 1.0 | 4 | 13996 | 0 | 20.034380999859422 | 18788 |
| lingoly | gpt-6-astra | 0/2 | 0.0 | 2 | 404 | 2 | 170.9120653339196 | 8944 |
| lingoly | gpt-6-luna | 0/2 | 0.0 | 4 | 404 | 0 | 105.96734150010161 | 26764 |
| lingoly | gpt-6.1-sol | 0/2 | 0.0 | 2 | 404 | 2 | 169.2881921660155 | 9068 |
| lingoly | gpt-6.1-terra | 0/2 | 0.0 | 4 | 404 | 0 | 74.15303383395076 | 21016 |
| lingoly_no_context | gpt-6-astra | 0/2 | 0.0 | 4 | 404 | 0 | 55.79591524996795 | 17128 |
| lingoly_no_context | gpt-6-luna | 0/2 | 0.0 | 2 | 404 | 2 | 52.26700975000858 | 8194 |
| lingoly_no_context | gpt-6.1-sol | 0/2 | 0.0 | 4 | 404 | 0 | 52.567468834109604 | 17526 |
| lingoly_no_context | gpt-6.1-terra | 0/2 | 0.0 | 4 | 404 | 0 | 18.374660417903215 | 16922 |

Missing counts follow source metrics. Errors and interrupted records, token breakdowns, and mean latency are preserved in runtime/static-final-summary.json.

`npm run validate` passed, exit 0. 14 tests passed in 1.496s, plus nested isolation test passed in 1.250s.

Process PID/PPID/command inspection found no static CLI workers with literal `model_provider=sprint_subscription` arguments. No processes killed.

Noncomplete records:

```json
[
  {
    "model": "gpt-6.1-terra",
    "benchmark": "PlanBench Blocksworld Hard - PDDL",
    "id": "instance-63",
    "status": "interrupted",
    "errors": [
      "global stop or deadline"
    ],
    "seconds": 1.107982625020668,
    "native_retry_notices": []
  },
  {
    "model": "gpt-6-astra",
    "benchmark": "bbeh",
    "id": "mini:boolean_expressions:0212",
    "status": "quota_stop",
    "errors": [
      "subscription quota/limit failure: {\"method\": \"error\", \"params\": {\"error\": {\"message\": \"Reconnecting... 1/5\", \"codexErrorInfo\": {\"responseStreamDisconnected\": {\"httpStatusCode\": 429}}, \"additionalDetails\": \"exceeded retry limit, last status: 429 Too Many Requests, request id: be637a43-1aeb-44d8-975b-983f17d428a3\", \"misalignment\": null}, \"willRetry\": true, \"threadId\": \"01a18814-89e4-7810-bc49-ec0ef223358c\", \"turnId\": \"01a18814-8a3b-7aa0-94f0-ca98f02b649e\"}, \"emittedAtMs\": 1793284410801}"
    ],
    "seconds": 1.6545957500347868,
    "native_retry_notices": null
  },
  {
    "model": "gpt-6.1-sol",
    "benchmark": "lingoly",
    "id": "187:Q 2.2:full_context",
    "status": "interrupted",
    "errors": [
      "global stop or deadline"
    ],
    "seconds": 75.5290025830036,
    "native_retry_notices": []
  },
  {
    "model": "gpt-6-astra",
    "benchmark": "lingoly",
    "id": "187:Q 2.2:full_context",
    "status": "interrupted",
    "errors": [
      "global stop or deadline"
    ],
    "seconds": 73.32232733396813,
    "native_retry_notices": []
  },
  {
    "model": "gpt-6-luna",
    "benchmark": "lingoly_no_context",
    "id": "220:Q 5.3:no_context",
    "status": "interrupted",
    "errors": [
      "global stop or deadline"
    ],
    "seconds": 22.296496625058353,
    "native_retry_notices": []
  }
]
```
