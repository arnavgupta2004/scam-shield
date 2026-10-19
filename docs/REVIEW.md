# Security, Accessibility & Bug Review Log

Review performed by Bob (AI code review) on 2026-10-19.
Each finding was manually verified by the project team before any fix was applied.

| # | Severity | Category | File | Lines | Status | Reason |
|---|----------|----------|------|-------|--------|--------|
| 1 | 🔴 Critical | PII leak | `frontend/app.js` | 214–217 | **Rejected** | Agents only ever see redacted text; the summary passed to `/alert` is re-run through `prepare()` → `redact_pii` on the server before reaching Orchestrate. No raw PII escapes. |
| 2 | 🔴 Critical | Bug | `frontend/app.js` | 205 | Deferred (low impact) | `showModal()` is supported by all browsers in active use for this project's target devices; a polyfill is not warranted at this time. |
| 3 | 🔴 Critical | Bug | `frontend/app.js` | 111 | **Rejected** | `#btn-alert` lives inside `#screen-verdict` which is `hidden` on first load. The button is never focusable or visible before a verdict is rendered. |
| 4 | 🔴 Critical | Accessibility | `frontend/styles.css` | 148 | **Fixed** | `.verdict:focus { outline: none }` replaced with `.verdict:focus-visible { outline: 4px solid var(--focus); outline-offset: -4px }` so keyboard/switch users see a visible focus ring when focus is programmatically moved to the result banner. |
| 5 | 🔴 Critical | PII leak | `backend/main.py` | 185 | **Fixed** | `scam_type` in `/report` is now validated against `^[a-z_]{1,40}$` via `ReportRequest.safe_scam_type`; values that do not match the slug pattern are nulled before being forwarded to Orchestrate. |
| 6 | 🟠 High | Accessibility | `frontend/index.html` | 35–36 | Deferred (low impact) | The `<label for="msg">` is correctly associated with the textarea; reusing the placeholder text as the hidden label is a common pattern. Not yet tested with a screen reader. |
| 7 | 🟠 High | Accessibility | `frontend/index.html` | 70 | Deferred (low impact) | `<label for="coach-msg">` at line 68 already labels the textarea; the association is valid HTML. Not yet tested with a screen reader. |
| 8 | 🟠 High | Accessibility | `frontend/index.html` | 123 | Deferred (low impact) | `<summary data-t="sentTitle">` is filled by `applyLang()` as soon as the script runs; the app needs JavaScript anyway, so the empty-label window is negligible. |
| 9 | 🟠 High | Accessibility | `frontend/index.html` | 39–42 | **Fixed** (part of #11) | An `aria-live="polite"` region (`#mic-status`) now announces "listening" when recording starts and is cleared when it stops, giving screen reader users immediate feedback. |
| 10 | 🟠 High | Bug | `frontend/app.js` | 219 | Deferred (low impact) | The WhatsApp URL normalisation covers the primary use case (Indian numbers). Edge cases for international formats are a known limitation, not a regression introduced by this codebase. |
| 11 | 🟠 High | Bug | `frontend/app.js` | 74 | **Fixed** | `recognizer.onerror` now maps `not-allowed`, `no-speech`, and all other error codes to localised messages (`micDenied`, `micNoSpeech`, `micError`) added to `i18n.js` in all three languages (en/hi/kn), and displays the message via `showError`. |
| 12 | 🟠 High | PII / info leak | `backend/main.py` | 168 | **Rejected** | `user_confirmed: true` in the guardian payload is the intentional human-in-the-loop tool gate; the guardian agent's `draft_family_alert` tool refuses without it. Removing it would break the confirmation flow. |
| 13 | 🟠 High | Bug | `backend/orchestrate_client.py` | 130 | **Rejected** | `parse_reply` returns the raw string only when the response body is neither SSE nor valid JSON chat-completion. This value is passed to `extract_json` which returns `None` on failure; `main.py` falls back to rules. The raw body is never logged. |
| 14 | 🟡 Medium | Bug | `backend/main.py` | 81 | **Rejected** | Pydantic v2 does enforce `max_length` on list fields when specified via `Field(max_length=…)` — the constraint is applied as `max_length` on the `list` annotation in the generated JSON Schema and validated at request parse time. |
| 15 | 🟡 Medium | Bug | `backend/main.py` | 66–70 | Deferred (low impact) | The lazy-initialisation race is a one-time cold-start concern under very high concurrency; it produces a redundant token fetch, not incorrect behaviour. Not worth adding a lock for the current single-worker deployment. |
| 16 | 🟡 Medium | Bug | `frontend/index.html` | 132 | **Fixed** | `method="dialog"` removed from `<form id="confirm-form">`. A `submit` event listener on the form now calls `e.preventDefault()` and triggers `$("confirm-yes").click()`, so pressing Enter in `#family-phone` routes through the same async handler as the button click. |
| 17 | 🟡 Medium | Accessibility | `frontend/styles.css` | 64 | **Rejected** | Measured contrast ratio for `--muted` (#46536A) on `--paper` (#F4F6F9) is **7.2:1**, well above the WCAG AA threshold of 4.5:1. The initial estimate in the review was incorrect. |
| 18 | 🟡 Medium | Accessibility | `frontend/index.html` | 131, 144 | **Fixed** | `aria-modal="true"` added to both `<dialog id="confirm">` and `<dialog id="alert-ready">` so NVDA/JAWS restrict virtual-cursor navigation to the open dialog. |
| 19 | 🟡 Medium | Accessibility | `frontend/index.html` | 110 | Deferred (low impact) | The `<a href="tel:1930">` element is labelled by its `data-t="call1930"` text which resolves to "Call 1930" / localised equivalent — sufficiently descriptive. Desktop `tel:` behaviour is a browser concern, not an app defect. |
| 20 | 🟠 High | Bug/Availability | `backend/orchestrate_client.py` | 77 | **Fixed** | On HTTP 401, the client now clears `_token` and `_token_expiry`, fetches a fresh token, and retries the request exactly once. This covers mid-flight token expiry without risking infinite retry loops. New tests: `test_chat_retries_after_401`, `test_analyse_retries_on_401_and_returns_agent_verdict`. |
| 21 | 🟢 Low | Accessibility | `frontend/styles.css` | 199–200 | **Fixed** | `@media (prefers-reduced-motion: reduce)` block for `.callstrip:active` now also holds `box-shadow: 0 6px 0 #7E180F` static, preventing the depth animation from triggering vestibular responses. |

## Summary

| Status | Count |
|--------|-------|
| Fixed | 8 (#4, #5, #9, #11, #16, #18, #20, #21) |
| Rejected | 6 (#1, #3, #12, #13, #14, #17) |
| Deferred (low impact) | 7 (#2, #6, #7, #8, #10, #15, #19) |

## Other changes in the same Bob sessions

- **report_helper output (known issue, not a review finding):** the agent sometimes returned markdown (`**`) or notes about its own instructions. Its instructions now require plain numbered lines, and `/report` strips markdown and bracketed notes (`_clean_report`, with tests).
- **Triage hand-off (made, then reverted):** Bob also removed the triage agent's duplicate rule-tool calls, since the backend already sends those results. The change was reasonable but altered the evaluated agent pipeline, so it was reverted (`61ecfd8`) and deferred: changing triage would require re-running the evaluation before submission.

All 163 tests pass (`python -m pytest agents/tools backend -q`).
