# 프롬프트 로그

아래 항목을 실제 작업 후 추가하세요.

유형 / 실험 ID / 날짜 / 기능 / 모델·설정 / 프롬프트 경로·버전 / 입력·근거 / 실제 출력 / 문제 / 변경 이유 / 제어 / 재검증 / 한계

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

## DEV-HOME-001 홈 바이어 시간 구현
- 유형: development_instruction
- 날짜/시간: 2026-10-25 14:30경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home)
- 모델/설정: Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 프롬프트 경로·버전: 해당 없음(서비스 프롬프트 아님)
- 지시 요약: Home의 `1. 바이어 시간`만 구현. 서울·선택한 브라질 도시(상파울루 기본, 포르탈레자·마나우스·히우브랑쿠) 현재 시각, 업무 상태(공휴일 > 주말 > 업무시간 09:00~18:00 가정 > 업무시간 외), 다음 업무 시작(KST), 가까운 국가 공휴일, 도시 선택. IANA 시간대·Intl.DateTimeFormat 사용, 고정 시차 금지. 공휴일은 서버에서 BrasilAPI 조회 + 연도별 메모리 캐시 + 실패 시 대체 자료/없음 처리. 뉴스·환율·전시회·PDF·OpenAI 제외. Git 작업 금지.
- 지시와 저장소의 차이(담당자 확인 필요):
  - features/home/feature_spec.md에 지시가 참조한 `## 1. 바이어 시간` 섹션·표시 예시·엔드포인트 초안·fallback 경로가 없음. 지시 본문을 기준으로 구현.
  - docs/decisions.md에는 홈 담당이 정은진, 홍은주 담당은 미정으로 되어 있음. 사용자가 홍은주/home으로 지정해 진행.
  - 지시의 엔드포인트 초안 `/home/api/holidays`와 응답 형식은 docs/data_contracts.md(`/api/home` 접두어, `{"ok", "data"}` 감싸기)와 다름. 공통 규칙에 맞춰 `GET /api/home/holidays?year=` + `{"ok": true, "data": {source, fetched_at, holidays}}`로 구현.
- 변경 파일: features/home/routes.py, service.py, templates/home/panel.html, static/home.js, static/home.css
- 구현 판단:
  - 시각·상태·다음 업무 시작은 브라우저(home.js)에서 계산. 현지 09:00 → 실제 시점 변환은 Intl로 후보 시점의 현지 시각을 확인해 보정하는 방식(고정 오프셋 미사용).
  - 갱신 주기 1분(분 경계 정렬). 화면이 분 단위까지만 표시하므로 1초 갱신은 불필요. 홈 탭이 숨겨지면 타이머 정지, 다시 보이면 즉시 갱신.
  - 도시 선택은 보기 설정이라 `data-work-ignore`로 작성 중 감지·종료 경고에서 제외.
  - BrasilAPI는 urllib 기본 User-Agent에 403을 반환해 User-Agent 헤더를 지정. HTTP 패키지 추가 없음(표준 urllib).
  - 대체 자료 경로는 features/home/data/holidays_br_{연도}.json을 읽도록만 구현. 검증된 출처가 없어 파일은 만들지 않음.
  - 공휴일 안내는 "이번 주/다음 주" 대신 "N일 후"로 표시(10/24(토) 기준 11/2를 "이번 주"로 쓰는 예시와 주 기준이 맞지 않아 혼동 방지).
- 발견 문제: urllib 기본 요청 403(위 처리). 테스트 스크립트 콘솔 cp949 출력 오류(검증 스크립트만 해당, PYTHONIOENCODING=utf-8로 재실행).
- 검증: validation.md 2026-10-25 항목. 서버 19/19, timeout 1건, 브라우저 29/29 통과.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 업무시간 09:00~18:00 근거 미확정, 주·시 공휴일 미반영, 대체 자료 파일 없음, feature_spec 미갱신.
