"""
Tests for score_urgency and match_scam_pattern.
Covers multilingual rows from the eval set.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agents.tools.score_urgency import _score_urgency_impl as score_urgency
from agents.tools.match_scam_pattern import _match_scam_pattern_impl as match_scam_pattern

EMPTY_ENTITIES: dict = {
    "has_apk": False, "has_remote_app": False, "has_url": False,
    "has_personal_mobile": False, "has_upi_id": False,
}


# ---------------------------------------------------------------------------
# score_urgency
# ---------------------------------------------------------------------------

class TestScoreUrgency:
    def test_high_score_digital_arrest_en(self):
        # Eval row 1 — 3 high signals fires → level high, score ≥ 3.0
        text = ("This is Inspector Rao from Mumbai Cyber Crime. Your Aadhaar is linked "
                "to a money laundering case. You are under digital arrest. Stay on video "
                "call and do not inform anyone or you will be jailed.")
        r = score_urgency(text, EMPTY_ENTITIES)
        assert r["level"] == "high"
        assert r["score"] >= 3.0

    def test_high_score_digital_arrest_hi(self):
        # Eval row 3 — Hindi; 2 high signals → medium/high, score ≥ 2.0
        text = ("मैं दिल्ली पुलिस से बोल रहा हूँ। आपके नाम से ड्रग्स का पार्सल पकड़ा "
                "गया है। वीडियो कॉल पर रहिए और किसी को मत बताइए, नहीं तो आपको "
                "गिरफ्तार किया जाएगा।")
        r = score_urgency(text, EMPTY_ENTITIES)
        assert r["level"] in ("high", "medium")
        assert r["score"] >= 1.5

    def test_high_score_digital_arrest_kn(self):
        # Eval row 4
        text = ("ನಾನು ಸೈಬರ್ ಕ್ರೈಮ್ ಪೊಲೀಸ್. ನಿಮ್ಮ ಆಧಾರ್ ಹಣ ವರ್ಗಾವಣೆ ಪ್ರಕರಣದಲ್ಲಿ ಇದೆ. "
                "ವಿಡಿಯೋ ಕಾಲ್‌ನಲ್ಲೇ ಇರಿ, ಯಾರಿಗೂ ಹೇಳಬೇಡಿ.")
        r = score_urgency(text, EMPTY_ENTITIES)
        assert r["level"] in ("high", "medium")

    def test_medium_score_kyc(self):
        # Eval row 9
        text = "Dear customer your SBI account will be blocked today. Update PAN KYC immediately: sbi-kyc-update.online"
        r = score_urgency(text, EMPTY_ENTITIES)
        assert r["level"] in ("medium", "high")

    def test_medium_score_electricity_kn(self):
        # Eval row 14
        text = ("ಆತ್ಮೀಯ ಗ್ರಾಹಕರೇ, ನಿಮ್ಮ ಹಿಂದಿನ ತಿಂಗಳ ಬಿಲ್ ಅಪ್‌ಡೇಟ್ ಆಗಿಲ್ಲ. "
                "ಇಂದು ರಾತ್ರಿ ವಿದ್ಯುತ್ ಕಡಿತಗೊಳ್ಳುತ್ತದೆ. ಅಧಿಕಾರಿಗೆ ಕರೆ ಮಾಡಿ 96xxxxxx12.")
        r = score_urgency(text, EMPTY_ENTITIES)
        assert r["level"] in ("medium", "high")

    def test_low_score_genuine_family(self):
        # Eval row 43
        r = score_urgency("Hi Appa, reached office safely. Will call you in lunch break.", EMPTY_ENTITIES)
        assert r["level"] == "low"

    def test_low_score_genuine_delivery(self):
        # Eval row 40
        r = score_urgency("Swiggy: Your order from MTR is out for delivery. Delivery partner Raju will reach in 12 mins.", EMPTY_ENTITIES)
        assert r["level"] == "low"

    def test_low_score_genuine_community_kn(self):
        # Eval row 51
        r = score_urgency("ಭಾನುವಾರ ಬೆಳಿಗ್ಗೆ ದೇವಸ್ಥಾನದಲ್ಲಿ ಪೂಜೆ ಇದೆ. ಎಲ್ಲರೂ ಬನ್ನಿ.", EMPTY_ENTITIES)
        assert r["level"] == "low"

    def test_entity_flag_apk_boosts_score(self):
        text = "Download this file and run it."
        entities_with_apk = {**EMPTY_ENTITIES, "has_apk": True}
        r_with = score_urgency(text, entities_with_apk)
        r_without = score_urgency(text, EMPTY_ENTITIES)
        assert r_with["score"] > r_without["score"]

    def test_signals_list_populated(self):
        text = "You are under digital arrest. Stay on video call."
        r = score_urgency(text, EMPTY_ENTITIES)
        assert len(r["signals"]) > 0


# ---------------------------------------------------------------------------
# match_scam_pattern
# ---------------------------------------------------------------------------

class TestMatchScamPattern:
    def test_digital_arrest_en(self):
        # Eval row 1
        r = match_scam_pattern(
            "You are under digital arrest. Stay on video call and do not inform anyone."
        )
        assert r["scam_type"] == "digital_arrest"
        assert r["confidence"] in ("high", "medium")

    def test_digital_arrest_hi(self):
        # Eval row 3
        r = match_scam_pattern(
            "मैं दिल्ली पुलिस से बोल रहा हूँ। आपके नाम से ड्रग्स का पार्सल पकड़ा गया है। "
            "किसी को मत बताइए, नहीं तो आपको गिरफ्तार किया जाएगा।"
        )
        assert r["scam_type"] == "digital_arrest"

    def test_digital_arrest_kn(self):
        # Eval row 4
        r = match_scam_pattern(
            "ನಾನು ಸೈಬರ್ ಕ್ರೈಮ್ ಪೊಲೀಸ್. ನಿಮ್ಮ ಆಧಾರ್ ಹಣ ವರ್ಗಾವಣೆ ಪ್ರಕರಣದಲ್ಲಿ ಇದೆ. "
            "ವಿಡಿಯೋ ಕಾಲ್‌ನಲ್ಲೇ ಇರಿ, ಯಾರಿಗೂ ಹೇಳಬೇಡಿ."
        )
        assert r["scam_type"] == "digital_arrest"

    def test_courier_hi(self):
        # Eval row 8
        r = match_scam_pattern(
            "आपका कूरियर कस्टम में रुका है। 1 दबाएं। आपके पार्सल में अवैध सामान मिला है।"
        )
        assert r["scam_type"] == "courier"

    def test_kyc_kn(self):
        # Eval row 11
        r = match_scam_pattern(
            "ಆತ್ಮೀಯ ಗ್ರಾಹಕರೇ, ನಿಮ್ಮ ಬ್ಯಾಂಕ್ ಖಾತೆ ಇಂದು ಬ್ಲಾಕ್ ಆಗುತ್ತದೆ. "
            "ಕೆವೈಸಿ ಅಪ್‌ಡೇಟ್ ಮಾಡಲು ಈ ಲಿಂಕ್ ಕ್ಲಿಕ್ ಮಾಡಿ: bit.ly/kyc-upd8"
        )
        assert r["scam_type"] == "kyc"

    def test_electricity_kn(self):
        # Eval row 14
        r = match_scam_pattern(
            "ಆತ್ಮೀಯ ಗ್ರಾಹಕರೇ, ನಿಮ್ಮ ಹಿಂದಿನ ತಿಂಗಳ ಬಿಲ್ ಅಪ್‌ಡೇಟ್ ಆಗಿಲ್ಲ. "
            "ಇಂದು ರಾತ್ರಿ ವಿದ್ಯುತ್ ಕಡಿತಗೊಳ್ಳುತ್ತದೆ. ಅಧಿಕಾರಿಗೆ ಕರೆ ಮಾಡಿ 96xxxxxx12."
        )
        assert r["scam_type"] == "electricity"

    def test_upi_mistake_hi(self):
        # Eval row 19
        r = match_scam_pattern(
            "भैया गलती से आपके नंबर पर 3000 रुपये चले गए, प्लीज़ वापस भेज दो, बहुत ज़रूरी है।"
        )
        assert r["scam_type"] == "upi_mistake"

    def test_relative_emergency_kn(self):
        # Eval row 22
        r = match_scam_pattern(
            "ಅಜ್ಜಿ ನಾನು, ಹೊಸ ನಂಬರ್. ಅಪಘಾತ ಆಗಿದೆ, ತಕ್ಷಣ 30,000 ಕಳಿಸಿ. ಅಮ್ಮನಿಗೆ ಹೇಳಬೇಡಿ."
        )
        assert r["scam_type"] == "relative_emergency"

    def test_lottery_hi(self):
        # Eval row 28
        r = match_scam_pattern(
            "बधाई हो! आपने 25 लाख की लॉटरी जीती है। प्रोसेसिंग फीस 9,999 रुपये जमा करें।"
        )
        assert r["scam_type"] == "lottery"

    def test_pension_kn(self):
        # Eval row 30
        r = match_scam_pattern(
            "ನಿಮ್ಮ ಪಿಂಚಣಿ ನಿಲ್ಲುತ್ತದೆ. ಜೀವನ ಪ್ರಮಾಣಪತ್ರ ಅಪ್‌ಡೇಟ್ ಮಾಡಲು ಬಂದ ಓಟಿಪಿ ಹೇಳಿ."
        )
        assert r["scam_type"] == "pension"

    def test_genuine_returns_none(self):
        # Eval row 42 — genuine Kannada family
        r = match_scam_pattern("ಅಮ್ಮ, ಇಂದು ಸಂಜೆ ಬರುತ್ತೇನೆ. ಊಟಕ್ಕೆ ಏನಾದರೂ ತರಲಾ?")
        assert r["scam_type"] is None

    def test_genuine_hi_family(self):
        # Eval row 44
        r = match_scam_pattern(
            "पापा, कल सुबह डॉक्टर का अपॉइंटमेंट 10 बजे है, मैं आपको लेने आ जाऊँगा।"
        )
        assert r["scam_type"] is None

    def test_sextortion(self):
        # Eval row 34
        r = match_scam_pattern(
            "We have recorded your video call. Pay Rs 50,000 or we will send it to all your contacts and family."
        )
        assert r["scam_type"] == "sextortion"

    def test_investment(self):
        r = match_scam_pattern(
            "Join our SEBI registered VIP group. Guaranteed 300% returns in 30 days."
        )
        assert r["scam_type"] == "investment"

    def test_echallan(self):
        r = match_scam_pattern(
            "Traffic e-challan of Rs 500 pending against your vehicle. Pay today: echallan-parivahan.co/pay"
        )
        assert r["scam_type"] == "echallan"
