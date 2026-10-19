#!/usr/bin/env python3
"""
One command for the demo video:

    python demo/make_video.py                 # record the live scenes, then build the video
    python demo/make_video.py --voice vo.m4a  # same, with your voiceover mixed in
    python demo/make_video.py --compose-only --voice vo.m4a   # reuse recordings, add voiceover

The backend must be running with Orchestrate configured (uvicorn backend.main:app).
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    args = sys.argv[1:]
    compose_only = "--compose-only" in args
    args = [a for a in args if a != "--compose-only"]
    rec_args = [a for a in args if a in ("--headed",) or a.startswith("--base")]
    if not compose_only:
        r = subprocess.run([sys.executable, str(HERE / "record.py"), *rec_args])
        if r.returncode:
            sys.exit(r.returncode)
    comp_args = []
    if "--voice" in args:
        comp_args = ["--voice", args[args.index("--voice") + 1]]
    sys.exit(subprocess.run([sys.executable, str(HERE / "compose.py"), *comp_args]).returncode)


if __name__ == "__main__":
    main()
