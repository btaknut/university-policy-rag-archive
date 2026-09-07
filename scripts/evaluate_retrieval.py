"""실제 ID가 지정된 검색 회귀 사례를 평가한다."""
from __future__ import annotations
import argparse, json, tempfile
from pathlib import Path
from common import ROOT
from search_lib import build_index, search

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--config",type=Path,default=ROOT/"config/retrieval_eval.json"); p.add_argument("--database",type=Path); args=p.parse_args()
    config=json.loads(args.config.read_text(encoding="utf-8")); cases=config.get("cases") or []
    if not cases or any(not case.get("expected") for case in cases):
        print(json.dumps({"status":"FAIL","reason":"모든 평가 사례에 실제 expected ID가 필요합니다."},ensure_ascii=False)); return 1
    temporary=None; database=args.database
    if database is None:
        temporary=tempfile.TemporaryDirectory(); database=Path(temporary.name)/"search.sqlite3"; build_index(database)
    top_k=int(config.get("top_k",5)); hits=0; reciprocal=0.0; failures=[]
    for case in cases:
        rows=search(database,query=case.get("query"),filters=case.get("filters") or {},limit=top_k,per_document=1)
        expected={(e["document_id"],e["version_id"]) for e in case["expected"]}
        rank=next((i for i,row in enumerate(rows,1) if (row["document_id"],row["version_id"]) in expected),None)
        forbidden=set(case.get("forbidden_section_kinds") or [])
        invalid=[r["chunk_id"] for r in rows if r.get("section_kind") in forbidden]
        if rank and not invalid: hits+=1; reciprocal+=1/rank
        else: failures.append({"name":case["name"],"rank":rank,"forbidden":invalid,"returned":[[r["document_id"],r["version_id"]] for r in rows]})
    recall=hits/len(cases); mrr=reciprocal/len(cases); passed=recall>=float(config["minimum_recall_at_k"]) and mrr>=float(config["minimum_mrr"])
    result={"status":"PASS" if passed else "FAIL",f"recall@{top_k}":round(recall,4),"mrr":round(mrr,4),"cases":len(cases),"failures":failures}
    print(json.dumps(result,ensure_ascii=False,indent=2));
    if temporary: temporary.cleanup()
    return 0 if passed else 1
if __name__=="__main__": raise SystemExit(main())
