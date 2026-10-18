"""
Offline fallbacks used only when watsonx Orchestrate is unreachable or returns
an unusable reply. Responses are marked source="rules"/"template" so the UI
and the eval can tell them apart from agent answers.

The rules alone miss new scam types, so the fallback never says "genuine":
it says "scam" when the rule score is high, otherwise "uncertain".
"""

from __future__ import annotations

_TEXT = {
    "en": {
        "scam": "This message shows common warning signs of a scam.",
        "uncertain": "We could not fully check this right now. Be careful.",
        "advice": "Do not pay, share any code, or install anything. If unsure, call a family member or 1930.",
        "alert": "Hello, I may have been targeted by a scam: {summary}. I have NOT sent any money or shared any codes. Please call me now.",
        "report": (
            "1. If you lost money, call 1930 right away. Speed helps stop the money.\n"
            "2. File a complaint at cybercrime.gov.in.\n"
            "3. Report the number or SMS on Chakshu (Sanchar Saathi portal).\n"
            "4. Tell your bank now if you shared any bank or UPI details."
        ),
    },
    "hi": {
        "scam": "इस संदेश में धोखाधड़ी के आम संकेत दिख रहे हैं।",
        "uncertain": "अभी हम इसकी पूरी जाँच नहीं कर पाए। सावधान रहें।",
        "advice": "कोई पैसा न भेजें, कोई कोड न बताएँ और कुछ भी इंस्टॉल न करें। शक हो तो परिवार को या 1930 पर फ़ोन करें।",
        "alert": "नमस्ते, शायद किसी ने मेरे साथ धोखा करने की कोशिश की है: {summary}। मैंने कोई पैसा नहीं भेजा है और कोई कोड नहीं बताया है। कृपया अभी मुझे फ़ोन करें।",
        "report": (
            "1. अगर पैसे गए हैं, तो तुरंत 1930 पर फ़ोन करें। जल्दी करने से पैसा रुक सकता है।\n"
            "2. cybercrime.gov.in पर शिकायत दर्ज करें।\n"
            "3. नंबर या SMS की शिकायत संचार साथी पोर्टल पर चक्षु में करें।\n"
            "4. अगर बैंक या UPI जानकारी दी है, तो अभी अपने बैंक को बताएँ।"
        ),
    },
    "kn": {
        "scam": "ಈ ಸಂದೇಶದಲ್ಲಿ ವಂಚನೆಯ ಸಾಮಾನ್ಯ ಲಕ್ಷಣಗಳು ಕಾಣುತ್ತಿವೆ.",
        "uncertain": "ಈಗ ಇದನ್ನು ಪೂರ್ತಿಯಾಗಿ ಪರಿಶೀಲಿಸಲು ಆಗಲಿಲ್ಲ. ಎಚ್ಚರವಾಗಿರಿ.",
        "advice": "ಹಣ ಕಳಿಸಬೇಡಿ, ಯಾವುದೇ ಕೋಡ್ ಹೇಳಬೇಡಿ, ಏನನ್ನೂ ಇನ್‌ಸ್ಟಾಲ್ ಮಾಡಬೇಡಿ. ಸಂದೇಹವಿದ್ದರೆ ಮನೆಯವರಿಗೆ ಅಥವಾ 1930ಗೆ ಕರೆ ಮಾಡಿ.",
        "alert": "ನಮಸ್ಕಾರ, ಯಾರೋ ನನಗೆ ವಂಚನೆ ಮಾಡಲು ಪ್ರಯತ್ನಿಸಿರಬಹುದು: {summary}. ನಾನು ಹಣ ಕಳಿಸಿಲ್ಲ, ಯಾವುದೇ ಕೋಡ್ ಹೇಳಿಲ್ಲ. ದಯವಿಟ್ಟು ಈಗಲೇ ನನಗೆ ಕರೆ ಮಾಡಿ.",
        "report": (
            "1. ಹಣ ಹೋಗಿದ್ದರೆ ತಕ್ಷಣ 1930ಗೆ ಕರೆ ಮಾಡಿ. ಬೇಗ ಕರೆ ಮಾಡಿದರೆ ಹಣ ತಡೆಯಬಹುದು.\n"
            "2. cybercrime.gov.in ನಲ್ಲಿ ದೂರು ನೀಡಿ.\n"
            "3. ಸಂಚಾರ ಸಾಥಿ ಪೋರ್ಟಲ್‌ನ ಚಕ್ಷುವಿನಲ್ಲಿ ಆ ನಂಬರ್ ಅಥವಾ SMS ಬಗ್ಗೆ ದೂರು ನೀಡಿ.\n"
            "4. ಬ್ಯಾಂಕ್ ಅಥವಾ UPI ವಿವರ ಹೇಳಿದ್ದರೆ ಈಗಲೇ ನಿಮ್ಮ ಬ್ಯಾಂಕ್‌ಗೆ ತಿಳಿಸಿ."
        ),
    },
}


def _t(lang: str) -> dict:
    return _TEXT.get(lang, _TEXT["en"])


# On a live call, any of these reported behaviours is enough to tell the user to
# stop: real officials, banks and family never ask for these on an unexpected call.
DANGER_CUES = {"police", "money", "otp", "secret", "app", "threat"}


def rules_verdict(urgency: dict, pattern: dict, lang: str, cues: list[str] | None = None) -> dict:
    t = _t(lang)
    is_scam = urgency.get("level") == "high" or bool(DANGER_CUES.intersection(cues or []))
    return {
        "verdict": "scam" if is_scam else "uncertain",
        "scam_type": pattern.get("scam_type"),
        "confidence": "medium" if is_scam else "low",
        "red_flags": [],
        "explanation": t["scam"] if is_scam else t["uncertain"],
        "advice": t["advice"],
    }


def alert_message(summary: str, lang: str) -> str:
    return _t(lang)["alert"].format(summary=summary.strip().rstrip("."))


def report_steps(lang: str) -> str:
    return _t(lang)["report"]
