# 아키텍처

## 데이터 흐름

`읽기 전용 통합 아카이브 → sources/raw → corpus/pdf(HWP 파생본) → corpus/normalized → rag/chunks.jsonl → 검색 어댑터` 순서다. 원본 계층은 증거와 해시를, PDF 계층은 ChatGPT·브라우저 호환 열람본을, 정규화 계층은 사람이 확인 가능한 텍스트를, RAG 계층은 검색 단위와 인용 문맥을 담당한다.

문서(`document_id`)는 유형과 보수적으로 정규화한 제목으로 식별하고, 실제 파일 해시마다 버전(`version_id`)을 둔다. 같은 제목이더라도 유형·부서·기존 version group 근거가 충돌하면 자동 병합하지 않는다. `version_group_id`가 문서와 개정본을 연결하며 `previous_version_id`와 `next_version_id`가 순서를 표현한다.

검색은 문서 유형·공개 범위·현행 상태 필터 후 키워드/벡터 후보를 만들고, 조문 경계와 버전 정보를 이용해 재순위화한다. 인용은 chunk에서 version과 source manifest를 역참조해 문서명, 조문, 개정일, 원본 페이지·URL·해시를 생성한다. 확인 불가능한 페이지는 비워 둔다.
