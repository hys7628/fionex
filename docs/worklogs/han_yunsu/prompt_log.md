# 프롬프트 로그

유형 / 실험 ID / 날짜 / 기능 / 모델·설정 / 프롬프트 경로·버전 / 입력·근거 / 실제 출력 / 문제 / 변경 이유 / 제어 / 재검증 / 한계

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

## DEV-MA-20261025-01 시장 분석 요구사항 명세 확정 및 커밋 준비
- 유형: development_instruction
- 날짜/시간: 2026-10-25 17:01 (Asia/Seoul)
- 작업자: 한윤수 (feature_spec.md 담당자 및 작업 브랜치 기준, 대화에서 별도 확인하지 않음)
- 기능: market_analysis
- 모델/설정: Claude Code (claude-opus-5-5), VSCode 확장. 서비스 모델 호출 없음
- 프롬프트 경로·버전: 해당 없음 (서비스 프롬프트 변경 없음)
- 지시 원문:
  1. "feature_spec.md commit 해줘"
  2. "prompt_log.md에 먼저 작성해줘"
- 변경 대상: features/market_analysis/feature_spec.md (+103 / −7, 미커밋)
  - 상태를 "사용자 협의 반영 최종 요구사항 명세(2026-10-25)"로 변경
  - 사용자·대상 시장(브라질 수입)·대상 제품(폴리에스터 DTY, 리젠 T2T 탐색용) 범위 명시
  - 품목코드 후보(HS 5402.33, NCM 5402.33.10/20/90), 기간(기본 36개월·최대 120개월), 단위, 평균 수입단가 산식, 결측·이상치, 추세·공급국 규칙 작성
  - 공통 조건: 새로고침 시 상태 유지(기존 공통 문서와 다른 최신 결정으로 표시), A4 세로 PDF, 키 관리, 자료 이용 권한 확인
  - 입력 필드, 결과 화면 순서·AI 분석 표 양식, 엔드포인트 의미상 계약, ComexStat/KOTRA/KITA/일반 뉴스 연결 방식과 미정 사항 작성
- 이번 세션 수행 내용: git 상태·diff 조회, docs/git_rules.md·docs/recording_rules.md 확인, 커밋 제목 제안, 본 기록 작성
- 커밋 처리: docs/git_rules.md의 "커밋은 사람이 수행" 규칙에 따라 AI는 커밋하지 않고 제목만 제안함
  - 제안 제목: `docs: 시장 분석 기능 요구사항 명세 확정`
- 테스트 입력/근거 자료: 없음. 명세 안의 ComexStat·KOTRA 정보는 공식 문서 조사 단계이며 실제 API 호출은 미실행
- 실제 응답·검증: 코드 변경이 없어 실행 검증 대상 없음. API 연결, 계산, PDF 생성 모두 미실행
- 발견 문제: 명세 본문 작성 과정의 지시 원문과 대화는 이 세션에 없어 기록하지 못함. 담당자가 원문을 제공하면 정정 내역으로 추가
- 담당자 판단: 미확인 (검토 후 직접 커밋 예정)
- 남은 한계: 새로고침 유지 결정에 따른 README·docs/decisions.md·docs/design_system.md 갱신은 공통 담당자 조정 전이라 반영하지 않음. sources.md·validation.md는 이번에 갱신하지 않음

## DEV-MA-20261025-02 시장 분석 1단계 구현 (ComexStat 통계)
- 유형: development_instruction
- 날짜/시간: 2026-10-25 17:05~18:00 무렵 (Asia/Seoul, 대략)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis
- 모델/설정: Claude Code (claude-opus-5-5). 서비스 AI(OpenAI) 호출 없음
- 지시 원문: "지시 : 서비스 구현해줘. 참고 : 궁금한 점은 전부 물어봐" (feature_spec.md 전문 첨부)
- 질문·사용자 답변(요약):
  - 범위: 1단계 통계부터 / 새로고침 유지: 일단 공통 규칙대로 / PDF: 서버 생성 + 무료 한글 글꼴(3단계)
  - 실제 호출 허용: ComexStat, KOTRA, OpenAI 소량(1단계에서는 ComexStat만 실제 호출)
  - 기본 NCM: 미염색 54023310만 / 이상치: 중앙값 ½~2배 / 반올림: 기본 안 / 캐시: 서버 메모리
  - 코드 형식: NCM 8자리 + HS 6자리 / 코드 개수: 한 번에 하나 / 국가명: 한국어 + 원문 / 그래프: 직접 SVG
  - jasonenv 패키지 설치: 허용 (requirements.txt 기준 설치, 파일 변경 없음)
- 발견 문제와 대응:
  - ComexStat period가 "연도 범위 × 월 범위"로 해석되어 연도를 넘는 기간이 누락·빈 결과 → 전체 연도 요청 후 서버에서 자르기
  - 연속 호출 429 → 직렬 호출·최소 간격·제한 재시도·서버 메모리 캐시·이전 자료 대체
  - jasonenv에 Flask·openai 미설치(README 기록과 불일치) → 사용자 허용 후 requirements.txt 설치
  - 좁은 결과 칸에서 표 숫자가 두 줄로 꺾임(헤드리스 Chrome 캡처로 확인) → 단위를 열 제목으로, 숫자 칸 줄바꿈 금지
- 추가 지시 원문: "prompt_log.md 기록해줘" (본 항목의 필수 항목 보강 요청)
- 프롬프트 경로·버전: 해당 없음(서비스 프롬프트 미작성, AI 분석은 2단계)
- 변경 파일: features/market_analysis/(comexstat_client.py 신규, service.py, routes.py, __init__.py, data/countries.json 신규, templates/.../panel.html, static/*.js·*.css, feature_spec.md), tests/test_market_analysis/(test_market_analysis.py 신규, README.md)
- 테스트 입력/근거 자료(모두 공개 통계, 사용자 자료 없음):
  - ComexStat 실호출: NCM 54023310, 2023-10~2026-09, 비교 공급국 한국(190)·중국(160) / NCM 54023310, 2025-01~12 / HS 540233, 2025-01~12 / 없는 코드 NCM 54029999
  - 대조 기준: ComexStat 2025-01~12 연간 합계 별도 요청(monthDetail=false, 상세 없음)
  - 모의 테스트: tests/test_market_analysis/test_market_analysis.py의 가상 값
- 실제 응답 발췌(관측값):
  - 2023-10~2026-09: FOB USD 925,142,540 / 797,257,802kg / 1.16 USD/kg, 36개월 모두 기록, 중국 1위(83.3%), 한국 16위(USD 39,600 / 14,400kg)
  - 2025년: 서비스 FOB 284,180,855 / 260,287,123kg = ComexStat 연간 합계 응답 값과 동일
  - HS 540233 2025년: FOB 329,820,536 / 294,821,881kg
  - 54029999: HTTP 400, code 입력란에 "현행 코드표에서 … 찾지 못했습니다"
  - ComexStat 2022-10~2026-09 요청: HTTP 200 빈 목록 / 2024-01~2026-09 요청: 매년 1~9월만 반환
- 변경 이유와 제어 방법:
  - 기간 누락 → 전체 연도(YYYY-01~YYYY-12)로 요청하고 서버에서 월 자르기. 테스트로 요청 본문 고정
  - 429 → 호출 직렬화(lock), 최소 10초 간격, 429·5xx·연결 실패만 15초·30초 후 최대 2회 재시도, 같은 날 메모리 캐시, 실패 시 이전 자료(stale) 표시
  - 수치 신뢰성 → 모든 수치는 코드 계산, 가중 평균단가, 기록 없는 월을 0으로 채우지 않음, 없는 코드와 결과 없음 구분
  - 표 가독성 → 단위를 열 제목으로 옮기고 숫자 칸 줄바꿈 금지
- 재실행 결과: 수정 후 모의 테스트 35개 통과, 공통 테스트 32개 통과, 헤드리스 Chrome 재캡처에서 숫자 한 줄 표시·콘솔 오류 없음 확인. 상세는 validation.md 2026-10-25 항목
- 담당자 판단: 미확인 (검토 후 직접 커밋 예정)
- 남은 한계: KOTRA·KITA·뉴스·AI·PDF 미구현, 공통 문서(README·data_contracts) 미갱신, 한국어 국가명 97개 사람 검토 필요, ComexStat country 항목 의미(원산국/선적국) 미확인, 공식 호출 한도 미확인

## DEV-MA-20261025-03 requirements.txt 설치 (develop 병합 후)
- 유형: development_instruction
- 날짜/시간: 2026-10-25 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (develop 병합 커밋 b7e718f 이후)
- 모델/설정: Claude Code (claude-opus-5-5). 서비스 AI 호출 없음
- 프롬프트 경로·버전: 해당 없음
- 지시 원문: "requirements.txt 실행해줘. 실행 후 prompt_log.md 기록해줘."
- 실행: Conda jasonenv(Python 3.11.17)에서 `python -m pip install -r requirements.txt`
- 실제 결과:
  - 새로 설치: pypdf 6.21.2 (develop 병합으로 requirements.txt에 추가된 공통 PDF 입력 검사용 패키지, 유정현 담당 공통 작업)
  - 이미 설치되어 있음: Flask 3.1.2, openai 3.37.0, pydantic 2.14.1, httpx2 2.16.0 (DEV-MA-20261025-02에서 설치)
- 확인:
  - 공통 테스트 `python -m unittest discover -s tests/test_common`: 56개 통과
  - 시장 분석 테스트 `python -m unittest discover -s tests/test_market_analysis`: 35개 통과
  - `import app` 성공
- 발견 문제: 없음. 기록 위치는 사용자 확인(한윤수 기록)으로 결정. 다른 조원 기록은 수정하지 않음
- 담당자 판단: 미확인
- 남은 한계: 앱 서버 실행·화면 확인과 실제 외부 API 호출은 이번에 하지 않음. requirements.txt 파일은 변경하지 않음

## DEV-MA-20261025-04 시장 분석 2~3단계 구현 (뉴스 수집·AI 분석·PDF)
- 유형: development_instruction
- 날짜/시간: 2026-10-25 저녁 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD b7e718f, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). 서비스 AI(OpenAI) 실제 호출 0회
- 지시 원문(요약): "fionex 프로젝트의 market_analysis 미구현 기능을 이어서 개발해줘 … 자료 수집(KOTRA·KITA·일반 뉴스), OpenAI 분석과 5차례 검토, PDF, 보류 항목과 추가 검증, 완료와 보고" (붙여 넣은 7개 절 지시문 전문)
- 질문·사용자 답변:
  - PDF 도구: "합의됨: ReportLab 추가"
  - KOTRA 키: ".env.example에 kotra api 가져와서 입력해놓으면 되는거야? 만약 그렇다면 KOTRA API 가져오는 법 알려줘." → .env.example에는 값 없이 이름만, 키는 .env/환경변수로 안내
  - 일반 뉴스: "GDELT이랑 네이버 검색 둘 다 확인. 네이버 API 가져오는 법 알려줘"
  - OpenAI 유료 검증: "3회까지 허용" (예상: 1회 6호출, gpt-5.4-mini 공식 단가 기준 약 $0.15 이하)
- 조사로 확인한 사실(출처는 sources.md):
  - KOTRA 15034831: 포털 페이지 내장 swagger에서 주소·인자(serviceKey, type, numOfRows, pageNo, search1 국가명, search2 제목, search4/7 게시일)·응답 필드(newsBdt 본문, dataType 저작권 정책 등) 확인. 공공누리 제4유형. 키 없이 401/SERVICE_KEY_IS_NULL(20), 가짜 키 SERVICE_KEY_IS_NOT_REGISTERED_ERROR(30) 실측
  - 네이버 뉴스 검색: 공식 문서로 주소·헤더·인자·필드·일 25,000회 확인. 키 없이 401/errorCode 024 실측
  - GDELT: 공식 블로그로 주소·인자 확인. 실제 호출 6회 이상 모두 429("one every 5 seconds"), 1회는 200이지만 빈 결과 `{}`(timespan=6months)
  - KITA: 공공데이터포털 '한국무역협회' 오픈 API 검색 0건, kita.net 첫 화면 API 안내 없음 → 연결 확인 중
  - ComexStat 정의: MDIC Manual.pdf에서 수입 국가=원산지, Brasil=재수입 등 브라질산, 수정 주기(월·연) 확인. NCM 54023310 개정 이력은 미확인
- 발견 문제와 대응:
  - 금액만 있고 중량이 빠진 행이 평균단가를 부풀릴 수 있음 → 짝이 맞는 행만으로 단가 계산, 결측 행 수 안내(테스트 추가)
  - OpenAI 키가 없을 때 '근거 부족·핵심 요약 0행'으로 잘못 안내 → 초안이 없으면 실패 사유만 표시
  - 키가 없어도 근거 재수집(GDELT 재시도 포함)으로 1분 이상 대기 → 실제 클라이언트일 때 키·모델 먼저 확인해 즉시 중단
  - ReportLab이 가변 글꼴을 직접 못 씀 → fontTools(작업용, 프로젝트 의존성 아님)로 400·700 정적 인스턴스 생성
- 변경 파일: features/market_analysis/(news_sources.py·analysis.py·pdf_report.py 신규, prompts/market_analysis_draft_v1.md·market_analysis_review_v1.md 신규, fonts/ 신규, service.py·routes.py·panel.html·market_analysis.js·.css·feature_spec.md 수정), tests/test_market_analysis/(test_phase2.py 신규, README.md), 공통: requirements.txt(reportlab), .env.example(키 이름 3개), README.md·docs/decisions.md(PDF 출력 도구 문장)
- 검증: validation.md 2026-10-25 2~3단계 항목
- 담당자 판단: 미확인
- 남은 한계: KOTRA·네이버 실제 기사 수신, GDELT 실제 필드, OpenAI 실제 분석 품질·비용·시간 모두 미검증. KITA 미연결. 새로고침 유지 보류

## SPE-MA-20261025-01 시장 분석 AI 프롬프트 v1 (미실행)
- 유형: service_prompt_experiment
- 프롬프트: features/market_analysis/prompts/market_analysis_draft_v1.md, market_analysis_review_v1.md (v1)
- 모델/설정: OPENAI_MODEL(후보 gpt-5.4-mini), max_output_tokens 4096, store=False(공통 설정)
- 테스트 입력: 미정(실제 통계 + 수집 기사 예정)
- 실제 응답: 없음. 실행 환경에 OPENAI_API_KEY가 없어 실제 호출하지 않음(승인 범위 최대 3회 중 0회 사용)
- 재실행 결과·담당자 판단: 미실행
