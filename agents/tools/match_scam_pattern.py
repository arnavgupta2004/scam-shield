"""
match_scam_pattern.py — keyword-cluster based scam type classifier.

Maps text to one of 14 scam types using multilingual (English, Hindi, Kannada)
keyword clusters sourced from kb/scam_playbooks.md and the eval set.

Returns:
    scam_type   str | None   — matched type or None
    confidence  str          — "high" / "medium" / "low"
    matches     list[str]    — keywords that fired (for debugging)
"""

from __future__ import annotations

import re
from ibm_watsonx_orchestrate.agent_builder.tools import tool

# ---------------------------------------------------------------------------
# Cluster definition
# Each cluster: (scam_type, min_matches_for_high, list_of_patterns)
# Confidence: matched ≥ min_high → "high", ≥ 1 → "medium" (if ≥2 → still medium)
# We pick the cluster with the most pattern hits; tie-breaks toward higher min_high.
# ---------------------------------------------------------------------------

def _pats(*terms: str) -> list[re.Pattern]:
    """Compile each term as a case-insensitive regex."""
    return [re.compile(t, re.IGNORECASE | re.UNICODE) for t in terms]


_CLUSTERS: list[tuple[str, int, list[re.Pattern]]] = [
    (
        "digital_arrest",
        2,
        _pats(
            r"\bdigital\s+arrest\b",
            r"\bdigital\s+custody\b",
            r"\barrest\s+warrant\b",
            r"\bCBI\b",
            r"\bED\b(?!\s*officer\s+of)",  # avoid false-match on "ED officer"
            r"\bEnforcement\s+Directorate\b",
            r"\bnarcotics\b",
            r"\bcyber\s*crime\s*police\b",
            r"\bunder\s+(?:digital\s+)?arrest\b",
            r"\bstay\s+on\s+(?:call|video\s+call)\b",
            r"\bdo\s+not\s+inform\s+anyone\b",
            r"\bjailed\b",
            r"दिल्ली\s*पुलिस|मुंबई\s*पुलिस",
            r"गिरफ्तार",
            r"डिजिटल\s*अरेस्ट",
            r"किसी\s*को\s*मत\s*बताइए",
            r"ड्रग्स",
            r"ಸೈಬರ್\s*ಕ್ರೈಮ್\s*ಪೊಲೀಸ್",
            r"ಆಧಾರ್\s*ಹಣ\s*ವರ್ಗಾವಣೆ",
            r"ವಿಡಿಯೋ\s*ಕಾಲ್.*ಇರಿ",
            r"ಯಾರಿಗೂ\s*ಹೇಳಬೇಡಿ",
        ),
    ),
    (
        "courier",
        2,
        _pats(
            r"\bcourier\b",
            r"\bparcel\b",
            r"\bcustoms\b",
            r"\bFedEx\b",
            r"\bDHL\b",
            r"\bpackage\s+is\s+held\b",
            r"\bdrugs?\b",
            r"\bpassports?\b",
            r"\bcustoms?\s*duty\b",
            r"\bMDMA\b",
            r"कूरियर",
            r"कस्टम",
            r"पार्सल",
            r"अवैध\s*सामान",
        ),
    ),
    (
        "kyc",
        2,
        _pats(
            r"\bKYC\b",
            r"\baccount\s+will\s+be\s+blocked\b",
            r"\b(?:SIM|account|netbanking)\s+(?:will\s+be\s+)?(?:deactivated|suspended|blocked)\b",
            r"\bupdate\s+(?:PAN\s+)?KYC\b",
            r"download\s+\w+\.apk",
            r"\bAPK\b",
            r"bit\.ly|\.online|\.top",
            r"ब्लॉक",
            r"खाता\s*बंद",
            r"ಬ್ಲಾಕ್",
            r"ಕೆವೈಸಿ",
            r"ಕ್ಲಿಕ್\s*ಮಾಡಿ",
        ),
    ),
    (
        "electricity",
        2,
        _pats(
            r"\belectricity\b",
            r"\bpower\s+will\s+be\s+disconnected\b",
            r"\bdisconnect(?:ed|ion)?\b",
            r"\belectricity\s+officer\b",
            r"\bQuickSupport\b",
            r"\bTeamViewer\b",
            r"\bAnyDesk\b",
            r"\bupdate\s+charge\b",
            r"ವಿದ್ಯುತ್\s*ಕಡಿತ",
            r"ಅಧಿಕಾರಿಗೆ\s*ಕರೆ\s*ಮಾಡಿ",
        ),
    ),
    (
        "fake_customer_care",
        2,
        _pats(
            r"\brefund\s+desk\b",
            r"\brefund\s+team\b",
            r"\benter\s+(?:your\s+)?(?:UPI\s+)?PIN\b",
            r"\bUPI\s+(?:collect\s+)?request\b",
            r"\bAnyDesk\b",
            r"\bshare\s+(?:the\s+)?\d+\s*digit\s+code\b",
            r"\bcancellation\s+refund\b",
            r"\bFlipkart\s+refund\b",
        ),
    ),
    (
        "upi_mistake",
        2,
        _pats(
            r"\bsent\s+by\s+mistake\b",
            r"\bby\s+mistake\b",
            r"\breturn\s+(?:the\s+)?(?:amount|money|Rs)\b",
            r"\bplease\s+return\b",
            r"\bUPI\b.*\bmistake\b",
            r"गलती\s*से",
            r"वापस\s*भेज",
        ),
    ),
    (
        "relative_emergency",
        2,
        _pats(
            r"\bnew\s+number\b",
            r"\bhad\s+an\s+accident\b",
            r"\bpolice\s+took\s+my\s+phone\b",
            r"\bdon.?t\s+tell\s+(?:papa|mom|amma|anyone)\b",
            r"\bstuck\s+at\s+(?:airport|customs)\b",
            r"\bcan.?t\s+talk\s+on\s+call\b",
            r"ಹೊಸ\s*ನಂಬರ್",
            r"ಅಪಘಾತ",
            r"ಅಮ್ಮನಿಗೆ\s*ಹೇಳಬೇಡಿ",
        ),
    ),
    (
        "investment",
        2,
        _pats(
            r"\bguaranteed\s+\d+%\s+return",
            r"\bSEBI\s+registered\b",
            r"\bVIP\s+group\b",
            r"\bIPO\s+allotment\b",
            r"\bwithdraw(?:al)?\s+(?:blocked|locked|pending)\b",
            r"\bpay\s+\d+%\s+tax\b",
            r"\bBitcoin\s+doubling\b",
            r"\bBTC\b",
            r"\bStockPro\b",
        ),
    ),
    (
        "job_task",
        2,
        _pats(
            r"\bpart.?time\s+job\b",
            r"\bliking\s+YouTube\s+videos\b",
            r"\bprepaid\s+task\b",
            r"\bdeposit\b.*\bget\s+back\b",
            r"\bTelegram\s+@\w+\b",
            r"\bHR\s+on\s+Telegram\b",
            r"@hr_\w+",
        ),
    ),
    (
        "lottery",
        2,
        _pats(
            r"\bKBC\b",
            r"\blucky\s+draw\b",
            r"\blottery\b",
            r"\bwon\s+(?:Rs\.?|₹)\s*[\d,]+\b",
            r"\bprocessing\s+fee\b",
            r"\bGST\s+to\s+claim\b",
            r"लॉटरी",
            r"बधाई\s*हो",
            r"प्रोसेसिंग\s*फीस",
        ),
    ),
    (
        "pension",
        2,
        _pats(
            r"\bpension\s+will\s+stop\b",
            r"\blife\s+certificate\b",
            r"\btreasury\s+office\b",
            r"\bshare\s+OTP\b",
            r"\bpension\s+office\b",
            r"ಪಿಂಚಣಿ\s*ನಿಲ್ಲುತ್ತದೆ",
            r"ಜೀವನ\s*ಪ್ರಮಾಣಪತ್ರ",
            r"ಓಟಿಪಿ\s*ಹೇಳಿ",
        ),
    ),
    (
        "echallan",
        2,
        _pats(
            r"\be.?challan\b",
            r"\btraffic\s+(?:fine|challan|violation)\b",
            r"\bRTO\b",
            r"\blicen[cs]e\s+suspension\b",
            r"echallan.*\.(?:apk|co|in)",
            r"parivahan\.co",
        ),
    ),
    (
        "lpg",
        2,
        _pats(
            r"\bLPG\s+(?:subsidy|connection|KYC|eKYC)\b",
            r"\bIndane\b",
            r"\bsubsidy\s+will\s+be\s+cancelled\b",
            r"\beKYC\b.*\bLPG\b",
            r"lpg.ekyc",
        ),
    ),
    (
        "sextortion",
        1,  # single strong signal is enough
        _pats(
            r"\brecorded\s+your\s+video\s+call\b",
            r"\bvideo\s+(?:call|recording)\b.*\bcontacts\b",
            r"\bsend\s+it\s+to\s+all\s+your\s+contacts\b",
            r"\bblackmailing\b",
            r"\bsextortion\b",
        ),
    ),
]


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def _match_scam_pattern_impl(text: str) -> dict:
    best_type: str | None = None
    best_count = 0
    best_min = 0
    best_matches: list[str] = []

    for scam_type, min_high, patterns in _CLUSTERS:
        fired = [p.pattern for p in patterns if p.search(text)]
        count = len(fired)
        if count > best_count or (count == best_count and min_high > best_min and count > 0):
            best_type = scam_type
            best_count = count
            best_min = min_high
            best_matches = fired

    if best_count == 0:
        return {"scam_type": None, "confidence": "none", "matches": []}

    if best_count >= best_min:
        confidence = "high"
    elif best_count >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    return {"scam_type": best_type, "confidence": confidence, "matches": best_matches}


@tool
def match_scam_pattern(text: str) -> dict:
    """
    Match *text* against multilingual keyword clusters for 14 scam types.

    Args:
        text: The (redacted) message text.

    Returns:
        scam_type   str | None  — matched scam type or None
        confidence  str         — "high" / "medium" / "low" / "none"
        matches     list[str]   — patterns that fired (human-readable)
    """
    return _match_scam_pattern_impl(text)
