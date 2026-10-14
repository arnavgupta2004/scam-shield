#!/usr/bin/env python3
"""
smoke_test.py — smoke test scam_shield_triage with eval rows 1 and 37.

Sends the preprocessed payload (as the backend would build it) to the
scam_shield_triage agent and prints the raw JSON replies.
"""

import json
import os
import sys
import re
import subprocess

# ---- preprocessing imports (same pipeline as backend) ---------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agents.tools.extract_entities import _extract_entities_impl as extract_entities
from agents.tools.redact_pii import redact_pii
from agents.tools.score_urgency import _score_urgency_impl as score_urgency
from agents.tools.match_scam_pattern import _match_scam_pattern_impl as match_scam_pattern

# ---- eval rows 1 and 37 --------------------------------------------------
ROWS = [
    {
        "id": 1,
        "lang": "en",
        "label": "scam",
        "scam_type": "digital_arrest",
        "text": (
            "This is Inspector Rao from Mumbai Cyber Crime. Your Aadhaar is linked "
            "to a money laundering case. You are under digital arrest. Stay on video "
            "call and do not inform anyone or you will be jailed."
        ),
    },
    {
        "id": 37,
        "lang": "en",
        "label": "genuine",
        "scam_type": "bank_otp",
        "text": (
            "123456 is your OTP for login to SBI YONO. Valid for 5 mins. "
            "Do not share OTP with anyone. -SBI"
        ),
    },
]


def build_payload(row: dict) -> dict:
    """Run the full backend pipeline and build the Orchestrate payload."""
    raw_text = row["text"]
    entities = extract_entities(raw_text)
    redacted = redact_pii(raw_text)
    urgency = score_urgency(redacted, entities)
    pattern = match_scam_pattern(redacted)

    # Only forward boolean flags (no raw PII values)
    flags = {
        "has_personal_mobile": entities["has_personal_mobile"],
        "has_upi_id":          entities["has_upi_id"],
        "has_url":             entities["has_url"],
        "has_apk":             entities["has_apk"],
        "has_remote_app":      entities["has_remote_app"],
    }

    payload_content = {
        "text": redacted,
        "lang": row["lang"],
        "mode": "message",
        "flags": flags,
        "urgency": urgency,
        "scam_type_hint": pattern.get("scam_type"),
    }

    return {
        "messages": [
            {"role": "user", "content": json.dumps(payload_content, ensure_ascii=False)}
        ]
    }


def get_token(api_key: str) -> str:
    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            "https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"apikey": api_key}),
        ],
        capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout)["token"]


def chat_with_agent(wo_url: str, agent_id: str, token: str, payload: dict) -> str:
    """POST to the chat completions endpoint and reassemble streaming SSE."""
    url = f"{wo_url}/v1/orchestrate/{agent_id}/chat/completions"
    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST", url,
            "-H", f"Authorization: Bearer {token}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps(payload, ensure_ascii=False),
        ],
        capture_output=True, text=True, timeout=120,
    )
    raw = result.stdout
    chunks = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                event = json.loads(data_str)
                choices = event.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        chunks.append(content)
            except json.JSONDecodeError:
                pass
    return "".join(chunks)


def main():
    wo_url = os.environ.get("WO_INSTANCE") or os.environ.get("ORCHESTRATE_BASE_URL", "")
    api_key = os.environ.get("WO_API_KEY") or os.environ.get("ORCHESTRATE_API_KEY", "")

    if not wo_url or not api_key:
        # Try loading .env
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if not os.path.exists(env_path):
            env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip()
            wo_url = os.environ.get("WO_INSTANCE", wo_url)
            api_key = os.environ.get("WO_API_KEY", api_key)

    if not wo_url or not api_key:
        print("ERROR: WO_INSTANCE and WO_API_KEY must be set (or .env present).")
        sys.exit(1)

    # Get agent ID for scam_shield_triage via orchestrate CLI
    try:
        result = subprocess.run(
            ["orchestrate", "agents", "list"],
            capture_output=True, text=True, timeout=30
        )
        # Extract ID — look for ea09d pattern from agents list output
        m = re.search(r"scam_shield_triage.*?(\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b)",
                      result.stdout, re.DOTALL | re.IGNORECASE)
        if not m:
            # Try reverse direction
            m = re.search(r"(\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b).*?scam_shield_triage",
                          result.stdout, re.DOTALL | re.IGNORECASE)
        agent_id = m.group(1) if m else None
    except Exception as e:
        agent_id = None

    if not agent_id:
        # Hardcode from known import
        agent_id = "ea09d1a4-7389-4cff-be55-e58223cdb73a"
        print(f"[INFO] Using hardcoded agent ID: {agent_id}")

    print(f"[INFO] WO_URL: {wo_url}")
    print(f"[INFO] Agent ID: {agent_id}")
    print()

    token = get_token(api_key)
    print("[INFO] Token obtained.")
    print()

    results = {}
    for row in ROWS:
        print(f"{'='*60}")
        print(f"EVAL ROW {row['id']} | label={row['label']} | scam_type={row['scam_type']}")
        print(f"Raw text: {row['text']}")
        print()

        payload = build_payload(row)
        print(f"Payload sent to triage:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print()

        print("Calling scam_shield_triage...")
        raw_reply = chat_with_agent(wo_url, agent_id, token, payload)
        print()
        print("RAW AGENT REPLY:")
        print(raw_reply)
        print()

        # Try to parse JSON from reply
        try:
            # Agent may wrap JSON in text; extract first JSON object
            m = re.search(r"\{.*\}", raw_reply, re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                print("PARSED JSON:")
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
                results[row["id"]] = parsed
        except Exception as e:
            print(f"[WARN] Could not parse JSON from reply: {e}")
        print()

    print("="*60)
    print("SMOKE TEST SUMMARY:")
    for row_id, verdict_data in results.items():
        label = next(r["label"] for r in ROWS if r["id"] == row_id)
        verdict = verdict_data.get("verdict", "?")
        match = "✓" if (
            (label == "scam" and verdict == "scam") or
            (label == "genuine" and verdict == "genuine")
        ) else "✗"
        print(f"  Row {row_id} ({label}): verdict={verdict} {match}")


if __name__ == "__main__":
    main()
