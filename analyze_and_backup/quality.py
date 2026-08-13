"""Cheap local quality checks that run on the Pi before the cloud AI call.

blur_score: Laplacian variance of the grayscale image. Sharp images have a
lot of high-frequency edge content, so the Laplacian (a 2nd-derivative edge
filter) has high variance; blurry images are smooth, so variance is low.
This is resolution-dependent -- the default threshold in config.py is a
starting point and should be recalibrated against real sample photos from
the actual camera (see README).

exposure_metrics: fraction of pixels clipped at pure black/white, plus mean
luminance, used to flag under/over-exposed shots.

Framing and overall subjective quality are NOT computed here -- those are
left to the vision agent, which is much better suited to composition
judgment than a hand-rolled CV heuristic.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def _grayscale_array(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.asarray(img.convert("L"), dtype=np.float64)


def blur_score(path: Path) -> float:
    gray = _grayscale_array(path)
    return float(ndimage.laplace(gray).var())


@dataclass
class ExposureMetrics:
    clipped_low_pct: float
    clipped_high_pct: float
    mean_luminance: float


def exposure_metrics(path: Path) -> ExposureMetrics:
    gray = _grayscale_array(path)
    total = gray.size
    return ExposureMetrics(
        clipped_low_pct=float(np.count_nonzero(gray <= 0)) / total,
        clipped_high_pct=float(np.count_nonzero(gray >= 255)) / total,
        mean_luminance=float(gray.mean()),
    )


def is_bad_exposure(
    metrics: ExposureMetrics,
    clip_pct_threshold: float,
    luminance_min: float,
    luminance_max: float,
) -> tuple[bool, list[str]]:
    reasons = []
    if metrics.clipped_low_pct > clip_pct_threshold:
        reasons.append(f"{metrics.clipped_low_pct:.1%} of pixels clipped to black")
    if metrics.clipped_high_pct > clip_pct_threshold:
        reasons.append(f"{metrics.clipped_high_pct:.1%} of pixels clipped to white")
    if metrics.mean_luminance < luminance_min:
        reasons.append(f"mean luminance {metrics.mean_luminance:.1f} below {luminance_min}")
    if metrics.mean_luminance > luminance_max:
        reasons.append(f"mean luminance {metrics.mean_luminance:.1f} above {luminance_max}")
    return (len(reasons) > 0, reasons)


def is_blurry(score: float, threshold: float) -> bool:
    return score < threshold
