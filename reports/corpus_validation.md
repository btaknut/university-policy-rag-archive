# 코퍼스 검증 보고서

- PASS: 20
- WARNING: 6
- FAIL: 0

## PASS — 원본 사본 SHA-256

불일치/누락 0건

## WARNING — 읽기 전용 통합 아카이브 보존

로컬 레거시 원본 미설정; source manifest와 LFS oid 검증으로 대체

## PASS — document_id 고유성

중복 0건

## PASS — version_id 고유성

중복 0건

## PASS — chunk_id 고유성

중복 0건

## PASS — 청크 원문 연결

고아 청크 0건

## PASS — 버전 참조 무결성

누락/타문서 0건, 비대칭 0건

## PASS — 버전 체인 순환

순환 시작점 0건

## PASS — 버전-source manifest 연결

역참조 누락 0건

## WARNING — latest_version_id 연결

불일치/누락 66건; 별도 PR B 보정 대상

## PASS — 메타데이터 경로

누락 0건

## PASS — HWP 파생본 완전성

한컴 PDF 847건, portable Markdown 6건, 누락 0건, PDF 오류 0건, portable 오류 0건

## PASS — 최신 확보본 단일성

복수 is_current 0문서

## PASS — 빈 청크

빈 청크 0건

## PASS — 최대 청크 크기

1,200 초과 0건

## PASS — restricted 청크 제외

위반 0건

## PASS — 인용 필드

누락 0건

## PASS — JSON Schema

오류 0건

## PASS — current_documents 부분집합

기대 337건, 실제 337건

## WARNING — latest_documents 부분집합

기대 337건, 실제 0건; PR B 생성 대상

## PASS — document_catalog 일치

문서 403건, 카탈로그 403건

## PASS — corpus_manifest 수량·해시

기준 데이터와 일치

## WARNING — 시행상태 신규 필드

미보강 버전 864건; PR B에서 추정 없이 이관

## WARNING — normalized front matter

불일치/누락 128건; PR B 재생성 대상

## WARNING — 대용량 중복 export

중복 산출물 57,258,437 bytes, 현재 청크와 불일치(오래된 bundle); 소비 경로 전환 후 별도 PR에서 제거

## PASS — 텍스트 미추출 버전

정규화 없음 0건
