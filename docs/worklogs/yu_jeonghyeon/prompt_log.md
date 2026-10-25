# 프롬프트 로그

현재 기록 없음. 아래 항목을 실제 작업 후 추가하세요.

유형 / 실험 ID / 날짜 / 기능 / 모델·설정 / 프롬프트 경로·버전 / 입력·근거 / 실제 출력 / 문제 / 변경 이유 / 제어 / 재검증 / 한계

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

---

## DI-2026_10_25-01 제품소개서 기능 명세 구체화
- 유형: development_instruction
- 날짜/시간: 2026-10-25 05:15 (Asia/Seoul)
- 작업자: 유정현 / 기능: 제품소개서(product_brochure)
- 도구·모델: Claude Code (Opus 5.5). 서비스 모델(OpenAI) 호출 없음
- 프롬프트 경로·버전: 해당 없음(서비스 프롬프트 미작성)
- 지시 요약: 공통 규칙·기존 명세 확인 후, 합의된 기능 방향과 첫 버전 설계안을 feature_spec.md에 확정/제안/미정으로 구분해 정리. 서비스 코드 구현·패키지 설치·OpenAI 호출·Git 변경 금지. 모델·SDK·PDF 라이브러리·상한값·타임아웃·엔드포인트 스키마·실제 제품 수치·정보 부족 정책·4페이지 초과 처리는 임의 확정 금지
- 테스트 입력/근거 자료: 없음(문서 작업)
- 실제 결과: features/product_brochure/feature_spec.md 재작성(목적, 흐름, 입력/출력, 범위, 분석·생성 단계 구분, 근거 검토 방식, 정보 출처 구분, 상태 유지, 오류 사례, 완료 기준, 공통 의존, 미정 항목)
- 발견 문제: 기존 명세 "자사 양식"·"자사 사진 활용" 표현이 합의된 "fionex 출력 양식, 공식 양식 아님"과 다름 → 합의 내용으로 대체하고 보고. docs/decisions.md에는 제품소개서 템플릿·지원 형식·이미지·바이어 입력이 여전히 미정으로 남아 있음(공통 문서, 미수정)
- 서비스 프롬프트 실험: 미실행
- OpenAI 실험: 미실행
- 담당자 판단: 검토 대기
- 남은 한계: 명세의 [제안]·[미정] 항목은 담당자 확인 필요. 기능 미구현

## DI-2026_10_25-02 공통 OpenAI 연결 첫 구현(텍스트 구조화·이미지 1장)
- 유형: development_instruction
- 날짜/시간: 2026-10-25 (Asia/Seoul). 작업 중 "Connection lost mid-response"로 중단 후 같은 날 재개
- 작업자: 유정현 / 범위: 공통(common/ai_client.py 등), 브랜치 feature/openai_common
- 도구·모델: Claude Code (Opus 5.5). 서비스 모델(OpenAI) 호출 없음
- 서비스 프롬프트: 해당 없음(기능별 프롬프트 미작성)
- 지시 요약: 텍스트 → 구조화 결과(Responses API `responses.parse` + Pydantic), 텍스트 프롬프트 → PNG 1장(Images API `images.generate`)의 공통 Python 연결만 구현. 모의 응답으로 검증. 모델은 환경변수(`OPENAI_MODEL`, `OPENAI_IMAGE_MODEL`). timeout 60/180초, max_retries 0, max_output_tokens 4096, store=False(텍스트만). 크기 3종·품질 low/medium/high·PNG. 실제 API 호출·Git 변경 금지
- 확인한 근거: 공식 문서 5개(structured-outputs, image-generation, models/gpt-5.4-mini, models/gpt-image-2.5-sunburst, your-data) 조회 2026-10-25. 설치한 SDK(openai 3.37.0) 시그니처·소스(`responses.parse`, `images.generate`, 예외 계층, parse 단계 검증) 직접 확인
- 중단 전 완료: openai 3.37.0 설치(jasonenv), common/errors.py, common/config.py 작성
- 재개 후 확인: 브랜치·status·diff, 두 파일이 끝까지 작성되어 import되는 것 확인. 남은 python 프로세스 3개는 사용자가 띄운 `app.py`(이번 작업과 무관, 종료하지 않음)
- 재개 후 작성: common/ai_client.py, tests/test_common/test_ai_client.py, requirements.txt, .env.example, docs/data_contracts.md, docs/decisions.md, README.md
- 발견 사항
  - openai 3.37.0의 HTTP 의존성은 httpx가 아니라 httpx2 2.16.0
  - 잘린 JSON은 SDK `responses.parse` 내부에서 pydantic ValidationError가 발생해 `AI_INCOMPLETE`가 아닌 `AI_OUTPUT_INVALID`로 보고됨(문서화)
  - jasonenv에 python-dotenv 1.1.1이 이미 설치되어 있어 Flask app.run / flask run이 `.env`를 자동 로드할 수 있음(requirements에는 없음). README에 명시
  - 공식 이미지 가이드는 Sunburst가 xhigh·max·auto 품질과 사용자 지정 크기도 지원한다고 설명 → 첫 버전 제한은 프로젝트 범위로만 표기
- 서비스 프롬프트 실험: 미실행 / OpenAI 실제 호출: 미실행
- 담당자 판단: 검토 대기
- 남은 한계: 실제 모델 접근 권한·응답 형식·품질·비용 미검증. PDF·스캔 PDF 입력은 후속 작업

## DI-2026_10_25-03 공통 OpenAI 연결 커밋 전 최종 검증·문서 정정
- 유형: development_instruction
- 날짜: 2026-10-25 (Asia/Seoul) / 작업자: 유정현 / 범위: 공통 OpenAI 연결
- 도구·모델: Claude Code (Opus 5.5). 서비스 모델(OpenAI) 호출 없음
- 지시 1(최종 검증): git 상태·diff, `pip check`, 공통 unittest 실행. 패키지·파일 변경 금지
  - Claude 실행 결과: 자동 승인 판정 오류로 Bash 명령이 차단되어 **미실행**. 우회하지 않고 보고함
  - Claude가 파일 읽기로 확인: requirements.txt 직접 의존성 4개 버전 = 설치 dist-info 버전. Flask·python-dotenv 소스로 `.env` 로드 경로 분석 → `common/config.py` docstring이 실제 동작과 다름을 발견
  - 정정: 이전 보고의 "SDK 로그 노출을 막았다"는 표현을 정정함. SDK 로그 억제 코드는 없고, 공통 코드 자체 로그 최소화·예외 체인 제거·`__repr__` 축약만 적용
- 사용자 직접 실행 결과를 전달받음(Claude 미관측): jasonenv python에서 `pip check` → No broken requirements found., unittest → Ran 32 tests in 0.465s OK
- 지시 2(문서·주석): config.py docstring을 "모듈은 .env를 직접 로드하지 않음, Flask 실행 경로·python-dotenv 여부에 따라 로드될 수 있음"으로 수정. README의 `.env` 설명을 소스 기준·실제 로드 미검증으로 수정, 밀려난 안내 문장 위치 복원. 실행 로직·테스트·패키지·환경변수 변경 없음. 테스트 재실행 안 함
- 이번 턴에도 git 확인 명령이 승인 판정 오류로 차단되어 현재 브랜치·변경 상태 미확인
- 서비스 프롬프트 실험: 미실행 / OpenAI 실제 호출: 미실행
- 남은 한계: 실제 OpenAI API 호출·모델 접근·품질·비용, 실제 `.env` 로드 동작 미검증

## DI-2026_10_25-04 공통 OpenAI 연결 실제 호출 결과 기록
- 유형: development_instruction
- 날짜: 2026-10-25 (Asia/Seoul) / 작업자: 유정현 / 범위: 공통 OpenAI 연결(커밋 879f015)
- 도구·모델: Claude Code (Opus 5.5). Claude는 OpenAI API를 호출하지 않음
- 사용자가 직접 실행한 결과를 전달받음
  - `generate_structured`: `message` 필드에 OK 반환 요청 → OK 출력. 모델명·사용량은 전달받지 못함
  - `generate_image`: 프롬프트 "A simple blue circle centered on a plain white background, no text.", 1024x1024, low → `Image OK: image/png 1024 1024 bytes: 756767`. 파일 미저장·육안 미확인
- 지시: 위 결과를 validation.md·prompt_log.md에 후속 검증으로 추가. 기존 미검증 기록 유지, 연결·반환 형식 확인과 업무 품질 검증 구분
- 판단: 연결·반환 형식은 사용자 보고 기준 확인. 업무 품질·비용·소요 시간·스캔 PDF 판독·번역 품질은 미검증
- 서비스 프롬프트 실험: 아님(연결 확인용 단순 요청이며 기능 프롬프트 아님)
- 남은 한계: 사용된 모델 값·응답 모델명·사용량 미확인, 이미지 내용 미확인

## DI-2026_10_25-05 공통 문서 검증 상태 표현 정정
- 유형: development_instruction / 날짜: 2026-10-25 (Asia/Seoul) / 작업자: 유정현
- 변경: docs/data_contracts.md(개요·후속 작업), README.md(현재 단계·기술 기준), docs/decisions.md(공통 OpenAI 연결)의 "실제 OpenAI 호출 미검증"을 "사용자 직접 실행 결과로 실제 호출·반환 형식 확인, 업무 품질·비용·소요 시간·응답 모델명·사용량 미검증, PDF·스캔 PDF 입력 미구현"으로 정정
- 서비스 코드·설정·패키지 변경 없음. API 호출·테스트 재실행 없음

## DI-2026_10_25-06 제품소개서 첫 화면(PDF 선택·결과 확인·수정) 구현
- 유형: development_instruction
- 날짜/시간: 2026-10-25 07:19 (Asia/Seoul) / 작업자: 유정현 / 기능: 제품소개서(product_brochure)
- 도구·모델: Claude Code (Opus 5.5). 서비스 모델(OpenAI) 호출 없음
- 사전 확인: 브랜치 feature/product_brochure, develop 병합 커밋 a619bc6가 origin과 일치, 작업 트리 깨끗, 병합 진행 중 아님. stash@{0}는 건드리지 않음
- 지시 요약: 한국어 PDF 1개 선택 화면과 분석 결과 항목별 확인·수정 화면만 구현. 실제 PDF 분석·OpenAI 호출·카탈로그 생성·PDF 출력 금지, 공통 코드·연결 규약 변경 금지. 분석 버튼 비활성("PDF 분석 연결 준비 중"), 별도 "개발용 예시 불러오기"(자동 불러오기 없음, 분석 결과가 아님을 표시), 항목별 값·제공·가상·사용자 확인을 독립 상태로 구분, 값 수정 시 확인 해제, 미제공 항목 입력은 사용자 추가 정보, 예시 재불러오기·새 PDF 선택 시 수정 내용 보호, 브라우저 저장소 미사용
- 변경: features/product_brochure/templates/product_brochure/panel.html, static/product_brochure.js, static/product_brochure.css, feature_spec.md(§17 추가, 머리말·§12·§16 갱신), tests/test_product_brochure/test_panel.py(신규)
- 설계 판단
  - 파일 입력은 공통 shell 자동 감지, 검토 영역은 `data-work-ignore` + `AppShell.work.setDraft`(수정·확인이 있을 때만). 예시는 결과가 아니므로 `setResult` 미사용
  - 예시에서 가상으로 제공된 MOQ·샘플·납기는 가상 표시 해제 불가, 제공 여부는 사용자가 변경 불가
  - 새 PDF 선택 취소 시 DataTransfer로 이전 파일 선택 복원
  - 상태 로직을 같은 JS 파일 안의 DOM 없는 객체로 분리하고 Node에서만 module.exports로 불러올 수 있게 함
- 서비스 프롬프트 실험: 해당 없음 / OpenAI 호출: 없음
- 담당자 판단: 검토 대기
- 남은 한계: 브라우저 동작 미확인. 분석 API·스키마·파일 상한·추출 항목 확정은 후속

## DI-2026_10_25-07 제품소개서 확인·수정 화면 배치·문구 정리
- 유형: development_instruction / 날짜: 2026-10-25 (Asia/Seoul) / 작업자: 유정현 / 기능: 제품소개서
- 지시 요약: 항목마다 반복되는 안내를 검토 영역 상단으로 모으고, 제품 설명은 넓게, 짧은 항목은 카드 가용 폭이 충분할 때만 2열·좁으면 1열. 확인 체크·가상 표시·기존 로직 유지, 글자 축소·내부 스크롤 금지, 공통 토큰·컴포넌트 재사용
- 변경
  - panel.html: 카드 설명 중복 문장 제거, 상단 "검토 방법"(.notice-info) 4줄 추가
  - product_brochure.js: 항목별 반복 문구(근거 위치·원문 발췌 없음, 체크 라벨의 부연) 제거, 미제공·사용자 추가 안내만 항목별 표시(안내가 없으면 숨기고 aria-describedby 해제), 그룹 항목을 공통 `.grid`로 감쌈, 제품 설명에 전체 폭 클래스
  - product_brochure.css: 항목 간격, 전체 폭 항목, 안내 목록 스타일(모두 `.feature-product_brochure` 범위)
  - feature_spec.md §17 화면 배치 설명 추가
- 상태 로직(Review)·이벤트 처리 변경 없음. 공통 파일·패키지 변경 없음. 테스트 추가 없음
- 서비스 프롬프트 실험: 해당 없음 / OpenAI 호출: 없음
- 남은 한계: 실제 배치·반응형은 브라우저 미확인
