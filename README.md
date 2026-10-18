# Scam Shield

Scam Shield helps senior citizens in Bengaluru check a suspicious message or phone call in English, Hindi or Kannada, and tells them in plain words what to do next. It runs on IBM watsonx Orchestrate agents.

**The problem.** Older adults are the main targets of "digital arrest", KYC, electricity, courier and fake-relative scams. These scams work by isolating the victim and rushing them, and the money usually leaves in the minutes before anyone else is called.

**What it does**

- **Check a message.** Paste or speak an SMS, WhatsApp message or call summary. You get a verdict (looks like a scam / looks safe / not sure), the warning signs, and one or two clear actions.
- **"I'm on a call right now".** Big buttons describe what the caller is saying ("says police", "asks for OTP", "says don't tell anyone"), and the app replies with an instruction like "Hang up now". The user doesn't need to type during a call.
- **Alert my family**, with human review built in. Nothing is drafted until the user confirms, and the user sends the message themselves on WhatsApp or SMS. The family number stays on the phone.
- **How to report.** 1930, cybercrime.gov.in and Chakshu (Sanchar Saathi), in the user's language.

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
     -> scam_analyst  [tools: check_link, extract_entities, lookup_playbook; KB: scam playbooks]
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
bash agents/import_all.sh            # tools, knowledge base, agents
python backend/agent_ids.py          # paste the printed ids into .env

uvicorn backend.main:app --reload    # open http://localhost:8000
```

Tests (no credentials needed): `python -m pytest agents/tools backend -q`

## Evaluation

```bash
python eval/eval.py                  # needs the backend running
```

Every row goes through the full pipeline (redaction, then the agents). Results are in [eval/eval_report.md](eval/eval_report.md).

- **Dev set**: 60 messages (36 scam, 24 genuine). The rule tools were written alongside it.
- **Held-out set**: 40 messages, including scam types the rules have never seen (rental deposit, OLX buyer, wrong-number crypto, insurance claim). Nothing was tuned on it.
- "Uncertain" is reported separately and never counted as a correct answer for a genuine message.

Rule tools alone (`python eval/baseline.py --compare eval/holdout_set.csv`): 100% recall on dev but 18% on held-out. The agents have to close that gap.

## How it was built

- **Built with IBM Bob** (Plan and Agent modes in Bob Shell): the build plan, all agent tools and their tests (`agents/tools`), the four Orchestrate agents, the import script and the rule baseline. See the commits marked "(Bob)".
- **Built without Bob**, after the Bob trial credits ran out: the web app (`frontend/`), the API (`backend/`) and the end-to-end evaluation script (`eval/eval.py`).
- The scam playbooks and test sets were prepared separately as data.

Known limits: the knowledge-base vector index failed to build on the trial instance (embedding service 502), so `lookup_playbook` serves the same playbooks as a tool. Hindi and Kannada text should be checked by native speakers.
