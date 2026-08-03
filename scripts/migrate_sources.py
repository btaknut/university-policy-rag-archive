"""통합 아카이브의 raw 계층을 비파괴·멱등 복사한다."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

from common import ROOT, SOURCE_ARCHIVE, candidate_documents, read_jsonl, sha256_file, write_csv, write_jsonl

EXCLUDED_FIELDS = ["source_file", "sha256", "reason", "access_level"]


def main() -> int:
    p = argparse.ArgumentParser(); mode = p.add_mutually_exclusive_group(required=True); mode.add_argument("--dry-run", action="store_true"); mode.add_argument("--execute", action="store_true"); args = p.parse_args()
    security_path = ROOT / "metadata/security_candidates.json"; security = json.loads(security_path.read_text(encoding="utf-8")) if security_path.exists() else {"findings": []}
    restricted = {f["sha256"]: f for f in security["findings"]}; source_manifest = []; excluded = []; copied = reused = errors = 0
    for doc in candidate_documents():
        occurrences = doc.get("source_occurrences") or [{"archive_relative_path": doc["archive_relative_path"]}]
        for occurrence in occurrences:
            source = SOURCE_ARCHIVE / occurrence["archive_relative_path"]
            if not source.exists(): errors += 1; continue
            digest = sha256_file(source)
            if digest in restricted:
                excluded.append({"source_file": occurrence["archive_relative_path"], "sha256": digest, "reason": ";".join(restricted[digest]["reasons"]), "access_level": "review_required"}); continue
            bucket = "regulations" if doc["document_type"] == "regulation" else "guidelines"
            raw_anchor = "data/raw/regulations/" if bucket == "regulations" else "data/raw/guidelines/"
            rel = occurrence["archive_relative_path"].replace("\\", "/"); rel = rel.split(raw_anchor, 1)[-1]
            target = ROOT / "sources/raw" / bucket / Path(rel)
            status = "planned"
            if target.exists() and sha256_file(target) == digest: status = "reused"; reused += 1
            elif args.execute:
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
                if sha256_file(target) != digest: raise IOError(f"해시 불일치: {source} -> {target}")
                status = "copied"; copied += 1
            source_manifest.append({"document_type": doc["document_type"], "legacy_document_id": doc["document_id"], "source_file": occurrence["archive_relative_path"], "archive_file": target.relative_to(ROOT).as_posix(), "sha256": digest, "file_size": source.stat().st_size, "status": status, "hash_verified": status in {"copied", "reused"}, "access_level": "public"})
    suffix = "" if args.execute else ".dry_run"
    write_jsonl(ROOT / f"metadata/source_manifest{suffix}.jsonl", source_manifest); write_csv(ROOT / f"metadata/excluded_files{suffix}.csv", excluded, EXCLUDED_FIELDS)
    restricted_dir = ROOT / "sources/restricted_manifest"; restricted_dir.mkdir(parents=True, exist_ok=True); write_jsonl(restricted_dir / f"restricted_files{suffix}.jsonl", excluded)
    print(json.dumps({"entries": len(source_manifest), "copied": copied, "reused": reused, "excluded": len(excluded), "errors": errors, "mode": "execute" if args.execute else "dry-run"}, ensure_ascii=False)); return 1 if errors else 0


if __name__ == "__main__": raise SystemExit(main())
