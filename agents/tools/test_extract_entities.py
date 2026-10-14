"""
Tests for extract_entities.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agents.tools.extract_entities import _extract_entities_impl as extract_entities


class TestURLs:
    def test_http_url(self):
        r = extract_entities("Visit https://sbi-kyc-update.online to update.")
        assert "https://sbi-kyc-update.online" in r["urls"]
        assert r["has_url"] is True

    def test_bare_domain(self):
        r = extract_entities("Pay at dhl-customs-clear.top/pay now.")
        assert r["has_url"] is True

    def test_shortener(self):
        # Eval row 11 — bit.ly URL
        r = extract_entities(
            "ಕೆವೈಸಿ ಅಪ್‌ಡೇಟ್ ಮಾಡಲು ಈ ಲಿಂಕ್ ಕ್ಲಿಕ್ ಮಾಡಿ: bit.ly/kyc-upd8"
        )
        assert r["has_url"] is True
        assert any("bit.ly" in u for u in r["urls"])

    def test_no_url(self):
        r = extract_entities("Good morning everyone.")
        assert r["has_url"] is False
        assert r["urls"] == []


class TestPhones:
    def test_10_digit_mobile(self):
        r = extract_entities("Call officer 9876543210 immediately.")
        assert "9876543210" in r["phones"]
        assert r["has_personal_mobile"] is True

    def test_masked_number_not_captured(self):
        # 98xxxxxx21 contains non-digits — regex won't match
        r = extract_entities("Call 98xxxxxx21 for support.")
        assert r["has_personal_mobile"] is False

    def test_no_phone(self):
        r = extract_entities("Hi Appa, reached office safely.")
        assert r["has_personal_mobile"] is False


class TestAPK:
    def test_apk_filename(self):
        # Eval row 10
        r = extract_entities("Download HDFC_KYC.apk and complete verification.")
        assert r["has_apk"] is True
        assert any("apk" in a.lower() for a in r["apps"])

    def test_traffic_challan_apk(self):
        # Eval row 32
        r = extract_entities("RTO Traffic Challan.apk - open to check your pending fines.")
        assert r["has_apk"] is True

    def test_no_apk(self):
        r = extract_entities("Your order from MTR is out for delivery.")
        assert r["has_apk"] is False


class TestRemoteApps:
    def test_quicksupport(self):
        # Eval row 15
        r = extract_entities("install QuickSupport app and pay Rs 10 update charge.")
        assert r["has_remote_app"] is True
        assert "QuickSupport" in r["apps"]

    def test_anydesk(self):
        # Eval row 17
        r = extract_entities("install AnyDesk and share the 9 digit code.")
        assert r["has_remote_app"] is True

    def test_no_remote_app(self):
        r = extract_entities("Swiggy: Your order from MTR is out for delivery.")
        assert r["has_remote_app"] is False


class TestUPI:
    def test_upi_vpa(self):
        r = extract_entities("Send money to fraudster@okaxis now.")
        assert r["has_upi_id"] is True

    def test_no_upi(self):
        r = extract_entities("Good morning everyone, residents association meeting.")
        assert r["has_upi_id"] is False


class TestKeywords:
    def test_english_keywords(self):
        r = extract_entities("Your Aadhaar is linked to a CBI arrest case.")
        assert "Aadhaar" in r["keywords"]
        assert "CBI" in r["keywords"]
        assert "arrest" in r["keywords"]

    def test_hindi_keywords_row3(self):
        # Eval row 3 — Hindi digital arrest
        r = extract_entities(
            "मैं दिल्ली पुलिस से बोल रहा हूँ। आपके नाम से ड्रग्स का पार्सल पकड़ा गया है। "
            "वीडियो कॉल पर रहिए और किसी को मत बताइए, नहीं तो आपको गिरफ्तार किया जाएगा।"
        )
        assert "गिरफ्तार" in r["keywords"]
        assert "पुलिस" in r["keywords"]
        assert "पार्सल" in r["keywords"]

    def test_kannada_keywords_row4(self):
        # Eval row 4 — Kannada digital arrest
        r = extract_entities(
            "ನಾನು ಸೈಬರ್ ಕ್ರೈಮ್ ಪೊಲೀಸ್. ನಿಮ್ಮ ಆಧಾರ್ ಹಣ ವರ್ಗಾವಣೆ ಪ್ರಕರಣದಲ್ಲಿ ಇದೆ. "
            "ವಿಡಿಯೋ ಕಾಲ್‌ನಲ್ಲೇ ಇರಿ, ಯಾರಿಗೂ ಹೇಳಬೇಡಿ."
        )
        assert "ಪೊಲೀಸ್" in r["keywords"]
        assert "ಆಧಾರ್" in r["keywords"]

    def test_kannada_keywords_row11(self):
        # Eval row 11 — Kannada KYC
        r = extract_entities(
            "ಆತ್ಮೀಯ ಗ್ರಾಹಕರೇ, ನಿಮ್ಮ ಬ್ಯಾಂಕ್ ಖಾತೆ ಇಂದು ಬ್ಲಾಕ್ ಆಗುತ್ತದೆ. "
            "ಕೆವೈಸಿ ಅಪ್‌ಡೇಟ್ ಮಾಡಲು ಈ ಲಿಂಕ್ ಕ್ಲಿಕ್ ಮಾಡಿ: bit.ly/kyc-upd8"
        )
        assert "ಬ್ಲಾಕ್" in r["keywords"]
        assert "ಕ್ಲಿಕ್" in r["keywords"]
        assert "ಕೆವೈಸಿ" in r["keywords"]

    def test_genuine_has_no_scam_keywords(self):
        # Eval row 43 — genuine family message
        r = extract_entities("Hi Appa, reached office safely. Will call you in lunch break.")
        assert r["keywords"] == []
