# 청크 마이그레이션 운영 절차

## 기본 원칙

- `document_id`와 `version_id`는 청크 재생성으로 변경하지 않는다.
- 일반 `sync_archive.py`와 공식 업데이트 Gate는 `build_chunks.py --mode incremental`을 사용한다.
- 증분 모드는 기존 `chunk_id`와 `text`를 삭제하거나 변경하면 실패한다.
- 전체 재청킹은 별도 C-2 데이터 PR에서만 수행하고 자동 병합하지 않는다.
- 공식 원문, Git LFS 객체와 `metadata/source_manifest.jsonl`은 청크 마이그레이션 대상이 아니다.

## 소비 경로 조사 결과

| 경로 | 상태 | 근거와 제한 |
|---|---|---|
| 저장소 내부 SQLite FTS5 | `confirmed` | `scripts/build_search_index.py`, `scripts/search_corpus.py`가 canonical chunks를 사용 |
| 저장소 내부 export 생성기 | `confirmed` | `scripts/export_rag_bundle.py`가 chunks와 manifest를 복사 |
| Git submodule 연계 방식 | `confirmed` | README와 RAG_INTEGRATION에 지원 방식으로 문서화 |
| 공개 GitHub의 저장소 URL 직접 참조 | `no_evidence` | `btaknut/university-policy-rag-archive` 문자열 검색 결과 없음 |
| 로컬 clone·이미 배포된 bundle·비공개 저장소 | `unknown` | GitHub 공개 코드 검색으로 확인 불가 |

`no_evidence`는 소비자가 없다는 뜻이 아니다. C-2 전환 전 저장소 관리자에게 로컬·비공개 소비 경로를 확인한다.

## C-1 미리보기

```bash
mkdir -p .artifacts/chunk-migration
python scripts/build_chunks.py \
  --mode incremental \
  --output .artifacts/chunk-migration/chunks-incremental.jsonl \
  --check-reference rag/chunks.jsonl \
  --check-determinism
python scripts/build_chunks.py \
  --mode preview \
  --output .artifacts/chunk-migration/chunks-v2.jsonl \
  --mapping-output .artifacts/chunk-migration/chunk-id-map.json \
  --check-determinism
```

매핑의 `review_required=true` 항목은 C-2 전에 확인한다. `removed`, `split`, `merged` 및 자동 대응 신뢰도가 낮은 `modified` 항목을 우선 검토한다.

## C-2 전환 조건

1. C-1이 `main`에 병합되어 있어야 한다.
2. 사용자가 C-2 실행을 별도로 승인해야 한다.
3. 외부 소비 경로 상태와 전환 담당이 기록되어야 한다.
4. 매핑 스키마와 모든 구 ID의 처리 결과가 검증되어야 한다.
5. 기존 12개 회귀 사례와 확대된 평가 자료가 모두 통과해야 한다.
6. 재생성 2회의 SHA-256이 일치해야 한다.
7. 공식 원문·LFS·source manifest 변경이 없어야 한다.

## 롤백

1. C-2 직전 `main` 커밋과 `rag/chunks.jsonl` SHA-256을 기록한다.
2. 장애 시 강제 push가 아닌 일반 revert PR을 만든다.
3. 기준 커밋의 chunks, document catalog, corpus manifest, 검색 평가자료와 GitHub catalog를 복원한다.
4. 검색 인덱스를 다시 생성하고 코퍼스 검증·검색 회귀평가·pytest를 실행한다.
5. 외부 소비자가 신 ID를 반영했다면 동일 매핑을 역방향으로 적용하거나 기준 bundle로 복구한다.
