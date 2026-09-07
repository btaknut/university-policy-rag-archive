"""결정적 로컬 검색 색인과 법규 섹션 분류 공통 함수."""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, Iterable

from common import ROOT, read_jsonl

SECONDARY_KINDS = {"promulgation_notice", "amendment_reason", "major_changes", "comparison_old", "comparison_new"}


def normalize_search_text(value: str | None, *, compact: bool = False) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = re.sub(r"[·ㆍ‧・./\\()\[\]{}<>:;,'\"“”‘’_-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+", "", text) if compact else text


def classify_section(text: str, section_path: str | None = None) -> tuple[str, str, str]:
    """불확실한 내용은 보존하되 검색 범위를 보수적으로 분리한다."""
    body = normalize_search_text(text[:3000])
    value = normalize_search_text(f"{section_path or ''}\n{text[:1200]}")
    # 변환된 HWP가 개정자료와 개정 전문을 한 청크에 담은 경우, 실제 전문 시작
    # 청크는 제목·연혁 뒤 여러 조문이 이어지는 형태로 보수적으로 식별한다.
    if len(re.findall(r"제\s*\d+\s*조", body)) >= 2 and not re.search(r"현\s*행\s*\|\s*개\s*정\s*안", body[:700]):
        return "operative_text", "primary", "normative"
    if re.search(r"신\s*구\s*조문\s*대비|현\s*행\s*개\s*정\s*안", value):
        return "comparison_old", "secondary", "historical_context"
    if re.search(r"개정\s*사유|제정\s*사유", value):
        return "amendment_reason", "secondary", "non_normative"
    if re.search(r"주요\s*(내용|개정)", value):
        return "major_changes", "secondary", "non_normative"
    if re.search(r"부\s*칙", value):
        return "supplementary_provision", "primary", "normative"
    if re.search(r"공포|일부개정안", value) and not re.search(r"제\s*\d+\s*조", value):
        return "promulgation_notice", "secondary", "non_normative"
    if re.search(r"별\s*표", value):
        return "appendix", "primary", "normative"
    if re.search(r"별\s*지|서\s*식", value):
        return "form", "primary", "normative"
    if re.search(r"제\s*\d+\s*조", value):
        return "operative_text", "primary", "normative"
    return "unknown", "secondary", "unknown"


def source_url_quality(url: str | None) -> str:
    value = (url or "").lower()
    if not value:
        return "unknown"
    if "selectboardarticle" in value or "mode=v" in value or "/view" in value:
        return "detail"
    if "list" in value or "mode=l" in value or "06010" in value:
        return "list_only"
    if "download" in value or "filedown" in value or "mode=d" in value:
        return "attachment_only"
    return "unknown"


def _semantic_fields(chunk: dict[str, Any], version: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    section_kind, retrieval_scope, normative_status = classify_section(chunk.get("text", ""), chunk.get("section_path"))
    return {
        "is_latest_version": version.get("is_latest_version", version.get("version_id") == document.get("latest_version_id")),
        "validity_status": version.get("validity_status", document.get("validity_status", "unknown")),
        "validity_evidence": version.get("validity_evidence", document.get("validity_evidence")),
        "validity_checked_at": version.get("validity_checked_at", document.get("validity_checked_at")),
        "status_confidence": version.get("status_confidence", document.get("status_confidence", "unknown")),
        "source_url_quality": version.get("source_url_quality", document.get("source_url_quality", source_url_quality(chunk.get("source_url")))),
        "section_kind": chunk.get("section_kind", section_kind),
        "retrieval_scope": chunk.get("retrieval_scope", retrieval_scope),
        "normative_status": chunk.get("normative_status", normative_status),
    }


def iter_index_rows(root: Path = ROOT) -> Iterable[dict[str, Any]]:
    documents = {d["document_id"]: d for d in read_jsonl(root / "metadata/documents.jsonl")}
    versions = {v["version_id"]: v for v in read_jsonl(root / "metadata/versions.jsonl")}
    for chunk in read_jsonl(root / "rag/chunks.jsonl"):
        if chunk.get("access_level") != "public":
            continue
        document = documents.get(chunk["document_id"], {})
        version = versions.get(chunk["version_id"], {})
        row = dict(chunk)
        row.update(_semantic_fields(chunk, version, document))
        row["alternative_titles"] = document.get("alternative_titles") or []
        row["source_page_url"] = version.get("source_page_url") or document.get("source_page_url") or chunk.get("source_url")
        row["normalized_title"] = normalize_search_text(row.get("title"))
        row["compact_title"] = normalize_search_text(row.get("title"), compact=True)
        aliases = " ".join(row["alternative_titles"])
        row["normalized_aliases"] = "|" + "|".join(normalize_search_text(a) for a in row["alternative_titles"]) + "|"
        row["compact_aliases"] = "|" + "|".join(normalize_search_text(a,compact=True) for a in row["alternative_titles"]) + "|"
        row["search_text"] = normalize_search_text(f"{row.get('title','')} {aliases} {row.get('department','')} {row.get('text','')}")
        row["compact_text"] = normalize_search_text(f"{row.get('title','')} {aliases} {row.get('text','')}", compact=True)
        yield row


def fts5_available(connection: sqlite3.Connection) -> bool:
    try:
        connection.execute("CREATE VIRTUAL TABLE temp.__fts_probe USING fts5(value)")
        connection.execute("DROP TABLE temp.__fts_probe")
        return True
    except sqlite3.OperationalError:
        return False


def build_index(database: Path, root: Path = ROOT) -> tuple[int, str]:
    database.parent.mkdir(parents=True, exist_ok=True)
    if database.exists():
        database.unlink()
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE records (
          id INTEGER PRIMARY KEY, chunk_id TEXT UNIQUE, document_id TEXT, version_id TEXT,
          title TEXT, alternative_titles TEXT, document_type TEXT, department TEXT,
          validity_status TEXT, status_confidence TEXT, is_latest_version INTEGER,
          revision_date TEXT, effective_date TEXT, article_no TEXT, appendix_no TEXT,
          section_path TEXT, section_kind TEXT, retrieval_scope TEXT, normative_status TEXT,
          text TEXT, normalized_file TEXT, source_page_url TEXT, sha256 TEXT,
          citation_label TEXT, normalized_title TEXT, compact_title TEXT, normalized_aliases TEXT, compact_aliases TEXT,
          search_text TEXT, compact_text TEXT, metadata TEXT
        );
        CREATE INDEX records_document_idx ON records(document_id, is_latest_version);
        CREATE INDEX records_filter_idx ON records(document_type, department, validity_status);
    """)
    use_fts = fts5_available(connection)
    if use_fts:
        connection.execute("CREATE VIRTUAL TABLE records_fts USING fts5(chunk_id UNINDEXED, title, aliases, body, compact, tokenize='unicode61')")
    count = 0
    columns = ["chunk_id", "document_id", "version_id", "title", "alternative_titles", "document_type", "department",
               "validity_status", "status_confidence", "is_latest_version", "revision_date", "effective_date", "article_no",
               "appendix_no", "section_path", "section_kind", "retrieval_scope", "normative_status", "text", "normalized_file",
               "source_page_url", "sha256", "citation_label", "normalized_title", "compact_title", "normalized_aliases", "compact_aliases", "search_text", "compact_text"]
    for count, row in enumerate(iter_index_rows(root), 1):
        values = []
        for name in columns:
            value = row.get(name)
            if name == "alternative_titles": value = json.dumps(value, ensure_ascii=False)
            if name == "is_latest_version": value = int(bool(value))
            values.append(value)
        values.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        connection.execute(f"INSERT INTO records ({','.join(columns)},metadata) VALUES ({','.join('?' for _ in range(len(values)))})", values)
        if use_fts:
            connection.execute("INSERT INTO records_fts VALUES (?,?,?,?,?)",(row["chunk_id"],row.get("title") or ""," ".join(row.get("alternative_titles") or []),row.get("search_text") or "",row.get("compact_text") or ""))
    connection.commit(); connection.close()
    return count, "fts5-unicode61" if use_fts else "sqlite-like-fallback"


def _fts_query(query: str) -> str:
    words = [w for w in normalize_search_text(query).split() if w]
    compact = normalize_search_text(query, compact=True)
    terms = [f'"{w.replace(chr(34), chr(34)*2)}"' for w in words]
    if compact and compact not in words: terms.append(f'"{compact}"')
    return " OR ".join(terms)


def search(database: Path, *, query: str | None = None, filters: dict[str, Any] | None = None,
           limit: int = 10, per_document: int = 2) -> list[dict[str, Any]]:
    filters = filters or {}; connection = sqlite3.connect(database); connection.row_factory = sqlite3.Row
    has_fts = connection.execute("SELECT 1 FROM sqlite_master WHERE name='records_fts'").fetchone() is not None
    select = "SELECT r.*, 0.0 AS score FROM records r"
    params: list[Any] = []; where = []
    if query and has_fts:
        select = "SELECT r.*, bm25(records_fts,8.0,4.0,1.0,2.0) AS score FROM records_fts JOIN records r ON r.chunk_id=records_fts.chunk_id"
        where.append("records_fts MATCH ?"); params.append(_fts_query(query))
    elif query:
        where.append("(r.search_text LIKE ? OR r.compact_text LIKE ?)")
        params += [f"%{normalize_search_text(query)}%", f"%{normalize_search_text(query, compact=True)}%"]
    mapping = {"document_type":"document_type", "department":"department", "validity_status":"validity_status",
               "article_no":"article_no", "appendix_no":"appendix_no"}
    for key, column in mapping.items():
        if filters.get(key): where.append(f"r.{column} = ?"); params.append(filters[key])
    if filters.get("title_exact"):
        normalized=normalize_search_text(filters["title_exact"]); where.append("(r.normalized_title = ? OR r.normalized_aliases LIKE ?)"); params += [normalized,f"%|{normalized}|%"]
    if filters.get("title_contains"):
        where.append("(r.normalized_title LIKE ? OR r.compact_title LIKE ? OR r.normalized_aliases LIKE ? OR r.compact_aliases LIKE ?)")
        params += [f"%{normalize_search_text(filters['title_contains'])}%", f"%{normalize_search_text(filters['title_contains'], compact=True)}%",f"%{normalize_search_text(filters['title_contains'])}%",f"%{normalize_search_text(filters['title_contains'],compact=True)}%"]
    if filters.get("revision_from"): where.append("r.revision_date >= ?"); params.append(filters["revision_from"])
    if filters.get("revision_to"): where.append("r.revision_date <= ?"); params.append(filters["revision_to"])
    if filters.get("effective_from"): where.append("r.effective_date >= ?"); params.append(filters["effective_from"])
    if filters.get("effective_to"): where.append("r.effective_date <= ?"); params.append(filters["effective_to"])
    if filters.get("current_only"):
        where += ["r.validity_status = 'in_force'", "r.status_confidence = 'confirmed'"]
    elif not filters.get("include_history"):
        where.append("r.is_latest_version = 1")
    if not filters.get("include_secondary"):
        where.append("r.retrieval_scope = 'primary'")
    sql = select + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY score, r.title, r.chunk_id LIMIT ?"
    params.append(max(limit * max(per_document, 1) * 5, 50))
    rows = connection.execute(sql, params).fetchall(); connection.close()
    results=[]; seen={}
    for raw in rows:
        row=dict(raw); doc=row["document_id"]
        if seen.get(doc,0)>=per_document: continue
        seen[doc]=seen.get(doc,0)+1
        context=re.sub(r"\s+"," ",row["text"]).strip()
        row["context"]=(context[:277]+"...") if len(context)>280 else context
        row["rank"]=len(results)+1
        row.pop("metadata",None); row.pop("search_text",None); row.pop("compact_text",None)
        results.append(row)
        if len(results)>=limit: break
    return results
