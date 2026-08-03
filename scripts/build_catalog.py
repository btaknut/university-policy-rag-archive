"""현행 문서 카탈로그, corpus manifest와 검증 검색 예시를 생성한다."""
from __future__ import annotations

import json
from collections import Counter

from common import ROOT, now, read_jsonl, sha256_file, write_json, write_jsonl


def main() -> int:
    docs = read_jsonl(ROOT / "metadata/documents.jsonl"); versions = read_jsonl(ROOT / "metadata/versions.jsonl"); chunks = read_jsonl(ROOT / "rag/chunks.jsonl")
    current = [d for d in docs if d.get("is_current") is True and d.get("latest_version_id")]
    write_jsonl(ROOT / "metadata/current_documents.jsonl", current); write_jsonl(ROOT / "rag/document_catalog.jsonl", docs)
    manifest = {"corpus_id": "knut-university-policy", "generated_at": now(), "documents": len(docs), "versions": len(versions), "current_documents": len(current), "chunks": len(chunks), "document_types": Counter(d["document_type"] for d in docs), "sha256": {"documents": sha256_file(ROOT/"metadata/documents.jsonl"), "chunks": sha256_file(ROOT/"rag/chunks.jsonl")}}
    write_json(ROOT / "rag/corpus_manifest.json", manifest)
    queries = [("학칙에서 휴학 관련 조문 검색", ["휴학"]), ("수강신청 관련 규정 검색", ["수강신청"]), ("장학금 관련 규정과 지침 동시 검색", ["장학"]), ("동일 제목 문서의 최신 개정본 검색", []), ("폐지되거나 과거 버전인 문서 검색", []), ("특정 부서가 담당하는 지침 검색", []), ("규정과 지침이 동시에 검색되는 경우 유형별 구분", []), ("조문 번호로 직접 검색", ["제1조"]), ("별표 또는 별지 검색", ["별표", "별지"])]
    examples = []
    for query, keywords in queries:
        matches = [c for c in chunks if keywords and any(k in (c["title"] + " " + c["text"]) for k in keywords)][:5]
        examples.append({"query": query, "expected": [{"document_id": c["document_id"], "version_id": c["version_id"], "article_no": c.get("article_no"), "chunk_id": c["chunk_id"]} for c in matches], "validation": "현재 실제 코퍼스의 문서 ID와 조문 위치를 기준으로 생성; 빈 기대값은 수동 필터 검증 사례"})
    write_json(ROOT / "rag/retrieval_examples.json", examples); print(json.dumps({"documents": len(docs), "versions": len(versions), "current": len(current), "chunks": len(chunks)}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
