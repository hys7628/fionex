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
