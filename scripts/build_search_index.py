"""커밋하지 않는 SQLite 로컬 검색 DB를 생성한다."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from common import ROOT
from search_lib import build_index

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--database",type=Path,default=ROOT/".artifacts/search/university_policy.sqlite3")
    args=parser.parse_args(); count,engine=build_index(args.database)
    print(json.dumps({"database":str(args.database),"indexed_chunks":count,"engine":engine},ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
