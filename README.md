# Scam Shield

[![Tests](https://github.com/arnavgupta2004/scam-shield/actions/workflows/tests.yml/badge.svg)](https://github.com/arnavgupta2004/scam-shield/actions/workflows/tests.yml)

**IBM Bobathon: Build for Bengaluru** · Student category · Safer Communities, Stronger Futures

Scam Shield helps senior citizens in Bengaluru check a suspicious message or phone call in English, Hindi or Kannada, and tells them in plain words what to do next. It runs on IBM watsonx Orchestrate agents; the agents and their tools were built with IBM Bob.

- Demo video: _add link_
- Presentation: _add link or file name_

## The problem

Older adults are the main targets of "digital arrest", KYC, electricity-cutoff, courier and fake-relative scams. These scams work by isolating the victim and rushing them, and the money usually leaves in the minutes before anyone else is called. What needs to improve is the moment of doubt: a senior needs a fast, trustworthy second opinion, in their own language, before they pay or share a code.

## What it does

- **Check a message.** Paste or speak an SMS, WhatsApp message or call summary. You get a verdict (looks like a scam / looks safe / not sure), the warning signs, and one or two clear actions, read aloud if you want.
- **Share from WhatsApp.** On Android, once the app is installed to the home screen, "Share" on any WhatsApp message opens Scam Shield directly with the text pre-filled. Not available on iPhone.
- **Check a screenshot.** Pick a screenshot from the gallery; the text is read on the phone and the image is never uploaded. Language data downloads on first use.
- **"I'm on a call right now".** Big buttons describe what the caller is saying ("says police", "asks for OTP", "says don't tell anyone"), and the app replies with an instruction like "Hang up now". No typing during a call.
- **Alert my family**, with human review built in. Nothing is drafted until the user confirms, and the user sends the message themselves on WhatsApp or SMS. The family number stays on the phone.
- **How to report.** 1930, cybercrime.gov.in and Chakshu (Sanchar Saathi), in the user's language.

## Results

Every message goes through the full pipeline: local PII redaction, then the watsonx Orchestrate agents. Full report: [eval/eval_report.md](eval/eval_report.md).

| | Rule tools alone | Scam Shield (rules + agents) |
|---|---|---|
| **Held-out set**: scams caught | 4 of 22 | **21 of 22** |
| Held-out: genuine messages wrongly flagged | 4 of 18 | 1 of 18 |
| Dev set: scams caught | 36 of 36 | 35 of 36 |
| Dev set: genuine messages wrongly flagged | 3 of 24 | 0 of 24 |
| Median time to an answer | instant | about 4 seconds |

- **Dev set** (60 messages): the rule tools were written alongside it, which is why rules alone look perfect there.
- **Held-out set** (40 messages): written separately, with scam types the rules have never seen (rental deposit, OLX buyer, wrong-number crypto, insurance claim). Nothing was tuned on it. Both sets were written by the team, not collected from real victims.
- The one dev miss (row 2) was a request that timed out and fell back to the rules, which answered "not sure". Held-out errors: a wrong-number romance opener marked safe (row 107) and a Hindi pharmacy delivery message flagged as a scam (row 136).

**Impact measure:** scams caught before the user acts. On messages the system had never seen, the agents raised it from 4 of 22 to 21 of 22, with an answer in about 4 seconds.

## Architecture

```
 Phone browser (PWA: en / hi / kn, voice in, read aloud)
        |  POST /analyse {text, lang, mode, cues}
        v
 FastAPI backend (runs locally)
   1. extract_entities on raw text  -> flags only (has_personal_mobile, has_upi_id, has_url, ...)
   2. redact_pii                    -> OTP, Aadhaar, PAN, card, CVV, UPI, phone replaced by tokens
   3. score_urgency + match_scam_pattern (fast rule hints)
        |  redacted text + flags + hints (no raw numbers ever leave this step)
        v
 watsonx Orchestrate
   scam_shield_triage (supervisor)
     -> scam_analyst  [tools: check_link, extract_entities, lookup_playbook; knowledge base: scam playbooks]
   guardian       [tool: draft_family_alert, refuses unless user_confirmed = true]
   report_helper
        |
        v
 Verdict JSON -> big, colour-coded answer in the user's language
```

If Orchestrate can't be reached, the backend answers from the local rules and the UI says it's a quick check only. That fallback never says "looks safe".

## Privacy and human review

- PII is redacted before any model call. The app shows the user exactly what was checked, with private numbers hidden.
- Message content is never logged; only the verdict, language and latency are.
- The family alert needs two confirmations: the dialog in the app and `user_confirmed=true` on the guardian tool. The user presses send.
- No accounts and no database. The family number is kept only in the phone's browser storage.

## Setup

Needs Python 3.11+, the `orchestrate` CLI and a watsonx Orchestrate instance.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env                 # add WO_INSTANCE and WO_API_KEY
orchestrate env activate <your-env>
bash agents/import_all.sh            # tools, knowledge base, agents (check the output for errors)
python backend/agent_ids.py          # paste the printed ids into .env

uvicorn backend.main:app --reload    # open http://localhost:8000
```

Tests (no credentials needed): `python -m pytest agents/tools backend -q`

Re-run the evaluation (backend must be running): `python eval/eval.py`. Rules-only baseline: `python eval/baseline.py --compare eval/holdout_set.csv`.

## Repository map

| Path | What it is |
|---|---|
| `agents/tools/` | Python tools imported into Orchestrate (redaction, entities, links, urgency, patterns, playbook lookup, family alert) and their tests |
| `agents/agents/` | The four agent definitions and the knowledge-base spec |
| `agents/import_all.sh` | Imports tools, knowledge base and agents in order |
| `kb/` | Scam playbooks (14 scam types) used by the knowledge base and `lookup_playbook` |
| `backend/` | FastAPI API, Orchestrate client, PII pipeline, offline fallback, tests |
| `frontend/` | The web app (plain HTML/CSS/JS, installable) |
| `eval/` | Test sets, rules baseline, end-to-end evaluation and its report |
| `PLAN.md` | The build plan produced in Bob's Plan mode |
| `docs/BOB_STORY.md` | How IBM Bob was used, with commit references |

## How it was built

- **Built with IBM Bob** (Plan and Agent modes in Bob Shell): the build plan, all agent tools and their tests, the four Orchestrate agents, the knowledge-base setup, the import script and the rules baseline. See [docs/BOB_STORY.md](docs/BOB_STORY.md) and the commits marked "(Bob)".
- **Built without Bob**, after the Bob trial credits ran out: the web app (`frontend/`), the API (`backend/`), the end-to-end evaluation script, and a later fix to the triage hand-off.
- **Reviewed with Bob**, after Pro+ credits were restored: Bob audited the app layer (backend and frontend) for PII leaks, accessibility problems and bugs, found 21 findings, and fixed the 8 accepted ones — including a 401-retry in the Orchestrate client, `scam_type` slug validation, a visible focus ring on the verdict banner, localised microphone-error messages with an `aria-live` announcement, `aria-modal` on both dialogs, and tighter `report_helper` output rules. Full log: [docs/REVIEW.md](docs/REVIEW.md).
- The scam playbooks and test sets were prepared separately as data.

## Known limits

- Tested on 100 team-written messages, not real-world traffic. A larger, independently written test set is the next step.
- Answers take about 4 seconds; a slow agent call occasionally times out and falls back to the rules.
- Hindi and Kannada output should be reviewed by native speakers.
- The prototype runs on a watsonx Orchestrate trial instance.

## License

MIT, see [LICENSE](LICENSE).
