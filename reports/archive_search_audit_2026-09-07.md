# 아카이브 저장·검색 구조 진단 — 2026-09-07

- 기준 커밋: `f497ce0135762f6aeaa76d9dc575b0b8490e038f`
- 범위: PR A(구조·검증·검색 코드), 공식 데이터 변경 없음
- 문서/버전/`is_current` 문서/청크: 403/864/337/15,021
- 한컴 PDF/Portable Markdown: 847/6
- 열린 PR: #1 한 건(범위 제외, 변경 없음)
- `main` 외 원격 브랜치: 6개(삭제 없음)

## 저장 구조

| 판정 | 항목 | 결과 |
|---|---|---|
| PASS | 원문 보존 | 1,778개 source manifest의 실제 파일 또는 LFS OID와 SHA-256 일치 |
| PASS | HWP 파생본 | 한컴 PDF 847개와 Portable Markdown 6개가 기존 검증 조건 충족 |
| WARNING | 중복 export | `rag/exports/.../chunks.jsonl` 57,258,437 bytes가 현재 `rag/chunks.jsonl`과 불일치한 오래된 복제본 |
| FAIL | 개인 PC 경로 | `config/sources.yaml`과 `scripts/common.py`가 특정 Windows 경로에 고정됨. PR A에서 환경변수 방식으로 수정 |
| REVIEW_REQUIRED | 과거 보고서 경로 | 보존 보고서 3개에 당시 로컬 경로가 기록되어 있음. 감사기록이므로 변조하지 않음 |
| WARNING | 결정성 | `build_catalog.py`의 실행시각 때문에 동일 입력에도 diff 발생. 입력 기반 시각으로 수정 |

## 검색 구조

| 판정 | 항목 | 결과 |
|---|---|---|
| FAIL | 로컬 검색 | 기존 FTS는 제목·본문 질의 예제이며 상태·날짜·조문 필터와 구조화 출력이 없음 |
| FAIL | 상태 의미 | `is_current`가 최신 확보본과 현행 시행본 의미로 혼용됨 |
| FAIL | 개정자료 혼합 | 개정사유·주요내용·신구조문 대비표와 개정 전문이 같은 청크에 혼합됨 |
| WARNING | heading | 전체 문서의 첫 heading 두 개를 모든 조문에 반복 적용함 |
| WARNING | 설정 불일치 | 설정은 700/1,200/80이나 코드는 650/850을 사용하고 overlap을 적용하지 않음 |
| REVIEW_REQUIRED | 벡터 어댑터 | Chroma·FAISS·Qdrant 파일은 계약 예시이며 완성된 운영 인덱서가 아님 |
| PASS | 역추적 | 청크에서 version/document ID, 원문 경로, URL, SHA-256, 인용 label 확인 가능 |

## 자동화·무결성

| 판정 | 항목 | 결과 |
|---|---|---|
| PASS | ID 고유성 | document/version/chunk 중복 0건 |
| PASS | 버전 체인 | 누락·타문서 참조 0건, previous/next 비대칭 0건 |
| WARNING | latest 연결 | 66개 문서의 `latest_version_id`가 누락되거나 해당 문서 버전으로 연결되지 않음. PR B 대상 |
| WARNING | front matter | 128개 normalized 문서의 핵심 front matter가 메타데이터와 불일치 또는 누락. PR B 대상 |
| PASS | 파생 카탈로그 | `current_documents.jsonl` 337개는 기존 `is_current` 부분집합, 문서 카탈로그 403개 일치 |
| PASS | corpus manifest | 문서·버전·청크 수와 기준 파일 SHA-256 일치 |
| FAIL | 검색 회귀 | 기존 평가 9건 중 빈 기대값이 있어 신뢰할 수 없음. 실제 ID 12건 평가로 교체 |
| FAIL | 저장소 보호 | GitHub 확인 결과 `main` protected=false, ruleset 0개 |
| WARNING | Actions PR 권한 | 직전 Gate에서 Actions의 PR 생성 권한이 거부됨. 저장소 설정 확인 필요 |

## PR A 조치와 분리 범위

- SQLite FTS5 로컬 색인·검색·평가 CLI와 NFKC/공백/문장부호 정규화를 추가한다.
- 신규 상태 필드는 호환 스키마에만 추가한다. 확인되지 않은 시행상태는 `unknown`이며 `is_current`를 `in_force`로 승격하지 않는다.
- 개정자료는 기본 검색에서 제외하고 기존 혼합 청크는 삭제하지 않는다.
- GitHub Markdown 카탈로그 생성기를 추가하되 실제 카탈로그·청크·메타데이터 생성은 PR B로 분리한다.
- 오래된 57MB export 삭제와 청크 ID 전환은 소비자 확인 후 별도 변경으로 남긴다.
- 공식 원문, 기존 ID, 공식 업데이트 배치, 백필 후보 122건은 변경하지 않는다.
