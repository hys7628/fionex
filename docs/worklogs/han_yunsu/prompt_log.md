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

## DEV-MA-20261026-01 일반 뉴스 검색 공급자 GDELT 통일
- 유형: development_instruction
- 날짜/시간: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD af0178d, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). 서비스 AI(OpenAI) 실제 호출 0회
- 지시 원문(요약): "fionex의 market_analysis에서 일반 뉴스 검색 공급자를 GDELT로 통일해줘. 네이버 뉴스 API 및 NAVER API HUB 사용 계획과 연결을 제거하고, 일반 뉴스 검색에는 GDELT만 사용하도록 수정해줘. … ComexStat 통계, KOTRA·한국무역협회 자료 활용 계획, OpenAI 분석은 유지한다." (붙여 넣은 7개 절 지시문: 6개월 목표·실제 검색 가능 기간 확인, 제목·메타데이터만 확인 표시, 최초 발견 시각≠게시일, 중복 제거·최대 20건, 재시도 최대 2회, 결과 없음과 실패 구분, 캐시, 모의·실제 호출 구분, 유료 테스트 금지, 비밀값 출력 금지, Git 작업 금지)
- 조사로 확인한 사실: GDELT 공식 안내는 "최근 3개월"이지만 실제 호출에서 약 120일 전 구간도 결과가 나옴. 첫 시도는 대부분 429. 응답에 게시일 필드 없음. 이용 조건은 GDELT 표기·링크 필요(sources.md)
- 발견 문제와 대응:
  - 처음에는 공식 안내대로 최근 89일만 검색하도록 구현 → 실측 결과와 맞지 않고 6개월 요청을 임의로 줄이는 셈이라, 6개월을 92일 구간 2개로 나눠 조회하고 90일 초과 구간은 '보장 안 됨', 실패·시간 상한 구간은 '조회하지 못한 기간'으로 표시하도록 변경
  - 섬유 검색어에도 무관 기사(식당·배우·지진)가 반환됨 → 제목의 제품·산업 주제 + 브라질 관련 조건을 모두 만족해야 선정. '브라질' 단어만으로는 선정하지 않음
  - GDELT 근거는 제목뿐이라 AI가 원인·인증·공급 조건을 지어낼 위험 → 서비스 프롬프트 v2 신규(v1 보존), title_only 규칙과 날짜 기준(date_basis) 전달
- 변경 파일: features/market_analysis/(news_sources.py, analysis.py, pdf_report.py, static/market_analysis.js, feature_spec.md 수정, prompts/market_analysis_draft_v2.md·market_analysis_review_v2.md 신규), tests/test_market_analysis/(test_phase2.py, README.md), 공통: .env.example(NAVER_* 2줄과 안내 주석 삭제)
- 제거한 네이버 항목: fetch_naver, NAVER_* 상수·검색어, USAGE의 naver, 네이버 테스트, 화면 문구, .env.example의 NAVER_CLIENT_ID·NAVER_CLIENT_SECRET, 명세의 네이버 계획(과거 기록은 이력으로 유지)
- 검증: validation.md 2026-10-26 항목(모의 82개·공통 56개 통과, GDELT 실제 호출 결과)
- 보안: .env.example 작업 사본에 사용자가 넣은 실제 키 값이 있음을 확인(값은 출력·기록하지 않음). 커밋에는 실제 값을 넣지 않음. 키 교체 여부는 사용자 판단
- 담당자 판단: 미확인
- 남은 한계: 5~6개월 전 구간 실제 결과 미확인, 429 빈도로 수집 시간이 길 수 있음, 앱 화면에서 실제 GDELT 기사로 E2E 미실행, KOTRA 실제 기사·OpenAI 실제 분석 미검증

## SPE-MA-20261026-01 시장 분석 AI 프롬프트 v2 (미실행)
- 유형: service_prompt_experiment
- 프롬프트: features/market_analysis/prompts/market_analysis_draft_v2.md, market_analysis_review_v2.md (v2, v1 기반)
- 변경 이유: 일반 뉴스가 GDELT 제목·메타데이터만이므로 제목에서 원인·인증·공급 조건·수치를 만들지 않고 "보도가 있다" 수준으로 제한, GDELT 최초 발견 시각을 게시일로 쓰지 않음
- 실제 응답: 없음(OPENAI_API_KEY 미설정, 비용 기준 확인 전 유료 테스트 금지 지시)
- 재실행 결과·담당자 판단: 미실행

## PLN-MA-20261026-01 기획 보조 역할 안내 붙여 넣기
- 유형: planning_instruction
- 날짜: 2026-10-26
- 지시 원문(요약): "앞으로 너는 팀 프로젝트 ‘fionex’의 기획과 Claude Code용 개발 프롬프트 작성을 도와줘. … 우선 저장소 문서를 읽고 … 정리해줘. 아직 코드를 작성하거나 개발 실행 프롬프트를 만들지는 마." + "추가_1 : 지금까지의 내용을 바탕으로 prompt_log.md 최신화해줘" + "추가_2 : 추가_1까지 완료하고 나면 commit 한 번 해줘."
- 처리: 로컬 저장소 문서 기준으로 정리 보고(GitHub 원격은 열지 않음), 기록 갱신 후 사용자 요청에 따라 커밋

## DEV-MA-20261026-02 뉴스 미표시 원인 분석 + 리플렉션 5회 점검·개선
- 유형: development_instruction
- 날짜: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD 11582c8, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). OpenAI 호출 0회, GDELT 실제 호출 0회(모의만)
- 지시 원문(요약): 리플렉션 패턴 "[초안] → [자기 비평] → [개선본]을 5회 반복 … 궁금한 점은 반드시 먼저 물어보고 진행해" + "추가 지시 : 뉴스 기사 서비스가 보이지 않는데 왜 안 보이는지 이유를 분석하고 해결할 수 있는 방법 알려줘"
- 질문·사용자 답변: 수정 범위 → "다른 모든 작업 수행 이후에 다시 물어봐줘"(그래서 먼저 scratchpad 사본에서만 패치·검증), GDELT → "모의 테스트만", 대상 → "명세 대비 미구현 점검, 오류·예외 처리, 알아서 판단", 커밋 → "커밋하지 않음". 이후 "1~3 모두 적용", "패치 적용 후 재시작"
- 뉴스 미표시 원인(서버 로그·설정 확인): ① 실행 중 서버가 20:15 시작·자동 재시작 꺼짐 → GDELT 통일 이전 코드로 동작 ② GDELT 429(재시도 2회 후 실패) ③ KOTRA 키가 .env.example에만 있고 줄이 나뉘어 있음, .env에는 없음 ④ jasonenv에 python-dotenv가 없어 .env 자체가 로드되지 않음(Flask 시작 안내 문구로 확인)
- 반복 결과:
  1. 적용: GDELT가 재시도 후에도 429면 남은 조회 중단, 누락 사유 '호출 한도' 표시(news_sources.fetch_gdelt)
  2. 적용: 넓은 검색 결과의 AI 사용 가능 기사가 기존보다 적으면 기존 근거 유지(service.run_ai의 widen, analysis.run의 widen_result 문구)
  3. 적용: KOTRA 키 누락 안내에 '서버 환경변수 설정 후 재시작, .env.example은 읽지 않음' 추가
  4. 보류: 시간 상한이 검색어 시작 전에만 확인돼 넘을 수 있으나 공용 _get_json 변경 위험 대비 이득이 작음
  5. 보류: 남은 미구현(새로고침 유지·KITA)은 명세에 이미 보류로 기록
- 실수: 키 이름 확인 중 .env.example의 이름 없는 줄(data.go.kr 키 값)이 대화에 한 번 출력됨. 파일·커밋에는 없음. 재발급 권고함
- 검증: validation.md 2026-10-26 리플렉션 항목
- 담당자 판단: 미확인
- 남은 한계: 실제 GDELT·KOTRA로 화면 확인 미실행(사용자가 키 설정·한도 회복 후 확인 필요)

## DEV-MA-20261026-03 뉴스 수집 방식 재검토·대체 API 조사·KOTRA 연결 확인
- 유형: development_instruction
- 날짜: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD 11582c8, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). OpenAI 0회
- 지시 원문(요약): "fionex의 market_analysis 뉴스 수집 방식을 재검토하고, 적합한 대안을 조사한 뒤 연결 작업을 진행해줘. … KOTRA API 키는 이미 공공데이터포털 키 설정 부분에 올바르게 삽입했다 … 원하는 조건은 ‘무료’이며 ‘호출 횟수 제한 없이 이용 가능’한 뉴스 API … 네이버 뉴스 API 사용은 제외 … 모든 조건을 충족하는 서비스를 확인하지 못하면 솔직하게 보고 … 대체 API가 확정·검증되기 전에는 기존 GDELT 코드를 먼저 삭제하지 마라"
- KOTRA: 키는 정상(실제 호출 resultCode 00). 이전 '설정 필요'의 원인은 서버가 .env를 읽지 않는 것(python-dotenv 미설치). 서버를 KOTRA 키 환경변수만 넣어 재시작해 연결 확인(OpenAI 키는 과금 방지를 위해 넣지 않음)
- 조사 결론: 공식 요금표·약관 기준으로 무료 + 호출 한도 없음 + 상업 이용 + 6개월 검색을 모두 만족하는 API는 확인하지 못함. GDELT가 가장 가까움(호출량 명시 없음·상업 무료)이나 5초당 1회 제한·공식 3개월 범위. 대체 공급자는 확정하지 않음(sources.md 비교)
- 발견 문제와 대응: 서버 실측에서 GDELT가 250건 상한 → 분할 재조회 실패 시 받은 결과를 모두 버리는 버그 확인 → 받은 결과 유지, URL 중복 제거, 재현 테스트 추가
- 변경 파일: features/market_analysis/news_sources.py(fetch_gdelt), feature_spec.md, tests/test_market_analysis/test_phase2.py
- 검증: validation.md 2026-10-26 KOTRA·조사·분할 실패 항목
- 담당자 판단: 미확인
- 남은 한계: 대체 공급자 결정(사용자), .env 자동 로드 방식(공통 합의 필요), GDELT 실제 결과 표시 재확인

## DEV-MA-20261026-04 작업 내용 커밋 요청
- 유형: development_instruction
- 날짜: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis
- 지시 원문: "일단 여기까지의 내용 COMMIT 하고 prompot_log.md 최신화해줘"
- 처리: 이 기록을 먼저 추가한 뒤 DEV-MA-20261026-02·03 변경(GDELT 호출 한도 시 중단, 근거 보강 결과 보호, KOTRA 키 안내 문구, GDELT 분할 조회 실패 시 받은 결과 유지, 명세·기록 갱신)을 사용자 요청에 따라 커밋. 실제 키가 들어 있는 .env.example 작업 사본과 개인 편집기 설정 .vscode/는 커밋에서 제외
- 커밋 전 검증: 시장 분석 테스트 86개·공통 테스트 56개 통과(DEV-MA-20261026-03 실행 결과, 이후 코드 변경 없음)

## DEV-MA-20261026-05 AI 설정 오류 원인 확인·GDELT 자동 호출 중단·기사별 표시·'건수' 열 삭제·KITA 경로 조사
- 유형: development_instruction (서비스 프롬프트 파일 변경 없음, AI 입력 context 문장 1줄 변경)
- 날짜: 2026-10-25 밤 ~ 2026-10-26 새벽 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD 2e3a8c4, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5), VSCode 확장. OpenAI 호출 0회, GDELT 호출 0회, KOTRA 실제 호출 약 7회(무료, 확인·E2E)
- 지시 원문(요약): "fionex의 market_analysis를 실행하고 아래 다섯 가지 문제를 해결해줘 … 1. app.py 실행과 AI 분석 오류 해결 2. GDELT 대체 무료 뉴스 API 후보 조사(사용자 선택 전 확정 금지, 네이버 제외) 3. 해외시장뉴스를 기사별로 표시(기사 제목 | 핵심 요약 1줄 | 원문 URL) 4. 해외시장뉴스 표의 '건수' 열 삭제 5. 한국무역협회(KITA) 자료 연결 방법 조사 6. 검증·문서·최종 보고". KOTRA 키 재요청 금지, 다른 프로세스 임의 종료 금지, 유료 OpenAI 테스트는 범위·비용 확인 후.
- 확인한 원인(AI 오류): .env에 OPENAI_API_KEY·OPENAI_MODEL 값은 있으나(존재만 확인) jasonenv에 python-dotenv가 없어 서버가 .env를 읽지 않음. 5003에 서버 2개(PID 19460: 이전 Claude 세션 flask run, KOTRA 키만 / PID 10040: VS Code 터미널 python app.py, 키 없음)가 동시에 LISTEN. 프로세스 환경변수 이름 존재 여부만 읽는 스크립트(scratchpad)로 확인, 값은 출력하지 않음.
- 변경:
  - analysis.py: config_status()·설정/공급자 오류 진단(diagnostic, needs_restart), 사용자용 설정 안내 문장, AI 입력 context의 일반 뉴스 문장(GDELT 기사가 없으면 '일반 뉴스 근거 없음')
  - news_sources.py: PROVIDERS에서 GDELT 제외·'일반 뉴스 공급자 선택 대기' 상태, has_general_provider, safe_url, KOTRA 확보 범위를 응답 내용으로 판단, 요약 자르기 제거, other_items, URL 중복 키에 쿼리 유지(버그 수정), _clean 이중 태그 제거
  - service.py: meta에 ai·general_news, other_items 공개 변환, 일반 뉴스 공급자 없으면 넓은 검색 생략
  - market_analysis.js/.css: 기사별 표(제목|핵심 요약 1줄|원문 URL), 출처 상태 표 3열, 640px 이하 카드 배치, 링크 검증, AI 설정 필요 안내·개발자 진단
  - pdf_report.py: 출처 상태 표 3열, 기사 표 3열(+기타 기사), 링크 검증, GDELT 표기는 GDELT 기사가 있을 때만
  - tests/test_phase2.py: GDELT 수집 테스트는 공급자를 명시적으로 켜고 실행, 신규 14개
- 발견 문제와 대응: ① KOTRA 실제 응답에 cntntSumar·newsBdt 없음 → '요약 제공 없음·원문 확인 필요', access=title_only ② E2E에서 28건 중 1건만 남는 문제 → URL 정규화가 쿼리(dataIdx)를 버리는 버그 수정 ③ 첫 화면 캡처에서 공통 .table th의 nowrap 때문에 제목·배지가 옆 칸과 겹침, 모바일 캡션이 세로로 쌓임 → 탭 CSS에서 해당 표만 줄바꿈 허용·캡션 block
- 할루시네이션 제어: 요약은 출처 제공 문장만 원문 그대로, 자동 발췌·AI 요약 금지. 일반 뉴스 근거가 없을 때 AI 입력에 '기사 근거 없음'을 명시. 출처가 없는 수치·주장 검사는 기존 코드 검사 유지
- 검증: validation.md 2026-10-26 항목
- 담당자 판단: 미확인(일반 뉴스 공급자 선택·OpenAI 유료 테스트 승인 대기)
- 남은 한계: 실제 OpenAI 분석 미실행, 새 공급자 미연결, python-dotenv 공통 합의 전, 5003의 이전 서버(PID 19460)는 수정 전 코드로 계속 실행 중

## SVC-MA-20261026-01 시장 분석 AI 분석 첫 실제 실행 (프롬프트 v2)
- 유형: service_prompt_experiment
- 날짜: 2026-10-26 00:07~00:08 (Asia/Seoul, 검증 서버 로그 기준)
- 작업자: 한윤수 / 기능: market_analysis
- 승인: 사용자 "1회만 진행"(예상 최대 6호출, 약 $0.15 이하 제시). 기존 승인 범위(최대 3회) 중 1회 사용
- 모델/설정: 응답 모델 gpt-5.4-mini-2026-03-17(OPENAI_MODEL은 .env 값, 이름만 확인), max_output_tokens 4096, store=False, 호출 상한 6, 시간 상한 480초
- 프롬프트 경로·버전: features/market_analysis/prompts/market_analysis_draft_v2.md, market_analysis_review_v2.md(파일 변경 없음). AI 입력 context의 일반 뉴스 문장만 DEV-MA-20261026-05에서 변경
- 입력: 검증용 서버(5013)에서 화면 기본값 조회(NCM 54023310, 브라질 수입, 2023-10~2026-09, 전체 공급국). 수치 근거 S1(코드 계산값). 기사 근거 0건(KOTRA 2건은 이용 범위 미확인으로 제외, 일반 뉴스 공급자 선택 대기)
- 실제 응답: docs/worklogs/han_yunsu/experiments/SVC-MA-20261026-01.json (표 9행, 검토 5회 기록 전문)
  - 사용량: 6회 호출, 입력 14,892 / 출력 6,411 토큰, 44.0초, 공식 단가 기준 추정 USD 0.04(청구액 미확인)
  - 상태: complete(초안+5회 검토 완료), 넓은 검색 없음(공급자 없음)
  - 발췌: "브라질의 NCM 54023310 수입은 2023-10~2026-09 기준 FOB USD 925,142,540, 797,257.8t이다."(사실, S1) / "재생·T2T 관련 기사 근거는 없다."(미확인)
- 발견 문제:
  1. 수치: 표의 수치(수입액·수입량·전년 대비 +6.8%/+9.7%/−2.6%·중국 83.3%·인도 15.2%·한국 16위 USD 39,600·월 최고/최저)는 모두 S1 사실 문장에 있는 값. 코드 검사의 '근거에 없는 수치' 0건. 화면 통계(같은 조회)와 대조 일치
  2. 코드 검사 오탐: 위험 2행 "재생원사나 T2T 수요 확대를 이 통계로 해석하면 안 된다"(주의 문장)가 't2t_interpretation'으로 남음 → 상태가 원래도 미확인이라 표 영향은 없으나 '자동 검사에서 남은 문제'로 표시됨
  3. 검토 기록의 신뢰성: 2·5회차는 rows_changed=false인데 모델이 changes에 '수정' 문장을 적음 → 화면의 '수정 사항'은 모델 진술이며 실제 변경 여부는 rows_changed로 판단해야 함
  4. 해석: "물량은 늘었지만 단가 압력도 있었던 시장으로 보이며"가 상태 '사실' 행의 시사점 칸에 있음(시사점 칸은 상태 구분 대상이 아님)
- 변경 이유·제어 방법: 이번 실행은 기준선 측정(프롬프트 변경 없음). 제어는 기존 코드 검사(출처 ID·수치·개수·T2T/견적)와 코드가 출처를 붙이는 방식
- 재실행 결과: 없음(승인 1회)
- 담당자 판단: 미확인
- 남은 한계: 기사 근거가 0건인 조건의 결과라 기사 기반 해석 품질은 확인 못 함. 오탐 규칙(부정문)·changes 진술 검증은 다음 작업 후보. 품질은 사람 검토 전

## DEV-MA-20261026-06 무료 뉴스 API 10개 이상 조사·K-stat 조사·미검증 항목 검증·python-dotenv 설치
- 유형: development_instruction
- 날짜: 2026-10-26 새벽 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD 2e3a8c4, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). OpenAI 6호출(SVC-MA-20261026-02 1회), GDELT 시험 호출(검증 스크립트 3회 429 + 단일 요청 2회 200·빈 결과), KOTRA 무료 호출
- 지시 원문: "1. 다른 무료 API 뉴스 사이트 조사해줘. 10개 이상 찾아서 표로 정리해서 보여줘 2. 한국무역협회 자료 말고 한국무역협회 K-STAT을 활용할 수 있는지 조사 후 결과 알려줘. 결과 확인 후 적용 여부 검토할게 3. 괄호 안에 있는 다음의 미검증 항목을 반드시 검증해(5003 서버 재시작 후 브라우저에서의 화면 확인, 실제 휴대폰 브라우저 확인(헤드리스 390px 에뮬레이션만 함,사람의 AI 결과 품질 검토,기사 근거가 있는 조건에서의 AI 분석) 4. requirements.txt에 python-dotenv 적어놨는데 버전까지 적어서 수정하고 requirements.txt 작동해서 설치까지 완료해줘."
- 처리:
  - requirements.txt: 사용자가 추가한 python-dotenv를 python-dotenv==1.2.4(pip index 최신, BSD-3-Clause)로 고정·설명 주석 추가(공통 파일, 사용자 지시). `pip install -r requirements.txt`로 설치, pip check 이상 없음
  - 5003: 사용자 지시에 따라 이전 서버(PID 19460) 종료 후 환경변수 없이 `python app.py`로 재시작 → .env 자동 로드 확인(서버 프로세스에 키·모델 존재, meta ai.ready=true), 헤드리스 Chrome으로 화면 확인
  - 실제 휴대폰: adb·연결 기기 없음, 서버가 127.0.0.1에만 열려 있어 수행 불가 → 사용자 절차 제시
  - 사람 검토: AI가 대신할 수 없어 AI 보조 검토와 사람 검토 체크리스트를 validation.md에 남김
  - 기사 근거 조건: GDELT 429·빈 결과 → MDIC 공식 공지 원문 발췌를 검증용 시험 근거로 넣어 실제 분석 1회(SVC-MA-20261026-02). 서비스 코드는 변경하지 않음
  - 실수: GDELT 대기 명령에 불필요한 `python -`가 들어가 입력 대기로 멈춤 → 해당 프로세스만 종료
- 검증: validation.md 2026-10-26 '미검증 항목 검증' 항목
- 담당자 판단: 미확인
- 남은 한계: 실제 휴대폰·사람 검토는 담당자 수행 필요, README의 python-dotenv 설명 갱신은 공통 문서라 제안만 함

## SVC-MA-20261026-02 기사 근거(공식 공지 1건)가 있는 조건의 실제 실행 (프롬프트 v2)
- 유형: service_prompt_experiment
- 날짜: 2026-10-26 새벽 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis
- 승인: 기존 승인 범위(최대 3회) 중 2회째. 사용자 지시 "기사 근거가 있는 조건에서의 AI 분석"을 반드시 검증
- 모델/설정: gpt-5.4-mini-2026-03-17, max_output_tokens 4096, store=False, 호출 상한 6
- 프롬프트: market_analysis_draft_v2.md / market_analysis_review_v2.md (변경 없음)
- 입력: ComexStat 실제 통계(SVC-01과 같은 조건) + 근거 N3: MDIC 공익성 평가 페이지(https://www.gov.br/mdic/.../fios-de-poliester) 원문 문장 그대로(제품·NCM 5402.33.10/20/90·중국산·개시일·기한·Circular nº 65). CC BY-ND 3.0, 검증 스크립트에서 추가(서비스 수집 경로 아님)
- 실제 응답: experiments/SVC-MA-20261026-02.json. 6호출, 45.6초, 입력 17,354·출력 7,777 토큰, 추정 USD 0.048. complete, 남은 자동 검사 0건, 1회차만 표 변경
- 발견 문제(할루시네이션·해석):
  1. 코드 표기 혼동: "N3는 5402.33.10을 포함한 넓은 하위품목… 54023310 전 품목의 영향 범위를 확정할 수 없다" → 5402.33.10은 54023310과 같은 코드. 근거가 조회 품목을 직접 다루는데 범위를 잘못 낮춤(상태 '미확인'). 코드 검사로 잡히지 않음
  2. 누락: 원문의 기한(증거 제출 단계 마감 30/10/2026, 최종 의견 마감 23/11/2026) 미반영
  3. 방향성: 공익성 평가는 기존 반덤핑 조치에 대한 평가인데 '규제 리스크'로만 표현(완화 가능성 미언급) — 원문에 결과 방향이 없으므로 단정은 금지, 다만 '조치 유지·변경 여부 평가 중'으로 쓰는 것이 정확
  4. 공식 공지를 '기사'로 부름(출처 종류 표현)
- 제어 방법 후보(미적용): 입력 facts에 조회 코드의 점 표기(5402.33.10)를 함께 넣기, 코드 검사에 'NCM 표기 동일성' 규칙 추가, 원문 날짜 누락 점검 항목을 검토 프롬프트 v3에 추가
- 재실행 결과: 없음
- 담당자 판단: 미확인
- 남은 한계: 근거 1건·공식 공지만의 조건. 일반 뉴스 근거 조건은 공급자 선택 후 재검증

## DEV-MA-20261026-07 세션 시작 문서 확인·첫 커밋 안내 (기록 누락분 추가, 시간상 DEV-MA-20261026-05보다 앞)
- 유형: development_instruction (코드 변경 없음)
- 날짜: 2026-10-25 밤 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD 2e3a8c4)
- 모델/설정: Claude Code (claude-opus-5-5), VSCode 확장. 서비스 모델 호출 없음
- 지시 원문(요약):
  1. 기획·Claude Code용 개발 프롬프트 작성 보조 역할 안내 + "[지금 할 일] 우선 저장소 문서를 읽고 … 실제로 읽은 파일과 접근하지 못한 파일, 내 담당 기능과 작업 범위, 개발 전에 결정하거나 보완해야 할 사항, 권장하는 첫 번째 개발 작업 … 아직 코드를 작성하거나 개발 실행 프롬프트를 만들지는 마."
  2. "commit하려고 하는데 터미널에 사용할 코드 만들어줘"
- 처리:
  1. GitHub 대신 로컬 저장소 문서(README, CLAUDE.md, AGENTS.md, docs 5종, feature_spec.md, worklogs 일부)를 읽기 전용으로 확인. 안내문(기능 개발 전제)과 실제 상태(1~3단계 구현·푸시 완료)의 차이, 새로고침 유지 요구 충돌, 명세 내 KOTRA 상태 불일치, python-dotenv 설치 기록 불일치 등을 보고. 첫 작업으로 '과금 없는 실데이터 E2E 점검·명세 정합화' 권장
  2. 변경이 .env.example 마지막 줄바꿈뿐(비밀값 없음)임을 확인하고 커밋하지 않는 정리 방법(git restore, .git/info/exclude)과 커밋할 경우의 명령을 안내
- 결과: 코드·문서 변경 없음
- 담당자 판단: 이후 다섯 가지 문제 해결 지시(DEV-MA-20261026-05)로 진행

## DEV-MA-20261026-08 일반 뉴스 공급자 결정·K-stat 미사용·휴대폰 검증 생략·커밋 분리 안내
- 유형: development_instruction (코드 변경 없음)
- 날짜: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis
- 모델/설정: Claude Code (claude-opus-5-5). 서비스 모델 호출 없음
- 지시 원문:
  1. "1. NewsData.io 사용할게. api 불러오는 법 알려줘. 2. K-stat 사용하지 않을게. 3. 휴대폰 브라우저 검증은 굳이 안해도 될 것 같아."
  2. (1번 처리 중 사용자 중단) "추천 커밋 제목대로 나눠서 commit하려고 해. vs code 터미널에 넣을 코드 각각 알려줘"
  3. "첫 번째 커밋으로 할 때 .env.example과 .vscode/를 넣지 않는 방법 알려줘."
  4. "지금까지의 대화 내용을 기반으로 prompt_log.md 최신화해줘."
- 담당자 결정(사용자 답변):
  - 일반 뉴스 공급자: NewsData.io 사용(DEV-MA-20261026-06 후보 표의 1번). 연결 구현은 아직 하지 않음
  - K-stat: 사용하지 않음(조사 결과: 브라질 품목별은 회원사 전용, 제공기관 Trade Map, Open API 없음, 자동 수집 금지)
  - 실제 휴대폰 브라우저 검증: 생략(헤드리스 390px 확인만 유지)
- 처리:
  1. NewsData.io 공식 문서 확인을 시작했으나 사용자 중단으로 안내하지 못함. 확인된 내용: 공식 문서 첫 페이지에 엔드포인트 이름(Latest News, News Archive 등)과 무료 플랜(일 200 크레딧, 최근 48시간, 12시간 지연)만 있고, 주소·인증 방식·인자·페이지 넘김은 세부 페이지 확인 필요(제3자 SDK 기준 /latest·/archive, page=nextPage 값은 공식 확인 전)
  2. 커밋 2개 분리 명령(PowerShell): requirements.txt 단독 커밋 → 기능·테스트·기록 16개 파일 지정 커밋 → 확인·푸시
  3. 파일을 직접 지정해 git add, `git add .`·`-A`·VS Code 전체 스테이징 사용 금지, `git diff --cached --name-only` 확인, 실수 시 `git restore --staged`, 선택 사항으로 .git/info/exclude에 .vscode/ 추가·.env.example 줄바꿈 변경 되돌리기 안내
- 결과(git log로 확인): 389338e "chore: python-dotenv 1.2.4 의존성 추가", 95c8577 "feat: 시장 분석 뉴스 기사별 표시와 AI 설정 진단 추가, 일반 뉴스 자동 수집 중단". 남은 변경: .env.example(줄바꿈), .vscode/(미추적)
- 남은 일:
  - NewsData.io 연결: 공식 세부 문서로 엔드포인트·인증·인자 확인, 사용자의 키 발급 후 .env에 새 환경변수(이름은 공통 규칙에 맞춰 확정, .env.example 추가는 공통 합의) 설정, 실제 호출 검증
  - 사용자 조건 '최근 6개월 기사'와 NewsData.io 무료 플랜(최근 48시간·12시간 지연)이 맞지 않음 → 6개월 확보 방법(유료 Archive 등) 또는 조건 조정을 담당자와 확인 필요
  - feature_spec.md에 위 세 가지 결정 반영(이번 지시는 prompt_log 최신화만이라 미반영)

## DEV-MA-20261026-09 NewsData.io 호출 방법 안내 (DEV-MA-20261026-08의 1번 재지시)
- 유형: development_instruction (코드 변경 없음, feature_spec.md에 결정 사항 반영)
- 날짜: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록)
- 지시 원문: "1. NewsData.io 사용할게. api 불러오는 법 알려줘. 2. K-stat 사용하지 않을게. 3. 휴대폰 브라우저 검증은 굳이 안해도 될 것 같아." (같은 지시 재전송)
- 확인: 공식 문서 페이지는 세부 내용이 화면에 렌더링되지 않아 확인 못 함. 키 없이 실제 호출로 /api/1/latest·/api/1/archive 존재, apikey 쿼리 인자, 401 오류 형식 확인(과금 없음). 공식 Python SDK(newsdataapi, PyPI) 예시: latest_api(q, country, language)
- 처리: 키 발급·설정·호출 예시 안내, feature_spec.md에 세 결정과 확인 내용 반영
- 남은 일: 키 발급 후 실제 응답 필드·브라질/포르투갈어 결과·응답 시간·무료 플랜의 기간 제한 실측, 연결 구현(사용자 요청 시)

## DEV-MA-20261026-10 NewsData.io 키 동작 확인·일반 뉴스 연결·대시보드 검증
- 유형: development_instruction
- 날짜: 2026-10-26 01시대 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD 95c8577, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). NewsData.io 실제 호출(무료 크레딧), OpenAI 6호출 1회(SVC-MA-20261026-03, 승인 3회 중 3회째)
- 지시 원문: "newsdata api key 받아왔어. 작동하는지 실행해보고 대시보드에서 잘 구현되는지 검증해줘."
- 실제 확인(키 값 미출력): .env에 NEWSDATA_API_KEY(36자). /latest 200·0.7~1.2초, 헤더 X-RateLimit-Limit 60·X-API-Limit-Remaining(일일 크레딧 잔량 199부터 감소), 무료 플랜 content·ai_summary는 "ONLY AVAILABLE IN PAID PLANS", ai_region·ai_org는 CORPORATE 전용, /archive(5~4개월 전)는 403 AccessDenied("upgrade your plan"). description은 93~6,000자 언론사 리드 문단
- 변경:
  - news_sources.py: fetch_newsdata(브라질·포르투갈어 검색어 4개, 검색어당 최대 2쪽, 401/키 오류는 즉시 중단, 한도 초과 시 남은 검색어 중단, 403은 해당 검색어만 실패), PROVIDERS에 newsdata, access 'description', 48시간 범위 coverage·안내, 일반 뉴스 관련성 규칙(제목·설명 앞 400자·키워드 + 산업·시장 맥락어 또는 무역 정책어 필요)
  - analysis.py: NewsData 근거 context 문장, AI 입력 설명 1,500자 상한(화면은 자르지 않음)
  - market_analysis.js/.css: 긴 언론사 설명 접기(자르지 않음), 'Powered by NewsData.io' 링크, 게시일(UTC) 표시
  - pdf_report.py: NewsData 표기, 설명은 PDF 미수록(제목·링크만)
  - service.py: meta.general_news.provider
  - .env.example: NEWSDATA_API_KEY= (이름만, 공통 검토 필요 표시)
  - tests: NewsdataTest 10개, 기본 공급자 테스트 갱신
- 발견 문제와 대응: 대시보드 1차 실행에서 선거 안내·다림질 요령 등 무관 기사가 '섬유·의류'로 선정됨(긴 설명 뒤쪽의 'vestuário' 등) → AI도 "뉴스 목록은 대부분 비관련 일반 기사"라고 표시 → 관련성 규칙 보강 후 관련 1건(산업 기사)만 선정, 나머지 23건은 주제 밖으로 분리
- 실수: 5003 재시작 시 부모 프로세스만 종료해 디버그 자동 재시작 자식(33200)이 포트를 계속 점유 → 제가 띄운 서버의 자식임을 확인하고 종료. 화면 확인 스크립트의 정규식 이스케이프 오류로 일부 텍스트 출력이 깨짐(화면 문제 아님)
- 검증: validation.md 2026-10-26 'NewsData.io' 항목
- 담당자 판단: 미확인
- 남은 한계: 무료 플랜은 최근 48시간만(6개월 조건 미충족), 관련성 규칙 수정 후 AI 재실행 안 함(추가 승인 필요), NewsData.io 약관의 AI 입력 허용 범위는 약관 문구 해석(내부 업무 목적) 기준이며 제공사 확인은 안 함

## SVC-MA-20261026-03 대시보드에서 NewsData.io 근거로 실제 실행 (프롬프트 v2)
- 유형: service_prompt_experiment
- 날짜: 2026-10-26 01:49~01:50 (Asia/Seoul)
- 승인: 기존 승인 범위(최대 3회) 중 3회째(마지막). 사용자 지시 "대시보드에서 잘 구현되는지 검증"
- 실행 경로: 5003 대시보드 → 분석 실행 → AI 분석 실행 버튼(서비스 경로 그대로)
- 입력: ComexStat 실제 통계 + NewsData.io 관련 기사(관련성 규칙 수정 전, 무관 기사 다수) + KOTRA 2건(AI 입력 제외)
- 실제 응답: experiments/SVC-MA-20261026-03.json(화면 텍스트). 6호출, 55.8초, 입력 32,933·출력 7,779 토큰, 추정 USD 0.0597, 5차례 검토 완료
- 관찰: 통계 수치 행은 SVC-01·02와 같은 값. 기사 근거 행은 "N2: 폴리에스터가 세계 섬유 생산에서 큰 비중… 브라질 수입 통계의 직접 원인으로 확인되지 않음(미확인)", 위험 행에 "뉴스 목록은 대부분 비관련 일반 기사"(미확인, N1~N11 출처) → 모델이 무관 근거를 사실로 끌어오지 않고 한계를 명시함. 반면 무관 기사 9건을 출처로 나열한 행은 출처 칸이 길어 가독성이 떨어짐
- 변경 이유·제어: 입력 품질 문제(무관 기사) → 프롬프트가 아니라 수집 단계 관련성 규칙으로 제어(DEV-MA-20261026-10)
- 재실행: 없음(승인 소진)
- 담당자 판단: 미확인

## DEV-MA-20261026-11 단가 검증·브라질 제외·KITA 삭제·핵심 기사 기준·안내 토글·요약 열 삭제·제목 번역
- 유형: development_instruction (서비스 프롬프트 신규: news_title_translate_v1.md)
- 날짜: 2026-10-26 02시대 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD ee1de3f, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). ComexStat 직접 호출 2회(검증), OpenAI 번역 1회(SVC-MA-20261026-04), NewsData.io 무료 크레딧
- 지시 원문: "1. 업로드한 사진을 참고해서 대만과 불가리아의 평균 수입단가를 검증해줘. 2. 공급국 비교의 나라 리스트에서 브라질은 삭제해줘. 3. image.png(717x152)를 참고하고 한국무역협회 내용은 삭제해줘. 4. 핵심 기사 3건에는 섬유 업계에서 눈여겨볼만한 기사로만 구성해줘. 5. image.png(805x127)을 참고하고 검색 기간 제한 내용은 토글화해줘. 6. 기사의 핵심 요약 1줄 열은 전부 삭제해줘. 7. 포르투갈어나 스페인어 제목으로 된 기사를 가져올 때는 한국어로 번역된 제목도 같이 붙여줘."
- 질문·사용자 답변: 번역 실제 테스트 → "최대 3회 승인", 브라질 처리 → "목록에서만 제외"(전체 수입액은 공식 합계 유지)
- 처리:
  1. 앱 코드를 거치지 않고 ComexStat POST /general에 국가 필터(대만 161, 불가리아 111)로 직접 조회해 합산: 대만 FOB USD 3,630,185 ÷ 868,228 kg = 4.1811, 불가리아 266,329 ÷ 53,467 kg = 4.9812 → 화면 4.18·4.98·868.2 t·53.5 t와 일치. '확인 필요'는 공급국 단가 중앙값 2배 초과라는 규칙에 따른 표시(계산 오류 아님). 대만 월별 단가 1.82~6.32로 편차 큼(제품 혼합 추정), 불가리아 4.49~5.33 소량 거래
  2. service.py: 원산지 브라질(105)을 공급국 목록·순위·국가 수·선택 목록에서 제외, 선택 시 입력 오류, 전체 수입액·비중 분모는 공식 합계 유지, 제외 금액·비중 안내
  3. news_sources.py: KITA 상태 행 삭제
  4. news_sources.py: KOTRA 관련성 판단에서 산업분류(indstCl) 제외(월드컵 소비 기사가 섬유로 판정되던 원인), 주제어에 fibras têxteis 등 추가. 화면 표 이름 '핵심 기사 · 섬유 업계 관련'. 건수를 3건으로 채우지 않음(기준에 맞는 기사만)
  5. 화면: 검색 기간 제한 안내를 접힌 토글(details)로
  6. 화면·PDF: 기사 표를 '기사 제목 | 원문 URL' 2열로(요약 열 삭제). description은 화면·PDF에 표시하지 않고 AI 입력에만 사용
  7. translation.py 신규 + prompts/news_title_translate_v1.md: 포르투갈어·스페인어 제목만 1회 호출로 번역, 같은 날 같은 제목 재사용, id 대조·빈 값·과도한 길이 검사, 실패·설정 없음은 원문만 표시. 화면·PDF에 'AI 번역' 표시
- 검증: validation.md 2026-10-26 '7개 지시' 항목
- 담당자 판단: 미확인
- 남은 한계: 핵심 기사는 하루치 결과로 2건 확인(3건 미만일 수 있음), 번역 품질은 사람 검토 전

## SVC-MA-20261026-04 기사 제목 번역 프롬프트 v1 첫 실제 실행
- 유형: service_prompt_experiment
- 날짜: 2026-10-26 02:46 (Asia/Seoul, 대시보드 실행)
- 승인: 사용자 "최대 3회 승인" 중 1회째
- 모델/설정: OPENAI_MODEL(.env 값), max_output_tokens 4096, 1회 호출. 응답 모델명·토큰은 이번 화면에 표시하지 않아 미기록(번역 상태 dict에는 남음)
- 프롬프트: features/market_analysis/prompts/news_title_translate_v1.md (신규)
- 입력: NewsData.io 포르투갈어 기사 제목 24건(공개 기사 제목)
- 실제 응답: experiments/SVC-MA-20261026-04.json(화면에서 읽은 원문·번역 쌍 9건). 24건 모두 번역 표시
- 관찰: "Plástico domina 59% da produção mundial de fibras…" → "플라스틱이 세계 섬유 생산의 59%를 차지하고 휴대전화 무게의 37%를 이룬다"(숫자 보존), "R$ 1.621" 원문 표기 유지, "1,7 mi de eleitores" → "170만 명"(규칙 2 '숫자 원문 그대로'와 달리 단위 환산 — 의미는 같음)
- 발견 문제: 단위 표기 환산 1건(오역 아님). 제어 후보: 규칙 2에 '수량 단위(mi, mil)도 원문 표기 유지' 명시(v2)
- 담당자 판단: 미확인

## DEV-MA-20261026-12 기사 아래 범위 문구·공급국 단가 '확인 필요' 표시 삭제
- 유형: development_instruction
- 날짜: 2026-10-26 03시대 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD ec85d72, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). OpenAI 번역 1회(서버 자동 재시작으로 번역 캐시가 비어 대시보드 확인 중 호출, 번역 승인 3회 중 2회째)
- 지시 원문: "1. 신문 기사 제목들 밑에 '제목·언론사 설명만 확인(본문 미확인)', '제목·메타데이터만 확인', 'AI 입력·PDF 본문 미사용 · 이용 범위 확인 필요'와 같은 문구는 전부 삭제해줘. 2. 대만과 불가리아의 평균 수입단가에 붙어 있는 확인 필요 문구 삭제해줘."
- 처리:
  1. 화면 기사 표의 확보 범위·이용 범위 배지 삭제, PDF 기사 표의 같은 문구 삭제. 데이터(access·ai_input·pdf_text)와 이용 범위 처리(KOTRA AI 입력 제외 등)는 그대로
  2. 공급국 표(상위 10개국·선택 공급국)의 단가 '확인 필요' 표시를 화면·PDF에서 삭제(대만·불가리아 단가는 DEV-MA-20261026-11에서 원자료와 일치 확인). 월별 표의 표시와 price_flag 데이터는 유지
- 검증: validation.md 2026-10-26 '범위 문구·공급국 확인 필요 삭제'
- 담당자 판단: 미확인

## DEV-MA-20261026-13 머리글 다운로드 문구 삭제 + 리플렉션 10회(UI 개선·불필요 문구 삭제)
- 유형: development_instruction
- 날짜: 2026-10-26 03시대 (Asia/Seoul, 정확한 시각 미기록)
- 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD ec85d72 이후, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). OpenAI 번역 1회(대시보드 확인 중 자동 재시작으로 캐시가 비어 호출, 번역 승인 3회 모두 사용)
- 지시 원문: (1) "빨간색으로 표시된 부분(다운로드 여부 확인 문구) 삭제해줘" (2) "당신은 FIONEX의 market_analysis를 검토하고 개선하는 담당자입니다. … 리플렉션 패턴을 정확히 10회 적용하세요 … 목적과 기대 결과: UI 개선 및 쓸데 없는 문구나 안내 사항 삭제 … 정확히 10줄만 출력하세요."
- 판단: 머리글 문구는 공통 static/js/app_shell.js(renderStatus)가 만들고 모든 탭이 쓰므로 공통 파일을 고치지 않고, 탭 코드에서 다운로드 요청 직후 공개 API AppShell.work.clear를 호출(leave_guard.js isGuarded는 downloadRequested를 쓰지 않아 이탈 경고 동작 동일)
- 회차별 반영(실제 변경만):
  1. 머리글 '다운로드 요청됨 · 저장 여부는 브라우저에서 확인' 미표시(clear 호출), PDF 옆 문구 → "PDF 다운로드를 요청했습니다."
  2. 출처 표 안내 칸에서 이용 조건 설명(usage_note) 제외
  3. PDF 출처 표도 같은 기준(일관성)
  4. '핵심 기사: … N건 / 후보 N건' 안내 문단 삭제(표 caption과 중복). GDELT 문장은 GDELT 기사가 있을 때만
  5. NewsData 표기 문장 → 'Powered by NewsData.io' 링크만(48시간 설명은 검색 기간 토글과 중복)
  6. 번역 안내 → "AI 번역은 OpenAI 기계 번역이며 원문 제목이 기준입니다."(제목별 'AI 번역' 표시와 중복된 건수 설명 삭제)
  7. AI 실행 안내 축약, 소요 시간 '수 분' → '1분 안팎'(실측 44~56초, SVC-01~03)
  8. 통계 참고 사항(notes)을 '통계 참고 사항 N건 보기' 토글로 접음(T2T 해석 주의·이전 자료 경고는 계속 표시)
  9. panel.html "공급국은 브라질에 수출한 국가입니다" 삭제(결과 화면의 '원산지 국가이며 판매 회사의 국가가 아님'과 모순)
  10. 변경 없음: 테스트·대시보드 검증만 수행
- 검증: validation.md 2026-10-26 '리플렉션 10회'
- 담당자 판단: 미확인

## DEV-MA-20261026-14 검색 기간 제한 토글 제목 변경
- 유형: development_instruction / 날짜: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록) / 작업자: 한윤수 / 기능: market_analysis
- 지시 원문: "수정 : '검색 기간 제한 안내 1건 보기' 대신 '검색 기간 제한 안내'로 바꿔줘"
- 처리: market_analysis.js newsHtml의 토글 제목을 '검색 기간 제한 안내'로 고정(건수·'보기' 제거)
- 검증: node --check 통과. 대시보드 화면 재확인은 미실행(문자열 1곳 변경)

## DEV-MA-20261026-15 머리글 '다운로드하지 않은 결과 있음' 표시 삭제(공통 변경)
- 유형: development_instruction / 날짜: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록) / 작업자: 한윤수 / 기능: market_analysis(공통 shell 변경 포함)
- 지시 원문: "수정 : '다운로드하지 않은 결과 있음' 영역 삭제해줘"
- 판단: 문구는 공통 static/js/app_shell.js renderStatus가 만들고, 같은 상태(setResult)가 새로고침·종료 경고에 쓰여 탭 코드만으로는 문구만 지울 수 없음 → 사용자 선택 "문구만 숨김·경고 유지"
- 처리(공통 파일, 다섯 탭 공통 적용): app_shell.js renderStatus에서 미다운로드 결과 상태의 머리글 문구·사이드바 점 표시 제거(작성 중·다운로드 요청됨 표시는 유지), docs/design_system.md '머리글 상태 표시' 문장 갱신. leave_guard.js 변경 없음
- 검증: node --check 통과, 공통 테스트 56개 통과, 5003 대시보드에서 분석 후 머리글 표시 hidden·사이드바 점 hidden·hasUndownloadedResult=true·isGuarded=true(이탈 경고 유지) 확인
- 남은 일: 공통 변경이므로 팀 공유·다른 탭 담당자 확인 필요

## DEV-MA-20261026-16 AI 분석 추정·미확인 행 5회 검토 후 확정 또는 삭제, PDF 검색 기간 문구 삭제
- 유형: development_instruction (서비스 프롬프트 신규: market_analysis_review_v3.md)
- 날짜: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록) / 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD 287fef8, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). OpenAI AI 분석 2회(SVC-MA-20261026-05·06, 사용자 승인 "최대 2회"), 제목 번역 호출 없음
- 지시 원문: (1) "AI 분석 중 미확인된 것과 추정된 것은 5번 스스로 개선해보고 출처에 기반해서 확인되지 않으면 삭제해줘. PDF에서도 삭제해줘" (2) "PDF 안에 있는 '일반 뉴스(NewsData.io) 2026-04-27~2026-10-23: 무료 플랜은 최근 48시간 기사만 제공(과거 기사 /archive는 유료, 2026-10-26 실측 403). 이 기간의 일반 뉴스는 확보하지 못했습니다.' 라는 문구는 삭제해줘."
- 처리:
  - review_v3.md: 매 회차 추정·미확인 행을 S1·인용 기사로 대조해 출처에 있는 사실만 남겨 확정하거나 삭제(삭제는 changes에 기록), 개수 채우기 금지, 점 표기 코드 동일성 명시. v2는 실험 기록이 있어 보존
  - analysis.py: check_rows에 'unconfirmed' 검사(사실이 아닌 행) → 5회 검토 입력 code_findings로 전달, finalize_rows가 사실 행만 남기고 removed_rows(사유 포함) 반환, 비율(%)은 근거의 비율과 단위까지 대조, 1~12 숫자 예외는 'N월·N개월' 표기만
  - 화면·PDF: 사실 행만 표시, 뺀 항목은 접힌 검토 기록(화면)·검토 기록 아래(PDF)에 건수·요지
  - PDF: 검색 기간 제한 안내(window.notes) 미수록, NewsData 표기 문장을 'Powered by NewsData.io'만으로(48시간 설명 삭제)
- 발견 문제: 1차 실행에서 "나머지 국가는 모두 개별 비중이 1% 미만" 이 '사실'로 통과 → 원인 ① 1~12 숫자 무조건 허용 ② S1의 '1위'의 1과 '1%'의 1을 같은 숫자로 인정 → 두 규칙 보강 후 저장된 1차 결과를 다시 검사해 해당 행이 잡히는 것 확인, 2차 실행에서는 해당 유형 문장 없음
- 검증: validation.md 2026-10-26 'AI 추정·미확인 삭제'
- 담당자 판단: 미확인
- 남은 한계: 사실 행만 남기면서 영업 기회·위험 구분이 비는 경우가 많음(2회 모두 빈 구분 있음). 화면 표는 코드(필터)·테스트로만 확인하고 대시보드 실제 화면은 이번에 미확인(번역 승인 소진으로 대시보드 실행을 피함)

## SVC-MA-20261026-05 / -06 검토 프롬프트 v3 실제 실행
- 유형: service_prompt_experiment / 날짜: 2026-10-26 / 승인: "최대 2회" 중 2회 사용
- 모델: gpt-5.4-mini-2026-03-17, 프롬프트 draft_v2 + review_v3, 근거: S1 + NewsData 기사 1건(AI 입력 허용), KOTRA 1건 제외
- 실제 응답: experiments/SVC-MA-20261026-05.json, -06.json
  - 05: 6호출·22.6초·입력 16,796/출력 5,053 토큰·추정 USD 0.0353. 최종 4행 모두 사실(S1). 1회차에 '폴리에스터 59%…구조적 배경 시사' 해석 행 삭제, 2회차에 '한국산 존재감 제한적' 해석 삭제, 코드 검사 7→0건. 단 '나머지 국가 1% 미만' 근거 없는 문장 통과(위 규칙 보강 계기)
  - 06: 6호출·18.2초·입력 16,026/출력 3,797 토큰·추정 USD 0.0291. 최종 3행 모두 사실(S1), 1회차에 추정 행 4건 삭제, 코드 검사 5→0건, 2~4회차 변경 없음
- 관찰: 5회차가 rows 변경 없이 changes에 진술을 적는 경향 계속(SVC-01과 같음). 시사점(implication)은 사실 행에서 짧은 일반론으로 남음
- 담당자 판단: 미확인

## DEV-MA-20261026-17 뉴스 수집 기능 전체 삭제(KOTRA·NewsData.io)
- 유형: development_instruction / 날짜: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록) / 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD 1e0b189, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). OpenAI·외부 뉴스 API 호출 0회
- 지시 원문: "kotra 시장뉴스와 newsdata.io 서비스는 아예 삭제해버리자." → 질문 "어느 범위로 삭제할까요?" 답변 "뉴스 기능 전체 삭제 (권장)"
- 처리: news_sources.py·translation.py·prompts/news_title_translate_v1.md 삭제(Git 이력에 남음), service·routes·analysis·pdf_report·화면 JS/CSS에서 뉴스·번역 코드 제거, AI는 통계만으로 바로 실행, .env.example 뉴스 키 2개 삭제(공통 파일), 메뉴 설명에서 '업계 소식' 삭제, 테스트 정리
- 실수와 대응: pdf_report.py로 safe_url을 옮기는 스크립트에서 정규식 이스케이프가 실제 제어 문자(NUL 등)로 들어가 import 오류 → 바이트 단위로 바로잡음. 그 사이 디버그 자동 재시작이 오류 파일을 불러오다 5003 서버가 종료됨 → 같은 방식으로 재시작
- 검증: 시장 분석 65개·공통 56개 테스트 통과, node --check 통과, 5003 대시보드에서 뉴스 영역·문구 없음·AI 버튼 즉시 활성·'⑤ 근거 자료'는 ComexStat만·뉴스 API 404 확인. AI 실제 실행은 승인 없음으로 미실행
- 남은 일: 로컬 .env의 뉴스 키 2개는 사용자가 직접 정리(앱이 쓰지 않음)

## DEV-MA-20261026-18 바이어 목록 서비스 요구사항 확인(질문만, 구현 전)
- 유형: development_instruction (코드 변경 없음, feature_spec.md에 요구사항 기록)
- 날짜: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록) / 작업자: 한윤수 / 기능: market_analysis
- 지시 원문: "브라질에서 리젠 t2t를 수입하는 업체를 찾아서 바이어 목록 서비스를 구현하고 싶어. 참고 : 궁금한 점은 전부 물어봐줘."
- 사전 조사(웹 검색 요약, 원문 미확인): MDIC/SECEX가 연도별 수출입 기업 명단(Cadastro de Empresas Exportadoras e Importadoras)을 공개하나 품목(NCM) 정보는 없다는 결과, 품목별 통계 파일에는 기업 정보 없음. ComexStat API에도 기업 구분 없음
- 질문·답변(3회): 위치 → 시장 분석 탭 안 새 영역 / 대상 → 두 묶음 구분 / 출처 → 무료 공식 공개 자료 / 항목 → 회사 연락처, 회사명·지역·업종 / ① 기준 → 섬유 업종 수입 업체로 대신 / ② 근거 → 업체 공식 웹·보도자료 허용 / 연락처 → 법인 대표 연락처만 / 출력 → "화면 표로 보여주는데 첫 5명의 바이어만 화면에 보여주고 나머지는 토글화" / 정렬 → 재생·T2T 근거 있는 업체 우선 / 업종 → 원사·원단 제조 / ② 수집 → 기준 자료 파일로 정리 / PDF → 전체 목록 포함
- 다음 단계(제안): 1) 공식 명단·CNPJ 공개 자료 실제 내려받아 항목·크기·이용 조건 확인 2) 섬유 업체 기준 데이터 생성 3) ② 재생 근거 조사 4) 화면·PDF 구현

## DEV-MA-20261026-19 바이어 목록 1단계(공식 무료 자료 확인)
- 유형: development_instruction (코드 변경 없음) / 날짜: 2026-10-26 (Asia/Seoul, 정확한 시각 미기록) / 작업자: 한윤수 / 기능: market_analysis
- 지시 원문: "1단계부터 시작할 것"
- 처리: MDIC 원자료 페이지·FAQ·통계 매뉴얼(PDF 내려받아 본문 추출), 국세청 CNPJ 항목 설명서(PDF 내려받아 확인), 공식 다운로드 주소·IBGE CNAE API 접근 시도, 업종 코드 후보 검색
- 결과: 수입 기업 명단은 공식 제공 안 됨(세무 기밀) / CNPJ 공개 자료로 업종·연락처는 가능하나 수입 여부 없음 / 공식 다운로드 주소는 자바스크립트 앱이라 명령줄 404 / IBGE API 연결 시간 초과 / 라이선스 문구 미확인
- 질문·답변: ① 재정의 → "원사·원단 제조 기업으로 (권장)", 규모 → "'그 외(중·대형)'만 (권장)", 자료 준비 → "국세청 자료를 통해서 브라질 업체 정보를 가져온다는 말이야? 이 부분 답변 먼저 해줘" → 브라질 연방국세청 CNPJ 공개 자료의 성격·항목·한계·사용 방식 설명, 자료 준비 방식 재질문
- 다음: 자료 준비 방식 답변 후 2단계(공식 다운로드 방법 확인 → 섬유 업체 정리본 생성)

## DEV-MA-20261026-20 바이어 목록 2·4단계(생성기·화면·PDF) 구현, 원본 내려받기 중단
- 유형: development_instruction / 날짜: 2026-10-26 (Asia/Seoul, 약 11:00~11:35) / 작업자: 한윤수 / 기능: market_analysis / 브랜치: feature/market_analysis (HEAD 106c590, 미커밋 변경)
- 모델/설정: Claude Code (claude-opus-5-5). OpenAI 호출 0회
- 지시 원문: "지시 : 권장 사안으로 진행해" → "바로 만들어줘" → "지시 : 바이어 작업 20분 안에는 끝내야하니까 가장 최단 시간에 해결할 수 있는 방법 고안해서 적용해줘"
- 처리: 국세청 CNPJ 공식 저장소의 WebDAV 경로 확인, buyer_data_builder.py(대상 CNAE 정규식 선별·파일별 병렬 처리), buyers.py(① 기준 자료+② 근거 병합, 근거 업체 먼저), GET /api/market-analysis/buyers, 화면 ⑥(첫 5곳+나머지 토글, 수입 여부 확인 불가 안내, 법인 대표 연락처), PDF ⑥(전체 목록), data/buyer_t2t_evidence.json(빈 틀), 테스트 5개
- 최단 경로 시도: 원본(Estabelecimentos·Empresas 약 6.8GB)을 Range 분할 병렬(56연결)로 내려받기 → 약 8분 동안 완료 조각 0, 수신 속도 0.01MB/s, 단일 요청도 0바이트 시간 초과(서버 차단 또는 과부하로 추정, 원인 미확인) → 내가 띄운 내려받기 프로세스 2개 종료. 20분 목표 달성 못 함
- 실수와 대응: 인라인 `python -` 줄이 입력 대기로 멈춤 → 작업 중지 후 Edit 도구로 수정. 테스트 모의 CNPJ 앞 8자리가 모두 같아 한 기업으로 묶임 → 테스트 자료 수정
- 미실행: 실제 목록 생성(원본 미확보), ② 재생·T2T 근거 조사(3단계)
