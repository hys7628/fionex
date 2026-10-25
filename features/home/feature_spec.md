# 홈
담당: ghddm
상태: 범위 확정, 상세 명세 초안. 구현 전 담당자가 미정 항목을 채웁니다.

## 목적/범위
브라질 바이어 시간, 원단/원사/섬유 최신 뉴스, 보고서 PDF 다운로드

## 입력·출력·데이터: 채울 항목
기준 도시·매체·갱신 주기·보고서 고정/동적 방식
지원 형식/용량, 필수/선택 필드, 실제 테스트 자료, 출력 항목을 확정하세요.

## 공통 조건
로그인·장기 저장·탭 간 자동 연동 없음. 탭 이동 시 상태 유지. 결과물 PDF 다운로드.
출처 없는 수치/인증/공급 조건을 AI로 채우지 않음. 제품 구분과 미확인 표시.

## 구현 전 작성
- 입력 필드/형식:
- 결과 형식/견본:
- 엔드포인트/요청/응답:
- 자료 출처/갱신:
- 오류·재시도:
- 완료 기준/검증 사례:

## 검증
현재 기능 미구현·실행 검증 미실시. 담당 worklogs에 실제 결과만 기록.

## 4. 환율 (추가 항목)
2026-10-25 작성. 현재 구현(features/home/fx.py, GET /api/home/fx, 홈 환율 카드) 기준. 회의 확정 범위 밖 추가 항목으로 팀 공유 필요.

### 목적
바이어와 단가·견적을 이야기하기 전에 USD/KRW, USD/BRL, BRL/KRW 흐름을 빠르게 확인한다.
USD를 중심 통화로 쓰는 것은 가정(실제 거래 통화 확인 전)이다. 환율 전망·해석·매매 추천·AI 사용 없음.

### 화면 표시
| 항목 | 표시 예(형식) | 비고 |
|---|---|---|
| USD/KRW | `1 USD = 1,405.20 KRW` (소수 2자리) | 한국수출입은행 매매기준율 |
| USD/BRL | `1 USD = 5.0377 BRL` (소수 4자리) | BCB PTAX 매도 |
| BRL/KRW | `1 BRL = 278.94 KRW` (소수 2자리) | **USD 경유 계산값 · 공식 고시 환율 아님** |
| 전일 대비 | `전일 대비 ▲ 상승 0.31% (직전 고시일 2026-10-22)` / `▼ 하락` / `– 변동 없음` | 직전 고시값이 없으면 `전일 대비: 비교 데이터 없음` |
| 실제 고시일 | `2026-10-23 고시 · {출처명}` | "오늘 환율" 표현을 쓰지 않음 |
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
