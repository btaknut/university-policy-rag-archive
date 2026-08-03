"""한국어 법규 조문 경계를 보존해 인용 가능한 RAG 청크를 생성한다."""
from __future__ import annotations

import hashlib
import json
import re

from common import ROOT, read_jsonl, strip_front_matter, token_estimate, write_jsonl

ARTICLE = re.compile(r"^(?:#{1,6}\s*)?(제\s*\d+\s*조(?:의\s*\d+)?)(?:\s*\(([^)]+)\))?", re.M)
HEADING = re.compile(r"^(#{1,3})\s+(.+)$")


def split_article(text: str) -> list[tuple[str | None, str | None, str]]:
    """문서를 조문 단위로 나누고 서문·부칙도 독립 보존한다."""
    matches = list(ARTICLE.finditer(text)); out = []
    if not matches: return [(None, None, text.strip())] if text.strip() else []
    if text[:matches[0].start()].strip(): out.append((None, None, text[:matches[0].start()].strip()))
    for i, match in enumerate(matches): out.append((re.sub(r"\s+", "", match.group(1)), match.group(2), text[match.start():(matches[i+1].start() if i+1 < len(matches) else len(text))].strip()))
    return out


def divide_long(text: str, target: int = 650, maximum: int = 850) -> list[str]:
    """같은 조문 내부에서만 빈 줄 의미 단위로 분할한다."""
    if token_estimate(text) <= maximum: return [text]
    def bisect_oversized(value: str) -> list[str]:
        if token_estimate(value) <= maximum: return [value]
        middle = len(value) // 2; candidates = [value.rfind("\n", 0, middle), value.rfind(" ", 0, middle), value.find("\n", middle), value.find(" ", middle)]
        cut = min((x for x in candidates if x > len(value) // 4), key=lambda x: abs(x-middle), default=middle)
        if cut <= 0 or cut >= len(value): cut = middle
        return bisect_oversized(value[:cut].strip()) + bisect_oversized(value[cut:].strip())
    raw_parts = re.split(r"\n\s*\n", text); parts = []
    for raw in raw_parts: parts.extend(bisect_oversized(raw))
    chunks = []; current = []
    for part in parts:
        if current and token_estimate("\n\n".join(current + [part])) > target: chunks.append("\n\n".join(current)); current = [part]
        else: current.append(part)
    if current: chunks.append("\n\n".join(current))
    return chunks


def main() -> int:
    versions = read_jsonl(ROOT / "metadata/versions.jsonl"); chunks = []
    for version in versions:
        if version.get("access_level") != "public" or not version.get("normalized_file"): continue
        path = ROOT / version["normalized_file"]; text = strip_front_matter(path.read_text(encoding="utf-8")); headings = [m.group(2) for line in text.splitlines() if (m := HEADING.match(line))]
        for article_index, (article_no, article_title, article_text) in enumerate(split_article(text)):
            for subindex, piece in enumerate(divide_long(article_text)):
                idx = len([c for c in chunks if c["version_id"] == version["version_id"]]); location = article_no or f"section-{article_index+1}"; chunk_id = f"CHK-{version['version_id']}-{article_index+1:04d}-{re.sub(r'[^0-9A-Za-z가-힣-]', '', location)}-{subindex+1:03d}"
                section_path = " > ".join(headings[:2]) if headings else None; context = f"문서명: {version['title']}\n유형: {'규정' if version['document_type']=='regulation' else '지침'}\n위치: {section_path or ''}{' > ' if section_path and article_no else ''}{article_no or ''} {article_title or ''}\n본문: {piece}"
                citation = version["title"] + (f" {article_no}" if article_no else "") + (f", {version['revision_date']} 개정" if version.get("revision_date") else "")
                chunks.append({"chunk_id": chunk_id, "document_id": version["document_id"], "version_id": version["version_id"], "version_group_id": version["version_group_id"], "document_type": version["document_type"], "title": version["title"], "category": version.get("category"), "department": version.get("department"), "authority_level": version.get("authority_level"), "access_level": version["access_level"], "is_current": version.get("is_current"), "current_status": version.get("current_status"), "enactment_date": version.get("enactment_date"), "revision_date": version.get("revision_date"), "effective_date": version.get("effective_date"), "section_path": section_path, "chapter": headings[0] if headings else None, "section": headings[1] if len(headings)>1 else None, "article_no": article_no, "article_title": article_title, "paragraph_no": None, "item_no": None, "appendix_no": None, "page_start": None, "page_end": None, "chunk_index": idx, "text": piece, "text_for_embedding": context, "token_count": token_estimate(context), "source_url": version.get("source_page_url") or version.get("source_url"), "source_file": version["source_file"], "normalized_file": version["normalized_file"], "sha256": version["sha256"], "citation_label": citation})
    write_jsonl(ROOT / "rag/chunks.jsonl", chunks); print(json.dumps({"chunks": len(chunks), "documents_with_chunks": len({c['document_id'] for c in chunks})}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
