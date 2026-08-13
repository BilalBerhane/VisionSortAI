"""Step 2 of the pipeline: extract per-photo metadata with exiftool.

exiftool gives us EXIF fields (timestamp, camera model, GPS) and can hash file
bytes, but byte hashing only catches exact duplicate files. Near-duplicates
(burst shots) are NOT exact byte copies, so duplicate detection instead uses a
perceptual hash of the pixel content -- see dedup.py.

Requires the exiftool CLI to be installed on the device running this code:
    sudo apt install libimage-exiftool-perl   # Raspberry Pi OS / Debian
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


class ExifToolNotFoundError(RuntimeError):
    def __init__(self, binary: str):
        super().__init__(
            f"exiftool binary '{binary}' was not found on PATH. Install it with "
            "'sudo apt install libimage-exiftool-perl' (Raspberry Pi OS / Debian) "
            "or set EXIFTOOL_BINARY to the correct path."
        )


@dataclass
class PhotoMetadata:
    path: str
    timestamp: str | None
    camera_model: str | None
    gps_latitude: float | None
    gps_longitude: float | None
    width: int | None
    height: int | None
    file_sha256: str
    raw: dict


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_metadata(path: Path, exiftool_binary: str = "exiftool", timeout: float = 30.0) -> PhotoMetadata:
    """Run `exiftool -j <path>` and parse the result into PhotoMetadata.

    Raises ExifToolNotFoundError if the binary isn't installed, ValueError if
    exiftool ran but returned no data for the file, and TimeoutError if the
    call doesn't finish within `timeout` seconds.

    stdin is explicitly closed (subprocess.DEVNULL) as a safety net against
    exiftool ever blocking waiting to read from stdin instead of just running
    and exiting.
    """
    path = Path(path)
    try:
        proc = subprocess.run(
            # -n: numeric output in general; -c "%.6f": force GPS coordinates
            # specifically to print as clean signed decimal degrees (without
            # this, GPS values can come back in a DMS-ish format or under a
            # tag name that doesn't match a plain "-n" numeric conversion,
            # which is why gps_latitude/longitude were coming back as None
            # even on photos confirmed to have GPS EXIF data).
            [exiftool_binary, "-j", "-n", "-c", "%.6f", str(path)],
            capture_output=True,
            text=True,
            check=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ExifToolNotFoundError(exiftool_binary) from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"exiftool failed on {path}: {exc.stderr.strip()}") from exc
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(
            f"exiftool did not respond within {timeout}s on {path}. "
            "Try running it directly (e.g. `exiftool -j -n <file>`) to check "
            "whether it's hanging outside this pipeline too."
        ) from exc

    records = json.loads(proc.stdout)
    if not records:
        raise ValueError(f"exiftool returned no metadata for {path}")
    raw = records[0]

    return PhotoMetadata(
        path=str(path),
        timestamp=raw.get("DateTimeOriginal") or raw.get("CreateDate") or raw.get("ModifyDate"),
        camera_model=raw.get("Model"),
        gps_latitude=_parse_gps(raw, "GPSLatitude"),
        gps_longitude=_parse_gps(raw, "GPSLongitude"),
        width=raw.get("ImageWidth"),
        height=raw.get("ImageHeight"),
        file_sha256=_sha256_of_file(path),
        raw=raw,
    )


def _parse_gps(raw: dict, key: str) -> float | None:
    """GPS values can show up under a couple of different keys/formats
    depending on exiftool version and whether the tag is duplicated across
    groups (e.g. plain "GPSLatitude" vs "Composite:GPSLatitude"), and with
    -c formatting they come back as strings like "51.051867" rather than
    native floats. Check the likely variants and coerce safely instead of
    silently returning None on a formatting mismatch.
    """
    for candidate_key in (key, f"Composite{key}", f"EXIF{key}"):
        value = raw.get(candidate_key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None
