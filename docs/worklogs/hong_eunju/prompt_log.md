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

## DEV-HOME-002 홈 업계 소식 수집·표시
- 유형: development_instruction
- 날짜/시간: 2026-10-25 16:20경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음)
- 모델/설정: Claude Code (claude-opus-5-5). 서비스 AI(OpenAI) 호출 없음
- 프롬프트 경로·버전: 해당 없음(서비스 프롬프트 아님)
- 지시 요약: Home `## 2. 최신 뉴스` 중 수집·정규화·화면 표시만 구현. KOTRA 해외시장뉴스 Open API, Google News RSS 포르투갈어 검색, ABIT(Google News RSS로만, 직접 크롤링 금지). 경로별 실패 분리·재시도, 공통 형식 정규화, URL/제목 중복 제거(같은 기사면 abit 유지), 최신순, 날짜·링크 없는 항목 제외, 경로별 1시간 메모리 캐시, timeout 10초. OpenAI 요약·본문 크롤링·PDF·환율·전시회 제외. Git 작업 금지.
- 지시와 저장소의 차이(담당자 확인 필요):
  - feature_spec.md에 지시가 참조한 `## 2. 최신 뉴스` 섹션·검색어 초안·엔드포인트 초안이 없음. 지시 본문 기준으로 구현.
  - 엔드포인트는 바이어 시간과 같이 공통 규칙에 맞춰 `GET /api/home/news?refresh=kotra|google|abit`, `{"ok", "data": {items, media}}`.
  - 공통 구조의 `snippet`은 넣지 않음: Google description은 제목·매체명만 반복(실제 응답 확인), KOTRA 내용요약은 이용 조건상 표시하지 않음. `summary_ko`도 없음.
- 변경 파일: features/home/routes.py, service.py, templates/home/panel.html, static/home.js, static/home.css
- 구현 판단:
  - 표준 라이브러리만 사용(urllib, xml.etree, concurrent.futures). 패키지 추가 없음. 세 경로와 ABIT 두 검색을 병렬 요청.
  - Google 검색어: 초안 1번만 사용. 2번 `(tecido OR malharia) têxtil`은 인체 조직(tecidos e órgãos)·할로윈·축구 유니폼 등 무관 결과가 많아 제외. `-site:vietnam.vn` 제외 연산자는 결과 구성이 크게 바뀌어(100건, 특정 사이트 48건, 헌혈·구인 글) 채택하지 않음.
  - ABIT: `site:` 동작 확인(38건 모두 abit.org.br). 초안 OR 묶음은 abit.org.br만 반환해, `site:abit.org.br when:30d`와 `"ABIT" têxtil when:30d`를 따로 검색해 합침. 둘 중 하나라도 실패하면 ABIT 경로 전체를 실패로 표시.
  - KOTRA: 공공데이터포털(15034831) 페이지에 포함된 Swagger 명세로 엔드포인트·변수·응답 필드 확인. search1=브라질, search4/search7=최근 180일. 산업분류 코드(search5) 값은 확인하지 못해 쓰지 않고 제목·키워드·산업분류·품목명에서 섬유 낱말로 거름. 인증키 환경변수 이름 `KOTRA_API_KEY` 제안(.env.example 미수정).
  - 실패 시 이전 성공 수집분은 지우지 않고 "갱신 실패, 이전 수집분 표시"로 안내. 키 없음은 재시도 버튼 없음.
  - 경로별 최신 20건까지 보관·표시. 외부 문자열은 textContent로만 렌더링. 링크 target=_blank, rel="noopener noreferrer".
- 발견 문제: 초기 중복 제거에서 URL로 버린 항목의 제목을 기억하지 않아 같은 기사가 남는 경우를 단위 검증에서 발견 → 버린 항목의 URL·제목도 기억하도록 수정 후 재검증 통과.
- 검증: validation.md 2026-10-25 업계 소식 항목. 서버 38/38, 브라우저 20/20, 바이어 시간 서버 회귀 19/19.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: KOTRA 실제 데이터 응답 미확인(키 없음), KOTRA 이용허락 제4유형(상업적 이용금지·변경금지)과 사내 업무 도구 사용 적합성 미확인, Google News RSS 비공식·검색 결과 노이즈(포르투갈·베트남 매체), 링크가 Google News 경유 주소.

## DEV-HOME-003 홈 뉴스 포르투갈어 제목 AI 한 줄 요약
- 유형: development_instruction
- 날짜/시간: 2026-10-25 16:00~16:50경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5)
- 지시 요약: 기존 뉴스에 Google News·ABIT 포르투갈어 제목의 한국어 한 줄 AI 요약만 추가. KOTRA 제외, 본문 크롤링 금지, batch 요청, 구조화 JSON, 코드 검증(id·타입·길이·입력에 없는 숫자), 실패 시 제목만, 뉴스 캐시와 연계, `AI 요약` 표시, 프롬프트 버전 파일과 A(규칙)/B(규칙+few-shot) 실제 비교 기록. 공통 파일 수정 필요 시 먼저 보고. Git 작업 금지.
- 작업 전 상태: `.env.example`에 작업 전부터 있던 미커밋 변경(`KOTRA_API_KEY=` 추가). 수정하지 않음. jasonenv에 requirements.txt의 openai·pydantic·httpx2가 설치되지 않은 상태 → requirements.txt 그대로 설치(파일 수정 없음). 실행 셸 환경변수에 OPENAI 값 없음, python-dotenv 미설치.
- 지시와 저장소의 차이: feature_spec.md에 뉴스 요약 계획·가상 예시가 없음(이전 작업과 같음). few-shot 예시는 새로 만든 가상 제목 사용.
- 변경 파일: features/home/news_summary.py(신규), prompts/news_summary_v1.md·v2.md(신규), service.py, routes.py, templates/home/panel.html, static/home.js, static/home.css, tests/test_home/test_news_summary.py(신규), tests/test_home/run_news_summary_experiment.py(신규)
- 구현 판단:
  - RSS description 재확인(111건 모두 제목+매체명 반복) → 입력은 id·제목만.
  - 공통 `common.ai_client.generate_structured` 사용. Home 전용 OpenAI 클라이언트 없음. openai·pydantic은 요약 시점에만 불러와 미설치 환경에서도 뉴스는 표시.
  - 목록 응답(/api/home/news)은 이미 만든 요약만 붙이고, 새 요약은 POST /api/home/news/summaries로 따로 요청(목록을 먼저 보여 줌). 요약 대상은 서버에 수집된 뉴스만이며 클라이언트 문장을 받지 않음.
  - 요약 캐시: (id, 제목) 기준 1시간. 빈 값·검증 탈락도 캐시해 다시 묻지 않음. AI 오류는 캐시하지 않음.
  - 검증 탈락 기준: 요청하지 않은 id 무시, 같은 id 서로 다른 값이면 폐기, 문자열 아님, 여러 줄, 80자 초과(자르지 않음), 한글 없음, 제목에 없는 숫자(쉼표·점 소수 구분은 같게 봄).
  - 모델은 코드에 고정하지 않음(OPENAI_MODEL 환경변수). 실험에서는 .env의 OPENAI_MODEL이 비어 있어 .env.example 초기 후보 gpt-5.4-mini를 실험 프로세스에만 지정.
- 발견 문제: AI 요약 배지가 흰 배경에서 잘 안 보이고 요약문이 줄바꿈됨(스크린샷 확인) → badge-info + 배치 조정.
- 검증: validation.md 2026-10-25 AI 요약 항목.
- 담당자 판단: 미기재(담당자 검토 필요)

## SPE-HOME-NEWS-001 뉴스 요약 프롬프트 v1/v2 비교
- 유형: service_prompt_experiment
- 날짜/시간: 2026-10-25 16:39 (Asia/Seoul)
- 작업자/기능: 홍은주 / home 업계 소식 AI 요약
- 모델/설정: 요청 OPENAI_MODEL=gpt-5.4-mini(.env.example 초기 후보, 실험 프로세스에만 지정), 응답 모델 `gpt-5.4-mini-2026-03-17`. Responses API `responses.parse`(구조화 출력), store=False, max_output_tokens=4096, timeout 60초, 재시도 0. temperature 등 미전송(공급자 기본값, 값 미확인).
- 프롬프트: A안 features/home/prompts/news_summary_v1.md(규칙만), B안 news_summary_v2.md(같은 규칙 + 가상 few-shot 4개)
- 테스트 입력: 가상 제목 10건(A 정상 2, B 숫자 함정 2, C 정보 부족 3, D 여러 숫자 3; few-shot 예시와 다른 문장) + 실행 시점 Google News 공개 제목 20건. 버전당 1회 요청(30건 묶음).
- 실제 출력: docs/worklogs/hong_eunju/experiments/news_summary_2026_10_25_163947.json
- 결과(코드 지표):

| 지표 | v1 | v2 |
|---|---|---|
| 호출·JSON 구조 | 성공 | 성공 |
| unknown/missing/duplicate id | 0/0/0 | 0/0/0 |
| 원 출력 중 입력에 없는 숫자 포함 | 2 | 1 |
| 60자 초과 | 0 | 0 |
| 정보 부족 3건 → 빈 값 | 3/3 | 3/3 |
| 요약해야 할 가상 사례를 빈 값으로 | 0 | 0 |
| 최종 채택 요약(30건 중) | 23 | 25 |
| 토큰(입력/출력) · 시간 | 1408/956 · 5.45s | 1648/895 · 4.25s |

- 발견 문제(원 출력 관측):
  - v1 실제 제목 "Teka ... inaugura loja em um dos principais centros ..." → "매장 1곳을 연다": 제목에 없는 숫자 1 → 코드에서 폐기(정상 동작). "em um dos"(~중 하나에) 의미도 잘못 읽음.
  - v1·v2 가상 D1 "terceiro trimestre de 2026" → "3분기": 뜻은 맞지만 제목에 숫자 3이 없어 코드가 폐기(숫자 검증의 보수적 오탐).
  - 사람 판독(담당 AI의 판독이며 사실 판정 아님): v1 "resíduos florestais"→"플로레스타산 잔재"(오역), "Projeto de Lei propõe"→"국회의원이 … 제안"(주체 왜곡). v2 "Sinditec"→"산디텍", "Marca catarinense"→"카타리나 브랜드"(지명 축약 왜곡). 제목에 없는 사실 추가는 위 숫자 1건 외 확인되지 않음.
  - v1은 "~한다" 문장형, v2는 기사 제목형("~ 투자", "~ 출범")으로 짧음.
- 변경 이유·제어: 입력을 제목만으로 제한, 규칙(입력 외 정보·숫자 추가 금지, 판단 불가 시 빈 값), 구조화 출력, 코드 숫자·id·길이·한글 검증, 실패 시 제목만 표시.
- 채택: **v1 유지**. v2가 숫자 탈락 1건 적고 채택 2건 많았으나 버전당 1회 실행이고 차이가 1~2건이며, v2에도 고유명사 왜곡이 있어 few-shot이 낫다는 근거로 보지 않음.
- 재실행: 미실행(같은 입력 반복 실행으로 편차 확인 필요).
- 남은 한계: 제목만 보고 만든 요약이라 기사 내용과 다를 수 있음(원문 확인 안내 표시). 서수·숫자 낱말(terceiro, um 등) 번역은 숫자 검증에서 탈락하거나 걸러지지 않음(한국어 숫자 낱말 "두 배" 등은 검사 대상 아님). 고유명사 음역 오류는 코드로 걸러지지 않음. 앱 경로(POST /api/home/news/summaries)의 실제 OpenAI 호출은 미실행(같은 함수·스키마·검증을 실험 스크립트로 실행, 앱 경로는 모의로 확인).

## DEV-HOME-004 KOTRA_API_KEY 확정 반영
- 유형: development_instruction
- 날짜/시간: 2026-10-25 16:50경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: KOTRA 인증키 환경변수명 `KOTRA_API_KEY` 확정. 서버는 이 이름을 읽고, 값은 .env에만 두며 코드·로그·worklog·화면에 출력하지 않음. .env.example에 값 없는 `KOTRA_API_KEY=`, README에 변수명만. 키가 없으면 KOTRA만 "설정 필요", Google News·ABIT는 정상.
- 변경 파일: features/home/service.py(상태 not_configured 추가·안내 문구·주석), static/home.js(배지 "설정 필요"·notice-info), .env.example(설명 주석 1줄, 빈 줄 정리. `KOTRA_API_KEY=`는 이전 커밋에 이미 있음), README.md(KOTRA 환경변수 절)
- 구현 판단: 키 없음은 실패가 아니라 설정 문제라 media.kotra.status를 `not_configured`로 분리(error.code `key_missing`, 재시도 버튼 없음). 잘못된 키(HTTP 401/403)는 기존대로 `error`·`access_denied`.
- 확인 사항: .env의 KOTRA_API_KEY는 값 존재 여부만 확인(값 미출력). 앱은 .env를 직접 읽지 않고 jasonenv에 python-dotenv가 없어, `python app.py`만으로는 .env 값이 반영되지 않음 → README에 실행 셸 설정 또는 python-dotenv 필요로 기록.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: KOTRA 실제 데이터 응답은 여전히 미확인(이번 범위에서 실제 키로 호출하지 않음).

## DEV-COMMON-001 로컬 .env 로딩 점검
- 유형: development_instruction
- 날짜/시간: 2026-10-25 17:00경 (Asia/Seoul)
- 작업자/기능: 홍은주 / 공통 개발환경(브랜치 feature/home, 작업 전 미커밋 변경 없음)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI·외부 API 호출 없음
- 지시 요약: `python app.py` 실행 시 .env의 OPENAI_API_KEY·OPENAI_MODEL·KOTRA_API_KEY가 환경변수로 로드되도록 현재 구조 확인 후 최소 변경. 기존 로딩 방식이 있으면 새 방식 추가 금지. OS 환경변수 우선, .env 없어도 실행, 키 값 출력·기록 금지. Home 기능 추가 개발·Git 작업 금지.
- 확인 결과: 앱 코드에 .env 로딩 코드 없음. Flask 3.1.2 `Flask.run()`이 `flask.cli.load_dotenv()`를 호출(`flask run`도 같은 함수 사용)하며, python-dotenv가 있으면 실행 위치부터 상위 방향으로 .env를 찾고 이미 os.environ에 있는 키는 건너뜀(소스 확인). jasonenv에 python-dotenv 미설치, requirements.txt에도 없음 → 지금까지 .env가 읽히지 않던 원인.
- 선택: 새 로딩 코드를 추가하지 않고 Flask 기본 동작을 사용. requirements.txt에 `python-dotenv==1.1.1` 추가(README에 기록돼 있던 버전), jasonenv에 설치. load_dotenv(override=False)를 직접 호출하는 방식은 Flask가 이미 같은 동작(기존 값 우선)을 하므로 중복이라 채택하지 않음.
- 변경 파일: requirements.txt, README.md(.env 로딩 절), common/config.py(모듈 설명 주석만). Home routes/service는 변경 없음.
- 검증: validation.md 2026-10-25 .env 로딩 항목. 값은 configured/missing·일치 여부만 출력.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 프로젝트 밖 폴더에서 실행하면 .env를 찾지 못함(README에 프로젝트 루트 실행 안내). 다른 팀원 환경에는 `pip install -r requirements.txt` 재실행 필요.

## DEV-HOME-005 홈 환율 카드
- 유형: development_instruction
- 날짜/시간: 2026-10-25 16:55~17:10경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5)
- 지시 요약: Home `## 4. 환율 (추가 항목)`만 구현. USD/KRW(한국수출입은행 OpenAPI), USD/BRL(BCB PTAX OData), BRL/KRW(USD 경유 계산값), 실제 고시일, 가능 시 전일 대비, 주말·공휴일 최대 7일 역조회, 소스별 독립 실패, 서버 메모리 캐시, 환율 카드 UI. 전망·AI 해석·추천·영구 저장 금지. 엔드포인트·필드·환경변수는 공식 문서와 프로젝트 규칙 확인 후 결정. 공통 파일 수정 전 보고. Git 작업 금지.
- 지시와 저장소의 차이(담당자 확인 필요): feature_spec.md에 `## 4. 환율` 섹션이 없음(지시 본문 기준 구현). 수출입은행 키 환경변수명 확정 문서 없음 → `KOREAEXIM_API_KEY`를 코드에서만 제안 이름으로 사용, .env.example·README 미수정. .env에 해당 키 없음.
- 변경 파일: features/home/fx.py(신규), service.py(FX_SOURCES·get_fx 연결), routes.py(GET /api/home/fx), templates/home/panel.html(환율 카드), static/home.js·home.css, tests/test_home/test_fx.py(신규)
- 구현 판단:
  - 응답: `{"ok", "data": {usd_krw, usd_brl, brl_krw}}`. 소스 객체는 실패해도 항상 내려주고 status(ok|error|not_configured)·error로 상태를 알림(지시 예시의 `| null` 대신, 화면에 확인 불가 사유를 보이기 위함). brl_krw만 계산 불가 시 null.
  - USD/KRW: 수출입은행 매매기준율(DEAL_BAS_R). 날짜별 조회라 오늘(서울)부터 하루씩 최대 7일, 직전 고시값은 그 전날부터 최대 7일. 지난 날짜 응답은 날짜별 보관(오늘은 11시 전후 갱신이라 보관 안 함). 쉼표 제거 후 Decimal.
  - USD/BRL: PTAX 매도(cotacaoVenda, 공식 명세 "Cotação de venda"). 기간 조회 1회(오늘(브라질리아) 기준 14일)로 최근·직전 고시값.
  - BRL/KRW = USD/KRW ÷ USD/BRL(Decimal, 소수 4자리 반올림, 화면 2자리). 두 값이 모두 정상일 때만.
  - 전일 대비 ((현재-이전)/이전)×100, 직전 고시값이 있을 때만. 화면은 ▲ 상승/▼ 하락/– 변동 없음 + 숫자.
  - 실패 정책: 이전 값(stale)을 보여 주지 않고 "확인 불가". 정상 결과 1시간, 실패·설정 필요 결과 5분 캐시. 재시도 버튼은 해당 소스만 refresh.
  - 인증 오류(RESULT 3)·일일 한도(RESULT 4)는 재시도 버튼 없음. 로그에는 호스트·코드만(키 포함 쿼리 미기록).
- 발견 문제:
  - 1440px 3열 카드에서 "1 USD = 1,405.20 KRW"가 줄바꿈 → 환율 값 글자 한 단계·항목 이름 폭 축소.
  - 브라우저 검증 1회차 테스트 서버에서 키 환경변수를 지웠지만, 이전 작업에서 설치한 python-dotenv로 app.run이 .env를 읽어 **실제 KOTRA 호출 1회분과 실제 OpenAI 요약 batch 호출(요약 33건 생성, 로그상 1회로 판단)이 계획 없이 발생**. 재검증은 FLASK_SKIP_DOTENV=1로 실행해 추가 호출 없음.
- 검증: validation.md 2026-10-25 환율 항목.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 수출입은행 실제 데이터 응답 미확인(키 없음), 환경변수명 미확정, 수출입은행 11시 이전·비영업일 실제 null 응답 형태 미확인(명세는 null, 관측은 오류 응답만).

## DEV-HOME-006 홈 브라질 섬유 전시회 카드
- 유형: development_instruction
- 날짜/시간: 2026-10-25 17:05~17:20경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: Home `## 5. 브라질 섬유 전시회 일정`만 구현. 기능 전용 정적 JSON, 예정 행사 필터(end ≥ 서울 오늘), 시작일 순, 기본 5건·limit, D-day(D-N/D-DAY/진행 중), 장소·분야·출처·공식 확인 여부, GET /api/home/fairs, 카드 UI. 후보 Inspiramais·Tecnotêxtil Brasil·Febratex Summit을 실제 출처로 재확인, 출처 없는 항목·미확인 값 추정 금지, 다음 일정 미확인 행사 제외. 크롤링·OpenAI·KOTRA·환율 호출 금지, 테스트는 FLASK_SKIP_DOTENV=1. Git 작업 금지.
- 지시와 저장소의 차이: feature_spec.md에 `## 5.` 섹션·후보 값이 없음(지시의 후보명만 기준으로 공식 사이트 확인).
- 데이터 판단(2026-10-25 공식 사이트 조회, sources.md):
  - Tecnotêxtil Brasil 2027: 공식 사이트 뉴스(2026-09-16) "Americana, de 27 a 30 de abril de 2027", 장소 안내 "A Fidam (Feira Industrial de Americana) é a sede" → verified true.
  - Febratex Summit 2027: 공식 사이트 "24 – 26 / Agosto / 2027 – Blumenau – SC", "Parque Vila Germânica" → verified true.
  - Inspiramais 2027-01-26~27 Centro de Eventos FIERGS(Porto Alegre/RS): 공식 'O Salão' 페이지는 2027, 홈 프로그램 안내는 같은 날짜를 2026으로 표기 → verified false + note.
  - 제외: Inspiramais 2027-08-03~04 Pro Magno(같은 사이트 머리글의 '07 e 08 de julho'와 충돌), Febratex 본 박람회 2028-08-22~25(공식 문구가 '등록 마감·현장 매표' 등 지난 행사 문구와 섞여 신뢰 불가, 지시상 제외 대상).
- 구현 판단: 데이터 위치 features/home/data/br_textile_fairs.json(green_claim/data와 같은 기능 전용 기준 자료 패턴). 파일이 작아 요청마다 읽음(수정 즉시 반영, 캐시 없음). 필수 name·start·end·url(http/https)·source·verified(bool)·checked_at, city·venue·focus·note는 없으면 null → 화면 "미확인". 잘못된 항목은 제외하고 건수만 안내. 파일 없음·형식 오류는 503 fairs_unavailable → 카드만 "일정 확인 불가"+재시도. limit 1 미만·정수 아님은 400, 20 초과는 20으로 제한.
- 발견 문제: 390px에서 장소·분야 값이 항목 이름 아래로 내려감 → 값 칸 flex 조정. 브라우저 검증 1회차에서 AI 요약 안내 확인 시점이 일러 실패(첫 요약 요청 때 openai 패키지 import로 수 초 지연) → 기다리는 방식으로 고친 뒤 통과(기능 문제 아님).
- 외부 호출: 출처 확인용 공식 사이트 조회(Inspiramais·Tecnotêxtil·Febratex·Febratex Summit 페이지). 테스트 서버는 FLASK_SKIP_DOTENV=1·키 없음으로 KOTRA·OpenAI 실제 호출 없음. 단, 뉴스 회귀 스크립트(DEV-HOME-002)가 **등록되지 않은 테스트 키로 KOTRA 게이트웨이 1회 호출**(403 거부, 실제 키 미사용).
- 검증: validation.md 2026-10-25 전시회 항목.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 일정은 수동 자료라 주기적 재확인 필요(자료 확인일 표시). Inspiramais 연도 확인 필요. 분야(focus)는 공식 소개 문구를 한국어로 요약한 것.

## DEV-HOME-007 KOREAEXIM_API_KEY 확정·환율 명세 작성
- 유형: development_instruction
- 날짜/시간: 2026-10-25 17:25~17:40경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 수출입은행 환율 API 환경변수명 `KOREAEXIM_API_KEY` 확정·.env.example·README 반영, 키 발급 절차 공식 확인(사람이 직접 발급), 키가 있으면 1회만 실제 확인, feature_spec에 현재 구현 기준 환율 섹션 작성, 문서·코드 차이는 코드를 바꾸지 말고 보고. 키 값 기록 금지, 환율 로직 재작성 금지, Git 작업 금지.
- 확인 결과: 코드는 이미 `KOREAEXIM_API_KEY`를 읽음(주석만 "확정"으로 수정). `.env`에 KOREAEXIM_API_KEY 없음(이름만 확인) → 실제 USD/KRW 호출 미실행.
- 키 발급 절차(2026-10-25 공식 페이지 확인): 한국수출입은행 홈페이지 Open API › 현재환율 API › 인증키 발급신청(HPHKIR020M01?apino=2&viewtype=O). 단계 "01 약관동의/실명인증 → 02 신청서작성 → 03 발급완료". 개인정보 수집(실명인증정보·성명·이메일, 2년 보유, 재동의 시 연장), 본인인증 휴대폰 또는 아이핀. 발급 키 조회는 '나의 인증키 발급내역'(본인 확인). 공공데이터포털 3068846은 API 유형 LINK(수출입은행 명세로 연결), 자동승인 표기. 일일 1000회(초과 시 result 4). 2년 지나면 키 파기 가능(result 3).
- 변경 파일: features/home/fx.py(주석), .env.example(`KOREAEXIM_API_KEY=`와 설명 주석 추가), README.md(한국수출입은행 환경변수 절), features/home/feature_spec.md(`## 4. 환율 (추가 항목)` 신설)
- 명세·코드 대조: endpoint·환경변수·캐시(1시간/5분/지난 날짜 보관)·역조회 7일·상태(ok|error|not_configured)·오류 코드 7종·refresh·응답 필드를 실제 응답·상수와 자동 대조해 모두 일치.
- 발견한 문서 차이(수정하지 않고 보고): .env.example 2번째 줄 "앱은 .env 파일을 자동으로 읽지 않는다"가 DEV-COMMON-001 이후 README(.env 자동 로딩)와 다름. feature_spec.md 기존 `## 검증`의 "현재 기능 미구현"이 현재 상태와 다름.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 실제 키 기반 USD/KRW 응답·`deal_bas_r` 실제 형식·11시 이전·비영업일 응답 미확인. 신청서(02단계) 입력 항목·인코딩/디코딩 키 구분 여부는 본인 인증 뒤 화면이라 미확인.

## DEV-HOME-008 홈 일일 브리핑 PDF 다운로드
- 유형: development_instruction
- 날짜/시간: 2026-10-25 17:40~18:10경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 보고서 카드를 "일일 브리핑 PDF 받기"로 교체. 머리말·바이어 시간·환율·최신 뉴스(8건, AI 요약은 있는 경우만)·다가오는 전시회(3건)·출처 및 유의사항(실패 목록 포함)의 A4 동적 PDF. 기존 service·캐시 재사용, 중복 API 호출 금지, 서버 디스크 저장 금지, 부분 실패 시 해당 섹션만 확인 불가, fetch→Blob→AppShell.work.downloadBlob. PDF 라이브러리·폰트·requirements 변경은 먼저 보고. 테스트는 FLASK_SKIP_DOTENV=1·mock. Git 작업 금지.
- 사전 조사(저장소·jasonenv 변경 없이 scratchpad에만 설치): fpdf2 2.8.9(LGPL-3.0)·reportlab 5.1.0(BSD) 모두 한글·포르투갈어·링크·A4 다쪽·메모리 생성 가능. Noto Sans KR 가변 폰트는 두 라이브러리 모두 기본 굵기 Thin으로 들어가고 fpdf2 굵게 변환에 23초 → 정적 인스턴스 필요. Nanum Gothic은 포르투갈어 악센트(ç ã é ô 등) 없음, 맑은 고딕은 재배포 불가.
- 사용자 결정(질문 응답): ReportLab 5.1.0, Noto Sans KR 정적 Regular·Bold 저장소 포함, 위치 features/home/fonts/, 바이어 시간은 서버에서 화면과 같은 규칙으로 계산.
- 변경 파일: requirements.txt(reportlab==5.1.0), README.md(PDF 문장), features/home/buyer_time.py·report.py(신규), fonts/(신규 4개), service.py(연결), routes.py(GET /api/home/report/daily.pdf), panel.html·home.js(보고서 카드), tests/test_home/test_report.py(신규)
- 구현 판단:
  - 엔드포인트: data_contracts의 /api/home 접두어에 맞춰 GET /api/home/report/daily.pdf?city=. city는 화면 기준 도시 선택값(IANA, 예 America/Manaus)을 그대로 사용(지시 예시 sao_paulo 대신 현재 화면 코드값 재사용), 잘못된 값 400 invalid_city, PDF 엔진 실패 500 report_failed.
  - 데이터: get_holidays·get_fx·get_news·get_upcoming_fairs(3)를 PDF 요청당 1회씩 호출(캐시 우선, 만료 영역만 기존 정책대로 갱신). AI 요약은 get_news가 붙여 주는 캐시된 요약만 사용(PDF로 OpenAI 호출 없음). KOTRA 항목에는 요약을 넣지 않음.
  - 바이어 시간: buyer_time.py에 home.js와 같은 규칙(공휴일→주말→09~18시, 다음 업무 시작 최대 31일, zoneinfo 변환). PDF의 가까운 공휴일은 지시대로 7일 이내(화면 카드는 14일).
  - 외부 문자열은 ReportLab 문단 마크업을 이스케이프해서 넣음(제목의 < > & 확인). 링크는 http(s) URL만 <a href>.
  - 응답 헤더 Content-Disposition attachment(서울 시각 파일명), Cache-Control no-store. BytesIO만 사용, 임시 파일 없음.
  - 화면: 생성 중 버튼 disabled·aria-busy·진행 문구, 완료 시 "다운로드를 요청했습니다. 저장 여부는 브라우저에서 확인하세요.", 실패 시 notice-danger(서버 고정 문장 또는 "서버에 연결하지 못했습니다") 후 재시도 가능.
- 발견 문제: 네트워크 실패 시 브라우저 영어 원문("Failed to fetch")이 안내에 노출 → 고정 한국어 문장으로 수정. 검증 스크립트 문제 2건(WebSocket open 이벤트 놓침, 배열 비교 정규식)은 스크립트만 수정.
- 외부 호출: 조사 단계 pip(scratchpad)·Google Fonts 공식 저장소 폰트 내려받기. 브라우저 검증 서버는 FLASK_SKIP_DOTENV=1·키 없음 → KOTRA·OpenAI·수출입은행 호출 없음(Google News RSS·PTAX·BrasilAPI 공개 데이터는 Home 화면 로딩과 PDF 생성 중 조회). 계획에 없던 KOTRA·OpenAI 호출 없음.
- 검증: validation.md 2026-10-25 일일 브리핑 항목.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 헤드리스 Chrome에서 같은 페이지 두 번째 이후 다운로드가 디스크에 저장되지 않음(앱은 Blob 다운로드 요청까지 확인, 원인 미확정 — Chrome 다중 다운로드 정책 추정). 실제 사용자 브라우저 확인 필요. docs/decisions.md의 "홈 보고서 고정/동적 미정"과 feature_spec PDF 섹션은 미갱신(팀 문서).
  - (정정 2026-10-25, DEV-HOME-009) 위 원인은 통합 검증에서 다시 확인함: 두 다운로드 모두 Chrome `completed`, 같은 분 같은 파일명을 검증 환경(`allow`)이 덮어쓴 것. GUID 저장에서는 두 파일 모두 저장. "Chrome 다중 다운로드 정책 추정"은 근거가 없었음.

## DEV-HOME-009 Home 통합 검증·명세 정리
- 유형: development_instruction
- 날짜/시간: 2026-10-25 18:20~18:45경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 실제 호출 없음
- 지시 요약: 새 기능 없이 Home 전체 통합 검증, feature_spec 섹션 1~5를 현재 구현 기준으로 정리, docs/decisions.md의 Home 관련 항목은 수정 없이 비교·제안 보고, 환경변수 문서 정합성, PDF 반복 다운로드 원인 분석·수동 검증 절차. 실제 OpenAI·KOTRA·수출입은행 호출 금지(FLASK_SKIP_DOTENV=1·mock), 공개 데이터도 가능하면 mock. Git 작업 금지.
- 변경 파일: features/home/feature_spec.md(전면 정리: 목적/범위·공통 조건·환경변수·테스트, `## 1. 바이어 시간`~`## 5. 브라질 섬유 전시회`, 기존 `## 4. 환율`은 유지하고 통합 검증 한 줄 추가, 빈 "구현 전 작성"·오래된 "검증" 절 제거), tests/test_home/test_holidays_news.py(신규 모의 테스트: 공휴일·뉴스 수집 — 실제 네트워크 스크립트에만 있던 검사를 외부 요청 없이 반복 가능하게). 기능 코드 변경 없음.
- 검증 방법: 저장소 밖 fixture 서버(뉴스·공휴일·환율·OpenAI 전송을 가짜 응답으로 바꾸고 urlopen 차단)를 정상·실패 두 모드로 띄워 headless Chrome 통합 검증. 다운로드 이벤트(Browser.downloadWillBegin/downloadProgress) 기록.
- 확인한 사실(PDF 반복 다운로드): 매번 새 Blob URL, `<a download>` 클릭, 60초 뒤 revoke, 두 요청 모두 200 application/pdf·같은 크기 Blob, Chrome 두 번 모두 begin→completed. `allow` 저장에서는 같은 분 같은 파일명이라 파일 1개만 남고, `allowAndName`(GUID)에서는 2개 모두 저장 → 앱 문제 아님, 검증 환경 덮어쓰기. 실제 브라우저의 같은 이름 처리는 미확인.
- 명세·코드 자동 대조: Flask에 등록된 Home API 6개, 오류 코드 전부, 상수 12개 일치.
- 발견 사항(수정하지 않고 보고): PDF 파일명이 분 단위라 같은 분 반복 다운로드 시 이름이 같아짐(초 단위 추가는 선택 사항). .env.example 2번째 줄 "앱은 .env 파일을 자동으로 읽지 않는다"가 현재 동작과 다름(공통 파일). docs/decisions.md Home 관련 항목 갱신 필요(공통 파일, 보고서 참고).
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 실제 사용자 브라우저(Chrome·Edge·Safari·모바일) 수동 확인, 화면낭독기, 실제 키 기반 USD/KRW·앱 경로 AI 요약 실제 호출.

## DEV-HOME-010 PR 전 공통 문서·설정 정합성 점검
- 유형: development_instruction
- 날짜/시간: 2026-10-25 18:50~19:05경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음. develop 병합 커밋 a8d7ec9 이후 — 공통 PDF 입력·pypdf 반영)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: .env.example의 오래된 dotenv 설명 정정, 환경변수 4종 정합성, docs/decisions.md의 Home 관련 차이를 구현 사실/사용자 지시/팀 결정 필요로 구분(규칙상 팀 합의가 필요하면 수정하지 않고 추천안), develop PR blocker 평가. Home 기능 코드·requirements 수정 금지, README는 현재 내용이 맞으면 수정하지 않음. Git 작업 금지.
- 판단: docs/decisions.md는 AGENTS.md "공통 변경은 사전 공유 → 수정 담당 합의 → 변경 → 검토"에 따라 수정하지 않고 추천 변경안만 보고. .env.example은 사용자 지시에 따라 설명 3줄만 수정(값 변경 없음). README는 develop 병합으로 Home PDF 문장이 "PDF 라이브러리 미선정"으로 되돌아가고 패키지 목록·구현 범위 문구가 현재와 달라 해당 3곳만 최소 수정.
- 변경 파일: .env.example(2번째 줄 → .env 자동 로딩·OS 우선·.env 없어도 실행·이 파일에는 변수명과 빈 값만 3줄), README.md(현재 단계의 구현 범위 문구에 홈 구현 반영, 패키지 목록에 python-dotenv·reportlab, PDF 출력 문장 복원).
- 발견 사항: jasonenv에 develop의 pypdf 6.21.2가 미설치 → requirements.txt 그대로 설치. common/ai_client.py가 pdf_utils(pypdf)를 모듈 상단에서 import하므로 미설치 환경에서는 Home AI 요약이 ImportError 처리로 "사용할 수 없음"이 됨(코드 판독, 실행 확인 안 함) → 팀원은 병합 후 `pip install -r requirements.txt` 필요. requirements.txt 20번째 줄 "PDF 출력 도구는 기능 개발 단계에서 선정·검증 후 추가한다"는 reportlab 추가와 맞지 않음(수정 금지 대상, 보고만). README ".env 로딩"의 `flask --app app run` 동작은 Flask 소스 기준이며 직접 실행 확인은 안 함.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: decisions.md 갱신은 팀 합의 후.

## DEV-HOME-011 PR 리뷰 7건 반영(뉴스 관련성·KOTRA 노출·AI 용어 보존·PDF 가독성)
- 유형: development_instruction
- 날짜/시간: 2026-10-25 18:55~19:20경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 실제 호출 없음
- 지시 요약: 새 기능·큰 리팩터링 없이 리뷰 7건 수정. [필수] 1 뉴스 관련성(섬유 키워드, .pt 매체 제외는 RSS source 도메인 기준, 상수 상단 분리, 검색어는 근거 있을 때만) 2 KOTRA 0건 원인 구분(경로별 수집/필터 후/선정 건수 화면·PDF·로그, 상위 N건 KOTRA 최소 1건, 가짜 기사 금지) 3 AI 요약 용어 보존 규칙 + few-shot 정확히 4개(정상·수치 함정·정보 부족·용어 보존), 버전 파일. [개선] 4 PDF 뉴스 제목 링크·URL 문자열 제거·2쪽 이내 5 BRL/KRW 고시일 칸 6 쪽 번호 n / N 7 Tecnotêxtil 일정 대조. Git 작업 금지, 유료 호출 금지.
- 변경 파일: features/home/service.py(관련성 필터·제외 매체·건수·select_top_news), report.py(뉴스 선정·제목 링크·도메인 표시·고시일 칸·열 너비·n / N 캔버스·경로별 건수·제목 다음 내용과 같은 쪽), news_summary.py(PROMPT_FILE v3), prompts/news_summary_v3.md(신규), static/home.js(경로별 건수), feature_spec.md(뉴스·AI·PDF·전시회 표 전체 날짜), tests/test_home 4개 파일.
- 판단:
  - 필터 기준은 저장한 실제 RSS 4개(2026-10-25 18:56)로 정함. Google 현재 검색어 53건 중 키워드 없는 제목 28·.pt 5. 브라질로 좁힌 검색어 후보(31건)는 'moda' 단독 등 일반 노이즈가 남아 검색어는 바꾸지 않음. ABIT 사이트 공식 글은 섬유 낱말 없는 제목(세제·수출·총회)이 많아 abit.org.br는 키워드 면제. 'moda' 단독은 오탐이 있어 구문('indústria da moda' 등)만 허용.
  - portugaltextil.com(.com이지만 포르투갈 매체)·vietnam.vn은 실제 RSS 근거로 EXCLUDED_MEDIA_DOMAINS에 넣음 → 리뷰어 확인 필요.
  - KOTRA 최소 노출은 PDF 상위 8건 선정에만 적용(화면은 경로별 최대 20건 그대로 모두 표시).
  - 프롬프트는 v1·v2를 고치지 않고 v3 신규. 수치 함정 예시는 v2의 ex4, 용어 보존 예시는 'resíduos florestais → 산림 부산물'(테스트 문장과 다른 가상 제목).
- 발견 문제: 헤딩('4. 다가오는 전시회')이 1쪽 끝에 홀로 남음 → h2 keepWithNext. 출처 안내의 '수집 기록 없음(수집 기록 없음)' 중복 문구 → 사유가 있을 때만 괄호. 검증 스크립트 작성 중 셸 heredoc의 \n 처리로 테스트 파일 문자열이 깨진 것 2건 → 편집 도구로 수정(코드 결함 아님).
- 외부 호출: Google News RSS 공개 요청 4회(현재·후보 검색어·ABIT 2종 저장, 필터 근거), Tecnotêxtil 공식 사이트 1회. OpenAI·KOTRA·수출입은행 0회. 계획에 없던 호출 없음.
- 서비스 프롬프트 실험: **v3 실제 호출 실험 미실행**(사용자 요청 없음, 유료 호출 금지). 모의 테스트로 규칙·예시 4개·예시 출력의 코드 검증 통과만 확인.
- 검증: validation.md 2026-10-25 PR 리뷰 반영 항목.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 제목 키워드 필터의 누락(섬유 낱말 없는 관련 기사), v3 실제 요약 품질, 실제 KOTRA 응답에서 최소 노출 동작(모의만).

## DEV-HOME-012 Home 화면 배치·시각 우선순위 개선
- 유형: development_instruction
- 날짜/시간: 2026-10-25 19:25~19:55경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음, 직전 커밋 23d53b9)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 기능·API·PDF 로직 변경 없이 Home의 HTML/CSS/화면용 JS만으로 배치 개선. 상단 얇은 헤더+PDF 버튼, 1행 바이어 시간 1/3·환율 2/3, 2행 뉴스 2/3·전시회 1/3, 하단 `출처 및 유의사항` details. 바이어 상태 큰 문구, 환율 숫자 타일, 뉴스 내부 스크롤 제거·매체 필터 탭·더 보기(클라이언트), 전시회 D-day 강조·상세 접기, PDF 성공 안내 자동 숨김. 공통 파일 수정 필요 시 보고 후 중단. Git 작업 금지.
- 판단:
  - 상단 큰 배너·설명 문구는 공통 머리글(templates/base.html, common.css `.page-header`, 설명은 routes.py FEATURE)이고, 머리글의 '다운로드 요청됨' 칩은 공통 app_shell.js가 downloadBlob에서 표시함 → 공통 파일이라 사용자에게 확인. 답변 "Home 범위만 진행": 공통 파일·`.page-header` 덮어쓰기 없이, PDF 버튼은 공통 머리글 바로 아래 Home 도구줄에 배치. 배너 축소·칩 자동 숨김은 공통 변경안으로 보고만.
  - 반응형 기준은 design_system의 1100px(2열 기준). 1024px은 사이드바가 보이는 폭이라 세로 배치.
  - 매체 필터 건수는 화면 목록 기준(경로 사이 중복 제외 후). API의 경로별 수집/필터 후/표시 건수는 `수집 현황` 접기 영역에 그대로 유지.
  - 더 보기: API가 경로별 최대 20건(합계 최대 60건)을 이미 주므로 화면에서만 8건 → 전체 펼침/접기. 새 요청 없음.
  - 업무시간 외 상태 색을 info(파랑)에서 warning(주황)으로, 공휴일을 warning에서 danger(빨강)로 바꿈(지시 색 규칙). 판정 로직 변경 없음.
- 변경 파일: features/home/templates/home/panel.html, static/home.css, static/home.js, feature_spec.md(화면 표시 문장만).
- 발견 문제: 1차 스크린샷에서 환율 단위가 타일마다 다르게 줄바꿈, 전일 대비 줄이 어색하게 줄바꿈, 바이어 카드가 환율 카드보다 230px 김 → 단위·직전 고시일을 별도 줄로, 설명·안내를 한 줄로 줄여 차이를 165px로 줄임. `출처 및 유의사항` summary를 flex로 두어 펼침 표시(▶)가 사라짐 → list-item으로 복구. 검증 스크립트 쪽 문제(키 충돌·자르기 길이·의도한 500 오류를 콘솔 오류로 셈, 가상 요약 없음)는 스크립트·fixture만 수정.
- 외부 호출: 없음(fixture 서버가 urlopen 차단, 차단 기록 0건). OpenAI·KOTRA·수출입은행·공개 API 0회.
- 검증: validation.md 2026-10-25 Home 화면 배치 개선 항목.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 공통 머리글 높이(1440px 134px)와 머리글 '다운로드 요청됨' 칩은 공통 변경 필요. 2행은 뉴스가 길어 전시회 카드 아래에 배경 빈 공간이 남음(카드 높이를 억지로 맞추지 않음).

## DEV-HOME-013 Home 화면 2차 조정(머리글 숨김·행 높이 정렬·밀도)
- 유형: development_instruction
- 날짜/시간: 2026-10-25 19:55~20:10경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, DEV-HOME-012 미커밋 변경 위에서 이어 작업)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 스크린샷 기준 재조정. 상단 `홈` 제목·설명 영역 삭제(공통 AppShell·사이드바 수정 금지), 일일 브리핑 바 압축, 행 단위 grid `align-items: stretch`(고정 높이 금지), 바이어 카드 2열 압축·업무시간 안내 이동, 환율 타일 높이 축소, 뉴스·전시회 밀도, 카드 패딩·제목/부제/본문 간격 통일. 1440/1024/390 실제 확인. Git 작업 금지.
- 판단:
  - `홈` 제목·설명은 공통 base.html 머리글이라 Home 패널에서 지울 수 없음. 공통 파일을 고치지 않고 home.css의 `.feature-home > .page-header`를 visually-hidden 방식으로 숨김. h1은 섹션 이름(aria-labelledby)과 탭 전환 초점 대상이므로 DOM에 남김. design_system의 "탭 CSS에서 공통 클래스 덮어쓰기 금지"와 충돌할 수 있어 보고 대상(공통 쪽 대안: FEATURE에 머리글 숨김 옵션 추가).
  - 카드 패딩은 공통 `.card` 값(24px / 960px 미만 20px)을 그대로 쓰고, 일일 브리핑 바 좌우 패딩만 같은 토큰으로 맞춤. 본문 요소 간격은 `--space-3` 하나.
  - 행 높이는 stretch로 맞추되 빈 칸 요소를 넣지 않음. 바이어 카드는 도시 선택을, 환율 카드는 짧은 BRL/KRW 안내 한 줄을 카드 맨 아래에 붙임(margin-top: auto).
  - 업무시간 가정값 문장은 카드에서 빼고 `출처 및 유의사항`으로(select의 aria-describedby는 그 항목을 가리킴). 공휴일 자료 줄은 상태 안내(role=status)라 카드에 짧게 유지.
  - 기준 도시는 PDF 바에서 화면낭독용 숨은 글로만 유지(JS가 갱신하는 요소 보존).
- 변경 파일: features/home/templates/home/panel.html, static/home.css, static/home.js(표시 문구·타일 구성만), feature_spec.md(화면 표시 문장).
- 발견 문제: 1차 측정에서 환율 타일 182px(BRL/KRW 고시일·출처가 두 줄씩 줄바꿈) → 출처를 `USD/KRW ÷ USD/BRL`로 줄이고(공식 고시 아님 안내는 카드 아래 한 줄) 타일 패딩 12px로 148px. 1024px에서 도시 선택이 오른쪽 끝으로 밀림 → 열 정렬 수정. 검증 스크립트의 머리글 숨김 판정 오류(잘린 자식 크기를 셈)는 스크립트만 수정.
- 외부 호출: 없음(fixture 서버 urlopen 차단, 차단 기록 0건).
- 검증: validation.md 2026-10-25 Home 화면 2차 조정 항목.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 2행은 stretch로 외곽선은 맞지만 뉴스(8건)가 길어 전시회 카드 안 아래쪽이 비어 있음(약 570px). 1행 환율 카드는 타일과 아래 안내 사이 약 100px 여백.

## DEV-HOME-014 다음 공휴일 상시 표시·뉴스 주제 태그·다른 탭 바로가기
- 유형: development_instruction
- 날짜/시간: 2026-10-25 20:10~20:40경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음, 직전 커밋 002ca25)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 3개 기능만 추가. (A) 바이어 시간·PDF에 다음 브라질 공휴일 항상 표시(기준 도시 현지 날짜 D-day, 연말 다음 해, 실패 시 확인 불가, 기존 공휴일 캐시 재사용). (B) 뉴스 주제 태그 6종(코드 기반, 제목만, 정규화·낱말 단위, 최대 2개·표 순서, 없으면 기타), API items[].tags, 화면 주제 필터(매체 필터와 동시 적용, 클라이언트만), PDF 태그. (C) 출처 및 유의사항 위 다른 탭 바로가기 4개(사이드바와 같은 이동). feature_spec의 (4-1) 키워드 표·6절 문구를 그대로 쓰라는 지시. Git 작업 금지.
- 문서 차이(사용자 확인): 로컬 feature_spec와 모든 브랜치(develop·main·origin/*)에 '(4-1) 뉴스 주제 태그' 표, '6. 다른 탭 바로가기' 문구, '다음 공휴일 항상 표시' 명세가 없음(저장소 .md 검색 0건). 사용자에게 확인 → "그냥 진행해".
  - 키워드 표: 초안으로 작성(관련성 필터 낱말 + 필수 검증 사례 기준). 코드 상수와 feature_spec (4-1)에 "초안"으로 표시. 확정 표가 오면 NEWS_TOPIC_KEYWORDS만 교체.
  - 바로가기 문구: 새로 쓰지 않고 각 탭 routes.py FEATURE의 label·description(사이드바·머리글 원본)을 템플릿에서 그대로 사용. 효율 수치 없음.
- 판단:
  - 다음 공휴일: 서버는 buyer_time.py `next_holiday`(기존 _HolidayLookup 연도 캐시, `dates()` 추가)·`next_holiday_text`, 화면은 home.js `nextHoliday`(기존 holidayYears·ensureYear). 같은 규칙·같은 표기. 다음 해는 올해에 남은 공휴일이 없을 때만 요청. 화면의 14일 안내 문구는 다음 공휴일로 교체, PDF는 '7일 이내 공휴일' 행을 '다음 공휴일' 행으로 합치고 7일 이내 공휴일(회신 지연 가능·주말)은 같은 줄에 덧붙여 정보 유지.
  - 태그 키워드는 관련성 필터와 분리(B): 필터(포함/제외)와 분류의 목적이 다르고, 합치면 필터 결과가 바뀔 수 있음. 정규화 함수 `_plain`과 낱말 분리 방식만 재사용. KOTRA 한국어 제목은 _plain이 한글을 지우므로 한국어 키워드는 원문 포함 여부로 판정.
  - 태그는 get_news의 병합 결과에 붙임(캐시·KOTRA·Google·ABIT 공통, PDF도 같은 값 사용).
- 변경 파일: features/home/buyer_time.py, service.py, report.py, static/home.js, static/home.css, templates/home/panel.html, feature_spec.md, tests/test_home/test_report.py, test_holidays_news.py.
- 발견 문제: 390px에서 바로가기 제목 '그린 클레임 체크'가 글자 단위로 끊김 → word-break: keep-all. 검증 스크립트 정규식 이스케이프·PDF 테스트 기대값(D-7 → 현지 날짜 기준 D-8) 오류는 테스트 쪽만 수정.
- 외부 호출: 없음(BrasilAPI·OpenAI·KOTRA·한국수출입은행 0회, fixture 서버 urlopen 차단 기록 0건).
- 서비스 프롬프트 실험: 해당 없음(AI 미사용).
- 검증: validation.md 2026-10-25 다음 공휴일·주제 태그·바로가기 항목.
- 담당자 판단: 미기재(담당자 검토 필요) — 특히 태그 키워드 초안과 바로가기 문구 원본 확인 필요
- 남은 한계: 태그는 제목 키워드만 보므로 '섬유 일반' 기사는 기타가 많음(저장한 실제 RSS 33건 중 기타 19). 확정 키워드 표 반영 필요.

## DEV-HOME-015 Home 요약 대시보드 단순화
- 유형: development_instruction
- 날짜/시간: 2026-10-25 20:40~21:05경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음, 직전 커밋 5e6c5a9)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 기능·API·PDF 변경 없이 Home 표시 우선순위와 카드 높이만 조정. 바이어(상태·도시·현지 시각·다음 공휴일만, 서울 시각·다음 연락 가능 KST·공휴일 출처·업무시간 가정 숨김), 환율 높이 축소(환율명·값·전일 대비, 고시일·출처 가장 작게), 뉴스 Home 3~4건 + 기존 상세보기 동선, 전시회 compact, 뉴스·전시회 높이 비슷하게(고정 높이·빈 spacer·내부 스크롤 금지), 비율 40/60·60/40 검토. Git 작업 금지.
- 판단:
  - 숨김은 CSS(`home-buyer-extra`, 정상 상태의 `#home-holiday-source.field-hint`)로만. 계산·DOM·PDF는 그대로. 공휴일 조회 실패·대체 자료 안내(notice)는 계속 보임.
  - 상태 문구는 지시 예시대로 `지금 연락 가능`·`업무시간 외`·`주말`·`공휴일`.
  - 별도 뉴스 상세 화면은 없음(새로 만들지 않음). 기존 카드 안 '더 보기'(이미 받은 목록 펼침)를 `업계 소식 더 보기 (N건)`로 재사용.
  - 뉴스 4건(권장)에서 실측 시 전시회와 내용 높이 차이가 커서(뉴스 675px·전시회 약 403px) 범위 안의 3건으로 정함. 필터 탭을 작게 해 매체·주제 각 한 줄.
  - 전시회 카드 아래 한 줄(자료 확인일 · 방문 전 출처 확인, 기존 안내 문장)을 카드 맨 아래에 붙여 늘어난 높이에서 두 카드의 마지막 줄이 맞도록 함(빈 요소 없음).
  - 출처 및 유의사항의 공휴일 줄에서 'BrasilAPI' 이름은 빼고 설명만 유지(공휴일 출처 표시 의무 명세 없음). KOTRA 출처 표기는 뉴스 카드 하단·유의사항에 그대로.
- 변경 파일: features/home/static/home.js, static/home.css, templates/home/panel.html, feature_spec.md(화면 표시 문장).
- 발견 문제: 측정 중 전시회 카드가 '일정 확인 불가'로 표시됨 → 원인은 fixture 서버를 템플릿 수정 전에 띄워 새 요소(#home-fairs-foot)가 없던 것(Flask 템플릿 캐시). 서버 재시작 후 정상. 측정 스크립트가 이 상태를 통과로 판정해 목록 표시·오류 안내 여부를 함께 보도록 수정.
- 외부 호출: 없음(fixture 서버 urlopen 차단 기록 0건).
- 검증: validation.md 2026-10-25 Home 요약 대시보드 항목.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 1440px 2행은 외곽선과 마지막 줄은 맞지만 전시회 목록과 아래 안내 줄 사이 약 150px 여백이 남음. 별도 뉴스 상세 화면은 없음.

## DEV-HOME-016 바이어 시각 색상 표시·환율 compact·전시회 중남미 확장
- 유형: development_instruction
- 날짜/시간: 2026-10-25 21:05~21:45경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음, 직전 커밋 2fc6e62)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: (1) 바이어 카드: 큰 상태 문구 제거, 현지 시각 색으로 상태 표시 + 작은 보조 글자, 서울·다음 연락 KST·공휴일 출처 숨김, 다음 공휴일 유지 (2) 환율 compact·바이어와 높이 정렬 (3) 전시회 브라질+중남미 확장(Expotextil Perú·Colombiatex·Createx는 확인 필요, Colombiamoda·IM Intermoda 제외) (4) 지역 필터 [전체][브라질][중남미], 전체에서 브라질 최소 2건 (5) PDF 전시회 표 국가 정보. 뉴스 Home 4건. Git 작업 금지.
- 판단:
  - 바이어: 판정 로직 그대로, 표시만 변경. 작은 글자는 `연락 가능`/`연락 어려움`, 이유(주말 등)는 화면낭독용 숨은 글. 높이를 맞추려고 기준 도시 선택을 시각 위로 올려 도시명을 겸하게 함(지시의 '도시명'과 '도시 선택'을 한 컨트롤로 합침, 도시명 텍스트는 화면낭독용으로 유지).
  - 전시회 데이터: 사용자 후보 표에 출처 URL이 없어 JSON 필수 url·source를 채우려고 공개 페이지를 확인(WebSearch 3회, WebFetch 4회 중 1회 405). 공식 사이트가 아니므로 verified=false, 페이지에 없는 장소·분야는 null.
  - region 구조: 필터 구분값 `brazil`(브라질) / `latin_america`(브라질 외 중남미) 둘 중 하나로 겹치지 않게. country는 표시용 국가명. 둘 다 필수(없거나 다른 region이면 제외, 건수만 안내). 파일명 br_textile_fairs.json은 다른 참조가 많아 유지.
  - 선정: fairs.select_for_all(브라질을 앞에서부터 최소 2건 먼저, 나머지 날짜순, 결과 날짜순). PDF는 get_upcoming(3, min_brazil=2), 화면은 같은 규칙을 home.js에서 받은 목록으로 계산. API 기본 응답은 날짜순 그대로(limit만).
  - PDF 표는 열을 늘리지 않고 '도시 · 장소' 열을 '국가 · 도시 · 장소'로(2쪽 유지).
- 변경 파일: features/home/data/br_textile_fairs.json, fairs.py, service.py(상수 별칭), report.py, static/home.js, static/home.css, templates/home/panel.html, feature_spec.md, tests/test_home/test_fairs.py, test_report.py.
- 발견 문제: 측정 스크립트가 닫힌 details 안 요소(Chrome은 레이아웃함)를 내용 높이에 넣어 잘못 계산 → 스크립트 수정. 기존 검증 스크립트 3곳(필터 그룹 선택자·시각 요소 분리·탭 넘침 범위)은 구조 변경에 맞춰 스크립트만 수정.
- 외부 호출: WebSearch 3회·WebFetch 4회(전시회 출처 확인, 공개 페이지, 1회 HTTP 405). OpenAI·KOTRA·한국수출입은행·BrasilAPI 0회.
- 검증: validation.md 2026-10-25 바이어 시각·환율·전시회 중남미 항목.
- 담당자 판단: 미기재(담당자 검토 필요) — 중남미 행사 공식 사이트 확인, 브라질 최소 2건 가정값 확인 필요
- 남은 한계: 1440px 2행 전시회 목록과 하단 안내 사이 약 120px 여백, 1행 환율 카드 내용이 바이어보다 약 28px 짧음(외곽선은 같음).

## DEV-HOME-017 1행(바이어 시간·환율) compact화
- 유형: development_instruction
- 날짜/시간: 2026-10-25 21:45~22:05경 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음, 직전 커밋 336e397)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 화면 스타일·배치만. 바이어·환율 부제 삭제, 기준 도시 선택을 제목 줄 오른쪽, 시각 옆 상태·날짜 한 줄, 카드 여백 축소, 환율 타일을 얇은 띠로·출처 축약(한국수출입은행·BCB PTAX·USD 경유)·고시일 월/일, 1행 높이 약 25~35% 축소. 기능·API·계산·PDF 변경 금지. Git 작업 금지.
- 판단:
  - 기준 도시 라벨은 화면에서 빼고 화면낭독용(visually-hidden label)으로 유지. select 높이는 공통 값 그대로(42px).
  - 카드 여백: 1행 두 카드에만 Home 전용 클래스 home-summary-card로 위아래 16px. 좌우를 줄이면 아래 카드와 제목 시작선이 4px 어긋나 공통 값(24px/20px) 유지. 공통 .card 여백을 Home 범위에서 바꾸는 예외(공통 파일은 수정하지 않음).
  - 출처 축약은 JS 표시 매핑(source 키 → 짧은 이름)만. 전체 출처명·고시일·직전 고시일은 타일 title, 상세 설명은 출처 및 유의사항(기존 문장 유지).
  - 목표(25~35%)보다 많이 줄었으나(약 40%) 정보가 눌리거나 겹치지 않아 그대로 둠.
- 변경 파일: features/home/templates/home/panel.html, static/home.css, static/home.js(환율 표시 문자열만), feature_spec.md(화면 표시 문장).
- 발견 문제: 390px에서 '한국수출입은행'이 글자 중간에서 끊김 → keep-all. 1차 여백 축소에서 좌우까지 줄여 제목 시작선이 어긋남 → 좌우 복원. 기존 검증 스크립트의 부제 간격 항목은 부제가 없는 1행 카드를 빼도록 스크립트만 수정.
- 외부 호출: 없음(fixture 서버 urlopen 차단 기록 0건).
- 검증: validation.md 2026-10-25 1행 compact 항목.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 1024px은 세로 배치라 환율이 바이어 아래(1행 정렬 해당 없음).

## DEV-HOME-018 Home 색감(밝은 블루-민트) 정리
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음, 직전 커밋 e722942)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 배치는 그대로, 첨부한 regenMap 화면의 색감·UI 무드(밝은 블루그레이 배경, 흰 카드·약한 그림자, 블루·민트 포인트, 네이비 숫자, 정돈된 상태색)만 Home에 반영. 기능·API·PDF 변경 금지, 공통 파일 수정이 필요하면 보고 후 중단. Git 작업 금지.
- 판단:
  - 첨부 이미지가 대화에 들어오지 않아 지시문의 색 설명만 기준으로 함(보고에 명시).
  - design_system: 탭 CSS는 tokens.css 색만 사용, .card·.btn·body 덮어쓰기 금지. 그래서 기존 토큰(흰 면·surface-hover 블루그레이·primary 블루·accent 민트·hero 그라데이션·text 네이비)만으로 Home 고유 요소를 다듬음: 일일 브리핑 바(hero 그라데이션·옅은 테두리·약한 그림자), 필터 칩(비선택 흰색, hover 민트, 선택 블루), 분류 라벨(옅은 블루그레이), 접기 요약 hover 민트, 바로가기 hover 민트·화살표 민트, 숫자 네이비.
  - 공통 변경이 필요한 부분은 적용하지 않고 제안만: 페이지 배경 톤, 카드 테두리·그림자, PDF 버튼(.btn-primary) 색, 상태색을 더 부드럽게(새 토큰). 공통 담당 합의 필요.
- 변경 파일: features/home/static/home.css(Home 요소 색 규칙 블록 추가).
- 외부 호출: 없음.
- 검증: validation.md 2026-10-26 색감 항목.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 공통 영역(배경·카드·주 버튼·상태색)이 그대로라 전체 인상 변화는 작음.

## DEV-HOME-019 업계 소식 상세 화면·검색(Google News 추가 검색)
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경: DEV-HOME-018 색감 작업 home.css·worklog 2건 — 유지)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: '업계 소식 더 보기' → 뉴스 상세 화면(새 사이드바 메뉴 금지). 검색은 받은 뉴스에서 먼저, 없으면 사용자가 버튼을 눌렀을 때만 Google News RSS 추가 검색. RSS 결과에도 관련성 필터·.pt 제외·중복 제거·주제 태그 적용, 새 OpenAI 호출 금지, 검색어·결과 영구 저장 금지, 매체·주제 필터, 오류·재시도, Home 복귀. Git 작업 금지.
- 판단:
  - 공통 shell은 패널 id와 같은 해시만 탭으로 처리하므로, 주소를 바꾸지 않고 Home 패널 안의 두 번째 화면을 JS로 보이고 숨김(공통 변경 없음). 브라우저 뒤로 가기와는 연결하지 않음(한계로 기록).
  - '더 보기'는 카드 안 펼치기 대신 상세 화면 열기로 바꿈(카드는 4건 유지). 카드·상세가 기사 표시·필터 탭 만들기를 같은 함수로 씀.
  - 내부 검색 대상: 제목·매체·매체 도메인·주제 태그·수집 경로 이름. AI 요약은 제외(생성 번역문으로 범위가 바뀌지 않게). 악센트·대소문자 무시, 여러 낱말 AND.
  - 외부 검색: 기존 _fetch_google_rss·parse_google_rss·_collected(is_relevant_news)·news_topics 재사용. 검색어에 섬유 낱말 묶음과 when:90d를 붙임(브라질·포르투갈어는 기존 주소 설정). 상한 NEWS_SEARCH_LIMIT=20, 검색어 2~80자. 서버 캐시 없음(검색어 보관하지 않음), 같은 검색어 중복 요청은 화면에서 막음.
- 변경 파일: features/home/service.py, routes.py, templates/home/panel.html, static/home.js, static/home.css, feature_spec.md, tests/test_home/test_holidays_news.py.
- 외부 호출: Google News RSS 실제 1회(구조·필터 확인용, 검색어 'poliéster reciclado'). OpenAI·KOTRA·한국수출입은행 0회. 브라우저 검증은 fixture 서버(urlopen 차단)로 외부 요청 0건.
- 발견 문제: 검증 스크립트의 1글자 검색어 'x'가 기존 제목(예: exportação)에 들어 있어 외부 검색 안내가 나오지 않음 → 앱 동작이 맞음, 검증 문자만 'Ж'로 바꿈. 기존 검증 스크립트의 '더 보기 펼침' 항목은 바뀐 동작(상세 화면 열기)에 맞게 수정.
- 검증: validation.md 2026-10-26 업계 소식 상세 항목.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 브라우저 뒤로 가기로 상세→홈 복귀 안 됨(← 홈으로 버튼 사용). 실제 사용자 브라우저·화면낭독기 미확인.

## DEV-HOME-020 다른 탭 바로가기 제외
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/home, 작업 전 미커밋 변경 없음)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: Home 하단 '다른 탭 바로가기'(시장 분석·제품소개서·그린 클레임 체크·홍보 스튜디오)를 구현하지 않음. 이미 구현됐으면 Home에서 그 영역만 제거. 공통 사이드바·다른 탭 주소는 수정 금지. feature_spec 정리, worklog에 실제 이유 기록. Git 작업 금지.
- 변경 이유: 중복 navigation 방지 및 Home 단순화를 위해 제외(공통 왼쪽 사이드바에 같은 탭 이동이 이미 있음).
- 변경 파일: features/home/templates/home/panel.html(바로가기 nav 삭제), static/home.css(바로가기 스타일 2곳 삭제), feature_spec.md(6절을 '제외'로, 화면 배치 문장에서 바로가기 삭제). JS·Python·공통 파일 변경 없음.
- 외부 호출: 없음.
- 검증: validation.md 2026-10-26 바로가기 제외 항목.
- 담당자 판단: 미기재(담당자 검토 필요)

## DEV-COMMON-002 공통 블루·아쿠아·민트 대시보드 UI 정리
- 유형: development_instruction
- 날짜/시간: 2026-10-26 16:31 (Asia/Seoul)
- 작업자/기능: 홍은주 / 공통(common_setup) (브랜치 feature/common_setup, 작업 전 git status clean)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: resources/design/dashboard_reference.png의 색감·카드 질감·버튼·상태 표현·인터랙션 분위기만 참고해 fionex 전체 공통 디자인을 밝은 블루·아쿠아·민트 B2B 대시보드로 통일. 배치 복제 금지, 기능 정보 구조·업무 흐름 유지. tokens.css 우선 정리(hex 반복 금지), 배경·사이드바·카드·버튼·입력·숫자·배지/태그·notice·표·인터랙션·탭 진입 효과·reduced-motion·shell 정리. 공통 기능 로직은 필요하면 이유·영향 확인 후 최소 수정. feature 파일은 공통 변경으로 해결 안 될 때만. 5개 탭 × 1440/1024/390 실제 검증, design_system.md 갱신, Git 작업 금지, 한국어 보고.
- 판단:
  - 기능 CSS 5개는 hex/rgba 없이 공통 토큰만 사용 → 기존 변수 이름은 유지하고 값만 바꾸면 5개 탭에 일관 반영(기능 파일 수정 불필요). 새 변수는 보조(`-border`, neutral, aqua, primary-gradient, shadow-hover/primary, focus-halo, motion, overlay)만 추가.
  - 블루는 기존 #1f63d8(royal에 가까움)을 #1d6ad4로 약간 맑게. 주 버튼 그라데이션 끝 색 #1677c4도 흰 글자 4.7:1. hover 그라데이션 후보(#1a80cc 끝)는 4.20:1로 미달 → hover는 색 변경 없이 그림자·1px 상승만.
  - 모서리: 버튼 pill → 10px(모바일 앱 느낌 제거), 카드 18 → 16px, md 12 → 10px. 배지·상태 칩만 pill 유지.
  - notice: 4px 왼쪽 선 + 진한 tint → 옅은 tint + 1px 상태 테두리 + 3px 강조선, 제목을 상태 글자색으로(아이콘 없이 뜻 전달), 본문 네이비.
  - 배지: 기본 `.badge`를 흰 배경→neutral(블루그레이)로. 분류 라벨용 `.badge-neutral`(점 없음)·`.tag` 추가. 기존 기능 코드의 배지는 모두 상태 modifier가 붙어 있어 영향 없음.
  - 숫자: Home·시장 분석 CSS가 이미 숫자 요소에 tabular-nums 적용 → 공통은 `.num`/`.tabular-nums` 유틸과 표 숫자 칸만 추가(body 전체 적용은 하지 않음).
  - 탭 진입: CSS만으로 `.feature-panel:not([hidden])`에 220ms 1회 애니메이션(app_shell.js 변경 없음). fill-mode backwards라 끝난 뒤 transform이 남지 않음(그린 클레임 fixed 팝오버 기준 박스 영향 없음).
  - 공통 기능 로직: 변경 없음. 5개 탭 로딩(.spinner+텍스트+disabled+aria-busy)·오류(.notice-danger/.field-error)가 이미 공통 체계 사용. 일회성 성공 안내는 Home(4초 자동 숨김)·시장 분석(안내 문장)·그린 클레임(다음 상태 변화 때 지움)이 각자 처리 중이고, 그린 클레임 성공 문구는 "브라우저 다운로드 목록에서 확인" 안내·면책 문장을 담고 있어 자동 숨김 시 정보 손실 → 공통 자동 숨김을 강제하지 않음. 통일이 필요하면 opt-in helper(AppShell 쪽)를 담당자 합의 후 추가하도록 제안만 함.
  - base.html·app_shell.js: DOM·id·data 속성 변경 필요 없음 → 수정하지 않음.
- 변경 파일: static/css/tokens.css, static/css/common.css, docs/design_system.md. (features/·base.html·app_shell.js·common/·.env.example·requirements.txt 변경 없음)
- 외부 호출: 0건(검증 서버에서 urllib.request.urlopen 차단, API 키 제거, FLASK_SKIP_DOTENV=1).
- 발견 문제: 첫 상호작용 검사에서 입력 초점 링이 비어 보였음 → 150ms transition 진행 중 측정한 검증 스크립트 문제, 300ms 대기 후 재측정 통과(코드 수정 없음). Playwright `networkidle` 대기는 페이지 주기 요청으로 끝나지 않아 `load`+3초 대기로 변경.
- 검증: validation.md 2026-10-26 공통 대시보드 UI 항목.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 실제 사용자 브라우저(Edge·Safari·모바일 기기)·화면낭독기·Windows 고대비 모드 미확인. 다른 담당자 탭은 공통 토큰 변경으로 색·모서리가 함께 바뀜(팀 공유 필요). 시장 분석의 '브라질 · 수입'은 분류 성격이지만 기능 코드가 badge-info를 써서 블루로 남음(담당자 판단 필요).

## DEV-COMMON-003 시장 분석 '브라질 · 수입' 분류 배지 정리 (DEV-COMMON-002 후속)
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / 공통 + market_analysis (브랜치 feature/common_setup)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 홍은주가 공통 UI와 5개 탭(Home·시장 분석·제품소개서·그린 클레임 체크·홍보 스튜디오)을 모두 담당하기로 확정. features/ 직접 수정 가능, 공통 디자인과 의미가 맞지 않는 부분은 직접 정리.
- 정정: DEV-COMMON-002 '남은 한계'의 "담당자 판단 필요"는 담당 범위 확정으로 해소. 아래처럼 직접 수정함.
- 변경: features/market_analysis/templates/market_analysis/panel.html — 고정 대상 시장 라벨 `badge badge-info` → `badge badge-neutral`.
  - 기존 동작: 상태(정보) 배지처럼 블루 + 점 표시.
  - 변경 동작: 분류 라벨(블루그레이 rgb(71,86,110) / rgb(238,242,247), 점 없음). 문구·위치·JS·API·PDF(pdf_report.py의 같은 문구) 변경 없음.
  - 이유: 상태가 아닌 단순 분류 라벨에 상태색을 쓰지 않는다는 design_system 배지 규칙에 맞춤.
- API contract 변경: 없음.
- 검증: validation.md 2026-10-26 DEV-COMMON-003.
- 담당자 판단: 미기재(담당자 검토 필요)

## DEV-COMMON-004 5개 탭 로딩·오류·성공·다운로드 UX 점검과 공통 패턴 정리
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / 공통 + home·market_analysis·green_claim·product_brochure·promotion_studio (브랜치 feature/common_setup, 작업 전 git status clean, 최근 커밋 8e6bb38)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 5개 탭의 로딩·오류·성공·다운로드 UX를 먼저 감사하고, 버튼 disabled·aria-busy·작업 중 문구, 중복 요청 방지, 오류 notice(자동 제거 금지·원문 노출 금지), 성공 A(일회성 3~5초)/B(유지) 구분, 다운로드 공통 helper·Blob URL 해제, finally 복원, race·탭 이동, 접근성을 정리. 비즈니스 로직·API contract 변경 금지(명백한 UX 버그만 최소 수정). Git 작업 금지.
- 감사 결과 요약: Home·그린 클레임은 busy 플래그·finally 복원·재시도·고정 문장 오류가 이미 갖춰짐(그린 클레임은 요청 번호·AbortController·시간 제한까지). 다운로드는 3개 탭 모두 AppShell.work.downloadBlob(60초 뒤 revoke) 사용, 탭별 임시 <a> 구현 없음. 제품소개서·홍보 스튜디오는 미구현(버튼 disabled, API 없음).
- 발견 문제와 판단:
  1. 시장 분석 PDF 중복 요청 가능(버그): PDF 요청 중 플래그가 없어, PDF 생성 중 '다시 불러오기'·AI 분석이 끝나면 updatePdfButton이 PDF 버튼을 다시 켬 → pdfBusy 추가.
  2. 시장 분석 브라우저 오류 원문 노출(버그): 조회·AI·PDF catch가 err.message를 그대로 표시 → fetch 실패 시 "Failed to fetch", AI 응답이 JSON이 아니면 SyntaxError 문장. 서버 오류 객체({code,message})만 표시하고 Error는 고정 문장으로.
  3. 시장 분석 PDF 결과가 작은 안내 문장에만 표시되고 화면낭독기 전달 없음, 성공 문구는 다음 상태 변화까지 남음 → 결과 카드에 aria-live 안내 영역 추가, 성공 notice-success 4초 뒤 제거(A), 실패 notice-danger role=alert 유지. 응답이 application/pdf가 아니면 실패 처리(서버는 항상 application/pdf로 응답, 정상 흐름 영향 없음).
  4. 시장 분석 바이어 목록 실패 시 "새로고침해 주세요"(새로고침하면 다른 탭 작업 소실, 앱 정책과 충돌) → 같은 자리 재시도 버튼.
  5. Home 오류 notice(뉴스·환율 요청 실패, PDF 실패)에 role 없음 → 화면낭독기 전달 안 됨 → role=alert, 전시회 확인 불가는 role=status.
  6. 5개 탭 모두 실행 중 버튼 문구가 그대로 → 공통 AppShell.ui.setButtonBusy(button, label) 추가(문구 교체·aria-busy, disabled는 기능 코드가 계속 관리해 기존 활성 조건과 충돌 없음). CSS로 작업 중 버튼은 원래 색 + 작은 회전 표시(점선 '사용 불가'와 구분). 버튼 옆 스피너가 있던 Home PDF 진행 문구는 삭제, 그린 클레임 상태 문장은 스피너만 뺌.
  7. 로딩 문구 혼재("~하는 중"/"검색 중...") → Home 영역 문장 '...'로 통일. 소요 시간·요금 안내 문장은 의미가 있어 유지.
  8. 제품소개서·홍보 스튜디오 결과 카드 PDF 버튼이 '준비 중' 안내와 연결 안 됨 → aria-describedby로 기존 안내 연결.
- 문제 없음으로 판단(수정 안 함): 오류 후 버튼 영구 disabled(모든 경로 finally/취소 함수에서 복원), Blob URL 미해제(downloadBlob 60초 revoke), 같은 notice 누적(Home은 id로 교체, 그린 클레임 replaceChildren), 성공 메시지 누적, 오류가 빨리 사라짐(자동 제거 없음), 탭 이동 후 loading 꼬임(브라우저 확인), race(그린 클레임 seq, Home·시장 분석은 버튼 잠금으로 순서 보장 → AbortController 추가 안 함). 일회성 성공 자동 제거 공통 helper는 2곳(Home·시장 분석)뿐이라 만들지 않고 4초를 문서 기준으로 둠.
- Chrome에서 초점 있는 버튼을 disabled로 바꿔도 activeElement 유지 확인 → 초점 복구 코드 추가 안 함(다른 브라우저 미확인).
- 변경 파일: static/js/app_shell.js(AppShell.ui.setButtonBusy), static/css/common.css(작업 중 버튼), features/home/static/home.js·templates/home/panel.html, features/market_analysis/static/market_analysis.js·templates/market_analysis/panel.html, features/green_claim/static/green_claim.js, features/product_brochure/templates/product_brochure/panel.html, features/promotion_studio/templates/promotion_studio/panel.html, docs/design_system.md, features/home·market_analysis·green_claim/feature_spec.md.
- API contract 변경: 없음(요청·응답 형식, 라우트, 서버 코드 변경 없음).
- 외부 호출: 0건 전송. 검증 서버에서 urlopen 차단(시도 45건 모두 차단: news.google.com·brasilapi.com.br·olinda.bcb.gov.br), ComexStat 함수는 가상 수치 모의, OpenAI 키 없음.
- 발견 문제(검증 도구): 모의 실행기에 `if __name__ == "__main__"`가 없어 그린 클레임 PDF 별도 프로세스(Windows spawn)가 실행기를 다시 실행 → PDF 30초 시간 제한 실패(UI는 실패 notice·버튼 복원으로 올바르게 처리). 실행기 수정 후 재실행 통과. 앱 코드 문제 아님.
- 검증: validation.md 2026-10-26 DEV-COMMON-004.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: JS 단위 테스트 체계가 없어 setButtonBusy는 브라우저 검증만. Firefox·Safari·화면낭독기 미확인. 시장 분석 AI 실행 버튼은 실행 시 결과 블록이 다시 그려져 초점이 사라짐(기존 동작, 이번 미수정). 시장 분석 AI 실제 실행·성공 화면은 유료 호출이라 미실행.

## DEV-COMMON-005 결과 영역 초점·키보드·화면낭독 흐름 정리
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / 공통 + market_analysis·home (감사: 5개 탭) (브랜치 feature/common_setup, 작업 전 git status clean, 최근 커밋 65f6e86)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 결과 생성·갱신 때 초점 상실·위치 인지 문제를 감사 후 정리. 시장 분석 AI 결과 후 초점 상실 우선 재현. 자동 로딩은 초점 이동 금지, 사용자 실행으로 큰 결과가 생기면 결과 제목 초점 검토, 짧은 완료는 status, 오류는 alert·첫 오류 필드, 성공 안내로 초점 뺏지 않음, disabled→enabled 버튼 자동 초점 금지, tabindex=-1, preventScroll + reduced-motion 스크롤, 큰 결과 전체 aria-live 지양, skip link·landmark·heading 확인. API·계산 변경 금지, Git 작업 금지.
- 정정(DEV-COMMON-004): "Chrome에서 초점 있는 버튼을 disabled로 바꿔도 activeElement 유지"는 잘못된 결론이었음. 렌더링이 없는 빈 테스트 페이지(setContent)에서만 측정한 결과였고, 실제 앱 페이지에서는 disabled로 바꾸는 순간 초점이 body로 이동함(focus fixup, 재현 결과 아래). 그래서 이번 작업에서 공통 복원 처리를 추가함.
- 재현(수정 전, 모의 서버·키보드 Enter): 분석 완료 후 activeElement BODY, 결과 제목 화면 위치 top -127(화면 밖), 결과 영역 aria-live=polite에 2,874자; AI 실행 중·완료 후 BODY(실행 버튼이 innerHTML로 다시 그려짐), 그 상태에서 Tab → 결과 표 안 링크; 바이어 재시도 성공 후 BODY; 바이어 목록 aria-live=polite에 82,992자. skip link·main#main-content·nav 레이블·탭별 heading(h1→h2→h3)은 정상.
- 판단:
  - 같은 패턴(버튼 disabled로 초점 상실, 결과 시작점 초점+스크롤)이 시장 분석 3곳·Home 2곳·그린 클레임 4개 버튼에 반복 → AppShell.ui에 작은 helper 2개.
    1. setButtonBusy: 시작 때 버튼에 초점이 있었으면 기억, 끝났을 때 초점이 비어 있고(body) 버튼이 활성·보이면 버튼으로 복원(setTimeout 0: disabled 복원이 뒤에 오는 기능 대비). 기능이 결과·오류 칸으로 옮겼으면 건드리지 않음.
    2. focusResult(target, {scroll, from}): tabindex 없으면 -1 부여, focus(preventScroll) 후 scrollIntoView(reduced-motion이면 auto). 숨겨진 탭/화면·detached 대상, 또는 사용자가 작업 중 from 밖으로 초점을 옮긴 경우 옮기지 않음(탭 이동 중 끝난 작업이 초점을 뺏지 않음).
  - 시장 분석: 분석 완료 → '분석 결과' h2(tabindex=-1)로 초점·스크롤(넓은 화면 오른쪽 위/좁은 화면 입력 아래에 결과가 생겨 위치 인지가 필요, 다음 행동 PDF·AI·그래프가 결과 안). AI 실행 시작·완료 → '④ AI 분석' region에 초점(버튼이 다시 그려지는 구조는 유지, 대규모 렌더링 리팩터링 안 함). 결과·바이어 aria-live 제거, 숨은 role=status 문장으로 짧게 알림. 바이어 재시도 성공 → 목록 제목, 다시 실패 → 새 재시도 버튼. 입력 오류 첫 필드 초점은 기존 유지. 결과 안 '브라질 수입' 라벨 badge-neutral(분류).
  - Home: 자동 로딩 초점 이동 없음 유지. PDF 완료/실패는 helper 복원으로 버튼 초점. 업계 소식 상세 'Google News에서 검색'이 검색 중 disabled·성공 후 hidden으로 초점 상실 → 성공 시 결과 건수 문장(role=status), 실패 시 다시 검색 버튼.
  - 그린 클레임: 기존 구조(중간 단계 초점 이동 없음, 최종 검수 결과 때만 3단계 제목 초점, 단계 aria-live) 유지. 버튼 초점 복원만 helper로 더해짐(코드 변경 없음).
  - 제품소개서·홍보 스튜디오: 미구현이라 변경 없음(disabled 버튼은 Tab에서 빠지고 '준비 중' 안내 연결은 DEV-COMMON-004에서 완료).
  - 스크롤 위치: 처음엔 결과 제목이 화면 맨 위에 붙어 초점 테두리가 잘리고, 390px에서는 sticky 상단바(56px)에 가려짐(캡처로 발견, 검증 스크립트 기준이 느슨했음) → common.css에서 [tabindex="-1"] scroll-margin-top 24px(960px 미만 상단바+16px). 그린 클레임 단계 제목·Home 상세 제목에도 적용됨.
  - skip link·main·nav는 이미 있음 → 추가하지 않음. heading 위계 명백한 오류 없음 → 수정 없음.
- 변경 파일: static/js/app_shell.js, static/css/common.css, features/market_analysis/static/market_analysis.js·templates/market_analysis/panel.html·feature_spec.md, features/home/static/home.js·feature_spec.md, docs/design_system.md, tests/test_common/test_shell_a11y.py(신규).
- API contract 변경: 없음. 계산·필터·판정 로직 변경 없음.
- 외부 호출: 0건 전송(urlopen 차단 시도 104건 모두 차단, ComexStat 모의, OpenAI 키 없음, 시장 분석 AI 응답은 브라우저 route로 가상 응답).
- 발견 문제(검증 도구): 검증 서버가 템플릿 수정 전에 시작돼 이전 템플릿을 캐시(debug 꺼짐) → 재시작. 테스트 기대값 오류 1건(결과 제목에서 Shift+Tab의 앞 요소는 왼쪽 열 '다시 불러오기'가 맞음), PDF 생성 대기 부족 1건 → 스크립트 수정. Git Bash의 `python -`가 멈춰 해당 프로세스만 종료.
- 검증: validation.md 2026-10-26 DEV-COMMON-005.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 실제 화면낭독기(NVDA·VoiceOver) 미실행(DOM role·aria 점검만). 작업 중에는 초점이 body에 머무름(끝나면 복원) — disabled 대신 aria-disabled로 바꾸면 작업 중에도 유지되지만 3개 탭 버튼 로직 변경이 커서 이번 범위 밖. Firefox·Safari 초점 동작 미확인. ④ AI 분석 summary 안의 h3(details/summary 안 heading)는 기존 구조 유지.

## DEV-COMMON-006 공통 사이드바·상단바에 FIONEX 공식 로고 적용
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / 공통(common_setup) (브랜치 feature/common_setup, 작업 전 git status clean, 최근 커밋 3ce7907)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: 사용자 제공 FIONEX_LOGO.png로 임시 CSS 로고(.brand-mark) 교체. 사이드바 150~170px·상단바 110~130px, height auto, 비율 유지, 텍스트 중복 금지, 슬로건 포함 원본 사용, 투명 여부 확인(배경 있으면 CSS로 제거하지 말고 보고), filter·배경 박스·과한 hover 금지, alt="FIONEX", 심볼 crop 금지, 팔레트 변경 금지, design_system에 Brand 규칙. Git 작업 금지.
- 원본 확인(사용자 Downloads/FIONEX_LOGO.png, 870,173 bytes): 2172×724(3:1), RGBA, 네 모서리 알파 0(투명 배경). 완전 불투명 픽셀 0.2%(글자 알파 약 202~253, 빛 번짐 반투명) → 흰 배경 합성 미리보기로 글자·리본 식별 확인, 처리 없이 원본 사용. 내용 영역(알파>32) x 127~2032 → 좌우 투명 여백 약 6%.
- 판단:
  - 경로: 기존 공통 asset 폴더 static/assets/(README: 공개·사용 허가 자료) + 이름 규칙 snake_case → static/assets/fionex_logo.png(원본과 바이트 동일, 파일 1개).
  - 기존 브랜드는 링크가 아닌 span → 링크를 새로 만들지 않음(홈 이동은 메뉴 '홈'과 중복). 사이드바·상단바 모두 같은 img, alt="FIONEX", width/height 원본 값으로 자리 확보.
  - 크기: 사이드바 168px(높이 56px), 상단바 120px(높이 40px, 상단바 56px 안). tokens.css에 --brand-logo-width, --brand-logo-width-compact 추가. 작은 화면 메뉴(드로어)는 닫기 버튼과 같은 줄이라 max-width:100%·min-width:0으로 넘치지 않게.
  - 정렬: 원본 왼쪽 투명 여백 때문에 로고 글자가 메뉴 아이콘보다 약 10px 안쪽 → .sidebar-head 좌우 padding --space-3 → --space-1(측정: 로고 글자 시작 약 29.8px, 메뉴 아이콘 28px).
  - .brand-mark는 base.html 한 곳만 사용 → DOM·CSS 삭제. .sidebar-brand/.topbar-brand의 글자 스타일(크기·굵기)도 텍스트가 없어져 삭제.
  - 파일 크기 870KB를 168px로 표시: 지시가 원본 사용·파일 하나라 리사이즈 사본을 만들지 않음(남은 문제로 보고).
- 변경 파일: static/assets/fionex_logo.png(신규), templates/base.html, static/css/common.css, static/css/tokens.css, docs/design_system.md, tests/test_common/test_shell_a11y.py(로고 구조 테스트 1건 추가).
- 외부 호출: 0건(검증 서버 urlopen 차단).
- 검증: validation.md 2026-10-26 DEV-COMMON-006.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 사이드바 168px에서 슬로건 글자 높이가 약 5px라 1배율 화면에서는 읽기 어려움(원본 축소 지시대로 유지). 870KB PNG를 작은 크기로 표시(첫 로딩 부담) — 표시 크기 2배 정도로 줄인 최적화 사본은 담당자 결정 필요. 로고 사용권·출처 기록(assets.md)은 사용자 제공 파일이라는 사실만 기록.

## DEV-COMMON-007 웹 UI 브랜드 폰트(Brand New Hyosung) 적용
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / 공통(common_setup) (브랜치 feature/common_setup, 작업 전 상태: 사용자가 만든 미추적 static/fonts/ 외 변경 없음, 최근 커밋 cdec84d)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 요약: static/fonts/brand/의 실제 파일로 @font-face 등록(파일명 그대로, 없는 굵기 가정 금지), --font-sans를 Brand New Hyosung 우선으로, 400/600 합성 점검·토큰 정리, 개별 font-family 정리, 버튼·입력·file 버튼·표·KPI·차트 SVG 글꼴 확인, 한·영·포 글리프 확인, 줄바꿈 회귀, PDF 변경 금지, 외부 CDN 금지, 실제 computed font·HTTP 200 확인. Git 작업 금지.
- 현재 구조 조사: 글꼴은 tokens.css --font-sans 한 곳 + common.css body만 사용, 기능 CSS의 font-family 0건(font: inherit 4곳은 컨트롤 상속용), 굵기는 모두 토큰 경유(직접 숫자 0건), @font-face 없음.
- 폰트 확인(fontTools 4.55.3, 세션 임시 폴더 설치 — 저장소·requirements 미변경): Light/Medium/Bold usWeightClass 300/500/700, family 'Brand New Hyosung', 한글 11,172/11,172, ASCII 전부, 숫자 폭 균일. 포르투갈어 악센트 문자 전부 없음(á ã â à ç é ê í ó õ ô ú ü 대·소문자), – — • € 없음. 저작권 'Copyright (c) 2023 by HYOSUNG CORPORATION. All rights reserved.', 라이선스 문구 없음, fsType 4.
- 판단:
  - @font-face는 공통 CSS 맨 앞(common.css), 경로 ../fonts/brand/<원본 파일명>(공백 포함, 따옴표 URL). 매핑은 메타데이터 그대로 300/500/700.
  - 굵기: 400 요청 시 브라우저가 500을, 600 요청 시 700을 고르므로 합성은 없지만, 토큰을 실제 파일에 맞춰 명시(regular·medium 500, semibold·bold 700) + body font-weight 지정. 화면이 지나치게 굵어지지 않는지 1440/1024/390 캡처로 확인(본문 Medium이 데이터 화면 가독성에 적합). 이전 시스템 글꼴(Malgun: 400/700만)에서도 600은 이미 700으로 그려졌으므로 강조 굵기 체감 변화는 작음.
  - fallback 순서는 기존 스택 앞에 브랜드 폰트만 추가. 포르투갈어 악센트 대체 글꼴로 Segoe UI를 앞에 두는 안을 캡처로 비교했으나 Malgun과 차이가 작아 지시 스택 유지.
  - ::file-selector-button이 Arial로 그려짐(실측) → font: inherit. body 기본 굵기 400 요청(실측) → 토큰 지정. select의 option 목록은 OS가 그리는 드롭다운이라 400 그대로(측정 제외).
  - 차트 SVG text는 HTML 상속으로 이미 브랜드 폰트(실측) → .ma-svg text 규칙 추가 안 함. 기능 CSS 변경 없음.
- 변경 파일: static/css/common.css(@font-face 3개, body 굵기, file 버튼 font), static/css/tokens.css(--font-sans, 굵기 토큰), docs/design_system.md(Typography), tests/test_common/test_shell_a11y.py(폰트 로컬 파일·외부 CDN 없음 테스트). static/fonts/brand/*.ttf 3개는 사용자가 넣은 파일 그대로(변경 없음, 미추적 상태).
- PDF: 변경 없음(features/*/fonts, report·pdf 코드 diff 0).
- 외부 호출: 0건(브라우저 외부 요청 0, 서버 urlopen 차단).
- 검증: validation.md 2026-10-26 DEV-COMMON-007.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 포르투갈어 악센트·– — • €는 시스템 글꼴 대체(모양·굵기 섞임), 웹 사용권 미확인(fsType 4·라이선스 문구 없음), 폰트 2.6MB 첫 로딩(서브셋·woff2 변환은 사용권 확인 후 검토), Flask가 .ttf를 application/octet-stream으로 응답(브라우저 로드는 정상), macOS·모바일 실제 렌더링 미확인.

## DEV-COMMON-008 웹·모든 탭 PDF 글꼴을 Pretendard로 통일
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / 공통 + home·market_analysis·green_claim PDF (브랜치 feature/common_setup, 작업 전 미커밋: DEV-COMMON-007 브랜드 폰트 변경 7개 파일·미추적 static/fonts/)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 원문: "글꼴 C:\Users\user\Documents\AX2\fionex\static\fonts\Pretendard-1.3.9 여기있는걸로 통일해주고 파일명도 리드미에 맞춰서 통일해주고 우리 전체탭 pdf 도 이 글꼴로 해줘"
- 판단:
  - '리드미'는 Pretendard 폴더에 README가 없어(LICENSE.txt만), 공식 배포본 파일명 규칙(`Pretendard-<굵기>`)을 그대로 쓰고 새 공통 폴더에 README.md(파일·용도·원본 경로·SHA-256·라이선스·글리프)를 만들어 이름을 그 표와 일치시키는 것으로 해석.
  - 배포본(67MB) 전체를 쓰지 않고 필요한 파일만 `static/fonts/pretendard/`로 복사(원본과 바이트 동일 확인): 웹 woff2 Regular·Medium·SemiBold·Bold(약 3.1MB), PDF TTF Regular·Bold(약 5.4MB), LICENSE.txt.
  - PDF: ReportLab은 CFF(.otf)를 못 쓰므로 배포본 `public/static/alternative/*.ttf`(glyf 외곽선) 사용. fontTools 확인: 한글 11,172·ASCII·포르투갈어 악센트·· • – — … € ₩ ▲ ▼ ①~⑥ ※ 포함, ⓘ만 없음, fsType 0, OFL 1.1.
  - 공통화: `common/config.py`에 FONT_DIR·PDF_FONT_FILES·PDF_FONT_NAMES 추가 → Home report.py·시장 분석 pdf_report.py는 등록 경로·이름만 교체, 그린 클레임 report_worker.py는 글자별 글꼴 선택·[U+XXXX] 구조를 유지하고 latin·ko 두 자리 모두 Pretendard(Vera·나눔고딕 제거, 사용하지 않게 된 os import 삭제).
  - 웹: Brand New Hyosung @font-face → Pretendard woff2 4개, --font-sans 맨 앞 Pretendard, 굵기 토큰 400·500·600·700 원복(파일 1:1). DEV-COMMON-007의 file 버튼 font: inherit·body 굵기 지정은 유지.
  - 정리: 쓰지 않게 된 기능별 fonts/ 폴더 3곳(home·market_analysis Noto Sans KR+OFL+README, green_claim 나눔고딕+OFL+README) 삭제(Git 이력에 남음). 사용자가 넣은 static/fonts/brand/(Brand New Hyosung)·static/fonts/Pretendard-1.3.9/(배포본)은 삭제하지 않음 — 커밋 제외 권장.
  - 그린 클레임 테스트 기대값 변경: 'NanumGothic·Vera 포함' → '포함 글꼴 모두 Pretendard'. 처음 실패(/Helvetica 포함) → 최소 PDF로 ReportLab 캔버스 기본 선언(/F1 12 Tf, 그리는 글자 없음)임을 확인하고 /Helvetica만 허용.
- 변경 파일: static/fonts/pretendard/(신규: woff2 4·ttf 2·LICENSE.txt·README.md), common/config.py, static/css/common.css, static/css/tokens.css, features/home/report.py, features/market_analysis/pdf_report.py, features/green_claim/report_worker.py, features/green_claim/tests/test_report.py, tests/test_common/test_shell_a11y.py, 삭제 features/{home,market_analysis,green_claim}/fonts/*(12개), docs/design_system.md, docs/decisions.md, README.md, requirements.txt(주석), features/{home,market_analysis,green_claim}/feature_spec.md.
- 외부 호출: 0건(PDF 생성·브라우저 검증 모두 urlopen 차단·가상 데이터).
- 검증: validation.md 2026-10-26 DEV-COMMON-008.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 시장 분석 PDF 차트 축 라벨이 작은 값에서 반올림으로 겹침(1500→"2K", 0.x→"1/0") — 글꼴과 무관한 기존 표기 규칙, 이번 미수정. PDF 글꼴 크기 변화로 실제 데이터(긴 뉴스 제목·AI 표)의 줄바꿈은 가상 데이터로만 확인. Flask가 woff2를 application/octet-stream으로 응답(로드는 정상). 미추적 원본 폴더 2곳(약 71MB) 처리 결정 필요.

## DEV-HOME-021 Home 주요 카드 제목 강조·설명 문장 삭제
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/common_setup, 작업 전 미커밋 변경 없음, 최근 커밋 f5813d9)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 원문: "홈에 이거 브라질 섬유·의류 관련 최신 소식입니다.브라질·중남미 섬유 전시회 일정입니다.  빼고 바이어시간, 환율,업계 소식,다가오는 전시회 이거를 좀 강조하고 싶은데 그림자나 굵기나 색상을 다르게? 보기 좋게해"
- 판단: 두 설명 문장(card-description) 삭제. 강조는 네 카드에 똑같이 적용(카드마다 다른 그림자 금지 규칙 유지): 위쪽 3px 로고색 그라데이션 띠(배경 레이어라 모서리에 맞게 잘림), 제목 --font-size-xl·Bold·자간 -0.02em + 앞 4px 세로 포인트 막대(블루→아쿠아→민트). 공통 .card·.card-title은 수정하지 않고 Home 전용 클래스(.home-main-card·.home-card-title)로 한정, 색은 토큰만. 960px 미만은 제목 18px.
- 변경 파일: features/home/templates/home/panel.html, features/home/static/home.css, features/home/feature_spec.md.
- 외부 호출: 0건. 검증: validation.md DEV-HOME-021.
- 담당자 판단: 미기재(담당자 검토 필요)

## DEV-HOME-022 환율 전일 대비 등락 색 표시
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / home (브랜치 feature/common_setup, 작업 전 미커밋 변경 없음)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 원문: "환율 등락 색상으로 나타내줘"
- 판단: 국내 시세 표기 관례대로 상승 빨강·하락 파랑·변동 없음 회색, 옅은 배경 알약(기존 상태 토큰 danger/info/neutral, 대비 5.8·6.1·6.6:1). 기존 ▲·▼ 기호와 '상승/하락' 낱말 유지(색만으로 구분하지 않음). 전일 대비가 있는 USD/KRW·USD/BRL만 적용, BRL/KRW(USD 경유 계산값)·비교 데이터 없음은 색 없음. 서버·API·계산 변경 없음(화면 JS가 change_pct 부호로 data-direction만 붙임). PDF의 전일 대비 표기는 이번에 바꾸지 않음.
- 변경 파일: features/home/static/home.js(fxChangeDirection, data-direction), features/home/static/home.css(등락 색 규칙), features/home/feature_spec.md.
- 외부 호출: 0건(가상 FX 응답으로 화면 확인). 검증: validation.md DEV-HOME-022.
- 담당자 판단: 미기재(담당자 검토 필요)

## DEV-MA-BUYER-002 바이어 우선순위 등급(②)·바이어별 AI 브리핑(③)
- 유형: development_instruction (서비스 프롬프트 buyer_briefing_v1.md 신규 작성, 실제 모델 실험은 미실행)
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / market_analysis (+공통 소폭: common.css .table-wrap, app_shell.js focusLost) (브랜치 feature/common_setup, 작업 전 미커밋 변경 없음, 최근 커밋 8529489)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음(모의만)
- 지시: 사용자가 붙여 넣은 '바이어 분석 기능 제안(①분포 ②등급 ③AI 브리핑)' + "시장분석 탭 수정할건데 1번은 빼고 가자 만들어줘"
- 판단:
  - ② 제안 규칙 그대로 코드화. '연락 가능'은 표의 높음(대표 전화+회사 도메인)으로 해석 → A 242·B 457·C 140(대안 '연락 수단 1개 이상'이면 A 500, 제안 표 정의와 달라 채택 안 함). 1340501(Estamparia e texturização)은 가연 포함 코드라 관련도 높음. 등급 근거 한 줄은 코드가 생성.
  - ③ 제안의 4가지 자료 중 관세 18%·반덤핑 유예는 확인된 정적 자료가 없어 넣지 않음(수치를 만들지 않음, 프롬프트 금지 + 코드 검사). 시장 통계는 시장 통계 탭의 조회 묶음(bundle)을 재사용(추가 ComexStat 호출 없음). 재생·T2T 근거는 기존 근거 파일(현재 0건).
  - 호출 1회 정책: 기존 시장 분석 AI처럼 5회 검토를 하지 않고 1회 생성 + 코드 검사(통과 항목만 표시). 같은 업체·묶음은 서버 메모리 3시간 재사용. 화면은 작업 중 모든 브리핑 버튼 잠금.
  - 미정 항목은 제안의 추천을 따르거나 보류: 브랜드 묶음(자료 없음)·포르투갈어 첫 연락 문구(제품소개서와 겹침 확인 전)·③ 별도 PDF는 이번에 미구현, ②는 기존 PDF ⑥에 포함.
  - 개인정보: AI 입력에 전화번호·CNPJ 번호를 넣지 않음(테스트로 확인).
- 발견·수정한 문제: (1) 표 칸의 .visually-hidden(absolute)이 .table-wrap 스크롤 상자 밖으로 나가 390px 바이어 화면에 페이지 가로 스크롤(문서 폭 992px) → 공통 .table-wrap에 position: relative. (2) 작업 중 비활성 버튼을 누르면 main(tabindex=-1)에 초점이 가 결과 제목으로 초점 이동이 생략됨 → 공통 focusLost가 main도 '초점 없음'으로 봄. (3) 등급 열 추가로 업종 칸 nth-child 선택자가 밀림 → 5번째로 수정. (4) 바이어 카드 설명 '근거 업체 먼저' → '우선순위 등급순'.
- 변경 파일: features/market_analysis/buyers.py, buyer_briefing.py(신규), prompts/buyer_briefing_v1.md(신규), routes.py, pdf_report.py, static/market_analysis.js·css, templates/market_analysis/panel.html, feature_spec.md, tests/test_market_analysis/test_buyer_briefing.py(신규 12건), static/css/common.css, static/js/app_shell.js, docs/design_system.md.
- API contract: 기존 응답 필드 유지, buyers 응답에 등급 필드 추가, 새 엔드포인트 POST /api/market-analysis/buyer-briefing.
- 외부 호출: 0건(가짜 AI·가상 통계, 브라우저는 route 가상 응답 + 키 없는 실제 서버).
- 검증: validation.md DEV-MA-BUYER-002.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 실제 OpenAI 브리핑 품질·비용·소요 시간 미검증, 숫자 없는 사실 오류는 코드로 못 잡음(고정 안내로 사람 확인 요구), 관세·반덤핑 자료·재생·T2T 근거·브랜드 묶음 미준비, ③ PDF 미구현, PDF가 53→65쪽(등급 열로 행 높이 증가).

## DEV-MA-BUYER-003 탭 이름 '시장/바이어 분석'·바이어 검색·브리핑 PDF·가독성
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / market_analysis (브랜치 feature/common_setup, 작업 전 미커밋 변경 없음, 최근 커밋 c28f265)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 원문: "시장분석탭을 시장/바이어 분석탭이라는 이름도 바꾸고 바이어쪽에 ai 분석한 후 pdf 변환기능 넣고 가독성 좋게 만들어줘 그리고 검색기능도 넣어줘"
- 판단:
  - 이름은 FEATURE label·title·설명만 변경(기능 id·주소·API 경로·Git 브랜치명 유지). 통계 PDF 제목·바닥글도 맞춤. 담당 배정 기록(decisions.md)·브랜치 규칙의 '시장 분석'은 과거 기록이라 유지.
  - 브리핑 PDF는 화면이 보낸 JSON 대신 서버 보관본(briefing_id)으로 생성 → 내용 변조·AI 재호출 없음, 만료 시 410 안내.
  - 가독성: 브리핑을 요약 머리 + 2열 블록 + Q/A 카드 + 안내 한 상자로 재구성(정보 항목은 그대로). 기존 고정 안내 3개 notice를 한 상자 목록으로 합쳐 세로 길이 감소.
  - 검색: 839곳을 받은 상태라 브라우저에서 거름(서버 요청 없음). 국세청 자료가 악센트 없는 대문자라 악센트·대소문자·CNPJ 기호 무시.
  - 함께 고친 것: 통계 PDF 축 눈금 반올림 겹침(DEV-COMMON-008에서 보고한 남은 문제).
- 발견 문제(검증 도구): 기존 검증 스크립트가 바뀌기 전 브리핑 마크업을 찾아 2건 실패 → 선택자만 갱신. 기존 PDF 테스트의 제목 기대값을 새 제목으로 수정. 새 테스트의 문자열 비교를 assertIs → assertEqual.
- 변경 파일: features/market_analysis/routes.py, buyer_briefing.py, pdf_report.py, static/market_analysis.js·css, templates/market_analysis/panel.html, feature_spec.md, tests/test_market_analysis/test_buyer_briefing.py·test_phase2.py, README.md, docs/design_system.md.
- API contract: 새 엔드포인트 POST /api/market-analysis/buyer-briefing/pdf, 브리핑 응답에 briefing_id 추가(기존 필드 유지).
- 외부 호출: 0건(브라우저 검증은 브리핑 generate만 가짜로 바꾼 저장소 밖 실행기).
- 검증: validation.md DEV-MA-BUYER-003.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 실제 OpenAI 브리핑 미실행, 브리핑 보관은 서버 메모리 3시간(재시작 시 PDF 받으려면 다시 브리핑 필요), 검색은 현재 받은 기준 자료 범위.

## DEV-MA-BUYER-004 바이어 목록 → 업체 상세 화면(정보·AI 브리핑·PDF)
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / market_analysis (브랜치 feature/common_setup, 작업 전 미커밋 변경 없음, 최근 커밋 bc71ee5)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 원문: (서브탭 3개 제안에 대해) "시장 통계 | 바이어 목록 | AI 브리핑 이렇게 말고 바이어 목록누르면 상세로 들어가게 할수있나"
- 판단: 서브탭은 2개 유지, 목록 → 상세(같은 탭 안 화면 전환, Home 업계 소식 상세와 같은 방식). 브리핑을 상세 안으로 옮기고 목록 행의 AI 버튼은 '상세 보기'로 바꿈(유료 호출은 상세에서 사용자가 명시적으로). 업체별 브리핑을 화면 메모리에 보관해 이전·다음 이동 시 재호출 없음. 진행 중 다른 업체로 옮겨도 결과가 엉뚱한 화면에 덮이지 않게 업체별로 처리. 상세 화면에서 브리핑 머리의 업체 정보는 위 업체 카드와 중복이라 시장 맥락 한 줄로 축소(PDF는 업체 표 유지). 상세를 열 때 제목으로 스크롤하면 이동 버튼 줄이 가려져, 초점은 제목·스크롤은 상세 맨 위로 조정.
- 변경 파일: features/market_analysis/templates/market_analysis/panel.html, static/market_analysis.js·css, feature_spec.md. Python·API 변경 없음.
- 외부 호출: 0건.
- 검증: validation.md DEV-MA-BUYER-004.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 브라우저 뒤로 가기로 목록 복귀 안 됨, 실제 OpenAI 브리핑 미실행.


## DEV-MA-BUYER-005 바이어 목록 '상세 보기' 펼치기 + AI 브리핑 글래스 창
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / market_analysis + 공통 토큰 (브랜치 feature/common_setup, 최근 커밋 f0245e5)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 원문: "상세보기는 그냥 목록탭에서 가볍게 확인하게 해주고 AI 브리핑누르면 AI브리핑이랑 상세보기 Glassmorphism하게 보이게 해줘"
- 판단: DEV-MA-BUYER-004 상세 화면을 없애고 (1) 행 아래 펼치기, (2) 네이티브 `<dialog>` 모달 글래스 창(초점 가둠·Esc·초점 복귀를 브라우저 기본 동작으로)으로 대체. 'AI 브리핑'을 누른 것이 곧 브리핑 요청이므로 받은 적 없는 업체는 창을 열 때 자동 1회 호출하고 목록에 유료 안내 문장을 붙임. 글래스 값은 tokens.css에 새 토큰으로 두고 떠 있는 창 전용으로 제한, blur 미지원·투명도 줄이기 설정에서는 불투명 면으로 대체. 패널 `overflow: hidden`이면 브리핑 제목 초점 시 패널이 스크롤되어 머리가 가려져 `overflow: clip`으로 바꿈.
- 변경 파일: static/css/tokens.css, features/market_analysis/templates/market_analysis/panel.html, static/market_analysis.js·css, feature_spec.md, docs/design_system.md. Python·API 변경 없음.
- 외부 호출: 0건.
- 검증: validation.md DEV-MA-BUYER-005.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 실제 OpenAI 브리핑 미실행, prefers-reduced-transparency 화면 미확인(Chrome 에뮬레이션 미사용).

## DEV-MA-BUYER-006 AI 브리핑 창 안 하위 탭(업체 상세 | AI 브리핑)
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / market_analysis (브랜치 feature/common_setup, DEV-MA-BUYER-005 미커밋 상태에서 이어서 작업)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 원문: "시장통계 바이어목록처럼 보기 쉽게 만들어줘" → 적용 위치 질문에 "AI 브리핑 창 안" 선택
- 판단: 바깥 하위 탭과 같은 클래스·키보드 동작을 쓰도록 탭 연결 코드를 `bindTabs`로 묶어 두 곳에서 사용. 사용자가 누른 것이 'AI 브리핑'이라 열 때 브리핑 탭. 상세 탭을 보는 사이 브리핑이 끝나면 초점을 빼앗지 않고 탭 옆 '새 결과' 표시. 탭 전환 시 창 높이가 바뀌어 탭이 움직여 창 높이를 고정.
- 변경 파일: features/market_analysis/templates/market_analysis/panel.html, static/market_analysis.js·css, feature_spec.md, docs/design_system.md. Python·API 변경 없음.
- 외부 호출: 0건.
- 검증: validation.md DEV-MA-BUYER-006.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 실제 OpenAI 브리핑 미실행.

## DEV-MA-STATS-007 시장 통계 조회 조건 → 분석 결과 두 화면
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / market_analysis (브랜치 feature/common_setup, DEV-MA-BUYER-006 미커밋 상태에서 이어서 작업)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 원문: "시장 바이오분석탭에서 시장통계에서 조회조건 다음창으로 분석결과 넘어가게 해줘야지" (중간에 세션이 끊겨 "계속 진행해"로 재개)
- 판단: 2열 workspace를 두 화면 순서로 변경. 수십 초 걸리는 조회를 기다리는 동안 결과 화면에서 진행 상태를 보이도록 '분석 실행' 즉시 전환. 실패는 입력 수정이 필요할 수 있어 조건 화면으로 되돌림(이전 결과 유지). '다시 불러오기'는 결과 화면 막대로 이동. 조건 요약을 막대에 둬 결과 화면에서도 무엇을 조회했는지 보이게 함.
- 변경 파일: features/market_analysis/templates/market_analysis/panel.html, static/market_analysis.js·css, feature_spec.md. Python·API 변경 없음.
- 외부 호출: 0건.
- 검증: validation.md DEV-MA-STATS-007.
- 담당자 판단: 미기재(담당자 검토 필요)
- 남은 한계: 실제 ComexStat 조회로는 확인하지 않음(모의 서버), 브라우저 뒤로 가기와 연결하지 않음.

## DEV-MERGE-001 develop → feature/common_setup 병합 충돌 정리
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul)
- 작업자/기능: 홍은주 / 공통 (브랜치 feature/common_setup, 사람이 시작한 병합 중 상태, MERGE_HEAD 4092930)
- 모델/설정(개발 도구): Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 지시 원문: "지금 깃 충돌난거 오류없이 병합해줘" → "아니 내꺼위주로 병합해"
- 판단: 충돌 2곳(제품소개서·홍보 스튜디오 panel.html)에서 내 쪽 변경은 미구현 자리 표시 버튼에 aria-describedby(…-pending)를 붙인 한 줄뿐이었고, develop은 그 버튼을 실제 기능 버튼으로 바꿈. 내 쪽 줄을 그대로 고르면 제품소개서는 data-review-empty가 사라져 product_brochure.js에서 null 오류, 홍보 스튜디오는 죽은 PDF 버튼이 중복되어 "오류 없이" 조건을 못 지킴 → 두 파일은 develop 구조로 정리. 그 밖의 내 작업(공통 UI·Pretendard·시장/바이어 분석)은 자동 병합으로 유지됨을 확인. requirements.txt reportlab 설명이 develop의 옛 글꼴 설명으로 되돌아가 내 쪽 Pretendard 통일 설명으로 복구하고 develop의 새 사용처(홍보 스튜디오·제품소개서, Noto Sans KR) 추가. 병합으로 깨진 테스트 3건(내 낡은 자리 표시 버튼 테스트, 첫 <dialog>를 집던 제품소개서 테스트) 수정.
- 변경 파일: features/product_brochure/templates/product_brochure/panel.html, features/promotion_studio/templates/promotion_studio/panel.html, requirements.txt, tests/test_common/test_shell_a11y.py, tests/test_product_brochure/test_panel.py, 이 기록 파일들.
- Git: add·commit은 사람이 수행(이번 작업은 파일 정리만).
- 외부 호출: 0건.
- 검증: validation.md DEV-MERGE-001.
- 남은 한계: 홍보 스튜디오·제품소개서 PDF는 아직 Noto Sans KR(Pretendard 통일 미적용). 두 탭 실제 OpenAI 기능은 미실행.
