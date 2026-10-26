# 홈
담당: 홍은주
상태: 구현 완료(2026-10-25). 아래 내용은 현재 코드(features/home/) 기준이며, 검증 근거는 docs/worklogs/hong_eunju/validation.md.

## 목적/범위
효성티앤씨 해외영업·마케팅 담당자가 Home 한 화면에서 브라질 바이어 연락 가능 시간, 원단·원사·섬유 최신 뉴스(포르투갈어 제목 AI 한 줄 요약 포함),
환율, 다가오는 브라질 섬유 전시회를 확인하고, 그 시점의 내용을 일일 브리핑 PDF로 내려받는다.
환율·전시회는 회의 확정 범위 밖 추가 항목이다(팀 공유 필요, docs/decisions.md 확인 필요).

## 공통 조건
로그인·장기 저장·탭 간 자동 연동 없음. 탭 이동 시 상태 유지. 결과물 PDF 다운로드.
출처 없는 수치/인증/공급 조건을 AI로 채우지 않음. 제품 구분과 미확인 표시.
- 화면 배치(2026-10-25 재배치): Home에서는 공통 머리글(홈 제목·설명·작업 상태 칩)을 home.css로 화면에서만 숨기고(h1은 화면낭독기·탭 전환 초점용으로 유지) `일일 브리핑` 바부터 시작 → 1행 바이어 시간(40%) · 환율(60%) → 2행 업계 소식(60%) · 다가오는 전시회(40%) → `출처 및 유의사항`(접기, 카드에 있던 긴 안내·출처 문장). 1100px 이상에서 같은 행 카드는 외곽 높이를 맞춤(grid stretch, 고정 높이 없음), 미만은 같은 순서로 세로 배치. 카드 패딩은 공통 `.card` 값(24px, 960px 미만 20px)으로 통일. 각 카드는 홈을 처음 열 때 한 번 요청하고, 탭을 다시 열 때는 다시 요청하지 않는다(DOM 유지).
- 카드마다 실패를 나눈다. 한 카드(또는 한 출처)가 실패해도 다른 카드는 그대로 동작한다.
- 외부 문자열(뉴스 제목·매체명·요약·전시회명)은 화면에서 textContent로만, PDF에서는 이스케이프해서 넣는다.
- 사용자 입력·결과를 서버 DB·디스크·브라우저 저장소에 저장하지 않는다. 서버 메모리 캐시는 공통 기준 자료(공휴일·뉴스·요약·환율)만 담는다.
- API 응답은 docs/data_contracts.md 형식(`{"ok": true, "data": …}` / `{"ok": false, "error": {code, message}}`), 경로는 `/api/home/…`.

### 환경변수 (값은 `.env`에만, 코드·로그·문서에 기록하지 않음)
| 이름 | 사용 위치 | 없을 때 |
|---|---|---|
| `OPENAI_API_KEY` · `OPENAI_MODEL` | 뉴스 AI 요약(common/ai_client.py) | 요약만 "AI 요약을 사용할 수 없습니다", 뉴스는 그대로 |
| `KOTRA_API_KEY` | 뉴스 KOTRA 경로 | KOTRA만 "설정 필요", Google·ABIT 정상 |
| `KOREAEXIM_API_KEY` | 환율 USD/KRW | USD/KRW만 "설정 필요", BRL/KRW 계산 안 함 |
`python app.py`(프로젝트 루트) 실행 시 Flask가 python-dotenv로 `.env`를 읽는다(OS 환경변수 우선). 테스트·검증 서버는 `FLASK_SKIP_DOTENV=1`로 실제 키를 쓰지 않는다.

### 테스트
`python -m unittest discover -s tests/test_home -v` (외부 요청 없음, 모의 응답). 파일: test_holidays_news(공휴일·뉴스 수집), test_news_summary(AI 요약), test_fx(환율), test_fairs(전시회), test_report(바이어 시간 서버 계산·PDF).

## 1. 바이어 시간
### 목적
지금 브라질 바이어에게 연락해도 되는지, 어렵다면 한국 시간으로 언제 다시 연락할 수 있는지 판단한다.

### 입력
기준 도시 선택(기본 상파울루). 값은 IANA 시간대: `America/Sao_Paulo`(상파울루) · `America/Fortaleza`(포르탈레자) · `America/Manaus`(마나우스) · `America/Rio_Branco`(히우브랑쿠).
선택은 보기 설정이라 작성 중 감지·이탈 경고에서 제외(`data-work-ignore`)하고, 페이지 메모리에만 유지한다.

### 화면 표시
Home 화면은 요약(2026-10-25): 기준 도시 선택(도시명 겸용) · 큰 현지 시각 · 작은 상태 글자 · 다음 공휴일만 보인다. 큰 상태 문구·배지는 쓰지 않는다.
- 현지 시각 `07:47`(크게, tabular-nums)의 색이 연락 가능 상태: 업무시간 초록, 업무시간 외·주말 주황, 공휴일 빨강. 판정 규칙은 그대로.
- 시각 아래 작은 글자(같은 색) `연락 가능` / `연락 어려움` + 현지 날짜 `10/25(일)`. 이유(업무시간·업무시간 외·주말·공휴일)는 화면낭독용 숨은 글로만 읽힌다(색만으로 전달하지 않음).
- 기준 도시 선택은 제목 줄 오른쪽에서 도시명을 겸한다(라벨 `기준 도시`·도시명 텍스트는 화면낭독용으로 유지). 카드 부제 없음.
- Home 화면에서 숨김(계산·DOM은 유지, 일일 브리핑 PDF에는 표시): 서울 현재 시각, 다음 연락 가능(다음 업무 시작) `10/26(월) 21:00 KST` + `현지 10/26(월) 09:00`(공휴일 자료를 확인하지 못한 날이 있으면 `· 공휴일 미반영`).
- 다음 공휴일(항상 표시, 2026-10-25): 기준 도시 **현지 날짜** 이후(오늘 포함) 가장 가까운 국가 공휴일 `11/2(월) Finados · D-8`, 오늘이면 `D-DAY`. 이름은 BrasilAPI `name` 원문(번역·AI 없음).
  올해 남은 공휴일이 없을 때만 다음 해 목록을 기존 `/api/home/holidays?year=`(연도 캐시)로 불러온다. 필요한 연도 자료를 확인하지 못하면 `다음 공휴일 확인 불가`(추측 없음). 기준 도시를 바꾸면 다시 계산.
  화면(home.js `nextHoliday`)과 PDF(buyer_time.py `next_holiday`·`next_holiday_text`)는 같은 규칙·같은 표기.
- 배치: 제목 | 기준 도시 선택 → 큰 현지 시각 옆 `연락 어려움 · 10/25(일)` 한 줄 → 다음 공휴일 한 줄. 1행(바이어 시간·환율) 카드만 위아래 여백을 줄임(16px, 좌우는 공통 값).
- 안내: 공휴일 자료 출처 줄은 Home 화면에 보이지 않는다(조회 실패·대체 자료 안내만 카드에 표시). 업무시간 가정값과 전체 문장 `기준: 현지 09:00~18:00 (가정, 확정되지 않은 업무시간) · 점심시간 미반영 · 브라질 국가 공휴일만 반영(주·시 공휴일 제외)`은 하단 `출처 및 유의사항`.

### 데이터 출처
- 시각: 브라우저 `Intl.DateTimeFormat`(timeZone 옵션). 고정 시차를 쓰지 않는다.
- 공휴일: BrasilAPI `GET https://brasilapi.com.br/api/feriados/v1/{연도}`, `type`이 `national`인 항목만. `?uf=`는 쓰지 않는다. User-Agent 지정(기본 urllib 값은 403).

### 작동 방식
- 상태 판정 순서: 국가 공휴일 → 토·일 → 현지 09:00 이상 18:00 미만 업무시간 → 업무시간 외(09:00·17:59 업무시간, 18:00 업무시간 외).
- 다음 업무 시작: 평일이고 국가 공휴일이 아닌 가장 가까운 날의 현지 09:00(오늘 09:00 전이면 오늘부터), 최대 31일 탐색, Intl로 시간대 변환.
- 화면은 분 경계마다 갱신하고 홈이 숨겨지면 멈춘다. 공휴일은 필요한 연도(오늘, 14일 뒤, 다음 업무일 탐색 연도)만 요청한다.
- PDF용 같은 규칙의 서버 계산: features/home/buyer_time.py(zoneinfo). PDF의 가까운 공휴일은 7일 이내.

### API
`GET /api/home/holidays?year=YYYY` (1900~2199, 아니면 400 `invalid_year`)
→ `{"ok": true, "data": {"source": "brasilapi|fallback|none", "fetched_at": "ISO(KST)|null", "holidays": [{"date", "name"}]}}`

### 캐시
서버 메모리 연도별(BrasilAPI 성공 결과만). 브라우저 페이지 메모리 연도별, `none`이었던 연도는 홈을 다시 열 때 재요청.

### 오류 처리
BrasilAPI timeout 5초. 실패 시 대체 자료 `features/home/data/holidays_br_{연도}.json`(현재 파일 없음, 출처 검증된 자료만 추가) → 없으면 `none`.
`none`이면 공휴일 없이 주말·업무시간만 판단하고 `공휴일 정보 확인 불가: 공휴일 없이 주말·업무시간만 판단합니다.` 대체 자료 사용 시 `공휴일 정보: 대체 자료 사용`.

### AI 사용
없음.

### 검증 상태
- 확인함: BrasilAPI 실제 응답(2026·2027, Finados 2026-11-02), 서버 19건(캐시·대체 자료·형식 오류·timeout 5초), 브라우저 29건(사례: 서울 10/26 10:00 → 상파울루 주말·다음 21:00 KST, 마나우스 22:00 KST, 히우브랑쿠 23:00 KST, 경계 09:00/17:59/18:00/08:00, 11/2 공휴일, 12/31 → 1/4, 분 경계 갱신, 공휴일 조회 실패), 서버 계산(buyer_time)도 같은 사례 통과, 통합 검증(도시 변경 후 마나우스 = 상파울루 - 1시간).
- 미검증: 실제 사용자 브라우저·기기·화면낭독기, 실제 BrasilAPI 장애(모의만), 실제 대체 공휴일 자료.

### 완료 기준
위 사례가 화면·서버 계산 모두 같은 결과, 공휴일 조회 실패 시에도 시계·주말 판정 유지, 업무시간 09~18시가 가정값으로 표시.

## 2. 최신 뉴스 (원단·원사·섬유)
### 목적
브라질 섬유 업계의 최신 소식을 원문 제목·매체·날짜·원문 링크로 빠르게 훑는다. 포르투갈어 제목은 한국어 한 줄 AI 요약을 곁들인다.

### 입력
없음(자동 수집). 실패한 수집 경로별 재시도 버튼.

### 화면 표시
- 매체 필터 탭 `[전체 N] [KOTRA n] [Google News n] [ABIT n]`(`<button aria-pressed>`, 회색 기본·선택만 포인트 색, 건수는 화면 목록 기준). 이미 받은 목록을 화면에서만 거른다(추가 요청 없음). 실패·설정 필요 경로는 탭에 `⚠`(+화면낭독용 문구).
- `수집 현황`(접기): 수집 경로별 상태 배지 `KOTRA`·`Google News`·`ABIT` + `정상`/`실패`/`설정 필요`, 갱신 시각과 `수집 N · 필터 후 M · 표시 K`(수집 기록이 없으면 `수집 기록 없음`).
- 실패 안내(notice)와 `○○ 다시 시도` 버튼(재시도 가능한 오류만), 이전 수집분이 있으면 `… 수집분을 계속 표시합니다.`
- 목록(최신순, 카드 안 스크롤 없음): Home 요약으로 기본 4건, 뉴스가 있으면 `업계 소식 더 보기 (전체 N건 · 검색)`으로 같은 탭 안의 상세 화면을 연다(아래 (4-2)). 굵은 원문 제목 링크(밑줄은 hover·focus 때만, 새 탭, `rel="noopener noreferrer"`), 회색 `AI 요약` 라벨 + 한국어 한 줄(있을 때만), 회색 수집 경로 라벨, 매체명, 날짜(시각 있으면 KST, KOTRA는 날짜만), 언어.
- 카드 하단 한 줄 `출처: KOTRA 해외시장뉴스 · Google News · ABIT …`, 긴 안내(최신 20건·갱신 주기·AI 요약·링크 경유·KOTRA 출처)는 `출처 및 유의사항`.
- 모든 경로 실패 시 빈 상태 `모든 수집 경로에서 뉴스를 불러오지 못했습니다…`.

### 데이터 출처
| 경로 | 방식 |
|---|---|
| KOTRA | 해외시장뉴스 Open API(공공데이터포털 15034831) `apis.data.go.kr/B410001/kotra_overseasMarketNews/ovseaMrktNews/ovseaMrktNews`, `search1=브라질`, 최근 180일, 100건, 제목·키워드·산업분류·품목명에 섬유 낱말(섬유·원사·원단·의류·화섬·폴리에스터·직물)이 있는 항목. 제목·날짜·링크·출처명만 표시(이용 조건: 출처표시·상업적 이용금지·변경금지 제4유형, 사내 사용 적합성 팀 확인 필요) |
| Google News | RSS `news.google.com/rss/search?q=…&hl=pt-BR&gl=BR&ceid=BR:pt-419`, 검색어 `("fio de poliéster" OR "fios têxteis" OR "indústria têxtil" OR "reciclagem têxtil") when:7d` |
| ABIT | 사이트 크롤링 없이 Google News RSS 두 검색 `site:abit.org.br when:30d` + `"ABIT" têxtil when:30d`(초안의 OR 묶음은 abit.org.br 결과만 돌아와 분리) |

### 작동 방식
- 세 경로를 병렬로 가져오고(요청 timeout 10초, 응답 2MB 상한) 경로별 최신 20건.
- 정규화 `{id, title, url, media, media_domain, published_at, origin, lang}`(media_domain: RSS `<source url>` 또는 KOTRA 링크의 호스트, `www.` 제거). Google 제목 끝 ` - 매체명` 제거. 날짜·링크(http/https)가 없거나 날짜를 해석할 수 없으면 제외. RSS description은 제목·매체명 반복이라 쓰지 않는다(`snippet` 없음).
- 관련성 필터(Google News·ABIT, 상수는 service.py 상단): 매체 도메인은 news.google.com 링크가 아니라 RSS `<source url>`로 판단. `.pt` 도메인과 `EXCLUDED_MEDIA_DOMAINS`(portugaltextil.com·vietnam.vn, 2026-10-25 실제 RSS 근거)는 제외, `abit.org.br`는 키워드 검사 면제, 그 밖은 제목에 섬유 낱말(`TEXTILE_NEWS_KEYWORDS`, 악센트·대소문자 무시, 낱말 단위) 또는 구문(`indústria da moda` 등, `moda` 단독 제외)이 있어야 통과. KOTRA는 기존 섬유 낱말 필터. Google 검색어는 좁힌 후보가 일반 노이즈를 줄이지 못해 바꾸지 않음.
- 건수: `collected`(응답에서 읽은 건수, 경로 안 중복 제외, KOTRA는 API 응답 건수) → `after_filter` → `count`(표시, 최대 20). 로그에 `collected=… filtered=… shown=…` 집계만 남겨 KOTRA 0건이 응답 0건/필터 후 0건인지 구분한다.
- 주제 태그: 정규화 후 각 항목에 `tags`(1~2개)를 붙인다. 아래 `(4-1)` 참고.
- 중복 제거: 같은 URL 또는 공백·대소문자를 정리한 같은 제목이면 하나만(abit → kotra → google 순으로 남김, 버린 항목의 URL·제목도 기억). 최신순 정렬.

### API
- `GET /api/home/news?refresh=kotra|google|abit` (잘못된 값 400 `invalid_refresh`)
  → `{"items": [{…, "tags": ["원사", "리사이클·ESG"]}], "media": {경로: {"status": "ok|error|not_configured", "fetched_at", "collected", "after_filter", "count", "stale", "error"?: {"code","message","retryable"}}}, "summary": {"pending": n}}`
  항목의 `summary_ko`는 이미 만든 요약이 있을 때만 붙는다.
- `GET /api/home/news/search?q=검색어` → (4-2) 참고
- `POST /api/home/news/summaries` → `{"status": "ok|unavailable|error", "message"?, "summaries": {id: 요약}}` (서버에 수집된 뉴스만 대상, 클라이언트 문장을 받지 않음)

### (4-1) 뉴스 주제 태그
**초안(2026-10-25)**: 요청에 명시된 (4-1) 키워드 표가 이 문서에 없어, 관련성 필터 낱말과 필수 검증 사례로 정한 초안이다. 확정 표가 오면 service.py `NEWS_TOPIC_KEYWORDS`만 바꾼다.
- 코드 기반 분류(AI 없음). 입력은 수집된 **제목만**(RSS description은 제목 반복이라 발췌 없음, AI 요약은 쓰지 않음).
- 판정용 정규화: 소문자 + 악센트 제거(`têxtil` → `textil`, 화면 제목은 그대로). 라틴 키워드는 낱말 단위(`fio`는 `desafio`에 맞지 않음), 두 낱말 이상은 구절 단위, 한국어(KOTRA 제목)는 글자 포함 여부.
- 표 순서가 우선순위, 기사당 최대 2개, 하나도 없으면 `기타`. 관련성 필터(포함/제외)와는 목적이 달라 키워드를 따로 둔다(필터 결과 불변).

| 순서 | 태그 | 키워드(초안) |
|---|---|---|
| 1 | 원사 | fio, fios, fiação, filamento(s), fibra(s), poliéster, polyester, poliamida, nylon, elastano, viscose, algodão · 원사, 화섬, 폴리에스터, 면화 |
| 2 | 원단 | tecido(s), malha(s), malharia, tecelagem, tinturaria, estamparia, denim · 원단, 직물, 편직 |
| 3 | 규제·무역 | exportação/exportações, importação/importações, cota(s), tarifa(s), imposto(s), tributária/tributário, antidumping, dumping, regulamenta, regulamentação, mercosul, acordo comercial, comércio exterior · 수출, 수입, 관세, 무역, 규제, 통관, 협정 |
| 4 | 리사이클·ESG | reciclagem, reciclado(s)/reciclada(s), sustentabilidade, sustentável/sustentáveis, esg, circular, economia circular, resíduos, carbono, emissões, rastreabilidade · 재활용, 리사이클, 친환경, 지속가능, 탄소 |
| 5 | 패션·리테일 | moda, varejo, vestuário, confecção/confecções, coleção, roupa(s), desfile, fashion, loja(s) · 패션, 의류, 소매, 유통, 브랜드 |
| 6 | 기타 | 위 키워드가 하나도 없을 때 |

- 화면: 기사마다 회색 주제 라벨(매체 라벨과 같은 계층), 매체 필터와 별도의 주제 필터 `[전체] [원사] [원단] [규제·무역] [리사이클·ESG] [패션·리테일] [기타]`(`aria-pressed`, 건수 표시). 두 필터는 함께 적용(둘 다 맞는 기사만), 이미 받은 목록을 화면에서만 거른다(추가 요청 없음). 맞는 기사가 없으면 `선택한 조건에 해당하는 뉴스가 없습니다.`
- PDF: 매체·날짜 줄 끝에 ` · 원사 · 리사이클·ESG`.

### (4-2) 업계 소식 상세·검색 (2026-10-26)
- 위치: Home 탭 안의 두 번째 화면(새 사이드바 메뉴·주소·공통 코드 변경 없음). 카드의 `업계 소식 더 보기`로 열면 Home 화면을 숨기고 상세 화면을 보이며 제목으로 초점, `← 홈으로`로 돌아오면 `더 보기` 버튼으로 초점. 페이지 이동·새로고침 없음(브라우저 뒤로 가기와는 연결하지 않음).
- 화면: 제목 `업계 소식` + 한 줄 설명, 검색 입력(라벨 `뉴스 검색`, placeholder `섬유, 폴리에스터, 재활용 원사, 수출 규제 등`, 최대 80자) + `검색` 버튼(넓으면 한 줄, 좁으면 줄바꿈), 매체·주제 필터(카드와 같은 탭·분류), `전체 N건` / `검색 결과 N건`, 기사 목록(카드와 같은 기사 표시).
- 기본 목록: 서버가 가진 현재 수집 뉴스 전체(경로별 최대 20건, 중복 제거 후 현재 34건). 새 페이지네이션·API 없음.
- 내부 검색(먼저): 받은 뉴스에서만, 입력하는 즉시. 대상은 제목·매체명·매체 도메인·주제 태그·수집 경로 이름(AI 요약 제외 — 생성된 번역문으로 범위가 바뀌지 않게). 앞뒤 공백·따옴표 정리, 대소문자·악센트 무시(`textil` = `têxtil`), 여러 낱말은 모두 포함(AND). 외부 요청 없음.
- 결과가 없으면 `현재 수집된 뉴스에서 결과를 찾지 못했습니다.` + `Google News에서 검색` 버튼. **버튼을 눌렀을 때만** `GET /api/home/news/search?q=`를 부른다(입력·제출만으로는 요청 없음, 같은 검색어 결과가 있으면 다시 부르지 않음, 요청 중 버튼 disabled·`aria-busy`·`검색 중...`). 2자 미만이면 버튼 비활성 + `Google News 검색은 두 글자 이상 입력하세요.` 검색이 끝나면(상세 화면이 열려 있고 초점이 검색 영역에 있거나 사라졌을 때만) 성공 시 결과 건수 문장, 실패 시 `Google News에서 다시 검색` 버튼으로 초점을 옮긴다(2026-10-26 DEV-COMMON-005, 버튼이 비활성·숨김이 되며 초점이 사라지던 문제).
- Google News 검색(서버 service.search_news): 기존 Google News RSS 주소(`hl=pt-BR&gl=BR&ceid=BR:pt-419`)에 `"검색어" (têxtil OR tecido OR fio OR confecção OR vestuário) when:90d`로 찾는다(`NEWS_SEARCH_CONTEXT`·`NEWS_SEARCH_WINDOW`). 결과에는 수집 뉴스와 같은 규칙(날짜·링크 유효성, 중복 제거, `.pt`·제외 매체 도메인 제외, 섬유 낱말 관련성 필터, 주제 태그 1~2개)을 적용하고 최대 `NEWS_SEARCH_LIMIT`=20건. 검색어가 섬유 기사와 무관하면(예: `AI`만) 필터를 통과한 기사만 보이므로 0건일 수 있다.
- 검색 결과 표시: `Google News 검색 결과 N건`, 기사마다 작은 `Google News 검색` 라벨(옅은 민트, 상태색 아님). 매체·주제 필터도 함께 적용. **새 AI 요약 없음**(같은 기사 id·제목에 이미 만든 요약만 붙임).
- API: `GET /api/home/news/search?q=` (2~80자) → `{"query", "items": [/api/home/news 항목과 같은 구조, tags 포함], "count", "source": "google_news_rss", "collected", "after_filter"}`. 검색어 오류 400 `invalid_query`, Google News 실패 502 `search_failed`(`Google News 검색 결과를 가져오지 못했습니다.`).
- 실패: 화면에 위 문장 + `Google News에서 다시 검색`. 기존 수집 뉴스·카드는 그대로.
- 저장 없음: 검색어·결과는 페이지 메모리에만(서버 캐시·파일·DB·localStorage·sessionStorage·IndexedDB 없음). 검색 입력은 작성 중 감지에서 제외(`data-work-ignore`).
- 검증(2026-10-26): 모의 테스트(관련 3/5건·.pt·무관·중복·태그·상한·AI 미호출·캐시 요약 재사용·400/502·기존 뉴스 유지), 브라우저 1440·1024·390(46항목), 실제 Google News RSS 1회(`poliéster reciclado`: 원본 12건, .pt 2건, 제외 매체 3건, 관련성 통과 2건).
### 캐시
경로별 서버 메모리 1시간. 갱신 실패 시 이전 성공 수집분을 지우지 않고 `stale`로 표시. 실패는 캐시하지 않는다. `refresh`는 그 경로만 다시 가져온다.

### 오류 처리
오류 코드 `key_missing`(→ `not_configured`, 외부 요청 없음, 재시도 없음) · `access_denied`(HTTP 401/403) · `timeout` · `fetch_failed` · `invalid_response`. 로그에는 호스트·오류 종류만(인증키 포함 쿼리 미기록).

### AI 사용 — 포르투갈어 제목 한국어 한 줄 요약
- 대상: origin `google`·`abit`, `lang`이 `pt…`, 세 낱말 이상 제목. **KOTRA는 요약하지 않는다.** 입력은 id·제목만(본문 크롤링 없음).
- 호출: 공통 `common.ai_client.generate_structured`(Responses API 구조화 출력, store=False), 모델은 `OPENAI_MODEL` 환경변수(코드 고정 없음), 최대 40건씩 묶어 1회 요청.
- 프롬프트: features/home/prompts/news_summary_v3.md 사용(2026-10-25 PR 리뷰 반영). v1 규칙 + 용어 의미 범위 보존 규칙(전문 용어·소재명을 넓히거나 일반화하지 않음) + 가상 few-shot 정확히 4개(정상·수치 함정·정보 부족·용어 보존). v1(규칙만)·v2(규칙+few-shot)는 기록용으로 유지. **v3 실제 호출 실험은 미실행**(모의 테스트로 규칙·예시·예시 출력의 코드 검증 통과만 확인).
- 코드 검증: 요청한 id만, 같은 id가 다른 값으로 중복되면 폐기, 문자열·한 줄·80자 이하(자르지 않음)·한글 포함, 제목에 없는 숫자가 하나라도 있으면 폐기(쉼표·점 소수 구분은 같게 봄). 탈락·빈 값은 요약 없음.
- 캐시: (id, 제목) 기준 1시간(빈 값·탈락 포함). AI 오류는 캐시하지 않는다. 같은 기사를 다시 수집해도 재요약하지 않는다.
- 실패: 키 없음 → `unavailable`, API·JSON 오류 → `error`, 둘 다 원문 제목만 표시하고 안내 한 줄. 목록을 먼저 보여 준 뒤 요약을 따로 요청한다(목록 지연 없음).
- 화면: 검증을 통과한 항목에만 `AI 요약` 배지. 안내 `"AI 요약"은 … 제목만 보고 만든 한국어 한 줄로, 기사 본문을 보지 않았으므로 원문 확인이 필요합니다.`

### 검증 상태
- 확인함: Google News RSS·ABIT 검색 실제 응답 구조(2026-10-25), 서버 38건(실제 RSS)·모의 9건(test_holidays_news), 브라우저 20건, KOTRA 키 없음·잘못된 키(403) 실제 응답, KOTRA 실제 데이터 2건 정상 수집(1회, 계획에 없던 호출로 기록됨), AI 요약 실제 호출(v1·v2 각 1회, gpt-5.4-mini, 30건)·모의 18건·브라우저 18건, 통합 검증(정상·실패 모드).
- 미검증: KOTRA 응답의 다양한 실제 형식(게시일 형식·필터 결과), Google RSS 요청 제한·차단 조건, 앱 경로(POST summaries)의 실제 OpenAI 호출, 같은 입력 반복 실험, 요약 사실 정확성 체계 평가.
- 관련성 필터 확인(2026-10-25 저장한 실제 RSS): Google 53 → 필터 후 13(.pt·portugaltextil.com·vietnam.vn·무관 제목 제외), ABIT 53 → 45(표시 20). 모의 테스트: 필터·도메인·KOTRA A~E.
- 알려진 한계: 키워드 필터는 제목만 보므로 섬유 낱말 없는 관련 기사는 빠질 수 있음, 링크가 Google News 경유 주소, 서수 번역(예: terceiro trimestre → 3분기)은 숫자 검증에서 탈락(보수적).

### 완료 기준
세 경로 정상 시 최신순·중복 없는 목록, 한 경로 실패 시 나머지 유지·해당 경로만 재시도, 키 없음은 설정 필요, AI 요약 실패·키 없음에도 원문 목록 유지, KOTRA 요약 없음.

## 3. 일일 브리핑 PDF
### 목적
버튼을 누른 시점의 홈 데이터를 A4 문서 한 부(보통 1~2쪽)로 묶어 공유·보관한다. 고정 PDF가 아니라 요청 때마다 만드는 동적 PDF다.

### 입력
화면의 기준 도시(바이어 시간 선택값)만 전달. 별도 입력 없음.

### 화면 표시
Home 맨 위 `일일 브리핑` 바(첫 화면): 한 줄 안내 `바이어 시간·환율·뉴스·전시회를 PDF로 정리`(기준 도시는 화면낭독용 숨은 글), `일일 브리핑 PDF` 버튼(생성 중에는 버튼 문구가 `PDF 준비 중...`·회전 표시·비활성, 공통 `AppShell.ui.setButtonBusy`),
완료 `다운로드를 요청했습니다.`(버튼 옆, 4초 뒤 자동 숨김), 실패 notice(`role="alert"`, 서버 고정 문장 또는 `서버에 연결하지 못했습니다.`)는 다시 누를 때까지 유지.
`서버에 저장하지 않음`·A4 구성 안내는 `출처 및 유의사항`. 공통 머리글의 `다운로드 요청됨 · 저장 여부는 브라우저에서 확인` 칩은 공통 shell(app_shell.js) 표시이며, Home에서는 머리글과 함께 화면에서 숨겨진다(화면낭독기에는 role=status로 남음).

### PDF 구성(순서)
머리말(fionex 일일 브리핑, 생성 시각, 서울 시각, 선택 도시 시각) → 1. 바이어 시간(상태·다음 업무 시작·다음 공휴일 `11/2(월) Finados · D-8`(7일 이내 공휴일이 있으면 같은 줄에 `· 7일 이내: … — 회신 지연 가능/(주말)`)·가정값 안내) →
2. 환율(값·고시일·전일 대비·출처, BRL/KRW는 USD 경유 계산값) → 3. 최신 뉴스(최신순 상위 8건, KOTRA 필터 통과 기사가 있으면 최소 1건 포함(`NEWS_SOURCE_MINIMUM`, 없으면 채우지 않음, 중복·최대 건수 유지): 제목이 원문 링크, `[AI 요약]`(Google·ABIT, 있을 때만), 경로·매체(도메인)·날짜·주제 태그. 긴 URL 문자열은 쓰지 않음) →
4. 다가오는 전시회(3건, 화면 '전체'와 같은 브라질 최소 2건 정책: 행사·기간·D-day·국가 · 도시 · 장소·확인 상태·출처 링크) → 5. 출처 및 유의사항(출처별 조회 시각, 뉴스 경로별 `수집 N건 / 필터 후 M건 / 브리핑 선정 K건`, 가정값·계산값·AI 요약 안내, 확인 필요 전시회, 수집 실패·확인 불가 항목 목록). 쪽마다 생성 시각·쪽 번호 `n / N`(전체 쪽 수를 아는 사용자 정의 캔버스). BRL/KRW 고시일 칸은 두 고시일이 같으면 `2026-10-23 (두 환율 동일)`, 다르면 `KRW 10-23 / BRL 10-24`. 뉴스 8건 기준 A4 2쪽 이내.

### 데이터 출처
기존 service 함수와 캐시: get_holidays · get_fx · get_news · get_upcoming_fairs(3). PDF 요청당 각 1회, 캐시 우선(만료 영역만 각 정책대로 갱신). AI 요약은 이미 만든 것만 사용(PDF로 OpenAI를 부르지 않음).

### 작동 방식
features/home/report.py가 ReportLab 5.1.0으로 BytesIO에 생성(임시 파일 없음). 폰트 features/home/fonts/ Noto Sans KR Regular·Bold(SIL OFL 1.1, 출처·sha256은 fonts/README.md).
화면은 fetch → Blob → `AppShell.work.downloadBlob`(새 Blob URL, `<a download>` 클릭, 60초 뒤 revoke, `markDownloadRequested`)으로 내려받는다. 버튼은 생성 중 disabled·aria-busy.

### API
`GET /api/home/report/daily.pdf?city=America/Sao_Paulo|America/Fortaleza|America/Manaus|America/Rio_Branco` (기본 상파울루)
- 성공: `application/pdf`, `Content-Disposition: attachment; filename="fionex_daily_briefing_YYYYMMDD_HHMM.pdf"`(서울 시각), `Cache-Control: no-store`.
- 실패: 400 `invalid_city`, PDF 생성 자체 실패 500 `report_failed`. 영역별 수집 실패는 PDF 안에 표시.

### 캐시
PDF는 캐시·저장하지 않는다. 데이터는 각 기능 캐시를 따른다.

### 오류 처리
영역별 독립: 환율 실패 `확인 불가`, 뉴스 실패 `뉴스를 불러오지 못했습니다`, 전시회 자료 오류 `일정 확인 불가`, 출처 단위 실패(예: USD/KRW·KOTRA 키 없음)는 사유와 함께 실패 목록. 값을 채워 넣지 않는다.

### AI 사용
PDF 생성에는 없음(캐시된 뉴스 요약 표시만).

### 검증 상태
- 확인함: 서버 9건(test_report: 바이어 시간 사례, 부분 실패, 파일명·디스크 무저장, 라우트 200/400/500), PDF 열어 확인(PyMuPDF: 쪽 수 1~2, Noto Sans KR 임베드, 한글·포르투갈어 악센트·▲▼·`<>&` 정상, 링크 21~38개, 깨진 글자 0, 긴 제목 줄바꿈·표 겹침 없음), 브라우저 16건(연타 1회 요청, Blob 다운로드, 도시 전달, 오류·재시도), 통합 검증 반복 다운로드(아래).
- 반복 다운로드: 같은 페이지에서 두 번 받으면 두 응답 모두 200·새 Blob·Chrome `downloadWillBegin`→`completed`가 확인됐다. 이전에 두 번째 파일이 "없던" 것은 파일명이 분 단위라 같은 분에 같은 이름이 되고 헤드리스 검증 환경(`allow`)이 덮어쓴 것으로, GUID 저장(`allowAndName`)에서는 두 파일 모두 저장됐다(2026-10-25 통합 검증).
- 리뷰 반영 확인(2026-10-25): test_report PDF 5건(pypdf: 뉴스 링크 8개·본문 URL 없음·`n / N`·고시일 칸·경로별 건수·KOTRA 최소 포함), PyMuPDF로 PDF 4종(fixture, 고시일 다름, 저장한 실제 RSS, 부분 실패) 열어 확인: 모두 2쪽, `1 / 2`·`2 / 2`, 본문 URL 0, .pt 매체 0, Tecnotêxtil 2027-04-27 ~ 2027-04-30.
- 미검증: 실제 사용자 Chrome·Edge·Safari·모바일에서 같은 분 두 번 저장 시 파일명 처리(보통 `(1)`이 붙는지), 실제 AI 요약이 들어간 실데이터 PDF, 흑백 인쇄, Adobe Reader 등 다른 뷰어, 화면낭독기.

### 완료 기준
버튼 1회 → PDF 1개, 6개 구획이 순서대로, 한글·포르투갈어 정상, 일부 데이터 실패에도 PDF 생성, 서버·프로젝트 폴더에 PDF가 남지 않음.

## 4. 환율 (추가 항목)
2026-10-25 작성. 현재 구현(features/home/fx.py, GET /api/home/fx, 홈 환율 카드) 기준. 회의 확정 범위 밖 추가 항목으로 팀 공유 필요.

### 목적
바이어와 단가·견적을 이야기하기 전에 USD/KRW, USD/BRL, BRL/KRW 흐름을 빠르게 확인한다.
USD를 중심 통화로 쓰는 것은 가정(실제 거래 통화 확인 전)이다. 환율 전망·해석·매매 추천·AI 사용 없음.

### 화면 표시
Home 화면은 부제 없는 환율 띠(얇은 구분선, 회색 상자 없음): 통화쌍 → 큰 숫자 `tabular-nums`(줄바꿈 없음) + 옆에 작은 단위 → 전일 대비(BRL/KRW는 `USD 경유`) → 가장 작은 회색 한 줄 `10/23 고시 · 한국수출입은행` / `BCB PTAX`(BRL/KRW는 `10/23 고시`). 전체 고시일·출처명·직전 고시일은 타일 title, 매매기준율·PTAX 매도·공식 고시 아님·계산식은 `출처 및 유의사항`. 1100px 이상 한 줄 3개, 600px 미만 2+1. 아래 표는 값 형식이다.
| 항목 | 표시 예(형식) | 비고 |
|---|---|---|
| USD/KRW | `1,405.20 KRW` (소수 2자리, 단위는 작게) | 한국수출입은행 매매기준율 |
| USD/BRL | `5.0377 BRL` (소수 4자리) | BCB PTAX 매도 |
| BRL/KRW | `278.94 KRW` (소수 2자리), 라벨 `USD 경유 계산값`, 출처 자리 `USD/KRW ÷ USD/BRL` | **USD 경유 계산값 · 공식 고시 환율 아님** |
| 전일 대비 | `▲ 상승 0.31%` / `▼ 하락` / `– 변동 없음`, 기준 직전 고시일은 고시일 옆 작은 글씨 `(직전 10-22)`(해가 다르면 전체 날짜) | 직전 고시값이 없으면 `전일 대비: 비교 데이터 없음` |
| 실제 고시일 | `2026-10-23 고시`, BRL/KRW는 `2026-10-23 고시 (두 환율 동일)`(괄호는 작은 글씨) 또는 `KRW … · BRL … 고시` | "오늘 환율" 표현을 쓰지 않음 |
| 출처 | 한국수출입은행 매매기준율 / Banco Central do Brasil PTAX 매도 | BRL/KRW는 두 값의 고시일을 함께 표시 |
표시 예의 숫자는 형식 설명용이며 코드 기본값이 아니다. API가 돌려준 값만 표시한다. 값이 없으면 `확인 불가`(BRL/KRW는 `계산 불가`).

### USD/KRW (한국수출입은행)
- 출처: 한국수출입은행 현재환율 API. 요청 `GET https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey={키}&searchdate=YYYYMMDD&data=AP01`
- 환경변수: `KOREAEXIM_API_KEY` (확정 2026-10-25, 값은 `.env`에만)
- 사용 필드: `cur_unit`(통화코드, `USD` 항목) · `deal_bas_r`(매매 기준율, 쉼표 제거 후 사용). `result` 1 성공 / 2 → `invalid_response` / 3 → `access_denied` / 4 → `rate_limited`.
- 비영업일: 서울 기준 오늘부터 하루씩 최대 7일(오늘 포함) 거슬러 최근 고시값을 찾는다. 직전 고시값은 최근 고시일 전날부터 최대 7일. 빈 목록·null은 고시 없음으로 본다(명세: 비영업일·영업일 11시 이전 요청 시 null).
- 키 없음: `not_configured`(오류 코드 `key_missing`), 외부 요청 없음, 화면 `USD/KRW 설정 필요`(재시도 버튼 없음).
- 오류: `access_denied`·`rate_limited`는 재시도 버튼 없음. `timeout`·`fetch_failed`·`invalid_response`·`no_recent_rate`는 재시도 가능. 요청 timeout 10초, 로그에는 호스트·오류 코드만(인증키 포함 쿼리 미기록).
- **실제 인증키 기반 USD/KRW 응답은 미검증**(키 미발급).

### USD/BRL (BCB PTAX)
- 출처: Banco Central do Brasil PTAX OData `CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)`, 날짜 `'MM-DD-YYYY'`, `$format=json`. 인증키 없음.
- 사용 필드: `cotacaoVenda`(Cotação de venda, PTAX 매도) · `dataHoraCotacao`(날짜). 같은 날짜가 여러 건이면 가장 늦은 시각 값.
- 브라질리아(America/Sao_Paulo) 기준 오늘까지 14일을 1회 조회해, 최근 7일 안의 마지막 고시값과 그 이전 7일 안의 직전 고시값을 쓴다.
- 실제 호출 확인(2026-10-25, 일요일): 최근 고시 2026-10-23 5.0377, 직전 2026-10-22 5.0383, 전일 대비 -0.01%(원본 값으로 계산 -0.0119%). 원본 API 응답과 일치.

### BRL/KRW 계산
`BRL/KRW = USD/KRW ÷ USD/BRL` (Decimal 계산, 응답은 소수 4자리 반올림, 화면 2자리).
두 값이 모두 `ok`일 때만 계산하고, 하나라도 없으면 `brl_krw: null`·화면 `계산 불가`. 이전 값·추정값으로 채우지 않는다. AI 사용 없음.

### 전일 대비
`((현재값 - 직전값) / 직전값) × 100`, 소수 둘째 자리 반올림. 직전 고시값을 확보한 경우에만 계산한다.

### 캐시 (서버 메모리)
- 소스별 결과: 정상 1시간, 실패·설정 필요 5분.
- 한국수출입은행 지난 날짜 응답: 날짜별 보관(고시 후 바뀌지 않는 값, 60일 지난 항목 정리). 오늘 날짜는 11시 전후 갱신이라 보관하지 않는다.
- `?refresh=usd_krw|usd_brl`은 그 소스만 캐시를 무시하고 다시 조회(화면 재시도 버튼). DB·디스크 저장 없음.

### 오류 처리
소스별로 독립 처리한다. 실패한 소스는 이전 값을 보여 주지 않고 `확인 불가`로 둔다.
- USD/KRW 실패: USD/BRL 유지, BRL/KRW 계산 불가.
- USD/BRL 실패: USD/KRW 유지, BRL/KRW 계산 불가.
- 둘 다 실패: 두 값 `확인 불가`, 소스별 안내·재시도. 서버 요청 자체 실패 시 카드에 `환율 불러오기 실패` + 전체 재시도.

### API
`GET /api/home/fx` (잘못된 `refresh` → 400 `invalid_refresh`)
```json
{"ok": true, "data": {
  "usd_krw": {"pair": "USD/KRW", "source": "koreaexim", "source_name": "한국수출입은행 매매기준율",
              "status": "ok|error|not_configured", "rate": 1405.2, "date": "YYYY-MM-DD",
              "previous": {"rate": 1400.9, "date": "YYYY-MM-DD"} | null, "change_pct": 0.31 | null,
              "fetched_at": "ISO(KST)", "error": {"code", "message", "retryable"}  /* 실패 시만 */},
  "usd_brl": {"pair": "USD/BRL", "source": "bcb_ptax", "source_name": "Banco Central do Brasil PTAX 매도", "status": "ok|error", ...},
  "brl_krw": {"rate": 278.9368, "derived": true, "method": "USD/KRW ÷ USD/BRL",
              "usd_krw_date": "YYYY-MM-DD", "usd_brl_date": "YYYY-MM-DD"} | null
}}
```
실패한 소스도 객체는 항상 내려주며 `rate`·`date`·`previous`·`change_pct`는 null이다. (숫자는 형식 예시)

### 검증 상태
확인함(2026-10-25, docs/worklogs/hong_eunju/validation.md DEV-HOME-005):
- BCB PTAX 실제 호출, 최근·직전 고시값, 일요일 → 금요일 고시일 처리, 원본 값 일치.
- 한국수출입은행: 키 없음 → `not_configured`(외부 요청 없음), 등록되지 않은 키 실제 호출 → `access_denied`(응답 `result: 3`).
- 모의 테스트(tests/test_home/test_fx.py): 쉼표 값 파싱, 주말 역조회, 7일 안 고시 없음, 직전값 없음, BRL/KRW 계산(1400 ÷ 5 = 280), 한쪽·양쪽 실패, 캐시·refresh, 인증 오류 시 키 미노출.
- 브라우저(headless Chrome): 정상·일부 실패·전체 실패·재시도 화면, 390/1024/1440px 가로 스크롤 없음(정상 화면 숫자는 응답 가로채기 가상 값).
- 통합 검증(2026-10-25, 외부 요청 없는 모의 서버): 정상 모드 세 값 표시, USD/KRW 실패 모드에서 USD/BRL 유지·BRL/KRW 계산 불가, 1440/1024/390px.
미확인:
- 실제 한국수출입은행 인증키 기반 USD/KRW 응답, 실제 `deal_bas_r` 쉼표 형식, 실제 11시 이전 응답, 실제 비영업일 역조회.
- 실제 사용자 브라우저·기기·화면낭독기.

### 완료 기준 / 검증 사례
- 일요일 접속: USD/BRL이 직전 영업일(금요일) 고시일과 함께 표시(실제 PTAX 확인).
- BCB 실제 응답과 화면 값 일치(5.0377, -0.01%).
- 수출입은행 키 없음: USD/KRW `설정 필요`, BRL/KRW `계산 불가`, USD/BRL 정상(실제 확인).
- 한쪽 실패: 다른 값 유지, BRL/KRW 미표시(모의·브라우저 확인).
- 390 / 1024 / 1440px 가로 스크롤 없음(브라우저 확인).
- 남은 완료 조건: 실제 키로 평일 USD/KRW 정상 표시와 BRL/KRW 계산 확인.

### 자료 출처
- 한국수출입은행 현재환율 API 개발명세: https://www.koreaexim.go.kr/ir/HPHKIR020M01?apino=2&viewtype=C (인증키 발급신청: 같은 페이지 `viewtype=O`)
- Banco Central do Brasil PTAX OData: https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/ (문서 /documentacao)

## 5. 브라질·중남미 섬유 전시회
### 목적
다가오는 브라질·중남미 섬유·의류 전시회 일정을 출처·확인 상태와 함께 보고 출장·바이어 미팅을 계획한다.

### 입력
없음. 자료는 담당자가 출처를 확인해 넣는 정적 JSON(자동 수집·AI 생성 없음).

### 화면 표시
카드 제목 `다가오는 전시회`. 지역 필터 `[전체] [브라질] [중남미]`(기본 전체, `aria-pressed`, 회색 기본·선택만 포인트 색, 건수 표시). 받은 목록을 화면에서만 거르고(추가 요청 없음) 필터마다 3건 표시.
- 전체: 날짜순이되 브라질 행사를 최소 2건(가정값 `MIN_BRAZIL_IN_ALL`, 있는 만큼만) 먼저 넣고 나머지를 날짜순으로 채운 뒤 날짜순 정렬. 브라질: region=brazil만. 중남미: region=latin_america(브라질 외)만. 해당 없으면 `선택한 지역의 예정 전시회가 없습니다.`
행사별 기본 표시: 큰 D-day(`D-93` / `D-DAY` / `진행 중`) | 행사명 · `페루 · Lima`(국가·도시) · `2026.11.05–11.08`(기간) · 한 줄에 `[확인 필요]`(미확인 행사만) `[상세 정보]`.
행사별 `상세 정보`(native `<details>`, 기본 접힘): 기간(전체 날짜), 장소(도시 · 장소), 분야, 확인 상태(`공식 사이트 확인` / `확인 필요`)와 확인일, 메모(있을 때), 출처 링크(새 탭, `rel="noopener noreferrer"`).
빈 값은 `미확인`. 예정 행사가 없으면 `확인된 예정 전시회가 없습니다`, 형식 오류 항목이 있으면 `일부 일정 제외` 안내, 자료 오류면 `일정 확인 불가` + 재시도. 카드 맨 아래 한 줄 `자료 확인일 … · 방문 전 출처에서 다시 확인하세요.`, 전체 안내는 `출처 및 유의사항`.

### 데이터 출처
features/home/data/br_textile_fairs.json(자료 확인일 2026-10-25, 출처 URL·문구는 docs/worklogs/hong_eunju/sources.md).
| 행사 | 기간 | 국가 · 도시 · 장소 | verified |
|---|---|---|---|
| Inspiramais | 2027-01-26 ~ 2027-01-27 | 브라질 · Porto Alegre/RS · Centro de Eventos FIERGS | false(공식 사이트 페이지 간 연도 표기 불일치) |
| Tecnotêxtil Brasil 2027 | 2027-04-27 ~ 2027-04-30 | 브라질 · Americana/SP · Fidam | true |
| Febratex Summit 2027 | 2027-08-24 ~ 2027-08-26 | 브라질 · Blumenau/SC · Parque Vila Germânica | true |
| Expotextil Perú 2026 | 2026-11-05 ~ 2026-11-08 | 페루 · Lima · Centro de Exposiciones Jockey | false(EventsEye 목록 기준, 공식 사이트 미확인) |
| Colombiatex de las Américas 2027 | 2027-01-19 ~ 2027-01-21 | 콜롬비아 · Medellín · 장소 미확인 | false(ICE 이탈리아 국가관 안내 기준) |
| Createx 2027 | 2027-05-25 ~ 2027-05-27 | 콜롬비아 · Bogotá · Corferias | false(EventsEye 목록 기준, 공식 사이트 미확인) |
표의 기간은 JSON의 start·end와 같은 전체 날짜로 쓴다(test_fairs가 대조). Tecnotêxtil Brasil 2027은 2026-10-25 공식 사이트 재확인("de 27 a 30 de abril de 2027").
제외: Inspiramais 2027-08(사이트 머리글 표기와 충돌), Febratex 본 박람회 2028(공식 문구가 지난 행사 문구와 섞여 신뢰 불가), Colombiamoda 2027(7월, 날짜 미확정), IM Intermoda 2027(일정 미확인). 날짜를 추정해 넣지 않는다.
필드: 필수 `name`·`start`·`end`(YYYY-MM-DD)·`url`(http/https)·`source`·`verified`(bool)·`checked_at`·`country`(표시용 국가명)·`region`(`brazil` | `latin_america`), 선택 `city`·`venue`·`focus`·`note`(없으면 null). 필수 값이 없거나 region이 둘 중 하나가 아니면 그 항목은 제외(건수만 안내). region은 화면 필터 구분값이라 브라질은 `brazil`, 브라질 외 중남미는 `latin_america`로 겹치지 않게 둔다. verified=true는 공식 사이트에서 일정·장소를 확인한 경우(목록 사이트 기준 행사는 false).

### 작동 방식
요청마다 파일을 읽는다(작은 파일, 수정 즉시 반영). 형식이 틀린 항목은 내보내지 않고 건수만 알린다. 서울 날짜 기준 `end ≥ 오늘`만, 시작일 순. D-day는 `시작일 - 오늘`(오늘 시작 D-DAY, 시작 후 종료 전 진행 중).

### API
`GET /api/home/fairs?limit=N` (기본 5, 20 초과는 20, 1 미만·정수 아님 400 `invalid_limit`)
→ `{"fairs": [{name, start, end, d_day, status: upcoming|today|ongoing, country, region, city, venue, focus, note, url, source, verified, checked_at}], "data_checked_at", "total_upcoming", "invalid_count"}`(날짜순).
자료 파일 없음·형식 오류 503 `fairs_unavailable`. 화면은 20건 요청 후 지역 필터·브라질 최소 노출을 화면에서 적용(현재 자료 6건). 일일 브리핑 PDF는 `get_upcoming(3, min_brazil=2)`로 화면 '전체'와 같은 정책.

### 캐시
없음(정적 파일, 요청마다 읽음).

### 오류 처리
자료 오류는 전시회 카드만 `일정 확인 불가`, 다른 카드 유지. 가짜 일정을 만들지 않는다.

### AI 사용
없음.

### 검증 상태
- 확인함: 공식 사이트 조회(2026-10-25), 서버 9건(필터·정렬·D-day 경계·limit·항목 오류 8종·파일 오류·라우트), 브라우저 18건(실제 자료 3건·배지·링크·빈 상태·오류 재시도·390/1024/1440px), 통합 검증.
- 미검증: 주최사 문의 등 추가 사실 확인, 실제 사용자 브라우저·화면낭독기.
- 운영: 일정은 수동 자료라 주기적 재확인 필요(Inspiramais 연도 확인 필요).

### 완료 기준
종료되지 않은 행사만 날짜순, D-day 코드 계산, 출처 없는 항목 미표시, 자료 오류 시 카드만 오류.

## 6. 다른 탭 바로가기 — 제외(2026-10-26)
Home에 다른 탭 바로가기 카드(시장 분석·제품소개서·그린 클레임 체크·홍보 스튜디오)를 두지 않는다. 공통 왼쪽 사이드바에 같은 탭 이동이 이미 있어 중복 navigation을 만들지 않고, Home은 핵심 정보에 집중한다.
2026-10-25에 한 번 구현했다가 2026-10-26 Home에서 그 영역(마크업·스타일)만 제거했다. 공통 사이드바·다른 탭의 주소(해시)는 바꾸지 않았다.
