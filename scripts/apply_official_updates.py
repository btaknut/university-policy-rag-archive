"""검토가 끝난 공식 원천 원문을 기존 코퍼스에 증분 반영한다.

기본 동작은 계획 검증만 수행한다. ``--apply``를 지정해야 raw 원본과
metadata 3종을 변경한다. HWP PDF 변환·Markdown·청크 생성은 기존 Windows
파이프라인에서 후속 실행한다.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import unquote_plus


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    temp.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_component(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value).strip("._")
    return cleaned[:96] or "record"


def find_download(downloads_dir: Path, record: dict[str, Any]) -> Path | None:
    names: list[str] = []
    for key in ("downloaded_filename", "attachment_filename"):
        name = record.get(key)
        if name and name not in names:
            names.append(name)
        decoded = unquote_plus(name) if name else None
        if decoded and decoded not in names:
            names.append(decoded)
    for name in names:
        candidate = downloads_dir / name
        if candidate.is_file():
            return candidate
    expected = record.get("sha256")
    if expected:
        for candidate in sorted(downloads_dir.glob("*")):
            if candidate.is_file() and sha256_file(candidate) == expected:
                return candidate
    return None


def canonical_raw_path(record: dict[str, Any]) -> Path:
    bucket = "regulations" if record["document_type"] == "regulation" else "guidelines"
    filename = record.get("attachment_filename") or record.get("downloaded_filename")
    if not filename:
        raise ValueError("attachment filename이 없습니다")
    return Path("sources/raw") / bucket / "official" / safe_component(
        record["source_id"]
    ) / safe_component(record["source_record_id"]) / filename


def expected_version_id(record: dict[str, Any]) -> str:
    date = re.sub(
        r"[^0-9]", "", record.get("revision_date") or record.get("effective_date") or ""
    ) or "unknown"
    return f"VER-{date}-{record['sha256'][:8]}"


def validate_batch(
    batch: dict[str, Any],
    downloads_dir: Path,
    documents: list[dict[str, Any]],
    versions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    documents_by_id = {row["document_id"]: row for row in documents}
    versions_by_id = {row["version_id"]: row for row in versions}
    hashes = {row.get("sha256") for row in versions}
    prepared: list[dict[str, Any]] = []
    errors: list[str] = []

    for index, source in enumerate(batch.get("records", []), 1):
        record = deepcopy(source)
        label = record.get("title") or f"record {index}"
        required = (
            "source_id",
            "source_record_id",
            "document_id",
            "document_type",
            "effective_date",
            "sha256",
            "file_size",
            "attachment_filename",
            "source_page_url",
            "attachment_url",
        )
        missing = [key for key in required if record.get(key) in (None, "")]
        if missing:
            errors.append(f"{label}: 필수값 누락 {', '.join(missing)}")
            continue
        if record["document_id"] not in documents_by_id:
            errors.append(f"{label}: 기존 document_id 없음 {record['document_id']}")
            continue
        same_document = [
            row for row in versions if row.get("document_id") == record["document_id"]
        ]
        latest = max(
            same_document,
            key=lambda row: (
                row.get("revision_date") or row.get("effective_date") or "",
                row["version_id"],
            ),
            default=None,
        )
        expected_previous = record.get("previous_version_id")
        if expected_previous and (
            latest is None or latest["version_id"] != expected_previous
        ):
            actual = latest["version_id"] if latest else "없음"
            errors.append(
                f"{label}: 기준 버전 불일치 {actual} != {expected_previous}"
            )
            continue
        path = find_download(downloads_dir, record)
        if path is None:
            errors.append(f"{label}: 다운로드 파일을 찾지 못함")
            continue
        digest = sha256_file(path)
        size = path.stat().st_size
        if digest != record["sha256"]:
            errors.append(f"{label}: SHA-256 불일치")
            continue
        if size != int(record["file_size"]):
            errors.append(f"{label}: 파일 크기 불일치 {size} != {record['file_size']}")
            continue
        version_id = record.get("version_id") or expected_version_id(record)
        if version_id in versions_by_id and versions_by_id[version_id].get("sha256") != digest:
            errors.append(f"{label}: version_id 충돌 {version_id}")
            continue
        if digest in hashes and version_id not in versions_by_id:
            errors.append(f"{label}: 기존 다른 버전에 같은 SHA-256이 존재")
            continue
        record["version_id"] = version_id
        record["captured_at"] = record.get("captured_at") or batch.get("captured_at")
        record["download_path"] = path
        record["archive_file"] = canonical_raw_path(record)
        record["already_present"] = version_id in versions_by_id
        prepared.append(record)

    if errors:
        raise ValueError("공식 원천 배치 검증 실패:\n- " + "\n- ".join(errors))
    if not prepared:
        raise ValueError("반영할 공식 원천 레코드가 없습니다")
    return prepared


def update_metadata(
    prepared: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    versions: list[dict[str, Any]],
    source_manifest: list[dict[str, Any]],
    updated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    documents_by_id = {row["document_id"]: row for row in documents}
    versions_by_id = {row["version_id"]: row for row in versions}

    for record in prepared:
        if record["already_present"]:
            continue
        doc = documents_by_id[record["document_id"]]
        same_document = [
            row for row in versions if row["document_id"] == record["document_id"]
        ]
        previous = max(
            same_document,
            key=lambda row: (
                row.get("revision_date") or row.get("effective_date") or "",
                row["version_id"],
            ),
            default=None,
        )
        for row in same_document:
            if row.get("is_current") is True:
                row["is_current"] = False
                row["current_status"] = "historical"
        if previous:
            previous["next_version_id"] = record["version_id"]

        revision_date = record.get("revision_date") or record["effective_date"]
        version = {
            "version_id": record["version_id"],
            "document_id": record["document_id"],
            "version_group_id": doc["version_group_id"],
            "revision_date": revision_date,
            "effective_date": record["effective_date"],
            "source_file": record["archive_file"].as_posix(),
            "normalized_file": None,
            "sha256": record["sha256"],
            "is_current": True,
            "current_status": "confirmed",
            "previous_version_id": previous["version_id"] if previous else None,
            "next_version_id": None,
            "change_summary": "공식 원천 신규 게시본",
            "version_confidence": "high",
            "access_level": "public",
            "title": doc["title"],
            "document_type": doc["document_type"],
            "category": doc.get("category"),
            "department": record.get("department") or doc.get("department"),
            "authority_level": doc["authority_level"],
            "source_url": record["attachment_url"],
            "source_page_url": record["source_page_url"],
            "enactment_date": doc.get("enactment_date"),
            "file_size": record["file_size"],
            "mime_type": "application/haansofthwp",
            "text_extraction_status": "pending_hancom_pdf",
            "pdf_conversion_status": "pending",
        }
        versions.append(version)
        versions_by_id[version["version_id"]] = version

        source_manifest.append(
            {
                "document_type": doc["document_type"],
                "legacy_document_id": doc["document_id"],
                "source_file": record["attachment_url"],
                "archive_file": record["archive_file"].as_posix(),
                "sha256": record["sha256"],
                "file_size": record["file_size"],
                "status": "copied",
                "hash_verified": True,
                "access_level": "public",
                "origin_type": "official_web",
                "source_id": record["source_id"],
                "source_record_id": record["source_record_id"],
                "source_page_url": record["source_page_url"],
                "source_url": record["attachment_url"],
                "collected_at": record.get("captured_at") or updated_at,
            }
        )

        doc.update(
            {
                "department": record.get("department") or doc.get("department"),
                "source_url": record["attachment_url"],
                "source_page_url": record["source_page_url"],
                "original_filename": record["attachment_filename"],
                "source_relative_path": record["archive_file"].as_posix(),
                "normalized_relative_path": None,
                "revision_date": revision_date,
                "effective_date": record["effective_date"],
                "current_status": "confirmed",
                "is_current": True,
                "latest_version_id": record["version_id"],
                "file_extension": ".hwp",
                "mime_type": "application/haansofthwp",
                "file_size": record["file_size"],
                "sha256": record["sha256"],
                "text_extraction_status": "pending_hancom_pdf",
                "updated_at": updated_at,
                "pdf_conversion_status": "pending",
            }
        )
        doc.pop("pdf_relative_path", None)

    versions.sort(key=lambda row: (row["document_id"], row.get("revision_date") or "", row["version_id"]))
    source_manifest.sort(key=lambda row: (row.get("archive_file") or "", row.get("sha256") or ""))
    return documents, versions, source_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--downloads-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo_root.resolve()
    batch = json.loads(args.batch.read_text(encoding="utf-8"))
    documents_path = repo / "metadata/documents.jsonl"
    versions_path = repo / "metadata/versions.jsonl"
    manifest_path = repo / "metadata/source_manifest.jsonl"
    documents = read_jsonl(documents_path)
    versions = read_jsonl(versions_path)
    source_manifest = read_jsonl(manifest_path)
    prepared = validate_batch(batch, args.downloads_dir, documents, versions)

    plan = {
        "mode": "apply" if args.apply else "plan",
        "records": len(prepared),
        "new_versions": sum(not row["already_present"] for row in prepared),
        "already_present": sum(row["already_present"] for row in prepared),
        "items": [
            {
                "document_id": row["document_id"],
                "version_id": row["version_id"],
                "sha256": row["sha256"],
                "archive_file": row["archive_file"].as_posix(),
                "already_present": row["already_present"],
            }
            for row in prepared
        ],
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not args.apply:
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = repo / ".artifacts/official-update/backups" / stamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    for path in (documents_path, versions_path, manifest_path):
        shutil.copy2(path, backup_dir / path.name)

    for row in prepared:
        target = repo / row["archive_file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha256_file(target) != row["sha256"]:
            raise ValueError(f"기존 raw 파일 해시 충돌: {target}")
        if not target.exists():
            shutil.copy2(row["download_path"], target)
        if sha256_file(target) != row["sha256"]:
            raise IOError(f"복사 후 SHA-256 불일치: {target}")

    updated_at = datetime.now(timezone.utc).isoformat()
    documents, versions, source_manifest = update_metadata(
        prepared, documents, versions, source_manifest, updated_at
    )
    write_jsonl(documents_path, documents)
    write_jsonl(versions_path, versions)
    write_jsonl(manifest_path, source_manifest)
    print(f"backup: {backup_dir.relative_to(repo).as_posix()}")
    print("next: Windows에서 scripts/convert_hwp_to_pdf.ps1 실행 후 index_pdf_derivatives.py, build_versions.py, build_chunks.py, build_catalog.py, validate_corpus.py 순으로 실행")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
