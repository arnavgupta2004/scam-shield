# Scam Shield

Scam Shield helps Bengaluru seniors identify scam messages and phone calls in English, Hindi, and Kannada. It uses watsonx Orchestrate agents backed by a scam-playbook knowledge base to return a verdict, explain the scam pattern, and guide the user to report it safely.

## Setup

> See [PLAN.md](PLAN.md) for full architecture and build plan.

```
# 1. Create and activate virtualenv
python3.11 -m venv .venv && source .venv/bin/activate

# 2. Install backend dependencies
pip install -r backend/requirements.txt

# 3. Configure credentials
cp .env.example .env   # then edit .env

# 4. Import agents into Orchestrate
bash agents/import_all.sh

# 5. Start the server (serves API + frontend)
uvicorn backend.main:app --reload
```

## Sections

- [Architecture](#) — see PLAN.md
- [Eval Report](eval/eval_report.md) — generated after running `python eval/eval.py`
