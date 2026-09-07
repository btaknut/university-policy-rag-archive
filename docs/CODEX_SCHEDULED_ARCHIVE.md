# Codex 예약 기반 공식 규정 아카이브 운영

## 목적

Codex 예약 작업을 주 스케줄러로 사용해 다음 4개 공식 원천을 매일 점검하고, 검증된 변경을 portable HWP Gate와 Git LFS를 거쳐 `main`에 반영한다.

1. 국립한국교통대학교 규정
2. 국립한국교통대학교 지침
3. 국립한국교통대학교 산학협력단 규정
4. 국립한국교통대학교 산학협력단 지침

Codex의 GitHub 연결은 배치 JSON과 점검 보고서만 작성한다. HWP/HWPX/PDF 원본, 변환 산출물 및 Git LFS 처리는 GitHub Actions의 portable HWP Gate가 담당한다.

## 자동 운영 흐름

1. Codex 예약 작업이 매일 19:00(Asia/Seoul)에 `config/official_sources.yaml`과 현재 메타데이터를 GitHub에서 읽는다.
2. 4개 공식 사이트의 목록·상세 페이지·첨부파일을 검색한다.
3. 신규·변경 후보를 임시 작업공간에 다운로드하여 파일 크기, SHA-256, 실제 파일 형식을 확인한다.
4. 후보가 없으면 예약 실행 결과만 남기고 GitHub는 수정하지 않는다.
5. 후보가 있으면 다음 두 텍스트 파일을 새 브랜치에 작성하고 배치 PR을 연다.
   - `reports/codex_official_update_batch_YYYY-MM-DD.json`
   - `reports/codex_official_update_YYYY-MM-DD.md`
6. 예약 작업이 공식 URL·해시·파일 크기·형식·이전 버전 연결·원천 오류와 필수 CI를 확인한다. 모든 조건이 충족된 경우에만 배치 PR을 병합한다.
7. 배치 JSON이 `main`에 들어오면 `Apply official update`가 자동 시작된다.
8. Actions가 원문을 다시 다운로드하고 해시·형식·한국어 변환 품질·코퍼스 무결성·Git LFS 상태와 전체 테스트를 검증한다.
9. Gate가 성공하면 데이터 PR을 생성하고, 생성 직후 HEAD가 변하지 않은 경우 일반 squash 병합을 시도한다.
10. 분기 보호·필수 승인·충돌·권한 오류가 있으면 우회하지 않고 데이터 PR을 남긴 채 실패 처리한다.
11. 예약 작업이 최신 `main`에서 버전 메타데이터와 최종 커밋을 확인해 실행 결과를 보고한다.

## 책임 경계

| 단계 | 실행 주체 | 쓰기 범위 |
|---|---|---|
| 정기 검색·대조 | Codex 예약 작업 | 없음 |
| 후보 다운로드·해시 | Codex 예약 작업 | 실행 중 임시 공간 |
| 후보 배치 제안 | Codex + GitHub 연결 | 텍스트 파일 2개, 배치 PR |
| 배치 검증·병합 | Codex 예약 작업 | 검증된 배치 PR |
| 원본 재다운로드·변환 | GitHub Actions | 작업 러너 |
| 원본·파생자료 반영 | GitHub Actions | Git LFS 포함 데이터 PR 생성·조건부 병합 |
| 최종 확인 | Codex 예약 작업 | 최신 `main` 검증 및 결과 보고 |

## 자동 반영 조건

다음 조건을 모두 충족해야 데이터 PR을 생성하고 자동 병합한다.

- 공식 상세 페이지와 첨부 URL 재확인
- 첨부파일 다운로드 성공
- 파일 크기 및 SHA-256 일치
- HWP/HWPX/PDF 실제 형식 확인
- `document_id`, `version_id`, `previous_version_id` 연결 확인
- portable HWP 변환 품질 기준 통과
- 원본과 변환물의 해시 검증
- Git LFS 속성 및 상태 확인
- 전체 코퍼스 검증 성공
- 전체 테스트 성공
- 원천 오류 0건
- 과거 백필 후보가 일상 배치에 포함되지 않음

하나라도 충족하지 않거나 상태를 확인할 수 없으면 데이터 PR을 병합하지 않는다.

## 안전 규칙

- Codex 예약 작업은 `main`에 직접 커밋하지 않는다.
- Codex 예약 작업은 바이너리 또는 Git LFS 포인터를 직접 커밋하지 않는다.
- 다운로드 실패, HTML 오류 응답, 해시 불일치가 있으면 후보를 반영하지 않는다.
- 날짜·문서 ID·이전 버전 ID·해시는 추정하지 않는다.
- 기존 브랜치나 같은 날짜의 PR이 있으면 중복 생성하지 않는다.
- 배치 PR은 자동 병합하지 않으며, Gate가 생성한 데이터 PR만 자동 병합한다.
- 분기 보호, 필수 승인 또는 권한 조건을 우회하는 관리자 병합 옵션은 사용하지 않는다.
- 기존 사용자 PR·이슈는 자동으로 닫거나 변경하지 않는다.
- 원천 오류만 있으면 코드 PR 대신 오류 이슈 1개만 생성한다.

## 수동 fallback

`check-official-sources.yml`은 `workflow_dispatch`만 유지한다. Codex 예약 장애, 원천별 재검증 또는 다운로드 artifact 확인이 필요할 때 수동으로 실행한다.

`apply-official-update.yml`도 수동 실행을 지원한다.

- `mode=plan`: 배치와 공식 원문을 검증하고 저장소는 변경하지 않는다.
- `mode=create_pr`, `merge_after_gate=false`: Gate 통과 후 데이터 초안 PR만 생성한다.
- `mode=create_pr`, `merge_after_gate=true`: Gate 통과 후 데이터 PR을 생성하고 일반 squash 병합을 시도한다.

## 예약 기준

- 주기: 매일
- 시각: 19:00
- 시간대: Asia/Seoul
- 대상 저장소: `btaknut/university-policy-rag-archive`
