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
