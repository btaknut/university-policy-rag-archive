# 아카이브 검색 데이터 결정적 재생성 — PR B

- 기준 `main`: `f497ce0135762f6aeaa76d9dc575b0b8490e038f`
- 선행 PR A HEAD: `5d64c155d4a6c7242e13aba54eb666b3fc26ee64`
- 범위: 메타데이터 보강, 기존 청크 의미 필드 보강, 카탈로그·manifest·검색 평가자료 재생성
- 제외: 공식 원문, Git LFS 객체, ID 재발급, 과거 백필 122건, 오래된 export 삭제, 재청킹

## 수량과 ID 보존

| 항목 | 이전 | 이후 | 결과 |
|---|---:|---:|---|
| 문서 | 403 | 403 | `document_id` 전부 보존 |
| 버전 | 864 | 864 | `version_id` 전부 보존 |
| 현행 호환 표시 | 337 | 337 | `is_current` 의미 변경 없음 |
| 최신 확보 문서 | 337 | 403 | 누락된 체인 말단 66건 연결 |
| 검색 청크 | 15,021 | 15,021 | `chunk_id` 전부 보존 |
| GitHub 카탈로그 | 0 | 7 files | 본문 복제 없이 생성 |

## 메타데이터·검색 보강

- 66개 문서의 `latest_version_id`를 기존 양방향 버전 체인의 유일한 말단에 연결했다.
- 공식 시행·폐지 근거를 새로 확인하지 않았으므로 864개 버전의 `validity_status`와 `status_confidence`는 모두 `unknown`이다. 기존 `is_current`를 `in_force`로 승격하지 않았다.
- URL 품질: 상세 페이지 625건, 목록 페이지만 확인 가능한 레코드 239건.
- normalized Markdown 64개 파일의 front matter 128항목을 보정했으며 본문은 변경하지 않았다.
- 기존 청크 ID를 유지하며 15,021개 전부에 검색 의미 필드를 기록했다.

| 청크 분류 | 건수 |
|---|---:|
| operative_text | 10,429 |
| supplementary_provision | 724 |
| appendix | 893 |
| form | 1,437 |
| amendment_reason | 12 |
| major_changes | 63 |
| comparison_old | 134 |
| promulgation_notice | 18 |
| unknown | 1,311 |
| 기본 검색 primary | 13,483 |
| 기본 제외 secondary | 1,538 |

## SHA-256

| 파일 | 이전 | 이후 |
|---|---|---|
| `metadata/documents.jsonl` | `8725e3fd86acfbf7ce1c9e02c26f92bbfda72cc255a111c43204d9a33bed2c73` | `47dfb549e2633afc7dfb1fde711cad52a43b5bdbe302bdba79c2f79c57161a8a` |
| `metadata/versions.jsonl` | `02c4828f9353100afc609e4270f30029c1e066128b4fc71da715ffdc82291f29` | `b1ba30d51e79cd8aa478d2e2e30309b912633b6450040358e57bce7a20f5ed58` |
| `rag/chunks.jsonl` | `3b3b43ac171ca657999cb79c56139ac10596b45c6170196ec385adfb5434a065` | `607e9a673012bb7d6af75a457a6d835c6df5be433f6d97f9f09fccb2dbb1f10a` |
| `rag/corpus_manifest.json` | `744e13a8e4c067f76209a7fadadccc6aa32459713898083c259e6ab08fa8d103` | `26ca8a5806c54ad8ad03c5c30fc9126ab8273ba5d634a749e2d8a0bb3a297288` |
| `metadata/source_manifest.jsonl` | `5898c3dad7aae9068330940fca52ce843fd131cd4355eaf42791e7a49fae7584` | 동일 |

## 검증

- 코퍼스 검증: `{"PASS": 24, "WARNING": 2}`
- 검색 인덱스: `{"database": ".cache/search.sqlite3", "indexed_chunks": 15021, "engine": "fts5-unicode61"}`
- 검색 회귀평가: `PASS`, Recall@5 1.0, MRR 1.0, 12 cases
- pytest: `37 passed in 16.73s`
- 생성 산출물 2회 빌드: 해시 일치
- document/version/chunk ID 변경: 0건
- 공식 원문·source manifest 변경: 0건

남은 경고는 로컬 레거시 원본 경로 미설정과 현재 청크와 다른 57,258,437-byte 과거 export다. 중복 감소량은 이번 PR에서 0 bytes이며 소비 경로 확인 후 별도 삭제 PR로 처리한다.

## PR C 분리 판정

PR A의 새 청킹 설정으로 전체 재청킹하면 청크 수가 15,021개에서 14,551개로 바뀌고 기존 ID 477개가 제거되며 7개가 추가된다. 따라서 이 변경은 PR B에 포함하지 않았고, 구 ID→신 ID 매핑·소비자 전환·롤백 절차를 갖춘 선택적 PR C 대상으로 남긴다.
