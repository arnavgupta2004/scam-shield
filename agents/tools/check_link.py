"""
check_link.py — classify URLs as suspicious or safe.

Flags a URL as suspicious if:
  - Domain is a known URL shortener
  - TLD is in the suspicious set (.top, .xyz, .online, .shop, .club, .icu)
  - Domain contains a legitimate brand name plus extra characters (lookalike)
  - Domain is not on the safe allowlist when it claims to be a known brand

Returns list[dict] with keys: url, domain, suspicious (bool), reason (str).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse
from ibm_watsonx_orchestrate.agent_builder.tools import tool

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

_SHORTENERS = frozenset({
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "tiny.cc", "rebrand.ly", "short.io",
})

_SUSPICIOUS_TLDS = frozenset({
    ".top", ".xyz", ".online", ".shop", ".club", ".icu", ".buzz",
    ".live", ".site", ".tech", ".store", ".link",
})

# Domains that are definitively safe for the brands they represent
_ALLOWLIST = frozenset({
    "sbi.co.in", "onlinesbi.sbi", "hdfcbank.com", "icicibank.com",
    "axisbank.com", "paytm.com", "phonepe.com", "gpay.app",
    "parivahan.gov.in", "echallan.parivahan.gov.in",
    "incometax.gov.in", "cybercrime.gov.in",
    "amazon.in", "flipkart.com", "swiggy.com", "zomato.com",
    "indane.co.in", "mylpg.in",
    "dhl.com", "fedex.com",
    "jio.com", "airtel.in", "vi.in",
})

# Brand names whose legitimate domains are well-known; lookalike detection
_BRAND_NAMES = [
    "sbi", "hdfc", "icici", "axis", "paytm", "phonepe",
    "parivahan", "echallan", "incometax", "cybercrime",
    "amazon", "flipkart", "swiggy", "zomato",
    "indane", "mylpg", "lpg",
    "dhl", "fedex",
    "jio", "airtel",
    "irctc", "uidai", "aadhaar",
]

_BRAND_RE = re.compile(
    r"(?:" + "|".join(re.escape(b) for b in _BRAND_NAMES) + r")",
    re.IGNORECASE,
)


def _extract_domain(url: str) -> str:
    """Return the netloc (lowercased) from a URL, handling bare domains."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return url.lower()


def _check_one(url: str) -> dict:
    domain = _extract_domain(url)

    # 1. Allowlist fast-path
    if domain in _ALLOWLIST:
        return {"url": url, "domain": domain, "suspicious": False, "reason": "allowlisted"}

    # 2. Known shortener
    if domain in _SHORTENERS:
        return {"url": url, "domain": domain, "suspicious": True,
                "reason": "URL shortener hides real destination"}

    # 3. Suspicious TLD
    for tld in _SUSPICIOUS_TLDS:
        if domain.endswith(tld):
            return {"url": url, "domain": domain, "suspicious": True,
                    "reason": f"suspicious TLD: {tld}"}

    # 4. Brand name in a domain that is NOT the allowlist
    if _BRAND_RE.search(domain):
        return {"url": url, "domain": domain, "suspicious": True,
                "reason": "brand name in unofficial domain (lookalike)"}

    return {"url": url, "domain": domain, "suspicious": False, "reason": "no flags"}


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def _check_link_impl(urls: list) -> list:
    return [_check_one(u) for u in urls]


@tool
def check_link(urls: list) -> list:
    """
    Classify each URL as suspicious or safe.

    Args:
        urls: list of URL strings extracted by extract_entities.

    Returns a list of dicts, one per URL, with keys:
        url        (str)  — original URL
        domain     (str)  — extracted domain
        suspicious (bool) — True if the URL is flagged
        reason     (str)  — human-readable reason for the verdict
    """
    return _check_link_impl(urls)
