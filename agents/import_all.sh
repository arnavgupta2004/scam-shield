#!/usr/bin/env bash
# agents/import_all.sh
#
# Imports tools, the knowledge base, and agents into the active Orchestrate
# environment in dependency order:
#   1. Tools (no deps)
#   2. Knowledge base (no deps)
#   3. Leaf agents: scam_analyst, guardian, report_helper  (depend on tools + KB)
#   4. Supervisor: scam_shield_triage  (depends on the three leaf agents)
#
# Prerequisites:
#   - orchestrate CLI installed (ibm-watsonx-orchestrate >= 2.18.1)
#   - Active environment configured: orchestrate env activate <name>
#   - Run from the repository root: bash agents/import_all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TOOLS_DIR="${SCRIPT_DIR}/tools"
AGENTS_DIR="${SCRIPT_DIR}/agents"
REQUIREMENTS="${TOOLS_DIR}/requirements.txt"

echo "=== Scam Shield — Orchestrate import ==="
echo "Repo root : ${REPO_ROOT}"
echo "Tools dir : ${TOOLS_DIR}"
echo "Agents dir: ${AGENTS_DIR}"
echo ""

# ---------------------------------------------------------------------------
# 1. Import Python tools
# ---------------------------------------------------------------------------
echo "--- Step 1: Import tools ---"

for tool_file in \
    "${TOOLS_DIR}/score_urgency.py" \
    "${TOOLS_DIR}/match_scam_pattern.py" \
    "${TOOLS_DIR}/check_link.py" \
    "${TOOLS_DIR}/extract_entities.py" \
    "${TOOLS_DIR}/lookup_playbook.py" \
    "${TOOLS_DIR}/draft_family_alert.py"; do

    tool_name="$(basename "${tool_file}" .py)"
    echo "  Importing tool: ${tool_name}"
    orchestrate tools import \
        -k python \
        -f "${tool_file}" \
        -r "${REQUIREMENTS}"
done

echo ""

# ---------------------------------------------------------------------------
# 2. Import knowledge base
# ---------------------------------------------------------------------------
echo "--- Step 2: Import knowledge base ---"
# Generate a temporary KB YAML with the absolute path to the document
# so the CLI can find it regardless of working directory.
KB_TMP="$(mktemp /tmp/scam_playbooks_kb_XXXXXX.yaml)"
cat > "${KB_TMP}" <<KBEOF
spec_version: v1
kind: knowledge_base
name: scam_playbooks_kb
description: |
  Scam playbooks for Scam Shield — covers 14 scam types targeting senior
  citizens in Bengaluru, with red-flag signals, genuine-message patterns,
  and response advice in English, Hindi and Kannada.
documents:
  - "${REPO_ROOT}/kb/scam_playbooks.txt"
vector_index:
  embeddings_model_name: ibm/slate-125m-english-rtrvr-v2
KBEOF
echo "  Importing KB: scam_playbooks_kb"
orchestrate knowledge-bases import -f "${KB_TMP}"
rm -f "${KB_TMP}"
echo ""

# ---------------------------------------------------------------------------
# 3. Import leaf agents (scam_analyst, guardian, report_helper)
# ---------------------------------------------------------------------------
echo "--- Step 3: Import leaf agents ---"

for agent_file in \
    "${AGENTS_DIR}/scam_analyst.yaml" \
    "${AGENTS_DIR}/guardian.yaml" \
    "${AGENTS_DIR}/report_helper.yaml"; do

    agent_name="$(basename "${agent_file}" .yaml)"
    echo "  Importing agent: ${agent_name}"
    orchestrate agents import -f "${agent_file}"
done

echo ""

# ---------------------------------------------------------------------------
# 4. Import supervisor agent (scam_shield_triage)
# ---------------------------------------------------------------------------
echo "--- Step 4: Import supervisor agent ---"
echo "  Importing agent: scam_shield_triage"
orchestrate agents import -f "${AGENTS_DIR}/triage.yaml"

echo ""
echo "=== Import complete ==="
echo ""
echo "Verify with:"
echo "  orchestrate tools list"
echo "  orchestrate knowledge-bases list"
echo "  orchestrate agents list"
