"""코퍼스 경로·해시·스키마·현행성·청크·보안을 종합 검증한다."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from jsonschema import Draft202012Validator

from common import ROOT, SOURCE_ARCHIVE, read_jsonl, sha256_file


def main() -> int:
    docs = read_jsonl(ROOT / "metadata/documents.jsonl"); versions = read_jsonl(ROOT / "metadata/versions.jsonl"); chunks = read_jsonl(ROOT / "rag/chunks.jsonl"); manifest = read_jsonl(ROOT / "metadata/source_manifest.jsonl")
    checks = []
    def add(name: str, status: str, detail: str) -> None: checks.append((name, status, detail))
    bad_hash = [m["archive_file"] for m in manifest if not (ROOT / m["archive_file"]).exists() or sha256_file(ROOT / m["archive_file"]) != m["sha256"]]
    add("원본 사본 SHA-256", "PASS" if not bad_hash else "FAIL", f"불일치/누락 {len(bad_hash)}건")
    changed_source = [m["source_file"] for m in manifest if not (SOURCE_ARCHIVE / m["source_file"]).exists() or sha256_file(SOURCE_ARCHIVE / m["source_file"]) != m["sha256"]]
    add("읽기 전용 통합 아카이브 보존", "PASS" if not changed_source else "FAIL", f"변경/누락 {len(changed_source)}건")
    for label, rows, key in (("document_id", docs, "document_id"), ("version_id", versions, "version_id"), ("chunk_id", chunks, "chunk_id")):
        counts = Counter(r.get(key) for r in rows); duplicate = [x for x, n in counts.items() if n > 1]; add(f"{label} 고유성", "PASS" if not duplicate else "FAIL", f"중복 {len(duplicate)}건")
    doc_ids = {d["document_id"] for d in docs}; version_ids = {v["version_id"] for v in versions}; orphan = [c["chunk_id"] for c in chunks if c["document_id"] not in doc_ids or c["version_id"] not in version_ids]; add("청크 원문 연결", "PASS" if not orphan else "FAIL", f"고아 청크 {len(orphan)}건")
    missing_paths = [v["version_id"] for v in versions if not (ROOT / v["source_file"]).exists() or (v.get("normalized_file") and not (ROOT / v["normalized_file"]).exists())]; add("메타데이터 경로", "PASS" if not missing_paths else "FAIL", f"누락 {len(missing_paths)}건")
    current = defaultdict(list)
    for v in versions:
        if v.get("is_current") is True: current[v["document_id"]].append(v)
    multiple = {k: v for k, v in current.items() if len(v) > 1}; add("현행본 단일성", "PASS" if not multiple else "FAIL", f"복수 현행 {len(multiple)}문서")
    empty = [c["chunk_id"] for c in chunks if not c.get("text", "").strip()]; long = [c["chunk_id"] for c in chunks if c.get("token_count", 0) > 1200]
    add("빈 청크", "PASS" if not empty else "FAIL", f"빈 청크 {len(empty)}건"); add("최대 청크 크기", "PASS" if not long else "FAIL", f"1,200 초과 {len(long)}건")
    restricted = [c["chunk_id"] for c in chunks if c.get("access_level") != "public"]; add("restricted 청크 제외", "PASS" if not restricted else "FAIL", f"위반 {len(restricted)}건")
    citation_missing = [c["chunk_id"] for c in chunks if not all(c.get(k) for k in ("title", "source_file", "sha256", "citation_label"))]; add("인용 필드", "PASS" if not citation_missing else "FAIL", f"누락 {len(citation_missing)}건")
    schema_errors = []
    for filename, rows in (("document.schema.json", docs), ("version.schema.json", versions), ("chunk.schema.json", chunks)):
        schema = json.loads((ROOT / "schemas" / filename).read_text(encoding="utf-8")); validator = Draft202012Validator(schema)
        for index, row in enumerate(rows):
            for err in validator.iter_errors(row): schema_errors.append(f"{filename}[{index}]: {err.message}")
    add("JSON Schema", "PASS" if not schema_errors else "FAIL", f"오류 {len(schema_errors)}건" + (("; " + "; ".join(schema_errors[:5])) if schema_errors else ""))
    normalized_missing = sum(not v.get("normalized_file") for v in versions); add("텍스트 미추출 버전", "WARNING" if normalized_missing else "PASS", f"정규화 없음 {normalized_missing}건(HWP 과거본 등 원본 보존)")
    counts = Counter(status for _, status, _ in checks); lines = ["# 코퍼스 검증 보고서", "", f"- PASS: {counts['PASS']}", f"- WARNING: {counts['WARNING']}", f"- FAIL: {counts['FAIL']}", ""]
    for name, status, detail in checks: lines += [f"## {status} — {name}", "", detail, ""]
    (ROOT / "reports").mkdir(exist_ok=True); (ROOT / "reports/corpus_validation.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(dict(counts), ensure_ascii=False)); return 1 if counts["FAIL"] else 0


if __name__ == "__main__": raise SystemExit(main())
