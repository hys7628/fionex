# 검증 기록

아래 항목을 실제 작업 후 추가하세요.

날짜 / 변경 내용 / 검증 절차 / 기대 / 실제 / 판정 / 미검증

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

## 2026-10-25 홈 바이어 시간 (DEV-HOME-001)
변경: features/home/ routes.py·service.py·panel.html·home.js·home.css
환경: Conda jasonenv Python 3.11.17, Flask 3.1.2, OPENAI_API_KEY 없이 실행. 검증 스크립트는 저장소 밖 임시 폴더에서 실행(저장소에 추가하지 않음).

### BrasilAPI 실제 응답 확인 (2026-10-25 14:22 KST, curl)
- `GET https://brasilapi.com.br/api/feriados/v1/2026` → HTTP 200, 14건, 항목 키 date/name/type/weekday, 모두 type "national". 2026-11-02 "Finados" 포함.
- 2027 → HTTP 200, 14건(2027-01-01 포함). 1800 → HTTP 404 `{"message":"Ano fora do intervalo suportado entre 1900 e 2199.", ...}`.
- Python urllib 기본 User-Agent → HTTP 403. User-Agent 지정 시 200.
- `?uf=SP`는 사용·확인하지 않음.

### 서버 (Flask test client, 19/19 통과)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| /api/home/holidays?year=2026 | ok, source=brasilapi, Finados 포함, 키 date/name | 일치, 14건 | 통과 |
| 같은 요청 재호출 | 캐시 사용 | fetched_at 동일, 1차 0.239s / 2차 0.0009s | 통과 |
| year=2027 | brasilapi, 2027-01-01 포함 | 일치 | 통과 |
| year 없음/abc/1800/2200 | 400 invalid_year | 4건 일치 | 통과 |
| BrasilAPI 닫힌 포트 + 대체 자료 없음 | source=none, 빈 목록, 캐시 안 함 | 일치 | 통과 |
| BrasilAPI 실패 + 임시 대체 파일(테스트 전용 TEST_ONLY 1건, 임시 폴더) | source=fallback | 일치 | 통과 |
| 대체 파일 손상 | source=none | 일치 | 통과 |
| 형식 오류 응답 5종(목록 아님/잘못된 날짜/다른 연도/빈 이름/국가 공휴일 없음) | 거부 | 5건 거부 | 통과 |
| 응답 없는 로컬 소켓으로 timeout | 약 5초 후 none | 5.03s 후 none | 통과 |

### 브라우저 (headless Chrome + CDP, 실제 서버 127.0.0.1:5003, 29/29 통과)
시각은 페이지의 Date를 지정 시점으로 바꿔 확인. 공휴일은 실제 서버→BrasilAPI 응답 사용(사례5만 요청 가로채기).

| 사례 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 1 서울 10/26(월) 10:00 | 상파울루 10/25(일) 22:00, 주말, 다음 업무 10/26(월) 21:00 KST | 일치, 공휴일 "11/2(월) Finados · 8일 후 — 회신 지연 가능" | 통과 |
| 2 서울 10/27(화) 22:00 | 상파울루 10:00, 업무시간, 다음 업무 숨김 | 일치 | 통과 |
| 경계 09:00 / 17:59 / 18:00 / 08:00 | 업무시간 / 업무시간 / 업무시간 외(10/28 21:00 KST) / 업무시간 외(당일 21:00 KST) | 일치 | 통과 |
| 3 상파울루 11/2 10:00 | BrasilAPI 실제 응답 기준 공휴일, 다음 11/3(화) 21:00 KST | 일치 | 통과 |
| 4 마나우스·히우브랑쿠·포르탈레자(사례1 시점) | 10/25 21:00·20:00·22:00, 다음 업무 22:00·23:00·21:00 KST | 일치(고정 12시간 차이 아님) | 통과 |
| 주말 공휴일 11/14(토) | 11/15(일) 안내 + (주말) | 일치 | 통과 |
| 연말 12/31(목) 19:00 | 1/1 공휴일·주말 건너뛰고 1/4(월) 21:00 KST(2027 자료 조회) | 일치 | 통과 |
| 분 경계 갱신 | 09:59 → 10:00 자동 변경 | 일치 | 통과 |
| 5 요청 실패 | 시계·주말 판정 유지, "공휴일 정보 확인 불가", 다음 업무에 "공휴일 미반영" | 일치. 11/2는 공휴일로 판정하지 않고 업무시간 | 통과 |
| 5 서버 source=none / fallback 응답 | 확인 불가 / "대체 자료 사용" 안내 | 일치 | 통과 |
| 도시 변경 | 새로고침 없이 즉시 갱신 | 일치 | 통과 |
| 다른 탭 이동 후 복귀 | 선택(마나우스)·화면 유지, 작성 중 표시 없음 | 일치 | 통과 |
| 브라우저 저장소 | localStorage·sessionStorage·IndexedDB 0건 | 0/0/0 | 통과 |
| 다른 4개 탭 표시 | 패널 표시 | 일치 | 통과 |
| 1440/1024/390px | 가로 스크롤 없음, 카드 화면 안 | 일치(스크린샷 육안 확인 1440·390) | 통과 |
JS 예외 0건. 콘솔 오류: favicon.ico 404(기존, 이번 변경과 무관), 사례5에서 의도적으로 실패시킨 요청 2건.

### 미검증
- 실제 사용자 조작 브라우저(헤드리스 외), Edge·Firefox·Safari·실제 모바일 기기, 화면낭독기.
- 홈 탭 숨김 시 타이머 정지, 백그라운드 탭 복귀 시 즉시 갱신(visibilitychange)은 코드만 작성, 동작 측정 안 함.
- 실제 BrasilAPI 장애 상황(로컬 닫힌 포트·무응답 소켓으로만 모의).
- 실제 대체 공휴일 자료(파일 없음).
- `python app.py`(debug 재시작기) 실행은 하지 않고 동일 앱을 `app.run(port=5003)`로 실행.

## 2026-10-25 홈 업계 소식 (DEV-HOME-002)
변경: features/home/ routes.py·service.py·panel.html·home.js·home.css
환경: Conda jasonenv Python 3.11.17, Flask 3.1.2, OPENAI_API_KEY·KOTRA 키 없이 실행. 검증 스크립트는 저장소 밖 임시 폴더.

### 외부 응답 확인 (2026-10-25 15:50~16:20 KST)
- Google News RSS `hl=pt-BR&gl=BR&ceid=BR:pt-419`: 5개 검색어 모두 HTTP 200 application/xml. channel language pt-BR.
  item 구조: title("제목 - 매체명"), link(news.google.com/rss/articles/… 경유 주소), guid, pubDate(RFC 822, GMT), description(제목 링크 + 매체명만), source(url 속성 = 매체 도메인).
- 초안 1번 검색어 53건(Vietnam.vn 14건 중 무관 기사 포함, Portugal Têxtil 8건). 초안 2번 19건, 무관 결과 다수 → 제외.
- `site:abit.org.br when:30d` 38건 모두 abit.org.br → site: 동작. 초안 OR 묶음 37건 모두 abit.org.br. `"ABIT" têxtil when:30d` 19건, 언론 매체.
- KOTRA: 공공데이터포털 15034831 페이지의 Swagger 명세에서 엔드포인트·요청 변수·응답 필드 확인. 키 없이 호출 → HTTP 401 `SERVICE_KEY_IS_NULL`(코드 20), 등록되지 않은 키 → HTTP 403 `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`(코드 30). **실제 뉴스 데이터 응답은 키가 없어 미실행.**

### 서버 (Flask test client, 38/38 통과)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| /api/home/news 실제 호출 | google·abit ok, kotra key_missing(외부 요청 없음) | google 20, abit 20, 외부 요청 3회(google 1 + abit 2), 0.83s | 통과 |
| 항목 형식 | id/title/url/media/published_at/origin/lang, summary_ko·snippet 없음, https 링크·날짜 있음 | 40건 일치 | 통과 |
| 최신순·URL/제목 중복 없음·제목 접미 제거 | 일치 | 일치 | 통과 |
| ABIT 매체 | 공식(ABIT)과 언론 보도 모두 | ABIT 14 + 언론 5개 매체 | 통과 |
| 1시간 안 재요청 | 외부 요청 0 | 0회, fetched_at 동일 | 통과 |
| refresh=google / abit / 캐시 만료 | 해당 경로만 재요청 | 1회 / 2회 / google 1회 | 통과 |
| refresh=bad·빈 값·대문자 | 400 invalid_refresh | 3건 일치 | 통과 |
| Google 실패(모의) | google error, 이전 수집분 있으면 stale·목록 유지, abit 정상 | 일치 | 통과 |
| ABIT 실패(모의 timeout) | abit error, google 정상 | 일치 | 통과 |
| 모든 경로 실패 / 예상 밖 예외 | 빈 목록·모두 error / 500 없이 fetch_failed | 일치 | 통과 |
| 중복 제거 단위 | 같은 URL → abit 유지, 공백·대소문자만 다른 제목 하나만, URL로 겹친 기사와 같은 제목도 제거 | 1차 실패(마지막 항목) → 수정 후 통과 | 통과 |
| RSS 정리 단위 | 날짜 없음·해석 불가·시간대 없음·링크 없음·javascript: 제외 | 일치 | 통과 |
| KOTRA 파싱 단위(명세 형태 TEST 입력, 실제 응답 아님) | 브라질·섬유 낱말만, 날짜 없음 제외, item 단일 객체 처리, 게이트웨이 오류 형식 거부 | 일치 | 통과 |
| KOTRA 등록되지 않은 키 실제 호출 | access_denied | HTTP 403 → access_denied | 통과 |
| 응답 없는 로컬 소켓 | 10초 후 timeout | 10.02s | 통과 |
바이어 시간 서버 회귀(DEV-HOME-001 스크립트) 19/19 통과.

### 브라우저 (headless Chrome + CDP, 실제 서버 127.0.0.1:5003, 20/20 통과)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 실제 수집 화면 | 목록·경로별 상태 3개·KOTRA 실패 안내(재시도 버튼 없음) | 39건(경로 간 중복 1건 제거), 링크 새 탭·rel noopener noreferrer, 배지·매체·KST 날짜·언어 | 통과 |
| 바이어 시간 카드 | 유지 | 시각 표시 정상 | 통과 |
| 탭 이동 후 복귀 | 뉴스 재요청 0, 목록 유지, 작성 중 표시 없음 | 일치 | 통과 |
| Google 실패 → 재시도(응답 가로채기) | 해당 경로 안내·버튼, 요청 중 disabled·aria-busy, refresh=google 1회, 새로고침 없음 | 일치, 완료 후 목록으로 초점 | 통과 |
| ABIT 실패(이전 수집분) | 이전 항목 유지 + 수집 시각 안내 | 일치 | 통과 |
| 모든 경로 실패 / 서버 요청 실패 | 빈 상태 + 실제 오류 안내, 가짜 항목 없음 / 위험 안내 + 전체 재시도 | 일치 | 통과 |
| 제목에 HTML | 텍스트로 표시, 실행 없음 | img 0개, 스크립트 미실행 | 통과 |
| 다른 4개 탭, 1440/1024/390px | 표시, 가로 스크롤 없음 | 일치(1440·390 스크린샷 육안 확인) | 통과 |
JS 예외 0건. 콘솔 오류: favicon.ico 404(기존), 의도적으로 실패시킨 요청 1건.

### 미검증
- KOTRA 실제 데이터 응답(인증키 없음): 게시일자 형식, item 배열 여부, 국가명 필터 값 "브라질" 동작, 섬유 낱말 필터 결과, 결과 순서, 인증키를 디코딩 키로 넣어야 하는지.
- 실제 Google·ABIT 장애(모의로만 확인), Google의 요청 제한·차단 조건.
- 실제 사용자 브라우저(헤드리스 외), Edge·Safari·실제 모바일 기기, 화면낭독기.
- 검색 결과 품질의 정량 평가(관련 기사 비율)는 하지 않음. 목록을 눈으로 확인한 소견만 기록.

## 2026-10-25 홈 뉴스 AI 한 줄 요약 (DEV-HOME-003, SPE-HOME-NEWS-001)
변경: features/home/news_summary.py·prompts/news_summary_v1.md·v2.md(신규), service.py·routes.py·panel.html·home.js·home.css, tests/test_home/(신규 2개)
환경: Conda jasonenv Python 3.11.17, Flask 3.1.2, openai 3.37.0·pydantic 2.14.1·httpx2 2.16.0(requirements.txt 그대로 이번에 설치). python-dotenv 미설치.

### 사전 확인
- Google News RSS description 재확인: Google 검색 1개 + ABIT 검색 2개, 111건 모두 제목+매체명 반복 → AI 입력에서 제외.
- 공통 테스트 `python -m unittest discover -s tests/test_common` 32건 OK(패키지 설치 후).

### 실제 OpenAI 호출 (SPE-HOME-NEWS-001)
- 실행: `tests/test_home/run_news_summary_experiment.py --live --real 20`, OPENAI_API_KEY는 .env 값을 실험 프로세스에만 읽음(출력·기록 안 함), OPENAI_MODEL=gpt-5.4-mini.
- 결과: v1·v2 각 1회 요청 성공, 응답 모델 gpt-5.4-mini-2026-03-17, 30건 batch 구조화 JSON 파싱 성공, id 불일치 0. 상세는 prompt_log와 experiments/news_summary_2026_10_25_163947.json.
- 결과 파일에 키 문자열("sk-") 0건 확인.

### 모의 테스트 `python -m unittest discover -s tests/test_home` (18건 OK)
공통 클라이언트 `_create_client`를 MockTransport로 바꿔 generate_structured 실제 경로를 지남.
| 사례 | 기대 | 실제 | 판정 |
|---|---|---|---|
| batch | 대상 3건을 한 요청으로, 입력은 id·title만, KOTRA 제외, store=False | 일치 | 통과 |
| 정상 요약 / 정보 부족 / 없는 숫자(15%) | 표시 / 빈 값 / 폐기, 셋 다 캐시 | 일치 | 통과 |
| 1시간 안 재요청 | OpenAI 호출 없음 | 0회 | 통과 |
| 새 기사 추가 / 같은 id 제목 변경 / 만료 | 새 기사만 요청 / 새로 요청 / 새로 요청 | 일치 | 통과 |
| 45건 | 40 + 5 두 번 | 일치 | 통과 |
| 잘린 JSON / 배열 형태 JSON | error, 요약 없음, 캐시 안 함(다음에 재시도) | 일치 | 통과 |
| 요청하지 않은 id만 응답 | 무시, 요약 없음 | 일치 | 통과 |
| HTTP 500 / 429 | error, 원문 제목만 안내 | 일치 | 통과 |
| 키 없음 | unavailable, OpenAI 요청 0, 뉴스 3건 그대로 | 일치 | 통과 |
| 숫자 검증 단위 | 2026·12,5%=12.5 허용 / 12억·2027·15·1200(원문 1.200)·전각 숫자 폐기 | 일치 | 통과 |
| id 검증 단위 | 없는 id 무시, 같은 id 다른 값 폐기, 같은 값 중복 허용, 누락 빈 값 | 일치 | 통과 |
| 길이·형식 단위 | 81자·여러 줄·한글 없음·문자열 아님 폐기 | 일치 | 통과 |
| 뉴스 연계 | 목록 요청은 AI 미호출·pending 2, 요약 후 목록에 summary_ko(KOTRA 없음), 수집 캐시는 원문 그대로, refresh 후 같은 기사 재요청 없음 | 일치 | 통과 |

### 브라우저 (headless Chrome + CDP, 실제 서버 127.0.0.1:5003, 18/18 통과)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 실제 서버(실제 Google·ABIT 수집, 서버에 OpenAI 키 없음) | 뉴스 39건 정상, 요약 0, "AI 요약을 사용할 수 없습니다" 1줄, GET 1·POST 1 | 일치 | 통과 |
| 탭 이동 후 복귀 | 뉴스·요약 재요청 0 | 0 | 통과 |
| 요약 지연 응답(가로채기) | 원문 제목 먼저 표시, 목록 aria-busy=true·진행 문구 | 일치 | 통과 |
| 요약 도착 | 요약 있는 항목만 "AI 요약" 표시, 빈 값·KOTRA 표시 없음 | 일치 | 통과 |
| 캐시된 요약 | 목록과 함께 표시, POST 없음 | 일치 | 통과 |
| 요약 요청 실패 / error 상태 | 목록 유지 + 안내 | 일치 | 통과 |
| 요약 문자열 HTML | 텍스트로 표시 | img 0, 미실행 | 통과 |
| 요약 중 경로 재시도 | 끝난 뒤 요약 재요청(POST 2), 새 기사 요약 | 일치 | 통과 |
| 바이어 시간·다른 4개 탭·1440/1024/390px | 유지·표시·가로 스크롤 없음 | 일치 | 통과 |
JS 예외 0. 콘솔 오류: favicon 404(기존), 의도적 실패 요청 1건.

### 회귀
- 바이어 시간 서버 검증(DEV-HOME-001 스크립트) 19/19, 뉴스 서버 검증(DEV-HOME-002 스크립트, 실제 RSS) 38/38 통과.

### 미검증
- 앱 경로(POST /api/home/news/summaries → 실제 OpenAI) 실제 호출: 미실행. 사전 안내한 실험 2회 범위를 넘지 않음. 서버는 OpenAI 키 없이 실행.
- 같은 입력 반복 실행 편차, 다른 모델, 비용 실측.
- 요약 사실 정확성의 체계적 평가(30건 원출력을 담당 AI가 눈으로 판독한 소견만 있음).

## 2026-10-25 KOTRA_API_KEY 확정 반영 (DEV-HOME-004)
변경: features/home/service.py·static/home.js, .env.example, README.md
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| .env.example 값 확인(값 미출력, 길이만) | OPENAI_API_KEY·KOTRA_API_KEY 빈 값 | 길이 0 / 0 | 통과 |
| 뉴스 서버 검증(DEV-HOME-002 스크립트, 실제 RSS, 서버 프로세스에 키 없음) | kotra `not_configured`·key_missing·재시도 불가·외부 요청 없음, google·abit 정상 | 38/38 통과 | 통과 |
| 등록되지 않은 키로 KOTRA 실제 호출 | `error`·access_denied(403) | 일치 | 통과 |
| 홈 모의 테스트 tests/test_home | 18건 OK | OK | 통과 |
| 브라우저(headless Chrome, 키 없는 테스트 서버 127.0.0.1:5013) | "KOTRA · 설정 필요" 배지·"KOTRA 설정 필요" 안내(재시도 버튼 없음), Google·ABIT 목록 정상 | 20/20 통과, JS 예외 0, 스크린샷 확인 | 통과 |
비고: 5003 포트는 사용자가 실행한 `python app.py`가 사용 중이라 테스트 서버를 5013에 띄움.
미검증: .env의 실제 KOTRA 키로 실제 데이터 조회(이번 범위 아님), python-dotenv 설치 환경에서 .env 자동 로딩.

## 2026-10-25 로컬 .env 로딩 (DEV-COMMON-001)
변경: requirements.txt(python-dotenv==1.1.1), README.md, common/config.py(주석). jasonenv에 python-dotenv 1.1.1 설치.
방법: app.py를 `__main__`으로 실행(= `python app.py`, app.run → flask.cli.load_dotenv)하고 werkzeug run_simple만 막아 환경변수 상태 확인. 값은 출력하지 않음.
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| A. .env 없는 폴더에서 실행 | 오류 없이 app.run 도달, 세 변수 missing | 일치 | 통과 |
| A. .env 없는 폴더에서 실제 서버(127.0.0.1:5014) | GET / 200 | 200 | 통과 |
| B. 프로젝트 루트(.env 있음)에서 실행 | OPENAI_API_KEY·OPENAI_MODEL·KOTRA_API_KEY configured | 3개 configured | 통과 |
| B. 프로젝트 루트에서 실제 서버 단독 실행(5014) | GET / 200 | 200 | 통과 |
| C. OS 환경변수에 임의 문자열을 먼저 넣고 실행 | .env가 덮어쓰지 않음 | 3개 모두 OS 값 유지 True | 통과 |
| FLASK_SKIP_DOTENV=1 | 로드 안 함 | 3개 missing | 통과 |
| 하위 폴더(features)에서 실행 | 상위 방향 탐색으로 로드 | 3개 configured | 통과 |
| 회귀: tests/test_home·tests/test_common | OK | OK / OK | 통과 |
| 회귀: 공휴일 서버(DEV-HOME-001)·뉴스 서버(DEV-HOME-002, 실제 RSS) | 통과 | 19/19 · 38/38 | 통과 |
| 회귀: test client GET / | 200, 탭 패널 5개, 홈 카드 3개, AI 요약 모듈 import | 일치 | 통과 |
비고: 처음 실제 서버 확인은 bash kill이 Windows python을 종료하지 못해 이전 서버가 남은 채 진행됨 → B만 PowerShell로 단독 재실행해 확인. 테스트 서버는 모두 종료.
test client·unittest는 app.run을 거치지 않아 .env를 읽지 않음(실제 키로 외부 호출 없음).
미검증: `flask --app app run` 경로(같은 load_dotenv 함수, 직접 실행 안 함), debug 재시작기 자식 프로세스에서의 값(부모 환경 상속, 직접 확인 안 함), 실제 키로 OpenAI·KOTRA 호출, 다른 팀원 PC.

## 2026-10-25 홈 환율 카드 (DEV-HOME-005)
변경: features/home/fx.py(신규)·service.py·routes.py·panel.html·home.js·home.css, tests/test_home/test_fx.py(신규)

### 공식 명세·실제 응답 확인 (2026-10-25 16:55~17:00 KST)
- 수출입은행 현재환율 API 개발명세(웹페이지): 요청 `GET https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey=&searchdate=&data=AP01`, searchdate 20150101·2015-01-01 형식, RESULT 1 성공/2 DATA코드 오류/3 인증코드 오류/4 일일제한횟수 마감, CUR_UNIT 통화코드, DEAL_BAS_R 매매 기준율, "비영업일 또는 영업당일 11시 이전 요청 시 null", 일일 1000회, 기존 www 도메인 2026-04-30 병행 종료.
- 수출입은행 실제 호출: 키 없음·등록되지 않은 키 → HTTP 200 `[{"result":3, 나머지 null}]`. 실제 키 없음 → **USD/KRW 데이터 응답 미확인**.
- BCB PTAX: OData $metadata와 문서 페이지 내장 명세 확인. `CotacaoDolarPeriodo(dataInicial, dataFinalCotacao)`, 날짜 'MM-DD-AAAA', cotacaoCompra "Cotação de compra", cotacaoVenda "Cotação de venda"(BRL/USD), dataHoraCotacao. 키 없이 HTTP 200. 10/15~10/25 조회 시 영업일 7건(주말 없음), 10/24(토) 일 조회는 빈 value.

### 실제 외부 호출 (앱 코드 경로)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| /api/home/fx, 수출입은행 키 없음 | usd_krw not_configured(외부 요청 없음), usd_brl ok, brl_krw null | 일치. PTAX 최근 고시 2026-10-23 5.0377, 직전 10-22 5.0383, -0.01%, 1.28s | 통과 |
| 원본 PTAX와 대조 | 같은 값 | 원본 10-22 5.0383 / 10-23 5.0377, 계산 -0.0119% | 통과 |
| 등록되지 않은 키(프로세스 안에서만) | usd_krw error access_denied, 재시도 불가, 응답에 키 없음 | 일치 | 통과 |

### 모의 테스트 tests/test_home/test_fx.py (15건, tests/test_home 전체 33건 OK)
| 사례 | 기대 | 판정 |
|---|---|---|
| parse_exim | 쉼표 값 파싱, 빈 목록·null·USD 없음 → 고시 없음, RESULT 2/3/4/기타 → 코드 | 통과 |
| parse_ptax | 날짜순, 같은 날 마지막 시각, 값 없음·날짜 오류 제외, 형식 오류 거부 | 통과 |
| 계산 | 1405.2/1400.9 → 0.31%, 1400÷5 = 280, 한쪽 없음 → null | 통과 |
| 일요일 기준 | 수출입은행 일·토 비어 금(10/23) 사용, 직전 목(10/22), PTAX 기간 1회(10-11~10-25) | 통과 |
| 7일 안 고시 없음 | 두 소스 no_recent_rate, 숫자 없음 | 통과 |
| 직전값 없음 | change_pct·previous null | 통과 |
| 한쪽 실패 / 둘 다 실패 / 예상 밖 예외 | 다른 소스 유지, brl_krw null, 실패 5분 캐시 | 통과 |
| 캐시 | 재요청 외부 0회, 만료 후 수출입은행은 오늘만 재조회, refresh=usd_brl은 PTAX만 | 통과 |
| 키 없음 / 인증 오류 로그 | 외부 요청 없음 / 로그·응답에 키 없음 | 통과 |
| 라우트 | 잘못된 refresh 3종 400 | 통과 |

### 브라우저 (headless Chrome, 테스트 서버 127.0.0.1:5013, 20/20 통과, 수정 후 재실행 2회 20/20)
실제 서버(PTAX 실제, 수출입은행 키 없음) + 응답 가로채기 가상 값.
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 실제 서버 | USD/KRW 확인 불가·"설정 필요" 안내(재시도 없음), USD/BRL 실제 PTAX·고시일·전일 대비, BRL/KRW 계산 불가, 바이어 시간·뉴스 동작 | 일치 | 통과 |
| 정상 | "1 USD = 1,405.20 KRW", "1 USD = 5.0377 BRL", "1 BRL = 278.94 KRW", 고시일·출처, ▲ 상승/▼ 하락, "USD 경유 계산값", "오늘" 표현 없음 | 일치 | 통과 |
| 비교 데이터 없음 / 변동 없음 | 문구 표시 | 일치 | 통과 |
| USD/KRW 실패 → 재시도 | 확인 불가·안내·버튼, 요청 중 disabled·aria-busy, refresh=usd_krw 1회, 새로고침 없음, 회복 후 BRL/KRW 표시·초점 목록 | 일치 | 통과 |
| USD/BRL 실패 / 둘 다 실패 / 서버 요청 실패 | 다른 값 유지 / 숫자 없음·안내 2 / 위험 안내 | 일치 | 통과 |
| 탭 이동 후 복귀, 다른 4개 탭, 1440/1024/390px | 재요청 0, 표시, 가로 스크롤 없음(1440·390 스크린샷 확인) | 일치 | 통과 |
JS 예외 0. 콘솔 오류: favicon 404(기존), 의도적 실패 1건.
주의: 1회차 테스트 서버는 python-dotenv로 .env를 읽어 실제 KOTRA·OpenAI 요약 호출이 발생(prompt_log DEV-HOME-005). 결과: KOTRA ok 2건(상파울루무역관, 제목·날짜·링크 파싱, KOTRA 항목에 요약 없음), 요약 33/41건. 2·3회차는 FLASK_SKIP_DOTENV=1.

### 회귀
tests/test_common OK, 공휴일 서버 19/19, 뉴스 서버(실제 RSS) 38/38.

### 미검증
- 수출입은행 실제 키로 USD/KRW 정상 응답·쉼표 형식·11시 이전·비영업일 실제 응답(키 없음).
- 실제 주말·공휴일 역조회는 PTAX만 실제(일요일 → 금요일). 수출입은행은 모의.
- 실제 사용자 브라우저·기기, 화면낭독기.

## 2026-10-25 홈 브라질 섬유 전시회 (DEV-HOME-006)
변경: features/home/data/br_textile_fairs.json·fairs.py(신규), service.py·routes.py·panel.html·home.js·home.css, tests/test_home/test_fairs.py(신규)

### 서버 (tests/test_home/test_fairs.py 9건 OK, tests/test_home 전체 42건 OK)
| 사례 | 기대 | 판정 |
|---|---|---|
| 필터·정렬 | 종료(10/24 끝) 제외, 오늘 끝나는 행사 포함, 시작일 순 | 통과 |
| D-day(기준 2026-10-25) | 2027-04-27 → D-184, 오늘 시작 → D-DAY, 시작 후 종료 전 → 진행 중 | 통과 |
| limit | 3건 제한, total_upcoming 8 | 통과 |
| 예정 없음 | 빈 목록 | 통과 |
| 항목 오류 8종(URL 없음·javascript: URL·출처 없음·날짜 오류·종료<시작·verified 문자열·이름 없음·객체 아님) | 제외, invalid_count 8, 값 보충 없음 | 통과 |
| 선택 값 없음 | city·venue·focus·note null 유지 | 통과 |
| 파일 없음·JSON 오류·최상위 형식 오류 3종 | FairsDataError | 통과 |
| 저장소 자료 | 제외 0건, 확인일 2026-10-25, https 링크, Inspiramais verified false+note | 통과 |
| 라우트 | 기본 5건, limit=2, limit=500 → 20, limit 0/-1/abc/빈 값 → 400 invalid_limit, 파일 오류 → 503 fairs_unavailable | 통과 |
| 실제 자료 API(test client) | Inspiramais D-93 → Tecnotêxtil D-184 → Febratex Summit D-303 | 통과 |

### 브라우저 (headless Chrome, 테스트 서버 127.0.0.1:5013 FLASK_SKIP_DOTENV=1·키 없음, 18/18 통과)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 실제 자료 | 3건 날짜순, D-93/D-184/D-303, "확인 필요"(Inspiramais)·"공식 사이트 확인", note, 출처 링크 target=_blank·rel noopener noreferrer, 자료 확인일 안내 | 일치 | 통과 |
| 기간·장소·분야 | "2027-04-27 ~ 2027-04-30", "Americana/SP · Fidam (…)" | 일치 | 통과 |
| 다른 Home 카드 | 바이어 시간, 환율(USD/KRW 확인 불가·USD/BRL 실제 PTAX), 뉴스 40건, KOTRA 설정 필요, AI 요약 사용 불가 안내 | 일치(1회차는 확인 시점이 일러 실패 → 대기 후 통과) | 통과 |
| 탭 이동 후 복귀 | /api/home/fairs 재요청 0 | 0 | 통과 |
| 진행 중·D-DAY·하루 행사·빈 값·제목 HTML(가로채기) | 배지 문구, "기간 2027-01-01", "미확인", HTML 텍스트 처리 | 일치 | 통과 |
| 빈 상태 / 일부 제외 | "확인된 예정 전시회가 없습니다" / "일부 일정 제외" | 일치 | 통과 |
| 자료 오류(503) → 재시도 | 카드만 "일정 확인 불가"+버튼, 바이어 시간 유지, 요청 중 disabled·aria-busy, 회복·새로고침 없음·초점 목록 | 일치 | 통과 |
| 다른 4개 탭, 1440/1024/390px | 표시, 가로 스크롤 없음(1440·390 스크린샷 확인, 390 줄바꿈 수정 후 재확인) | 일치 | 통과 |
JS 예외 0. 콘솔 오류: favicon 404(기존), 의도적 503 1건.

### 회귀·외부 호출
- tests/test_common OK, 공휴일 서버 19/19, 뉴스 서버(실제 Google RSS) 38/38. 모두 .env 미로드·OpenAI 키 없음.
- KOTRA·OpenAI 실제 키 호출 없음. 뉴스 회귀 스크립트의 잘못된 테스트 키 KOTRA 게이트웨이 호출 1회(403).

### 미검증
- 실제 사용자 브라우저·기기, 화면낭독기. 일정 자체의 정확성은 출처 문구 기준이며 주최사 문의 등 추가 확인은 하지 않음.

## 2026-10-25 KOREAEXIM_API_KEY 확정·환율 명세 (DEV-HOME-007)
변경: features/home/fx.py(주석), .env.example, README.md, features/home/feature_spec.md
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| .env 키 존재(이름만) | — | KOREAEXIM_API_KEY 없음 → 실제 USD/KRW 호출 미실행 | 미실행 |
| .env.example | `KOREAEXIM_API_KEY=` 빈 값, CRLF 유지 | 추가됨, CRLF 12/LF 0 | 통과 |
| README | 변수명·용도·.env 저장·키 없을 때 동작 안내 | 추가됨 | 통과 |
| 코드 변수명 | fx.EXIM_KEY_ENV == KOREAEXIM_API_KEY | 일치 | 통과 |
| 명세·코드 자동 대조(모의 응답, 외부 요청 없음) | endpoint·변수명·URL·캐시 3600/300·역조회 7·상태·오류 코드·refresh·응답 필드 | 10개 항목 모두 일치 | 통과 |
| 키 없음 응답 | usd_krw not_configured, brl_krw null | 일치 | 통과 |
| tests/test_home(42) · tests/test_common | OK | OK / OK | 통과 |
| 앱 import·GET / (FLASK_SKIP_DOTENV=1) | 200 | 200 | 통과 |
| diff 키 검사 | 실제 키 없음 | 0건(README의 빈 값 안내 문구만 패턴에 걸림) | 통과 |
외부 호출: 수출입은행·공공데이터포털 공식 페이지 조회만. 환율 API·KOTRA·OpenAI 호출 없음.
미검증: 실제 키 기반 USD/KRW 응답 전체(키 발급 후 확인 필요).

## 2026-10-25 홈 일일 브리핑 PDF (DEV-HOME-008)
변경: requirements.txt(reportlab==5.1.0), README.md, features/home/buyer_time.py·report.py·fonts/(신규), service.py·routes.py·panel.html·home.js, tests/test_home/test_report.py(신규)
환경: jasonenv에 reportlab 5.1.0·pillow 13.0.0·charset-normalizer 3.5.2 설치. 테스트 서버 FLASK_SKIP_DOTENV=1·키 없음(127.0.0.1:5013).

### 서버 (tests/test_home/test_report.py 9건 OK, tests/test_home 전체 51건 OK, 가상 fixture)
| 사례 | 기대 | 판정 |
|---|---|---|
| 바이어 시간 규칙(화면과 같은 사례) | 서울 10/26 10:00 → 상파울루 10/25(일) 22:00 주말·다음 10/26(월) 21:00 KST, 마나우스 21:00·22:00 KST, 09:00/17:59 업무시간, 18:00 → 10/28 21:00, 08:00 → 당일 21:00, 11/2 공휴일 → 11/3 21:00, 12/31 19:00 → 1/4 21:00 | 통과 |
| 7일 이내 공휴일 | 10/25 기준 11/2 제외(8일 후), 10/27 기준 Finados 6일 후 | 통과 |
| 공휴일 확인 불가 | 공휴일 없이 판단(11/2 업무시간), 출처 none 기록 | 통과 |
| 정상 수집 | 실패 0, 뉴스 10건 중 8건, 전시회 3건, get_news·get_fx 각 1회(refresh 없음) | 통과 |
| 영역 실패(환율·뉴스 예외, 전시회 자료 오류) | 실패 목록 3개, PDF 생성 유지 | 통과 |
| 소스 단위 실패(USD/KRW·KOTRA 키 없음) | 실패 목록에 사유 포함, PDF 생성 | 통과 |
| 파일명·디스크 | %PDF~%%EOF, 1KB 초과, 파일명 fionex_daily_briefing_20261026_1000.pdf(서울), 프로젝트에 PDF 새로 생기지 않음 | 통과 |
| 라우트 | 200 application/pdf·attachment·no-store, 기본 도시 200, city=sao_paulo/빈 값/Asia/Seoul → 400 invalid_city, 엔진 예외 → 500 report_failed | 통과 |

### PDF 내용 확인 (PyMuPDF로 열어 텍스트·링크·글꼴 추출, 페이지 이미지 육안 확인. PyMuPDF는 세션 임시 폴더에만 설치)
| PDF | 쪽 | 크기 | 확인 |
|---|---|---|---|
| 가상 데이터·상파울루 | 2 | 48,870B | 섹션 6개 순서, 글꼴 NotoSansKR Regular·Bold(본문 Helvetica 0건), 링크 21개, São Paulo·Indústria têxtil·Produção·Confecções·Tecnotêxtil, ▲ 상승 0.31%·▼ 하락 0.01%, 1,405.20 KRW·5.0377 BRL·278.94 KRW, "USD 경유 계산값", "[AI 요약]"(KOTRA 항목 요약 없음), "확인 필요", D-93, 제목 "<특집> & 전망" 그대로, 긴 제목 줄바꿈·표 겹침 없음 |
| 가상 데이터·마나우스 | 2 | 48,928B | 브라질 시각 10/25(일) 21:00, 다음 업무 10/26(월) 22:00 KST |
| 부분 실패 | 1 | 35,534B | 환율 "확인 불가", 뉴스 "뉴스를 불러오지 못했습니다", 전시회 "일정 확인 불가", 실패 목록 3개 |
| 브라우저가 실제 서버에서 받은 PDF(실제 공개 데이터) | 2 | 64,096B | 섹션 순서, 링크 38개, 깨진 글자(U+FFFD) 0, 악센트 á â ã ç ê í ú, USD/BRL 5.0377, USD/KRW·KOTRA 키 없음이 실패 목록에 사유와 함께 표시 |

### 브라우저 (headless Chrome, 16/16 통과)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 버튼 3회 연속 클릭(실제 마우스 이벤트) | 요청 1회, 생성 중 disabled·aria-busy·진행 문구 | 일치 | 통과 |
| 완료 | 파일 저장(%PDF, 서울 시각 파일명), "다운로드를 요청했습니다…", 새로고침 없음, 머리글 "다운로드 요청됨" | 일치 | 통과 |
| 도시 마나우스 | city=America%2FManaus 요청, 안내 "마나우스", 선택·다른 카드 유지, application/pdf Blob 다운로드 요청 | 일치 | 통과 |
| 500 JSON / 재시도 / 네트워크 실패 / PDF 아닌 응답 | 위험 안내·버튼 재활성 / 안내 제거·Blob 요청 / "서버에 연결하지 못했습니다" / 다운로드 없이 안내 | 일치(네트워크 문구는 영어 원문 노출 발견 후 수정) | 통과 |
| 다른 4개 탭·복귀 후 상태, 1440/1024/390px | 표시·유지, 가로 스크롤 없음(1440·390 스크린샷) | 일치 | 통과 |
주의: 같은 페이지에서 두 번째 이후 PDF는 Blob 다운로드 요청까지는 확인했지만 헤드리스 Chrome이 디스크에 저장하지 않음(같은 폴더에 Chrome 구성요소 CRX 파일이 함께 받아짐). 원인 미확정.

### 회귀
전시회 브라우저(DEV-HOME-006 스크립트) 18/18, 환율 브라우저(DEV-HOME-005 스크립트) 20/20, tests/test_common OK, 공휴일 서버 19/19. 뉴스 서버 스크립트는 뉴스 코드 미변경·KOTRA 게이트웨이 호출을 피하려고 이번에는 실행하지 않음.

### 외부 호출
KOTRA·OpenAI·수출입은행 호출 없음. 공개 데이터(Google News RSS·BCB PTAX·BrasilAPI)는 테스트 서버 화면 로딩과 PDF 생성 중 조회. 조사 단계에서 PyPI 패키지·Google Fonts 공식 저장소 폰트 내려받기.

### 미검증
- 실제 사용자 브라우저(Edge·Safari·모바일)의 다운로드 동작과 같은 페이지 반복 다운로드.
- 실제 AI 요약이 들어간 실제 데이터 PDF(키 없는 서버라 요약 없음. 가상 데이터로 표시 형식만 확인).
- 인쇄(흑백) 출력물 확인, 화면낭독기, Adobe Reader 등 다른 PDF 뷰어(PyMuPDF·Chrome 다운로드만 확인).
- (정정, DEV-HOME-009) "같은 페이지 두 번째 PDF 미저장"은 같은 분 같은 파일명을 검증 환경이 덮어쓴 것으로 확인됨(아래 항목).

## 2026-10-25 Home 통합 검증·명세 정리 (DEV-HOME-009)
변경: features/home/feature_spec.md, tests/test_home/test_holidays_news.py(신규). 기능 코드 변경 없음.

### 서버 테스트 (모두 FLASK_SKIP_DOTENV=1, OPENAI·KOTRA·KOREAEXIM 환경변수 제거, 외부 요청 없음)
| 명령 | 결과 |
|---|---|
| `python -m unittest tests.test_home.test_holidays_news` | 9 OK (신규: 뉴스 수집·정규화·중복 제거·정렬, 캐시·refresh, 실패 분리·stale, KOTRA 키 없음, 전체 실패, 공휴일 캐시·대체 자료·none, 라우트 400) |
| `python -m unittest tests.test_home.test_news_summary` | 18 OK |
| `python -m unittest tests.test_home.test_fx` | 15 OK |
| `python -m unittest tests.test_home.test_fairs` | 9 OK |
| `python -m unittest tests.test_home.test_report` | 9 OK |
| `python -m unittest discover -s tests/test_home` | 60 OK |
| `python -m unittest discover -s tests/test_common` | 32 OK |
실패 0. 실제 네트워크를 쓰는 기존 임시 스크립트(공휴일 19·뉴스 38)는 이번에 실행하지 않음(같은 검사를 모의 테스트로 대체).

### 브라우저 통합 (headless Chrome, 외부 요청 없는 fixture 서버 정상 5013·실패 5014, 16/16 통과)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 정상 모드 전체 | 바이어 시간·공휴일 출처, 환율 3값(1,405.20 KRW·5.0377 BRL·278.94 KRW), 뉴스 3경로 정상(KOTRA 포함), 전시회 3건·확인 상태 | 일치 | 통과 |
| AI 요약 | Google·ABIT 해당 항목만 "AI 요약", 빈 값·KOTRA 없음 | 일치 | 통과 |
| 도시 마나우스 | 브라질 시각 = 상파울루 - 60분, PDF 안내 도시 변경, 새로고침 없음, 작성 중 표시 없음 | 일치 | 통과 |
| PDF 2회(실제 마우스 클릭, 간격 2초·6초 각 1회 실행) | 두 응답 200 application/pdf, 새 Blob 2개, 버튼 재활성 | 일치. Chrome 두 번 begin→completed(46,627~46,628B). `allow`는 같은 이름 파일 1개, `allowAndName`은 PDF 2개(%PDF) | 통과 |
| 탭 이동 후 복귀 | 도시·뉴스 4건·환율·전시회·PDF 상태 유지 | 일치 | 통과 |
| 다른 4개 탭 | 표시 | 일치 | 통과 |
| 1440/1024/390px | 카드 5개 겹침 없음, 가로 스크롤 없음(전체 화면 캡처 육안 확인) | 일치(1차 실행은 기대 카드 수를 6으로 잘못 적어 실패 → 기대값 수정) | 통과 |
| 실패 모드 | Google 실패 안내·재시도, KOTRA 설정 필요, AI 요약 실패 안내, USD/KRW 확인 불가·BRL/KRW 계산 불가, USD/BRL·전시회·ABIT 유지, PDF 생성·다운로드 요청 | 일치 | 통과 |
JS 예외 0. 콘솔 오류 favicon 404(기존)만. fixture 서버가 막은 외부 요청 0건.

### 문서 정합성
- feature_spec ↔ 코드 자동 대조: Home API 6개(GET fairs·fx·holidays·news·report/daily.pdf, POST news/summaries), 오류 코드 전부, 상수 12개 일치.
- 환경변수: 코드(OPENAI_API_KEY·OPENAI_MODEL·KOTRA_API_KEY·KOREAEXIM_API_KEY) = .env.example = README. .env.example 2번째 줄 설명 문구만 현재 동작과 다름.

### 미검증
실제 사용자 브라우저(Chrome·Edge·Safari·모바일)에서의 반복 다운로드 파일명 처리, 화면낭독기, 실제 키 기반 USD/KRW, 앱 경로 실제 AI 요약.

## 2026-10-25 PR 전 공통 문서·설정 정합성 (DEV-HOME-010)
변경: .env.example(설명 3줄), README.md(3곳). Home 기능 코드·requirements.txt 변경 없음.
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| .env.example 설명 | README ".env 로딩"과 같은 동작(python app.py 시 자동 로딩, OS 우선, .env 없어도 실행) | 일치, 값 줄 변경 없음, CRLF 14/LF 0 | 통과 |
| .env.example 값 | 키 값 없음 | OPENAI_API_KEY·KOTRA_API_KEY·KOREAEXIM_API_KEY 빈 값, OPENAI_MODEL·OPENAI_IMAGE_MODEL은 공개 초기 후보 | 통과 |
| 환경변수 이름 | 코드 = .env.example = README | OPENAI_API_KEY·OPENAI_MODEL·KOTRA_API_KEY·KOREAEXIM_API_KEY 일치 | 통과 |
| develop 병합 후 패키지 | requirements 설치 상태 | pypdf 미설치 발견 → requirements.txt 그대로 설치(6.21.2) | 조치 |
| `python -m unittest discover -s tests/test_home` (FLASK_SKIP_DOTENV=1, 키 환경변수 제거) | OK | 60 OK | 통과 |
| `python -m unittest discover -s tests/test_common` | OK | 56 OK(병합된 test_pdf 포함) | 통과 |
| 앱 import·GET /, common.ai_client import | 200 | 200 | 통과 |
테스트를 다시 돌린 이유: 문서 변경 때문이 아니라 develop 병합으로 공통 코드(ai_client·pdf_utils)가 바뀌었기 때문. 브라우저 검증은 이번에 다시 하지 않음(Home 코드·화면 변경 없음). 외부 API·AI 호출 없음.

## 2026-10-25 PR 리뷰 반영 (DEV-HOME-011)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 저장한 실제 RSS에 필터 적용(Q0 현재 검색어·ABIT 2종, 2026-10-25 18:56) | .pt·무관 제목 제외 | Google 수집 53 → 필터 후 13(브라질 매체·섬유 관련, vietnam.vn 6·portugaltextil.com 2 포함 제외), ABIT 53 → 45(표시 20) | 통과 |
| 검색어 후보(브라질로 좁힘) 비교 | 노이즈 감소 근거 | 31건 중 남은 19건에 'moda'·공예 등 일반 노이즈 → 검색어 변경 안 함 | 근거 없음(미변경) |
| test_holidays_news 관련성·KOTRA A~E | 통과 | 필터 통과/제외 문장, .pt·portugaltextil.com·abit.org.br 면제, 악센트 무시, RSS source 도메인 기준, 경로별 건수, A 응답 0(collected=0 filtered=0 로그)·B 필터 0·C 최소 포함·D 없으면 채우지 않음·E 중복 없음 | 통과 |
| test_news_summary v3 | 규칙·예시 4개 | 채택 파일 v3, 용어 보존 규칙, ex1~ex4, 예시 출력이 validate_summaries 통과(빈 값 1건만 empty) | 통과 |
| test_report PDF | 링크·URL·쪽 번호 등 | pypdf 추출: 뉴스 링크 8개, 본문 https:// 없음, 쪽마다 'n / N', '2026-10-23 (두 환율 동일)', 'KRW 10-23 / BRL 10-24', 경로별 '수집/필터 후/브리핑 선정', KOTRA 최소 1건 | 통과 |
| test_fairs 자료·명세 대조 | 일치 | Tecnotêxtil 2027-04-27~2027-04-30 verified, feature_spec 표 3행이 JSON start·end와 같음 | 통과 |
| PDF 4종 PyMuPDF로 열어 확인(fixture 8건 혼합·고시일 다름·저장한 실제 RSS+KOTRA 0·부분 실패) | 2쪽 이내 | 모두 2쪽, '1 / 2'·'2 / 2', 본문 URL 0, .pt 도메인 0, Noto Sans KR 임베드, Tecnotêxtil 2027-04-27 ~ 2027-04-30, 고시일 칸 한 줄, 부분 실패 목록(USD/KRW 키·Google 시간 초과) | 통과 |
| PDF 이미지 육안(80dpi) | 겹침·잘림 없음 | 1차: '4. 다가오는 전시회' 제목이 1쪽 끝에 홀로 남음 → keepWithNext 후 2쪽 첫머리로 이동 확인 | 수정 후 통과 |
| 브라우저(fixture 서버, 외부 요청 차단) 390/1024/1440 | 경로별 건수, 가로 넘침 없음 | 정상: 'KOTRA 수집 2 · 필터 후 1 · 표시 1'. KOTRA 0+Google 실패: '수집 0 · 필터 후 0 · 표시 0', Google '수집 기록 없음'+재시도 안내, ABIT 2건 유지. 7/7, JS 예외 0, 막힌 외부 요청 0 | 통과 |
| `python -m unittest discover -s tests/test_home` (FLASK_SKIP_DOTENV=1) | OK | 76 OK | 통과 |
| `python -m unittest discover -s tests/test_common` | OK | 56 OK | 통과 |
생성한 PDF·스크린샷은 저장소 밖 scratchpad에만 있음. 외부 호출: Google News RSS 4회·Tecnotêxtil 공식 사이트 1회(공개). OpenAI·KOTRA·수출입은행 0회.

### 미검증
v3 프롬프트 실제 OpenAI 호출(미실행), 실제 KOTRA 응답에서의 최소 노출, 실제 키 기반 USD/KRW가 들어간 PDF, 실제 사용자 브라우저.

## 2026-10-25 Home 화면 배치 개선 (DEV-HOME-012)
실제 Flask 서버(저장소 밖 fixture 서버, FLASK_SKIP_DOTENV=1, urlopen 차단) 2대: 5013 many(2026-10-25 저장한 실제 RSS 파일 + 가상 KOTRA·환율·가상 AI 요약, 뉴스 34건), 5014 kotra0(KOTRA 0건 + Google 실패). headless Chrome CDP로 측정·클릭, 전체 화면 캡처를 눈으로 확인.
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 1440px 배치 | 도구줄 얇음, PDF 버튼 첫 화면, 1행 1/3·2/3, 2행 2/3·1/3 | 도구줄 78px, PDF 버튼 y=202~244(창 900), 바이어 363·환율 726, 뉴스 726·전시회 363, 환율 타일 3개 한 줄 | 통과 |
| 1024px 배치 | 찌그러짐 없음 | 1100px 미만이라 세로 배치(카드 폭 697 동일), 환율 타일 3개 한 줄, PDF 버튼 첫 화면 | 통과 |
| 390px 배치 | 순서·가로 스크롤 | 도구줄→바이어→환율→뉴스→전시회→유의사항, 가로 넘침 없음, 환율 타일 세로 1열, 필터 탭 줄바꿈(카드 안), D-day·행사명 겹침 없음 | 통과 |
| 뉴스 목록 | 내부 스크롤 없음, 첫 제목 전체 | overflow visible·scrollHeight=clientHeight, 첫 제목 목록 영역 안, 3개 폭 모두 | 통과 |
| 기본 8건·더 보기 | 클라이언트 펼침 | 34건 중 8건, '더 보기 (26건)'. ABIT 필터 8→20→8, aria-expanded 전환, 새 요청 없음 | 통과 |
| 매체 필터 | 해당 경로만, aria-pressed | 전체 34·KOTRA 1·Google News 13·ABIT 20, Google 선택 시 google만·pressed true, KOTRA 1건 | 통과 |
| 실패 경로 | ⚠·재시도 유지 | kotra0: 'Google News 0 ⚠ (수집 실패)', 'KOTRA 0', 'Google News 다시 시도' 클릭 → 다시 실패 시 버튼 유지·초점 | 통과 |
| 수집 현황 | 경로별 건수 유지 | 접기 영역에 '수집 N · 필터 후 M · 표시 K' 3경로 | 통과 |
| 바이어 상태 | 큰 문구·색 | '지금은 주말' 22px, home-status-warning(주황). 업무시간·공휴일 문구는 코드 확인만(실행 시각이 주말이라 화면 미확인) | 부분 확인 |
| 환율 타일 | 숫자 > 출처, tabular-nums | 숫자 28px·출처 12px, tabular-nums, 잘림 없음, BRL/KRW 'USD 경유 계산값' 표시 | 통과 |
| 뉴스 항목 | 굵은 제목·밑줄 없음, 회색 라벨 | 700·none, 라벨(Google News·ABIT·KOTRA·AI 요약) 회색 rgb(85,101,125), KOTRA 항목 AI 요약 0 | 통과 |
| 전시회 | D-day 크게, 상세 접힘 | D-day 22px > 행사명 16px, 'Inspiramais' 확인 필요 배지, 상세에 기간·장소·분야·확인일·메모·출처 링크 | 통과 |
| 출처 및 유의사항 | details, 필수 문구 | 기본 접힘, 업무시간 가정·BrasilAPI·한국수출입은행·PTAX·USD 경유 계산값·AI 요약·'KOTRA 자료 출처: KOTRA 해외시장뉴스'·전시회 안내 포함, 키보드 초점·열림 | 통과 |
| 도시 선택 | 갱신 | 마나우스 → 현지 시각·도구줄 기준 도시 갱신, 머리글 작성 중 칩 없음 | 통과 |
| 탭 이동 후 복귀 | 상태 유지 | 필터(Google)·도시·목록 34건 유지 | 통과 |
| PDF 성공 | 버튼 옆, 몇 초 뒤 숨김 | '다운로드를 요청했습니다.' 버튼과 같은 줄, 3초 보임·4.6초 숨김, 다운로드 요청 동작 | 통과 |
| PDF 오류(응답을 500으로 바꿈) | 안내 유지 | 5.5초 뒤에도 notice 유지, 버튼 다시 사용 가능 | 통과 |
| JS 예외·콘솔 | 없음 | 예외 0, 콘솔 오류는 favicon 404와 의도한 PDF 500만 | 통과 |
| `python -m unittest discover -s tests/test_home` / `tests/test_common` | OK | 76 OK / 56 OK | 통과 |
브라우저 검증 62/62(스크립트 1·2차 실패는 검증 스크립트·fixture 문제로 수정, 앱 코드 문제 아님). 외부 호출 0건.

### 미검증
실제 사용자 브라우저(Edge·Safari·모바일 기기), 화면낭독기 실제 낭독, 업무시간·공휴일 상태의 실제 화면 색(코드만 확인), 실제 키를 쓴 데이터 화면.

## 2026-10-25 Home 화면 2차 조정 (DEV-HOME-013)
같은 fixture 서버 2대(5013 many·5014 kotra0, FLASK_SKIP_DOTENV=1, urlopen 차단), headless Chrome CDP 측정·캡처 육안 확인.
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 공통 홈 머리글 | 화면에서 없음, h1 유지 | 머리글 1×1px(화면 밖), h1 '홈'·패널 aria-labelledby 유지, 3개 폭 | 통과 |
| 맨 위 | 일일 브리핑 바 | 1440: 바 y=32(본문 시작), 높이 66px(이전 78), PDF 버튼 y=44~86 | 통과 |
| 1440 1행 | 외곽 하단 같음 | 바이어·환율 모두 y=122~503(381px). 바이어 카드 535→381px. 환율 타일 182→148px, 타일과 아래 안내 줄 사이 약 100px 여백 | 통과(여백 있음) |
| 1440 2행 | 외곽 하단 같음 | 뉴스·전시회 모두 y=527~1499(972px). 전시회 내용은 약 403px, 나머지는 카드 안 빈 영역(빈 요소 추가 없음) | 통과(여백 있음) |
| 1440 첫 화면 | PDF·바이어 상태·환율 | PDF 버튼 하단 86, 상태 하단 256, 환율 타일 하단 394(창 900) | 통과 |
| 패딩·간격 | 통일 | 카드 5개 좌우 패딩 24px(390px은 20px), 제목→부제 4px·부제→본문 16px 4개 카드 같음, 부제 모두 한 줄(1440) | 통과 |
| 1024 | 찌그러짐 없음 | 세로 배치, 바이어 358px·환율 327px(타일 3개 한 줄), 도시 선택 이름 옆으로 정렬(1차 오른쪽 끝 → 수정) | 통과 |
| 390 | 순서·가로 스크롤 | 바→바이어→환율→뉴스→전시회→유의사항, 가로 넘침 없음, 바이어 373px | 통과 |
| 기능(이전 항목 전부 재실행) | 유지 | 필터·더 보기·재시도·도시 선택·탭 복귀·PDF 성공 4초 숨김·PDF 오류 유지·details·AI 요약·KOTRA 요약 없음 | 통과 |
| 브라우저 검증 합계 | | 79/79, JS 예외 0 | 통과 |
| `python -m unittest discover -s tests/test_home` / `tests/test_common` | OK | 76 OK / 56 OK | 통과 |
외부 호출 0건.

### 미검증
실제 사용자 브라우저(Edge·Safari·모바일 기기), 화면낭독기 실제 낭독(숨긴 머리글 h1·상태 칩 낭독 포함), 업무시간·공휴일 상태 화면 색(실행 시각이 주말).

## 2026-10-25 다음 공휴일·뉴스 주제 태그·다른 탭 바로가기 (DEV-HOME-014)
### 서버 테스트(FLASK_SKIP_DOTENV=1, 모의)
| 사례 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 다음 공휴일 A 같은 해(현지 2026-10-25) | 11/2(월) Finados · D-8 | 같음 | 통과 |
| B 오늘 공휴일(11/2) | D-DAY | 같음 | 통과 |
| C 연말(2026-12-26, 2026 남은 공휴일 없음) | 1/1(금) Confraternização mundial · D-6 | 같음 | 통과 |
| D 다음 해 자료 없음 / 올해 자료 없음 | 다음 공휴일 확인 불가 | 둘 다 같음 | 통과 |
| E 기준 도시 날짜(04:30Z: 상파울루 11/2 · 히우브랑쿠 11/1) | D-DAY / D-1, 서울 날짜 아님 | 같음 | 통과 |
| 다음 해 요청 범위 | 올해에 남은 공휴일이 있으면 다음 해 요청 없음 | 요청 연도 [2026]만 | 통과 |
| 태그 필수 1 `Brasil regulamenta acesso a cotas de exportação para a Noruega` | 규제·무역 | ['규제·무역'] | 통과 |
| 태그 필수 2 `Abrapa destaca inovação e sustentabilidade como caminhos para o futuro do algodão` | 원사, 리사이클·ESG | ['원사', '리사이클·ESG'] | 통과 |
| 태그 필수 3 `Setor enfrenta o desafio de crescer em 2027` | 원사 아님 → 기타 | ['기타'] | 통과 |
| 태그 필수 4 `Veja as novidades da semana` | 기타 | ['기타'] | 통과 |
| 정규화·낱말·최대 2개·순서·한국어 | FIOS de POLIÉSTER→원사, Desafios→기타, 5개 맞는 제목→원사·원단, 한국어 KOTRA 제목 | 같음 | 통과 |
| API items[].tags | 모든 항목 1~2개 | 같음 | 통과 |
| 관련성 필터 불변 | 태그 키워드만 있는 제목은 여전히 제외 | 같음, 기존 필터 테스트 전부 통과 | 통과 |
| PDF 테스트 | 다음 공휴일 행, 태그, 2쪽 이내 | 같음 | 통과 |
| `python -m unittest discover -s tests/test_home` / `tests/test_common` | OK | 85 OK / 56 OK | 통과 |

### PDF 실제 생성(PyMuPDF로 열어 확인, 저장소 밖)
fixture·고시일 다름·저장한 실제 RSS(KOTRA 0)·부분 실패 4종: 모두 2쪽, '1 / 2'·'2 / 2', '다음 공휴일 11/2(월) Finados · D-8', 뉴스 8건 모두 매체·날짜 줄 끝에 태그(예: `… · 10/22(목) 23:55 KST · 리사이클·ESG · 패션·리테일`), 본문 URL 0, 제목 링크 유지. 1쪽 이미지 육안 확인.

### 브라우저(fixture 서버 5013 many·5014 kotra0, urlopen 차단, headless Chrome CDP)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 시계 고정 2026-10-25 15:00Z | 다음 공휴일 11/2(월) Finados · D-8, 2027 요청 없음 | 같음 | 통과 |
| 시계 고정 2026-11-02 04:30Z | 상파울루 D-DAY·상태 '오늘은 공휴일' → 히우브랑쿠로 바꾸면 D-1(현지 11/1, 서울 11/2) | 같음 | 통과 |
| 시계 고정 2026-11-20 15:00Z | 1/1(금) Confraternização mundial · D-42, holidays?year=2027 1회 | 같음 | 통과 |
| 공휴일 API 500 | 다음 공휴일 확인 불가 | 같음 | 통과 |
| 1440·1024·390 태그 | 34건 모두 1~2개, 회색 | 같음(원사 7·원단 1·규제·무역 3·리사이클·ESG 3·패션·리테일 5·기타 19) | 통과 |
| 주제 필터·동시 적용·빈 상태 | 원사만 / ABIT+규제·무역 / KOTRA+원단 → 안내 | 같음, 뉴스 API 추가 요청 0 | 통과 |
| 바로가기 | href·이름 = 사이드바, 클릭 시 해당 탭·해시·query 없음, 복귀 후 Home 상태 유지 | 4개 모두 같음 | 통과 |
| 바로가기 배치 | 1440 한 줄 4개, 1024·390 2×2, 가로 스크롤 없음 | 같음(390 제목 줄바꿈 수정 후) | 통과 |
| 기존 화면 회귀(test_home_layout) | 79항목 | 79/79 | 통과 |
신규 기능 26/26, JS 예외 0, 외부 호출 0건.

### 미검증
실제 사용자 브라우저(Edge·Safari·모바일 기기), 화면낭독기 낭독, 실제 BrasilAPI 응답으로 연말(12월 말) 다음 해 조회, 확정 키워드 표 기준 분류 품질.

## 2026-10-25 Home 요약 대시보드 단순화 (DEV-HOME-015)
fixture 서버(5013 many·5014 kotra0, FLASK_SKIP_DOTENV=1, urlopen 차단), headless Chrome CDP 측정·캡처 육안 확인.
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 바이어 카드(1440·1024·390) | 서울 시각·다음 연락 가능 KST·공휴일 출처 숨김, 상태 가장 큼 | 화면 글자: '주말 / 브라질 현지 10/25(일) 08:29 상파울루 / 다음 공휴일 11/2(월) Finados · D-8 / 기준 도시', KST 없음, 상태 22px | 통과 |
| 바이어 카드 높이 | 줄어듦 | 1440 381→274px, 1024 358→274px, 390 373→266px | 통과 |
| 환율 카드 높이 | 줄어듦 | 1440 381→274px(행 높이), 1024 327→241px, 타일 148→127px(390 111px). 글자 크기 숫자 28 > 전일 대비 14 > 고시일·출처 12 | 통과 |
| 뉴스 | 3건 + 업계 소식 더 보기, 내부 스크롤 없음 | 3건, '업계 소식 더 보기 (31건)', 펼침/접기 3→전체→3, 스크롤 없음 | 통과 |
| 전시회 | 3건, D-day·행사명·기간·도시, 상세 접힘 | 같음, 맨 아래 '자료 확인일 2026-10-25 · 방문 전 출처에서 다시 확인하세요.' | 통과 |
| 1440 비율 | 40/60 · 60/40 | 바이어 436·환율 653, 뉴스 653·전시회 436 | 통과 |
| 1440 행 높이 | 외곽 하단 같음 | 1행 122~396(274), 2행 420~1012(592). 2행 마지막 안내 줄 높이 같음, 전시회 목록 아래 약 150px 여백 | 통과(여백 있음) |
| 1440 첫 화면(창 900) | 핵심 정보 | PDF 버튼(86)·상태(256)·현지 시각(291)·다음 공휴일(318)·환율 타일(339)·뉴스·전시회 카드 윗부분(420~) | 통과 |
| 390 | 순서·가로 스크롤 | 바→바이어→환율→뉴스→전시회→바로가기→유의사항, 넘침 없음 | 통과 |
| 기존 화면·신규 기능 회귀 | 유지 | test_home_layout 78/78(1행 내용 높이 비교 항목은 이번 구조에 맞지 않아 제외), test_home_features 26/26, 요약 측정 16/16, JS 예외 0 | 통과 |
| `python -m unittest discover -s tests/test_home` / `tests/test_common` | OK | 85 OK / 56 OK | 통과 |
외부 호출 0건. PDF·API·서버 코드 변경 없음.

### 미검증
실제 사용자 브라우저(Edge·Safari·모바일 기기), 화면낭독기 낭독.

## 2026-10-25 바이어 시각 색상·환율 compact·전시회 중남미 확장 (DEV-HOME-016)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| test_fairs 지역(A 브라질·B 중남미·C 전체) | 각 region만 / 모두 | 같음 | 통과 |
| D 전체 + 브라질 최소 2건 | 날짜순 L1 다음 B1·B2 | ['L1', 'B1', 'B2'] | 통과 |
| E 브라질 1건뿐 | 1건만, 가짜 없음 | ['L1', 'L2', 'B1'] | 통과 |
| F 날짜 미확정 행사 | 자료에 없음 | Colombiamoda·Intermoda 없음 | 통과 |
| G country/region 누락·잘못된 region | 제외, 건수 안내 | 3건 제외, invalid_count 3 | 통과 |
| 실제 자료 | 6건(브라질 3·중남미 3), 중남미는 verified=false, region↔country 일치 | 같음 | 통과 |
| H PDF 테스트 | '국가 · 도시 · 장소', '페루 · Lima' | 같음 | 통과 |
| `python -m unittest discover -s tests/test_home` / `tests/test_common` | OK | 90 OK / 56 OK | 통과 |

### PDF 실제 생성(PyMuPDF로 열어 확인, 저장소 밖)
fixture·고시일 다름·저장한 실제 RSS·부분 실패 4종 모두 2쪽, '1 / 2'·'2 / 2'. 실제 자료 PDF 전시회 표: Expotextil Perú 2026(페루 · Lima · Centro de Exposiciones Jockey, 확인 필요, EventsEye 링크) · Inspiramais(브라질) · Tecnotêxtil Brasil 2027(브라질) = 브라질 최소 2건 정책. Colombiamoda·Intermoda 없음. 2쪽 이미지 육안 확인(한글·포르투갈어·스페인어 악센트 정상).

### 브라우저(fixture 서버 5013 many·5014 kotra0, urlopen 차단, headless Chrome CDP)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 시계 고정 4종 | 업무시간 초록·업무시간 외/주말 주황·공휴일 빨강, 작은 글자, 화면낭독 이유 | 시각·글자 색 rgb(11,117,100)/(138,83,0)/(180,35,24), '연락 가능'/'연락 어려움', 숨은 글 '(업무시간)'·'(주말)'·'(업무시간 외)'·'(공휴일)', 시각 40px·글자 14px | 통과 |
| 바이어 화면 글자 | '주말'·KST·서울·BrasilAPI 없음, 다음 공휴일 있음 | 같음 | 통과 |
| 1440 1행 | 외곽 같음 | 바이어·환율 269px(전 274), 내용 끝 245/217px | 통과 |
| 환율 | 숫자 > 전일 대비 > 출처 | 28 > 14 > 12px, 타일 127px | 통과 |
| 뉴스 | 4건 + 업계 소식 더 보기, 스크롤 없음 | 같음 | 통과 |
| 지역 필터 | [전체 6][브라질 3][중남미 3], 회색, 화면 안 | 같음(1440·1024·390) | 통과 |
| 전체 3건 | 브라질 최소 2건 | Expotextil Perú(페루 · Lima)·Inspiramais·Tecnotêxtil(브라질) | 통과 |
| 브라질/중남미 필터 | 해당 행사만, 미확정 행사 없음 | 브라질 3·중남미 3 | 통과 |
| 읽는 순서 | D-day·행사명 → 국가·도시 → 기간 | 같음 | 통과 |
| 1440 2행 | 외곽·마지막 줄 같음 | 뉴스·전시회 675px, 하단 안내 줄 같은 높이(전시회 목록 아래 약 120px 여백) | 통과(여백 있음) |
| 가로 스크롤 / JS 예외 | 없음 | 없음 | 통과 |
| 회귀 | 기존 화면·신규 기능 | test_home_layout 78/78, test_home_features 26/26, 6차 29/29 | 통과 |
외부 호출(브라우저·PDF 검증 중) 0건.

### 미검증
중남미 행사 공식 주최 사이트 일정, 실제 사용자 브라우저(Edge·Safari·모바일 기기), 화면낭독기 실제 낭독.

## 2026-10-25 1행(바이어 시간·환율) compact화 (DEV-HOME-017)
fixture 서버(5013 many·5014 kotra0, FLASK_SKIP_DOTENV=1, urlopen 차단), 브라우저 시계 고정 2026-10-25 10:47Z(상파울루 일 07:47), headless Chrome CDP 측정·캡처 육안 확인. 같은 스크립트로 수정 전·후 측정.
| 항목 | 수정 전 | 수정 후 | 판정 |
|---|---|---|---|
| 1440 바이어 카드 높이 | 269px | 161px(약 40% 감소) | 통과 |
| 1440 환율 카드 높이 | 269px | 161px | 통과 |
| 1440 환율 타일 높이 | 127px | 91px | 통과 |
| 1440 하단선 | 391 / 391 | 283 / 283(같음) | 통과 |
| 1440 뉴스 카드 시작(y) / 첫 화면 뉴스 영역 / 다 보이는 기사 | 415 / 485px / 3건 | 307 / 593px / 4건 | 통과 |
| 1024 바이어 / 환율 | 269 / 241px | 161 / 158px(세로 배치), 뉴스 영역 221→411px | 통과 |
| 390 바이어 / 환율 | 261 / 464px | 161 / 276px(환율 2+1), 숫자 줄바꿈 없음, 가로 스크롤 없음 | 통과 |
| 표시 | 부제 없음, 도시 선택 제목 줄, 시각 40px 주황(주말), '연락 어려움 · 10/25(일)', 다음 공휴일 한 줄, 환율 '10/23 고시 · 한국수출입은행' / 'BCB PTAX' / BRL/KRW 'USD 경유 · 10/23 고시' | 같음 | 통과 |
| 회귀 | test_home_layout 78/78(부제 간격 항목은 1행 카드 제외), test_home_features 26/26, 6차 29/29, JS 예외 0 | | 통과 |
| `python -m unittest discover -s tests/test_home` | OK | 90 OK(Python 변경 없음) | 통과 |
외부 호출 0건. Python·API·PDF 파일 변경 없음(git diff *.py 없음).

## 2026-10-26 Home 색감 정리 (DEV-HOME-018)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 새 글자·배경 조합 대비(WCAG 공식 계산) | 4.5:1 이상 | 민트 hover 칩 5.00, 선택 칩 5.84, 분류 라벨 5.32, 바 보조 글자(그라데이션 양끝) 5.06·5.23, 바 제목 13.27, 환율 숫자 15.53, 바로가기 hover 설명 5.29, 민트 화살표 5.61 | 통과 |
| 1440·1024·390 화면(fixture 서버, urlopen 차단) | 배치·높이 그대로, 가로 스크롤·예외 없음 | 1행 161px·뉴스 시작 y=309 등 이전과 같음(1440 첫 측정은 서버 기동 전 접속 실패로 다시 측정), 예외 0 | 통과 |
| 회귀 | 유지 | test_home_layout 78/78, test_home_features 26/26, 6차 29/29(분류 라벨 글자색 rgb(85,101,125) 그대로) | 통과 |
외부 호출 0건. Python·API·PDF 변경 없음.

## 2026-10-26 업계 소식 상세 화면·검색 (DEV-HOME-019)
### 서버(모의, FLASK_SKIP_DOTENV=1)
| 사례 | 기대 | 실제 | 판정 |
|---|---|---|---|
| A RSS 6건(중복 1) | 관련 3건 | 3건(collected 5, after_filter 3) | 통과 |
| B .pt 매체 / C 섬유 무관 / D 중복 | 제외 / 제외 / 1건 | 같음 | 통과 |
| E 태그 | 모든 기사 1~2개 | 같음(첫 기사 원사·리사이클·ESG) | 통과 |
| 검색어 구성 | 따옴표 + 섬유 낱말 + when:90d, hl=pt-BR&gl=BR&ceid=BR:pt-419 | 같음 | 통과 |
| 상한 | 30건 → 20건 | 20 | 통과 |
| AI | 새 호출 없음, 캐시 요약만 재사용 | _request 미호출, 캐시 요약 붙음 | 통과 |
| G 빈칸·공백·1글자·81자 | 400 invalid_query, 외부 요청 없음 | 같음 | 통과 |
| F RSS 실패 | 502 search_failed 고정 문장, 기존 뉴스 그대로 | 같음 | 통과 |
| `python -m unittest discover -s tests/test_home` / `tests/test_common` | OK | 94 OK / 56 OK | 통과 |

### 실제 Google News RSS 1회
검색어 `poliéster reciclado` → HTTP 200, 원본 item 12건, 중복 제거 12건, .pt 2건, 제외 매체 도메인 3건(portugaltextil.com 포함), 관련성 통과 2건(축구 유니폼·버스 PET 등 섬유 낱말 없는 기사 제외).

### 브라우저(fixture 서버 5013 many·5014 kotra0, urlopen 차단, headless Chrome CDP)
1440·1024·390 각각: 카드 4건 + '업계 소식 더 보기 (전체 34건 · 검색)' → 상세(Home 숨김·제목 초점·전체 34건) → 'ALGODAO' 내부 검색(algodão 기사, 외부 요청 0) → '원사'(태그 검색) → 무결과 검색어 입력만으로 요청 0, 안내·버튼 → 버튼 1회 요청 → 관련 3건·'Google News 검색' 라벨·태그·새 탭 링크·새 AI 요약 없음 → 같은 검색어 재제출 요청 0 → 매체 KOTRA로 검색 결과 0건 → 주제 '원사'·매체 ABIT 동시 적용 → 1글자 무결과 버튼 비활성 → 'falha' 실패 안내·'다시 검색'(1440 재시도 1회) → 가로 스크롤 없음 → '← 홈으로'(초점 더 보기, 카드 4건, 주소 그대로). 46/46, localStorage·sessionStorage 0, JS 예외 0. 서버 기록 검색 요청 7건(=버튼 클릭 수). 1440 검색창+버튼 한 줄, 390 줄바꿈 육안 확인.
회귀: test_home_layout 78/78, test_home_features 26/26, 6차 29/29(더 보기 동작 변경에 맞춰 기대값만 수정).

### 미검증
브라우저 뒤로 가기 연동(구현 안 함), 실제 사용자 브라우저(Edge·Safari·모바일 기기), 화면낭독기 낭독.

## 2026-10-26 다른 탭 바로가기 제외 (DEV-HOME-020)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 1440·1024·390 화면(fixture 서버, urlopen 차단) | 바로가기 영역 없음, 출처 및 유의사항이 2행 바로 아래, 가로 스크롤 없음 | 같음(하단 캡처 육안 확인) | 통과 |
| 공통 사이드바 4개 탭 이동 | 그대로(해시 동일, query 없음), 다녀온 뒤 Home 상태 유지 | 같음 | 통과 |
| 회귀 | 유지 | test_home_layout 78/78, test_home_features 23/23(바로가기 항목 3개를 '영역 없음·사이드바 이동' 확인으로 바꿈), 6차 29/29, 뉴스 상세 46/46, JS 예외 0 | 통과 |
| `python -m unittest discover -s tests/test_home` | OK | 94 OK | 통과 |
외부 호출 0건.

## 2026-10-26 공통 블루·아쿠아·민트 대시보드 UI (DEV-COMMON-002)
변경: static/css/tokens.css, static/css/common.css, docs/design_system.md (기능 파일·base.html·app_shell.js 변경 없음)
환경: Conda jasonenv Python 3.11.17, Flask 3.1.2. 검증 서버 127.0.0.1:5013(저장소 밖 실행기: FLASK_SKIP_DOTENV=1, API 키 제거, urllib.request.urlopen 차단). 브라우저: 시스템 Chrome + playwright-core 1.48.2(세션 임시 폴더에 설치, 저장소·requirements 미추가).

### 서버·테스트
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| `import app` + test_client `GET /`, tokens.css·common.css | 200 | 200(55,697 bytes), 200, 200 | 통과 |
| `python -m unittest discover -s tests/test_common` | OK | 56 OK | 통과 |
| `-s tests/test_home` | OK | 94 OK | 통과 |
| `-s tests/test_market_analysis` | OK | 71 OK | 통과 |
| `-s features/green_claim/tests` (PYTHONUTF8=1) | OK | 178 OK (UTF-8 미설정 시 cp949 콘솔 인코딩 오류로 중단 → 환경 문제, 재실행 통과) | 통과 |
| `-s tests/test_green_claim`·`test_product_brochure`·`test_promotion_studio` | - | 0건(테스트 없음) | 해당 없음 |

### 화면(5개 탭 × 1440·1024·390, 전체 화면 캡처 15장 육안 확인)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| Home·시장 분석·제품소개서·그린 클레임 체크·홍보 스튜디오 진입 | 패널 표시, AppShell.current 일치 | 15/15 일치 | 통과 |
| 가로 스크롤·화면 밖 요소(스크롤 컨테이너 제외) | 없음 | 15/15 없음 | 통과 |
| JS 예외·console error | 없음 | 0건(3개 폭) | 통과 |
| 수정 전 캡처와 비교 | 배치 동일, 색·모서리·테두리·안내 상자만 변경 | 같음(카드 1px 테두리 추가로 높이 2px 차이 수준) | 통과 |
| 390 Home·홍보 스튜디오 | 카드·안내·버튼 겹침·잘림 없음 | 같음 | 통과 |

### 상호작용(26/26 통과)
탭 진입 애니메이션 panel-enter·종료 후 opacity 1/transform none, 그린 클레임 입력 → Home → 복귀 시 입력 유지, 사이드바 작성 중 점·머리글 칩·aria-current, active 메뉴 rgb(234,242,253)/rgb(21,89,184), 메뉴 hover rgb(240,245,251), 입력 키보드 초점 블루 테두리 + rgba(29,106,212,.28) 3px 링 + outline 2px(투명), primary hover translateY(-1px)·그림자 증가·radius 10px·그라데이션, Tab 초점 버튼 outline solid 블루, disabled 점선·글자 rgb(84,99,122), 1440 스크롤 500px 후 사이드바 top 0·높이 900, 카드 1px rgb(231,236,243)·16px·그림자, notice info/danger tint·3px 강조·제목 상태색·본문 네이비, 상태 배지 점 있음 vs neutral 점 없음, 표 머리 rgb(246,248,251)·숫자 tabular-nums 오른쪽·행 hover rgb(246,249,254), spinner 회전, 시장 분석 빈 입력 실행 → field-error 3건, 390 메뉴 열림·main inert·메뉴 초점 → Esc 닫힘·토글로 초점 복귀 → 메뉴로 그린 클레임 이동 후 닫힘, reduced-motion에서 탭 진입 애니메이션 none·transition 0s·버튼 hover 이동 none.
(첫 실행 25/26: 입력 초점을 transition 150ms 중에 측정한 스크립트 문제 → 300ms 대기 후 26/26. 표·notice·배지는 테스트용 임시 요소로 계산 스타일만 확인 후 제거, 화면 데이터 아님)

### 대비(WCAG 계산)
흰 글자/primary 5.17, /그라데이션 끝 4.70, primary-text/흰 6.66·/soft 5.90, text 15.67, muted/흰 6.10·/배경 5.63, success/soft 5.31, warning/soft 6.17, danger/soft 5.83, info/soft 6.07, neutral 6.61, 입력 테두리 3.50.

### 미검증
실제 사용자 브라우저(Edge·Safari·Firefox·모바일 기기), 화면낭독기, Windows 고대비 모드, 실제 외부 데이터가 들어온 상태의 표·뉴스·환율 화면(이번 검증은 외부 차단 상태의 오류·설정 필요 화면), 그린 클레임·시장 분석의 실제 분석 결과 화면(유료/외부 호출 필요해 미실행), PDF 출력물(화면 CSS와 별개라 영향 없음으로 판단, 미확인).

## 2026-10-26 시장 분석 분류 배지 정리 (DEV-COMMON-003)
변경: features/market_analysis/templates/market_analysis/panel.html (badge-info → badge-neutral)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 시장 분석 1440 배지 계산 스타일·캡처 | badge-neutral, 블루그레이, 점 없음, 문구 동일 | bg rgb(238,242,247), 글자 rgb(71,86,110), ::before none, "브라질 · 수입" | 통과 |
| `python -m unittest discover -s tests/test_market_analysis` | OK | 71 OK | 통과 |
| 5개 탭 × 1440/1024/390 재캡처(검증 서버 5013, 외부 차단) | 가로 스크롤 없음, JS 예외 0 | 15/15, 예외 0 | 통과 |
| 공통 상호작용 재실행 | 26/26 | 26/26 | 통과 |
외부 호출 0건.

## 2026-10-26 로딩·오류·성공·다운로드 UX 정리 (DEV-COMMON-004)
변경: static/js/app_shell.js, static/css/common.css, features/home(home.js·panel.html·feature_spec), features/market_analysis(market_analysis.js·panel.html·feature_spec), features/green_claim(green_claim.js·feature_spec), features/product_brochure·promotion_studio panel.html, docs/design_system.md
환경: Conda jasonenv Python 3.11.17, Flask 3.1.2. 검증 서버 127.0.0.1:5013(저장소 밖 실행기: FLASK_SKIP_DOTENV=1, API 키 제거, urlopen 차단, ComexStat get_latest_month·query_imports·lookup_code를 가상 수치로 대체 — 기존 test_market_analysis와 같은 패치 방식, 실제 통계 아님). 그린 클레임 검수 성공 응답은 features/green_claim/tests/test_review_report_flow.py의 가상 사례 A + 모의 AI로 만든 JSON을 브라우저 route로 반환. 지연·500·네트워크 끊김은 Playwright route로 주입. 브라우저: 시스템 Chrome + playwright-core 1.48.2(세션 임시 폴더).

### 단위 테스트
| 절차 | 실제 | 판정 |
|---|---|---|
| `python -m unittest discover -s tests/test_common` | 56 OK | 통과 |
| `-s tests/test_home` | 94 OK | 통과 |
| `-s tests/test_market_analysis` | 71 OK | 통과 |
| `-s features/green_claim/tests` (PYTHONUTF8=1) | 178 OK | 통과 |
| `-s tests/test_green_claim`·`test_product_brochure`·`test_promotion_studio` | 0건(테스트 없음) | 해당 없음 |
| JS 문법(node vm 파싱) app_shell·home·market_analysis·green_claim | 오류 없음 | 통과 |
새 JS helper 단위 테스트: JS 테스트 체계가 없어 추가하지 않음(브라우저 검증으로 대신).

### UX 상호작용(36/36 통과, 첫 실행 34/36은 검증 실행기 문제 — 아래)
| 항목 | 결과 |
|---|---|
| 시장 분석 실행 중 | 버튼 '분석 중...'·disabled·aria-busy, 결과 영역 aria-busy, 중복 클릭·requestSubmit 재제출에도 analyze 요청 1회, 완료 후 '분석 실행'·활성·결과 표시 |
| 시장 분석 PDF | 'PDF 준비 중...'·disabled·aria-busy, PDF 생성 중 '다시 불러오기' 완료 후에도 PDF 버튼 비활성 유지(수정 전 버그 시나리오), 요청 1회·다운로드 발생, notice-success role=status → 4초 뒤 제거, 버튼 복원 |
| 시장 분석 PDF 500 | notice-danger role=alert·서버 문장·5초 뒤에도 유지·버튼 복원·결과 표 유지 |
| 시장 분석 PDF 네트워크 끊김 | 고정 문장('연결하지 못했거나'), Failed to fetch 등 원문 없음, notice 1개 |
| 시장 분석 조회 네트워크 끊김 | 폼 오류 role=alert 고정 문장, 원문 없음, 이전 결과 유지, 버튼 복원 |
| 시장 분석 실행 중 탭 이동 → 복귀 | 완료 상태(버튼 '분석 실행'·활성, aria-busy false, 오류 없음) |
| 바이어 목록 500(HTML 응답) | '새로고침' 안내 없음, 재시도 버튼 → 다시 불러와 표 표시 |
| Home 일일 브리핑 PDF | 'PDF 준비 중...'·disabled·aria-busy(버튼·영역), 중복 클릭에도 요청 1회, 실제 서버 PDF 다운로드, 버튼 복원, '다운로드를 요청했습니다.' 4초 뒤 숨김 |
| Home PDF 500 / 네트워크 끊김 | notice-danger role=alert 5초 뒤에도 유지·버튼 복원 / '서버에 연결하지 못했습니다' 고정 문장, notice 1개 |
| Home 환율·뉴스 재시도 실패 2회 | 요청 오류 notice 각 1개(누적 없음), role=alert, aria-busy 해제 |
| Home 로딩 문구 | 4개 모두 '...' |
| 그린 클레임 검수(키 없음 실제 서버, 900ms 지연) | '검수 중...'·disabled·aria-busy, 옆 안내 문장 유지·스피너 중복 없음, 요청 1회, notice-danger role=alert, 버튼 복원 |
| 그린 클레임 검수 성공(모의 응답) → PDF(실제 서버 생성) | 'PDF 준비 중...'·안내 '30초', 요청 1회, 다운로드 발생, 버튼 복원, notice-success, 5초 뒤에도 유지(B 유형) |
| 그린 클레임 PDF 네트워크 끊김 | notice-danger 1개·고정 문장·버튼 복원 |
| 그린 클레임 파일 추출 500(지연 800ms) | 누른 버튼만 '글자 추출 중...', 두 버튼 disabled, 실패 notice-danger role=alert, '글자 추출' 복원 |
| 제품소개서·홍보 스튜디오 | 버튼 4개 모두 disabled + '준비 중' 안내 aria-describedby 연결 |
| 390px 작업 중 버튼 | 가로 스크롤 없음 |
| reduced-motion | 작업 중 버튼 회전 animation-duration 0s |
| JS 예외 | 모든 페이지 0건 |
첫 실행 실패 2건: 모의 실행기에 `if __name__ == "__main__"`가 없어 그린 클레임 PDF 별도 프로세스(Windows spawn)가 실행기를 다시 실행 → 서버 PDF 30초 시간 제한. 이때도 화면은 실패 notice·버튼 복원으로 처리됨. 실행기 수정 후 36/36.

### 공통 회귀
| 절차 | 실제 | 판정 |
|---|---|---|
| 5개 탭 × 1440/1024/390 캡처 | 15/15 표시, 가로 스크롤·화면 밖 요소 없음, JS 예외 0 | 통과 |
| 공통 상호작용(DEV-COMMON-002 스크립트) | 26/26 | 통과 |
| 작업 중 화면 캡처 육안(시장 분석 1440·390 버튼, Home PDF, 그린 클레임 검수, 바이어 오류) | 원래 색 + 회전 표시, 문구 잘림 없음 | 통과 |

### 외부 호출
전송 0건. 차단된 시도 45건(news.google.com·brasilapi.com.br·olinda.bcb.gov.br), ComexStat는 모의 함수, OpenAI 키 없음.

### 미검증
Firefox·Safari·모바일 기기·화면낭독기 실제 낭독, Firefox에서 disabled 버튼 초점 유지 여부, 시장 분석 AI 분석 실행·성공 화면(유료 호출), 실제 ComexStat 응답으로 조회, 실제 외부 뉴스·환율이 들어온 Home, 그린 클레임 실제 AI 검수·OCR.

## 2026-10-26 결과 초점·키보드·화면낭독 흐름 (DEV-COMMON-005)
변경: static/js/app_shell.js, static/css/common.css, features/market_analysis(JS·panel·spec), features/home(JS·spec), docs/design_system.md, tests/test_common/test_shell_a11y.py(신규)
환경: jasonenv Python 3.11.17, Flask 3.1.2. 검증 서버 127.0.0.1:5013(저장소 밖 모의 실행기: FLASK_SKIP_DOTENV=1, API 키 제거, urlopen 차단, ComexStat 가상 수치). 시장 분석 AI는 meta의 ai.ready만 브라우저 route로 true로 바꾸고 /api/market-analysis/ai는 가상 응답(성공·실패). 그린 클레임 검수 성공은 통합 테스트 가상 사례 JSON. Chrome + playwright-core 1.48.2, 키보드는 Playwright keyboard.press(Tab·Shift+Tab·Enter·Space·ArrowLeft/Right·End).
수정 전 재현: 분석 완료 후 activeElement BODY·결과 제목 top -127, AI 실행 중·완료 후 BODY, 바이어 재시도 성공 후 BODY, aria-live 영역 결과 2,874자·바이어 82,992자.

### 단위 테스트
| 절차 | 실제 | 판정 |
|---|---|---|
| `-s tests/test_common` | 62 OK(신규 test_shell_a11y 6건 포함) | 통과 |
| `-s tests/test_home` | 94 OK | 통과 |
| `-s tests/test_market_analysis` | 71 OK | 통과 |
| `-s features/green_claim/tests` (PYTHONUTF8=1) | 178 OK | 통과 |
| JS 문법(node vm) app_shell·home·market_analysis | 오류 없음 | 통과 |

### 키보드·초점(41/41 + Home 상세 4/4 통과)
| 시나리오 | 결과 |
|---|---|
| skip link | 첫 Tab에 화면에 보임 → Enter로 main#main-content 초점 |
| 사이드바 | Enter로 탭 전환 → 탭 h1 초점, Shift+Tab 역순, Space는 링크라 전환 안 함(기본 동작) |
| 시장 분석 빈 입력 | 첫 오류 필드(품목코드) 초점, aria-invalid, aria-describedby에 오류 문장 |
| 시장 분석 정상 분석(키보드, 결과 제목이 화면 밖인 상태에서) | '분석 결과' h2 초점, 위 여백 포함 화면 안으로 스크롤, role=status "분석 결과가 준비되었습니다…", Tab → PDF 버튼, Shift+Tab → 왼쪽 열 '다시 불러오기'(DOM 순서) |
| 시장 분석 AI 성공·실패 | 실행 중·완료 후 '④ AI 분석' region 초점(BODY 아님), 성공 status / 실패 role=alert, Tab으로 영역 안 첫 요소·'AI 분석 실행' 도달 |
| 시장 분석 PDF 성공·실패 | 작업 끝나면 PDF 버튼으로 초점 복원, 실패 role=alert(성공 안내가 초점 안 뺏음) |
| 시장 분석 조회 네트워크 실패 | 실행 버튼 초점 복원, 폼 오류 role=alert |
| 분석 중 Home으로 이동 | 완료돼도 숨긴 시장 분석으로 초점 이동 없음 |
| 바이어 목록 | 자동 로딩 실패 초점 이동 없음 → 재시도 실패 시 새 재시도 버튼 → 성공 시 목록 제목, 하위 탭 화살표·End 이동 |
| Home | 자동 로딩 중 사용자가 둔 도시 select 초점 유지, PDF 성공(Enter)·실패(Space) 버튼 초점 복원 + 실패 role=alert, 환율·뉴스 재시도 실패 → 새 재시도 버튼, 전시회 필터 button+aria-pressed Enter 전환 |
| Home 상세 Google 검색(뉴스 0건이라 숨긴 '더 보기'를 스크립트로 열어 확인) | 실패 → '다시 검색' 버튼, 성공(버튼 숨김) → 결과 건수 문장(role=status), 검색 중 검색창으로 옮기면 초점 유지 |
| 그린 클레임 | 2단계 이동 시 단계 제목 초점, 검수 실패 → 검수 버튼 복원 + role=alert, 검수 성공 → 3단계 결과 제목 1회, PDF 성공·실패 → PDF 버튼 복원, 중간 단계(추출) 실패 → 추출 버튼 유지 |
| 제품소개서·홍보 스튜디오 | 입력은 Tab 접근, disabled 버튼은 Tab에서 빠짐 |
| reduced-motion | 결과 제목 초점 직후 이미 목표 위치(top 24px) — 즉시 스크롤 |
| 기본 모션 | 초점 직후 이동 중 → 1초 뒤 top 24px(부드러운 스크롤) |
| 390px | 결과 제목이 sticky 상단바(56px) 아래에 보임, 가로 스크롤 없음 |
| JS 예외 | 전 시나리오 0건 |
첫 실행 38/41: 기대값 오류 1(Shift+Tab 앞 요소), PDF 생성 대기 부족 2 → 스크립트 수정 후 41/41. 이후 캡처에서 결과 제목이 화면 맨 위에 붙고 390px에서 상단바에 가려지는 문제 발견 → scroll-margin-top 추가, 위치 기준을 강화(1440 ≥20px, 390 ≥56px)해 재실행 41/41.

### 화면낭독기 관련
실제 NVDA·VoiceOver 실행: 하지 않음. 브라우저 DOM 점검만: role=status/alert, aria-live 위치(큰 결과·바이어 목록 제거, 짧은 상태 문장만), aria-busy, aria-describedby, 초점 대상(tabindex=-1 제목·region).

### 회귀
| 절차 | 실제 | 판정 |
|---|---|---|
| 5개 탭 × 1440/1024/390 캡처 | 15/15, 가로 스크롤 없음, JS 예외 0 | 통과 |
| 공통 상호작용(DEV-COMMON-002) | 26/26 | 통과 |
| 로딩·오류·다운로드 UX(DEV-COMMON-004) | 36/36 | 통과 |
| 초점 캡처 육안(1440 키보드, 1440 기본, 390) | 제목 위 여백, 키보드 초점 테두리 표시, 상단바에 안 가림 | 통과 |

### 외부 호출
전송 0건. 차단 시도 104건(news.google.com·brasilapi.com.br·olinda.bcb.gov.br).

### 미검증
실제 화면낭독기 낭독, Firefox·Safari·모바일 기기 초점 동작, 실제 OpenAI AI 분석·그린 클레임 AI 검수, 실제 외부 뉴스가 있는 Home 상세(이번엔 0건 상태에서 확인).

## 2026-10-26 FIONEX 공식 로고 적용 (DEV-COMMON-006)
변경: static/assets/fionex_logo.png(신규), templates/base.html, static/css/common.css, static/css/tokens.css, docs/design_system.md, tests/test_common/test_shell_a11y.py
환경: jasonenv Python 3.11.17(Pillow로 원본 검사), 검증 서버 127.0.0.1:5013(저장소 밖 모의 실행기, urlopen 차단), Chrome + playwright-core 1.48.2.

| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 원본 검사(Pillow) | 크기·비율·투명 | 2172×724, 3.0, RGBA, 모서리 알파 0 | 확인 |
| 흰 배경 합성 미리보기 | 글자·리본 식별 | 네이비 글자·블루/민트 리본 선명 | 확인 |
| 복사본 동일성(cmp) | 원본과 같음 | identical | 통과 |
| GET /static/assets/fionex_logo.png | 200 | 200, 870,173 bytes | 통과 |
| 1440·1024 사이드바 | 1개 표시, 168×56, 비율 3.000, 사이드바 안, 메뉴와 간격, 세로 스크롤 없음 | 168×56 at x20 y24, 첫 메뉴와 간격 24px, 스크롤 없음 | 통과 |
| 로고 정렬 | 로고 글자 시작이 메뉴 아이콘 세로선 근처 | 29.8px vs 28px | 통과 |
| 390 상단바 | 120×40, 메뉴 버튼 오른쪽, 상단바 높이 안 | 통과 | 통과 |
| 390 메뉴(드로어) | 로고가 닫기 버튼과 겹치지 않음, 비율 유지 | 통과 | 통과 |
| alt·filter·brand-mark | alt=FIONEX, filter none, .brand-mark 0개 | 통과 | 통과 |
| 가로 스크롤·JS·로드 오류(3폭) | 없음 | 없음 | 통과 |
| 2배율(1440) 캡처 육안 | 흐리지 않음 | 글자·슬로건 선명 | 통과 |
| 로고 검증 스크립트 | - | 15/15 | 통과 |
| `-s tests/test_common` | OK | 63 OK(로고 구조 테스트 1건 추가) | 통과 |
| `-s tests/test_home` / `test_market_analysis` / `features/green_claim/tests` | OK | 94 / 71 / 178 OK | 통과 |
| 5개 탭 × 1440/1024/390 | 정상 | 15/15, 가로 스크롤·JS 예외 0 | 통과 |
| 공통 상호작용 / 키보드·초점 | 유지 | 26/26 / 41/41 | 통과 |
외부 호출: 0건.

### 미검증
실제 사용자 브라우저(Edge·Safari·모바일 기기)·고해상도 실제 모니터, 1배율 화면에서 슬로건 가독성(약 5px로 판독 어려움 — 원본 축소 그대로), 큰 PNG 첫 로딩 시간.

## 2026-10-26 브랜드 폰트 Brand New Hyosung 적용 (DEV-COMMON-007)
변경: static/css/common.css, static/css/tokens.css, docs/design_system.md, tests/test_common/test_shell_a11y.py (폰트 파일 static/fonts/brand/*.ttf는 사용자 제공 그대로)
환경: jasonenv Python 3.11.17, fontTools 4.55.3(세션 임시 폴더), 검증 서버 127.0.0.1:5013(모의 실행기, urlopen 차단), Chrome + playwright-core 1.48.2. 실제 렌더링 글꼴은 CDP CSS.getPlatformFontsForNode(요소별 실제 사용 글꼴·글자 수)로 측정.

### 폰트 파일
| 파일 | usWeightClass | 한글 | ASCII | 포르투갈어 악센트 | 기타 |
|---|---|---|---|---|---|
| Brand New Hyosung Light.ttf | 300 | 11,172 | 전부 | 없음 | – — • € 없음 |
| Brand New Hyosung Medium.ttf | 500 | 11,172 | 전부 | 없음 | 동일 |
| Brand New Hyosung Bold.ttf | 700 | 11,172 | 전부 | 없음 | 동일 |

### 실제 렌더링 글꼴(27/27 통과)
body 본문·사이드바 메뉴(활성/일반)·버튼·select·Home KPI(현재 시각)·카드 제목·badge·notice 제목·필터 칩·그린 클레임 안내문·input(품목코드)·시장 분석 KPI·표 td.num·표 th·차트 SVG text.ma-axis·차트 툴팁 → 모두 "Brand New Hyosung(웹폰트)"만 사용.
포르투갈어: 시장 분석 품목명 'Fios texturizados de poliésteres' → Brand New Hyosung 90자 + Malgun Gothic 1자(é). textarea 입력('… Nosso fio é 100% sustentável e não causa …')은 CDP로 측정 불가 → font-family "Brand New Hyosung" + 캡처 육안(é·á·ã만 대체 글꼴로 조금 가늘고 a 모양 다름, 글자 누락 없음).
file 선택 버튼: 수정 전 Arial → 수정 후 "Brand New Hyosung". 화면 요소 굵기: 수정 전 400·500·700 → body 굵기 지정 후 500·700만(OS가 그리는 select option 제외).
표 숫자 tabular-nums 유지, SVG text font-family 상속 "Brand New Hyosung".
폰트 face: 500 loaded·700 loaded·300 unloaded(미사용이라 요청 안 함).

### 네트워크
| 요청 | 결과 |
|---|---|
| /static/fonts/brand/Brand New Hyosung Medium.ttf | 200 (application/octet-stream) |
| /static/fonts/brand/Brand New Hyosung Bold.ttf | 200 (application/octet-stream) |
| 그 외 글꼴 요청 | 없음 |
| 127.0.0.1:5013 밖 요청 | 0건 |

### 회귀
| 절차 | 실제 | 판정 |
|---|---|---|
| 5개 탭 × 1440/1024/390 | 15/15, 가로 스크롤·화면 밖 요소 없음, JS 예외 0. 캡처 육안: 사이드바 메뉴·버튼·칩·표 머리·badge·notice·placeholder·KPI·그린 클레임 긴 안내문 줄바꿈·잘림 이상 없음 | 통과 |
| 공통 상호작용 / 키보드·초점 / 로딩·오류 UX / 로고 | 26/26 / 41/41 / 36/36 / 15/15 | 통과 |
| `-s tests/test_common` | 64 OK(폰트 로컬 파일·외부 CDN 없음 테스트 추가) | 통과 |
| PDF 관련 파일 diff(features/*/pdf*·report*·fonts, common/pdf_utils.py) | 변경 없음 | 통과 |
포르투갈어 대체 글꼴 비교 캡처(현재 스택 vs Segoe UI 우선 vs Malgun만): 차이 작음 → 스택 유지.

### 미검증
macOS·iOS·Android 실제 렌더링(대체 글꼴 다름), 실제 사용자 브라우저·고해상도 모니터, 웹 사용권, 느린 네트워크에서 swap 전환 체감.

## 2026-10-26 웹·모든 탭 PDF Pretendard 통일 (DEV-COMMON-008)
변경: static/fonts/pretendard/(신규), common/config.py, static/css/common.css·tokens.css, features/home/report.py, features/market_analysis/pdf_report.py, features/green_claim/report_worker.py·tests/test_report.py, tests/test_common/test_shell_a11y.py, 기능별 fonts/ 3곳 삭제, 문서
환경: jasonenv Python 3.11.17, fontTools 4.55.3·PyMuPDF 1.24.14(세션 임시 폴더 설치, 저장소·requirements 미변경), 검증 서버 127.0.0.1:5013(모의, urlopen 차단), Chrome + playwright-core 1.48.2.

### 파일
| 확인 | 결과 |
|---|---|
| 복사본과 배포본 바이트 비교(cmp) | woff2 4·ttf 2·LICENSE.txt 모두 동일 |
| TTF 형식·굵기·임베딩 | glyf(TrueType), Regular 400·Bold 700, fsType 0, Version 1.309 |
| 글리프 | 한글 11,172/11,172, ASCII 전부, 포르투갈어 악센트 누락 없음, ⓘ만 없음 |

### PDF 실제 생성(가상 데이터, PyMuPDF로 열기·렌더링)
| PDF | 쪽수·크기 | 포함 글꼴 | 포르투갈어 문자(추출) | 대체·깨짐 |
|---|---|---|---|---|
| Home 일일 브리핑(build_daily, 외부 수집 차단) | 2쪽, 47,657 bytes | Pretendard-Regular·Bold (+ ReportLab 기본 선언 Helvetica) | ê ú | U+FFFD 0, 실제 [U+] 대체 0 |
| 시장 분석(ComexStat 가상 수치, 품목명 'poliésteres … ação têxtil') | 53쪽, 254,942 bytes | Pretendard-Regular·Bold | Í á ã ç é ê | 0, 0 |
| 그린 클레임(통합 테스트 가상 사례, POST /api/green-claim/report 별도 프로세스) | 6쪽, 94,562 bytes | Pretendard-Regular·Bold | É Í à á â ã ç é ê í ó õ ú | 0, 0('[U+XXXX]'는 범례 고정 문장) |
페이지 이미지 육안(Home 1쪽, 시장 분석 1쪽, 그린 클레임 2쪽): 표 넘침·잘림·겹침 없음, não·Código·§1º·poliésteres 정상. 시장 분석 차트 축 라벨 반올림 겹침은 기존 표기 규칙(글꼴 무관).
/Helvetica 확인: Pretendard만 쓰는 최소 ReportLab 문서도 페이지 리소스에 Helvetica(/F1 12 Tf 선언 1회, 그린 글자 없음) 포함.

### 웹(27/27 통과, CDP 실제 렌더링 글꼴)
body·사이드바(Medium/SemiBold)·버튼·select·Home KPI·카드 제목·badge·notice·필터 칩·그린 클레임 안내문·input·시장 분석 KPI·표 th/td.num·차트 SVG text·툴팁·file 선택 버튼 → 모두 Pretendard 웹폰트만. 포르투갈어(Perú·Tecnotêxtil·poliésteres 91자)도 대체 글꼴 없음. 화면 굵기 400·500·600·700, face 4개 loaded.
네트워크: /static/fonts/pretendard/Pretendard-{Regular,Medium,SemiBold,Bold}.woff2 각 200, Brand New Hyosung·외부 요청 0건.

### 테스트·회귀
| 절차 | 실제 | 판정 |
|---|---|---|
| `-s tests/test_common` | 65 OK(Pretendard 단일 로컬 글꼴·모든 PDF 공통 경로·기능별 fonts 폴더 없음 테스트) | 통과 |
| `-s tests/test_home` / `test_market_analysis` | 94 / 71 OK | 통과 |
| `-s features/green_claim/tests` | 첫 실행 1 실패(/Helvetica) → 기대값 수정 후 178 OK | 통과 |
| 5개 탭 × 1440/1024/390 | 15/15, 가로 스크롤·JS 예외 0, 캡처 육안 줄바꿈 이상 없음 | 통과 |
| 공통 상호작용 / 키보드·초점 / 로딩·오류 UX / 로고 | 26/26 / 41/41 / 36/36 / 15/15 | 통과 |
외부 호출 0건.

### 미검증
실제 외부 데이터(긴 뉴스 제목·실제 AI 분석 표)로 만든 PDF의 줄바꿈, macOS·모바일 렌더링, PDF 뷰어별(Acrobat·브라우저) 표시.

## 2026-10-26 Home 주요 카드 강조 (DEV-HOME-021)
| 절차 | 기대 | 실제 | 판정 |
|---|---|---|---|
| 1440 Home 계산 스타일 | 제목 4개 22px/700, 업계 소식·전시회 설명 문장 0개, 강조 카드 4개 | 바이어 시간·환율·업계 소식·다가오는 전시회 22px/700, 설명 0, 카드 4 | 통과 |
| 1440·390 캡처 육안 | 위 띠·포인트 막대 표시, 도시 선택과 제목 한 줄, 줄바꿈·넘침 없음 | 같음 | 통과 |
| 5개 탭 × 1440/1024/390(검증 서버, 외부 차단) | 가로 스크롤·JS 예외 없음 | 15/15 | 통과 |
| `-s tests/test_home` / `tests/test_common` | OK | 94 / 65 OK | 통과 |
외부 호출 0건.
