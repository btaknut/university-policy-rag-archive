"""상위 RAG 시스템용 독립 bundle과 선택적 ZIP을 생성한다."""
from __future__ import annotations

import argparse
import shutil

from common import ROOT


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--zip", action="store_true"); args = p.parse_args(); target = ROOT / "rag/exports/university_policy_rag_bundle"; target.mkdir(parents=True, exist_ok=True)
    for source, name in ((ROOT/"metadata/documents.jsonl", "documents.jsonl"), (ROOT/"rag/chunks.jsonl", "chunks.jsonl"), (ROOT/"rag/corpus_manifest.json", "corpus_manifest.json")): shutil.copy2(source, target/name)
    (target/"README.md").write_text("# University Policy RAG Bundle\n\n`documents.jsonl`과 `chunks.jsonl`로 키워드 또는 벡터 인덱스를 재생성한다. `access_level=public`만 포함하며 SHA-256과 source_file을 인용 근거로 유지한다.\n", encoding="utf-8")
    archive = shutil.make_archive(str(target), "zip", target) if args.zip else None; print({"bundle": str(target), "zip": archive}); return 0


if __name__ == "__main__": raise SystemExit(main())
