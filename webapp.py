#!/usr/bin/env python3
"""Local web interface -- lets someone who just inserted an SD/USB card see
what happened: which photos were kept, which documents were found and what
they say, and basic run stats. Reads straight from local_backup/, refreshed
on every request (no caching), so it always reflects the latest pipeline run.

Run:
    python webapp.py
Then visit http://<pi-hostname>.local:5000 on any device on the same network
(see generate_qr.py for a printable QR code pointing at that address).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_from_directory, url_for

from analyze_and_backup.config import CONFIG
from analyze_and_backup.results import (
    filter_by_kind,
    load_latest_records,
    search_documents,
    summarize,
)

app = Flask(__name__)


def backup_dir() -> Path:
    return Path(CONFIG.local_backup_dir)


def stop_file() -> Path:
    return Path(CONFIG.stop_file_path)


def is_run_active() -> bool:
    """Checks (read-only, no elevated privileges needed) whether a
    analyze-and-backup@*.service instance is currently running. Degrades to
    "unknown -> False" if systemctl isn't available at all, e.g. when
    running this on a dev machine instead of the actual Pi."""
    try:
        proc = subprocess.run(
            ["systemctl", "list-units", "analyze-and-backup@*.service",
             "--state=running,activating", "--no-legend", "--plain"],
            capture_output=True, text=True, timeout=5,
        )
        return bool(proc.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _safe_media_path(folder: Path, filename: str) -> Path:
    """Resolve filename under folder, refusing any path-traversal attempt."""
    target = (folder / filename).resolve()
    if not target.is_relative_to(folder.resolve()):
        abort(403)
    return target


@app.route("/")
def dashboard():
    records = load_latest_records(backup_dir())
    summary = summarize(records)
    recent_photos = filter_by_kind(records, "photo")[:12]
    recent_documents = filter_by_kind(records, "document")[:6]
    run_active = is_run_active()
    return render_template(
        "dashboard.html",
        summary=summary,
        recent_photos=recent_photos,
        recent_documents=recent_documents,
        run_active=run_active,
        stop_requested=run_active and stop_file().exists(),
    )


@app.route("/control/stop", methods=["POST"])
def control_stop():
    """Drops a signal file the running pipeline checks between photos and
    halts on -- see Pipeline.stop_requested() in pipeline.py. We deliberately
    don't call systemctl/sudo from here: touching a file needs no elevated
    privileges, so the web app never needs root."""
    sf = stop_file()
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.touch(exist_ok=True)
    return redirect(url_for("dashboard"))


@app.route("/photos")
def photos():
    records = load_latest_records(backup_dir())
    all_photos = filter_by_kind(records, "photo")
    return render_template("photos.html", photos=all_photos)


@app.route("/documents")
def documents():
    records = load_latest_records(backup_dir())
    query = request.args.get("q", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    results = search_documents(records, query=query, date_from=date_from, date_to=date_to)
    return render_template(
        "documents.html",
        documents=results,
        query=query,
        date_from=date_from,
        date_to=date_to,
    )


@app.route("/activity")
def activity():
    """Deletions + uncertain items -- the audit trail."""
    records = load_latest_records(backup_dir())
    deletions = filter_by_kind(records, "deletion")
    uncertain = filter_by_kind(records, "uncertain")
    return render_template("activity.html", deletions=deletions, uncertain=uncertain)


@app.route("/media/photos/<path:filename>")
def media_photo(filename):
    folder = backup_dir() / "photos"
    _safe_media_path(folder, filename)
    return send_from_directory(folder, filename)


@app.route("/media/documents/<path:filename>")
def media_document(filename):
    folder = backup_dir() / "documents"
    _safe_media_path(folder, filename)
    return send_from_directory(folder, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
