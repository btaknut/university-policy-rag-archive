"""고신뢰도 원본을 안정적 문서·버전 ID와 Markdown으로 정규화한다."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from common import DOCUMENT_FIELDS, ROOT, VERSION_FIELDS, candidate_documents, now, read_jsonl, stable_document_id, title_key, version_id, write_jsonl


def q(value: object) -> str:
    """YAML scalar를 JSON 호환 인용한다."""
    return "null" if value is None else json.dumps(value, ensure_ascii=False)


def main() -> int:
    source_manifest = read_jsonl(ROOT / "metadata/source_manifest.jsonl"); source_by_hash = defaultdict(list)
    for row in source_manifest: source_by_hash[row["sha256"]].append(row)
    extraction = {row["sha256"]: row for row in read_jsonl(ROOT / "metadata/extraction_results.jsonl")}
    candidates = [d for d in candidate_documents() if d["sha256"] in source_by_hash]
    coarse = defaultdict(list)
    for d in candidates: coarse[(d["document_type"], title_key(d["title"]))].append(d)
    grouped = defaultdict(list)
    for (dtype, key), items in coarse.items():
        departments = {x.get("department") for x in items if x.get("department")}
        for item in items:
            discriminator = item.get("department") or "" if len(departments) > 1 else ""
            grouped[(dtype, key, discriminator)].append(item)
    documents = []; versions = []; generated = now()
    for (dtype, _key, discriminator), items in sorted(grouped.items(), key=lambda x: x[0]):
        canonical = max((x.get("title") or "" for x in items), key=len); doc_id = stable_document_id(dtype, canonical, discriminator); group_id = f"VG-{hashlib.sha256((dtype + ':' + title_key(canonical) + ':' + discriminator).encode()).hexdigest()[:12]}"
        version_rows = []
        for item in sorted(items, key=lambda x: (x.get("revision_date") or "", x["sha256"])):
            vid = version_id(item.get("revision_date"), item["sha256"]); extract = extraction.get(item["sha256"], {"status": "unsupported", "text_file": None})
            status = "confirmed" if item.get("is_current") is True else "historical" if item.get("is_current") is False else "unknown"
            normalized = None
            if extract.get("text_file"):
                bucket = "regulations" if dtype == "regulation" else "guidelines"; target = ROOT / "corpus/normalized" / bucket / doc_id / f"{vid}.md"; target.parent.mkdir(parents=True, exist_ok=True)
                body = (ROOT / extract["text_file"]).read_text(encoding="utf-8")
                front = ["---", f"document_id: {q(doc_id)}", f"version_id: {q(vid)}", f"document_type: {q(dtype)}", f"title: {q(canonical)}", f"is_current: {str(item.get('is_current')).lower() if item.get('is_current') is not None else 'null'}", f"current_status: {q(status)}", f"enactment_date: {q(item.get('enactment_date'))}", f"revision_date: {q(item.get('revision_date'))}", f"effective_date: {q(item.get('effective_date'))}", f"issuing_organization: {q('국립한국교통대학교')}", f"department: {q(item.get('department'))}", f"source_url: {q(item.get('source_page_url') or item.get('original_url'))}", f"source_file: {q(source_by_hash[item['sha256']][0]['archive_file'])}", f"sha256: {q(item['sha256'])}", "access_level: public", "---", "", f"# {canonical}", ""]
                target.write_text("\n".join(front) + body.strip() + "\n", encoding="utf-8"); normalized = target.relative_to(ROOT).as_posix()
            version_rows.append({"version_id": vid, "document_id": doc_id, "version_group_id": group_id, "revision_date": item.get("revision_date"), "effective_date": item.get("effective_date"), "source_file": source_by_hash[item["sha256"]][0]["archive_file"], "normalized_file": normalized, "sha256": item["sha256"], "is_current": item.get("is_current"), "current_status": status, "previous_version_id": None, "next_version_id": None, "change_summary": None, "version_confidence": item.get("metadata_confidence"), "access_level": "public", "title": canonical, "document_type": dtype, "category": item.get("category"), "department": item.get("department"), "authority_level": "university_rule" if dtype == "regulation" else "university_guideline", "source_url": item.get("original_url"), "source_page_url": item.get("source_page_url"), "enactment_date": item.get("enactment_date"), "file_size": item.get("file_size"), "mime_type": item.get("mime_type"), "text_extraction_status": extract.get("status")})
        confirmed = [v for v in version_rows if v["is_current"] is True]
        latest = confirmed[0] if len(confirmed) == 1 else None; representative = latest or version_rows[-1]
        documents.append({"document_id": doc_id, "document_type": dtype, "title": canonical, "alternative_titles": sorted({x.get("title") for x in items if x.get("title") and x.get("title") != canonical}), "category": representative.get("category"), "subcategory": None, "issuing_organization": "국립한국교통대학교", "department": representative.get("department"), "authority_level": representative["authority_level"], "access_level": "public", "source_archive": "university_policy_archive", "source_url": representative.get("source_url"), "source_page_url": representative.get("source_page_url"), "original_filename": representative["source_file"].split("/")[-1], "source_relative_path": representative["source_file"], "normalized_relative_path": representative.get("normalized_file"), "enactment_date": representative.get("enactment_date"), "revision_date": representative.get("revision_date"), "effective_date": representative.get("effective_date"), "abolition_date": None, "current_status": "confirmed" if latest else "unknown", "is_current": True if latest else None, "version_group_id": group_id, "latest_version_id": latest["version_id"] if latest else None, "file_extension": "." + representative["source_file"].rsplit(".", 1)[-1].lower(), "mime_type": representative.get("mime_type"), "file_size": representative.get("file_size"), "sha256": representative["sha256"], "text_extraction_status": representative.get("text_extraction_status"), "metadata_confidence": representative.get("version_confidence"), "collected_at": None, "updated_at": generated, "notes": f"버전 {len(version_rows)}건; 최신본은 명시적 기존 메타데이터만 확정"})
        versions.extend(version_rows)
    write_jsonl(ROOT / "metadata/documents.jsonl", documents); write_jsonl(ROOT / "metadata/versions.jsonl", versions)
    print(json.dumps({"documents": len(documents), "versions": len(versions), "normalized": sum(bool(v["normalized_file"]) for v in versions)}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
