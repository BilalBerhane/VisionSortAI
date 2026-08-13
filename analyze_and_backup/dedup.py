"""Duplicate detection via perceptual hashing.

Runs entirely on the Pi, before any photo is sent to the cloud AI agent --
this is a deliberate cost/latency optimization: don't pay for a vision-model
call on a photo that's about to be deleted as a duplicate anyway.

Method: 64-bit perceptual hash (phash), compared with Hamming distance.
Threshold of 8 (out of 64 bits, ~12% difference) is the standard starting
point used by image-dedup tooling for "near-identical" images -- burst shots
of the same subject a fraction of a second apart. Distances above that are
treated as genuinely different photos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import imagehash
from PIL import Image


def compute_phash(path: Path) -> imagehash.ImageHash:
    with Image.open(path) as img:
        return imagehash.phash(img)


def hamming_distance(a: imagehash.ImageHash, b: imagehash.ImageHash) -> int:
    return a - b  # imagehash overloads subtraction as Hamming distance


@dataclass
class IndexEntry:
    path: str
    phash: imagehash.ImageHash
    blur_score: float


@dataclass
class DuplicateIndex:
    """Tracks perceptual hashes seen so far in this SD-card session.

    Duplicate resolution uses blur_score (a cheap local metric) rather than
    the agent's quality_score, so the loser in a duplicate pair never needs
    an agent call at all.
    """

    threshold: int = 8
    _entries: list[IndexEntry] = field(default_factory=list)

    def find_duplicate(self, phash: imagehash.ImageHash) -> IndexEntry | None:
        for entry in self._entries:
            if hamming_distance(phash, entry.phash) <= self.threshold:
                return entry
        return None

    def add(self, path: Path, phash: imagehash.ImageHash, blur_score: float) -> IndexEntry:
        entry = IndexEntry(path=str(path), phash=phash, blur_score=blur_score)
        self._entries.append(entry)
        return entry

    def replace(self, old: IndexEntry, path: Path, phash: imagehash.ImageHash, blur_score: float) -> IndexEntry:
        self._entries.remove(old)
        return self.add(path, phash, blur_score)


@dataclass
class DuplicateResolution:
    keep_path: str
    delete_path: str | None  # None means the new candidate replaces the index entry in place


def resolve_duplicate(existing: IndexEntry, candidate_path: Path, candidate_blur_score: float) -> DuplicateResolution:
    """Sharper photo (higher Laplacian-variance blur_score) wins."""
    if candidate_blur_score > existing.blur_score:
        return DuplicateResolution(keep_path=str(candidate_path), delete_path=existing.path)
    return DuplicateResolution(keep_path=existing.path, delete_path=str(candidate_path))
