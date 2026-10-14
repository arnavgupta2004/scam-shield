"""
lookup_playbook.py — offline fallback for knowledge-base embedding failures.

Parses the scam playbook text bundled below and returns the matching section
for a given scam_type. If no section matches, returns the
"Universal red-flag signals" section so the agent always has grounded context.

This tool works entirely offline — no KB index call is made.
"""

from __future__ import annotations

import re
from ibm_watsonx_orchestrate.agent_builder.tools import tool

# ---------------------------------------------------------------------------
# Bundled KB text — kept in sync with kb/scam_playbooks.md
# Bundling avoids a file-system dependency on the server.
# ---------------------------------------------------------------------------
_KB_TEXT = """
## 1. Digital arrest (fake police / CBI / customs / narcotics)
**How it works:** Caller claims your Aadhaar, phone number or a parcel is linked to a crime (money laundering, drugs, illegal SIM). Moves you to a video call with someone in "uniform", fake ID cards or court documents. Says you are under "digital arrest", must stay on camera, tell no one, and transfer money to a "verification" or "RBI safe" account.
**Red flags:**
- Any claim that you are arrested over a phone or video call
- Demand to stay on call / not tell family ("secrecy order")
- Money transfer to "clear your name", "verify funds", or a "safe account"
- Uniforms, badges, letterheads shown on video; call transferred between "officers"
**Reality:** Indian police, CBI, ED, customs or courts never arrest anyone over a video call and never ask for money transfers to verify innocence. There is no such thing as "digital arrest".
**Tell the user:** "This is a scam. You are not in trouble. Hang up now. Real police never arrest anyone on a video call. Call your family."

## 2. Courier / customs parcel
**How it works:** Call or IVR message: "Your FedEx/DHL/courier parcel contains drugs/passports/illegal items" or "is held at customs — pay duty". Often leads into a digital-arrest script.
**Red flags:** Parcel you never sent; "press 1 to talk to executive"; transfer to "police"; payment link for customs duty via SMS/WhatsApp.
**Reality:** Courier companies do not connect you to police; customs duty is not collected over WhatsApp/UPI from strangers.
**Tell the user:** "Courier companies don't transfer you to the police. Hang up. Check only on the courier's official app or website."

## 3. KYC update / account will be blocked
**How it works:** SMS/WhatsApp: "Your bank account / SIM / PAN will be blocked today, update KYC" with a link or APK file. Link steals login, OTP or installs a screen-reading app.
**Red flags:** Deadline "today"/"within 24 hours"; link not on the bank's official domain; `.apk` file; asks for OTP, PIN, card number or Aadhaar.
**Reality:** Banks ask you to visit the branch or official app for KYC; they never ask for OTP/PIN and never send APK files.
**Tell the user:** "Banks never block your account over SMS links. Don't click. Go to your branch or official bank app."

## 4. Electricity bill disconnection
**How it works:** "Dear consumer, your electricity will be disconnected tonight at 9:30 PM because last month's bill was not updated. Call officer 98xxxxxxxx." Caller asks to install a remote-access app or pay via link.
**Red flags:** Personal mobile number for an "officer"; same-night disconnection; remote-access app (AnyDesk/TeamViewer/QuickSupport); small "update fee".
**Reality:** Electricity providers send official notices and do not ask you to install apps or call personal numbers.
**Tell the user:** "Electricity offices don't call from personal numbers or ask you to install apps. Check your bill on the official site or office."

## 5. Fake customer care number
**How it works:** User searches online for a bank/airline/e-commerce helpline and calls a fake number listed in ads or edited map listings. "Agent" asks for remote-access app or a refund via UPI collect request.
**Red flags:** Refund that requires *you* to enter UPI PIN; remote-access app; mobile number instead of toll-free.
**Reality:** You never enter a UPI PIN to *receive* money.
**Tell the user:** "Entering your UPI PIN sends money, it never receives it. Use only the number printed on the official app or card."

## 6. "Sent money by mistake" / UPI collect request
**How it works:** Fake credit SMS or a real small credit, then a call: "I sent ₹5,000 by mistake, please return." Or a UPI "collect request" disguised as payment.
**Red flags:** Pressure to return money quickly; collect request instead of credit; SMS not from bank's sender ID.
**Reality:** Check your actual bank balance in the bank app. Mistaken transfers are reversed through the bank, not by you.
**Tell the user:** "Check your bank app, not the SMS. If money really came by mistake, the bank will handle it."

## 7. Relative / friend in emergency (incl. AI voice clone)
**How it works:** Call or WhatsApp from a new number: "It's me, your grandson, I've had an accident / been arrested, send money now, don't tell Mom." Voice may be AI-cloned.
**Red flags:** New number; urgency; secrecy; can't do a video call; asks for gift cards or UPI to a third party.
**Reality:** Real family can be verified by calling their known number.
**Tell the user:** "Hang up and call your relative on the number you already have. Ask a question only they would know."

## 8. Investment / stock-tips WhatsApp or Telegram group
**How it works:** Added to group with "SEBI-registered expert" promising 200–500% returns, fake app showing profits, withdrawals blocked until "tax" or "fee" is paid.
**Red flags:** Guaranteed or huge returns; app not on official store; must pay to withdraw; famous person photos.
**Reality:** No legitimate investment guarantees returns; SEBI-registered advisors don't run anonymous WhatsApp groups.
**Tell the user:** "Guaranteed high returns are always a scam. Don't add more money to 'unlock' withdrawals."

## 9. Part-time job / task scam
**How it works:** "Earn ₹3,000/day liking YouTube videos / rating hotels." Small payouts first, then "prepaid tasks" requiring deposits.
**Red flags:** Pay-to-work; Telegram tasks; small initial earnings to build trust.
**Reality:** Real jobs don't ask you to pay deposits.
**Tell the user:** "Any job that asks you to pay first is a scam."

## 10. Lottery / KBC / prize
**How it works:** "You won ₹25 lakh in KBC lottery / lucky draw, pay processing fee/GST to claim."
**Red flags:** You never entered; fee to claim; WhatsApp image with logos.
**Tell the user:** "You can't win a lottery you never entered. Never pay to receive a prize."

## 11. Pension / life certificate (senior-targeted)
**How it works:** Caller posing as treasury/pension office: "Your pension will stop, update your life certificate / PPO details", asks for OTP or bank details.
**Red flags:** Pension stopping "today"; OTP request; link to non-government site.
**Reality:** Life certificates are submitted at the bank, pension office, or official Jeevan Pramaan channels; officials never ask for OTPs.
**Tell the user:** "Pension offices never ask for OTP on the phone. Visit your bank or pension office."

## 12. Fake traffic e-challan
**How it works:** SMS: "Traffic violation challan of ₹500 pending, pay now to avoid court" with a lookalike link or APK.
**Red flags:** APK attachment; non-government domain; threat of court/licence cancellation today.
**Reality:** Check challans only on the official government e-challan / Parivahan portal or the traffic police site by typing the address yourself.
**Tell the user:** "Don't open the link. Check challans only on the official government website."

## 13. Gas / LPG / subsidy KYC
**How it works:** "Your LPG connection/subsidy will be cancelled, complete eKYC" with link or call asking for Aadhaar OTP.
**Red flags & advice:** Same as KYC scams — official distributors do eKYC in person or via official app.

## 14. Sextortion video call
**How it works:** Unknown video call shows explicit content, screen is recorded, then blackmail threatening to send it to contacts.
**Tell the user (calm, non-judgemental):** "You haven't done anything wrong. Don't pay — paying leads to more demands. Block, keep screenshots, and report to 1930."

## Universal red-flag signals
| Signal | Weight hint |
|---|---|
| Claims of arrest, police, CBI, ED, customs, court | High |
| Instruction to keep secret / stay on call | High |
| Request for OTP, UPI PIN, CVV, card number, Aadhaar/PAN | High |
| Remote-access app or `.apk` file | High |
| Deadline: today / tonight / within hours | Medium |
| Link domain not matching the claimed organisation; URL shorteners | Medium |
| Personal mobile number for an "official" | Medium |
| Guaranteed returns, prizes, pay-to-earn | Medium |
| New number claiming to be family | Medium |
| Generic greeting ("Dear customer") | Low |

## Genuine message patterns (to reduce false alarms)
- Bank OTP messages that *say* "do not share this OTP" and come with no call or link request
- Delivery updates for orders the user placed, from the official sender ID, with no payment request
- Bills from official sender IDs pointing to official domains, with no threat of same-day cutoff
- Messages from saved contacts with normal conversation
"""

# ---------------------------------------------------------------------------
# Mapping: scam_type slug → heading keyword(s) to locate the section
# ---------------------------------------------------------------------------
_TYPE_TO_HEADING: dict[str, str] = {
    "digital_arrest":     "Digital arrest",
    "courier":            "Courier / customs",
    "kyc":                "KYC update",
    "electricity":        "Electricity bill",
    "fake_customer_care": "Fake customer care",
    "upi_mistake":        "Sent money by mistake",
    "relative_emergency": "Relative / friend in emergency",
    "investment":         "Investment / stock",
    "job_task":           "Part-time job",
    "lottery":            "Lottery / KBC",
    "pension":            "Pension / life certificate",
    "echallan":           "Fake traffic e-challan",
    "lpg":                "Gas / LPG",
    "sextortion":         "Sextortion",
}

_UNIVERSAL_HEADING = "Universal red-flag signals"


def _extract_section(heading_fragment: str) -> str:
    """Return the KB section whose heading contains *heading_fragment* (case-insensitive)."""
    # Split on lines that start with "## "
    sections = re.split(r"\n(?=## )", _KB_TEXT.strip())
    for section in sections:
        first_line = section.split("\n", 1)[0]
        if heading_fragment.lower() in first_line.lower():
            return section.strip()
    return ""


def _lookup_playbook_impl(scam_type: str) -> str:
    """Core logic — separated so tests can import without the @tool decorator."""
    heading = _TYPE_TO_HEADING.get(scam_type.strip().lower())
    if heading:
        section = _extract_section(heading)
        if section:
            return section
    # Fallback: universal red-flag signals
    return _extract_section(_UNIVERSAL_HEADING)


@tool
def lookup_playbook(scam_type: str) -> str:
    """
    Return the playbook section for *scam_type* from the bundled scam playbook KB.

    This tool works entirely offline — it reads from text bundled in the tool
    itself, so it functions even when the knowledge-base embedding index is down.

    If *scam_type* does not match any known playbook the tool returns the
    "Universal red-flag signals" section, which applies to every scam.

    Args:
        scam_type: Snake-case scam type, e.g. "digital_arrest", "kyc",
                   "lottery".  Case-insensitive.  Pass your best guess — the
                   universal fallback is always returned for unknown types.

    Returns:
        The matching playbook section as plain Markdown text.
    """
    return _lookup_playbook_impl(scam_type)
