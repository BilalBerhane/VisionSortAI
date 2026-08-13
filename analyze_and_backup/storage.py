"""Step 6-7 of the pipeline: backup / persistence.

BackupStore is the interface the pipeline codes against. Two implementations:
  - AzureBackupStore: uploads approved photos/documents to Azure Blob
    Storage. The Cosmos DB write (searchable metadata index) is the
    partner's Azure-infrastructure territory -- this class exposes a single
    clearly-marked integration point (`_write_index_record`) rather than
    assuming a particular Cosmos DB client/schema, and falls back to an
    append-only local JSON-lines log until that's wired up.
  - LocalBackupStore: pure local-filesystem implementation for dev/testing
    without any Azure account at all.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


@dataclass
class BackupRecord:
    kind: str  # "photo" | "document" | "deletion" | "uncertain"
    source_path: str
    stored_at: str  # ISO timestamp
    metadata: dict


class BackupStore(Protocol):
    def upload_photo(self, path: Path, metadata: dict) -> BackupRecord: ...
    def upload_document_record(self, path: Path, metadata: dict) -> BackupRecord: ...
    def log_deletion(self, path: Path, reason: str) -> BackupRecord: ...
    def log_uncertain(self, path: Path, reason: str) -> BackupRecord: ...


class LocalBackupStore:
    """Writes files into local_backup/{photos,documents}/ and appends every
    action to local_backup/index.jsonl. Used for tests and offline dev runs."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        (self.base_dir / "photos").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "documents").mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_dir / "index.jsonl"

    def _append_index(self, record: BackupRecord) -> None:
        with open(self.index_path, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def upload_photo(self, path: Path, metadata: dict) -> BackupRecord:
        path = Path(path)
        dest = self.base_dir / "photos" / path.name
        shutil.copy2(path, dest)
        record = BackupRecord("photo", str(path), self._now(), metadata)
        self._append_index(record)
        return record

    def upload_document_record(self, path: Path, metadata: dict) -> BackupRecord:
        path = Path(path)
        dest = self.base_dir / "documents" / path.name
        shutil.copy2(path, dest)
        record = BackupRecord("document", str(path), self._now(), metadata)
        self._append_index(record)
        return record

    def log_deletion(self, path: Path, reason: str) -> BackupRecord:
        record = BackupRecord("deletion", str(path), self._now(), {"reason": reason})
        self._append_index(record)
        return record

    def log_uncertain(self, path: Path, reason: str) -> BackupRecord:
        record = BackupRecord("uncertain", str(path), self._now(), {"reason": reason})
        self._append_index(record)
        return record


class AzureBackupStore:
    """Uploads to Azure Blob Storage. Cosmos DB indexing is stubbed --
    replace _write_index_record with the team's Cosmos DB client call."""

    def __init__(self, connection_string: str, container: str):
        from azure.storage.blob import BlobServiceClient

        self._client = BlobServiceClient.from_connection_string(connection_string)
        self._container = container
        self._container_client = self._client.get_container_client(container)
        try:
            self._container_client.create_container()
        except Exception:
            pass  # already exists

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _upload_blob(self, path: Path, blob_prefix: str) -> str:
        path = Path(path)
        blob_name = f"{blob_prefix}/{path.name}"
        with open(path, "rb") as data:
            self._container_client.upload_blob(name=blob_name, data=data, overwrite=True)
        return self._container_client.get_blob_client(blob_name).url

    def _write_index_record(self, record: BackupRecord) -> None:
        # TODO(teammate): replace with the real Cosmos DB write.
        # Keeping a local fallback log means this module works end-to-end
        # (and is testable) before the Cosmos DB integration lands.
        fallback = Path("azure_index_fallback.jsonl")
        with open(fallback, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def upload_photo(self, path: Path, metadata: dict) -> BackupRecord:
        url = self._upload_blob(path, "photos")
        record = BackupRecord("photo", str(path), self._now(), {**metadata, "blob_url": url})
        self._write_index_record(record)
        return record

    def upload_document_record(self, path: Path, metadata: dict) -> BackupRecord:
        url = self._upload_blob(path, "documents")
        record = BackupRecord("document", str(path), self._now(), {**metadata, "blob_url": url})
        self._write_index_record(record)
        return record

    def log_deletion(self, path: Path, reason: str) -> BackupRecord:
        record = BackupRecord("deletion", str(path), self._now(), {"reason": reason})
        self._write_index_record(record)
        return record

    def log_uncertain(self, path: Path, reason: str) -> BackupRecord:
        record = BackupRecord("uncertain", str(path), self._now(), {"reason": reason})
        self._write_index_record(record)
        return record
