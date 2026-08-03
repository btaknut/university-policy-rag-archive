"""읽기 전용 통합 아카이브와 민감정보 후보를 감사한다."""
from __future__ import annotations

import collections
import json
from pathlib import Path

from common import ROOT, SOURCE_ARCHIVE, candidate_documents, now, scan_text, sha256_file, write_json


def main() -> int:
    if not SOURCE_ARCHIVE.is_dir(): raise FileNotFoundError(f"통합 아카이브가 없습니다: {SOURCE_ARCHIVE}")
    files = [p for p in SOURCE_ARCHIVE.rglob("*") if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts and "__pycache__" not in p.parts]
    ext = collections.Counter(p.suffix.lower() or "[none]" for p in files); total = sum(p.stat().st_size for p in files)
    docs = candidate_documents(); findings = []
    for doc in docs:
        text_path = SOURCE_ARCHIVE / (doc.get("text_relative_path") or "__missing__")
        if not text_path.exists() or text_path.stat().st_size > 20 * 1024 * 1024: continue
        try: reasons = scan_text(text_path.read_text(encoding="utf-8", errors="replace"))
        except OSError: continue
        if reasons: findings.append({"sha256": doc["sha256"], "document_id": doc["document_id"], "title": doc["title"], "reasons": reasons, "source_relative_path": doc["source_relative_path"]})
    write_json(ROOT / "metadata/security_candidates.json", {"generated_at": now(), "findings": findings})
    large = {"25mb": sum(p.stat().st_size >= 25*1024*1024 for p in files), "50mb": sum(p.stat().st_size >= 50*1024*1024 for p in files), "100mb": sum(p.stat().st_size >= 100*1024*1024 for p in files)}
    lines = ["# 원본 감사 보고서", "", f"- 원본: `{SOURCE_ARCHIVE}`", f"- 전체 파일: {len(files):,}개", f"- 전체 크기: {total:,} bytes", f"- 실제 규정·지침 후보: {len(docs):,}개", f"- 보안 검토 후보: {len(findings):,}개", f"- 25/50/100MB 이상: {large['25mb']}/{large['50mb']}/{large['100mb']}개", "", "## 확장자", ""]
    lines += [f"- `{k}`: {v:,}" for k, v in sorted(ext.items(), key=lambda x: (-x[1], x[0]))]
    lines += ["", "보안 후보는 자동 삭제하지 않고 raw·정규화·RAG 커밋 대상에서 제외한다. 탐지는 보조 수단이므로 공개 전 수동 검토가 필요하다."]
    (ROOT / "reports").mkdir(exist_ok=True); (ROOT / "reports/source_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"files": len(files), "bytes": total, "document_candidates": len(docs), "security_candidates": len(findings), "large": large}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
