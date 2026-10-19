# The Bob Story

How IBM Bob was used to build Scam Shield, with the commits that show it.

## 1. Plan mode: design before code

The project started as an empty folder with the scam playbooks and a labelled test set. Bob read both (`@kb/scam_playbooks.md`, `@eval/eval_set.csv`) in Plan mode and produced [PLAN.md](../PLAN.md): folder layout, ten tasks, build order and constraints. The plan was then reviewed and corrected in Plan mode before any code was written, for example:

- send every message to the analyst agent instead of letting rules mark messages "genuine", because the rules missed Hindi and Kannada scams;
- make the family-alert gate default to "not confirmed";
- run entity extraction on the raw text before redaction, so phone numbers and UPI IDs still count as evidence.

Commit: `d8eedb2` Plan: Scam Shield build plan (Bob Plan mode)

## 2. Agent mode: tools, tested one task at a time

Each task from the plan ran as its own short Bob session, ending with passing tests and a commit.

| Commit | What Bob built |
|---|---|
| `2b9dea0` | Project skeleton and `redact_pii` (OTP, Aadhaar, PAN, card, CVV, UPI, phone) with 32 tests |
| `55aa83a` | Fixes for redaction leaks found in review: spaced card numbers, `+91 98765 43210` phones, "pincode" read as an OTP |
| `a061e19` | `extract_entities`, `check_link`, `score_urgency`, `match_scam_pattern` with English, Hindi and Kannada keywords; the rules baseline over dev and held-out sets |
| `8fdf827`, `d792b1f` | The four watsonx Orchestrate agents (triage supervisor, scam analyst, guardian, report helper), the `draft_family_alert` tool with its confirmation gate, the knowledge-base spec and `import_all.sh`; language pass-through fixed so replies follow the user's language |
| `26d5d2d` | `lookup_playbook`, a tool fallback when the knowledge-base embedding service returned 502 errors |

Bob also read the watsonx Orchestrate ADK documentation itself to get the agent YAML schema and CLI commands right, connected the ADK to the trial instance, imported everything and ran smoke tests against the live agents.

## 3. What Bob found along the way

- The ADK `@tool` decorator wraps return values, so Bob split each tool into a plain function (used by the backend and tests) and a decorated wrapper (used by Orchestrate).
- The rules baseline showed the gap the agents had to close: 36 of 36 scams caught on the dev set but only 4 of 22 on the held-out set.
- When knowledge-base indexing failed on the trial instance, Bob stopped after two attempts, reported the exact error, and built the `lookup_playbook` fallback.

## 4. What was built without Bob

Bob's trial credits (50 Bobcoins) ran out after the agents were finished. The web app, the FastAPI backend, the end-to-end evaluation script and a later fix to the triage hand-off were built without Bob.

## 5. Pro+ credits restored: Bob reviews the app layer

After Pro+ credits were restored, Bob reviewed the app layer — `backend/` and `frontend/` — that had been written entirely without it. Working in Ask mode, Bob audited the code for three categories of risk:

- **PII paths to Orchestrate or the logs** (`backend/main.py`, `backend/pipeline.py`, `backend/orchestrate_client.py`, `frontend/app.js`)
- **Accessibility problems** for elderly users (`frontend/index.html`, `frontend/styles.css`)
- **Bugs** across all five files

Bob found 21 findings and presented them with severity, file and line. The team verified each one and accepted 8 for immediate fixing:

| Finding | What was fixed |
|---|---|
| #4 | `.verdict:focus { outline: none }` removed; replaced with a visible `:focus-visible` ring so keyboard/switch users see where focus lands after a verdict |
| #5 | `scam_type` in `/report` now validated against `^[a-z_]{1,40}$`; anything else is nulled before reaching Orchestrate |
| #9 + #11 | `recognizer.onerror` now maps `not-allowed`, `no-speech` and other codes to localised messages (`micDenied`, `micNoSpeech`, `micError`) added to `i18n.js` in all three languages; an `aria-live="polite"` region announces "listening" to screen readers |
| #16 | `method="dialog"` removed from the confirmation form; a `submit` listener now routes Enter-in-phone-field through the same async handler as the confirm button |
| #18 | `aria-modal="true"` added to both `<dialog>` elements |
| #20 | On HTTP 401, `OrchestrateClient.chat` now clears the cached token and retries the call exactly once with a fresh token |
| #21 | `prefers-reduced-motion` block for `.callstrip:active` now also holds the `box-shadow` static |
| #7 | `report_helper.yaml` output-format rules tightened: explicit prohibition on preamble, bracketed notes and closing text |

Bob added tests for the two new backend behaviours (#20 and #5) and the suite stayed green at 163 passed. A full review log with Accept/Reject reasoning for all 21 findings is in [docs/REVIEW.md](REVIEW.md).

Commits: `5c727e8` Fix verified review findings + review log (Bob) · `e28e1b5` Docs: Bob review of app layer (Bob). An earlier commit in the same session (`d8cf21c`) also tightened the report helper and changed the triage agent; the triage change was reverted to keep the evaluated configuration (see REVIEW.md).
