"""제목·부서·유형·시행상태·날짜·조문을 필터링하는 로컬 검색 CLI."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from common import ROOT
from search_lib import search

DISPLAY=("rank","title","document_type","department","document_id","version_id","validity_status","status_confidence","revision_date","effective_date","article_no","section_kind","context","normalized_file","source_page_url","sha256","citation_label")

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("query",nargs="?",default=None)
    p.add_argument("--database",type=Path,default=ROOT/".artifacts/search/university_policy.sqlite3")
    p.add_argument("--title-exact"); p.add_argument("--title-contains"); p.add_argument("--type",dest="document_type")
    p.add_argument("--department"); p.add_argument("--validity-status"); p.add_argument("--current-only",action="store_true")
    p.add_argument("--include-history",action="store_true"); p.add_argument("--include-secondary",action="store_true")
    p.add_argument("--revision-from"); p.add_argument("--revision-to"); p.add_argument("--effective-from"); p.add_argument("--effective-to")
    p.add_argument("--article",dest="article_no"); p.add_argument("--appendix",dest="appendix_no")
    p.add_argument("--limit",type=int,default=10); p.add_argument("--per-document",type=int,default=2); p.add_argument("--format",choices=("table","json"),default="table")
    args=p.parse_args()
    if not args.database.exists(): p.error(f"검색 DB가 없습니다: {args.database}. 먼저 build_search_index.py를 실행하십시오.")
    filters={k:v for k,v in vars(args).items() if k not in {"query","database","limit","per_document","format"} and v not in (None,False)}
    rows=search(args.database,query=args.query,filters=filters,limit=args.limit,per_document=max(args.per_document,1))
    if args.format=="json": print(json.dumps([{k:r.get(k) for k in DISPLAY} for r in rows],ensure_ascii=False,indent=2)); return 0
    print("\t".join(DISPLAY))
    for row in rows: print("\t".join(str(row.get(k) or "").replace("\t"," ").replace("\n"," ") for k in DISPLAY))
    return 0
if __name__ == "__main__": raise SystemExit(main())
