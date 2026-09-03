from __future__ import annotations

import hashlib
from email.message import Message
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from download_official_batch import download_batch


class FakeClient:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.visited = []

    def text(self, url: str):
        self.visited.append(url)
        return "page", Message()

    def download(self, url: str, target_dir: Path, extra_headers=None, filename=None):
        assert extra_headers == {"Referer": "https://example.test/detail"}
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        target.write_bytes(self.payload)
        return target, hashlib.sha256(self.payload).hexdigest(), Message()


def batch_for(payload: bytes) -> dict:
    return {
        "records": [
            {
                "version_id": "VER-20260901-abcd1234",
                "source_page_url": "https://example.test/detail",
                "attachment_url": "https://example.test/download",
                "downloaded_filename": "verified.hwp",
                "file_size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        ]
    }


def test_download_batch_visits_page_and_verifies_file(tmp_path: Path):
    payload = b"official bytes"
    client = FakeClient(payload)
    results = download_batch(batch_for(payload), tmp_path, client)
    assert results[0]["status"] == "verified"
    assert client.visited == ["https://example.test/detail"]
    assert (tmp_path / "verified.hwp").read_bytes() == payload


def test_download_batch_rejects_hash_mismatch(tmp_path: Path):
    batch = batch_for(b"expected")
    with pytest.raises(RuntimeError, match="SHA-256"):
        download_batch(batch, tmp_path, FakeClient(b"different"))
