"""Shared paths, colours, fonts and an HTML-to-PNG helper for the demo video tools."""

from __future__ import annotations

from pathlib import Path

DEMO = Path(__file__).resolve().parent
ROOT = DEMO.parent
ASSETS = DEMO / "assets"
FONTS = ASSETS / "fonts"
SLIDES = ASSETS / "slides"
OUT = DEMO / "output"

W, H = 1920, 1080
NAVY = "#14213D"
PAPER = "#F4F6F9"
GREEN = "#0F5E59"
MINT = "#8FD3C9"
SOFT = "#DCE3EE"
MUTED = "#AEB9CC"

# Phone video placement on the 1920x1080 canvas (scenes recorded at 540x1080).
PHONE_W, PHONE_H = 486, 972
PHONE_X, PHONE_Y = W - 160 - PHONE_W, (H - PHONE_H) // 2


def font_css() -> str:
    """@font-face rules for the bundled open-licence fonts (file:// URLs)."""
    faces = [
        ("Atkinson Hyperlegible", "atkinson-hyperlegible-latin-400-normal.woff2", 400),
        ("Atkinson Hyperlegible", "atkinson-hyperlegible-latin-700-normal.woff2", 700),
        ("Noto Sans Kannada", "noto-sans-kannada-kannada-400-normal.woff2", 400),
        ("Noto Sans Kannada", "noto-sans-kannada-kannada-700-normal.woff2", 700),
        ("Noto Sans Devanagari", "noto-sans-devanagari-devanagari-400-normal.woff2", 400),
        ("Noto Sans Devanagari", "noto-sans-devanagari-devanagari-700-normal.woff2", 700),
    ]
    return "\n".join(
        f"@font-face{{font-family:'{fam}';src:url('{(FONTS / f).as_uri()}') format('woff2');font-weight:{w}}}"
        for fam, f, w in faces
    )


BASE_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1920px;height:1080px;overflow:hidden}
body{font-family:'Atkinson Hyperlegible','Noto Sans Kannada','Noto Sans Devanagari',sans-serif}
"""


def page(body: str, css: str = "") -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{font_css()}{BASE_CSS}{css}</style></head><body>{body}</body></html>"


def render_pngs(items: list[tuple[str, Path]]) -> None:
    """Render (html, out_path) pairs to 1920x1080 PNGs with headless Chromium."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": W, "height": H})
        for html, out in items:
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(".tmp.html")
            tmp.write_text(html, encoding="utf-8")
            pg.goto(tmp.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(150)
            pg.screenshot(path=str(out))
            tmp.unlink()
        browser.close()
