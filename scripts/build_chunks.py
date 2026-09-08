"""한국어 법규 청크를 안전한 증분 또는 명시적 전체 재생성 모드로 만든다."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from common import ROOT, load_yaml, read_jsonl, strip_front_matter, token_estimate, write_jsonl
from search_lib import classify_section

ARTICLE = re.compile(r"^(?:#{1,6}\s*)?(제\s*\d+\s*조(?:의\s*\d+)?)(?:\s*\(([^)]+)\))?", re.M)


def split_article(text: str) -> list[tuple[str | None, str | None, str]]:
    matches = list(ARTICLE.finditer(text))
    out: list[tuple[str | None, str | None, str]] = []
    if not matches:
        return [(None, None, text.strip())] if text.strip() else []
    if text[: matches[0].start()].strip():
        out.append((None, None, text[: matches[0].start()].strip()))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        out.append((re.sub(r"\s+", "", match.group(1)), match.group(2), text[match.start() : end].strip()))
    return out


def divide_long(text: str, target: int = 650, maximum: int = 850) -> list[str]:
    if token_estimate(text) <= maximum:
        return [text]

    def bisect_oversized(value: str) -> list[str]:
        if token_estimate(value) <= maximum:
            return [value]
        middle = len(value) // 2
        candidates = [value.rfind("\n", 0, middle), value.rfind(" ", 0, middle), value.find("\n", middle), value.find(" ", middle)]
        cut = min((position for position in candidates if position > len(value) // 4), key=lambda position: abs(position - middle), default=middle)
        if cut <= 0 or cut >= len(value):
            cut = middle
        return bisect_oversized(value[:cut].strip()) + bisect_oversized(value[cut:].strip())

    parts: list[str] = []
    for raw in re.split(r"\n\s*\n", text):
        parts.extend(bisect_oversized(raw))
    chunks: list[str] = []
    current: list[str] = []
    for part in parts:
        if current and token_estimate("\n\n".join(current + [part])) > target:
            chunks.append("\n\n".join(current))
            current = [part]
        else:
            current.append(part)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def overlap_tail(text: str, budget: int) -> str:
    if budget <= 0:
        return ""
    units = re.findall(r"\S+\s*", text)
    selected: list[str] = []
    for unit in reversed(units):
        if token_estimate("".join(reversed(selected + [unit]))) > budget:
            break
        selected.append(unit)
    return "".join(reversed(selected)).strip()


def _heading_for_offset(text: str, offset: int) -> list[str]:
    stack: list[str] = []
    for match in re.finditer(r"^(#{1,6})\s+(.+)$", text[:offset], re.M):
        level = len(match.group(1))
        stack = stack[: level - 1]
        stack.append(match.group(2).strip())
    return stack


def _citation(version: dict[str, Any], article_no: str | None) -> str:
    value = version["title"] + (f" {article_no}" if article_no else "")
    return value + (f", {version['revision_date']} 개정" if version.get("revision_date") else "")


def _embedding_text(version: dict[str, Any], chunk: dict[str, Any]) -> str:
    section_path = chunk.get("section_path") or ""
    article_no = chunk.get("article_no") or ""
    article_title = chunk.get("article_title") or ""
    separator = " > " if section_path and article_no else ""
    document_type = "규정" if version["document_type"] == "regulation" else "지침"
    return f"문서명: {version['title']}\n유형: {document_type}\n위치: {section_path}{separator}{article_no} {article_title}\n본문: {chunk['text']}"


def _refresh_chunk(chunk: dict[str, Any], version: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    """경계·ID·본문은 보존하고 현재 메타데이터와 검색 문맥만 갱신한다."""
    refreshed = dict(chunk)
    section_kind, retrieval_scope, normative_status = classify_section(chunk["text"], chunk.get("section_path"))
    refreshed.update({
        "chunk_schema_version": "2.0", "document_id": version["document_id"], "version_id": version["version_id"],
        "version_group_id": version["version_group_id"], "document_type": version["document_type"], "title": version["title"],
        "category": version.get("category"), "department": version.get("department"), "authority_level": version.get("authority_level"),
        "access_level": version["access_level"], "is_current": version.get("is_current"), "current_status": version.get("current_status"),
        "is_latest_version": version["version_id"] == document.get("latest_version_id"),
        "validity_status": version.get("validity_status", "unknown"), "status_confidence": version.get("status_confidence", "unknown"),
        "enactment_date": version.get("enactment_date"), "revision_date": version.get("revision_date"), "effective_date": version.get("effective_date"),
        "section_kind": section_kind, "retrieval_scope": retrieval_scope, "normative_status": normative_status,
        "source_url": version.get("source_page_url") or version.get("source_url"), "source_file": version["source_file"],
        "normalized_file": version["normalized_file"], "sha256": version["sha256"], "citation_label": _citation(version, chunk.get("article_no")),
    })
    refreshed["text_for_embedding"] = _embedding_text(version, refreshed)
    refreshed["token_count"] = token_estimate(refreshed["text_for_embedding"])
    return refreshed


def generate_version_chunks(root: Path, version: dict[str, Any], document: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    text = strip_front_matter((root / version["normalized_file"]).read_text(encoding="utf-8"))
    target, maximum, overlap = int(config["target_tokens"]), int(config["max_tokens"]), int(config.get("overlap_tokens", 0))
    chunks: list[dict[str, Any]] = []
    cursor = 0
    for article_index, (article_no, article_title, article_text) in enumerate(split_article(text)):
        offset = text.find(article_text, cursor)
        cursor = max(cursor, offset + len(article_text))
        headings = _heading_for_offset(text, max(offset, 0))
        context_probe = {
            "section_path": " > ".join(headings) if headings else None,
            "article_no": article_no,
            "article_title": article_title,
            "text": "",
        }
        context_overhead = max(0, token_estimate(_embedding_text(version, context_probe)) - 1)
        pieces = divide_long(
            article_text,
            max(1, target - context_overhead),
            max(1, maximum - context_overhead),
        )
        for subindex, raw_piece in enumerate(pieces):
            location = article_no or f"section-{article_index + 1}"
            chunk_id = f"CHK-{version['version_id']}-{article_index + 1:04d}-{re.sub(r'[^0-9A-Za-z가-힣-]', '', location)}-{subindex + 1:03d}"
            section_path = " > ".join(headings) if headings else None
            paragraph = re.search(r"(?<![가-힣])[①②③④⑤⑥⑦⑧⑨⑩]", raw_piece) or re.search(r"^\s*(\d+)항", raw_piece, re.M)
            item = re.search(r"^\s*(\d+)\s*[.)]", raw_piece, re.M)
            appendix = re.search(r"(별\s*(?:표|지)(?:\s*제?\s*\d+\s*호?)?)", raw_piece)
            seed = {
                "chunk_id": chunk_id, "section_path": section_path, "chapter": headings[0] if headings else None,
                "section": headings[-1] if headings else None, "article_no": article_no, "article_title": article_title,
                "paragraph_no": paragraph.group(0).strip() if paragraph else None, "item_no": item.group(1) if item else None,
                "appendix_no": re.sub(r"\s+", "", appendix.group(1)) if appendix else None, "page_start": None, "page_end": None,
                "chunk_index": len(chunks), "text": raw_piece,
            }
            base = _refresh_chunk(seed, version, document)
            capacity = max(0, maximum - base["token_count"])
            prefix = overlap_tail(pieces[subindex - 1], min(overlap, capacity)) if subindex else ""
            seed["text"] = (prefix + "\n\n" + raw_piece).strip() if prefix else raw_piece
            chunk = _refresh_chunk(seed, version, document)
            if chunk["token_count"] > maximum:
                raise RuntimeError(f"최대 청크 크기 초과: {chunk_id}={chunk['token_count']}")
            chunks.append(chunk)
    return chunks


def _load_context(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    return (
        load_yaml(root / "config/chunking.yaml"),
        read_jsonl(root / "metadata/versions.jsonl"),
        {row["document_id"]: row for row in read_jsonl(root / "metadata/documents.jsonl")},
    )


def generate_full(root: Path = ROOT) -> list[dict[str, Any]]:
    config, versions, documents = _load_context(root)
    chunks: list[dict[str, Any]] = []
    for version in versions:
        if version.get("access_level") == "public" and version.get("normalized_file"):
            chunks.extend(generate_version_chunks(root, version, documents.get(version["document_id"], {}), config))
    return chunks


def generate_incremental(reference: list[dict[str, Any]], root: Path = ROOT) -> list[dict[str, Any]]:
    """기존 ID·본문을 보존하고 아직 청크가 없는 신규 버전만 생성한다."""
    config, versions, documents = _load_context(root)
    versions_by_id = {row["version_id"]: row for row in versions}
    unknown = sorted({row["version_id"] for row in reference} - set(versions_by_id))
    if unknown:
        raise RuntimeError(f"기존 청크가 알 수 없는 version_id를 참조합니다: {unknown[:5]}")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in reference:
        grouped.setdefault(row["version_id"], []).append(row)
    output: list[dict[str, Any]] = []
    for version in versions:
        version_id = version["version_id"]
        existing = sorted(grouped.get(version_id, []), key=lambda row: (row.get("chunk_index", 0), row["chunk_id"]))
        if existing:
            if version.get("access_level") != "public" or not version.get("normalized_file"):
                raise RuntimeError(f"기존 공개 청크를 자동 제거할 수 없습니다: {version_id}")
            output.extend(_refresh_chunk(row, version, documents.get(version["document_id"], {})) for row in existing)
        elif version.get("access_level") == "public" and version.get("normalized_file"):
            output.extend(generate_version_chunks(root, version, documents.get(version["document_id"], {}), config))
    before = {row["chunk_id"]: row["text"] for row in reference}
    after = {row["chunk_id"]: row["text"] for row in output}
    removed = set(before) - set(after)
    changed = [chunk_id for chunk_id in set(before) & set(after) if before[chunk_id] != after[chunk_id]]
    if removed or changed:
        raise RuntimeError(f"증분 모드가 기존 청크를 변경했습니다: removed={len(removed)}, text_changed={len(changed)}")
    return output


def rows_sha256(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--mode", choices=("incremental", "preview", "rechunk"), default="incremental")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mapping-output", type=Path)
    parser.add_argument("--allow-id-changes", action="store_true")
    parser.add_argument("--check-reference", type=Path)
    parser.add_argument("--check-determinism", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repo_root.resolve()
    canonical = (root / "rag/chunks.jsonl").resolve()
    reference_path = (args.reference or canonical).resolve()
    output_path = args.output.resolve() if args.output else ((root / ".artifacts/chunk-migration/chunks-v2.jsonl").resolve() if args.mode == "preview" else canonical)
    if args.mode == "preview" and output_path == canonical:
        raise RuntimeError("preview 모드는 canonical rag/chunks.jsonl에 쓸 수 없습니다")
    if args.mode == "rechunk" and output_path == canonical and not args.allow_id_changes:
        raise RuntimeError("canonical 전체 재청킹에는 --allow-id-changes가 필요합니다")

    reference = read_jsonl(reference_path)
    chunks = generate_incremental(reference, root) if args.mode == "incremental" else generate_full(root)
    if args.check_determinism:
        repeated = generate_incremental(reference, root) if args.mode == "incremental" else generate_full(root)
        if rows_sha256(chunks) != rows_sha256(repeated):
            raise RuntimeError("청크 생성 결과가 결정적이지 않습니다")
    write_jsonl(output_path, chunks)
    if args.check_reference and rows_sha256(chunks) != rows_sha256(read_jsonl(args.check_reference.resolve())):
        raise RuntimeError("증분 생성물이 기준 청크와 일치하지 않습니다")
    if args.mapping_output:
        from chunk_migration import build_migration_map, write_and_validate
        write_and_validate(args.mapping_output.resolve(), build_migration_map(reference, chunks), root)

    before_ids = {row["chunk_id"] for row in reference}
    after_ids = {row["chunk_id"] for row in chunks}
    print(json.dumps({
        "mode": args.mode, "output": output_path.relative_to(root).as_posix() if output_path.is_relative_to(root) else str(output_path),
        "chunks": len(chunks), "documents_with_chunks": len({row["document_id"] for row in chunks}), "sha256": rows_sha256(chunks),
        "reference_chunks": len(reference), "retained_ids": len(before_ids & after_ids), "removed_ids": len(before_ids - after_ids), "new_ids": len(after_ids - before_ids),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
