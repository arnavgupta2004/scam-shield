#!/usr/bin/env python3
"""
End-to-end evaluation: sends every labelled row through the running backend
(/analyse -> watsonx Orchestrate agents) and reports how well it does.

  python eval/eval.py                         # dev + held-out (+ blind if present)
  python eval/eval.py --dataset eval/holdout_set.csv
  python eval/eval.py --dry-run               # no server, no Orchestrate: rules-only, to test the script

Scoring (no flattering):
  - "scam" on a scam row = caught; "genuine" on a scam row = missed.
  - "uncertain" is reported on its own and never counted as correct for genuine rows.
  - Recall is given strictly (uncertain = missed) and as "warned" (uncertain = flagged,
    since the user is told to be careful).
  - Rows answered by the offline rules fallback instead of the agents are counted
    separately; if any appear, the agent numbers are not clean.

Writes eval/eval_report.md and eval/results_<dataset>.csv.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETS = ["eval/eval_set.csv", "eval/holdout_set.csv", "eval/blind_set.csv"]
SET_NAMES = {"eval_set": "dev", "holdout_set": "held-out", "blind_set": "blind"}


def load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["label"] = r["label"].strip().lower()
    return rows


async def run_rows(rows, client: httpx.AsyncClient, concurrency: int, retries: int):
    sem = asyncio.Semaphore(concurrency)
    results = [None] * len(rows)

    async def one(i, row):
        async with sem:
            for attempt in range(retries + 1):
                t0 = time.perf_counter()
                try:
                    resp = await client.post("/analyse", json={"text": row["text"], "lang": row["lang"], "mode": "message"})
                    resp.raise_for_status()
                    body = resp.json()
                    results[i] = {**row, "pred": body["verdict"], "source": body["source"],
                                  "pred_type": body.get("scam_type") or "",
                                  "latency_ms": int((time.perf_counter() - t0) * 1000), "error": ""}
                    break
                except Exception as exc:  # keep going; record the failure
                    if attempt == retries:
                        results[i] = {**row, "pred": "error", "source": "error", "pred_type": "",
                                      "latency_ms": int((time.perf_counter() - t0) * 1000),
                                      "error": type(exc).__name__}
                    else:
                        await asyncio.sleep(2 * (attempt + 1))
            done = sum(r is not None for r in results)
            print(f"\r  {done}/{len(rows)}", end="", flush=True)

    await asyncio.gather(*(one(i, r) for i, r in enumerate(rows)))
    print()
    return results


def safe_div(a, b):
    return a / b if b else None


def metrics(results: list[dict]) -> dict:
    scam = [r for r in results if r["label"] == "scam"]
    gen = [r for r in results if r["label"] == "genuine"]
    c = Counter((r["label"], r["pred"]) for r in results)
    tp, fn = c[("scam", "scam")], c[("scam", "genuine")]
    fp, tn = c[("genuine", "scam")], c[("genuine", "genuine")]
    u_s, u_g = c[("scam", "uncertain")], c[("genuine", "uncertain")]
    lat = [r["latency_ms"] for r in results if r["source"] == "agent"]
    return {
        "n": len(results), "n_scam": len(scam), "n_genuine": len(gen),
        "tp": tp, "fn": fn, "fp": fp, "tn": tn, "uncertain_scam": u_s, "uncertain_genuine": u_g,
        "precision": safe_div(tp, tp + fp),
        "recall_strict": safe_div(tp, len(scam)),
        "recall_warned": safe_div(tp + u_s, len(scam)),
        "false_alarm_strict": safe_div(fp, len(gen)),
        "false_alarm_warned": safe_div(fp + u_g, len(gen)),
        "genuine_cleared": safe_div(tn, len(gen)),
        "sources": dict(Counter(r["source"] for r in results)),
        "latency_median_ms": int(statistics.median(lat)) if lat else None,
        "latency_p90_ms": int(statistics.quantiles(lat, n=10)[-1]) if len(lat) >= 10 else None,
    }


def pct(x):
    return "n/a" if x is None else f"{x * 100:.0f}%"


def report(all_results: dict[str, list[dict]], mode_note: str) -> str:
    names = list(all_results)
    m = {n: metrics(r) for n, r in all_results.items()}
    lines = [
        "# Scam Shield evaluation report",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M}. {mode_note}",
        "",
        "Each row was sent through the full pipeline: local PII redaction, then the watsonx Orchestrate "
        "agents. The dev set was written alongside the rules; the held-out set was written separately "
        "and never used to tune anything.",
        "",
        "| Metric | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]
    rows = [
        ("Messages (scam / genuine)", lambda x: f"{x['n']} ({x['n_scam']} / {x['n_genuine']})"),
        ("Scams caught (strict recall)", lambda x: pct(x["recall_strict"])),
        ("Scams caught or warned (uncertain counted)", lambda x: pct(x["recall_warned"])),
        ("Scams marked safe (missed)", lambda x: str(x["fn"])),
        ("Precision", lambda x: pct(x["precision"])),
        ("Genuine messages cleared", lambda x: pct(x["genuine_cleared"])),
        ("False alarms (genuine marked scam)", lambda x: pct(x["false_alarm_strict"])),
        ("Genuine marked uncertain", lambda x: str(x["uncertain_genuine"])),
        ("Median latency (agent answers)", lambda x: "n/a" if x["latency_median_ms"] is None else f"{x['latency_median_ms'] / 1000:.1f} s"),
        ("90th percentile latency", lambda x: "n/a" if x["latency_p90_ms"] is None else f"{x['latency_p90_ms'] / 1000:.1f} s"),
        ("Answered by agents / rules fallback / errors",
         lambda x: f"{x['sources'].get('agent', 0)} / {x['sources'].get('rules', 0)} / {x['sources'].get('error', 0)}"),
    ]
    for label, fn in rows:
        lines.append(f"| {label} | " + " | ".join(fn(m[n]) for n in names) + " |")

    for name, results in all_results.items():
        lines += ["", f"## {name}: by language", "", "| Language | Scams caught | Genuine cleared |", "|---|---|---|"]
        by_lang = defaultdict(list)
        for r in results:
            by_lang[r["lang"]].append(r)
        for lang in sorted(by_lang):
            mm = metrics(by_lang[lang])
            lines.append(f"| {lang} | {mm['tp']}/{mm['n_scam']} | {mm['tn']}/{mm['n_genuine']} |")
        wrong = [r for r in results if not (
            (r["label"] == "scam" and r["pred"] == "scam") or (r["label"] == "genuine" and r["pred"] == "genuine"))]
        if wrong:
            lines += ["", f"Rows not answered correctly ({len(wrong)}):", ""]
            for r in wrong:
                note = f", {r['error']}" if r["error"] else ""
                lines.append(f"- id {r['id']} ({r['lang']}, {r['label']}/{r['scam_type']}): got **{r['pred']}** via {r['source']}{note}")

    if any(m[n]["sources"].get("rules") or m[n]["sources"].get("error") for n in names):
        lines += ["", "> Some rows were answered by the offline rules fallback or failed. "
                      "Those are not agent answers; re-run when Orchestrate is reachable for clean numbers."]
    return "\n".join(lines) + "\n"


def write_csv(path: Path, results: list[dict]):
    cols = ["id", "lang", "label", "scam_type", "pred", "pred_type", "source", "latency_ms", "error"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", default="http://localhost:8000")
    ap.add_argument("--dataset", action="append", help="CSV path (repeatable). Default: dev, held-out, blind if present")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=90)
    ap.add_argument("--limit", type=int, help="only the first N rows of each set (quick check)")
    ap.add_argument("--dry-run", action="store_true", help="run the backend in-process without Orchestrate (rules only)")
    ap.add_argument("--report", default="eval/eval_report.md")
    args = ap.parse_args()

    paths = [ROOT / p for p in (args.dataset or DEFAULT_SETS)]
    paths = [p for p in paths if p.exists()]
    if not paths:
        sys.exit("No dataset files found.")

    async def go():
        if args.dry_run:
            import os
            os.environ.pop("WO_INSTANCE", None)
            os.environ.pop("WO_API_KEY", None)
            sys.path.insert(0, str(ROOT))
            from backend.main import app
            transport = httpx.ASGITransport(app=app)
            base = "http://dry-run"
        else:
            transport, base = None, args.backend
        async with httpx.AsyncClient(base_url=base, timeout=args.timeout, transport=transport) as client:
            if not args.dry_run:
                try:
                    health = (await client.get("/health")).json()
                except Exception:
                    sys.exit(f"Backend not reachable at {args.backend}. Start it with: uvicorn backend.main:app")
                if not health.get("orchestrate_configured") or not health["agents_configured"].get("analyse"):
                    print("WARNING: backend has no Orchestrate credentials/agent id; results will be rules-only.")
            out = {}
            for p in paths:
                rows = load_rows(p)[: args.limit] if args.limit else load_rows(p)
                name = SET_NAMES.get(p.stem, p.stem)
                print(f"{name}: {len(rows)} rows")
                out[name] = await run_rows(rows, client, args.concurrency, args.retries)
                write_csv(ROOT / "eval" / f"results_{p.stem}.csv", out[name])
            return out

    results = asyncio.run(go())
    note = "DRY RUN: rules fallback only, no agents." if args.dry_run else f"Backend: {args.backend}."
    text = report(results, note)
    (ROOT / args.report).write_text(text, encoding="utf-8")
    print()
    print(text.split("\n## ")[0])
    print(f"Full report: {args.report}")


if __name__ == "__main__":
    main()
