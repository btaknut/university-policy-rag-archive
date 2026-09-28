from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from common import read_jsonl
from common import write_jsonl
import build_versions
import hashlib

def test_version_links_stay_in_document():
    versions=read_jsonl(ROOT/"metadata/versions.jsonl"); by_id={v["version_id"]:v for v in versions}
    for v in versions:
        for key in ("previous_version_id","next_version_id"):
            if v.get(key): assert by_id[v[key]]["document_id"]==v["document_id"]


def test_rebuild_keeps_latest_reference_without_claiming_legal_validity(tmp_path, monkeypatch):
    monkeypatch.setattr(build_versions, 'ROOT', tmp_path)
    (tmp_path/'metadata').mkdir()
    docs=[{'document_id':'D','latest_version_id':'V','is_current':None,'current_status':'unknown'}]
    vers=[{'document_id':'D','version_id':'V','revision_date':'2026-01-01','sha256':'a'*64,'is_current':None,'current_status':'unknown'}]
    write_jsonl(tmp_path/'metadata/documents.jsonl',docs)
    write_jsonl(tmp_path/'metadata/versions.jsonl',vers)
    assert build_versions.main()==0
    assert read_jsonl(tmp_path/'metadata/documents.jsonl')[0]['latest_version_id']=='V'
    v=read_jsonl(tmp_path/'metadata/versions.jsonl')[0]
    assert v['is_latest_version'] is True
    assert v['validity_status']=='unknown'
    assert v['status_confidence']=='unknown'


def test_frontmatter_refresh_preserves_body_and_portable_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(build_versions,'ROOT',tmp_path)
    (tmp_path/'metadata').mkdir()
    body='제1조 본문과 별표를 보존한다.\n'
    (tmp_path/'v.md').write_text('---\nis_current: true\ncurrent_status: "confirmed"\n---\n'+body)
    versions=[{'version_id':'old','document_id':'D','normalized_file':'v.md','is_current':False,'current_status':'historical','portable_conversion_status':'success'}]
    write_jsonl(tmp_path/'metadata/portable_hwp_manifest.jsonl',[{'version_id':'old','normalized_sha256':'oldhash'}])
    build_versions.sync_front_matter(versions,[{'document_id':'D','latest_version_id':'new'}])
    content=(tmp_path/'v.md').read_text()
    assert content.split('---\n')[-1]==body
    assert 'is_current: false' in content
    digest=hashlib.sha256(content.encode()).hexdigest()
    assert versions[0]['portable_markdown_sha256']==digest
    assert read_jsonl(tmp_path/'metadata/portable_hwp_manifest.jsonl')[0]['normalized_sha256']==digest
