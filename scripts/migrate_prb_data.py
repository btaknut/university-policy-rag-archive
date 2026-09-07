"""One-shot PR B migration; the workflow removes this helper after use."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from search_lib import classify_section  # noqa: E402

BASE_HASHES = {
    "metadata/documents.jsonl": "8725e3fd86acfbf7ce1c9e02c26f92bbfda72cc255a111c43204d9a33bed2c73",
    "metadata/versions.jsonl": "02c4828f9353100afc609e4270f30029c1e066128b4fc71da715ffdc82291f29",
    "rag/chunks.jsonl": "3b3b43ac171ca657999cb79c56139ac10596b45c6170196ec385adfb5434a065",
    "rag/corpus_manifest.json": "744e13a8e4c067f76209a7fadadccc6aa32459713898083c259e6ab08fa8d103",
    "metadata/source_manifest.jsonl": "5898c3dad7aae9068330940fca52ce843fd131cd4355eaf42791e7a49fae7584",
}


def run(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, check=True, text=True, capture_output=True).stdout


def sha(path: str | Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def read_jsonl(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in (ROOT / path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    with (ROOT / path).open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def url_quality(row: dict) -> str:
    value = (row.get("source_page_url") or row.get("source_url") or "").lower()
    if not value:
        return "unknown"
    if "selectboardarticle" in value or "mode=v" in value or "/view" in value:
        return "detail"
    if "list" in value or "mode=l" in value or "06010" in value:
        return "list_only"
    if "download" in value or "filedown" in value or "mode=d" in value:
        return "attachment_only"
    return "unknown"


def repair_front_matter(versions: list[dict]) -> tuple[int, int]:
    changed_files = changed_fields = 0
    core = ("document_id", "version_id", "title", "sha256", "is_current", "current_status")
    for version in versions:
        relative = version.get("normalized_file")
        if not relative:
            continue
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        if not match:
            continue
        front = yaml.safe_load(match.group(1)) or {}
        before = dict(front)
        for key in core:
            if key in front and front.get(key) != version.get(key):
                front[key] = version.get(key)
                changed_fields += 1
        if front == before:
            continue
        rendered = yaml.safe_dump(front, allow_unicode=True, sort_keys=False, default_flow_style=False).rstrip()
        path.write_text(f"---\n{rendered}\n---\n\n{text[match.end():].lstrip()}", encoding="utf-8", newline="\n")
        changed_files += 1
    return changed_files, changed_fields


def main() -> None:
    documents = read_jsonl("metadata/documents.jsonl")
    versions = read_jsonl("metadata/versions.jsonl")
    chunks = read_jsonl("rag/chunks.jsonl")
    original_document_ids = [row["document_id"] for row in documents]
    original_version_ids = [row["version_id"] for row in versions]
    original_chunk_ids = [row["chunk_id"] for row in chunks]

    grouped: dict[str, list[dict]] = defaultdict(list)
    for version in versions:
        grouped[version["document_id"]].append(version)
    tails = {}
    for document_id, rows in grouped.items():
        candidates = [row for row in rows if not row.get("next_version_id")]
        if len(candidates) != 1:
            raise RuntimeError(f"{document_id}: expected one chain tail, got {len(candidates)}")
        tails[document_id] = candidates[0]["version_id"]
    if set(tails) != set(original_document_ids):
        raise RuntimeError("version groups and documents differ")

    for document in documents:
        document.update({
            "latest_version_id": tails[document["document_id"]],
            "is_latest_version": True,
            "validity_status": "unknown",
            "validity_evidence": None,
            "validity_checked_at": None,
            "status_confidence": "unknown",
            "source_url_quality": url_quality(document),
        })
    for version in versions:
        version.update({
            "is_latest_version": version["version_id"] == tails[version["document_id"]],
            "validity_status": "unknown",
            "validity_evidence": None,
            "validity_checked_at": None,
            "status_confidence": "unknown",
            "source_url_quality": url_quality(version),
        })
    write_jsonl("metadata/documents.jsonl", documents)
    write_jsonl("metadata/versions.jsonl", versions)
    repaired_files, repaired_fields = repair_front_matter(versions)

    version_map = {row["version_id"]: row for row in versions}
    document_map = {row["document_id"]: row for row in documents}
    for chunk in chunks:
        version = version_map[chunk["version_id"]]
        document = document_map[chunk["document_id"]]
        kind, scope, normative = classify_section(chunk.get("text", ""), chunk.get("section_path"))
        chunk.update({
            "chunk_schema_version": "2.0",
            "is_latest_version": version["version_id"] == document["latest_version_id"],
            "validity_status": version["validity_status"],
            "status_confidence": version["status_confidence"],
            "section_kind": kind,
            "retrieval_scope": scope,
            "normative_status": normative,
        })
    write_jsonl("rag/chunks.jsonl", chunks)

    if original_document_ids != [row["document_id"] for row in documents]:
        raise RuntimeError("document IDs changed")
    if original_version_ids != [row["version_id"] for row in versions]:
        raise RuntimeError("version IDs changed")
    if original_chunk_ids != [row["chunk_id"] for row in chunks]:
        raise RuntimeError("chunk IDs changed")
    if sha("metadata/source_manifest.jsonl") != BASE_HASHES["metadata/source_manifest.jsonl"]:
        raise RuntimeError("source manifest changed")
    run("git", "diff", "--quiet", "--", "sources/raw")

    run(sys.executable, "scripts/build_catalog.py")
    run(sys.executable, "scripts/build_github_catalog.py")
    generated = [
        "metadata/current_documents.jsonl", "metadata/latest_documents.jsonl", "rag/chunks.jsonl",
        "rag/document_catalog.jsonl", "rag/corpus_manifest.json", "rag/retrieval_examples.json",
    ] + [str(path.relative_to(ROOT)) for path in sorted((ROOT / "catalog").rglob("*.md"))]
    first = {path: sha(path) for path in generated}
    run(sys.executable, "scripts/build_catalog.py")
    run(sys.executable, "scripts/build_github_catalog.py")
    if first != {path: sha(path) for path in generated}:
        raise RuntimeError("generated outputs are not deterministic")

    validation = run(sys.executable, "scripts/validate_corpus.py")
    search = run(sys.executable, "scripts/build_search_index.py", "--database", ".cache/search.sqlite3")
    evaluation = run(sys.executable, "scripts/evaluate_retrieval.py", "--database", ".cache/search.sqlite3")
    tests = run(sys.executable, "-m", "pytest", "-q")
    shutil.rmtree(ROOT / ".cache", ignore_errors=True)

    section_counts = Counter(row["section_kind"] for row in chunks)
    scope_counts = Counter(row["retrieval_scope"] for row in chunks)
    quality_counts = Counter(row["source_url_quality"] for row in versions)
    new_hashes = {path: sha(path) for path in BASE_HASHES if path != "metadata/source_manifest.jsonl"}
    report = f"""# 아카이브 검색 데이터 결정적 재생성 — PR B

- 기준 `main`: `f497ce0135762f6aeaa76d9dc575b0b8490e038f`
- 선행 PR A HEAD: `5d64c155d4a6c7242e13aba54eb666b3fc26ee64`
- 범위: 메타데이터 보강, 기존 청크 의미 필드 보강, 카탈로그·manifest·검색 평가자료 재생성
- 제외: 공식 원문, Git LFS 객체, ID 재발급, 과거 백필 122건, 오래된 export 삭제, 재청킹

## 수량과 ID 보존

| 항목 | 이전 | 이후 | 결과 |
|---|---:|---:|---|
| 문서 | 403 | {len(documents)} | `document_id` 전부 보존 |
| 버전 | 864 | {len(versions)} | `version_id` 전부 보존 |
| 현행 호환 표시 | 337 | {sum(row.get('is_current') is True for row in documents)} | `is_current` 의미 변경 없음 |
| 최신 확보 문서 | 337 | {sum(row.get('is_latest_version') is True for row in versions)} | 누락된 체인 말단 66건 연결 |
| 검색 청크 | 15,021 | {len(chunks):,} | `chunk_id` 전부 보존 |
| GitHub 카탈로그 | 0 | {len(list((ROOT / 'catalog').rglob('*.md')))} files | 본문 복제 없이 생성 |

## 메타데이터·검색 보강

- 66개 문서의 `latest_version_id`를 기존 양방향 버전 체인의 유일한 말단에 연결했다.
- 공식 시행·폐지 근거를 새로 확인하지 않았으므로 864개 버전의 `validity_status`와 `status_confidence`는 모두 `unknown`이다. 기존 `is_current`를 `in_force`로 승격하지 않았다.
- URL 품질: 상세 페이지 {quality_counts['detail']}건, 목록 페이지만 확인 가능한 레코드 {quality_counts['list_only']}건.
- normalized Markdown {repaired_files}개 파일의 front matter {repaired_fields}항목을 보정했으며 본문은 변경하지 않았다.
- 기존 청크 ID를 유지하며 15,021개 전부에 검색 의미 필드를 기록했다.

| 청크 분류 | 건수 |
|---|---:|
| operative_text | {section_counts['operative_text']:,} |
| supplementary_provision | {section_counts['supplementary_provision']:,} |
| appendix | {section_counts['appendix']:,} |
| form | {section_counts['form']:,} |
| amendment_reason | {section_counts['amendment_reason']:,} |
| major_changes | {section_counts['major_changes']:,} |
| comparison_old | {section_counts['comparison_old']:,} |
| promulgation_notice | {section_counts['promulgation_notice']:,} |
| unknown | {section_counts['unknown']:,} |
| 기본 검색 primary | {scope_counts['primary']:,} |
| 기본 제외 secondary | {scope_counts['secondary']:,} |

## SHA-256

| 파일 | 이전 | 이후 |
|---|---|---|
| `metadata/documents.jsonl` | `{BASE_HASHES['metadata/documents.jsonl']}` | `{new_hashes['metadata/documents.jsonl']}` |
| `metadata/versions.jsonl` | `{BASE_HASHES['metadata/versions.jsonl']}` | `{new_hashes['metadata/versions.jsonl']}` |
| `rag/chunks.jsonl` | `{BASE_HASHES['rag/chunks.jsonl']}` | `{new_hashes['rag/chunks.jsonl']}` |
| `rag/corpus_manifest.json` | `{BASE_HASHES['rag/corpus_manifest.json']}` | `{new_hashes['rag/corpus_manifest.json']}` |
| `metadata/source_manifest.jsonl` | `{BASE_HASHES['metadata/source_manifest.jsonl']}` | 동일 |

## 검증

- 코퍼스 검증: `{validation.strip()}`
- 검색 인덱스: `{search.strip()}`
- 검색 회귀평가: `{json.loads(evaluation)['status']}`, Recall@5 {json.loads(evaluation)['recall@5']}, MRR {json.loads(evaluation)['mrr']}, 12 cases
- pytest: `{tests.strip().splitlines()[-1]}`
- 생성 산출물 2회 빌드: 해시 일치
- document/version/chunk ID 변경: 0건
- 공식 원문·source manifest 변경: 0건

남은 경고는 로컬 레거시 원본 경로 미설정과 현재 청크와 다른 57,258,437-byte 과거 export다. 중복 감소량은 이번 PR에서 0 bytes이며 소비 경로 확인 후 별도 삭제 PR로 처리한다.

## PR C 분리 판정

PR A의 새 청킹 설정으로 전체 재청킹하면 청크 수가 15,021개에서 14,551개로 바뀌고 기존 ID 477개가 제거되며 7개가 추가된다. 따라서 이 변경은 PR B에 포함하지 않았고, 구 ID→신 ID 매핑·소비자 전환·롤백 절차를 갖춘 선택적 PR C 대상으로 남긴다.
"""
    (ROOT / "reports/archive_search_data_regeneration_2026-09-07.md").write_text(report, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
