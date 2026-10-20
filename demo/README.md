# Demo video

Builds the demo video (just under 3 minutes) from live recordings of the app, animated cards, the deck slides and a Bob Shell recording, with captions and a timed voiceover script. It also takes the screenshots for the deck.

The app scenes are real: the recorder waits for each answer from the watsonx Orchestrate agents and **stops if any answer came from the offline rules or templates**. Answers are never edited. The only change to a recording is that the time spent waiting for an agent plays faster, with an on-screen label giving the real wait (for example "6× · 12.3 s real time").

## Run it

```bash
source .venv/bin/activate
pip install -r demo/requirements.txt
python -m playwright install chromium

uvicorn backend.main:app          # in one terminal, with .env set up
python demo/make_video.py         # in another: records 6 scenes, then builds the video
```

Output in `demo/output/`:

| File | What it is |
|---|---|
| `scam-shield-demo.mp4` | The video (silent until you add your voice) |
| `voiceover.txt` | What to say, with the time each line starts and ends |
| `captions.srt` | Captions; upload this file to YouTube with the video |
| `screens/*.png` | Real app screenshots for the deck (verdicts, live-call coach, family alert, report steps) |
| `scenes/*.webm` | The raw recordings |
| `scenes/*.json` | When each agent call started and ended, and named moments, used to time the speed-ups and callouts |

## Add your voice

1. Play `scam-shield-demo.mp4` and record yourself reading `voiceover.txt` along with it (QuickTime › New Audio Recording, or your phone).
2. Save it, for example as `vo.m4a`, then: `python demo/make_video.py --compose-only --voice vo.m4a`

## What is in the video

- **Cold open** (`animate.py`): a "digital arrest" call's words appear, then the real verdict screenshot from this recording lands.
- **Live scenes** (`record.py`): the phone in a device frame, with numbered callouts beside it that appear at recorded moments (for example `verdict`, `call0.start`, `verdict+2`).
- **How it works** (`animate.py`): the four agents, and the message before and after on-device redaction (the masked text is real `redact_pii` output).
- **Built with Bob**: the Bob commits read from git, then the Bob Shell montage from `demo/clips/bob_shell.mp4`.
- **Results and close** (`animate.py`): held-out scams caught, counted up, and a closing card.

## Bob Shell footage

`demo/clips/bob_shell.mp4` is a screen recording of a Bob Shell session. `BOB_SHELL` in `timeline.py` picks the moments (start, end, speed-up, crop) and blanks out anything private, such as the signed-in e-mail on Bob's login line. If you replace the clip or change a crop, check the frames again. The montage is skipped if the clip is missing.

## Changing things

- Scene order, timings, callouts and narration: `demo/timeline.py`. `compose.py` warns when a line has more words than its scene can fit at a calm pace.
- Animated cards (cold open, architecture, results, close): `demo/animate.py`. Each frame is rendered by pausing the page's CSS animations at that time, so the timing is exact.
- How much faster agent waits play: `WAIT_SPEED` in `demo/compose.py`
- Re-record one scene (check_en, screenshot, call_kn, alert, genuine, tricks): `python demo/record.py --only call_kn`, then `python demo/compose.py`
- Watch the browser while recording: add `--headed`
- The slide images in `assets/slides/` are rendered from the deck; replace them with exports of the deck if you change the slides.
- Fonts in `assets/fonts/` are Atkinson Hyperlegible and Noto Sans (SIL Open Font License, licences included).
