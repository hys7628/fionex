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
