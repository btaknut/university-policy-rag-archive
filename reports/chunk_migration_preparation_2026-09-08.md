# 청크 마이그레이션 준비 보고서 — C-1

- 기준 `main`: `0e58b52440a3567ecf400275684d1a9cdc646d8d`
- 범위: 안전한 증분 청킹, 명시적 전체 재청킹, 결정적 ID 매핑, CI 진단
- 제외: 실제 `rag/chunks.jsonl` 교체, 공식 원문·Git LFS·source manifest 변경, export 삭제, 과거 백필

## 기준선

| 항목 | 결과 |
|---|---:|
| 문서 | 403 |
| 버전 | 864 |
| canonical 청크 | 15,021 |
| 기준 pytest | 37 passed |
| 코퍼스 검증 | PASS 24 / WARNING 2 / FAIL 0 |
| 검색 평가 | Recall@5 1.0 / MRR 1.0 / 12 cases |

## 안전 증분 생성

`--mode incremental`을 별도 출력 경로에서 두 번 실행했다. canonical 데이터와 SHA-256이 일치했고 기존 ID·본문 변경은 없었다.

| 항목 | 결과 |
|---|---:|
| 출력 청크 | 15,021 |
| 유지 ID | 15,021 |
| 제거 ID | 0 |
| 신규 ID | 0 |
| SHA-256 | `607e9a673012bb7d6af75a457a6d835c6df5be433f6d97f9f09fccb2dbb1f10a` |

## 전체 v2 미리보기

기존 생성기를 그대로 시험했을 때 14,551개 중 `token_count > 1200`인 청크 19개가 확인됐다. C-1에서는 embedding 문맥 길이까지 제한에 포함하고, overlap 예산이 0일 때 긴 단위를 추가하던 경계를 수정했다. 수정 후 두 번 생성한 파일의 SHA-256이 일치했다.

| 항목 | 결과 |
|---|---:|
| 신규 미리보기 청크 | 14,662 |
| 유지 ID | 14,644 |
| 제거 ID | 377 |
| 신규 ID | 18 |
| 순감소 | 359 |
| 최대 token_count | 1,200 |
| 제한 초과 | 0 |
| 중복 ID | 0 |
| 빈 청크 | 0 |
| 미리보기 SHA-256 | `91abe05f985c95c36dd1be57eaa84efd35193dec1d88a5c86b8ba1002b48d1cd` |

## 매핑 결과

| 관계 | 건수 |
|---|---:|
| unchanged | 10,851 |
| modified | 3,793 |
| split | 25 |
| merged | 340 |
| removed | 12 |
| new | 18 |
| review_required | 1,589 |

관계 수는 기존 청크 15,021건을 기준으로 집계하며 `new` 18건은 별도 신규 ID다. 실제 C-2 전에는 `review_required` 항목과 외부 소비자 전환을 확인해야 한다.

## 데이터 SHA-256

| 파일 | SHA-256 |
|---|---|
| `rag/chunks.jsonl` | `607e9a673012bb7d6af75a457a6d835c6df5be433f6d97f9f09fccb2dbb1f10a` |
| `metadata/documents.jsonl` | `47dfb549e2633afc7dfb1fde711cad52a43b5bdbe302bdba79c2f79c57161a8a` |
| `metadata/versions.jsonl` | `b1ba30d51e79cd8aa478d2e2e30309b912633b6450040358e57bce7a20f5ed58` |
| `metadata/source_manifest.jsonl` | `5898c3dad7aae9068330940fca52ce843fd131cd4355eaf42791e7a49fae7584` |

## 소비 경로

- `confirmed`: 저장소 내부 SQLite FTS5, export 생성기, 문서화된 Git submodule 방식
- `no_evidence`: 공개 GitHub 코드에서 이 저장소 URL을 직접 참조한 결과 없음
- `unknown`: 로컬 clone, 이미 내려받은 bundle, 비공개 저장소

공개 검색 결과가 없다는 사실만으로 외부 소비자가 없다고 판단하지 않는다.

## 전환 및 롤백 조건

C-2는 C-1 병합과 사용자 별도 승인 후 수행한다. 구 ID 대응표, 확대 검색 평가, 외부 소비 경로, 두 번 생성한 해시, 공식 데이터 무변경을 확인해야 한다. 장애 시 기준 커밋 `0e58b52440a3567ecf400275684d1a9cdc646d8d`의 검색 파생자료를 일반 revert PR로 복원하고 전체 검증을 다시 실행한다.

## C-1 최종 검증

- pytest: 45 passed
- 안전 증분 생성: canonical SHA-256 일치, ID 제거·본문 변경 0건
- 전체 미리보기 2회: SHA-256 일치
- ID 매핑: JSON Schema 및 기존·신규 ID 참조 무결성 통과
- 코퍼스: PASS 24 / WARNING 2 / FAIL 0
- 검색 인덱스: 15,021 chunks / SQLite FTS5
- 검색 평가: Recall@5 1.0 / MRR 1.0 / 12 cases
- `git diff --check`: 통과
