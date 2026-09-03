from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_official_update_gate import build_pipeline_commands, verify_gate_versions


def test_pipeline_command_order(tmp_path: Path):
    commands = build_pipeline_commands(
        tmp_path, tmp_path / "batch.json", tmp_path / "downloads", force_pdf=True
    )
    rendered = [" ".join(command) for command in commands]
    assert "apply_official_updates.py" in rendered[0]
    assert "--apply" in rendered[0]
    assert "convert_hwp_to_pdf.ps1" in rendered[1]
    assert "-Force" in rendered[1]
    assert "index_pdf_derivatives.py" in rendered[2]
    assert "build_versions.py" in rendered[3]
    assert "build_chunks.py" in rendered[4]
    assert "build_catalog.py" in rendered[5]
    assert "validate_corpus.py" in rendered[6]
    assert rendered[7].endswith("-m pytest -q")


def test_verify_gate_versions(tmp_path: Path):
    (tmp_path / "metadata").mkdir()
    (tmp_path / "corpus/pdf/guidelines/GDL-example").mkdir(parents=True)
    (tmp_path / "corpus/normalized/guidelines/GDL-example").mkdir(parents=True)
    pdf = "corpus/pdf/guidelines/GDL-example/VER-20260818-abcd1234.pdf"
    normalized = "corpus/normalized/guidelines/GDL-example/VER-20260818-abcd1234.md"
    (tmp_path / pdf).write_bytes(b"pdf")
    (tmp_path / normalized).write_text("text", encoding="utf-8")
    version = {
        "version_id": "VER-20260818-abcd1234",
        "sha256": "a" * 64,
        "is_current": True,
        "pdf_conversion_status": "success",
        "pdf_relative_path": pdf,
        "normalized_file": normalized,
    }
    (tmp_path / "metadata/versions.jsonl").write_text(
        json.dumps(version) + "\n", encoding="utf-8"
    )
    batch = {
        "records": [
            {
                "version_id": "VER-20260818-abcd1234",
                "sha256": "a" * 64,
            }
        ]
    }
    results = verify_gate_versions(tmp_path, batch)
    assert all(results[0]["checks"].values())


def test_verify_gate_versions_rejects_missing_pdf(tmp_path: Path):
    (tmp_path / "metadata").mkdir()
    version = {
        "version_id": "VER-20260818-abcd1234",
        "sha256": "a" * 64,
        "is_current": True,
        "pdf_conversion_status": "pending",
        "pdf_relative_path": None,
        "normalized_file": None,
    }
    (tmp_path / "metadata/versions.jsonl").write_text(
        json.dumps(version) + "\n", encoding="utf-8"
    )
    batch = {
        "records": [
            {
                "version_id": "VER-20260818-abcd1234",
                "sha256": "a" * 64,
            }
        ]
    }
    with pytest.raises(RuntimeError, match="최종 Gate 실패"):
        verify_gate_versions(tmp_path, batch)
