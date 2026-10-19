"""
End-to-end Playwright tests for Scam Shield.

The backend runs locally with Orchestrate mocked (see conftest.py).
All tests use Chromium in headless mode (the pytest-playwright default).

Scenarios:
  1. check_message_scam_verdict  – paste a message, submit, see scam banner
  2. live_coach_kannada          – switch to Kannada, open coach, tap two cues,
                                   submit, see verdict in Kannada
  3. alert_refuses_without_confirm – /alert with user_confirmed omitted returns 403
  4. share_text_prefill          – ?share_text= query param pre-fills the textarea
  5. language_switch             – switching lang button updates the page heading
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def go(page: Page, base: str, path: str = "/") -> None:
    page.goto(base + path)
    # Wait for the JS bundle to finish executing (app name appears in the title).
    page.wait_for_function("() => document.title === 'Scam Shield'")


# ---------------------------------------------------------------------------
# 1. Check a message → scam verdict
# ---------------------------------------------------------------------------

def test_check_message_scam_verdict(page: Page, live_server_url: str) -> None:
    go(page, live_server_url)

    # Fill the textarea and submit.
    page.fill("#msg", "You are under digital arrest. Stay on call and tell no one.")
    page.click("#btn-check")

    # The waiting screen appears, then the verdict screen.
    verdict_band = page.locator("#verdict-band")
    expect(verdict_band).to_be_visible(timeout=10_000)

    # The verdict banner must carry the scam CSS class.
    expect(verdict_band).to_have_class("verdict is-scam", timeout=10_000)

    # The heading text comes from i18n "This looks like a scam".
    verdict_title = page.locator("#verdict-title")
    expect(verdict_title).to_have_text("This looks like a scam")

    # The advice text from the mock reply must be visible somewhere on the page.
    expect(page.get_by_text("Hang up now.")).to_be_visible()


# ---------------------------------------------------------------------------
# 2. Live-call coach in Kannada
# ---------------------------------------------------------------------------

def test_live_coach_kannada(page: Page, live_server_url: str) -> None:
    go(page, live_server_url)

    # Switch to Kannada.
    page.click("[data-lang='kn']")
    # The title heading should now be in Kannada.
    expect(page.locator("#home-title")).to_contain_text("ಅನುಮಾನ")

    # Open the live-call coach.
    page.click("#btn-call")
    expect(page.locator("#screen-coach")).to_be_visible()

    # Tap two cues.
    cue_buttons = page.locator(".cue")
    cue_buttons.nth(0).click()  # first cue (police)
    cue_buttons.nth(2).click()  # third cue (otp)

    # Submit.
    page.click("#btn-coach")

    # Verdict must appear.
    verdict_band = page.locator("#verdict-band")
    expect(verdict_band).to_be_visible(timeout=10_000)
    expect(verdict_band).to_have_class("verdict is-scam", timeout=10_000)

    # The live-coach path shows advice-now (large text), not advice-block.
    advice_now = page.locator("#advice-now")
    expect(advice_now).to_be_visible()
    expect(advice_now).not_to_be_empty()


# ---------------------------------------------------------------------------
# 3. Family alert refuses without confirmation (API-level)
# ---------------------------------------------------------------------------

def test_alert_refuses_without_confirmation(page: Page, live_server_url: str) -> None:
    """POST /alert without user_confirmed must return 403.

    Tested at the fetch level so we don't need to drive a dialog interaction;
    the backend gate is the important invariant here.
    """
    go(page, live_server_url)

    status = page.evaluate(
        """async (base) => {
            const r = await fetch(base + '/alert', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({summary: 'fake police call', lang: 'en'}),
            });
            return r.status;
        }""",
        live_server_url,
    )
    assert status == 403, f"expected 403 without user_confirmed, got {status}"

    # Also check explicit false.
    status2 = page.evaluate(
        """async (base) => {
            const r = await fetch(base + '/alert', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({summary: 'fake police call', lang: 'en',
                                      user_confirmed: false}),
            });
            return r.status;
        }""",
        live_server_url,
    )
    assert status2 == 403, f"expected 403 with user_confirmed=false, got {status2}"


# ---------------------------------------------------------------------------
# 4. share_text query-param pre-fills the textarea
# ---------------------------------------------------------------------------

def test_share_text_prefill(page: Page, live_server_url: str) -> None:
    shared = "You have won Rs 50000 prize. Click here."
    go(page, live_server_url, f"/?share_text={shared.replace(' ', '+')}")

    textarea = page.locator("#msg")
    expect(textarea).to_have_value(shared)

    # The URL should have been cleared (history.replaceState) so no query param.
    assert "share_text" not in page.url


# ---------------------------------------------------------------------------
# 5. Language switch updates the page heading
# ---------------------------------------------------------------------------

def test_language_switch(page: Page, live_server_url: str) -> None:
    go(page, live_server_url)

    heading = page.locator("#home-title")

    # Default is English.
    expect(heading).to_contain_text("Got a message or call that feels wrong?")

    # Switch to Hindi.
    page.click("[data-lang='hi']")
    expect(heading).to_contain_text("अजीब")

    # Switch to Kannada.
    page.click("[data-lang='kn']")
    expect(heading).to_contain_text("ಅನುಮಾನ")

    # Back to English.
    page.click("[data-lang='en']")
    expect(heading).to_contain_text("Got a message or call that feels wrong?")
