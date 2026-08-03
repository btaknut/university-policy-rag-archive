"""대학 규정·지침 RAG 코퍼스 공통 유틸리티."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ARCHIVE = Path(r"C:\Users\kwon\Documents\university_policy_archive")
SOURCE_DOCS = SOURCE_ARCHIVE / "metadata" / "documents.jsonl"
DOCUMENT_FIELDS = ["document_id", "document_type", "title", "alternative_titles", "category", "subcategory", "issuing_organization", "department", "authority_level", "access_level", "source_archive", "source_url", "source_page_url", "original_filename", "source_relative_path", "normalized_relative_path", "enactment_date", "revision_date", "effective_date", "abolition_date", "current_status", "is_current", "version_group_id", "latest_version_id", "file_extension", "mime_type", "file_size", "sha256", "text_extraction_status", "metadata_confidence", "collected_at", "updated_at", "notes"]
VERSION_FIELDS = ["version_id", "document_id", "version_group_id", "revision_date", "effective_date", "source_file", "normalized_file", "sha256", "is_current", "current_status", "previous_version_id", "next_version_id", "change_summary", "version_confidence", "access_level", "title", "document_type", "category", "department", "authority_level", "source_url", "source_page_url", "enactment_date", "file_size", "mime_type", "text_extraction_status"]
CHUNK_FIELDS = ["chunk_id", "document_id", "version_id", "version_group_id", "document_type", "title", "category", "department", "authority_level", "access_level", "is_current", "current_status", "enactment_date", "revision_date", "effective_date", "section_path", "chapter", "section", "article_no", "article_title", "paragraph_no", "item_no", "appendix_no", "page_start", "page_end", "chunk_index", "text", "text_for_embedding", "token_count", "source_url", "source_file", "normalized_file", "sha256", "citation_label"]
REAL_DOCUMENT_EXTENSIONS = {".pdf", ".hwp", ".hwpx", ".docx", ".xlsx", ".xls"}
TEXT_EXTENSIONS = {".txt", ".md", ".html", ".htm", ".json", ".jsonl", ".csv", ".yaml", ".yml", ".py", ".ps1"}

SECURITY_PATTERNS = {
    "resident_registration_number": re.compile(r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)"),
    "personal_mobile_number": re.compile(r"(?<!\d)01[016789]-?\d{3,4}-?\d{4}(?!\d)"),
    "external_email_address": re.compile(r"\b[A-Z0-9._%+-]+@(?![A-Z0-9.-]*ut\.ac\.kr\b)[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "api_key_or_token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})"),
    "password_assignment": re.compile(r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*[^\s'\"]{6,}"),
    "internal_ipv4": re.compile(r"(?<!\d)(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3})(?!\d)"),
}


def now() -> str:
    """UTC ISO 시각."""
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    """스트리밍 SHA-256."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def verify_content_or_lfs_pointer(path: Path, expected_sha256: str) -> bool:
    """실제 파일 해시 또는 Git LFS 포인터 oid가 기대 해시와 일치하는지 확인한다."""
    if not path.exists(): return False
    if path.stat().st_size < 1024:
        try:
            pointer = path.read_text(encoding="utf-8")
            match = re.search(r"^oid sha256:([0-9a-f]{64})$", pointer, re.M)
            if match: return match.group(1) == expected_sha256
        except (UnicodeDecodeError, OSError): pass
    return sha256_file(path) == expected_sha256


def load_yaml(path: Path) -> dict[str, Any]:
    """UTF-8 YAML 로드."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """JSONL을 목록으로 읽는다."""
    if not path.exists(): return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """UTF-8 JSONL을 원자 교체한다."""
    path.parent.mkdir(parents=True, exist_ok=True); temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows: stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temp.replace(path)


def write_json(path: Path, value: Any) -> None:
    """UTF-8 JSON을 원자 교체한다."""
    path.parent.mkdir(parents=True, exist_ok=True); temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"); temp.replace(path)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    """Excel 호환 UTF-8-SIG CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore"); writer.writeheader()
        for row in rows: writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def title_key(title: str) -> str:
    """제목의 날짜·구두점을 제거한 보수적 문서 키."""
    text = re.sub(r"\([^)]*(?:제정|개정|시행|\d{4})[^)]*\)", "", title or "")
    text = re.sub(r"\d{4}[.년_-]\s*\d{1,2}(?:[.월_-]\s*\d{1,2}일?)?", "", text)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def stable_document_id(document_type: str, title: str, discriminator: str = "") -> str:
    """유형·정규화 제목 기반 안정적 문서 ID."""
    prefix = {"regulation": "REG", "guideline": "GDL", "rule": "RUL", "manual": "MAN"}.get(document_type, "ETC")
    seed = f"{document_type}:{title_key(title)}:{discriminator}".encode("utf-8")
    return f"{prefix}-{hashlib.sha256(seed).hexdigest()[:12]}"


def version_id(revision_date: str | None, digest: str) -> str:
    """날짜와 내용 해시 기반 버전 ID."""
    date = re.sub(r"[^0-9]", "", revision_date or "") or "unknown"
    return f"VER-{date}-{digest[:8]}"


def candidate_documents() -> list[dict[str, Any]]:
    """기존 고신뢰도 첨부 문서만 실제 규정·지침 후보로 선택한다."""
    return [d for d in read_jsonl(SOURCE_DOCS) if d.get("metadata_confidence") == "high" and d.get("file_extension", "").lower() in REAL_DOCUMENT_EXTENSIONS]


def scan_text(text: str) -> list[str]:
    """민감·비밀정보 패턴 이름을 반환한다."""
    return [name for name, pattern in SECURITY_PATTERNS.items() if pattern.search(text)]


def strip_front_matter(text: str) -> str:
    """기존 YAML front matter를 제거한다."""
    if text.startswith("---"):
        match = re.match(r"^---\s*\n.*?\n---\s*\n?", text, flags=re.S)
        if match: return text[match.end():]
    return text


def token_estimate(text: str) -> int:
    """외부 tokenizer 없이 재현 가능한 한국어 혼합 토큰 근사치."""
    korean = len(re.findall(r"[가-힣]", text)); other = len(re.findall(r"[A-Za-z0-9]+|[^\sA-Za-z0-9가-힣]", text))
    return max(1, (korean + 1) // 2 + other)
