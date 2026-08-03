"""외부 API 없이 chunks.jsonl을 SQLite FTS5로 색인·검색하는 예제."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def build(chunks_path: Path, database: Path, current_only: bool = True) -> int:
    """공개 청크를 FTS5에 적재한다."""
    conn = sqlite3.connect(database); conn.execute("DROP TABLE IF EXISTS chunks"); conn.execute("CREATE VIRTUAL TABLE chunks USING fts5(chunk_id UNINDEXED, document_id UNINDEXED, title, text, metadata UNINDEXED)"); count = 0
    for line in chunks_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("access_level") != "public" or (current_only and row.get("is_current") is not True): continue
        conn.execute("INSERT INTO chunks VALUES (?,?,?,?,?)", (row["chunk_id"], row["document_id"], row["title"], row["text"], json.dumps(row, ensure_ascii=False))); count += 1
    conn.commit(); conn.close(); return count


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--chunks", type=Path, default=Path("rag/chunks.jsonl")); p.add_argument("--database", type=Path, default=Path("university_policy.sqlite3")); p.add_argument("--include-history", action="store_true"); p.add_argument("--query"); p.add_argument("--dry-run", action="store_true"); args = p.parse_args()
    if args.dry_run: print(sum(1 for x in args.chunks.read_text(encoding="utf-8").splitlines() if x)); return 0
    print({"indexed": build(args.chunks, args.database, not args.include_history)})
    if args.query:
        conn = sqlite3.connect(args.database)
        for row in conn.execute("SELECT chunk_id,title,snippet(chunks,3,'[',']','…',24) FROM chunks WHERE chunks MATCH ? LIMIT 10", (args.query,)): print(row)
    return 0


if __name__ == "__main__": raise SystemExit(main())
