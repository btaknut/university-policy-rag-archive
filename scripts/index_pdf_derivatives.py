"""HWP 파생 PDF를 검증하고 메타데이터·미추출 Markdown을 갱신한다."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from common import ROOT, now, read_jsonl, sha256_file, write_jsonl


def yaml_value(value: object) -> str:
    """YAML front matter용 JSON 호환 값."""
    return "null" if value is None else json.dumps(value, ensure_ascii=False)


def main() -> int:
    manifest_rows = []
    paths = sorted((ROOT / "metadata").glob("hwp_pdf_manifest*.jsonl"), key=lambda p: (p.name == "hwp_pdf_manifest.jsonl", p.name))
    for path in paths: manifest_rows.extend(read_jsonl(path))
    manifest = list({m["version_id"]: m for m in manifest_rows}.values())
    versions = read_jsonl(ROOT / "metadata/versions.jsonl")
    documents = read_jsonl(ROOT / "metadata/documents.jsonl")
    manifest_by_version = {m["version_id"]: m for m in manifest if m.get("status") in {"converted", "reused"} and m.get("pdf_file")}
    counts: Counter[str] = Counter(); failures = []
    for version in versions:
        item = manifest_by_version.get(version["version_id"])
        if not item: continue
        pdf_path = ROOT / item["pdf_file"]
        try:
            reader = PdfReader(str(pdf_path))
            page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
            text_chars = sum(len(t) for t in page_texts)
            version["pdf_relative_path"] = pdf_path.relative_to(ROOT).as_posix()
            version["pdf_sha256"] = sha256_file(pdf_path)
            version["pdf_pages"] = len(reader.pages)
            version["pdf_text_chars"] = text_chars
            version["pdf_conversion_status"] = "success" if reader.pages else "failed"
            version["pdf_generated_at"] = now()
            if not version.get("normalized_file") and text_chars:
                bucket = "regulations" if version["document_type"] == "regulation" else "guidelines"
                target = ROOT / "corpus/normalized" / bucket / version["document_id"] / f"{version['version_id']}.md"
                target.parent.mkdir(parents=True, exist_ok=True)
                front = ["---", f"document_id: {yaml_value(version['document_id'])}", f"version_id: {yaml_value(version['version_id'])}", f"document_type: {yaml_value(version['document_type'])}", f"title: {yaml_value(version['title'])}", f"is_current: {str(version.get('is_current')).lower() if version.get('is_current') is not None else 'null'}", f"current_status: {yaml_value(version.get('current_status'))}", f"revision_date: {yaml_value(version.get('revision_date'))}", f"source_file: {yaml_value(version['source_file'])}", f"pdf_file: {yaml_value(version['pdf_relative_path'])}", f"sha256: {yaml_value(version['sha256'])}", "access_level: public", "extraction_method: hancom_pdf_text_layer", "---", "", f"# {version['title']}", ""]
                body = []
                for index, text in enumerate(page_texts, 1):
                    if text: body += [f"<!-- page: {index} -->", "", text, ""]
                target.write_text("\n".join(front + body), encoding="utf-8")
                version["normalized_file"] = target.relative_to(ROOT).as_posix()
                version["text_extraction_status"] = "success_from_pdf"
                counts["new_markdown"] += 1
            elif not text_chars:
                version["text_extraction_status"] = "needs_ocr"
                counts["needs_ocr"] += 1
            counts["validated_pdf"] += 1
        except Exception as exc:
            version["pdf_conversion_status"] = "failed_validation"
            failures.append({"version_id": version["version_id"], "pdf_file": item.get("pdf_file"), "error": str(exc)})
            counts["failed"] += 1

    by_version = {v["version_id"]: v for v in versions}
    for doc in documents:
        latest = by_version.get(doc.get("latest_version_id"))
        if latest and latest.get("pdf_relative_path"):
            doc["pdf_relative_path"] = latest["pdf_relative_path"]
            doc["pdf_conversion_status"] = latest.get("pdf_conversion_status")
        elif any(v["document_id"] == doc["document_id"] and v.get("pdf_relative_path") for v in versions):
            doc["pdf_conversion_status"] = "available_for_versions"

    write_jsonl(ROOT / "metadata/versions.jsonl", versions)
    write_jsonl(ROOT / "metadata/documents.jsonl", documents)
    write_jsonl(ROOT / "metadata/hwp_pdf_manifest.jsonl", sorted(manifest, key=lambda x: x["version_id"]))
    report = ["# HWP PDF 변환 보고서", "", f"- PDF 검증 성공: {counts['validated_pdf']:,}건", f"- 신규 Markdown 추출: {counts['new_markdown']:,}건", f"- OCR 필요: {counts['needs_ocr']:,}건", f"- 검증 실패: {counts['failed']:,}건", "", "원본 HWP는 수정하지 않았다. PDF는 한컴오피스 2020의 PDF 저장 기능으로 생성했고 pypdf로 페이지 구조와 텍스트 레이어를 다시 열어 검증했다."]
    if failures:
        report += ["", "## 실패", ""] + [f"- `{x['version_id']}`: {x['error']}" for x in failures[:100]]
    (ROOT / "reports/hwp_pdf_conversion.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(dict(counts), ensure_ascii=False)); return 1 if failures else 0


if __name__ == "__main__": raise SystemExit(main())
