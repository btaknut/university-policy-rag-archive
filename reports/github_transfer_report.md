# GitHub 이전 보고서

- 작업 일시: 2026-08-03 (Asia/Seoul)
- 로컬 원본: `C:\Users\kwon\Documents\university_policy_archive`
- 로컬 작업 저장소: `C:\Users\kwon\Documents\university-policy-rag-archive`
- 대상: `btaknut/university-policy-rag-archive`
- 인증 사용자: `btaknut`
- 저장소 결과: 새 private 저장소 생성 및 빈 저장소 clone
- 권한: ADMIN / push 가능
- 브랜치: `main` (신규 저장소 최초 이력)
- Pull Request: 해당 없음 — 빈 저장소 최초 main 이전

## 데이터 결과

- 원본 문서 버전: 858건
- 규정 문서 그룹: 132건
- 지침 문서 그룹: 271건
- 기타: 0건
- 현행 확정 문서: 334건
- 과거 버전: 463건
- 현행 불명확 버전: 61건
- 정확 중복: 620그룹 / 추가 출처 발생 914건
- 충돌: 32건
- 정규화 성공: 858건
- 추출 실패: 0건
- OCR 필요: 0건
- HWP 파생 PDF: 847건
- 보안 제외: 0건
- RAG 청크: 14,923건
- Git LFS 파일: 원본 1,772개 + 파생 PDF 847개
- 예상 작업 트리 크기: 약 457,295,488 bytes

## 검증·Git

- 로컬 코퍼스 검증: PASS 15 / WARNING 0 / FAIL 0
- pytest: 8 passed
- 비밀 패턴 Git 검사: 탐지 0건
- 100MB 이상 일반 Git 파일: 0건
- 데이터 커밋: `3f8dff9` (`feat: add normalized corpus and Korean legal RAG pipeline`)
- LFS/CI 검증 커밋: `d9caaef4da577b3ea21a6595416d605122253c93`
- CI: PASS — `validate-corpus` run [30775676363](https://github.com/btaknut/university-policy-rag-archive/actions/runs/30775676363)

HWP 847건은 모두 검색 가능한 PDF로 변환하고, 기존 미추출 버전 346건의 Markdown을 추가 생성했다. 복수 현행본 32건과 바이너리 내 이미지·서명·비정형 개인정보는 계속 수동 검토가 필요하다. 저장소 공개 전환은 별도 거버넌스 검토 없이 수행하면 안 된다.
