from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from convert_hwp_portable import analyze_markdown, quality_errors, sha256_file


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_quality_gate_accepts_korean_articles():
    body = "예시 운영 지침\n제1조(목적) " + "이 지침의 목적과 적용 범위를 정한다. " * 12
    metrics = analyze_markdown(body, "예시 운영 지침")
    assert metrics["article_count"] == 1
    assert metrics["title_present"] is True
    assert quality_errors(metrics) == []


def test_quality_gate_rejects_garbled_text():
    metrics = analyze_markdown("example \ufffd" * 30, "예시 운영 지침")
    errors = quality_errors(metrics)
    assert any("한글" in error for error in errors)
    assert any("replacement" in error for error in errors)
    assert any("제목" in error for error in errors)


def test_portable_conversion_updates_markdown_and_metadata(tmp_path: Path):
    source_bytes = b"fake hwp used by the fake converter"
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    source_rel = "sources/raw/guidelines/source.hwp"
    source = tmp_path / source_rel
    source.parent.mkdir(parents=True)
    source.write_bytes(source_bytes)

    document = {
        "document_id": "GDL-example",
        "document_type": "guideline",
        "title": "예시 운영 지침",
        "issuing_organization": "국립한국교통대학교",
        "latest_version_id": "VER-20260818-" + source_sha[:8],
    }
    version_id = document["latest_version_id"]
    version = {
        "version_id": version_id,
        "document_id": document["document_id"],
        "document_type": "guideline",
        "title": document["title"],
        "source_file": source_rel,
        "sha256": source_sha,
        "is_current": True,
        "current_status": "confirmed",
        "access_level": "public",
        "department": "예시부서",
    }
    write_jsonl(tmp_path / "metadata/documents.jsonl", [document])
    write_jsonl(tmp_path / "metadata/versions.jsonl", [version])
    batch = {
        "records": [
            {
                "version_id": version_id,
                "sha256": source_sha,
            }
        ]
    }
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(json.dumps(batch), encoding="utf-8")

    fake = tmp_path / "unhwp"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "if sys.argv[1] == 'version':\n"
        "    print('unhwp 0.9.1')\n"
        "else:\n"
        "    output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "    body = '예시 운영 지침\\n제1조(목적) ' + '이 지침의 목적과 적용 범위를 정한다. ' * 15\n"
        "    output.write_text(body, encoding='utf-8')\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/convert_hwp_portable.py"),
            "--repo-root",
            str(tmp_path),
            "--batch",
            str(batch_path),
            "--unhwp",
            str(fake),
        ],
        check=True,
    )

    versions = [json.loads(line) for line in (tmp_path / "metadata/versions.jsonl").read_text(encoding="utf-8").splitlines()]
    updated = versions[0]
    normalized = tmp_path / updated["normalized_file"]
    assert normalized.is_file()
    assert updated["portable_conversion_status"] == "success"
    assert updated["portable_extraction_version"] == "0.9.1"
    assert updated["portable_markdown_sha256"] == sha256_file(normalized)
    assert updated["pdf_conversion_status"] == "not_generated_portable"
    assert "extraction_method: \"unhwp-0.9.1\"" in normalized.read_text(encoding="utf-8")
