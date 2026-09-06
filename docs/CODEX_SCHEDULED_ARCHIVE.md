# Codex 예약 기반 공식 규정 아카이브 운영

## 목적

Codex 예약 작업을 주 스케줄러로 사용해 다음 4개 공식 원천을 정기 점검하고, 검증 가능한 텍스트 배치를 GitHub 초안 PR로 전달한다.

1. 국립한국교통대학교 규정
2. 국립한국교통대학교 지침
3. 국립한국교통대학교 산학협력단 규정
4. 국립한국교통대학교 산학협력단 지침

HWP/HWPX/PDF 원본과 변환 산출물은 Codex의 GitHub 연결로 직접 커밋하지 않는다. 바이너리와 Git LFS 처리는 GitHub Actions의 portable HWP Gate가 담당한다.

## 운영 흐름

1. Codex 예약 작업이 `config/official_sources.yaml`과 현재 메타데이터를 GitHub에서 읽는다.
2. 4개 공식 사이트의 목록·상세 페이지·첨부파일을 검색한다.
3. 신규·변경 후보를 임시 작업공간에 다운로드하여 파일 크기, SHA-256, 실제 파일 형식을 확인한다.
4. 후보가 없으면 예약 실행 결과만 남기고 GitHub는 수정하지 않는다.
5. 후보가 있으면 다음 두 텍스트 파일을 새 브랜치에 작성하고 초안 PR을 연다.
   - `reports/codex_official_update_batch_YYYY-MM-DD.json`
   - `reports/codex_official_update_YYYY-MM-DD.md`
6. 담당자가 공식 상세 페이지, 첨부 URL, 날짜, SHA-256, 기존 버전 연결을 검토한 뒤 배치 PR을 병합한다.
7. GitHub Actions의 `Apply official update`를 `create_pr` 모드와 병합된 `batch_path`로 실행한다.
8. Actions가 원문을 다시 다운로드하고 해시·형식·한국어 변환 품질·코퍼스 무결성·Git LFS 상태를 검증한 뒤 데이터 초안 PR을 생성한다.
9. 담당자가 데이터 PR을 최종 검토·병합한다.

## 책임 경계

| 단계 | 실행 주체 | 쓰기 범위 |
|---|---|---|
| 정기 검색·대조 | Codex 예약 작업 | 없음 |
| 후보 다운로드·해시 | Codex 예약 작업 | 실행 중 임시 공간 |
| 후보 배치 제안 | Codex + GitHub 연결 | 텍스트 파일 2개, 초안 PR |
| 원본 재다운로드·변환 | GitHub Actions | 작업 러너 |
| 원본·파생자료 반영 | GitHub Actions | Git LFS 포함 데이터 초안 PR |
| 최종 승인 | 저장소 관리자 | PR 병합 |

## 안전 규칙

- Codex 예약 작업은 `main`에 직접 쓰지 않는다.
- Codex 예약 작업은 바이너리 또는 Git LFS 포인터를 직접 커밋하지 않는다.
- 다운로드 실패, HTML 오류 응답, 해시 불일치가 있으면 후보를 반영하지 않는다.
- 날짜·문서 ID·이전 버전 ID·해시는 추정하지 않는다.
- 기존 브랜치나 같은 날짜의 PR이 있으면 중복 생성하지 않는다.
- 자동 병합은 사용하지 않는다.
- 원천 오류만 있으면 코드 PR 대신 오류 이슈 1개만 생성한다.
- 첫 2회 예약 실행은 결과 범위와 오탐 여부를 사람이 확인한다.

## 수동 fallback

`check-official-sources.yml`은 예약 실행을 제거하고 `workflow_dispatch`만 유지한다. Codex 예약 장애, 원천별 재검증, 다운로드 artifact 확인이 필요할 때 수동으로 실행한다.

`apply-official-update.yml`은 실제 반영 Gate다. 현재 GitHub 연결은 이 workflow를 직접 dispatch하지 않으므로, 배치 PR을 병합한 뒤 저장소 관리자가 GitHub Actions 화면에서 실행한다.

## 예약 기준

- 주기: 매주 월요일
- 시각: 07:15
- 시간대: Asia/Seoul
- 대상 저장소: `btaknut/university-policy-rag-archive`
