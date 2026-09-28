"""버전 순서를 연결하고 명시적 현행본 충돌을 보수적으로 처리한다."""
from __future__ import annotations

import csv
import json
import re
import hashlib
from collections import defaultdict

from common import ROOT, read_jsonl, write_csv, write_jsonl

CONFLICT_FIELDS = ["conflict_id", "document_id_1", "document_id_2", "conflict_reason", "source_path_1", "source_path_2", "sha256_1", "sha256_2", "review_required", "notes"]
DUPLICATE_FIELDS = ["duplicate_group_id", "document_id", "duplicate_type", "compared_document_id", "sha256_match", "recommended_action", "notes"]


def sync_front_matter(versions, documents):
    """본문을 보존하며 변경된 상태 필드 및 portable 파생본 해시만 맞춘다."""
    docs = {d['document_id']: d for d in documents}
    portable_path = ROOT / 'metadata/portable_hwp_manifest.jsonl'
    portable = read_jsonl(portable_path)
    portable_by_id = {p['version_id']: p for p in portable}
    changed = False
    for version in versions:
        if not version.get('normalized_file'):
            continue
        path = ROOT / version['normalized_file']
        if not path.is_file():
            continue
        content = path.read_text(encoding='utf-8')
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.S)
        if not match:
            continue
        front = match.group(1)
        for field in ('is_current', 'current_status'):
            front = re.sub(r'^' + field + r':[^\n]*$',
                           field + ': ' + json.dumps(version.get(field), ensure_ascii=False),
                           front, flags=re.M)
        if front == match.group(1):
            continue
        updated = content[:match.start(1)] + front + content[match.end(1):]
        path.write_text(updated, encoding='utf-8', newline='\n')
        if version.get('portable_conversion_status') == 'success':
            digest = hashlib.sha256(updated.encode('utf-8')).hexdigest()
            version['portable_markdown_sha256'] = digest
            if version['version_id'] in portable_by_id:
                portable_by_id[version['version_id']]['normalized_sha256'] = digest
                changed = True
            doc = docs[version['document_id']]
            if doc.get('latest_version_id') == version['version_id']:
                doc['portable_markdown_sha256'] = digest
    if changed:
        write_jsonl(portable_path, portable)


def main() -> int:
    versions = read_jsonl(ROOT / "metadata/versions.jsonl"); documents = read_jsonl(ROOT / "metadata/documents.jsonl"); groups = defaultdict(list); conflicts = []
    for v in versions: groups[v["document_id"]].append(v)
    for doc_id, items in groups.items():
        items.sort(key=lambda x: (x.get("revision_date") is not None, x.get("revision_date") or "", x["sha256"]))
        for i, item in enumerate(items):
            item["previous_version_id"] = items[i-1]["version_id"] if i else None; item["next_version_id"] = items[i+1]["version_id"] if i + 1 < len(items) else None
        current = [x for x in items if x.get("is_current") is True]
        if len(current) > 1:
            for item in current: item["is_current"] = None; item["current_status"] = "unknown"
            for a, b in zip(current, current[1:]): conflicts.append({"conflict_id": f"CUR-{a['sha256'][:6]}-{b['sha256'][:6]}", "document_id_1": doc_id, "document_id_2": doc_id, "conflict_reason": "복수 버전이 현행본으로 표시됨", "source_path_1": a["source_file"], "source_path_2": b["source_file"], "sha256_1": a["sha256"], "sha256_2": b["sha256"], "review_required": True, "notes": "현행본 자동 확정 해제"})
    by_document = {d["document_id"]: d for d in documents}
    for doc_id, items in groups.items():
        current = [x for x in items if x.get("is_current") is True]
        doc = by_document[doc_id]
        if len(current) == 1:
            doc["is_current"] = True; doc["current_status"] = "confirmed"; doc["latest_version_id"] = current[0]["version_id"]
        else:
            doc["is_current"] = None; doc["current_status"] = "unknown"
            # 최신 확보본은 법적 시행상태와 별개다. 기존 검증된 연결을 보존한다.
            if doc.get("latest_version_id") not in {v['version_id'] for v in items}:
                doc["latest_version_id"] = items[-1]['version_id']
        for item in items:
            item['is_latest_version'] = item['version_id'] == doc['latest_version_id']
            item.setdefault('validity_status', 'unknown')
            item.setdefault('status_confidence', 'unknown')
            item.setdefault('source_url_quality', 'detail' if item.get('source_page_url') and ('mode=V' in item['source_page_url'] or 'selectBoardArticle' in item['source_page_url']) else 'unknown')
    source_manifest = read_jsonl(ROOT / "metadata/source_manifest.jsonl"); occurrences = defaultdict(list)
    for row in source_manifest: occurrences[row["sha256"]].append(row)
    duplicates = []
    version_by_hash = {v["sha256"]: v for v in versions}
    for digest, rows in occurrences.items():
        if len(rows) < 2 or digest not in version_by_hash: continue
        version = version_by_hash[digest]
        for row in rows[1:]: duplicates.append({"duplicate_group_id": f"EXACT-{digest[:12]}", "document_id": version["document_id"], "duplicate_type": "exact_duplicate", "compared_document_id": version["document_id"], "sha256_match": True, "recommended_action": "논리 버전 하나로 연결하고 출처 발생 경로 보존", "notes": row["archive_file"]})
    sync_front_matter(versions, documents)
    write_jsonl(ROOT / "metadata/versions.jsonl", versions); write_jsonl(ROOT / "metadata/documents.jsonl", documents); write_csv(ROOT / "metadata/conflicts.csv", conflicts, CONFLICT_FIELDS); write_csv(ROOT / "metadata/duplicates.csv", duplicates, DUPLICATE_FIELDS)
    print(json.dumps({"version_groups": len(groups), "versions": len(versions), "current_conflicts": len(conflicts)}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
