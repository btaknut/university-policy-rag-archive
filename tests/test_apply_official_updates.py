from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from apply_official_updates import update_metadata, validate_batch


def fixture_rows(payload: bytes):
    digest = hashlib.sha256(payload).hexdigest()
    documents = [
        {
            "document_id": "GDL-example",
            "document_type": "guideline",
            "title": "예시 지침",
            "version_group_id": "VG-example",
            "authority_level": "university_guideline",
            "department": "예시부서",
            "is_current": True,
            "current_status": "confirmed",
            "latest_version_id": "VER-20240101-oldhash0",
            "enactment_date": None,
        }
    ]
    versions = [
        {
            "version_id": "VER-20240101-oldhash0",
            "document_id": "GDL-example",
            "revision_date": "2024-01-01",
            "effective_date": "2024-01-01",
            "sha256": "0" * 64,
            "is_current": True,
            "current_status": "confirmed",
            "next_version_id": None,
        }
    ]
    batch = {
        "records": [
            {
                "source_id": "sanhak_guidelines",
                "source_record_id": "record:file:1",
                "document_id": "GDL-example",
                "document_type": "guideline",
                "title": "예시 지침",
                "department": "예시부서",
                "revision_date": "2026-08-18",
                "effective_date": "2026-08-18",
                "previous_version_id": "VER-20240101-oldhash0",
                "attachment_filename": "예시 지침.hwp",
                "downloaded_filename": "downloaded.hwp",
                "source_page_url": "https://example.test/detail",
                "attachment_url": "https://example.test/download",
                "file_size": len(payload),
                "sha256": digest,
                "captured_at": "2026-09-03",
            }
        ]
    }
    return batch, documents, versions


def test_validate_and_update_official_batch(tmp_path: Path):
    payload = b"HWP fixture bytes"
    (tmp_path / "downloaded.hwp").write_bytes(payload)
    batch, documents, versions = fixture_rows(payload)

    prepared = validate_batch(batch, tmp_path, documents, versions)
    assert prepared[0]["version_id"].startswith("VER-20260818-")
    assert prepared[0]["archive_file"].as_posix().startswith(
        "sources/raw/guidelines/official/sanhak_guidelines/"
    )

    documents, versions, manifest = update_metadata(
        prepared, documents, versions, [], "2026-09-03T00:00:00+00:00"
    )
    old, new = versions
    assert old["is_current"] is False
    assert old["next_version_id"] == new["version_id"]
    assert new["previous_version_id"] == old["version_id"]
    assert new["pdf_conversion_status"] == "not_generated_portable"
    assert new["text_extraction_status"] == "pending_portable_hwp"
    assert documents[0]["latest_version_id"] == new["version_id"]
    assert manifest[0]["origin_type"] == "official_web"


def test_validate_rejects_hash_mismatch(tmp_path: Path):
    payload = b"expected"
    (tmp_path / "downloaded.hwp").write_bytes(b"different")
    batch, documents, versions = fixture_rows(payload)

    with pytest.raises(ValueError, match="SHA-256"):
        validate_batch(batch, tmp_path, documents, versions)


def test_validate_rejects_stale_previous_version(tmp_path: Path):
    payload = b"expected"
    (tmp_path / "downloaded.hwp").write_bytes(payload)
    batch, documents, versions = fixture_rows(payload)
    batch["records"][0]["previous_version_id"] = "VER-stale"

    with pytest.raises(ValueError, match="기준 버전 불일치"):
        validate_batch(batch, tmp_path, documents, versions)
