#!/usr/bin/env python3
"""
Record the live app scenes for the demo video and take screenshots for the deck.

Needs the backend running with watsonx Orchestrate configured:
    uvicorn backend.main:app
    python demo/record.py

Every /analyse, /alert and /report answer is checked: if any came from the
offline rules or templates instead of the agents, recording stops (so the
video only shows real agent answers). --allow-fallback is for testing only.

Writes demo/output/scenes/<scene>.webm, <scene>.json (when each agent call started
and ended, and named moments, in seconds from the start of the recording) and
demo/output/screens/*.png
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT  # noqa: E402
from timeline import ROW1, ROW37, SAMPLE_SMS  # noqa: E402
from urllib.parse import quote  # noqa: E402

VIEW = {"width": 540, "height": 1080}

# Shows a soft circle where each tap lands, so viewers can follow the clicks.
TAP_SCRIPT = """
addEventListener('pointerdown', e => {
  const d = document.createElement('div');
  Object.assign(d.style, {position:'fixed', left:(e.clientX-28)+'px', top:(e.clientY-28)+'px', width:'56px', height:'56px',
    borderRadius:'50%', background:'rgba(242,169,0,.45)', border:'3px solid #F2A900', pointerEvents:'none',
    zIndex:99999, transition:'transform .5s, opacity .5s'});
  document.body.appendChild(d);
  requestAnimationFrame(() => { d.style.transform = 'scale(1.6)'; d.style.opacity = '0'; });
  setTimeout(() => d.remove(), 600);
}, true);
"""


class FallbackUsed(Exception):
    pass


def run(base: str, allow_fallback: bool, headed: bool, only: list[str] | None):
    from playwright.sync_api import sync_playwright

    scenes_dir = OUT / "scenes"
    screens_dir = OUT / "screens"
    tmp = OUT / "_rec"
    for d in (scenes_dir, screens_dir):
        d.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(tmp, ignore_errors=True)

    sources: list[tuple[str, str]] = []
    # Timing for the video: agent calls and named moments, relative to the recording start.
    timing = {"t0": 0.0, "calls": [], "marks": {}}

    def now() -> float:
        return round(time.monotonic() - timing["t0"], 3)

    def mark(name):
        timing["marks"][name] = now()

    def is_agent_call(req) -> bool:
        return req.method == "POST" and req.url.split("?")[0].endswith(("/analyse", "/alert", "/report"))

    def on_request(req):
        if is_agent_call(req):
            timing["calls"].append({"ep": req.url.split("?")[0].rsplit("/", 1)[-1], "start": now()})

    def watch(resp):
        path = resp.url.split("?")[0]
        if is_agent_call(resp.request):
            ep = path.rsplit("/", 1)[-1]
            open_calls = [c for c in timing["calls"] if c["ep"] == ep and "end" not in c]
            if open_calls:
                open_calls[0]["end"] = now()
            try:
                src = json.loads(resp.text()).get("source", "?")
            except Exception:
                src = f"HTTP {resp.status}"
            sources.append((ep, src))

    def check(scene):
        bad = [(ep, s) for ep, s in sources if s != "agent"]
        sources.clear()
        if bad and not allow_fallback:
            raise FallbackUsed(f"{scene}: answers not from the agents: {bad}. "
                               "Check the backend log and Orchestrate, then run again.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)

        def scene(name, path="/", family=None):
            ctx = browser.new_context(viewport=VIEW, device_scale_factor=2,
                                      record_video_dir=str(tmp / name), record_video_size=VIEW)
            ctx.add_init_script(TAP_SCRIPT)
            if family:  # a family number saved earlier on this phone
                ctx.add_init_script(f"try{{localStorage.setItem('familyPhone','{family}')}}catch(e){{}}")
            timing.update(t0=time.monotonic(), calls=[], marks={})  # the video starts with the page
            pg = ctx.new_page()
            pg.on("request", on_request)
            pg.on("response", watch)
            pg.goto(base + path)
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(1200)
            return ctx, pg

        def finish(name, ctx, pg):
            video = pg.video
            ctx.close()
            src = Path(video.path())
            shutil.move(str(src), scenes_dir / f"{name}.webm")
            (scenes_dir / f"{name}.json").write_text(
                json.dumps({"calls": timing["calls"], "marks": timing["marks"]}, indent=1), encoding="utf-8")
            check(name)
            print(f"  recorded {name}")

        def wait_verdict(pg):
            pg.wait_for_selector("#screen-verdict:not([hidden])", timeout=120_000)
            pg.wait_for_timeout(600)

        def slow_scroll(pg, to, steps=20):
            start = pg.evaluate("scrollY")
            for i in range(1, steps + 1):
                pg.evaluate(f"scrollTo(0, {start + (to - start) * i / steps})")
                pg.wait_for_timeout(60)

        todo = only or ["check_en", "screenshot", "call_kn", "alert", "genuine", "tricks"]

        if "check_en" in todo:
            # Opened the way Android's share sheet opens it: the shared text arrives in the URL.
            ctx, pg = scene("check_en", path="/?share_text=" + quote(ROW1))
            mark("shared")
            pg.wait_for_timeout(1500)
            pg.click("#btn-check")
            wait_verdict(pg)
            mark("verdict")
            pg.wait_for_timeout(2500)
            pg.screenshot(path=str(screens_dir / "verdict-en-scam.png"))
            pg.click("details.sent summary")
            mark("sent")
            pg.wait_for_timeout(300)
            slow_scroll(pg, pg.evaluate("document.body.scrollHeight"))
            pg.wait_for_timeout(2500)
            slow_scroll(pg, 0)
            pg.wait_for_timeout(800)
            finish("check_en", ctx, pg)

        if "screenshot" in todo:
            sample = tmp / "sample-sms.png"
            sample.parent.mkdir(parents=True, exist_ok=True)
            maker = browser.new_page(viewport={"width": 540, "height": 420}, device_scale_factor=2)
            maker.set_content(SAMPLE_SMS)
            maker.screenshot(path=str(sample))
            maker.close()
            ctx, pg = scene("screenshot")
            pg.wait_for_timeout(800)
            with pg.expect_file_chooser() as fc:
                pg.click("#btn-ocr")
            fc.value.set_files(str(sample))
            mark("ocr_start")
            pg.wait_for_function("document.querySelector('#msg').value.length > 40 || !document.querySelector('#home-error').hidden",
                                 timeout=180_000)
            if pg.is_visible("#home-error"):
                raise FallbackUsed("screenshot: text recognition failed (" + pg.inner_text("#home-error") + ")")
            mark("ocr_done")
            pg.wait_for_timeout(1500)
            pg.click("#btn-check")
            wait_verdict(pg)
            mark("verdict")
            pg.wait_for_timeout(3000)
            pg.screenshot(path=str(screens_dir / "verdict-screenshot.png"))
            finish("screenshot", ctx, pg)

        if "call_kn" in todo:
            ctx, pg = scene("call_kn", family="9876543210")
            pg.click("[data-lang=kn]")
            pg.wait_for_timeout(1200)
            pg.click("#btn-call")
            pg.wait_for_timeout(1500)
            mark("cues")
            pg.click(".cue >> nth=0")
            pg.wait_for_timeout(900)
            pg.click(".cue >> nth=3")
            pg.wait_for_timeout(1200)
            pg.screenshot(path=str(screens_dir / "call-coach-kn.png"))
            pg.click("#btn-coach")
            wait_verdict(pg)
            mark("verdict")
            pg.wait_for_timeout(3000)
            pg.screenshot(path=str(screens_dir / "verdict-kn-call.png"))
            pg.click("#btn-read")  # read aloud (audio is not in the recording)
            pg.wait_for_timeout(1200)
            pg.click("#btn-report")
            mark("report")
            pg.wait_for_function("document.querySelector('#report-steps').textContent.length > 40", timeout=120_000)
            pg.wait_for_timeout(300)
            slow_scroll(pg, pg.evaluate("document.querySelector('#report-block').offsetTop - 200"))
            pg.wait_for_timeout(3000)
            pg.screenshot(path=str(screens_dir / "report-kn.png"))
            finish("call_kn", ctx, pg)

        if "alert" in todo:
            ctx, pg = scene("alert")
            pg.click("#msg")
            pg.keyboard.insert_text(ROW1)
            pg.click("#btn-check")
            wait_verdict(pg)
            mark("verdict")
            pg.wait_for_timeout(1000)
            pg.click("#btn-alert")
            mark("confirm")
            pg.wait_for_timeout(1000)
            pg.click("#family-phone")
            pg.keyboard.type("9876543210", delay=60)
            pg.wait_for_timeout(1000)
            pg.screenshot(path=str(screens_dir / "alert-confirm.png"))
            pg.click("#confirm-yes")
            pg.wait_for_selector("#alert-ready[open]", timeout=120_000)
            mark("ready")
            pg.wait_for_timeout(3500)
            pg.screenshot(path=str(screens_dir / "alert-ready.png"))
            finish("alert", ctx, pg)

        if "genuine" in todo:
            ctx, pg = scene("genuine")
            pg.click("#msg")
            pg.keyboard.insert_text(ROW37)
            pg.wait_for_timeout(800)
            pg.click("#btn-check")
            wait_verdict(pg)
            mark("verdict")
            pg.wait_for_timeout(3500)
            pg.screenshot(path=str(screens_dir / "verdict-genuine.png"))
            finish("genuine", ctx, pg)

        if "tricks" in todo:
            ctx, pg = scene("tricks")
            pg.click("[data-lang=hi]")
            pg.wait_for_timeout(1000)
            pg.click("#btn-tricks")
            mark("cards")
            pg.wait_for_timeout(2500)
            pg.screenshot(path=str(screens_dir / "tricks-hi.png"))
            for _ in range(2):
                pg.click("#btn-tricks-next")
                pg.wait_for_timeout(2200)
            finish("tricks", ctx, pg)

        browser.close()
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--allow-fallback", action="store_true", help="testing only: keep scenes answered by the rules")
    ap.add_argument("--headed", action="store_true", help="show the browser while recording")
    ap.add_argument("--only", nargs="*", help="re-record some scenes: check_en screenshot call_kn alert genuine tricks")
    args = ap.parse_args()

    import urllib.request
    try:
        health = json.load(urllib.request.urlopen(args.base + "/health", timeout=10))
    except Exception:
        sys.exit(f"Backend not reachable at {args.base}. Start it with: uvicorn backend.main:app")
    if not (health.get("orchestrate_configured") and health["agents_configured"].get("analyse")) and not args.allow_fallback:
        sys.exit("Backend has no Orchestrate credentials or agent ids (.env). The video must show real agent answers.")

    print("Recording scenes (each waits for the real agent answer)...")
    try:
        run(args.base, args.allow_fallback, args.headed, args.only)
    except FallbackUsed as e:
        sys.exit(f"Stopped: {e}")
    print(f"Done. Scenes: {OUT / 'scenes'}  Screenshots for the deck: {OUT / 'screens'}")


if __name__ == "__main__":
    main()
