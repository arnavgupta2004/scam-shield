#!/usr/bin/env python3
"""
Print the agent-id lines for .env, read from the active Orchestrate environment.

  python backend/agent_ids.py >> .env      (then check .env for duplicates)

Needs the orchestrate CLI with the right environment activated.
If the table layout of `orchestrate agents list` changes, copy the ids by hand.
"""

import re
import subprocess
import sys

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
WANTED = {"scam_shield_triage": "TRIAGE_AGENT_ID", "guardian": "GUARDIAN_AGENT_ID",
          "report_helper": "REPORT_AGENT_ID", "scam_analyst": "SCAM_ANALYST_AGENT_ID"}


def main():
    try:
        out = subprocess.run(["orchestrate", "agents", "list", "-v"], capture_output=True, text=True, timeout=60).stdout
        if not re.search(UUID, out, re.I):
            out = subprocess.run(["orchestrate", "agents", "list"], capture_output=True, text=True, timeout=60).stdout
    except FileNotFoundError:
        sys.exit("orchestrate CLI not found. Activate the venv that has ibm-watsonx-orchestrate.")

    found = {}
    for line in out.splitlines():
        ids = re.findall(UUID, line, re.I)
        for name, var in WANTED.items():
            if ids and re.search(rf"\b{name}\b", line):
                found[var] = ids[0]
    # Fallback for JSON-ish verbose output: name and id on nearby lines.
    if len(found) < 3:
        for name, var in WANTED.items():
            m = re.search(rf'"name":\s*"{name}".{{0,600}}?"id":\s*"({UUID})"', out, re.S | re.I) or \
                re.search(rf'"id":\s*"({UUID})".{{0,600}}?"name":\s*"{name}"', out, re.S | re.I)
            if m:
                found.setdefault(var, m.group(1))

    if not found:
        sys.exit("No agent ids found. Run `orchestrate agents list` and copy them into .env by hand.")
    for var in WANTED.values():
        if var in found:
            print(f"{var}={found[var]}")
    missing = [v for v in WANTED.values() if v not in found]
    if missing:
        print(f"# not found: {', '.join(missing)}", file=sys.stderr)


if __name__ == "__main__":
    main()
