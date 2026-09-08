# 청크 마이그레이션 결과 보고서 — C-2

- 기준 `main`: `301ea02d056c34acd14d8698cb2cedf981f350d5`
- 작업 브랜치: `codex/chunk-migration-v2-20260908`
- 롤백 기준: C-2 병합 직전 위 기준 커밋
- 생성기: C-1에서 확정한 `scripts/build_chunks.py` 및 `scripts/chunk_migration.py`
- 제외 범위: 공식 원문, Git LFS 객체, `metadata/source_manifest.jsonl`, 공식 업데이트 배치, 백필, 오래된 export 삭제

## 변경 수량

| 항목 | 전환 전 | 전환 후 | 차이 |
|---|---:|---:|---:|
| 청크 | 15,021 | 14,662 | -359 |
| 유지 ID | - | 14,644 | - |
| 삭제 ID | - | 377 | - |
| 신규 ID | - | 18 | - |
| 문서 | 403 | 403 | 0 |
| 버전 | 864 | 864 | 0 |

## ID 매핑

매핑 파일은 `rag/chunk_id_mapping_v1_to_v2.json`이다. 기존 ID 15,021개를 정확히 한 번씩 처리하고, 신규 ID 18개를 별도 `new` 항목으로 기록한다. 각 항목은 문서·버전 ID, 구·신 청크 ID, 본문 SHA-256, 조문·항·별표·서식 위치, 텍스트 중첩 점수와 근거, 자동 대응 여부 및 `review_required`를 포함한다.

| 관계 | 건수 |
|---|---:|
| unchanged | 10,851 |
| modified | 3,793 |
| split | 25 |
| merged | 340 |
| removed | 12 |
| new | 18 |
| review_required | 1,589 |

- 일대다 대응: 25건 — 각 대상 ID가 매핑 파일에 명시됨
- 대상 없는 구 ID: 12건 — `removed`로 명시됨
- 다대일 대응: 340건 — `merged`로 명시됨
- 자동 대응 불가 또는 검토 필요: 1,589건 — `review_required=true`로 명시됨

## SHA-256

| 파일 | 전환 전 | 전환 후 |
|---|---|---|
| `rag/chunks.jsonl` | `607e9a673012bb7d6af75a457a6d835c6df5be433f6d97f9f09fccb2dbb1f10a` | `91abe05f985c95c36dd1be57eaa84efd35193dec1d88a5c86b8ba1002b48d1cd` |
| `rag/corpus_manifest.json` | `26ca8a5806c54ad8ad03c5c30fc9126ab8273ba5d634a749e2d8a0bb3a297288` | `a67ceba6ed105beac94e0c7d0fd68e656b2c7bd6bcfc18d06110c19e7225ba2e` |
| `rag/retrieval_examples.json` | `2d0fda9967cb410605f21cf76ad56bbe1f33324bb6b9e3b69f85eb774a092485` | `578338856b91cfa9bfe7bd1e03a1678088a265a198a3d98cf67d3c53124c7956` |
| `rag/chunk_id_mapping_v1_to_v2.json` | - | `6def5804d2ecbb7d26332e1503191f7624be5de7d6c2cc50f37cfec626ce79b4` |
| `metadata/documents.jsonl` | `47dfb549e2633afc7dfb1fde711cad52a43b5bdbe302bdba79c2f79c57161a8a` | 변경 없음 |
| `metadata/versions.jsonl` | `b1ba30d51e79cd8aa478d2e2e30309b912633b6450040358e57bce7a20f5ed58` | 변경 없음 |
| `metadata/source_manifest.jsonl` | `5898c3dad7aae9068330940fca52ce843fd131cd4355eaf42791e7a49fae7584` | 변경 없음 |

동일 입력으로 생성물을 두 번 빌드했으며 두 `chunks.jsonl`의 SHA-256이 모두 `91abe05f985c95c36dd1be57eaa84efd35193dec1d88a5c86b8ba1002b48d1cd`로 일치했다.

## 검색 회귀평가

| 평가 | 사례 | Recall@5 | MRR | 실패 |
|---|---:|---:|---:|---:|
| 전환 전 | 12 | 1.0 | 1.0 | 0 |
| 전환 후 | 30 | 1.0 | 1.0 | 0 |

기존 12건은 유지했다. 추가 사례는 규정·지침, 최신·연혁, 조문, 부칙, 별표, 서식, 띄어쓰기 변형과 교통대 규정·교통대 지침·산학협력단 규정·산학협력단 지침의 네 원천 유형을 포함한다.

## 무결성 및 전체 검증

- 빈 청크: 0
- 고아 청크: 0
- 중복 `chunk_id`: 0
- 최대 `token_count`: 1,200
- 최대 토큰 제한 위반: 0
- document/version 참조 오류: 0
- source 및 normalized 경로 오류: 0
- 인용 필드 누락: 0
- ID 매핑 스키마 및 구·신 ID 참조 무결성: 통과
- 전체 pytest: 45 passed
- 코퍼스 검증: PASS 24 / WARNING 2 / FAIL 0
- SQLite FTS5 검색 인덱스: 14,662청크 생성 성공
- Git LFS 상태: 공식 원문·LFS 객체 변경 없음
- 공식 업데이트 Gate: C-1의 증분 모드 보호 유지, 워크플로 변경 없음

경고 2건은 로컬 레거시 원본 미설정과 현재 청크와 불일치하는 오래된 export bundle이며, 이번 C-2 범위에서 삭제하거나 혼합하지 않는다.

## 외부 소비자 영향

| 소비 경로 | 상태 | 전환 영향 |
|---|---|---|
| 저장소 내부 SQLite FTS5 | `confirmed` | C-2 청크로 재생성 및 평가 완료 |
| 저장소 내부 export 생성기 | `confirmed` | 생성 가능하나 오래된 export 삭제·재배포는 별도 작업 |
| 문서화된 Git submodule 방식 | `confirmed` | C-2 병합 후 새 커밋으로 갱신 필요 |
| 공개 GitHub의 저장소 URL 직접 참조 | `no_evidence` | 공개 검색에서 근거 없음; 소비자가 없다는 의미는 아님 |
| 로컬 clone·기배포 bundle·비공개 저장소 | `unknown` | 저장소 관리자의 별도 확인 필요 |

## 전환과 롤백

PR은 자동 병합하지 않는다. 병합 전 외부 소비자의 구 ID 사용 여부와 `review_required` 항목을 검토한다. 병합 후 소비자는 `rag/chunk_id_mapping_v1_to_v2.json`을 이용해 참조를 전환하고 검색 인덱스를 다시 생성한다.

문제가 발생하면 force push나 관리자 우회를 사용하지 않고 기준 커밋 `301ea02d056c34acd14d8698cb2cedf981f350d5`의 청크, manifest, 카탈로그 및 평가자료를 복원하는 일반 revert PR을 생성한다. 복원 후 전체 pytest, 코퍼스 검증, 검색 인덱스 생성과 회귀평가를 다시 실행한다.
