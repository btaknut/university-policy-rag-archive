"""한국어 법규 조문 경계를 보존해 인용 가능한 RAG 청크를 생성한다."""
from __future__ import annotations

import hashlib
import json
import re

from common import ROOT, load_yaml, read_jsonl, strip_front_matter, token_estimate, write_jsonl
from search_lib import classify_section

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


def overlap_tail(text: str, budget: int) -> str:
    """이전 청크 끝에서 설정 토큰 이하의 결정적 문맥을 가져온다."""
    units=re.findall(r"\S+\s*",text); selected=[]
    for unit in reversed(units):
        if selected and token_estimate("".join(reversed(selected+[unit])))>budget: break
        selected.append(unit)
    return "".join(reversed(selected)).strip()


def _heading_for_offset(text: str, offset: int) -> list[str]:
    """현재 위치 이전에 실제로 등장한 Markdown heading 계층만 반환한다."""
    stack: list[str] = []
    for match in re.finditer(r"^(#{1,6})\s+(.+)$", text[:offset], re.M):
        level=len(match.group(1)); stack=stack[:level-1]; stack.append(match.group(2).strip())
    return stack


def main() -> int:
    config=load_yaml(ROOT/"config/chunking.yaml"); target=int(config["target_tokens"]); maximum=int(config["max_tokens"]); overlap=int(config.get("overlap_tokens",0))
    versions = read_jsonl(ROOT / "metadata/versions.jsonl"); docs={d["document_id"]:d for d in read_jsonl(ROOT/"metadata/documents.jsonl")}; chunks = []
    for version in versions:
        if version.get("access_level") != "public" or not version.get("normalized_file"): continue
        path = ROOT / version["normalized_file"]; text = strip_front_matter(path.read_text(encoding="utf-8")); document=docs.get(version["document_id"],{})
        cursor=0
        for article_index, (article_no, article_title, article_text) in enumerate(split_article(text)):
            offset=text.find(article_text,cursor); cursor=max(cursor,offset+len(article_text)); headings=_heading_for_offset(text,max(offset,0))
            pieces=divide_long(article_text,target,maximum)
            for subindex, raw_piece in enumerate(pieces):
                capacity=max(0,maximum-token_estimate(raw_piece)); prefix=overlap_tail(pieces[subindex-1],min(overlap,capacity)) if subindex else ""
                piece=(prefix+"\n\n"+raw_piece).strip() if prefix else raw_piece
                idx = len([c for c in chunks if c["version_id"] == version["version_id"]]); location = article_no or f"section-{article_index+1}"; chunk_id = f"CHK-{version['version_id']}-{article_index+1:04d}-{re.sub(r'[^0-9A-Za-z가-힣-]', '', location)}-{subindex+1:03d}"
                section_path = " > ".join(headings) if headings else None; section_kind,retrieval_scope,normative_status=classify_section(piece,section_path)
                context = f"문서명: {version['title']}\n유형: {'규정' if version['document_type']=='regulation' else '지침'}\n위치: {section_path or ''}{' > ' if section_path and article_no else ''}{article_no or ''} {article_title or ''}\n본문: {piece}"
                citation = version["title"] + (f" {article_no}" if article_no else "") + (f", {version['revision_date']} 개정" if version.get("revision_date") else "")
                paragraph=(re.search(r"(?<![가-힣])[①②③④⑤⑥⑦⑧⑨⑩]",piece) or re.search(r"^\s*(\d+)항",piece,re.M)); item=re.search(r"^\s*(\d+)\s*[.)]",piece,re.M); appendix=re.search(r"(별\s*(?:표|지)(?:\s*제?\s*\d+\s*호?)?)",piece)
                chunks.append({"chunk_id": chunk_id, "chunk_schema_version":"2.0", "document_id": version["document_id"], "version_id": version["version_id"], "version_group_id": version["version_group_id"], "document_type": version["document_type"], "title": version["title"], "category": version.get("category"), "department": version.get("department"), "authority_level": version.get("authority_level"), "access_level": version["access_level"], "is_current": version.get("is_current"), "current_status": version.get("current_status"), "is_latest_version":version.get("version_id")==document.get("latest_version_id"), "validity_status":version.get("validity_status","unknown"), "status_confidence":version.get("status_confidence","unknown"), "enactment_date": version.get("enactment_date"), "revision_date": version.get("revision_date"), "effective_date": version.get("effective_date"), "section_path": section_path, "section_kind":section_kind, "retrieval_scope":retrieval_scope, "normative_status":normative_status, "chapter": headings[0] if headings else None, "section": headings[-1] if headings else None, "article_no": article_no, "article_title": article_title, "paragraph_no": paragraph.group(0).strip() if paragraph else None, "item_no": item.group(1) if item else None, "appendix_no": re.sub(r"\s+","",appendix.group(1)) if appendix else None, "page_start": None, "page_end": None, "chunk_index": idx, "text": piece, "text_for_embedding": context, "token_count": token_estimate(context), "source_url": version.get("source_page_url") or version.get("source_url"), "source_file": version["source_file"], "normalized_file": version["normalized_file"], "sha256": version["sha256"], "citation_label": citation})
    write_jsonl(ROOT / "rag/chunks.jsonl", chunks); print(json.dumps({"chunks": len(chunks), "documents_with_chunks": len({c['document_id'] for c in chunks})}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
