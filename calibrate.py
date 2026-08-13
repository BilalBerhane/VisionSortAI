#!/usr/bin/env python3
"""Threshold calibration helper -- run against a folder of REAL photos to see
the actual blur_score distribution instead of guessing at the config.py
placeholder (100.0).

It won't pick a threshold for you (that requires human eyeballing), but it
will: print summary stats, show how many photos would get flagged at a range
of candidate thresholds, and copy the lowest-scoring (most likely blurry)
photos into a review folder, filename-prefixed with their score, so you can
open that folder and visually confirm whether they're actually blurry.

Usage:
    python calibrate.py --path "C:\\...\\Test_Pics"
    python calibrate.py --path "C:\\...\\Test_Pics" --review-count 30 --review-dir .\\blur_review
"""
from __future__ import annotations

import argparse
import shutil
import statistics
from pathlib import Path

from analyze_and_backup.quality import blur_score, exposure_metrics


def main():
    parser = argparse.ArgumentParser(description="Calibrate the blur threshold against real photos")
    parser.add_argument("--path", required=True, help="Folder of real photos to analyze")
    parser.add_argument("--review-dir", default="./blur_review", help="Where to copy the lowest-scoring (likely-blurry) photos for visual review")
    parser.add_argument("--review-count", type=int, default=20, help="How many of the lowest-scoring photos to copy for review")
    parser.add_argument("--good-review-dir", default="./quality_review", help="Where to copy the highest-scoring (likely-sharp) photos for visual review")
    parser.add_argument("--good-review-count", type=int, default=20, help="How many of the highest-scoring photos to copy for review")
    parser.add_argument("--no-good-review", action="store_true", help="Skip copying the sharp/good comparison set")
    parser.add_argument("--extensions", nargs="*", default=[".jpg", ".jpeg", ".png"])
    args = parser.parse_args()

    folder = Path(args.path)
    exts = {e.lower() for e in args.extensions}
    photos = [p for p in sorted(folder.rglob("*")) if p.is_file() and p.suffix.lower() in exts]
    if not photos:
        print(f"No photos found in {folder} with extensions {exts}")
        return

    results = []
    for p in photos:
        try:
            score = blur_score(p)
            exp = exposure_metrics(p)
            results.append((p, score, exp))
        except Exception as exc:
            print(f"  SKIP {p.name}: {exc}")

    if not results:
        print("Nothing scored successfully.")
        return

    results.sort(key=lambda r: r[1])  # ascending blur_score => most-likely-blurry first
    scores = [r[1] for r in results]

    print(f"\n{len(results)} photos scored from {folder}")
    print(
        f"blur_score  min={min(scores):.1f}  max={max(scores):.1f}  "
        f"mean={statistics.mean(scores):.1f}  median={statistics.median(scores):.1f}"
    )

    print("\nHow many photos would be flagged 'blurry' at each candidate threshold:")
    for t in (25, 50, 75, 100, 125, 150, 200, 250, 300):
        n = sum(1 for s in scores if s < t)
        print(f"  threshold {t:>4}: {n:>4} / {len(scores)}  ({n / len(scores):.0%})")

    n_show = min(20, len(results))
    print(f"\n{n_show} LOWEST blur_score photos (most likely blurry -- check these first):")
    for p, score, _ in results[:n_show]:
        print(f"  {score:>9.1f}  {p.name}")

    print(f"\n{n_show} HIGHEST blur_score photos (most likely sharp, for comparison):")
    for p, score, _ in results[-n_show:]:
        print(f"  {score:>9.1f}  {p.name}")

    review_dir = Path(args.review_dir)
    review_dir.mkdir(parents=True, exist_ok=True)
    n_copy = min(args.review_count, len(results))
    for p, score, _ in results[:n_copy]:
        dest = review_dir / f"{score:.0f}_{p.name}"
        shutil.copy2(p, dest)

    print(
        f"\nCopied the {n_copy} lowest-scoring photos into {review_dir.resolve()}, "
        "filenames prefixed with their blur_score. Open that folder and look at them:\n"
        "  - if they're genuinely blurry, note the highest score among the genuinely-blurry ones\n"
        "  - if some look fine to your eye, note their score too -- your real threshold should sit\n"
        "    between the highest confirmed-blurry score and the lowest confirmed-fine score\n"
        "Then update BLUR_VARIANCE_THRESHOLD in your .env to that number."
    )

    if not args.no_good_review:
        good_dir = Path(args.good_review_dir)
        good_dir.mkdir(parents=True, exist_ok=True)
        n_good = min(args.good_review_count, len(results))
        for p, score, _ in results[-n_good:]:
            dest = good_dir / f"{score:.0f}_{p.name}"
            shutil.copy2(p, dest)

        print(
            f"\nCopied the {n_good} highest-scoring photos into {good_dir.resolve()} "
            "(the sharp/good comparison set) -- filenames prefixed with their blur_score. "
            "Useful for sanity-checking that your threshold isn't accidentally catching good photos too."
        )


if __name__ == "__main__":
    main()
