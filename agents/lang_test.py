#!/usr/bin/env python3
"""
lang_test.py — verify scam_analyst replies in the language given by `lang`.

Test 1: Row 37 text, lang=en  → expect English reply
Test 2: Row 4 text,  lang=kn  → expect Kannada reply
"""

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agents.tools.extract_entities import _extract_entities_impl as extract_entities
from agents.tools.redact_pii import redact_pii
from agents.tools.score_urgency import _score_urgency_impl as score_urgency
from agents.tools.match_scam_pattern import _match_scam_pattern_impl as match_scam_pattern

TESTS = [
    {
        "id": 37,
        "lang": "en",
        "label": "genuine",
        "text": "123456 is your OTP for login to SBI YONO. Valid for 5 mins. Do not share OTP with anyone. -SBI",
        "expect_lang": "English",
    },
    {
        "id": 4,
        "lang": "kn",
        "label": "scam",
        "text": "ನಾನು ಸೈಬರ್ ಕ್ರೈಮ್ ಪೊಲೀಸ್. ನಿಮ್ಮ ಆಧಾರ್ ಹಣ ವರ್ಗಾವಣೆ ಪ್ರಕರಣದಲ್ಲಿ ಇದೆ. ವಿಡಿಯೋ ಕಾಲ್‌ನಲ್ಲೇ ಇರಿ, ಯಾರಿಗೂ ಹೇಳಬೇಡಿ.",
        "expect_lang": "Kannada",
    },
]


def build_payload(row: dict) -> dict:
    raw_text = row["text"]
    entities = extract_entities(raw_text)
    redacted = redact_pii(raw_text)
    urgency = score_urgency(redacted, entities)
    pattern = match_scam_pattern(redacted)

    flags = {
        "has_personal_mobile": entities["has_personal_mobile"],
        "has_upi_id":          entities["has_upi_id"],
        "has_url":             entities["has_url"],
        "has_apk":             entities["has_apk"],
        "has_remote_app":      entities["has_remote_app"],
    }

    payload_content = {
        "text":           redacted,
        "lang":           row["lang"],
        "mode":           "message",
        "flags":          flags,
        "urgency":        urgency,
        "scam_type_hint": pattern.get("scam_type"),
    }
    return {
        "messages": [
            {"role": "user", "content": json.dumps(payload_content, ensure_ascii=False)}
        ]
    }


def get_token(api_key: str) -> str:
    result = subprocess.run(
        ["curl", "-s", "-X", "POST",
         "https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"apikey": api_key})],
        capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout)["token"]


def chat_with_agent(wo_url: str, agent_id: str, token: str, payload: dict) -> str:
    url = f"{wo_url}/v1/orchestrate/{agent_id}/chat/completions"
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", url,
         "-H", f"Authorization: Bearer {token}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps(payload, ensure_ascii=False)],
        capture_output=True, text=True, timeout=120,
    )
    chunks = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                event = json.loads(data_str)
                choices = event.get("choices", [])
                if choices:
                    content = choices[0].get("delta", {}).get("content", "")
                    if content:
                        chunks.append(content)
            except json.JSONDecodeError:
                pass
    return "".join(chunks)


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def get_agent_id() -> str:
    # --verbose returns JSON; parse it to find scam_shield_triage
    result = subprocess.run(
        ["orchestrate", "agents", "list", "--verbose"],
        capture_output=True, text=True, timeout=30,
    )
    text = result.stdout
    # JSON output is {"native": [...], "external": [...], "assistant": [...]}
    try:
        data = json.loads(text)
        all_agents = []
        if isinstance(data, list):
            all_agents = data
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    all_agents.extend(v)
        for a in all_agents:
            if isinstance(a, dict) and a.get("name") == "scam_shield_triage":
                return a.get("id") or a.get("agent_id")
    except (json.JSONDecodeError, TypeError):
        pass
    # Fallback: scan for full UUID next to name in text
    m = re.search(
        r'"name"\s*:\s*"scam_shield_triage".*?"id"\s*:\s*"([0-9a-f-]{36})"',
        text, re.DOTALL | re.IGNORECASE,
    ) or re.search(
        r'"id"\s*:\s*"([0-9a-f-]{36})".*?"name"\s*:\s*"scam_shield_triage"',
        text, re.DOTALL | re.IGNORECASE,
    )
    if m:
        return m.group(1)
    return None


def main():
    load_env()
    wo_url  = os.environ.get("WO_INSTANCE") or os.environ.get("ORCHESTRATE_BASE_URL", "")
    api_key = os.environ.get("WO_API_KEY") or os.environ.get("ORCHESTRATE_API_KEY", "")
    if not wo_url or not api_key:
        sys.exit("ERROR: WO_INSTANCE and WO_API_KEY must be set (or .env present).")

    agent_id = get_agent_id()
    if not agent_id:
        sys.exit("ERROR: Could not find scam_shield_triage agent ID via 'orchestrate agents list'.")

    print(f"[INFO] WO_URL   : {wo_url}")
    print(f"[INFO] Agent ID : {agent_id}")
    token = get_token(api_key)
    print("[INFO] Token obtained.\n")

    for t in TESTS:
        sep = "=" * 70
        print(sep)
        print(f"TEST: Row {t['id']} | lang={t['lang']} | expected reply language: {t['expect_lang']}")
        print(f"Input JSON: {{\"text\": \"...\", \"lang\": \"{t['lang']}\", \"mode\": \"message\", \"flags\": {{}}}}")
        print(f"Raw input text: {t['text']}\n")

        payload = build_payload(t)
        print("Preprocessed payload (sent to triage):")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("\nCalling scam_shield_triage ...\n")

        raw_reply = chat_with_agent(wo_url, agent_id, token, payload)

        print("RAW AGENT REPLY:")
        print(raw_reply)
        print()


if __name__ == "__main__":
    main()
