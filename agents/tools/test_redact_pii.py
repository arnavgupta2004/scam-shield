"""
Tests for redact_pii.redact_pii.

Covers every PII type, uses eval-set rows as ground-truth fixtures,
and verifies that non-PII content (URLs, plain text) is untouched.
"""

import sys
import os

# Allow running from repo root without install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agents.tools.redact_pii import redact_pii


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------

class TestOTP:
    def test_otp_before_digits(self):
        # "OTP 482913" — eval row 53
        result = redact_pii("OTP 482913 for transaction of Rs 2,000 at RELIANCE DIGITAL. Do not share with anyone, including bank staff.")
        assert "[OTP]" in result
        assert "482913" not in result
        # surrounding text preserved
        assert "RELIANCE DIGITAL" in result
        assert "Do not share" in result

    def test_otp_digits_then_label(self):
        # "123456 is your OTP" — eval row 37
        result = redact_pii("123456 is your OTP for login to SBI YONO. Valid for 5 mins. Do not share OTP with anyone. -SBI")
        assert "[OTP]" in result
        assert "123456" not in result
        # rest of message intact
        assert "SBI YONO" in result
        assert "Do not share OTP" in result

    def test_otp_colon_format(self):
        result = redact_pii("Your verification code: 938271. Do not share.")
        assert "[OTP]" in result
        assert "938271" not in result

    def test_pin_label(self):
        result = redact_pii("Enter PIN 4567 to confirm.")
        assert "[OTP]" in result
        assert "4567" not in result

    def test_otp_not_fired_without_context(self):
        # A bare number with no OTP context should NOT be redacted as OTP
        # (it might get caught by phone/card/Aadhaar, but that's tested separately)
        result = redact_pii("Order total is Rs 1200.")
        assert "[OTP]" not in result


# ---------------------------------------------------------------------------
# Aadhaar
# ---------------------------------------------------------------------------

class TestAadhaar:
    def test_12_consecutive_digits(self):
        result = redact_pii("Your Aadhaar number is 234567891234.")
        assert "[AADHAAR]" in result
        assert "234567891234" not in result

    def test_spaced_groups(self):
        result = redact_pii("Aadhaar: 2345 6789 1234")
        assert "[AADHAAR]" in result
        assert "2345 6789 1234" not in result

    def test_hyphen_groups(self):
        result = redact_pii("Aadhaar: 2345-6789-1234")
        assert "[AADHAAR]" in result
        assert "2345-6789-1234" not in result


# ---------------------------------------------------------------------------
# PAN
# ---------------------------------------------------------------------------

class TestPAN:
    def test_standard_pan(self):
        result = redact_pii("My PAN is ABCDE1234F and I need help.")
        assert "[PAN]" in result
        assert "ABCDE1234F" not in result

    def test_pan_not_partial_word(self):
        # Should not match random all-caps that don't fit PAN format
        result = redact_pii("HELLO WORLD FROM INDIA")
        assert "[PAN]" not in result


# ---------------------------------------------------------------------------
# Card numbers
# ---------------------------------------------------------------------------

class TestCard:
    def test_16_digit_card(self):
        result = redact_pii("Card number 4111111111111111 is invalid.")
        assert "[CARD]" in result
        assert "4111111111111111" not in result

    def test_13_digit_card(self):
        result = redact_pii("Use card 4000000000000.")
        assert "[CARD]" in result

    def test_19_digit_card(self):
        result = redact_pii("Long card 4111111111111111222.")
        assert "[CARD]" in result


# ---------------------------------------------------------------------------
# CVV
# ---------------------------------------------------------------------------

class TestCVV:
    def test_cvv_label(self):
        result = redact_pii("Enter CVV 123 to complete payment.")
        assert "[CVV]" in result
        assert "123" not in result

    def test_cvc_label(self):
        result = redact_pii("CVC: 4567")
        assert "[CVV]" in result
        assert "4567" not in result

    def test_cvv_eval_row_35(self):
        # Eval row 35: asks for card CVV
        result = redact_pii(
            "Submit bank details and card CVV at incometax-refund-gov.online to receive."
        )
        # No CVV digits in this text so no replacement, but URL must be untouched
        assert "incometax-refund-gov.online" in result


# ---------------------------------------------------------------------------
# UPI VPA
# ---------------------------------------------------------------------------

class TestUPI:
    def test_upi_vpa(self):
        result = redact_pii("Send to 98765@okaxis urgently.")
        assert "[UPI]" in result
        assert "98765@okaxis" not in result

    def test_upi_word_at_word(self):
        result = redact_pii("UPI id: rahul.sharma@ybl")
        assert "[UPI]" in result
        assert "rahul.sharma@ybl" not in result

    def test_email_also_redacted(self):
        # UPI pattern also catches emails — acceptable for this use-case
        result = redact_pii("Contact me at user@example.com for details.")
        assert "user@example.com" not in result


# ---------------------------------------------------------------------------
# Phone numbers
# ---------------------------------------------------------------------------

class TestPhone:
    def test_10_digit_mobile(self):
        result = redact_pii("Call officer 9876543210 immediately.")
        assert "[PHONE]" in result
        assert "9876543210" not in result

    def test_6_start_mobile(self):
        result = redact_pii("Callback: 6000001234")
        assert "[PHONE]" in result

    def test_non_indian_number_not_redacted(self):
        # 10-digit number starting with 5 — not an Indian mobile
        result = redact_pii("Number 5123456789")
        assert "[PHONE]" not in result

    def test_masked_number_untouched(self):
        # Already-masked numbers like 98xxxxxx21 contain non-digits — not matched
        result = redact_pii("Call 98xxxxxx21 for support.")
        assert "[PHONE]" not in result
        assert "98xxxxxx21" in result


# ---------------------------------------------------------------------------
# Non-PII must survive untouched
# ---------------------------------------------------------------------------

class TestNonPII:
    def test_url_not_redacted(self):
        # Eval row 9 — URL must pass through; redact_pii must not touch domains
        result = redact_pii(
            "Dear customer your SBI account will be blocked today. "
            "Update PAN KYC immediately: sbi-kyc-update.online"
        )
        assert "sbi-kyc-update.online" in result

    def test_genuine_bank_debit_untouched(self):
        # Eval row 38 — Rs amount and partial account are not PII
        result = redact_pii(
            "Rs 1,250.00 debited from a/c XX1234 on 12-10-26 to BIGBASKET via UPI. "
            "Not you? Call 1800 1234 -Bank"
        )
        assert "BIGBASKET" in result
        # Toll-free 1800 1234 is 9 digits total (with space) — not an Indian mobile
        assert "1800" in result

    def test_plain_message_untouched(self):
        result = redact_pii("Good morning everyone, residents association meeting this Sunday.")
        assert result == "Good morning everyone, residents association meeting this Sunday."

    def test_rupee_amount_not_redacted(self):
        # Rs 25,00,000 — comma-separated, not a plain digit string
        result = redact_pii("You have won Rs 25,00,000 in KBC lottery.")
        assert "25,00,000" in result

    def test_account_partial_not_redacted(self):
        # XX1234 — partial account number, not a full digit run
        result = redact_pii("Rs 32,500.00 credited to a/c XX1234.")
        assert "XX1234" in result


# ---------------------------------------------------------------------------
# Eval-set row snapshots
# ---------------------------------------------------------------------------

class TestEvalRows:
    def test_row_37_otp_message(self):
        """Eval row 37 — genuine SBI OTP. OTP digits redacted, safety text preserved."""
        original = "123456 is your OTP for login to SBI YONO. Valid for 5 mins. Do not share OTP with anyone. -SBI"
        result = redact_pii(original)
        assert "123456" not in result
        assert "[OTP]" in result
        assert "SBI YONO" in result
        assert "Do not share OTP" in result
        assert "-SBI" in result

    def test_row_53_otp_message(self):
        """Eval row 53 — transaction OTP. Digits redacted, context preserved."""
        original = "OTP 482913 for transaction of Rs 2,000 at RELIANCE DIGITAL. Do not share with anyone, including bank staff."
        result = redact_pii(original)
        assert "482913" not in result
        assert "[OTP]" in result
        assert "RELIANCE DIGITAL" in result
        assert "Do not share with anyone" in result

    def test_row_9_url_survives(self):
        """Eval row 9 — scam URL must survive so check_link can analyse it."""
        original = "Dear customer your SBI account will be blocked today. Update PAN KYC immediately: sbi-kyc-update.online"
        result = redact_pii(original)
        assert "sbi-kyc-update.online" in result

    def test_row_2_no_false_redaction(self):
        """Eval row 2 — digital arrest scam. No real PII in text; message largely preserved."""
        original = (
            "CBI notice: An arrest warrant has been issued in your name. "
            "To verify your funds transfer your savings to the RBI safe account "
            "given by the officer. Amount will be returned after verification."
        )
        result = redact_pii(original)
        assert "CBI notice" in result
        assert "RBI safe account" in result
