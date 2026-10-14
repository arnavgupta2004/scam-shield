"""
redact_pii.py — strip PII from text before any LLM call.

Redacts (in order):
  1. OTP / verification code (4–8 digits, context-gated)
  2. Aadhaar (exactly 12 digits, possibly space/hyphen separated in groups of 4)
  3. PAN (ABCDE1234F format)
  4. Card numbers (13–19 digits, not already consumed as Aadhaar)
  5. CVV (3–4 digits, context-gated)
  6. UPI VPA (word@word)
  7. Indian mobile numbers (10 digits, starts 6–9)

Replacements: [OTP], [AADHAAR], [PAN], [CARD], [CVV], [UPI], [PHONE]
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Patterns — ordered from most-specific / longest to least-specific
# ---------------------------------------------------------------------------

# 1. OTP: 4–8 digits preceded (or followed) by an OTP-signal word.
#    Handles:  "OTP 482913", "123456 is your OTP", "code: 7890", "PIN 1234"
_OTP_BEFORE = re.compile(
    r"(?i)(?:otp|one[- ]time[- ](?:password|code)|verification[- ]code|code|passcode|pin)"
    r"[\s:]*"
    r"(\b\d{4,8}\b)",
)
_OTP_AFTER = re.compile(
    r"\b(\d{4,8})\b"
    r"[\s]*(?:is[- ]your[- ])?"
    r"(?:otp|one[- ]time[- ](?:password|code)|verification[- ]code|code|passcode|pin)\b",
    re.IGNORECASE,
)

# 2. Aadhaar: 12 consecutive digits OR groups of 4 separated by spaces/hyphens.
#    Must be surrounded by word boundaries so it doesn't swallow longer numbers.
_AADHAAR = re.compile(
    r"(?<!\d)"
    r"(?:\d{4}[- ]\d{4}[- ]\d{4}|\d{12})"
    r"(?!\d)"
)

# 3. PAN: exactly AAAAA9999A (5 uppercase letters, 4 digits, 1 uppercase letter)
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")

# 4. Card numbers: 13–19 consecutive digits not already matched as Aadhaar.
#    Using a negative lookbehind/lookahead to avoid partial digit-string collisions.
_CARD = re.compile(r"(?<!\d)\d{13,19}(?!\d)")

# 5. CVV: 3–4 digits after CVV/CVC/security code
_CVV = re.compile(
    r"(?i)(?:cvv|cvc|security[- ]code)[\s:]*(\b\d{3,4}\b)"
)

# 6. UPI VPA: word@word (e.g. john@okaxis, 9876543210@upi)
#    Allow alphanumeric + underscore + hyphen + dot on each side.
_UPI = re.compile(r"\b[\w.\-]{2,}@[\w.\-]{2,}\b")

# 7. Indian mobile: exactly 10 digits starting with 6–9, not inside a longer number.
_PHONE = re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)")


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def redact_pii(text: str) -> str:
    """
    Return a copy of *text* with all PII replaced by safe placeholder tokens.

    Applies patterns in a deterministic order (most-specific first) to prevent
    partial-match collisions.  The original string is never modified.

    Tokens used: [OTP], [AADHAAR], [PAN], [CARD], [CVV], [UPI], [PHONE]
    """
    # Step 1: OTP (context-gated — replace the digit group only, preserve label)
    def _replace_otp_before(m: re.Match) -> str:
        return m.group(0).replace(m.group(1), "[OTP]")

    def _replace_otp_after(m: re.Match) -> str:
        return m.group(0).replace(m.group(1), "[OTP]")

    text = _OTP_BEFORE.sub(_replace_otp_before, text)
    text = _OTP_AFTER.sub(_replace_otp_after, text)

    # Step 2: Aadhaar
    text = _AADHAAR.sub("[AADHAAR]", text)

    # Step 3: PAN
    text = _PAN.sub("[PAN]", text)

    # Step 4: Card numbers (13–19 digits left after Aadhaar consumed 12-digit ones)
    text = _CARD.sub("[CARD]", text)

    # Step 5: CVV (context-gated — replace the digit group only)
    def _replace_cvv(m: re.Match) -> str:
        return m.group(0).replace(m.group(1), "[CVV]")

    text = _CVV.sub(_replace_cvv, text)

    # Step 6: UPI VPA
    text = _UPI.sub("[UPI]", text)

    # Step 7: Phone (10 digits 6–9 start; after UPI so 9876543210@upi is already [UPI])
    text = _PHONE.sub("[PHONE]", text)

    return text
