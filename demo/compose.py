#!/usr/bin/env python3
"""
Build the demo video from the slides, the recorded scenes and real repo data.

    python demo/compose.py                      # silent video + captions + timed voiceover script
    python demo/compose.py --voice my_voice.m4a # also mix in your voiceover

Writes demo/output/scam-shield-demo.mp4, captions.srt and voiceover.txt.
Run demo/record.py first.
"""

from __future__ import annotations

import argparse
import html
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DEMO, GREEN, H, MINT, MUTED, NAVY, OUT, PHONE_H, PHONE_W, PHONE_X, PHONE_Y,  # noqa: E402
                    ROOT, SLIDES, SOFT, W, page, render_pngs)
from timeline import SCENES  # noqa: E402

FPS = 30


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: list[str]):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpeg failed:\n" + r.stderr[-2000:])


def clip_seconds(path: Path) -> float:
    import imageio_ffmpeg
    _, secs = imageio_ffmpeg.count_frames_and_secs(str(path))
    return float(secs)


ENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-preset", "medium", "-crf", "20", "-an"]


# ---------------------------------------------------------------- stills built from real data

def scene_background(title: str, sub: str) -> str:
    """Navy canvas with the scene title on the left and a frame for the phone recording."""
    fx, fy = PHONE_X - 14, PHONE_Y - 14
    return page(f"""
<div style="position:absolute;inset:0;background:{NAVY}"></div>
<div style="position:absolute;left:{fx}px;top:{fy}px;width:{PHONE_W + 28}px;height:{PHONE_H + 28}px;border-radius:40px;background:#2E3D5C"></div>
<div style="position:absolute;left:160px;top:0;bottom:0;width:{PHONE_X - 300}px;display:flex;flex-direction:column;justify-content:center;gap:28px">
  <p style="font-size:30px;color:{MINT};font-weight:700">Scam Shield · live demo</p>
  <h1 style="font-size:84px;line-height:1.1;color:#F4F6F9;font-weight:700">{html.escape(title)}</h1>
  <p style="font-size:40px;line-height:1.35;color:{SOFT}">{html.escape(sub)}</p>
  <p style="font-size:26px;color:{MUTED};margin-top:24px">Real answers from IBM watsonx Orchestrate agents, recorded unedited</p>
</div>""")


def git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return ""


def bob_card() -> str:
    """The Bob commits and the opening of PLAN.md, read from the repository as they are."""
    log = git("log", "--reverse", "-F", "--grep=(Bob", "--date=format:%d %b %H:%M",
              "--format=%h  %ad  %s").strip().splitlines()
    rows = "".join(
        f"<p style='font-size:20px;line-height:1.55;color:{SOFT};font-family:monospace;white-space:nowrap;"
        f"overflow:hidden;text-overflow:ellipsis'>"
        f"<span style='color:{MINT}'>{html.escape(l[:7])}</span>{html.escape(l[7:])}</p>"
        for l in log[:20]
    ) or f"<p style='font-size:28px;color:{SOFT}'>(git log not available)</p>"
    plan = (ROOT / "PLAN.md").read_text(encoding="utf-8").splitlines() if (ROOT / "PLAN.md").exists() else []
    start = next((i for i, l in enumerate(plan) if l.startswith("## Milestones")), 0)
    excerpt = "\n".join(l for l in plan[start:start + 14] if l.strip())
    return page(f"""
<div style="position:absolute;inset:0;background:{NAVY};padding:110px 128px;display:flex;flex-direction:column;gap:40px">
  <h1 style="font-size:64px;color:#F4F6F9;font-weight:700">Built with IBM Bob: the real commits</h1>
  <div style="display:flex;gap:48px;flex:1;min-height:0">
    <div style="flex:1.5;min-width:0;display:flex;flex-direction:column;gap:4px;background:#1E2E50;border-radius:20px;padding:36px 40px">
      <p style="font-size:26px;color:{MINT};font-weight:700;margin-bottom:14px">git log --grep "(Bob)"</p>{rows}
    </div>
    <div style="flex:1;background:#1E2E50;border-radius:20px;padding:36px 40px;overflow:hidden">
      <p style="font-size:26px;color:{MINT};font-weight:700;margin-bottom:14px">PLAN.md, written in Bob’s Plan mode</p>
      <pre style="font-size:22px;line-height:1.45;color:{SOFT};white-space:pre-wrap;font-family:monospace">{html.escape(excerpt)}</pre>
    </div>
  </div>
</div>""")


# ---------------------------------------------------------------- segments

def still_segment(png: Path, seconds: float, out: Path):
    run([ffmpeg(), "-y", "-loop", "1", "-t", f"{seconds:.2f}", "-i", str(png),
         "-vf", f"scale={W}:{H},format=yuv420p", *ENC, str(out)])


def scene_segment(bg: Path, clip: Path, min_seconds: float, out: Path) -> float:
    trim = 0.5  # skip the blank first frames of each recording
    length = max(clip_seconds(clip) - trim, 1.0)
    total = max(length, min_seconds)
    pad = total - length
    fc = (f"[1:v]trim=start={trim},setpts=PTS-STARTPTS,fps={FPS},scale={PHONE_W}:{PHONE_H},"
          f"tpad=stop_mode=clone:stop_duration={pad:.2f}[ph];"
          f"[0:v][ph]overlay={PHONE_X}:{PHONE_Y}:shortest=1,format=yuv420p")
    run([ffmpeg(), "-y", "-loop", "1", "-t", f"{total:.2f}", "-i", str(bg), "-i", str(clip),
         "-filter_complex", fc, "-t", f"{total:.2f}", *ENC, str(out)])
    return total


def user_clip_segment(clip: Path, out: Path) -> float:
    run([ffmpeg(), "-y", "-i", str(clip), "-vf",
         f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={NAVY[1:]},fps={FPS},format=yuv420p",
         *ENC, str(out)])
    return clip_seconds(out)


# ---------------------------------------------------------------- captions

def ts(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


def chunks(text: str, limit: int = 84) -> list[str]:
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > limit:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return out + ([cur] if cur else [])


def write_captions(timed: list[tuple[float, float, str]]):
    srt, vo, n = [], [], 1
    for start, dur, text in timed:
        if not text:
            continue
        vo.append(f"[{ts(start)[3:8]} – {ts(start + dur)[3:8]}]  {text}")
        parts = chunks(text)
        total_chars = sum(len(p) for p in parts)
        t = start
        for p in parts:
            d = dur * len(p) / total_chars
            srt.append(f"{n}\n{ts(t)} --> {ts(t + d - 0.05)}\n{p}\n")
            n += 1
            t += d
    (OUT / "captions.srt").write_text("\n".join(srt), encoding="utf-8")
    (OUT / "voiceover.txt").write_text(
        "Scam Shield demo: read each line while that part is on screen (times are mm:ss).\n\n" + "\n\n".join(vo) + "\n",
        encoding="utf-8")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", help="your recorded voiceover (m4a/mp3/wav) to mix in")
    args = ap.parse_args()

    work = OUT / "_build"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)

    # Stills rendered from repo data and scene backgrounds.
    renders = []
    for s in SCENES:
        if s["kind"] == "scene":
            renders.append((scene_background(s["title"], s["sub"]), work / f"bg_{s['name']}.png"))
        elif s["kind"] == "card":
            renders.append((bob_card(), work / f"{s['name']}.png"))
    render_pngs(renders)

    segments, timed, t = [], [], 0.0
    for i, s in enumerate(SCENES):
        out = work / f"{i:02d}_{s['name']}.mp4"
        if s["kind"] == "slide":
            png = SLIDES / f"{s['name']}.png"
            if not png.exists():
                sys.exit(f"Missing slide image {png}")
            still_segment(png, s["seconds"], out)
            dur = float(s["seconds"])
        elif s["kind"] == "card":
            still_segment(work / f"{s['name']}.png", s["seconds"], out)
            dur = float(s["seconds"])
        elif s["kind"] == "scene":
            clip = OUT / "scenes" / f"{s['name']}.webm"
            if not clip.exists():
                sys.exit(f"Missing recording {clip}. Run: python demo/record.py")
            dur = scene_segment(work / f"bg_{s['name']}.png", clip, s["seconds"], out)
        elif s["kind"] == "clip":
            clip = DEMO / "clips" / f"{s['name']}.mp4"
            if not clip.exists():
                continue
            dur = user_clip_segment(clip, out)
        segments.append(out)
        timed.append((t, dur, s.get("say", "")))
        print(f"  {ts(t)[3:8]}  {s['name']} ({dur:.0f}s)")
        t += dur

    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
    silent = OUT / "scam-shield-demo-silent.mp4"
    run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(silent)])
    write_captions(timed)

    final = OUT / "scam-shield-demo.mp4"
    if args.voice:
        run([ffmpeg(), "-y", "-i", str(silent), "-i", args.voice, "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(final)])
        print(f"\nVideo with voiceover: {final}")
    else:
        shutil.copyfile(silent, final)
        print(f"\nSilent video: {final}")
    print(f"Length {ts(t)[3:8]}. Captions: {OUT / 'captions.srt'}  Timed script: {OUT / 'voiceover.txt'}")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
