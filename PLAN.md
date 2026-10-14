# Scam Shield — Build Plan

## Overview

Scam Shield is a Bobathon project that helps Bengaluru seniors identify scam messages and calls in English, Hindi and Kannada. It has three deliverables:

1. **Orchestrate backend** — a multi-agent system with four agents and five Python tools that analyses text/call transcripts and returns a verdict.
2. **PWA frontend** — a mobile-first, high-contrast web app with voice input, a live-coach mode, and a verdict screen, served and backed by a single FastAPI server.
3. **Eval script** — a CLI runner over `eval/eval_set.csv` that reports precision, recall and median latency.

Everything is scoped to be buildable in 3 days on a tight credit budget. LLM calls are minimised: `extract_entities` runs on raw text first to capture entity flags, then `redact_pii` strips PII before anything reaches the model; all five tools are offline Python; Orchestrate is only called once per user request.

---

## Folder Structure

```
scam-shield/
├── PLAN.md
├── README.md
├── .env.example
│
├── agents/                          # Orchestrate project
│   ├── pyproject.toml
│   ├── import_all.sh                # orchestrate tools/agents/kb import commands
│   ├── agents/
│   │   ├── triage.yaml              # supervisor agent YAML
│   │   ├── scam_analyst.yaml        # specialist + KB reference YAML
│   │   ├── guardian.yaml            # alert agent with confirm gate YAML
│   │   └── report_helper.yaml       # cybercrime reporting guide YAML
│   └── tools/
│       ├── redact_pii.py            # strips Aadhaar/PAN/OTP/card before LLM
│       ├── extract_entities.py      # phone numbers, URLs, app names
│       ├── check_link.py            # domain vs known-good list check
│       ├── score_urgency.py         # weighted red-flag score
│       └── match_scam_pattern.py    # keyword/regex pattern → scam_type hint
│
├── backend/
│   ├── requirements.txt
│   ├── main.py                      # FastAPI app + StaticFiles mount for frontend
│   ├── routes/
│   │   ├── analyse.py               # POST /analyse  → calls Orchestrate API
│   │   └── health.py                # GET  /health
│   └── orchestrate_client.py        # thin wrapper for Orchestrate API calls
│
├── frontend/                        # served by FastAPI StaticFiles at /
│   ├── index.html
│   ├── manifest.json
│   ├── service-worker.js
│   └── src/
│       ├── main.js                  # app bootstrap
│       ├── screens/
│       │   ├── Home.js              # paste/type or voice input
│       │   ├── LiveCoach.js         # "I'm on a call right now" mode
│       │   └── Verdict.js           # result display
│       ├── components/
│       │   ├── VoiceButton.js       # Web Speech API, lang selector
│       │   └── ConfirmDialog.js     # used before guardian sends alert
│       └── styles/
│           └── main.css             # high-contrast, large text, WCAG AA
│
├── eval/
│   ├── eval_set.csv                 # 60 rows: 36 scam, 24 genuine
│   └── eval.py                     # runner: calls backend, computes metrics
│
└── kb/
    └── scam_playbooks.md            # uploaded to scam_analyst KB in Orchestrate
```

---

## Milestones and Build Order

### Milestone 1 — Python tools and agent scaffolding (Day 1 morning)
Build and unit-test the five Python tools that all agents depend on. These have no external API dependencies and can be fully tested offline.

### Milestone 2 — Orchestrate agents (Day 1 afternoon – Day 2 morning)
Write YAML agent definitions and `import_all.sh`. Upload `kb/scam_playbooks.md` as the `scam_analyst` knowledge base. Import and smoke-test via the `orchestrate` CLI.

### Milestone 3 — FastAPI backend (Day 2 morning)
Single server: calls Orchestrate, runs the two offline preprocessing steps (extract_entities then redact_pii), serves the frontend via StaticFiles. Keeps credentials in `.env`.

### Milestone 4 — PWA frontend (Day 2 afternoon)
Home screen with text/voice input, Live-Coach cue-button mode, Verdict screen. No build step — plain HTML/CSS/JS. Register a service worker for offline splash.

### Milestone 5 — Eval script (Day 3 morning)
Run the 60-row CSV through the backend, compute precision, recall (strict and lenient), false-alarm rate and median latency. Output `eval/eval_report.md`.

### Milestone 6 — Polish and README (Day 3 afternoon)
Wire remaining edges (confirm dialog for guardian, language toggling, share link), write README with setup steps and demo instructions.

---

## Sub-Tasks

---

### Task 1 — Repo skeleton and configuration

**Intent:** Create the directory structure, dependency files and `.env.example` so every subsequent task has a stable place to land.

**Expected Outcomes:**
- All directories from the folder structure above exist.
- `agents/pyproject.toml` declares `ibm-watsonx-orchestrate` and `pytest` dependencies.
- `backend/requirements.txt` declares `fastapi`, `uvicorn`, `httpx`, `python-dotenv`.
- No `frontend/package.json` — the frontend is served by FastAPI StaticFiles, no Node toolchain needed.
- `.env.example` lists `ORCHESTRATE_API_KEY`, `ORCHESTRATE_BASE_URL`, `ORCHESTRATE_AGENT_ID`.
- `README.md` has a one-paragraph project description and placeholder sections.

**Todo:**
1. Create all directories (`agents/agents/`, `agents/tools/`, `backend/routes/`, `frontend/src/screens/`, `frontend/src/components/`, `frontend/src/styles/`, `eval/`, `kb/`).
2. Write `agents/pyproject.toml`.
3. Write `backend/requirements.txt`.
4. Write `.env.example`.
5. Write stub `README.md`.

**Relevant Context:**
- `kb/scam_playbooks.md` already exists — do not move or rename it.
- `eval/eval_set.csv` already exists — do not modify it.
- No `frontend/package.json` is needed; drop it from this task.

**Status:** [ ] pending

---

### Task 2 — Python tool: `redact_pii`

**Intent:** Strip all PII from a string before it is sent to any LLM call. This is a hard security requirement — it must run first in the pipeline.

**Expected Outcomes:**
- `agents/tools/redact_pii.py` exports a function `redact_pii(text: str) -> str`.
- Redacts: 12-digit Aadhaar numbers, 10-char PAN (format ABCDE1234F), 4–8 digit OTPs (context-aware: preceded by "OTP", "code", "pin"), card numbers (13–19 digits), CVV (3–4 digit after "CVV"/"CVC"), UPI VPAs (pattern `word@word`), and Indian mobile numbers (10 digits starting with 6–9).
- Replacements use obvious tokens: `[AADHAAR]`, `[PAN]`, `[OTP]`, `[CARD]`, `[CVV]`, `[UPI]`, `[PHONE]`.
- A `pytest` test in `agents/tools/test_redact_pii.py` covers each pattern and verifies the genuine bank OTP message (row 37 in eval set) is correctly handled (OTP digits redacted but rest of message preserved).

**Todo:**
1. Write regex patterns for each PII type.
2. Apply in a deterministic order (longest/most-specific first) to avoid partial matches.
3. Export as an ADK-compatible Python tool function with a docstring.
4. Write tests.

**Relevant Context:**
- Eval rows 37 and 53 are genuine bank OTP messages — the tool must redact the OTP digit string but must not destroy the surrounding safety warning.
- Eval row 9 has a scam URL and a fake domain — the domain must NOT be redacted by this tool (that is `check_link`'s job).
- ADK tool functions are plain Python functions; the decorator or registration happens in `main.py`.

**Status:** [ ] pending

---

### Task 3 — Python tool: `extract_entities`

**Intent:** Pull structured boolean entity flags and raw values from a message **before PII redaction**, so the backend can send compact signals to Orchestrate instead of raw text. Running on raw text ensures phone numbers and UPI IDs are captured before they are replaced with tokens.

**Expected Outcomes:**
- `agents/tools/extract_entities.py` exports `extract_entities(text: str) -> dict`.
- Returns a dict with:
  - `urls` (list of URL strings)
  - `phones` (list of raw phone strings)
  - `apps` (list of named remote-access/APK apps found)
  - `keywords` (list of high-signal words matched)
  - Boolean flags: `has_personal_mobile`, `has_upi_id`, `has_url`, `has_apk`, `has_remote_app`
- High-signal app names to detect: AnyDesk, TeamViewer, QuickSupport, and any `*.apk` filename.
- High-signal keywords: "OTP", "UPI PIN", "Aadhaar", "arrest", "digital arrest", "CBI", "ED", "customs", "refund", "prize", "lottery", "KBC", "guaranteed return", "prepaid task".
- `has_personal_mobile`: true if a 10-digit mobile number appears outside of an official bank sender-ID context.
- `has_upi_id`: true if a UPI VPA pattern (`word@word`) is found.

**Todo:**
1. Write URL extractor (regex, handles common shorteners like bit.ly).
2. Write phone extractor (reuse pattern from `redact_pii` but return values instead of redacting); set `has_personal_mobile`.
3. Write app-name and APK detector; set `has_apk` and `has_remote_app`.
4. Write keyword scanner (case-insensitive).
5. Write UPI VPA detector; set `has_upi_id`.
6. Set `has_url` if `urls` is non-empty.
7. Write tests covering at least one case per entity type and flag.

**Relevant Context:**
- Eval rows 10 and 32 have APK filenames.
- Eval rows 15 and 17 mention remote-access app names.
- **This tool is called on raw text BEFORE `redact_pii`** — the backend pipeline order is: `extract_entities(raw)` → `redact_pii(raw)` → send `{redacted_text, entity_flags}` to Orchestrate.
- Only the boolean flags and non-PII values (urls, apps, keywords) are forwarded to Orchestrate; raw phone/UPI values stay in the backend.

**Status:** [ ] pending

---

### Task 4 — Python tool: `check_link`

**Intent:** Flag URLs whose domain does not match the legitimate organisation being impersonated, or that use URL shorteners, or have lookalike domains.

**Expected Outcomes:**
- `agents/tools/check_link.py` exports `check_link(urls: list[str]) -> list[dict]`.
- Each dict has `url`, `domain`, `suspicious: bool`, `reason: str`.
- Suspicious if: domain is a known shortener (bit.ly, tinyurl, t.co, etc.), TLD is not `.gov.in`/`.in`/`.com`/`.org` for Indian govt/bank claims, domain contains a legitimate brand name followed by extra words (e.g. `sbi-kyc-update.online`, `dhl-customs-clear.top`), or domain ends in `.top`/`.xyz`/`.online`/`.shop`.
- A hardcoded allowlist of ~10 genuine domains (sbi.co.in, hdfcbank.com, parivahan.gov.in, etc.) for fast safe-listing.

**Todo:**
1. Write domain extractor from URL.
2. Implement shortener list check.
3. Implement suspicious-TLD check.
4. Implement brand-name-in-subdomain heuristic.
5. Implement allowlist fast-path.
6. Write tests for eval rows 7, 9, 11, 31, 33, 35.

**Relevant Context:**
- Eval row 7: `dhl-customs-clear.top` — suspicious TLD and brand in domain.
- Eval row 9: `sbi-kyc-update.online` — suspicious TLD.
- Eval row 35: `incometax-refund-gov.online` — `.online` TLD with govt brand.

**Status:** [ ] pending

---

### Task 5 — Python tools: `score_urgency` and `match_scam_pattern`

**Intent:** Produce two fast, offline signals — a numeric urgency score and a candidate scam type — from the redacted text and extracted entities. Both tools must match keywords in all three languages, not just Roman script.

**Expected Outcomes:**
- `agents/tools/score_urgency.py` exports `score_urgency(text: str, entities: dict) -> dict` returning `{"score": float, "level": "low"|"medium"|"high", "signals": list[str]}`. Uses the weight table from the playbooks (High/Medium/Low weights: 3/2/1). Score is normalised 0–10.
- `agents/tools/match_scam_pattern.py` exports `match_scam_pattern(text: str) -> dict` returning `{"scam_type": str|None, "confidence": "low"|"medium"|"high"}`. Maps keyword clusters to the 14 scam types. Returns `None` if no cluster fires strongly enough.
- **Multilingual keyword clusters**: each cluster includes Roman-script English terms AND Devanagari Hindi terms AND Kannada script terms. Examples:
  - `digital_arrest`: "digital arrest", "CBI", "ED", "गिरफ्तार", "डिजिटल अरेस्ट", "ಸೈಬರ್ ಕ್ರೈಮ್ ಪೊಲೀಸ್", "ಆಧಾರ್"
  - `kyc`: "KYC", "blocked", "ब्लॉक", "ಬ್ಲಾಕ್", "खाता बंद"
  - `courier`: "courier", "customs", "parcel", "कूरियर", "कस्टम"
  - `relative_emergency`: "accident", "hospital", "new number", "हॉस्पिटल", "ಅಪಘಾತ", "ಹೊಸ ನಂಬರ್"
  - `lottery`: "lottery", "लॉटरी", "बधाई", "prize"
  - `pension`: "pension", "life certificate", "पिंचणि", "ಪಿಂಚಣಿ"
- Genuine messages must score low (eval rows 37–60).

**Todo:**
1. Build the weight-map from the "Universal red-flag signals" table in `kb/scam_playbooks.md`.
2. Implement `score_urgency` — iterate over signals (using multilingual patterns), sum weights, normalise.
3. Build multilingual keyword clusters for all 14 scam types using eval rows 3, 4, 8, 11, 14, 19, 22, 28, 30 as ground-truth sources for Devanagari and Kannada terms.
4. Implement `match_scam_pattern` — return the top-scoring cluster if it exceeds a minimum match count.
5. Write tests using at least 8 rows from the eval set including at least 2 Hindi rows and 2 Kannada rows.

**Relevant Context:**
- The signal table is in `kb/scam_playbooks.md` under "Universal red-flag signals".
- Hindi eval rows: 3, 8, 19, 28, 44 (genuine). Kannada eval rows: 4, 11, 14, 22, 30, 42, 51, 60 (mix of scam and genuine).
- Devanagari keywords from eval: "गिरफ्तार", "पार्सल", "ब्लॉक", "खाता बंद", "वापस भेज", "अवैध", "लॉटरी", "प्रोसेसिंग फीस".
- Kannada keywords from eval: "ಪೊಲೀಸ್", "ಆಧಾರ್", "ಬ್ಲಾಕ್", "ಕ್ಲಿಕ್", "ವಿದ್ಯುತ್", "ಅಪಘಾತ", "ಪಿಂಚಣಿ", "ಓಟಿಪಿ".

**Status:** [ ] pending

---

### Task 6 — Orchestrate agents

**Intent:** Define the four agents as YAML files, register the Python tools, and create the `import_all.sh` script that loads everything into Orchestrate via the CLI.

**Expected Outcomes:**
- Package name in `agents/pyproject.toml` is `ibm-watsonx-orchestrate` (not `-adk`). Tools use the `@tool` decorator from `ibm_watsonx_orchestrate.agent_builder.tools`.
- Each tool file in `agents/tools/` has a `@tool`-decorated function with a clear docstring; tool registration uses `orchestrate tools import -k python`.
- **triage** (`agents/agents/triage.yaml`): supervisor agent; receives redacted text + entity flags + urgency score + scam_type hint; routes to scam_analyst for every message (no short-circuit); after receiving the verdict, optionally routes to guardian or report_helper. Lists scam_analyst, guardian, and report_helper as collaborators.
- **scam_analyst** (`agents/agents/scam_analyst.yaml`): references `kb/scam_playbooks.md` knowledge base; has `check_link` tool attached; receives the redacted text + entity flags; returns a structured verdict JSON: `{verdict: "scam"|"genuine"|"uncertain", scam_type, confidence, explanation, advice}`.
- **guardian** (`agents/agents/guardian.yaml`): its system prompt hard-requires explicit user confirmation before any alert action; the `send_alert` tool signature has `user_confirmed: bool` with default `False` and the function body raises an error unless `user_confirmed is True`; never self-initiates.
- **report_helper** (`agents/agents/report_helper.yaml`): fixed grounded context with reporting steps for 1930, cybercrime.gov.in, and Chakshu on Sanchar Saathi; no KB upload needed.
- All agents include a system-prompt instruction: "Respond in the same language the user wrote in (English, Hindi, or Kannada)."
- `agents/import_all.sh` runs the full sequence: import tools, import knowledge base, import agents, in dependency order.
- **Before writing any YAML**, read `https://developer.watson-orchestrate.ibm.com/llms.txt` to confirm exact YAML schema and CLI command syntax.

**Todo:**
1. Read `https://developer.watson-orchestrate.ibm.com/llms.txt` (or equivalent SDK docs) and note the exact YAML agent definition schema and `orchestrate` CLI commands.
2. Add `@tool` decorator to all five tool functions in `agents/tools/`.
3. Write `agents/agents/scam_analyst.yaml` with KB reference and `check_link` tool.
4. Write `agents/agents/guardian.yaml` with confirm-gate system prompt and `send_alert` tool stub (raises unless `user_confirmed=True`).
5. Write `agents/agents/report_helper.yaml` with grounded reporting steps.
6. Write `agents/agents/triage.yaml` with collaborator list and routing instructions; every message goes to scam_analyst — no genuine short-circuit.
7. Write `agents/import_all.sh`.
8. Smoke-test: `bash agents/import_all.sh` and send two eval rows (one scam, one genuine) via `orchestrate chat`.

**Relevant Context:**
- Guardian alert constraint (hard requirement): `send_alert` tool must have `user_confirmed: bool = False` and must refuse unless explicitly `True`.
- PII is redacted in the backend before triage receives the text.
- `score_urgency` and `match_scam_pattern` are run in the backend pipeline and their outputs are included in the payload sent to triage; they are NOT called again inside the agent.
- `extract_entities` is also run in the backend; only the boolean flags are forwarded to Orchestrate.

**Status:** [ ] pending

---

### Task 7 — FastAPI backend

**Intent:** A single Python server that preprocesses input, calls Orchestrate, and serves the frontend as static files — one process, one port.

**Expected Outcomes:**
- `backend/main.py` runs with `uvicorn backend.main:app`.
- `POST /analyse` accepts `{"text": str, "lang": "en"|"hi"|"kn", "mode": "message"|"live_coach"}`.
  - Pipeline: `extract_entities(raw_text)` → `redact_pii(raw_text)` → `score_urgency(redacted, entities)` → `match_scam_pattern(redacted)` → build payload → call Orchestrate.
  - Payload sent to Orchestrate: `{redacted_text, lang, mode, entity_flags: {has_personal_mobile, has_upi_id, has_url, has_apk, has_remote_app}, urgency: {score, level, signals}, scam_type_hint}`.
  - Returns `{"verdict": str, "scam_type": str|None, "confidence": str, "explanation": str, "advice": str}`.
- `GET /health` returns `{"status": "ok"}`.
- `backend/main.py` mounts `../frontend` as `StaticFiles` at path `/` (with `html=True`) so `index.html` is served at the root.
- No CORS middleware needed since API and frontend share the same origin.
- Credentials loaded from `.env` via `python-dotenv`.
- `backend/orchestrate_client.py` wraps the Orchestrate REST call; timeout 30 s; on timeout returns `{"verdict": "uncertain", "explanation": "Analysis timed out, please try again."}`.

**Todo:**
1. Write `backend/orchestrate_client.py` with async `httpx` call to Orchestrate API.
2. Write `backend/routes/analyse.py` — input validation, full preprocessing pipeline, call Orchestrate client, return response.
3. Write `backend/routes/health.py`.
4. Write `backend/main.py` — FastAPI app, router registration, StaticFiles mount.
5. Write `backend/requirements.txt`.
6. Test with `curl` against a running backend with a mocked Orchestrate response; verify `GET /` returns `index.html`.

**Relevant Context:**
- `ORCHESTRATE_BASE_URL`, `ORCHESTRATE_API_KEY`, `ORCHESTRATE_AGENT_ID` from `.env`.
- `redact_pii`, `extract_entities`, `score_urgency`, `match_scam_pattern` all live in `agents/tools/` and are imported directly by the backend.
- StaticFiles mount must come after all API routes so `/analyse` and `/health` are not shadowed.

**Status:** [ ] pending

---

### Task 8 — PWA frontend

**Intent:** A mobile-first web app that seniors can use to paste a suspicious message or describe a live call using large tap buttons. No React/Vue — plain HTML/CSS/JS for zero-build-time simplicity. Served by the FastAPI backend at `/`.

**Expected Outcomes:**
- `frontend/index.html` — single-page app shell with three screens (Home, LiveCoach, Verdict) shown/hidden via CSS class.
- **Home screen**: large text-area for pasting/typing, a mic button using the Web Speech API (`lang` toggles between `kn-IN`, `hi-IN`, `en-IN`), a language selector (3 buttons), a submit button labelled "Check this message", and a secondary button "I'm on a call right now" that switches to LiveCoach mode.
- **LiveCoach screen**: six large tap buttons describing what the caller is saying — "Claiming to be police / CBI / court", "Asking for money transfer", "Asking for OTP or PIN", "Saying don't tell anyone", "Asking to install an app", "Other (describe)". Tapping a button highlights it and appends its cue text to the analysis payload. Optional voice input (Web Speech API) lets the senior add their own description. A "Get advice now" button sends all selected cues to `POST /analyse` with `mode: live_coach`. Advice is shown inline in large bold text. Rationale: a browser cannot capture the other party's audio on an active phone call; cue buttons are a reliable, fast alternative.
- **Verdict screen**: coloured banner (red = scam, green = genuine, yellow = uncertain), scam type label, plain-language explanation in the detected language, advice text, a "Report to 1930" button, and a "Send alert to family" button that opens a `ConfirmDialog`.
- **ConfirmDialog**: modal requiring explicit tap of "Yes, send alert" — cannot be dismissed accidentally. On confirm, opens a pre-filled `sms:` URI (falls back to a WhatsApp `wa.me` deep-link) so the user's native messaging app sends the alert; the app never sends SMS itself.
- `frontend/manifest.json` and `frontend/service-worker.js` for PWA installability and offline splash.
- `frontend/src/styles/main.css`: minimum font size 18px body / 24px headings, WCAG AA contrast, large tap targets (min 48px height).

**Todo:**
1. Write `frontend/src/styles/main.css` (high-contrast theme first, everything else builds on it).
2. Write `frontend/index.html` with screen scaffold and screen-switch logic.
3. Write `frontend/src/components/VoiceButton.js` — Web Speech API wrapper, language-aware.
4. Write `frontend/src/screens/Home.js`.
5. Write `frontend/src/screens/LiveCoach.js` — six cue buttons + optional voice + "Get advice now".
6. Write `frontend/src/screens/Verdict.js`.
7. Write `frontend/src/components/ConfirmDialog.js` — on confirm, opens `sms:` / WhatsApp deep-link; never sends SMS directly.
8. Write `frontend/manifest.json` and `frontend/service-worker.js`.
9. Wire `frontend/src/main.js` to bootstrap all screens and handle API calls to `/analyse`.

**Relevant Context:**
- The browser cannot capture the other party's audio on an active phone call; the cue-button approach is the correct solution.
- The confirm dialog is the client-side counterpart to the guardian's `user_confirmed` gate.
- Voice API `lang` values: `kn-IN`, `hi-IN`, `en-IN` — must be set before `SpeechRecognition.start()`.
- API calls go to `/analyse` (same origin — no CORS needed since frontend is served by the same FastAPI process).

**Status:** [ ] pending

---

### Task 9 — Eval script

**Intent:** Run the 60-row eval set through the live backend and report a full metrics breakdown so the team can demonstrate accuracy at the Bobathon.

**Expected Outcomes:**
- `eval/eval.py` is a CLI script runnable as `python eval/eval.py --backend http://localhost:8000`.
- For each row it calls `POST /analyse`, records `verdict` and elapsed time.
- Treats `verdict == "scam"` as positive class; `uncertain` is tracked separately and reported but never silently merged into TP, TN, FP, or FN.
- Computes and reports:
  - **Precision** = TP / (TP + FP) — `uncertain` on genuine rows does not count as FP.
  - **Recall (strict)** = TP / (TP + FN + uncertain_on_scam) — `uncertain` on a scam row counts as a miss.
  - **Recall (lenient)** = (TP + uncertain_on_scam) / (TP + FN + uncertain_on_scam) — treats `uncertain` as a soft flag.
  - **False-alarm rate** = FP / (FP + TN + uncertain_on_genuine) — explicit measure of how often genuine messages are wrongly flagged.
  - **Uncertain rate** = total `uncertain` / total rows.
  - F1 on both strict and lenient recall.
  - Median latency (ms) across all rows.
  - Per-language breakdown (en / hi / kn) for all metrics.
  - Per-scam-type breakdown.
- Writes results to `eval/eval_report.md` and prints a summary table to stdout.

**Todo:**
1. Write the CSV loader (reads `eval/eval_set.csv`).
2. Write the async batch caller using `httpx` (concurrent, rate-limited to max 5 in-flight to avoid credit spikes).
3. Write the metrics calculator with the `uncertain` handling described above.
4. Write the `eval_report.md` writer with per-language and per-type tables.
5. Add a `--dry-run` flag that uses a mock response so the script structure can be validated before credits are spent.

**Relevant Context:**
- The eval set has 36 scam rows (ids 1–36) and 24 genuine rows (ids 37–60).
- Language distribution: en = majority, hi = 6 rows, kn = 7 rows.
- `uncertain` must never be silently collapsed into a true-negative on genuine rows — report it as its own category.

**Status:** [ ] pending

---

### Task 10 — README and wiring

**Intent:** Complete the README with setup and run instructions, and ensure all loose wires are connected (language passed through, ConfirmDialog opens share link, `.env.example` complete).

**Expected Outcomes:**
- `README.md` covers: project description, ASCII architecture diagram, prerequisites, setup steps (clone → `pip install` → `.env` → `bash agents/import_all.sh` → `uvicorn backend.main:app`), demo script for the Bobathon judges, and a link to the eval report.
- Setup is at most 5 commands from a fresh clone.
- The backend correctly passes `lang` to Orchestrate so agents respond in the right language.
- `ConfirmDialog` opens `sms:` / WhatsApp deep-link on confirm; verified that it does not call any send API.
- `.env.example` is audited and complete against all `os.environ` calls in the codebase.

**Todo:**
1. Audit all `os.environ` references in `backend/` and update `.env.example`.
2. Verify `lang` flows end-to-end: frontend → POST body → backend payload → Orchestrate request.
3. Verify `ConfirmDialog` opens share link, not a send API call.
4. Write `README.md` with setup under 5 commands.

**Relevant Context:**
- Bobathon judges will follow the README to run the demo; the ASCII diagram is the authoritative architecture reference.
- The single server command (`uvicorn backend.main:app`) serves both API and frontend — highlight this in the README.

**Status:** [ ] pending

---

## Constraints and Non-Goals

- **No database** — no persistence between sessions; each analysis is stateless.
- **No authentication** — this is a demo; the backend is not hardened.
- **No paid SMS gateway** — after ConfirmDialog confirmation the frontend opens a `sms:` URI or WhatsApp `wa.me` deep-link; the app never calls a send API.
- **No React/Next.js/Vue** — plain HTML/JS only; zero build tooling for the frontend.
- **No streaming** — single-shot Orchestrate API call; live-coach sends selected cues on demand.
- **No live-call audio capture** — the browser cannot capture the other party; the LiveCoach screen uses cue buttons instead of real-time transcription.
- **PII redaction is local only** — `redact_pii` runs in the backend process; only redacted text is sent to Orchestrate; original text is never stored or forwarded.
- **extract_entities runs on raw text** — entity flags are derived before redaction; only boolean flags (not raw PII values) are forwarded to Orchestrate.
- **No triage short-circuit** — every message goes to scam_analyst regardless of urgency score; the score is a signal, not a gate.
