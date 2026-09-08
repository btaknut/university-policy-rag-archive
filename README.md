# 국립한국교통대학교 규정·지침 RAG 코퍼스

규정과 지침의 원본, 정규화 Markdown, 인용 가능한 RAG 청크를 분리해 보존하는 독립 코퍼스다. 특정 벡터 DB에 종속되지 않으며 `rag/chunks.jsonl`로 검색 인덱스를 재생성할 수 있다. 이 자료는 검색 지원용이며 대학의 공식 규정집이나 행정·법률 해석을 대체하지 않는다.

## 3계층 구조

- `sources/raw`: SHA-256 검증을 거친 원본 사본. 규정과 지침은 디렉터리와 `document_type`으로 구분한다.
- `corpus/normalized`: 버전별 UTF-8 Markdown과 YAML front matter.
- `rag`: 한국어 법규 구조 기반 청크, 문서 카탈로그, 재현 가능한 manifest와 export bundle.

메타데이터는 `metadata/documents.jsonl`, `metadata/versions.jsonl`, `metadata/source_manifest.jsonl`에 연결된다. 기존 `is_current`는 **최신 확보본 표시**이며 법적 의미의 현행 시행 여부가 아니다. 시행상태는 `validity_status`와 공식 근거로 별도 관리하고, 근거가 없으면 `unknown`이다.

## 설치와 전체 실행

```powershell
git lfs install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python scripts\audit_source.py
python scripts\migrate_sources.py --dry-run
python scripts\migrate_sources.py --execute
python scripts\extract_text.py
python scripts\normalize_documents.py
python scripts\build_versions.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\convert_hwp_to_pdf.ps1
python scripts\index_pdf_derivatives.py
python scripts\build_chunks.py --mode incremental
python scripts\build_catalog.py
python scripts\build_github_catalog.py
python scripts\validate_corpus.py
python scripts\build_search_index.py
python scripts\evaluate_retrieval.py
python -m pytest -q
python scripts\export_rag_bundle.py --zip
```

증분 갱신은 `python scripts\sync_archive.py`로 수행한다. 기본 모드는 기존 청크 ID와 본문 경계를 보존하고 아직 청크가 없는 신규 버전만 생성한다. 원본에서 사라진 파일은 자동 삭제하지 않는다.

전체 재청킹은 일반 동기화와 분리한다. 미리보기는 canonical 파일을 건드리지 않으며, 실제 교체에는 명시적인 승인 옵션이 필요하다.

```powershell
python scripts\build_chunks.py --mode preview --output .artifacts\chunk-migration\chunks-v2.jsonl --mapping-output .artifacts\chunk-migration\chunk-id-map.json --check-determinism
python scripts\sync_archive.py --rechunk
```

`--rechunk`는 기존 `chunk_id`를 변경할 수 있으므로 ID 매핑·소비자 전환·롤백 검토를 마친 데이터 PR에서만 사용한다. 자세한 절차는 [청크 마이그레이션 운영 절차](docs/CHUNK_MIGRATION.md)를 따른다.

## HWP 확인용 PDF

Windows에서 한컴오피스 2020 COM 자동화를 이용해 HWP 원본을 `corpus/pdf/{regulations,guidelines}/{document_id}/{version_id}.pdf`로 변환한다. 원본 HWP는 변경하지 않는다. PDF는 페이지 수·텍스트 레이어·SHA-256을 검증하며 기존 텍스트가 없던 버전은 PDF 텍스트로 Markdown을 생성한다. 대량 변환은 `python scripts\run_hwp_conversion_parallel.py run --shards 4`를 사용할 수 있다. PDF는 Git LFS로 관리되어 ChatGPT와 일반 PDF 도구가 문서 내용을 열람할 수 있다.

## 로컬 검색

```powershell
python scripts\build_search_index.py
python scripts\search_corpus.py "휴학" --type regulation --format table
python scripts\search_corpus.py "연구비" --department 산학협력단 --include-history --format json
python scripts\search_corpus.py --title-exact "금고지정심의위원회 운영 지침" --include-secondary
```

검색 DB는 `.artifacts/search`에 만들며 커밋하지 않는다. 기본 검색은 최신 확보 버전과 규범 본문·부칙·별표·서식만 대상으로 한다. `--current-only`는 `validity_status=in_force`이고 근거 신뢰도가 `confirmed`인 문서만 반환한다. 개정사유와 신구조문 대비표는 `--include-secondary`를 명시해야 검색된다.

## 상위 RAG와 검색 필터

상위 프로젝트는 이 저장소를 Git submodule 또는 데이터 배포물로 참조한다. 기본 검색은 `is_latest_version=true`, `access_level=public`, `retrieval_scope=primary`로 제한하고, 법적 현행본 검색은 확인된 `validity_status=in_force`를 추가한다. 청크의 `source_file`, `source_url`, `article_no`, `revision_date`, `sha256`, `citation_label`을 답변 근거로 유지한다. 자세한 절차는 [RAG_INTEGRATION.md](RAG_INTEGRATION.md)를 참고한다.

## 보안·Git LFS

민감정보 후보는 raw, 정규화, 청크에서 제외하고 `sources/restricted_manifest`와 보안 보고서에 해시·사유만 기록한다. `.env`와 API 키는 커밋하지 않는다. PDF/HWP/HWPX/DOCX/XLSX는 Git LFS 대상으로 지정했다. 공개 전에는 문서 권리와 개인정보를 다시 검토해야 한다.
