"""기존 정규화 결과를 재사용하고 지원 바이너리에서 텍스트를 추출한다."""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from common import ROOT, SOURCE_ARCHIVE, candidate_documents, read_jsonl, strip_front_matter, write_jsonl


def legacy_text_index() -> dict[str, Path]:
    """기존 규정 ID·지침 ID 메타데이터에서 첨부 해시→정규화 Markdown을 연결한다."""
    index: dict[str, Path] = {}; reg = SOURCE_ARCHIVE / "data/raw/regulations"
    for meta in (reg / "metadata").glob("*.json"):
        try: obj = json.loads(meta.read_text(encoding="utf-8-sig"))
        except Exception: continue
        normalized = next(iter((reg / "normalized/markdown").glob(f"{obj.get('regulation_id')}_*.md")), None)
        if normalized:
            for att in obj.get("attachments", []):
                if att.get("sha256"): index[att["sha256"]] = normalized
    gdl = SOURCE_ARCHIVE / "data/raw/guidelines/sources/university_guidelines"; normalized_dir = gdl / "normalized/markdown"
    for meta in (gdl / "archive").rglob("version_metadata.json"):
        try: obj = json.loads(meta.read_text(encoding="utf-8-sig"))
        except Exception: continue
        normalized = normalized_dir / f"{obj.get('guideline_id')}.md"
        if normalized.exists():
            for att in obj.get("attachments", []):
                if att.get("sha256") and att.get("version_status") == "active": index[att["sha256"]] = normalized
    return index


def direct_extract(path: Path) -> tuple[str | None, str]:
    """PDF/DOCX/HWPX의 직접 추출. HWP는 보수적으로 미지원 처리한다."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        pages = []
        for i, page in enumerate(PdfReader(str(path)).pages, 1): pages.append(f"\n<!-- page: {i} -->\n" + (page.extract_text() or ""))
        text = "\n".join(pages).strip(); return (text, "success") if text else (None, "needs_ocr")
    if ext == ".docx":
        from docx import Document
        doc = Document(str(path)); return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip()), "success"
    if ext == ".hwpx":
        chunks = []
        with zipfile.ZipFile(path) as zf:
            for name in sorted(n for n in zf.namelist() if re.match(r"Contents/section\d+\.xml$", n, re.I)):
                root = ElementTree.fromstring(zf.read(name)); chunks.extend(e.text for e in root.iter() if e.tag.endswith("}t") and e.text)
        return ("\n".join(chunks), "success") if chunks else (None, "failed")
    return None, "unsupported"


def main() -> int:
    legacy = legacy_text_index(); manifest = read_jsonl(ROOT / "metadata/source_manifest.jsonl"); by_hash = {m["sha256"]: ROOT / m["archive_file"] for m in manifest}
    results = []; counts: dict[str, int] = {}
    for doc in candidate_documents():
        if doc["sha256"] not in by_hash: continue
        text = None; status = "unsupported"; method = None
        if doc["sha256"] in legacy:
            text = strip_front_matter(legacy[doc["sha256"]].read_text(encoding="utf-8", errors="replace")); status = "success"; method = "legacy_normalized"
        else:
            try: text, status = direct_extract(by_hash[doc["sha256"]]); method = "direct"
            except Exception as exc: status = "failed"; method = f"error:{exc}"
        output = None
        if text and text.strip():
            output_path = ROOT / "temp/extracted" / f"{doc['document_id']}.md"; output_path.parent.mkdir(parents=True, exist_ok=True); output_path.write_text(text.strip(), encoding="utf-8"); output = output_path.relative_to(ROOT).as_posix()
        results.append({"legacy_document_id": doc["document_id"], "sha256": doc["sha256"], "status": status, "method": method, "text_file": output}); counts[status] = counts.get(status, 0) + 1
    write_jsonl(ROOT / "metadata/extraction_results.jsonl", results); print(json.dumps(counts, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
