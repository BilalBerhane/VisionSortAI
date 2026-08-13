import json
import subprocess

import pytest

from analyze_and_backup import metadata as metadata_module
from analyze_and_backup.metadata import ExifToolNotFoundError, extract_metadata


SAMPLE_EXIFTOOL_JSON = [
    {
        "SourceFile": "photo.jpg",
        "DateTimeOriginal": "2026:08:12 14:30:00",
        "Model": "Raspberry Pi Camera Module 3",
        "GPSLatitude": 51.0447,
        "GPSLongitude": -114.0719,
        "ImageWidth": 4608,
        "ImageHeight": 2592,
    }
]


def test_extract_metadata_parses_exiftool_output(tmp_path, monkeypatch):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake jpeg bytes")

    def fake_run(cmd, capture_output, text, check, stdin=None, timeout=None):
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(SAMPLE_EXIFTOOL_JSON), stderr="")

    monkeypatch.setattr(metadata_module.subprocess, "run", fake_run)

    result = extract_metadata(photo)

    assert result.timestamp == "2026:08:12 14:30:00"
    assert result.camera_model == "Raspberry Pi Camera Module 3"
    assert result.gps_latitude == pytest.approx(51.0447)
    assert result.width == 4608
    assert result.height == 2592
    assert len(result.file_sha256) == 64  # sha256 hex digest length


def test_extract_metadata_parses_gps_when_formatted_as_string(tmp_path, monkeypatch):
    """exiftool with -c "%.6f" prints coordinates as strings like "51.044700",
    not native floats -- make sure that still comes through as a float."""
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake jpeg bytes")

    sample = [{**SAMPLE_EXIFTOOL_JSON[0], "GPSLatitude": "51.044700", "GPSLongitude": "-114.071900"}]

    def fake_run(cmd, capture_output, text, check, stdin=None, timeout=None):
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(sample), stderr="")

    monkeypatch.setattr(metadata_module.subprocess, "run", fake_run)
    result = extract_metadata(photo)

    assert result.gps_latitude == pytest.approx(51.0447)
    assert result.gps_longitude == pytest.approx(-114.0719)


def test_extract_metadata_falls_back_to_composite_gps_key(tmp_path, monkeypatch):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake jpeg bytes")

    sample = [dict(SAMPLE_EXIFTOOL_JSON[0])]
    del sample[0]["GPSLatitude"]
    del sample[0]["GPSLongitude"]
    sample[0]["CompositeGPSLatitude"] = 51.0447
    sample[0]["CompositeGPSLongitude"] = -114.0719

    def fake_run(cmd, capture_output, text, check, stdin=None, timeout=None):
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(sample), stderr="")

    monkeypatch.setattr(metadata_module.subprocess, "run", fake_run)
    result = extract_metadata(photo)

    assert result.gps_latitude == pytest.approx(51.0447)
    assert result.gps_longitude == pytest.approx(-114.0719)


def test_extract_metadata_gps_none_when_photo_has_no_gps(tmp_path, monkeypatch):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake jpeg bytes")

    sample = [dict(SAMPLE_EXIFTOOL_JSON[0])]
    del sample[0]["GPSLatitude"]
    del sample[0]["GPSLongitude"]

    def fake_run(cmd, capture_output, text, check, stdin=None, timeout=None):
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(sample), stderr="")

    monkeypatch.setattr(metadata_module.subprocess, "run", fake_run)
    result = extract_metadata(photo)

    assert result.gps_latitude is None
    assert result.gps_longitude is None


def test_extract_metadata_raises_clear_error_when_binary_missing(tmp_path, monkeypatch):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake jpeg bytes")

    def fake_run(cmd, capture_output, text, check, stdin=None, timeout=None):
        raise FileNotFoundError()

    monkeypatch.setattr(metadata_module.subprocess, "run", fake_run)

    with pytest.raises(ExifToolNotFoundError, match="exiftool"):
        extract_metadata(photo)


def test_extract_metadata_raises_on_empty_result(tmp_path, monkeypatch):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"fake jpeg bytes")

    def fake_run(cmd, capture_output, text, check, stdin=None, timeout=None):
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

    monkeypatch.setattr(metadata_module.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="no metadata"):
        extract_metadata(photo)
