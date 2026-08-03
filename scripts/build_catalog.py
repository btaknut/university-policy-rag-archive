"""현행 문서 카탈로그, corpus manifest와 검증 검색 예시를 생성한다."""
from __future__ import annotations

import json
from collections import Counter

from common import ROOT, now, read_jsonl, write_json, write_jsonl


def main() -> int:
    docs = read_jsonl(ROOT / "metadata/documents.jsonl"); versions = read_jsonl(ROOT / "metadata/versions.jsonl"); chunks = read_jsonl(ROOT / "rag/chunks.jsonl")
    current = [d for d in docs if d.get("is_current") is True and d.get("latest_version_id")]
    write_jsonl(ROOT / "metadata/current_documents.jsonl", current); write_jsonl(ROOT / "rag/document_catalog.jsonl", docs)
    manifest = {"corpus_id": "knut-university-policy", "generated_at": now(), "documents": len(docs), "versions": len(versions), "current_documents": len(current), "chunks": len(chunks), "document_types": Counter(d["document_type"] for d in docs), "sha256": {"documents": None, "chunks": None}}
    write_json(ROOT / "rag/corpus_manifest.json", manifest)
    queries = ["학칙에서 휴학 관련 조문 검색", "수강신청 관련 규정 검색", "장학금 관련 규정과 지침 동시 검색", "동일 제목 문서의 최신 개정본 검색", "폐지되거나 과거 버전인 문서 검색", "특정 부서가 담당하는 지침 검색", "규정과 지침이 동시에 검색되는 경우 유형별 구분", "조문 번호로 직접 검색", "별표 또는 별지 검색"]
    examples = [{"query": q, "expected_document_ids": [], "validation": "실제 청크에서 제목·유형·조문 위치를 사람이 확인하며 존재하지 않는 정답은 고정하지 않음"} for q in queries]
    write_json(ROOT / "rag/retrieval_examples.json", examples); print(json.dumps({"documents": len(docs), "versions": len(versions), "current": len(current), "chunks": len(chunks)}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
