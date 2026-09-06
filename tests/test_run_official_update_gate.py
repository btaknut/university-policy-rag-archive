from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_official_update_gate import build_pipeline_commands, verify_gate_versions


def write_version(tmp_path: Path, version: dict) -> None:
    (tmp_path / "metadata").mkdir(exist_ok=True)
    (tmp_path / "metadata/versions.jsonl").write_text(
        json.dumps(version) + "\n", encoding="utf-8"
    )


def batch(version_id: str, digest: str) -> dict:
    return {"records": [{"version_id": version_id, "sha256": digest}]}


def test_pipeline_command_order(tmp_path: Path):
    commands = build_pipeline_commands(
        tmp_path,
        tmp_path / "batch.json",
        tmp_path / "downloads",
        tmp_path / "unhwp",
        force_markdown=True,
    )
    rendered = [" ".join(command) for command in commands]
    assert "apply_official_updates.py" in rendered[0]
    assert "--apply" in rendered[0]
    assert "convert_hwp_portable.py" in rendered[1]
    assert "--force" in rendered[1]
    assert "build_versions.py" in rendered[2]
    assert "build_chunks.py" in rendered[3]
    assert "build_catalog.py" in rendered[4]
    assert "validate_corpus.py" in rendered[5]
    assert rendered[6].endswith("-m pytest -q")


def test_verify_gate_versions_accepts_portable_markdown(tmp_path: Path):
    version_id = "VER-20260818-abcd1234"
    source_bytes = b"hwp"
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    source = tmp_path / "sources/raw/guidelines/source.hwp"
    source.parent.mkdir(parents=True)
    source.write_bytes(source_bytes)
    normalized = tmp_path / "corpus/normalized/guidelines/GDL-example/version.md"
    normalized.parent.mkdir(parents=True)
    normalized.write_text("정상 한글 Markdown", encoding="utf-8")
    version = {
        "version_id": version_id,
        "source_file": source.relative_to(tmp_path).as_posix(),
        "sha256": source_sha,
        "is_current": True,
        "normalized_file": normalized.relative_to(tmp_path).as_posix(),
        "portable_conversion_status": "success",
        "portable_extraction_tool": "unhwp",
        "portable_extraction_version": "0.9.1",
        "portable_markdown_sha256": hashlib.sha256(normalized.read_bytes()).hexdigest(),
        "portable_text_chars": 300,
        "portable_hangul_chars": 200,
        "portable_hangul_ratio": 0.66,
        "portable_replacement_chars": 0,
        "pdf_conversion_status": "not_generated_portable",
    }
    write_version(tmp_path, version)
    results = verify_gate_versions(tmp_path, batch(version_id, source_sha))
    checks = results[0]["checks"]
    assert checks["portable_markdown_complete"] is True
    assert checks["native_pdf_complete"] is False
    assert checks["derivative_complete"] is True


def test_verify_gate_versions_accepts_native_pdf(tmp_path: Path):
    version_id = "VER-20260818-abcd1234"
    source_bytes = b"hwp"
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    source = tmp_path / "sources/raw/guidelines/source.hwp"
    source.parent.mkdir(parents=True)
    source.write_bytes(source_bytes)
    normalized = tmp_path / "corpus/normalized/guidelines/GDL-example/version.md"
    normalized.parent.mkdir(parents=True)
    normalized.write_text("text", encoding="utf-8")
    pdf = tmp_path / "corpus/pdf/guidelines/GDL-example/version.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"pdf")
    version = {
        "version_id": version_id,
        "source_file": source.relative_to(tmp_path).as_posix(),
        "sha256": source_sha,
        "is_current": True,
        "normalized_file": normalized.relative_to(tmp_path).as_posix(),
        "pdf_conversion_status": "success",
        "pdf_relative_path": pdf.relative_to(tmp_path).as_posix(),
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "pdf_pages": 1,
    }
    write_version(tmp_path, version)
    results = verify_gate_versions(tmp_path, batch(version_id, source_sha))
    assert results[0]["checks"]["native_pdf_complete"] is True
    assert results[0]["checks"]["derivative_complete"] is True


def test_verify_gate_versions_rejects_missing_derivative(tmp_path: Path):
    version_id = "VER-20260818-abcd1234"
    source_bytes = b"hwp"
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    source = tmp_path / "source.hwp"
    source.write_bytes(source_bytes)
    version = {
        "version_id": version_id,
        "source_file": source.name,
        "sha256": source_sha,
        "is_current": True,
        "pdf_conversion_status": "not_generated_portable",
        "normalized_file": None,
    }
    write_version(tmp_path, version)
    with pytest.raises(RuntimeError, match="최종 Gate 실패"):
        verify_gate_versions(tmp_path, batch(version_id, source_sha))
