"""
redact_pii.py — strip PII from text before any LLM call.

Redacts (in order):
  0. Spaced/hyphenated card numbers (4-4-4-4 Visa/MC, 4-6-5 Amex) — before Aadhaar
     so "4111 1111 1111 1111" is not partially consumed as a 12-digit Aadhaar.
  1. OTP / verification code (4–8 digits, context-gated, word-boundary on keyword)
  2. Aadhaar (exactly 12 digits, possibly space/hyphen separated in groups of 4)
  3. PAN (ABCDE1234F format)
  4. Card numbers (13–19 consecutive digits)
  5. CVV (3–4 digits, context-gated)
  6. UPI VPA (word@word)
  7. Indian mobile numbers (10 digits, starts 6–9, optional +91/0 prefix,
     optional single space/hyphen after first 5 digits)

Replacements: [OTP], [AADHAAR], [PAN], [CARD], [CVV], [UPI], [PHONE]
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Patterns — ordered from most-specific / longest to least-specific
# ---------------------------------------------------------------------------

# 0. Spaced/hyphenated card numbers — must come BEFORE Aadhaar.
#    Visa/Mastercard: 4-4-4-4 groups (sep by space or hyphen)
#    Amex:            4-6-5 groups
#    Each group boundary requires exactly one space or hyphen.
_CARD_SPACED = re.compile(
    r"(?<!\d)"
    r"(?:"
    r"\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}"   # 4-4-4-4  (16 digits)
    r"|"
    r"\d{4}[- ]\d{6}[- ]\d{5}"              # 4-6-5    (15 digits, Amex)
    r")"
    r"(?!\d)"
)

# 1. OTP: 4–8 digits preceded (or followed) by an OTP-signal word.
#    \b before the keyword ensures "pincode" doesn't match "code",
#    and "passcode" / "pincode" as compound words are excluded by the \b guard.
#    Handles:  "OTP 482913", "123456 is your OTP", "verification code: 7890"
_OTP_BEFORE = re.compile(
    r"(?i)"
    r"\b(?:otp|one[- ]time[- ](?:password|code)|verification[- ]code|passcode)\b"
    r"[\s:]*"
    r"(\b\d{4,8}\b)",
)
# Separate pattern for bare "code" and "pin" — require them to stand alone
# (preceded by whitespace/start and followed by whitespace/punctuation)
# so they don't fire inside compound words like "pincode" or "barcode".
_OTP_BEFORE_SHORT = re.compile(
    r"(?i)"
    r"(?:^|(?<=\s)|(?<=:))"          # start / preceded by whitespace or colon
    r"(?:code|pin)"
    r"(?=[\s:])"                      # followed by whitespace or colon
    r"[\s:]*"
    r"(\b\d{4,8}\b)",
)
_OTP_AFTER = re.compile(
    r"\b(\d{4,8})\b"
    r"[\s]*(?:is[- ]your[- ])?"
    r"(?:otp|one[- ]time[- ](?:password|code)|verification[- ]code|passcode)\b",
    re.IGNORECASE,
)

# 2. Aadhaar: 12 consecutive digits OR groups of 4 separated by spaces/hyphens.
#    (Spaced cards already consumed above, so 4-4-4 no longer collides.)
_AADHAAR = re.compile(
    r"(?<!\d)"
    r"(?:\d{4}[- ]\d{4}[- ]\d{4}|\d{12})"
    r"(?!\d)"
)

# 3. PAN: exactly AAAAA9999A (5 uppercase letters, 4 digits, 1 uppercase letter)
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")

# 4. Card numbers: 13–19 consecutive digits not yet consumed.
_CARD = re.compile(r"(?<!\d)\d{13,19}(?!\d)")

# 5. CVV: 3–4 digits after CVV/CVC/security code
_CVV = re.compile(
    r"(?i)(?:cvv|cvc|security[- ]code)[\s:]*(\b\d{3,4}\b)"
)

# 6. UPI VPA: word@word (e.g. john@okaxis, 9876543210@upi)
_UPI = re.compile(r"\b[\w.\-]{2,}@[\w.\-]{2,}\b")

# 7a. Prefixed phone — +91 or 0 prefix; must run BEFORE Aadhaar because
#     "+919876543210" contains 12 consecutive digits after the + which
#     would otherwise match _AADHAAR.
_PHONE_PREFIXED = re.compile(
    r"(?:"
    r"\+91[\s-]?[6-9]\d{4}[\s-]?\d{5}"   # +91 prefix, optional mid-split
    r"|"
    r"0[6-9]\d{4}[\s-]?\d{5}"             # 0 prefix, optional mid-split
    r")"
)

# 7b. Bare phone — no prefix; run after UPI so 9876543210@upi is already [UPI].
#     Covers bare 10-digit and 5-5 split without prefix.
_PHONE_BARE = re.compile(
    r"(?:"
    r"[6-9]\d{4}[\s-]\d{5}"          # 5-5 with mandatory separator
    r"|"
    r"(?<!\d)[6-9]\d{9}(?!\d)"       # 10 consecutive digits
    r")"
)


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
    # Step 0: Spaced/hyphenated card numbers (before Aadhaar to avoid 4-4-4 collision)
    text = _CARD_SPACED.sub("[CARD]", text)

    # Step 0.5: Prefixed phones (+91/0) before Aadhaar, because +919876543210
    #           contains 12 consecutive digits that _AADHAAR would otherwise consume.
    text = _PHONE_PREFIXED.sub("[PHONE]", text)

    # Step 1: OTP (context-gated — replace the digit group only, preserve label)
    def _replace_otp_before(m: re.Match) -> str:
        return m.group(0).replace(m.group(1), "[OTP]")

    text = _OTP_BEFORE.sub(_replace_otp_before, text)
    text = _OTP_BEFORE_SHORT.sub(_replace_otp_before, text)
    text = _OTP_AFTER.sub(lambda m: m.group(0).replace(m.group(1), "[OTP]"), text)

    # Step 2: Aadhaar
    text = _AADHAAR.sub("[AADHAAR]", text)

    # Step 3: PAN
    text = _PAN.sub("[PAN]", text)

    # Step 4: Card numbers (13–19 consecutive digits not yet consumed)
    text = _CARD.sub("[CARD]", text)

    # Step 5: CVV (context-gated — replace the digit group only)
    def _replace_cvv(m: re.Match) -> str:
        return m.group(0).replace(m.group(1), "[CVV]")

    text = _CVV.sub(_replace_cvv, text)

    # Step 6: UPI VPA
    text = _UPI.sub("[UPI]", text)

    # Step 7: Bare phones (after UPI so 9876543210@upi is already [UPI])
    text = _PHONE_BARE.sub("[PHONE]", text)

    return text
