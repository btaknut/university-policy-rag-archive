# HWP PDF 변환 보고서

- PDF 검증 성공: 847건
- 신규 Markdown 추출: 346건
- OCR 필요: 0건
- 검증 실패: 0건

원본 HWP는 수정하지 않았다. PDF는 한컴오피스 2020의 PDF 저장 기능으로 생성했고 pypdf로 페이지 구조와 텍스트 레이어를 다시 열어 검증했다.

## 전체 및 시각 검증

- 전체 페이지: 8,955쪽
- 전체 추출 텍스트: 7,690,096자
- PDF 용량: 162,424,849 bytes
- 모든 HWP 버전에 원본 HWP SHA-256, PDF SHA-256, PDF 경로, 페이지 수를 연결했다.
- 164쪽 지침의 첫·중간·마지막 페이지, 93쪽 규정의 중간 페이지, 1쪽 규정의 전체 페이지를 Poppler로 렌더링해 확인했다.
- 한글 글꼴, 표 테두리와 셀, 장·조문, 페이지 번호, 여백이 정상이며 잘림·겹침·검은 사각형은 발견되지 않았다.

ChatGPT 열람 경로는 `corpus/pdf/regulations`와 `corpus/pdf/guidelines`이며, RAG 텍스트는 연결된 `corpus/normalized`와 `rag/chunks.jsonl`을 사용한다.
