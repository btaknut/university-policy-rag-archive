"""GitHub/ChatGPT 탐색용 소형 Markdown 카탈로그를 결정적으로 생성한다."""
from __future__ import annotations
import argparse
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
from common import ROOT, read_jsonl
from search_lib import source_url_quality

PAGE_SIZE=200

def _link(path: str | None) -> str:
    return f"[본문](https://github.com/btaknut/university-policy-rag-archive/blob/main/{quote(path, safe='/')})" if path else "-"

def _row(document, version):
    status=version.get("validity_status",document.get("validity_status","unknown"))
    confidence=version.get("status_confidence",document.get("status_confidence","unknown"))
    aliases=", ".join(document.get("alternative_titles") or []) or "-"
    source=version.get("source_page_url") or document.get("source_page_url")
    source_link=f"[공식]({source})" if source else "-"
    return f"| {document['title']} | {aliases} | {document['document_type']} | {document.get('department') or '-'} | {version.get('version_id') or '-'} | {status}/{confidence} | {version.get('revision_date') or '-'} | {version.get('effective_date') or '-'} | `{document['document_id']}` | {_link(version.get('normalized_file'))} | {source_link} |"

def _write(path:Path,title:str,rows:list[str]):
    header=[f"# {title}","","자동 생성 파일입니다. 수동 편집하지 마십시오.","","| 문서명 | 대체제목 | 유형 | 부서 | 최신 확보 버전 | 시행상태 | 개정일 | 시행일 | document_id | 본문 | 출처 |","|---|---|---|---|---|---|---|---|---|---|---|"]
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text("\n".join(header+rows)+"\n",encoding="utf-8",newline="\n")

def build(output:Path)->int:
    docs=read_jsonl(ROOT/"metadata/documents.jsonl"); versions={v["version_id"]:v for v in read_jsonl(ROOT/"metadata/versions.jsonl")}
    pairs=[]
    for d in docs:
        v=versions.get(d.get("latest_version_id"),{})
        pairs.append((d,v))
    pairs.sort(key=lambda pair:(pair[0].get("document_type",""),pair[0].get("title",""),pair[0]["document_id"]))
    groups={"regulations":[p for p in pairs if p[0].get("document_type")=="regulation"],"guidelines":[p for p in pairs if p[0].get("document_type")=="guideline"]}
    for name,items in groups.items():
        for page,start in enumerate(range(0,len(items),PAGE_SIZE),1): _write(output/"latest"/f"{name}-{page:03d}.md",f"최신 확보 {name} {page}",[_row(*p) for p in items[start:start+PAGE_SIZE]])
    _write(output/"by-title.md","제목별 문서",[_row(*p) for p in sorted(pairs,key=lambda p:(p[0]["title"],p[0]["document_id"]))])
    _write(output/"by-department.md","부서별 문서",[_row(*p) for p in sorted(pairs,key=lambda p:(p[0].get("department") or "~",p[0]["title"]))])
    review=[p for p in pairs if p[1].get("validity_status",p[0].get("validity_status","unknown"))=="unknown" or source_url_quality(p[1].get("source_page_url") or p[0].get("source_page_url"))!="detail"]
    _write(output/"review-required.md","검토 필요 문서",[_row(*p) for p in review])
    readme=["# GitHub 탐색용 카탈로그","","`metadata`에서 결정적으로 생성하며 본문을 복제하지 않습니다.","","- `latest/`: 유형별 최신 확보본","- `by-title.md`: 제목·대체제목 탐색","- `by-department.md`: 담당 부서 탐색","- `review-required.md`: 시행상태 또는 상세 URL 확인 필요","",f"문서 {len(pairs)}개, 검토 필요 {len(review)}개"]
    (output/"README.md").write_text("\n".join(readme)+"\n",encoding="utf-8",newline="\n"); return len(pairs)

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--output",type=Path,default=ROOT/"catalog"); args=p.parse_args()
    print({"documents":build(args.output),"output":str(args.output)}); return 0
if __name__=="__main__": raise SystemExit(main())
