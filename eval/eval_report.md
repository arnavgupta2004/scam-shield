# Scam Shield evaluation report

Generated 2026-10-19 02:04. Backend: http://localhost:8000.

Each row was sent through the full pipeline: local PII redaction, then the watsonx Orchestrate agents. The dev set was written alongside the rules; the held-out set was written separately and never used to tune anything.

| Metric | dev | held-out |
|---|---|---|
| Messages (scam / genuine) | 60 (36 / 24) | 40 (22 / 18) |
| Scams caught (strict recall) | 97% | 95% |
| Scams caught or warned (uncertain counted) | 100% | 95% |
| Scams marked safe (missed) | 0 | 1 |
| Precision | 100% | 95% |
| Genuine messages cleared | 100% | 94% |
| False alarms (genuine marked scam) | 0% | 6% |
| Genuine marked uncertain | 0 | 0 |
| Median latency (agent answers) | 4.5 s | 4.1 s |
| 90th percentile latency | 6.1 s | 5.0 s |
| Answered by agents / rules fallback / errors | 59 / 1 / 0 | 40 / 0 / 0 |

## dev: by language

| Language | Scams caught | Genuine cleared |
|---|---|---|
| en | 26/27 | 19/19 |
| hi | 4/4 | 2/2 |
| kn | 5/5 | 3/3 |

Rows not answered correctly (1):

- id 2 (en, scam/digital_arrest): got **uncertain** via rules

## held-out: by language

| Language | Scams caught | Genuine cleared |
|---|---|---|
| en | 15/16 | 14/14 |
| hi | 3/3 | 1/2 |
| kn | 3/3 | 2/2 |

Rows not answered correctly (2):

- id 107 (en, scam/wrong_number_romance): got **genuine** via agent
- id 136 (hi, genuine/pharmacy): got **scam** via agent

> Some rows were answered by the offline rules fallback or failed. Those are not agent answers; re-run when Orchestrate is reachable for clean numbers.
