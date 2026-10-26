# 검수 기준 자료

## 현재 단계: 1단계 문구 검수 기준 (2026-10-25 수동 확보)
brazil_claim_criteria/
- source_register.md: 출처·조회 시각·버전 단서·사용권 확인 상태
- cdc_l8078_excerpt.md: CDC 관련 조항 포르투갈어 원문 발췌
- review_criteria_ko.md: 한국어 검토 기준 정리(비공식 번역)
- conar_excerpt.md: CONAR 환경 관련 조항·부속서 U 포르투갈어 원문 발췌(2026-10-25 후속 추가)

CONAR 원문 발췌·번역은 이용약관 제한으로 저장 보류. 조항 번호·제목만 기록.
후속(2026-10-25): 담당자가 CONAR를 검수 기준에 포함하는 요구사항을 유지해 발췌·비공식 번역을 추가했다. CONAR AI 이용 허가는 미확인(source_register.md).
자동 조회·변경 감지·갱신은 구현되지 않았다. 기준 자료 파일 구조·버전 관리 방식은 구현 전에 확정한다(feature_spec.md).

## 구조화 기준 묶음과 로더 (2026-10-26)
- brazil_claim_criteria/criteria_bundle.json: 위 md 자료를 문구 검수용 구조로 옮긴 기준 묶음(CDC 9개·CONAR 15개 기준, 자료 3개). 텍스트는 md의 해당 칸을 그대로 옮겼고 새 번역·해석을 만들지 않았다. CDC-118(시행 조항)은 기준이 아니라 CDC 자료의 보조 발췌로 연결.
- 로더: features/green_claim/criteria_loader.py의 load_criteria(). 불러올 때마다 md 원문 발췌·검토 정리·출처 목록과 대조하고 내용 해시를 확인한다. 하나라도 맞지 않으면 전체 실패.
- 날짜 구분: sources[].retrieved_at은 공식 자료 실제 조회 시각(2026-10-25), bundle_created_at은 묶음 작성 시각. bundle_version은 자체 버전이며 공식 판·버전이 아니다.
- 최신성: freshness.mode "stored_only" — 저장된 기준을 쓰며 공식 출처 최신성은 다시 확인하지 않았다. 해시는 변경 감지용이며 최신성·법적 효력을 증명하지 않는다.
- CONAR AI 이용 허가는 계속 미확인이다. 로더 구현은 허가 확인이 아니다.
- md 자료를 고치면 묶음의 근거 파일 해시·대응 검사가 실패한다. 묶음을 다시 만드는 갱신 절차(공식 재조회·검증 후 교체)는 다음 작업이다.

## 변경 확인과 갱신 관리 (2026-10-26)
위 마지막 문장의 "다음 작업"이 아래 도구로 추가되었다. 기본 기준 폴더(brazil_claim_criteria/)의 기존 md·묶음은 그대로 두고 직접 고치지 않는다.

폴더
- brazil_claim_criteria/: 기본(base) 기준. sources_meta.json은 묶음 생성 입력(자료별 법적 성격·역할·판·날짜·사용권 메모)으로 추가했으며 값은 기존 묶음 sources에서 그대로 옮겼다.
- criteria_versions/<버전 ID>/: 검토 후 활성화한 기준(생기면 Git에 올림). 만든 뒤 고치지 않는다.
- criteria_state/active.json: 활성 버전 포인터(생기면 Git에 올림). 없으면 base 사용. check_state.json·criteria.lock은 실행 상태라 Git 제외.
- criteria_work/: 후보·감지 기록 작업 폴더(Git 제외).

사용법(저장소 루트, jasonenv Python 3.11)
- 상태 보기(네트워크 없음): `python -m features.green_claim.criteria_admin status`
- 공식 출처 확인(네트워크): `python -m features.green_claim.criteria_admin check`
  - CDC(Planalto)만 robots.txt 확인 후 조회. CONAR 웹·PDF는 이용 조건으로 보류(코드 정책). 요청당 10초·전체 30초·출처별 2요청·5,000,000바이트, 재시도 없음.
  - 비교는 조항 단위 전체 비교다. 저장 발췌를 조항(Art.·Artigo·부속서 U 항목)으로 나누고, 공식 페이지에서 같은 조항의 시작~끝 본문 전체를 공백만 정규화해 비교한다(숫자·부정어·문장부호는 그대로).
  - brazil_claim_criteria/comparison_units.json: 각 발췌 단위가 2026-10-25 확보본에서 조항 전체(full)인지 일부(partial)인지 기록(원문 텍스트 없음). partial 단위(CDC Art. 3·6·60, CONAR Artigo 27, 부속서 U 서문)는 발췌 밖 변경을 알 수 없어 `partial_checked`(부분 확인)로만 표시한다.
  - 결과 `no_change_found`는 모든 대상 조항 전체가 저장 발췌와 같다는 뜻이며, 공식 개정·시행 여부나 대상 외 조항을 확인한 것이 아니다. 현재 기준으로는 partial 단위가 있어 CDC도 최대 `partial_checked`다.
  - 원문 발췌를 고친 후보는 comparison_units.json도 확보본 기준으로 다시 판정해야 한다(`criteria_check.html_lines` + `measure_coverage`). 판정할 수 없으면 해당 단위를 partial 또는 unbounded로 둔다.
  - `change_detected`면 criteria_work/detected/에 감지 기록이 남고 "미반영 변경" 경고가 이어진다. 기준은 자동으로 바뀌지 않는다.
- 갱신(검토한 내용만)
  1. `prepare <후보>` — 활성 기준 자료를 criteria_work/candidates/<후보>/로 복사
  2. 후보 폴더의 원문 발췌·번역·지침·출처 목록·sources_meta.json을 사람이 검토해 고친다(번역·해석은 사람이 작성, 자동 번역 없음)
  3. `build <후보> --version <자체 버전>` → `validate <후보>`
  4. 후보 폴더에 review.json 작성: reviewed_by, reviewed_at, scope, translation_reviewed: true, guidance_reviewed: true, criteria_updated_on: "YYYY-MM-DD"(이 기준 자료가 실제로 갱신된 날짜. 화면·PDF "기준 자료 업데이트 날짜". 확보일·생성일·작업일로 대신 쓰지 않음), (선택) sources_rechecked: ["SRC-…"]
  5. `activate <후보>` — 새 버전 폴더를 만들고 포인터만 교체. 이전 기준은 `rollback`으로 되돌린다.

실패 시 조치
- build 실패(CRITERIA_BUILD_FAILED): 후보 폴더의 md 누락·구간 머리글·출처 행·sources_meta.json 형식을 확인. 실패한 묶음은 남지 않는다.
- activate 거부(CRITERIA_REVIEW_MISSING): review.json 필수 항목·true 값 확인. 검토하지 않은 후보는 활성화하지 않는다.
- activate 실패(CRITERIA_ACTIVATION_FAILED): 포인터는 바뀌지 않아 기존 기준을 계속 쓴다. 남은 *.partial 폴더는 다음 activate 때 정리된다.
- 로드 실패(CRITERIA_POINTER_INVALID): active.json 손상·폴더 없음. 자동으로 base로 돌아가지 않으므로 `rollback` 또는 포인터 확인.
- 다른 작업 진행 중(CRITERIA_BUSY): 잠시 뒤 다시 실행. 프로세스가 중단돼 잠금이 남으면 600초 뒤 자동 정리되며, 진행 중인 작업이 없음을 확인했다면 `unlock --force`.
- check 실패(failed): 기존 기준을 그대로 쓴다. 실패를 "변경 없음"으로 보지 않는다. 같은 요청을 짧게 반복하지 않는다.
  - server_closed(공식 서버가 응답 없이 연결을 끊음, failed_step으로 robots/page 단계 확인): 2026-10-26 개발 환경에서 robots.txt 단계로 재현. 원인 미확정. User-Agent를 바꾸거나 robots 확인을 건너뛰지 말고, 다른 네트워크에서의 결과·사이트 이용 조건을 담당자가 확인한다. 그동안은 저장 기준과 경고로 진행된다.

## 후속 단계: 인증 갭 분석
제품별 인증 적용 범위·근거 문서·검토일·유효기간·사용 조건·문구 목록을 담당자가 검증 후 추가. 법적 요건/브랜드 요구/자발 인증 분리.
