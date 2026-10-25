# 출처

아래 항목을 실제 작업 후 추가하세요.

자료명 / 기관 / URL·파일 경로 / 조회일 / 적용 제품·범위 / 사용권

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

## BrasilAPI 공휴일
- 자료명: BrasilAPI Feriados Nacionais v1
- 기관: BrasilAPI(오픈소스 공개 API)
- URL: https://brasilapi.com.br/api/feriados/v1/{연도}
- 조회일: 2026-10-25 (2026·2027 응답 확인, 지원 범위 1900~2199는 404 응답 문구로 확인)
- 적용 범위: 홈 바이어 시간의 브라질 국가 공휴일(type "national")만. 주·시 공휴일, `?uf=` 미사용
- 사용권: 미확인(이용약관·호출 제한 확인 필요)

## Google News RSS 검색
- 자료명: Google News RSS 검색(비공식 피드)
- 기관: Google
- URL: https://news.google.com/rss/search?q={검색어}&hl=pt-BR&gl=BR&ceid=BR:pt-419
- 조회일: 2026-10-25 (HTTP 200, XML 구조·site: 연산자 동작 확인)
- 적용 범위: 홈 업계 소식 Google News·ABIT 경로의 기사 제목·매체명·날짜·링크. 본문 미수집
- 사용권: 미확인(비공식 피드, 이용약관·요청 제한 확인 필요). 기사 저작권은 각 매체

## ABIT (Google News RSS 경유)
- 자료명: ABIT 공식 사이트 게시물 및 ABIT 인용 보도
- 기관: Associação Brasileira da Indústria Têxtil e de Confecção (abit.org.br)
- URL: Google News RSS `site:abit.org.br when:30d`, `"ABIT" têxtil when:30d` (사이트 직접 접속·크롤링 안 함)
- 조회일: 2026-10-25
- 적용 범위: 홈 업계 소식 ABIT 경로. 제목·매체·날짜·링크만
- 사용권: 미확인

## KOTRA 해외시장뉴스 Open API
- 자료명: 대한무역투자진흥공사_해외시장뉴스
- 기관: KOTRA (공공데이터포털 https://www.data.go.kr/data/15034831/openapi.do)
- URL: https://apis.data.go.kr/B410001/kotra_overseasMarketNews/ovseaMrktNews/ovseaMrktNews
- 조회일: 2026-10-25 (포털 Swagger 명세 확인, 키 없음·잘못된 키 응답만 확인. 실제 뉴스 데이터 미확인)
- 적용 범위: 홈 업계 소식 KOTRA 경로. 제목·게시일·원문 링크·출처명만 표시, 내용요약·본문 미사용
- 사용권: 포털 표시 이용허락범위 "공공저작물: 출처표시, 상업적 이용금지, 변경금지(제4유형)". 개발계정 트래픽 10,000, 자동승인. 사내 업무 도구 사용이 상업적 이용에 해당하는지 미확인(팀 확인 필요)

## 한국수출입은행 현재환율 API
- 자료명: 현재환율 API(Open API)
- 기관: 한국수출입은행
- URL: 개발명세 https://www.koreaexim.go.kr/ir/HPHKIR020M01?apino=2&viewtype=C · 요청 https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON
- 조회일: 2026-10-25 (명세 확인, 인증 오류 응답만 실제 확인. 실제 환율 데이터 미확인)
- 적용 범위: 홈 환율 USD/KRW 매매기준율(DEAL_BAS_R)
- 사용권: 인증키 발급 필요, 일일 1000회. 이용약관 세부 미확인

## Banco Central do Brasil PTAX OData
- 자료명: PTAX — Cotação do Dólar por período (CotacaoDolarPeriodo)
- 기관: Banco Central do Brasil
- URL: https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/ (명세 $metadata, 문서 /documentacao), 데이터셋 https://dadosabertos.bcb.gov.br/dataset/dolar-americano-usd-todos-os-boletins-diarios
- 조회일: 2026-10-25 (실제 호출 성공)
- 적용 범위: 홈 환율 USD/BRL PTAX 매도(cotacaoVenda)
- 사용권: 데이터셋 페이지 표시 Open Data Commons Open Database License (ODbL). 인증키 불필요(실제 확인)
