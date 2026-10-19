#!/usr/bin/env python3
"""
Build the demo video from the recorded scenes, animated cards, slides and real repo data.

    python demo/compose.py                      # silent video + captions + timed voiceover script
    python demo/compose.py --voice my_voice.m4a # also mix in your voiceover

Writes demo/output/scam-shield-demo.mp4, captions.srt and voiceover.txt.
Run demo/record.py first.

App recordings are never edited: the only change is that the time spent waiting
for an agent is played faster, with an on-screen label giving the real wait.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animate  # noqa: E402
from common import (DEMO, H, MINT, MUTED, NAVY, OUT, PHONE_H, PHONE_W, PHONE_X, PHONE_Y,  # noqa: E402
                    ROOT, SLIDES, SOFT, W, page, render_pngs)
from timeline import BOB_SHELL, SCENES  # noqa: E402

FPS = 30
FADE = 0.3          # dip-to-navy between segments
WAIT_SPEED = 6.0    # how much faster agent waits are played
NAVY_HEX = "0x" + NAVY[1:]
AGENT_LABEL = {"analyse": "watsonx Orchestrate agents", "alert": "guardian agent", "report": "report helper agent"}


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: list[str]):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpeg failed:\n" + r.stderr[-3000:])


def clip_seconds(path: Path) -> float:
    import imageio_ffmpeg
    _, secs = imageio_ffmpeg.count_frames_and_secs(str(path))
    return float(secs)


ENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-preset", "medium", "-crf", "18", "-an"]


def fades(total: float) -> str:
    return (f"fade=t=in:st=0:d={FADE}:color={NAVY_HEX},"
            f"fade=t=out:st={max(total - FADE, 0):.3f}:d={FADE}:color={NAVY_HEX}")


# ---------------------------------------------------------------- live scenes: timing

class Timeline:
    """Maps recording time to video time when agent waits are played faster."""

    def __init__(self, clip_len: float, calls: list[dict], trim: float = 1.2):
        waits = []
        for c in calls:
            if "end" in c and c["end"] - c["start"] > 1.6:
                waits.append([max(c["start"] + 0.5, trim), c["end"] - 0.4, c])
        self.pieces = []  # (src_start, src_end, speed, call or None)
        t = trim
        for a, b, c in waits:
            if a > t:
                self.pieces.append((t, a, 1.0, None))
            self.pieces.append((a, b, WAIT_SPEED, c))
            t = b
        if clip_len > t:
            self.pieces.append((t, clip_len, 1.0, None))

    def out(self, src: float) -> float:
        acc = 0.0
        for a, b, speed, _ in self.pieces:
            if src <= a:
                return acc
            if src <= b:
                return acc + (src - a) / speed
            acc += (b - a) / speed
        return acc

    @property
    def length(self) -> float:
        return sum((b - a) / s for a, b, s, _ in self.pieces)

    def waits(self):
        for a, b, speed, c in self.pieces:
            if c is not None:
                yield self.out(a), self.out(b), c


def anchor_time(anchor, timing: dict) -> float:
    """'verdict', 'call0.end', 'verdict+1.5' or a number of seconds (all recording time)."""
    if isinstance(anchor, (int, float)):
        return float(anchor)
    offset = 0.0
    if "+" in anchor:
        anchor, extra = anchor.split("+")
        offset = float(extra)
    if anchor.startswith("call"):
        idx, key = anchor[4:].split(".")
        return timing["calls"][int(idx)][key] + offset
    return timing["marks"][anchor] + offset


# ---------------------------------------------------------------- live scenes: pictures

def scene_background(scene: dict, shown: int) -> str:
    """Scene title, the first `shown` callouts, and the phone's frame."""
    items = []
    for i, (_, text) in enumerate(scene.get("callouts", [])[:shown]):
        newest = i == shown - 1
        items.append(f"""
<div style="display:flex;gap:22px;align-items:flex-start;opacity:{1 if newest else .62}">
  <div style="flex:none;width:50px;height:50px;border-radius:50%;background:{MINT if newest else '#2E3D5C'};color:{NAVY};
       display:flex;align-items:center;justify-content:center;font-size:27px;font-weight:700">{i + 1}</div>
  <p style="font-size:35px;line-height:1.3;color:#FFFFFF;font-weight:{700 if newest else 400};padding-top:4px">{html.escape(text)}</p>
</div>""")
    fx, fy = PHONE_X - 14, PHONE_Y - 14
    return page(f"""
<div style="position:absolute;inset:0;background:radial-gradient(1200px 900px at 75% 50%,#1D3157 0%,{NAVY} 70%)"></div>
<div style="position:absolute;left:{fx}px;top:{fy}px;width:{PHONE_W + 28}px;height:{PHONE_H + 28}px;border-radius:52px;
     background:#0B1322;box-shadow:0 0 0 3px #33456B,0 40px 90px rgba(0,0,0,.55)"></div>
<div style="position:absolute;left:150px;top:110px;width:{PHONE_X - 290}px">
  <p style="font-size:26px;letter-spacing:.1em;text-transform:uppercase;color:{MINT};font-weight:700">Live demo · real agent answers</p>
  <h1 style="font-size:78px;line-height:1.08;color:#F4F6F9;font-weight:700;margin-top:18px">{html.escape(scene['title'])}</h1>
  <p style="font-size:36px;line-height:1.35;color:{SOFT};margin-top:16px">{html.escape(scene['sub'])}</p>
  <div style="display:flex;flex-direction:column;gap:26px;margin-top:54px">{''.join(items)}</div>
</div>
<p style="position:absolute;left:150px;bottom:56px;font-size:22px;color:{MUTED}">
  Recorded live from IBM watsonx Orchestrate, unedited · waits for the agents are sped up and labelled</p>""")


def wait_badge(call: dict) -> str:
    secs = call["end"] - call["start"]
    label = AGENT_LABEL.get(call["ep"], "agents")
    return page(f"""
<div style="position:absolute;left:{PHONE_X - 30}px;top:{PHONE_Y + PHONE_H - 150}px;width:{PHONE_W + 60}px;display:flex;justify-content:center">
  <div style="background:rgba(11,19,34,.92);border:2px solid {MINT};border-radius:40px;padding:14px 28px;
       color:#FFFFFF;font-size:25px;font-weight:700;box-shadow:0 10px 30px rgba(0,0,0,.4);white-space:nowrap">
    <span style="color:{MINT}">⏩ {WAIT_SPEED:g}×</span> waiting for the {label} · {secs:.1f} s real time</div>
</div>""", "html,body{background:transparent}")


def phone_mask() -> str:
    return page(f"""<div style="position:absolute;inset:0;background:#000"></div>
<div style="position:absolute;left:{PHONE_X}px;top:{PHONE_Y}px;width:{PHONE_W}px;height:{PHONE_H}px;border-radius:40px;background:#FFF"></div>""")


def scene_segment(work: Path, scene: dict, clip: Path, timing: dict, out: Path) -> float:
    tl = Timeline(clip_seconds(clip), timing.get("calls", []))
    length = tl.length
    total = max(length, scene["seconds"])
    pad = total - length

    reveals = [max(tl.out(anchor_time(a, timing)), 0.2) for a, _ in scene.get("callouts", [])]
    bgs = [work / f"bg_{scene['name']}_{k}.png" for k in range(len(reveals) + 1)]
    waits = list(tl.waits())
    badges = [work / f"badge_{scene['name']}_{j}.png" for j in range(len(waits))]
    render_pngs([(scene_background(scene, k), p) for k, p in enumerate(bgs)])
    render_pngs([(wait_badge(c), p) for (_, _, c), p in zip(waits, badges)], transparent=True)

    inputs, fc = [], []
    for p in bgs:
        inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(p)]
    ci = len(bgs)
    inputs += ["-i", str(clip)]
    mi = ci + 1
    inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(work / "mask.png")]
    for p in badges:
        inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(p)]

    n = len(tl.pieces)
    fc.append(f"[{ci}:v]fps={FPS},split={n}" + "".join(f"[s{i}]" for i in range(n)))
    for i, (a, b, speed, _) in enumerate(tl.pieces):
        fc.append(f"[s{i}]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{speed}[p{i}]")
    fc.append("".join(f"[p{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,fps={FPS},scale={PHONE_W}:{PHONE_H},"
              f"tpad=stop_mode=clone:stop_duration={pad:.3f},format=yuva420p[ph0]")
    fc.append(f"[{mi}:v]crop={PHONE_W}:{PHONE_H}:{PHONE_X}:{PHONE_Y},format=gray[mk]")
    fc.append("[ph0][mk]alphamerge[ph]")
    fc.append("[0:v]format=yuv420p[b0]")
    for k in range(1, len(bgs)):
        fc.append(f"[{k}:v]format=yuva420p,fade=t=in:st={reveals[k - 1]:.3f}:d=0.4:alpha=1[f{k}]")
        fc.append(f"[b{k - 1}][f{k}]overlay[b{k}]")
    fc.append(f"[b{len(bgs) - 1}][ph]overlay={PHONE_X}:{PHONE_Y}[v0]")
    last = "v0"
    for j, (a, b, _) in enumerate(waits):
        fc.append(f"[{last}][{mi + 1 + j}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[w{j}]")
        last = f"w{j}"
    fc.append(f"[{last}]{fades(total)},format=yuv420p[out]")
    run([ffmpeg(), "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[out]", "-t", f"{total:.3f}", *ENC, str(out)])
    return total


# ---------------------------------------------------------------- stills and cards

def still_segment(png: Path, seconds: float, out: Path, zoom: float = 0.05):
    """A still with a slow push-in (rendered at 2x so the motion stays smooth)."""
    frames = int(round(seconds * FPS))
    vf = (f"scale={W * 2}:{H * 2},zoompan=z='1+{zoom}*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d=1:s={W}x{H}:fps={FPS},{fades(seconds)}")
    run([ffmpeg(), "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{seconds:.3f}", "-i", str(png),
         "-vf", vf, "-frames:v", str(frames), *ENC, str(out)])


def add_fades(src: Path, seconds: float, out: Path):
    run([ffmpeg(), "-y", "-i", str(src), "-vf", fades(seconds), *ENC, str(out)])


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
<div style="position:absolute;inset:0;background:{NAVY};padding:100px 128px;display:flex;flex-direction:column;gap:36px">
  <div>
    <p style="font-size:28px;color:{MINT};font-weight:700">Built with IBM Bob</p>
    <h1 style="font-size:64px;color:#F4F6F9;font-weight:700;margin-top:8px">{len(log)} commits by Bob, straight from git</h1>
  </div>
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


# ---------------------------------------------------------------- Bob Shell montage

BOX_X, BOX_Y, BOX_W, BOX_H = 140, 250, 1640, 760


def bob_piece_background(piece: dict) -> str:
    return page(f"""
<div style="position:absolute;inset:0;background:{NAVY}"></div>
<p style="position:absolute;left:140px;top:72px;font-size:28px;color:{MINT};font-weight:700">{html.escape(piece['kicker'])}</p>
<h1 style="position:absolute;left:140px;top:116px;width:1640px;font-size:50px;line-height:1.15;color:#F4F6F9;font-weight:700">
  {html.escape(piece['title'])}</h1>
<div style="position:absolute;left:{BOX_X - 12}px;top:{BOX_Y - 12}px;width:{BOX_W + 24}px;height:{BOX_H + 24}px;border-radius:22px;background:#1E2E50"></div>
<p style="position:absolute;left:140px;bottom:26px;font-size:22px;color:{MUTED}">
  Real Bob Shell session on this repository · cropped{' and sped up' if piece['speed'] > 1 else ''}</p>""")


def bob_shell_segment(work: Path, clip: Path, out: Path) -> float:
    parts, total = [], 0.0
    for i, pc in enumerate(BOB_SHELL):
        bg = work / f"bobbg_{i}.png"
        render_pngs([(bob_piece_background(pc), bg)])
        dur = (pc["to"] - pc["from"]) / pc["speed"]
        x, y, w, h = pc["crop"]
        scale = min(BOX_W / w, BOX_H / h)
        sw, sh = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
        ox, oy = BOX_X + (BOX_W - sw) // 2, BOX_Y + (BOX_H - sh) // 2
        masks = "".join(f",drawbox=x={mx}:y={my}:w={mw}:h={mh}:color=white:t=fill" for mx, my, mw, mh in pc.get("hide", []))
        fc = (f"[1:v]trim=start={pc['from']}:end={pc['to']},setpts=(PTS-STARTPTS)/{pc['speed']},fps={FPS},"
              f"crop={w}:{h}:{x}:{y}{masks},scale={sw}:{sh}:flags=lanczos[c];"
              f"[0:v][c]overlay={ox}:{oy}:shortest=1,{fades(dur)},format=yuv420p[out]")
        part = work / f"bob_{i}.mp4"
        run([ffmpeg(), "-y", "-loop", "1", "-t", f"{dur:.3f}", "-i", str(bg), "-i", str(clip),
             "-filter_complex", fc, "-map", "[out]", "-t", f"{dur:.3f}", *ENC, str(part)])
        parts.append(part)
        total += dur
    lst = work / "bob_list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    return total


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
        words = len(text.split())
        vo.append(f"[{ts(start)[3:8]} – {ts(start + dur)[3:8]}]  ({words} words in {dur:.0f} s)\n{text}")
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
        "Scam Shield demo: read each line while that part is on screen (times are mm:ss).\n"
        "Start each line as its part begins; every line fits its part at a calm pace.\n\n" + "\n\n".join(vo) + "\n",
        encoding="utf-8")


# ---------------------------------------------------------------- main

def anim_html(name: str) -> str:
    if name == "hook":
        return animate.hook_card(OUT / "screens" / "verdict-en-scam.png",
                                 "You are under digital arrest. Stay on the video call. Do not inform anyone, or you will be jailed.")
    if name == "arch":
        return animate.architecture_card()
    if name == "headline":
        return animate.headline_card(21, 4, 22, "4.1 s", "1 in 18")
    if name == "close":
        return animate.close_card()
    raise SystemExit(f"Unknown animated card {name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", help="your recorded voiceover (m4a/mp3/wav) to mix in")
    args = ap.parse_args()

    work = OUT / "_build"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    render_pngs([(phone_mask(), work / "mask.png")])

    segments, timed, t = [], [], 0.0
    for i, s in enumerate(SCENES):
        out = work / f"{i:02d}_{s['name']}.mp4"
        kind = s["kind"]
        if kind == "slide":
            png = SLIDES / f"{s['name']}.png"
            if not png.exists():
                sys.exit(f"Missing slide image {png}")
            still_segment(png, s["seconds"], out)
            dur = float(s["seconds"])
        elif kind == "card":
            png = work / f"{s['name']}.png"
            render_pngs([(bob_card(), png)])
            still_segment(png, s["seconds"], out, zoom=0.035)
            dur = float(s["seconds"])
        elif kind == "anim":
            raw = work / f"{s['name']}_raw.mp4"
            animate.render_animation(anim_html(s["name"]), s["seconds"], raw, ffmpeg(), FPS)
            add_fades(raw, s["seconds"], out)
            dur = float(s["seconds"])
        elif kind == "scene":
            clip = OUT / "scenes" / f"{s['name']}.webm"
            tfile = clip.with_suffix(".json")
            if not clip.exists() or not tfile.exists():
                sys.exit(f"Missing recording {clip} (or its timing file). Run: python demo/record.py --only {s['name']}")
            dur = scene_segment(work, s, clip, json.loads(tfile.read_text(encoding="utf-8")), out)
        elif kind == "bobshell":
            clip = DEMO / "clips" / "bob_shell.mp4"
            if not clip.exists():
                continue
            dur = bob_shell_segment(work, clip, out)
        else:
            sys.exit(f"Unknown scene kind {kind}")
        segments.append(out)
        timed.append((t, dur, s.get("say", "")))
        words = len(s.get("say", "").split())
        warn = "  <- narration may be rushed" if dur and words / dur > 2.7 else ""
        print(f"  {ts(t)[3:8]}  {s['name']} ({dur:.1f}s, {words} words){warn}")
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
