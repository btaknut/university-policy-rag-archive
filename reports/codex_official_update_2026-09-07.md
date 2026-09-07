# Codex 공식 원천 점검 보고서 — 2026-09-07

## 결론

- 4개 공식 원천에서 958개 레코드를 수집했다.
- 원천 접속·파싱 오류는 0건이다.
- 원문 다운로드, SHA-256 및 HWP 5.0 형식을 확인한 후보는 128건이다.
- 이번 배치는 최신 공포분 6건만 포함한다. 이 중 5건은 2026-09-03 기존 검토 배치의 미반영 항목이고, 1건은 2026-09-02 신규 게시된 학생연구자 지원 지침이다.
- 나머지 과거 누락 후보 122건은 최신 변경과 혼합하지 않고 별도 백필 배치로 분리해야 한다.

## 원천별 결과

| source_id | 수집 | 해시 일치 | 메타데이터 일치 | 신규 버전 후보 | 신규 문서 후보 | 보조 첨부 | 비고 |
|---|---:|---:|---:|---:|---:|---:|---|
| ut_regulations | 225 | 19 | 111 | 0 | 1 | 94 | 신규 문서 후보 1건은 첨부 URL·파일이 없어 배치 제외 |
| ut_guidelines | 559 | 478 | 0 | 0 | 75 | 6 | 해시 검증된 후보 1건, 게시물 메타데이터만 있는 74건은 배치 제외 |
| sanhak_regulations | 82 | 1 | 21 | 50 | 10 | 0 | 해시 검증 후보 60건은 과거 백필 대상으로 분리 |
| sanhak_guidelines | 92 | 4 | 21 | 39 | 28 | 0 | 해시 검증 후보 67건 중 최신 5건을 이번 배치에 포함 |

## 이번 배치 6건

| 시행일 | 문서 | source_id | 파일 크기 | SHA-256 | 공식 상세 페이지 |
|---|---|---|---:|---|---|
| 2026-09-02 | 학생연구자 지원 지침 | sanhak_guidelines | 660480 | `cdea9dfc1e191d1bab6c6aa337e7a9f688a7d2d62a888bba9f7688180d8b7145` | https://sanhak.ut.ac.kr/kr/html/sub06/060102.html?mode=V&no=d77679f979c0764385b7ea2298f412e2&GotoPage=1 |
| 2026-09-01 | 산학협력단 부속기관 설치 운영 지침 | sanhak_guidelines | 73728 | `9d8a4735751d34a9d1fc33488f2ecfd2321e12b5962273c189816b303c19f7a2` | https://sanhak.ut.ac.kr/kr/html/sub06/060102.html?mode=V&no=4ceb13bd32b40b2b4f4a933ee112a07c&GotoPage=1 |
| 2026-08-20 | 금고지정심의위원회 운영 지침 | ut_guidelines | 45056 | `a0a46fcdce001c66d6d89b0496dd478268539c595e9f1849231b2768089046a3` | https://www.ut.ac.kr/cop/bbs/BBSMSTR_000000000052/selectBoardList.do |
| 2026-08-18 | 연구비관리규정 세부시행지침 | sanhak_guidelines | 243200 | `a8cf6c232b9afd49ab296dec6dfcd233a362bd26cdfd6b0df31d0a12dc4479a3` | https://sanhak.ut.ac.kr/kr/html/sub06/060102.html?mode=V&no=3eeed4b4c255ab3f711e784f6ef3f8a0&GotoPage=1 |
| 2026-08-18 | 산학협력단 팀제 운영 지침 | sanhak_guidelines | 78336 | `a75e88cab80c740acbb6259f51cb50fffa42e6702dded1bd1445db55295e1820` | https://sanhak.ut.ac.kr/kr/html/sub06/060102.html?mode=V&no=9f44ca9c19da5617a3e097ce01c2400e&GotoPage=1 |
| 2026-08-18 | 연구소 설립 운영에 관한 지침 | sanhak_guidelines | 89088 | `b1ec2163a05b28cfa6275d08f677cdf4db3efe1873d9edf8ccf8286b1f3ce00c` | https://sanhak.ut.ac.kr/kr/html/sub06/060102.html?mode=V&no=57597dfb68e1c642a93547e32fb89eb0&GotoPage=1 |

## 대조 및 검증 근거

1. 기준 저장소 커밋: `92870366aa4a044945adab9b5ccfd2e07c03cf5d`
2. `metadata/versions.jsonl`의 제목 정규화, 시행일 및 SHA-256과 대조했다.
3. 6개 파일을 공식 첨부 URL에서 다시 다운로드했다.
4. 6개 파일 모두 Linux `file` 판정에서 `Hancom HWP (Hangul Word Processor) file, version 5.0`으로 확인했다.
5. 학생연구자 지원 지침은 기존 문서 `GDL-479a733267fe`, 이전 버전 `VER-20220907-4667a59c`에 연결했다.
6. 기존 5건의 ID·이전 버전 연결은 `reports/p1_official_update_batch_2026-09-03.json`과 일치시켰다.

## 수동 검토 체크리스트

- [ ] 6개 공식 상세 페이지의 제목·공포일·첨부파일을 확인한다.
- [ ] 학생연구자 지원 지침의 이전 버전 연결이 적절한지 확인한다.
- [ ] 이 배치 PR을 병합한다.
- [ ] `Apply official update` workflow를 `create_pr` 모드로 실행한다.
- [ ] `batch_path`에 `reports/codex_official_update_batch_2026-09-07.json`을 입력한다.
- [ ] 생성된 데이터 초안 PR에서 Git LFS 상태, 변환 품질, 코퍼스 검증 결과를 확인한다.

## 별도 개선 필요사항

- 공식 설정의 `include_history: true`는 매주 모든 과거 개정 이력을 다시 조회해 실행 시간이 과도하게 길어진다. 정기 점검은 최신본 중심, 과거 이력은 별도 백필 작업으로 분리하는 구성이 필요하다.
- 산학협력단 규정·지침에서 확인된 과거 누락 후보 122건은 최신 배치와 분리하여 여러 백필 PR로 나눠야 한다.
