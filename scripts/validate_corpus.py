"""코퍼스 경로·해시·스키마·버전·파생 산출물을 종합 검증한다."""
from __future__ import annotations
import json, re
from collections import Counter, defaultdict
from jsonschema import Draft202012Validator
import yaml
from common import ROOT, SOURCE_ARCHIVE, read_jsonl, sha256_file, verify_content_or_lfs_pointer

def main() -> int:
    docs=read_jsonl(ROOT/"metadata/documents.jsonl"); versions=read_jsonl(ROOT/"metadata/versions.jsonl"); chunks=read_jsonl(ROOT/"rag/chunks.jsonl"); manifest=read_jsonl(ROOT/"metadata/source_manifest.jsonl")
    checks=[]
    def add(name,status,detail): checks.append((name,status,detail))
    bad_hash=[m["archive_file"] for m in manifest if not verify_content_or_lfs_pointer(ROOT/m["archive_file"],m["sha256"])]
    add("원본 사본 SHA-256","PASS" if not bad_hash else "FAIL",f"불일치/누락 {len(bad_hash)}건")
    if SOURCE_ARCHIVE.exists():
        legacy=[m for m in manifest if m.get("origin_type","legacy_archive")=="legacy_archive"]
        changed=[m["source_file"] for m in legacy if not (SOURCE_ARCHIVE/m["source_file"]).exists() or sha256_file(SOURCE_ARCHIVE/m["source_file"])!=m["sha256"]]
        add("읽기 전용 통합 아카이브 보존","PASS" if not changed else "FAIL",f"변경/누락 {len(changed)}건")
    else: add("읽기 전용 통합 아카이브 보존","WARNING","로컬 레거시 원본 미설정; source manifest와 LFS oid 검증으로 대체")
    for label,rows,key in (("document_id",docs,"document_id"),("version_id",versions,"version_id"),("chunk_id",chunks,"chunk_id")):
        count=Counter(r.get(key) for r in rows); duplicate=[v for v,n in count.items() if n>1]
        add(f"{label} 고유성","PASS" if not duplicate else "FAIL",f"중복 {len(duplicate)}건")
    doc_ids={d["document_id"] for d in docs}; version_ids={v["version_id"] for v in versions}
    orphan=[c["chunk_id"] for c in chunks if c["document_id"] not in doc_ids or c["version_id"] not in version_ids]
    add("청크 원문 연결","PASS" if not orphan else "FAIL",f"고아 청크 {len(orphan)}건")
    by_version={v["version_id"]:v for v in versions}; bad_refs=[]; asymmetric=[]; cycles=[]
    for version in versions:
        for field,reverse in (("previous_version_id","next_version_id"),("next_version_id","previous_version_id")):
            linked=version.get(field)
            if not linked: continue
            target=by_version.get(linked)
            if not target or target.get("document_id")!=version["document_id"]: bad_refs.append(f"{version['version_id']}:{field}")
            elif target.get(reverse)!=version["version_id"]: asymmetric.append(f"{version['version_id']}:{field}")
    add("버전 참조 무결성","PASS" if not bad_refs and not asymmetric else "FAIL",f"누락/타문서 {len(bad_refs)}건, 비대칭 {len(asymmetric)}건")
    for version in versions:
        seen=set(); current_id=version["version_id"]
        while current_id and current_id in by_version:
            if current_id in seen: cycles.append(version["version_id"]); break
            seen.add(current_id); current_id=by_version[current_id].get("next_version_id")
    add("버전 체인 순환","PASS" if not cycles else "FAIL",f"순환 시작점 {len(set(cycles))}건")
    manifest_links={(m["archive_file"],m["sha256"]) for m in manifest}; unlinked_versions=[v["version_id"] for v in versions if (v["source_file"],v["sha256"]) not in manifest_links]
    add("버전-source manifest 연결","PASS" if not unlinked_versions else "FAIL",f"역참조 누락 {len(unlinked_versions)}건")
    latest_bad=[d["document_id"] for d in docs if not d.get("latest_version_id") or by_version.get(d.get("latest_version_id"),{}).get("document_id")!=d["document_id"]]
    add("latest_version_id 연결","PASS" if not latest_bad else "WARNING",f"불일치/누락 {len(latest_bad)}건" + ("; 별도 PR B 보정 대상" if latest_bad else ""))
    missing=[v["version_id"] for v in versions if not (ROOT/v["source_file"]).exists() or (v.get("normalized_file") and not (ROOT/v["normalized_file"]).exists())]
    add("메타데이터 경로","PASS" if not missing else "FAIL",f"누락 {len(missing)}건")
    hwp=[v for v in versions if v["source_file"].lower().endswith(".hwp")]
    def pdf_ok(v): return bool(v.get("pdf_relative_path") and v.get("pdf_sha256") and v.get("pdf_pages") and v.get("pdf_conversion_status")=="success" and verify_content_or_lfs_pointer(ROOT/v["pdf_relative_path"],v["pdf_sha256"]))
    def portable_ok(v):
        p=ROOT/v["normalized_file"] if v.get("normalized_file") else None
        return bool(v.get("portable_conversion_status")=="success" and v.get("portable_extraction_tool")=="unhwp" and v.get("portable_extraction_version") and v.get("portable_markdown_sha256") and p and p.is_file() and sha256_file(p)==v["portable_markdown_sha256"] and int(v.get("portable_text_chars") or 0)>=200 and int(v.get("portable_hangul_chars") or 0)>=80 and float(v.get("portable_hangul_ratio") or 0)>=.15 and int(v.get("portable_replacement_chars") or 0)==0)
    native=sum(pdf_ok(v) for v in hwp); portable=sum(portable_ok(v) for v in hwp); incomplete=[v["version_id"] for v in hwp if not pdf_ok(v) and not portable_ok(v)]
    claimed_pdf=[v["version_id"] for v in hwp if (v.get("pdf_relative_path") or v.get("pdf_sha256") or v.get("pdf_conversion_status")=="success") and not pdf_ok(v)]
    claimed_portable=[v["version_id"] for v in hwp if v.get("portable_conversion_status") and not portable_ok(v)]
    add("HWP 파생본 완전성","PASS" if not incomplete and not claimed_pdf and not claimed_portable else "FAIL",f"한컴 PDF {native}건, portable Markdown {portable}건, 누락 {len(incomplete)}건, PDF 오류 {len(claimed_pdf)}건, portable 오류 {len(claimed_portable)}건")
    current=defaultdict(list)
    for v in versions:
        if v.get("is_current") is True: current[v["document_id"]].append(v)
    multiple={k:v for k,v in current.items() if len(v)>1}; add("최신 확보본 단일성","PASS" if not multiple else "FAIL",f"복수 is_current {len(multiple)}문서")
    empty=[c["chunk_id"] for c in chunks if not c.get("text","").strip()]; long=[c["chunk_id"] for c in chunks if c.get("token_count",0)>1200]
    add("빈 청크","PASS" if not empty else "FAIL",f"빈 청크 {len(empty)}건"); add("최대 청크 크기","PASS" if not long else "FAIL",f"1,200 초과 {len(long)}건")
    restricted=[c["chunk_id"] for c in chunks if c.get("access_level")!="public"]; add("restricted 청크 제외","PASS" if not restricted else "FAIL",f"위반 {len(restricted)}건")
    citations=[c["chunk_id"] for c in chunks if not all(c.get(k) for k in ("title","source_file","sha256","citation_label"))]; add("인용 필드","PASS" if not citations else "FAIL",f"누락 {len(citations)}건")
    schema_errors=[]
    datasets=(("document.schema.json",docs),("version.schema.json",versions),("chunk.schema.json",chunks),("source-manifest.schema.json",manifest),("portable-hwp-manifest.schema.json",read_jsonl(ROOT/"metadata/portable_hwp_manifest.jsonl")))
    for filename,rows in datasets:
        validator=Draft202012Validator(json.loads((ROOT/"schemas"/filename).read_text(encoding="utf-8")))
        for index,row in enumerate(rows): schema_errors.extend(f"{filename}[{index}]: {e.message}" for e in validator.iter_errors(row))
    batch_validator=Draft202012Validator(json.loads((ROOT/"schemas/official-update-batch.schema.json").read_text(encoding="utf-8")))
    for path in sorted((ROOT/"reports").glob("*_official_update_batch_*.json")): schema_errors.extend(f"{path.name}: {e.message}" for e in batch_validator.iter_errors(json.loads(path.read_text(encoding="utf-8"))))
    corpus=json.loads((ROOT/"rag/corpus_manifest.json").read_text(encoding="utf-8")); corpus_validator=Draft202012Validator(json.loads((ROOT/"schemas/corpus-manifest.schema.json").read_text(encoding="utf-8")))
    schema_errors.extend(f"corpus_manifest: {e.message}" for e in corpus_validator.iter_errors(corpus))
    add("JSON Schema","PASS" if not schema_errors else "FAIL",f"오류 {len(schema_errors)}건"+("; "+"; ".join(schema_errors[:5]) if schema_errors else ""))
    current_docs=read_jsonl(ROOT/"metadata/current_documents.jsonl"); expected_current=[d for d in docs if d.get("is_current") is True and d.get("latest_version_id")]
    add("current_documents 부분집합","PASS" if current_docs==expected_current else "FAIL",f"기대 {len(expected_current)}건, 실제 {len(current_docs)}건")
    latest_path=ROOT/"metadata/latest_documents.jsonl"; latest_docs=read_jsonl(latest_path); expected_latest=[d for d in docs if d.get("latest_version_id")]
    add("latest_documents 부분집합",("PASS" if latest_docs==expected_latest else "FAIL") if latest_path.exists() else "WARNING",f"기대 {len(expected_latest)}건, 실제 {len(latest_docs)}건" + ("; PR B 생성 대상" if not latest_path.exists() else ""))
    catalog=read_jsonl(ROOT/"rag/document_catalog.jsonl"); add("document_catalog 일치","PASS" if catalog==docs else "FAIL",f"문서 {len(docs)}건, 카탈로그 {len(catalog)}건")
    manifest_ok=corpus.get("documents")==len(docs) and corpus.get("versions")==len(versions) and corpus.get("chunks")==len(chunks) and corpus.get("sha256",{}).get("documents")==sha256_file(ROOT/"metadata/documents.jsonl") and corpus.get("sha256",{}).get("chunks")==sha256_file(ROOT/"rag/chunks.jsonl")
    add("corpus_manifest 수량·해시","PASS" if manifest_ok else "FAIL","기준 데이터와 일치" if manifest_ok else "수량 또는 SHA-256 불일치")
    semantic_missing=sum(1 for v in versions if not all(k in v for k in ("is_latest_version","validity_status","status_confidence","source_url_quality")))
    add("시행상태 신규 필드","PASS" if not semantic_missing else "WARNING",f"미보강 버전 {semantic_missing}건" + ("; PR B에서 추정 없이 이관" if semantic_missing else ""))
    front_errors=[]
    for version in versions:
        if not version.get("normalized_file"): continue
        path=ROOT/version["normalized_file"]
        if not path.is_file(): continue
        match=re.match(r"^---\s*\n(.*?)\n---\s*\n",path.read_text(encoding="utf-8"),re.S)
        if not match: front_errors.append(f"{version['version_id']}:missing"); continue
        front=yaml.safe_load(match.group(1)) or {}
        for key in ("document_id","version_id","title","sha256","is_current","current_status"):
            if key in front and front.get(key)!=version.get(key): front_errors.append(f"{version['version_id']}:{key}")
    add("normalized front matter","PASS" if not front_errors else "WARNING",f"불일치/누락 {len(front_errors)}건" + ("; PR B 재생성 대상" if front_errors else ""))
    export=ROOT/"rag/exports/university_policy_rag_bundle/chunks.jsonl"; duplicate=export.stat().st_size if export.exists() else 0
    export_state="현재 청크와 동일" if duplicate and sha256_file(export)==sha256_file(ROOT/"rag/chunks.jsonl") else "현재 청크와 불일치(오래된 bundle)"
    add("대용량 중복 export","PASS" if not duplicate else "WARNING",f"중복 산출물 {duplicate:,} bytes, {export_state}; 소비 경로 전환 후 별도 PR에서 제거")
    normalized_missing=sum(not v.get("normalized_file") for v in versions); add("텍스트 미추출 버전","WARNING" if normalized_missing else "PASS",f"정규화 없음 {normalized_missing}건")
    counts=Counter(status for _,status,_ in checks); lines=["# 코퍼스 검증 보고서","",f"- PASS: {counts['PASS']}",f"- WARNING: {counts['WARNING']}",f"- FAIL: {counts['FAIL']}",""]
    for name,status,detail in checks: lines += [f"## {status} — {name}","",detail,""]
    (ROOT/"reports").mkdir(exist_ok=True); (ROOT/"reports/corpus_validation.md").write_text("\n".join(lines),encoding="utf-8",newline="\n")
    print(json.dumps(dict(counts),ensure_ascii=False)); return 1 if counts["FAIL"] else 0

if __name__=="__main__": raise SystemExit(main())
