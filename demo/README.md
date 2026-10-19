# Demo video

Builds the ~3-minute demo video from the deck slides and live recordings of the app, with captions and a timed voiceover script. It also takes the screenshots for the deck.

The app scenes are real: the recorder waits for each answer from the watsonx Orchestrate agents and **stops if any answer came from the offline rules or templates**.

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

## Add your voice

1. Play `scam-shield-demo.mp4` and record yourself reading `voiceover.txt` along with it (QuickTime › New Audio Recording, or your phone).
2. Save it, for example as `vo.m4a`, then: `python demo/make_video.py --compose-only --voice vo.m4a`

## Optional: your own Bob Shell footage

Save a screen recording of Bob Shell as `demo/clips/bob_shell.mp4` and it is placed after the Bob commits card. Its voiceover line is empty, so add a sentence to the `bob_shell` entry in `timeline.py` if you talk over it.

## Changing things

- Scene order, timings and narration: `demo/timeline.py`
- Re-record one scene (check_en, screenshot, call_kn, alert, genuine, tricks): `python demo/record.py --only call_kn`, then `python demo/compose.py`
- Watch the browser while recording: add `--headed`
- The slide images in `assets/slides/` are rendered from the deck; replace them with exports of the deck if you change the slides.
- Fonts in `assets/fonts/` are Atkinson Hyperlegible and Noto Sans (SIL Open Font License, licences included).
