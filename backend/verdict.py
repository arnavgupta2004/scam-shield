"""Turn an agent's free-text reply into a validated verdict dict."""

from __future__ import annotations

import json
import re

VERDICTS = {"scam", "genuine", "uncertain"}
CONFIDENCES = {"high", "medium", "low"}

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _json_objects(text: str):
    """Yield every balanced top-level {...} object that parses as JSON."""
    depth = 0
    start = None
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    yield json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    pass
                start = None


def extract_json(text: str, required_key: str, _depth: int = 0) -> dict | None:
    """Find the first JSON object in *text* containing *required_key*.

    A supervisor sometimes returns its collaborator's wrapper verbatim, e.g.
    {"thread_id": "...", "message": "{\\"verdict\\": ...}"}, so string values
    are searched as well (one level deep).
    """
    candidates = [m.group(1) for m in _FENCE_RE.finditer(text)] + [text]
    nested: list[str] = []
    for chunk in candidates:
        for obj in _json_objects(chunk):
            if not isinstance(obj, dict):
                continue
            if required_key in obj:
                return obj
            nested += [v for v in obj.values() if isinstance(v, str) and "{" in v]
    if _depth < 1:
        for value in nested:
            found = extract_json(value, required_key, _depth + 1)
            if found:
                return found
    return None


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()][:3]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalise_verdict(obj: dict | None) -> dict | None:
    """Validate and clean an agent verdict. Returns None if unusable."""
    if not obj:
        return None
    verdict = str(obj.get("verdict", "")).strip().lower()
    if verdict not in VERDICTS:
        return None
    confidence = str(obj.get("confidence", "")).strip().lower()
    if confidence not in CONFIDENCES:
        confidence = "medium"
    scam_type = obj.get("scam_type")
    if scam_type in ("", "null", "none", "None"):
        scam_type = None
    return {
        "verdict": verdict,
        "scam_type": scam_type if verdict != "genuine" else None,
        "confidence": confidence,
        "red_flags": _as_list(obj.get("red_flags")),
        "explanation": str(obj.get("explanation", "")).strip(),
        "advice": str(obj.get("advice", "")).strip(),
    }
