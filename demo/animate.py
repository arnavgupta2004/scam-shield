"""
Animated cards for the demo video, rendered frame by frame.

Each card is an HTML page that uses CSS animations. Every frame, all animations
are paused and moved to that frame's time, then the page is captured, so the
result is smooth and exactly timed (no screen recording involved).
"""

from __future__ import annotations

import base64
import html
import subprocess
from pathlib import Path

from common import GREEN, H, MINT, MUTED, NAVY, PAPER, SOFT, W, page

RED = "#C62828"
AMBER = "#F2A900"


def render_animation(html_doc: str, seconds: float, out: Path, ffmpeg: str, fps: int = 30):
    """Render an animated HTML page to an H.264 mp4 of the given length."""
    from playwright.sync_api import sync_playwright

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.html")
    tmp.write_text(html_doc, encoding="utf-8")
    frames = int(round(seconds * fps))
    enc = subprocess.Popen(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), "-preset", "medium", "-crf", "18", "-an", str(out)],
        stdin=subprocess.PIPE)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": W, "height": H})
        pg.goto(tmp.as_uri())
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        for i in range(frames):
            ms = i * 1000 / fps
            pg.evaluate(f"document.getAnimations().forEach(a => {{ a.pause(); a.currentTime = {ms}; }})")
            enc.stdin.write(pg.screenshot(type="jpeg", quality=93))
        browser.close()
    enc.stdin.close()
    if enc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed while rendering {out.name}")
    tmp.unlink()


def _img(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


ANIM_CSS = f"""
body{{background:{NAVY};color:{PAPER}}}
@keyframes rise{{from{{opacity:0;transform:translateY(28px)}}to{{opacity:1;transform:none}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes slidein{{from{{opacity:0;transform:translateX(160px) scale(.96)}}to{{opacity:1;transform:none}}}}
@keyframes pop{{0%{{opacity:0;transform:scale(.6)}}70%{{opacity:1;transform:scale(1.06)}}100%{{opacity:1;transform:scale(1)}}}}
@keyframes ring{{0%{{transform:scale(1);opacity:.7}}100%{{transform:scale(2.2);opacity:0}}}}
@keyframes draw{{from{{opacity:1;transform:scaleX(0)}}to{{opacity:1;transform:scaleX(1)}}}}
@keyframes glow{{0%,100%{{box-shadow:0 0 0 0 rgba(198,40,40,0)}}50%{{box-shadow:0 0 90px 10px rgba(198,40,40,.55)}}}}
.a{{opacity:0;animation-fill-mode:both;animation-timing-function:cubic-bezier(.2,.8,.2,1)}}
"""


# ---------------------------------------------------------------- cold open

def hook_card(verdict_png: Path, words: str) -> str:
    """A scam call's words appear one by one, then the real Scam Shield verdict lands."""
    spans = "".join(
        f"<span class='a' style='animation:fade .25s {0.9 + i * 0.16:.2f}s both'>{html.escape(w)} </span>"
        for i, w in enumerate(words.split()))
    return page(f"""
<div style="position:absolute;left:150px;top:150px;width:1000px">
  <div class="a" style="animation:rise .6s .1s both;display:flex;align-items:center;gap:28px">
    <div style="position:relative;width:96px;height:96px">
      <div style="position:absolute;inset:0;border-radius:50%;background:{RED};animation:ring 1.2s .1s 6 both"></div>
      <div style="position:absolute;inset:0;border-radius:50%;background:#33415F;display:flex;align-items:center;justify-content:center;font-size:50px;font-weight:700">?</div>
    </div>
    <div>
      <p style="font-size:40px;font-weight:700">Unknown caller · video call</p>
      <p style="font-size:30px;color:{MUTED}">“Inspector Rao, Mumbai Cyber Crime”</p>
    </div>
  </div>
  <p style="margin-top:64px;font-size:64px;line-height:1.25;font-weight:700;color:#FFFFFF">{spans}</p>
  <p class="a" style="animation:rise .7s 6.4s both;margin-top:70px;font-size:38px;color:{MINT};font-weight:700">
    One tap later: a second opinion, from IBM watsonx Orchestrate agents.</p>
</div>
<div class="a" style="animation:slidein .8s 4.7s both;position:absolute;right:180px;top:70px;width:470px;height:940px;
     border-radius:46px;background:#2E3D5C;padding:14px">
  <div style="width:100%;height:100%;border-radius:34px;overflow:hidden;animation:glow 2.4s 5.3s 2 both">
    <img src="{_img(verdict_png)}" style="width:100%;display:block">
  </div>
</div>
<p class="a" style="animation:fade .6s 5.2s both;position:absolute;right:180px;top:1022px;width:470px;text-align:center;
   font-size:22px;color:{MUTED}">Real agent answer, recorded live</p>
""", ANIM_CSS)


# ---------------------------------------------------------------- how it works

def _box(x, y, w, h, delay, kicker, title, lines, accent=MINT, bg="#1E2E50"):
    items = "".join(f"<p style='font-size:23px;line-height:1.4;color:{SOFT}'>{l}</p>" for l in lines)
    return f"""
<div class="a" style="animation:rise .6s {delay}s both;position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;
     background:{bg};border-radius:22px;padding:26px 28px;border-top:6px solid {accent}">
  <p style="font-size:20px;letter-spacing:.08em;text-transform:uppercase;color:{accent};font-weight:700">{kicker}</p>
  <p style="font-size:33px;font-weight:700;margin:8px 0 14px;line-height:1.15">{title}</p>{items}
</div>"""


def _arrow(x, y, w, delay, vertical=False):
    if vertical:
        return (f"<div class='a' style='animation:fade .3s {delay}s both;position:absolute;left:{x}px;top:{y}px;width:6px;"
                f"height:{w}px;background:{MINT};border-radius:3px'></div>")
    return f"""
<div class="a" style="animation:draw .45s {delay}s both;transform-origin:left;position:absolute;left:{x}px;top:{y}px;
     width:{w}px;height:6px;background:{MINT};border-radius:3px"></div>
<div class="a" style="animation:fade .2s {delay + 0.4}s both;position:absolute;left:{x + w - 6}px;top:{y - 11}px;width:0;height:0;
     border-left:22px solid {MINT};border-top:14px solid transparent;border-bottom:14px solid transparent"></div>"""


def architecture_card() -> str:
    y, h, w = 250, 370, 380
    xs = [110, 560, 1010, 1460]
    boxes = [
        _box(xs[0], y, w - 30, h, 0.3, "On the phone", "Any way in",
             ["Share from WhatsApp", "Paste or speak", "Screenshot: text read<br>on the device", "Live call: tap cues"]),
        _box(xs[1], y, w - 30, h, 1.3, "Before anything leaves", "Privacy first",
             ["Evidence noted on raw text", "redact_pii masks phone,<br>OTP, Aadhaar, UPI, card",
              "Only redacted text<br>is sent"], accent=AMBER),
        _box(xs[2], y, w - 30, h, 2.3, "IBM watsonx Orchestrate", "Triage supervisor",
             ["scam_shield_triage", "Fast hints: urgency score,<br>pattern match", "Always hands off to<br>the analyst"]),
        _box(xs[3], y, w - 30, h, 3.3, "Specialist agent", "Scam analyst",
             ["Red-flag reasoning", "Scam-playbook knowledge<br>base, check_link,<br>lookup_playbook",
              "Verdict in the user’s<br>language"], accent="#FF8A80"),
    ]
    arrows = "".join(_arrow(xs[i] + w - 30 + 12, y + h // 2, 76, 1.0 + i)
                     for i in range(3))
    lower = [
        f"<p class='a' style='animation:fade .4s 4.6s both;position:absolute;left:1010px;top:660px;font-size:24px;"
        f"color:{MUTED}'>Called by the app only when the user taps:</p>",
        _box(1010, 706, 420, 228, 4.8, "After the user says yes", "Guardian agent",
             ["Drafts the family alert; its<br>tool refuses without a yes"], accent=GREEN, bg="#18324A"),
        _box(1460, 706, 350, 228, 5.4, "On request", "Report helper",
             ["1930 · cybercrime.gov.in<br>· Chakshu, in plain steps"], accent=GREEN, bg="#18324A"),
    ]
    # the message as it travels: raw on the phone, masked after step 2
    token = f"""
<div class="a" style="animation:rise .5s 0.8s both;position:absolute;left:110px;top:668px;width:800px;font-family:monospace">
  <p style="font-size:22px;color:{MUTED};margin-bottom:8px">On the phone</p>
  <p style="font-size:27px;background:#2A1E2E;border-radius:12px;padding:14px 18px;color:#FFD2CC">
    …Call +91 98765 43210 and share the OTP 482913.</p>
</div>
<div class="a" style="animation:rise .5s 1.9s both;position:absolute;left:110px;top:800px;width:800px;font-family:monospace">
  <p style="font-size:22px;color:{MUTED};margin-bottom:8px">What the agents receive</p>
  <p style="font-size:27px;background:#16332F;border-radius:12px;padding:14px 18px;color:{MINT}">
    …Call [PHONE] and share the OTP [OTP].</p>
</div>
<p class="a" style="animation:fade .6s 6.4s both;position:absolute;left:110px;top:960px;font-size:24px;color:{MUTED}">
  If Orchestrate can’t be reached, offline rules answer and the app says so · unit and browser tests run in CI on every push</p>
"""
    return page(f"""
<p class="a" style="animation:rise .5s 0s both;position:absolute;left:110px;top:90px;font-size:28px;color:{MINT};font-weight:700">How it works</p>
<h1 class="a" style="animation:rise .5s .1s both;position:absolute;left:110px;top:132px;font-size:64px;font-weight:700">
  Four agents, and private numbers never leave the phone</h1>
{''.join(boxes)}{arrows}{''.join(lower)}
{token}""", ANIM_CSS)


# ---------------------------------------------------------------- results

def headline_card(ours: int, rules: int, total: int, median_s: str, false_alarms: str) -> str:
    """Count-up of held-out scams caught: Scam Shield against keyword rules."""
    def bar(label, n, colour, delay, y):
        pct = n / total * 100
        return f"""
<p class="a" style="animation:rise .5s {delay}s both;position:absolute;left:160px;top:{y}px;font-size:38px;font-weight:700">{label}</p>
<div class="a" style="animation:fade .3s {delay}s both;position:absolute;left:160px;top:{y + 66}px;width:1240px;height:64px;background:#24365A;border-radius:14px"></div>
<div class="a" style="animation:draw 1.6s {delay + .2}s both;transform-origin:left;position:absolute;left:160px;top:{y + 66}px;width:{1240 * pct / 100:.0f}px;height:64px;background:{colour};border-radius:14px"></div>
<p class="a" style="animation:fade .3s {delay + .2}s both;position:absolute;left:1440px;top:{y + 40}px;font-size:100px;font-weight:700;color:{colour}">
  <span class="num" style="--n:0;animation:count{n} 1.6s {delay + .2}s both"></span><span style="font-size:48px;color:{MUTED}"> / {total}</span></p>
<style>@keyframes count{n}{{from{{--n:0}}to{{--n:{n}}}}}</style>"""
    return page(f"""
<p class="a" style="animation:rise .5s 0s both;position:absolute;left:160px;top:110px;font-size:30px;color:{MINT};font-weight:700">Held-out test: scam messages the system had never seen</p>
<h1 class="a" style="animation:rise .5s .1s both;position:absolute;left:160px;top:160px;font-size:72px;font-weight:700">Scams caught</h1>
{bar("Scam Shield (watsonx Orchestrate agents)", ours, MINT, 0.6, 330)}
{bar("Keyword rules alone", rules, "#FF8A80", 1.2, 560)}
<div class="a" style="animation:rise .6s 3.0s both;position:absolute;left:160px;top:830px;display:flex;gap:90px">
  <p style="font-size:34px"><b style="color:{MINT};font-size:52px">{median_s}</b><br><span style="color:{SOFT}">median answer</span></p>
  <p style="font-size:34px"><b style="color:{MINT};font-size:52px">{false_alarms}</b><br><span style="color:{SOFT}">false alarms</span></p>
  <p style="font-size:34px"><b style="color:{MINT};font-size:52px">3</b><br><span style="color:{SOFT}">languages</span></p>
</div>
""", ANIM_CSS + "@property --n{syntax:'<integer>';inherits:false;initial-value:0}"
                ".num{counter-reset:n var(--n)}.num::after{content:counter(n)}")


# ---------------------------------------------------------------- close

def close_card() -> str:
    words = "When in doubt, check first.".split()
    title = "".join(f"<span class='a' style='display:inline-block;animation:rise .6s {0.2 + i * 0.12:.2f}s both'>"
                    f"{html.escape(w)}&nbsp;</span>" for i, w in enumerate(words))
    chips = ["IBM watsonx Orchestrate · 4 agents", "Built with IBM Bob", "Kannada · Hindi · English", "Open source (MIT)"]
    chip_html = "".join(
        f"<span class='a' style='animation:pop .5s {1.6 + i * 0.15:.2f}s both;display:inline-block;padding:14px 26px;"
        f"border-radius:40px;background:#1E2E50;border:2px solid #33456B;font-size:28px;color:{SOFT}'>{c}</span>"
        for i, c in enumerate(chips))
    shield = (f"<svg width='120' height='140' viewBox='0 0 24 28'><path d='M12 1 2 5v7c0 7 4.5 12.5 10 15 5.5-2.5 10-8 10-15V5z' "
              f"fill='{GREEN}' stroke='{MINT}' stroke-width='1.2'/><path d='m7.5 14 3 3 6-6.5' fill='none' stroke='#fff' "
              f"stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'/></svg>")
    return page(f"""
<div style="position:absolute;inset:0;background:radial-gradient(1100px 700px at 50% 40%,#1D3157 0%,{NAVY} 70%)"></div>
<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:34px;text-align:center">
  <div class="a" style="animation:pop .7s 0s both">{shield}</div>
  <h1 style="font-size:104px;font-weight:700;color:#FFFFFF;line-height:1.05">{title}</h1>
  <p class="a" style="animation:rise .6s 1.0s both;font-size:44px;color:{MINT}">ಸಂದೇಹವಿದ್ದರೆ, ಮೊದಲು ಪರಿಶೀಲಿಸಿ · शक हो, तो पहले जाँचें</p>
  <div style="display:flex;gap:18px;flex-wrap:wrap;justify-content:center;margin-top:16px">{chip_html}</div>
  <p class="a" style="animation:rise .6s 2.6s both;font-size:40px;color:#FFFFFF;font-weight:700;margin-top:26px">github.com/arnavgupta2004/scam-shield</p>
  <p class="a" style="animation:fade .6s 3.0s both;font-size:28px;color:{MUTED}">Arnav Gupta · B.Tech Data Science and AI, IIIT Dharwad · IBM Bobathon: Build for Bengaluru</p>
</div>""", ANIM_CSS)
