"""
eval/baseline.py — offline baseline over one or two eval datasets.

Uses only the five Python tools (no network calls, no Orchestrate).
Verdict rule:
  scam    if urgency level is "high" OR "medium", OR match_scam_pattern returns a type
  genuine otherwise

Usage:
    # Single dataset (default: eval/eval_set.csv)
    python eval/baseline.py

    # Explicit path
    python eval/baseline.py --dataset eval/eval_set.csv

    # Side-by-side comparison (dev vs held-out)
    python eval/baseline.py --dataset eval/eval_set.csv --compare eval/holdout_set.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.tools.redact_pii import redact_pii
from agents.tools.extract_entities import _extract_entities_impl as extract_entities
from agents.tools.score_urgency import _score_urgency_impl as score_urgency
from agents.tools.match_scam_pattern import _match_scam_pattern_impl as match_scam_pattern

_DEFAULT_DATASET = os.path.join(os.path.dirname(__file__), "eval_set.csv")
_HOLDOUT_DATASET = os.path.join(os.path.dirname(__file__), "holdout_set.csv")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def predict(text: str) -> str:
    """Return 'scam' or 'genuine' using only offline tools."""
    entities = extract_entities(text)
    redacted = redact_pii(text)
    urgency = score_urgency(redacted, entities)
    pattern = match_scam_pattern(redacted)
    if urgency["level"] in ("high", "medium") or pattern["scam_type"] is not None:
        return "scam"
    return "genuine"


def run_dataset(path: str) -> list[dict]:
    """Load CSV, run predict on every row, return result dicts."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "lang": row["lang"],
            "label": row["label"],
            "scam_type": row["scam_type"],
            "pred": predict(row["text"]),
        })
    return results


def compute_metrics(rows: list[dict]) -> dict:
    tp = fp = tn = fn = 0
    for r in rows:
        pred, gold = r["pred"], r["label"]
        if gold == "scam" and pred == "scam":
            tp += 1
        elif gold == "genuine" and pred == "scam":
            fp += 1
        elif gold == "genuine" and pred == "genuine":
            tn += 1
        else:  # gold == "scam" and pred == "genuine"
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    far = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return {
        "total": len(rows), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1, "false_alarm_rate": far,
    }


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

W = 50  # column width


def _hdr(label: str) -> str:
    return f"  {label:<{W - 2}}"


def print_single(label: str, results: list[dict]) -> None:
    """Print full report for one dataset."""
    overall = compute_metrics(results)
    _print_overall(label, overall)

    by_lang: dict[str, list] = defaultdict(list)
    for r in results:
        by_lang[r["lang"]].append(r)
    for lang in sorted(by_lang):
        m = compute_metrics(by_lang[lang])
        _print_overall(f"LANGUAGE: {lang.upper()} ({m['total']} rows)", m)

    _print_type_recall(results)
    _print_misses(results)


def _print_overall(title: str, m: dict) -> None:
    print(f"\n{'=' * W}")
    print(f"  {title}")
    print(f"{'=' * W}")
    print(f"  Rows      : {m['total']}")
    print(f"  TP/FP/TN/FN: {m['tp']}/{m['fp']}/{m['tn']}/{m['fn']}")
    print(f"  Precision : {m['precision']:.3f}")
    print(f"  Recall    : {m['recall']:.3f}")
    print(f"  F1        : {m['f1']:.3f}")
    print(f"  False-alarm: {m['false_alarm_rate']:.3f}")


def _print_type_recall(results: list[dict]) -> None:
    by_type: dict[str, list] = defaultdict(list)
    for r in results:
        if r["label"] == "scam":
            by_type[r["scam_type"]].append(r)
    print(f"\n{'=' * W}")
    print("  PER-SCAM-TYPE RECALL")
    print(f"{'=' * W}")
    for stype in sorted(by_type):
        rows = by_type[stype]
        correct = sum(1 for r in rows if r["pred"] == "scam")
        print(f"  {stype:22} {correct}/{len(rows)} = {correct/len(rows):.2f}")


def _print_misses(results: list[dict]) -> None:
    misses = [r for r in results if r["label"] != r["pred"]]
    if misses:
        print(f"\n{'=' * W}")
        print(f"  MISCLASSIFIED ({len(misses)})")
        print(f"{'=' * W}")
        for r in misses:
            print(f"  id={r['id']:>3} lang={r['lang']} gold={r['label']:7} pred={r['pred']:7} {r['scam_type']}")


def print_side_by_side(label_a: str, results_a: list[dict],
                       label_b: str, results_b: list[dict]) -> None:
    """Print a two-column comparison: overall, per-language, per-type."""
    C = 30  # per-column width

    def row(left: str, right: str) -> None:
        print(f"  {left:<{C}}  {right}")

    def divider() -> None:
        print(f"  {'─' * C}  {'─' * C}")

    # ---- Overall ----
    ma = compute_metrics(results_a)
    mb = compute_metrics(results_b)
    print(f"\n{'=' * (C * 2 + 6)}")
    row(f"[ {label_a} ]", f"[ {label_b} ]")
    print(f"{'=' * (C * 2 + 6)}")
    divider()
    row(f"  Rows      : {ma['total']}", f"  Rows      : {mb['total']}")
    row(f"  TP/FP/TN/FN: {ma['tp']}/{ma['fp']}/{ma['tn']}/{ma['fn']}",
        f"  TP/FP/TN/FN: {mb['tp']}/{mb['fp']}/{mb['tn']}/{mb['fn']}")
    row(f"  Precision : {ma['precision']:.3f}", f"  Precision : {mb['precision']:.3f}")
    row(f"  Recall    : {ma['recall']:.3f}",    f"  Recall    : {mb['recall']:.3f}")
    row(f"  F1        : {ma['f1']:.3f}",        f"  F1        : {mb['f1']:.3f}")
    row(f"  False-alarm: {ma['false_alarm_rate']:.3f}",
        f"  False-alarm: {mb['false_alarm_rate']:.3f}")
    divider()

    # ---- Per language ----
    langs = sorted(set(r["lang"] for r in results_a) | set(r["lang"] for r in results_b))
    print(f"\n  {'PER-LANGUAGE'}")
    divider()
    for lang in langs:
        ra = [r for r in results_a if r["lang"] == lang]
        rb = [r for r in results_b if r["lang"] == lang]
        if not ra and not rb:
            continue
        mla = compute_metrics(ra) if ra else {}
        mlb = compute_metrics(rb) if rb else {}
        left = (f"  {lang.upper()}: P={mla['precision']:.2f} R={mla['recall']:.2f}"
                f" F1={mla['f1']:.2f}") if mla else "  —"
        right = (f"  {lang.upper()}: P={mlb['precision']:.2f} R={mlb['recall']:.2f}"
                 f" F1={mlb['f1']:.2f}") if mlb else "  —"
        row(left, right)
    divider()

    # ---- Per scam type ----
    types_a: dict[str, list] = defaultdict(list)
    types_b: dict[str, list] = defaultdict(list)
    for r in results_a:
        if r["label"] == "scam":
            types_a[r["scam_type"]].append(r)
    for r in results_b:
        if r["label"] == "scam":
            types_b[r["scam_type"]].append(r)
    all_types = sorted(types_a.keys() | types_b.keys())
    print(f"\n  {'PER-SCAM-TYPE RECALL'}")
    divider()
    for stype in all_types:
        ra = types_a.get(stype, [])
        rb = types_b.get(stype, [])
        ca = sum(1 for r in ra if r["pred"] == "scam")
        cb = sum(1 for r in rb if r["pred"] == "scam")
        left = f"  {stype}: {ca}/{len(ra)}={ca/len(ra):.2f}" if ra else f"  {stype}: —"
        right = f"  {stype}: {cb}/{len(rb)}={cb/len(rb):.2f}" if rb else f"  {stype}: —"
        row(left, right)
    divider()

    # ---- Misses ----
    misses_a = [r for r in results_a if r["label"] != r["pred"]]
    misses_b = [r for r in results_b if r["label"] != r["pred"]]
    if misses_a or misses_b:
        print(f"\n  MISCLASSIFIED — {label_a} ({len(misses_a)}):")
        for r in misses_a:
            print(f"    id={r['id']:>3} lang={r['lang']} gold={r['label']:7} pred={r['pred']:7} {r['scam_type']}")
        print(f"\n  MISCLASSIFIED — {label_b} ({len(misses_b)}):")
        for r in misses_b:
            print(f"    id={r['id']:>3} lang={r['lang']} gold={r['label']:7} pred={r['pred']:7} {r['scam_type']}")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline scam-shield baseline over eval CSV(s)."
    )
    parser.add_argument(
        "--dataset",
        default=_DEFAULT_DATASET,
        metavar="PATH",
        help=f"Primary eval CSV (default: {_DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--compare",
        default=None,
        metavar="PATH",
        help="Second CSV to compare side-by-side (e.g. holdout_set.csv)",
    )
    args = parser.parse_args()

    results_a = run_dataset(args.dataset)
    label_a = os.path.basename(args.dataset).replace(".csv", "")

    if args.compare:
        results_b = run_dataset(args.compare)
        label_b = os.path.basename(args.compare).replace(".csv", "")
        print_side_by_side(
            f"dev  [{label_a}]", results_a,
            f"held-out  [{label_b}]", results_b,
        )
    else:
        print_single(f"OVERALL — {label_a}", results_a)


if __name__ == "__main__":
    main()
