"""
Tests for check_link.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agents.tools.check_link import _check_link_impl as check_link


def result_for(url):
    results = check_link([url])
    assert len(results) == 1
    return results[0]


class TestAllowlist:
    def test_sbi_allowlisted(self):
        r = result_for("https://sbi.co.in/login")
        assert r["suspicious"] is False
        assert r["reason"] == "allowlisted"

    def test_parivahan_allowlisted(self):
        r = result_for("https://parivahan.gov.in")
        assert r["suspicious"] is False


class TestShorteners:
    def test_bitly(self):
        # Eval row 11
        r = result_for("bit.ly/kyc-upd8")
        assert r["suspicious"] is True
        assert "shortener" in r["reason"].lower()

    def test_tinyurl(self):
        r = result_for("https://tinyurl.com/abc123")
        assert r["suspicious"] is True


class TestSuspiciousTLD:
    def test_dot_top(self):
        # Eval row 7: dhl-customs-clear.top/pay
        r = result_for("dhl-customs-clear.top/pay")
        assert r["suspicious"] is True

    def test_dot_online(self):
        # Eval row 9: sbi-kyc-update.online
        r = result_for("sbi-kyc-update.online")
        assert r["suspicious"] is True

    def test_incometax_dot_online(self):
        # Eval row 35
        r = result_for("incometax-refund-gov.online")
        assert r["suspicious"] is True

    def test_lpg_ekyc_in(self):
        # Eval row 33: lpg-ekyc-update.in — brand in domain, suspicious
        r = result_for("lpg-ekyc-update.in")
        assert r["suspicious"] is True


class TestBrandLookalike:
    def test_sbi_lookalike(self):
        r = result_for("https://sbi-netbanking.com/login")
        assert r["suspicious"] is True
        assert "lookalike" in r["reason"].lower()

    def test_hdfc_lookalike(self):
        r = result_for("hdfc-kyc-portal.in")
        assert r["suspicious"] is True

    def test_echallan_lookalike(self):
        # Eval row 31: echallan-parivahan.co/pay
        r = result_for("echallan-parivahan.co/pay")
        assert r["suspicious"] is True


class TestEmpty:
    def test_empty_list(self):
        assert check_link([]) == []

    def test_multiple_mixed(self):
        results = check_link(["sbi.co.in", "bit.ly/abc", "sbi-fake.online"])
        safe = [r for r in results if not r["suspicious"]]
        sus = [r for r in results if r["suspicious"]]
        assert len(safe) == 1
        assert len(sus) == 2
