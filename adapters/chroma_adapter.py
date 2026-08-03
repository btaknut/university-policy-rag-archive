"""Chroma 적재 인터페이스 예시. 기본 dry-run은 외부 API를 호출하지 않는다."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--chunks",type=Path,default=Path("rag/chunks.jsonl")); p.add_argument("--include-history",action="store_true"); p.add_argument("--execute",action="store_true"); a=p.parse_args(); rows=[json.loads(x) for x in a.chunks.read_text(encoding="utf-8").splitlines() if x]; rows=[r for r in rows if r["access_level"]=="public" and (a.include_history or r.get("is_current") is True)]
    if not a.execute: print({"adapter":"chroma","sample_count":len(rows),"provider":os.getenv("EMBEDDING_PROVIDER")}); return 0
    raise SystemExit("실제 적재는 embedding provider와 Chroma 클라이언트를 명시적으로 구성한 뒤 구현하십시오.")
if __name__=="__main__": raise SystemExit(main())
