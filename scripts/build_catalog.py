"""현행 문서 카탈로그, corpus manifest와 검증 검색 예시를 생성한다."""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone

from common import ROOT, read_jsonl, sha256_file, write_json, write_jsonl


def deterministic_generated_at(rows: list[dict]) -> str:
    """입력이 같으면 같은 생성시각을 사용한다."""
    if os.environ.get("SOURCE_DATE_EPOCH"):
        return datetime.fromtimestamp(int(os.environ["SOURCE_DATE_EPOCH"]),timezone.utc).isoformat()
    candidates=sorted(str(r.get(k)) for r in rows for k in ("updated_at","collected_at","portable_converted_at") if r.get(k))
    return candidates[-1] if candidates else "1970-01-01T00:00:00+00:00"


def main() -> int:
    docs = read_jsonl(ROOT / "metadata/documents.jsonl"); versions = read_jsonl(ROOT / "metadata/versions.jsonl"); chunks = read_jsonl(ROOT / "rag/chunks.jsonl")
    current = [d for d in docs if d.get("is_current") is True and d.get("latest_version_id")]
    latest = [d for d in docs if d.get("latest_version_id")]
    write_jsonl(ROOT / "metadata/current_documents.jsonl", current); write_jsonl(ROOT / "metadata/latest_documents.jsonl", latest); write_jsonl(ROOT / "rag/document_catalog.jsonl", docs)
    manifest = {"corpus_id": "knut-university-policy", "generated_at": deterministic_generated_at(docs+versions), "documents": len(docs), "versions": len(versions), "current_documents": len(current), "chunks": len(chunks), "document_types": Counter(d["document_type"] for d in docs), "sha256": {"documents": sha256_file(ROOT/"metadata/documents.jsonl"), "chunks": sha256_file(ROOT/"rag/chunks.jsonl")}}
    write_json(ROOT / "rag/corpus_manifest.json", manifest)
    evaluation=json.loads((ROOT/"config/retrieval_eval.json").read_text(encoding="utf-8"))
    examples=[{"query":case.get("query"),"filters":case.get("filters",{}),"expected":case["expected"],"validation":"실제 코퍼스 ID를 사용하는 자동 회귀평가"} for case in evaluation["cases"]]
    write_json(ROOT / "rag/retrieval_examples.json", examples); print(json.dumps({"documents": len(docs), "versions": len(versions), "current": len(current), "chunks": len(chunks)}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
