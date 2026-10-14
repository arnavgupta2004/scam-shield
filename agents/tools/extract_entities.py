"""
extract_entities.py — extract structured signals from RAW text (before redact_pii).

Must run on raw text so phone numbers and UPI IDs are captured before they are
replaced by [PHONE]/[UPI] tokens.

Returns a dict with:
  urls              list[str]   — all URLs found
  phones            list[str]   — raw 10-digit Indian mobiles
  apps              list[str]   — named remote-access apps / APK filenames
  keywords          list[str]   — high-signal scam keywords matched
  has_personal_mobile  bool
  has_upi_id           bool
  has_url              bool
  has_apk              bool
  has_remote_app       bool
"""

from __future__ import annotations

import re
from ibm_watsonx_orchestrate.agent_builder.tools import tool

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_URL_RE = re.compile(
    r"https?://[^\s\"'<>]+"
    r"|(?<!\w)"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"(?:com|in|org|net|gov|top|xyz|online|shop|co\.in|gov\.in|ly|me)"
    r"(?:/[^\s\"'<>]*)?",
    re.IGNORECASE,
)

_PHONE_RE = re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)")

_APK_RE = re.compile(r"\b\w[\w.\-]*\.apk\b", re.IGNORECASE)

_REMOTE_APPS = re.compile(
    r"\b(?:AnyDesk|TeamViewer|QuickSupport|ScreenConnect|RemotePC)\b",
    re.IGNORECASE,
)

_UPI_RE = re.compile(r"\b[\w.\-]{2,}@[\w.\-]{2,}\b")

# High-signal keywords — English, Devanagari (Hindi), Kannada
_KEYWORDS: list[tuple[re.Pattern, str]] = [
    # English
    (re.compile(r"\bOTP\b"),                                "OTP"),
    (re.compile(r"\bUPI\s*PIN\b", re.I),                   "UPI PIN"),
    (re.compile(r"\bAadhaar\b", re.I),                     "Aadhaar"),
    (re.compile(r"\bdigital\s+arrest\b", re.I),            "digital arrest"),
    (re.compile(r"\barrest\b", re.I),                      "arrest"),
    (re.compile(r"\bCBI\b"),                               "CBI"),
    (re.compile(r"\bED\b"),                                "ED"),
    (re.compile(r"\bcustoms\b", re.I),                     "customs"),
    (re.compile(r"\brefund\b", re.I),                      "refund"),
    (re.compile(r"\bprize\b", re.I),                       "prize"),
    (re.compile(r"\blottery\b", re.I),                     "lottery"),
    (re.compile(r"\bKBC\b"),                               "KBC"),
    (re.compile(r"\bguaranteed\s+return", re.I),           "guaranteed return"),
    (re.compile(r"\bprepaid\s+task\b", re.I),              "prepaid task"),
    # Hindi / Devanagari
    (re.compile(r"गिरफ्तार"),                               "गिरफ्तार"),
    (re.compile(r"डिजिटल\s*अरेस्ट"),                       "डिजिटल अरेस्ट"),
    (re.compile(r"पुलिस"),                                  "पुलिस"),
    (re.compile(r"कूरियर"),                                 "कूरियर"),
    (re.compile(r"कस्टम"),                                  "कस्टम"),
    (re.compile(r"पार्सल"),                                 "पार्सल"),
    (re.compile(r"अवैध"),                                   "अवैध"),
    (re.compile(r"ब्लॉक"),                                  "ब्लॉक"),
    (re.compile(r"खाता\s*बंद"),                             "खाता बंद"),
    (re.compile(r"वापस\s*भेज"),                             "वापस भेज"),
    (re.compile(r"लॉटरी"),                                  "लॉटरी"),
    (re.compile(r"बधाई"),                                   "बधाई"),
    (re.compile(r"प्रोसेसिंग\s*फीस"),                      "प्रोसेसिंग फीस"),
    (re.compile(r"हॉस्पिटल"),                               "हॉस्पिटल"),
    # Kannada
    (re.compile(r"ಪೊಲೀಸ್"),                                "ಪೊಲೀಸ್"),
    (re.compile(r"ಸೈಬರ್"),                                  "ಸೈಬರ್"),
    (re.compile(r"ಆಧಾರ್"),                                  "ಆಧಾರ್"),
    (re.compile(r"ಬ್ಲಾಕ್"),                                 "ಬ್ಲಾಕ್"),
    (re.compile(r"ಕ್ಲಿಕ್"),                                 "ಕ್ಲಿಕ್"),
    (re.compile(r"ವಿದ್ಯುತ್"),                               "ವಿದ್ಯುತ್"),
    (re.compile(r"ಅಪಘಾತ"),                                  "ಅಪಘಾತ"),
    (re.compile(r"ಪಿಂಚಣಿ"),                                 "ಪಿಂಚಣಿ"),
    (re.compile(r"ಓಟಿಪಿ"),                                  "ಓಟಿಪಿ"),
    (re.compile(r"ಹೊಸ\s*ನಂಬರ್"),                            "ಹೊಸ ನಂಬರ್"),
    (re.compile(r"ಕೆವೈಸಿ"),                                 "ಕೆವೈಸಿ"),
    (re.compile(r"ಹಣ\s*ವರ್ಗಾವಣೆ"),                          "ಹಣ ವರ್ಗಾವಣೆ"),
]


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def _extract_entities_impl(text: str) -> dict:
    urls: list[str] = _URL_RE.findall(text)
    phones: list[str] = _PHONE_RE.findall(text)
    apk_matches: list[str] = _APK_RE.findall(text)
    remote_app_matches: list[str] = _REMOTE_APPS.findall(text)
    upi_matches: list[str] = _UPI_RE.findall(text)
    keywords: list[str] = [label for pat, label in _KEYWORDS if pat.search(text)]

    return {
        "urls": urls,
        "phones": phones,
        "apps": apk_matches + remote_app_matches,
        "keywords": keywords,
        "has_url": bool(urls),
        "has_apk": bool(apk_matches),
        "has_remote_app": bool(remote_app_matches),
        "has_personal_mobile": bool(phones),
        "has_upi_id": bool(upi_matches),
    }


@tool
def extract_entities(text: str) -> dict:
    """
    Extract structured entity flags and values from *raw* text (before PII redaction).

    Run this BEFORE redact_pii so that phone numbers and UPI IDs are captured
    while still present in the original string.

    Returns a dict with raw lists (urls, phones, apps, keywords) and boolean
    convenience flags (has_personal_mobile, has_upi_id, has_url, has_apk,
    has_remote_app).  Raw phone strings are kept in the backend and must NOT
    be forwarded to Orchestrate; only the boolean flags travel upstream.
    """
    return _extract_entities_impl(text)
