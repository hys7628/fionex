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
