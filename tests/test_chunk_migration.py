from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_chunks
from build_chunks import generate_incremental, rows_sha256
from chunk_migration import build_migration_map, validate_mapping_references, write_and_validate


def base_chunk(chunk_id: str, version_id: str, text: str, index: int = 0) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": "REG-test",
        "version_id": version_id,
        "section_path": "제1장",
        "article_no": "제1조",
        "paragraph_no": None,
        "item_no": None,
        "appendix_no": None,
        "chunk_index": index,
        "text": text,
    }


def prepare_repo(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config/chunking.yaml").write_text(
        "target_tokens: 700\nmax_tokens: 1200\noverlap_tokens: 80\n", encoding="utf-8"
    )
    (tmp_path / "metadata").mkdir()
    document = {"document_id": "REG-test", "latest_version_id": "VER-new"}
    versions = [
        {
            "version_id": "VER-old", "document_id": "REG-test", "version_group_id": "REG-test",
            "document_type": "regulation", "title": "시험 규정", "access_level": "public",
            "normalized_file": "corpus/old.md", "source_file": "sources/old.hwp", "sha256": "a" * 64,
            "is_current": False, "current_status": "historical", "revision_date": "2020-01-01",
        },
        {
            "version_id": "VER-new", "document_id": "REG-test", "version_group_id": "REG-test",
            "document_type": "regulation", "title": "시험 규정", "access_level": "public",
            "normalized_file": "corpus/new.md", "source_file": "sources/new.hwp", "sha256": "b" * 64,
            "is_current": True, "current_status": "current", "revision_date": "2026-01-01",
        },
    ]
    (tmp_path / "metadata/documents.jsonl").write_text(json.dumps(document) + "\n", encoding="utf-8")
    (tmp_path / "metadata/versions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in versions), encoding="utf-8")
    (tmp_path / "corpus").mkdir()
    (tmp_path / "corpus/old.md").write_text("제1조(목적) 기존 본문", encoding="utf-8")
    (tmp_path / "corpus/new.md").write_text("제1조(목적) 신규 본문", encoding="utf-8")


def test_incremental_preserves_existing_id_and_text_and_adds_new_version(tmp_path: Path):
    prepare_repo(tmp_path)
    existing = base_chunk("CHK-legacy", "VER-old", "제1조(목적) 기존 경계 본문")
    result = generate_incremental([existing], tmp_path)
    old = next(row for row in result if row["version_id"] == "VER-old")
    new = [row for row in result if row["version_id"] == "VER-new"]
    assert old["chunk_id"] == "CHK-legacy"
    assert old["text"] == existing["text"]
    assert old["is_latest_version"] is False
    assert new and all(row["is_latest_version"] is True for row in new)


def test_incremental_rejects_orphan_reference(tmp_path: Path):
    prepare_repo(tmp_path)
    with pytest.raises(RuntimeError, match="알 수 없는 version_id"):
        generate_incremental([base_chunk("CHK-orphan", "VER-missing", "본문")], tmp_path)


def test_rows_hash_is_deterministic():
    rows = [base_chunk("CHK-1", "VER-1", "본문")]
    assert rows_sha256(rows) == rows_sha256([dict(rows[0])])


@pytest.mark.parametrize("mode", ["preview", "rechunk"])
def test_canonical_rechunk_requires_explicit_safe_path_or_approval(tmp_path: Path, monkeypatch, mode: str):
    canonical = tmp_path / "rag/chunks.jsonl"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_chunks.py", "--repo-root", str(tmp_path), "--mode", mode, "--output", str(canonical)],
    )
    expected = "preview 모드" if mode == "preview" else "--allow-id-changes"
    with pytest.raises(RuntimeError, match=expected):
        build_chunks.main()


def test_mapping_covers_unchanged_removed_new_and_validates(tmp_path: Path):
    old = [base_chunk("CHK-same", "VER-1", "같은 본문"), base_chunk("CHK-old", "VER-2", "사라진 본문")]
    new = [base_chunk("CHK-same", "VER-1", "같은 본문"), base_chunk("CHK-new", "VER-3", "새 본문")]
    value = build_migration_map(old, new)
    assert value["summary"]["retained_ids"] == 1
    assert value["summary"]["removed_ids"] == 1
    assert value["summary"]["new_ids"] == 1
    output = tmp_path / "map.json"
    write_and_validate(output, value, ROOT)
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == "1.0"
    validate_mapping_references(value, old, new)
