"""
draft_family_alert.py — draft a short alert message for a family member.

Hard requirement: user_confirmed MUST be True or the function refuses.
The alert is returned as text for the user to send themselves via SMS/WhatsApp;
this tool never sends anything.
"""

import re
from ibm_watsonx_orchestrate.agent_builder.tools import tool


@tool
def draft_family_alert(message_summary: str, lang: str, user_confirmed: bool = False) -> dict:
    """
    Draft a short alert message from a senior citizen to a trusted family member
    about a possible scam. Refuses unless user_confirmed is True.

    Args:
        message_summary: A brief description of the suspected scam (no OTPs,
                         PINs, or card numbers — include only what the scammer
                         asked for and whether any money/codes were shared).
        lang:            Language for the alert: "en", "hi", or "kn".
        user_confirmed:  Must be True (set by the app after the user taps
                         "Yes, send alert" in the ConfirmDialog). Defaults to
                         False; the tool refuses if not explicitly True.

    Returns:
        A dict with:
          status  — "drafted" on success, "needs_confirmation" if refused
          message — the alert text (present only when status is "drafted")
    """
    if not user_confirmed:
        return {"status": "needs_confirmation"}

    # Strip any residual PII patterns that may have slipped through
    _pii_re = re.compile(
        r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"   # Aadhaar-like
        r"|\b[A-Z]{5}\d{4}[A-Z]\b"              # PAN
        r"|\b(?:OTP|PIN|CVV)\s*[:\-]?\s*\d{4,8}\b"
        r"|\b(?:card|account)\s*(?:no|number)?\.?\s*\d[\d\s\-]{11,18}\b",
        re.IGNORECASE,
    )
    safe_summary = _pii_re.sub("[REDACTED]", message_summary)

    if lang == "hi":
        message = (
            f"नमस्ते, मुझे एक संभावित धोखे का सामना हुआ: {safe_summary}. "
            "मैंने कोई पैसे नहीं भेजे हैं और कोई कोड शेयर नहीं किया है। "
            "कृपया अभी मुझे फोन करें।"
        )
    elif lang == "kn":
        message = (
            f"ನಮಸ್ಕಾರ, ನನಗೆ ಒಂದು ಸಂಭಾವ್ಯ ವಂಚನೆ ಎದುರಾಗಿದೆ: {safe_summary}. "
            "ನಾನು ಯಾವುದೇ ಹಣ ಕಳಿಸಿಲ್ಲ ಮತ್ತು ಯಾವುದೇ ಕೋಡ್ ಹಂಚಿಕೊಂಡಿಲ್ಲ. "
            "ದಯವಿಟ್ಟು ಈಗ ನನಗೆ ಕರೆ ಮಾಡಿ."
        )
    else:  # default: English
        message = (
            f"Hello, I may have been targeted by a scam: {safe_summary}. "
            "I have NOT sent any money or shared any codes. "
            "Please call me now."
        )

    return {"status": "drafted", "message": message}
