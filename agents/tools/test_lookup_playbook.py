"""
Tests for lookup_playbook.

Verifies:
- Every known scam_type returns its own section (not the universal fallback).
- Unknown types return the "Universal red-flag signals" section.
- Eval row 1 scam_type (digital_arrest) returns the digital-arrest playbook.
- Eval row 37 scam_type (bank_otp, unknown) returns the universal fallback.
- Section content is non-empty and contains expected text.
- Case-insensitivity of scam_type input.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agents.tools.lookup_playbook import _lookup_playbook_impl as lookup_playbook

UNIVERSAL_MARKER = "Universal red-flag signals"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_universal(text: str) -> bool:
    return UNIVERSAL_MARKER in text


# ---------------------------------------------------------------------------
# Known scam types — each must return its own section, not the universal one
# ---------------------------------------------------------------------------

class TestKnownTypes:
    def test_digital_arrest(self):
        result = lookup_playbook("digital_arrest")
        assert "digital arrest" in result.lower()
        assert "CBI" in result or "police" in result.lower()
        assert not is_universal(result)

    def test_courier(self):
        result = lookup_playbook("courier")
        assert "courier" in result.lower()
        assert not is_universal(result)

    def test_kyc(self):
        result = lookup_playbook("kyc")
        assert "kyc" in result.lower()
        assert not is_universal(result)

    def test_electricity(self):
        result = lookup_playbook("electricity")
        assert "electricity" in result.lower()
        assert not is_universal(result)

    def test_fake_customer_care(self):
        result = lookup_playbook("fake_customer_care")
        assert "customer care" in result.lower()
        assert not is_universal(result)

    def test_upi_mistake(self):
        result = lookup_playbook("upi_mistake")
        assert "mistake" in result.lower()
        assert not is_universal(result)

    def test_relative_emergency(self):
        result = lookup_playbook("relative_emergency")
        assert "relative" in result.lower() or "emergency" in result.lower()
        assert not is_universal(result)

    def test_investment(self):
        result = lookup_playbook("investment")
        assert "investment" in result.lower() or "sebi" in result.lower()
        assert not is_universal(result)

    def test_job_task(self):
        result = lookup_playbook("job_task")
        assert "job" in result.lower() or "task" in result.lower()
        assert not is_universal(result)

    def test_lottery(self):
        result = lookup_playbook("lottery")
        assert "lottery" in result.lower() or "kbc" in result.lower()
        assert not is_universal(result)

    def test_pension(self):
        result = lookup_playbook("pension")
        assert "pension" in result.lower()
        assert not is_universal(result)

    def test_echallan(self):
        result = lookup_playbook("echallan")
        assert "challan" in result.lower() or "e-challan" in result.lower()
        assert not is_universal(result)

    def test_lpg(self):
        result = lookup_playbook("lpg")
        assert "lpg" in result.lower() or "gas" in result.lower()
        assert not is_universal(result)

    def test_sextortion(self):
        result = lookup_playbook("sextortion")
        assert "sextortion" in result.lower() or "video call" in result.lower()
        assert not is_universal(result)


# ---------------------------------------------------------------------------
# Unknown / fallback types
# ---------------------------------------------------------------------------

class TestFallback:
    def test_unknown_type_returns_universal(self):
        result = lookup_playbook("unknown_scam_xyz")
        assert is_universal(result)

    def test_empty_string_returns_universal(self):
        result = lookup_playbook("")
        assert is_universal(result)

    def test_bank_otp_returns_universal(self):
        # eval row 37: label=genuine, scam_type=bank_otp — not a playbook entry
        result = lookup_playbook("bank_otp")
        assert is_universal(result)
        # The universal section should contain the high-weight signals table
        assert "arrest" in result.lower() or "OTP" in result

    def test_universal_section_content(self):
        result = lookup_playbook("totally_unknown")
        assert "High" in result
        assert "Medium" in result
        assert "Low" in result


# ---------------------------------------------------------------------------
# Case-insensitivity
# ---------------------------------------------------------------------------

class TestCaseInsensitive:
    def test_uppercase_slug(self):
        result = lookup_playbook("DIGITAL_ARREST")
        assert "digital arrest" in result.lower()
        assert not is_universal(result)

    def test_mixed_case_slug(self):
        result = lookup_playbook("Lottery")
        assert "lottery" in result.lower()
        assert not is_universal(result)


# ---------------------------------------------------------------------------
# Eval-row smoke tests
# ---------------------------------------------------------------------------

class TestEvalRows:
    def test_row1_digital_arrest(self):
        """Eval row 1: scam, digital_arrest — must get the digital arrest playbook."""
        result = lookup_playbook("digital_arrest")
        # Playbook text should contain the key reality-check sentence
        assert "digital arrest" in result.lower()
        assert "hang up" in result.lower() or "police never arrest" in result.lower()

    def test_row37_bank_otp_fallback(self):
        """Eval row 37: genuine, bank_otp — no playbook exists, must get universal fallback."""
        result = lookup_playbook("bank_otp")
        assert is_universal(result)
        # Universal fallback should mention OTP (it's in the signals table)
        assert "OTP" in result
