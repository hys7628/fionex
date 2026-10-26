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

## DI-2026_10_25-08 공통 OpenAI 연결 PDF 입력 지원 추가
- 유형: development_instruction
- 날짜/시간: 2026-10-25 08:10 (Asia/Seoul) / 작업자: 유정현 / 범위: 공통(common/ai_client.py 등), 브랜치 feature/openai_common
- 도구·모델: Claude Code (Opus 5.5). 서비스 모델(OpenAI) 호출 없음
- ID 메모: 이 브랜치 기록에는 DI-02~05만 있으나 feature/product_brochure에 DI-01·06·07이 있어 중복을 피해 08 사용
- 사전 확인
  - 1차: HEAD 2d9f4bc, 로컬 develop 05ac128이 HEAD의 조상이 아님(내용은 동일) → 지시대로 수정하지 않고 보고, 사용자 선택으로 중단
  - 2차(사용자가 GitHub Desktop에서 develop 병합 후): HEAD 05ac128 = develop, develop이 HEAD의 조상, 작업 트리 깨끗, 병합 중 아님. 원격 정보는 마지막 fetch 기준. stash@{0} 미조작
  - develop에 다른 팀원의 공통 구현 없음(중복 구현 없음)
- 지시 요약: 기존 텍스트·이미지 함수 유지, PDF 구조화 함수와 PDF 검사(파일 1개·10 MiB·20쪽, 빈 파일·크기·서명·구조·암호화·0쪽·페이지 초과) 추가. base64 data URL input_file 직접 포함, 고정 파일명, Files API·URL 미사용, timeout 120초·재시도 0·max_output_tokens 4096·store=False, detail은 공식 지원 확인 시 high. 실제 API 호출·라우트 구현 금지
- 확인한 근거(2026-10-25 조회)
  - file-inputs 가이드: input_file의 file_data(data:application/pdf;base64,…)·filename, detail auto/low/high·기본 auto·"GPT-5.6 이후 auto=high, 이전 모델 low", PDF 페이지 이미지에만 영향, 비전 지원 모델(gpt-4o 이후 등)은 텍스트+페이지 이미지, 파일당 50 MB 미만·요청 합계 50 MB, 페이지 상한·스캔 PDF 처리 명시 없음
  - gpt-5.4-mini 모델 페이지: 입력 text·image, 기능 file_uploads. PDF·detail 명시 없음 → 간접 판단, 실제 계정 호출 미확인
  - SDK openai 3.37.0 ResponseInputFileParam: file_data·file_id·file_url·filename·detail
  - pypdf: PyPI 6.21.2, BSD-3-Clause, requires_python >=3.9, Python 3.11 분류자, 3.11에서 필수 의존성 없음
- 이전 보고 대조: detail 기본값·5.6 미만 low 설명은 일치. 이전 근거 URL(pdf-files)과 이번 file-inputs 가이드 내용 일치. "gpt-5.4-mini PDF 지원 미확인"은 모델 페이지 기준 여전히 명시 없음
- 설치: jasonenv에 pypdf==6.21.2만 추가(pip freeze 전후 비교에서 pypdf 한 줄만 추가), pip check 정상
- 발견 사항
  - pypdf 6.21.2 PdfReader는 암호화 PDF에 빈 비밀번호로 자동 해제를 시도(_reader.py _handle_encryption) → 해제 전 멈추는 전용 리더 사용(내부 메서드 의존, 버전 고정)
  - pypdf는 헤더 오류 시 "invalid pdf header: b'<앞 5바이트>'"를 경고 로그에 남김 → pypdf 로거 전파 차단(전역 영향 문서화)
  - 처음 작성한 로그 누출 테스트는 전체 비밀 문자열만 찾아 5바이트 누출을 잡지 못함을 대조 실험으로 발견 → 5바이트 표지·경고 문구 검사로 수정하고 차단 해제 시 누출을 확인하는 대조 테스트 추가
  - AES 암호화 테스트 PDF는 cryptography 없이 생성 불가 → RC4만 테스트
- 변경: common/ai_client.py, common/config.py, common/pdf_utils.py, common/errors.py, requirements.txt, docs/data_contracts.md, docs/decisions.md, README.md, tests/test_common/test_pdf.py(신규). .env.example은 새 환경변수가 없어 변경 없음
- 서비스 프롬프트 실험: 미실행 / OpenAI 실제 호출: 미실행
- 담당자 판단: 검토 대기
- 남은 한계: 실제 PDF·스캔 PDF 호출, detail high 동작, 판독 품질·비용·시간 미검증. 업로드 라우트·화면 연결 미구현

## DI-2026_10_25-09 PDF 공통 함수 실제 호출 결과 기록(텍스트 PDF 1회)
- 유형: development_instruction
- 날짜: 2026-10-25 (Asia/Seoul) / 작업자: 유정현 / 범위: 공통 OpenAI 연결(커밋 a7b940e, feature/openai_common)
- 도구·모델: Claude Code (Opus 5.5). Claude는 OpenAI API를 호출하지 않았고 실행 결과를 직접 관측하지 않음
- 사용자가 직접 실행한 결과를 전달받음(jasonenv CMD, `generate_structured_from_pdf` 1회)
  - 응답 모델: gpt-5.4-mini-2026-03-17
  - PDF: PdfInfo(size_bytes=104195, page_count=3). 텍스트 PDF(사용자 보고). 문서 원문·로컬 경로는 기록하지 않음
  - 구조화 결과: {"product_name":"리젠 T2T (regen T2T)","moq_text":"500 kg / 시연용 가상 값","moq_is_virtual":true}
  - 사용량: TokenUsage(input_tokens=10239, output_tokens=46, total_tokens=10285)
- 요청 성격: 연결 확인용 최소 추출(제품명·MOQ·MOQ 가상 여부 3개 필드 스키마). 지시문·스키마 원문은 전달받지 않음. 제품소개서 서비스 프롬프트가 아님
- 지시: 위 결과를 기록하고 README·data_contracts·decisions의 "PDF 실제 호출 미검증" 표현을 확인된 범위만 갱신
- 판단: 해당 모델에서 텍스트 PDF input_file(커밋 기준 detail high, 고정 파일명) 요청이 오류 없이 처리되고 스키마 검증 결과가 반환됨을 사용자 보고로 확인. 추출 2개 항목과 MOQ 가상 표시 구분이 응답에 나타남
- 서비스 프롬프트 실험: 미실행(이번 호출은 연결 확인용)
- 남은 한계: 스캔 PDF 판독, 나머지 항목·전체 문서 정확성, 비용 금액, 소요 시간, detail별 차이, 제품소개서 화면·분석 라우트 연결 미검증·미구현

## DI-2026_10_25-10 제품소개서 PDF 분석 서버(스키마·서비스 프롬프트·API·모의 테스트)
- 유형: development_instruction(코딩 도구 지시). 서비스 프롬프트 brochure_extract_v1은 작성만 했고 service_prompt_experiment는 미실행
- 날짜/시간: 2026-10-25 10:40 (Asia/Seoul) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5). 서비스 모델(OpenAI) 호출 없음
- 사전 확인: HEAD f39a65e(develop 9e2066c 병합 완료), develop이 HEAD의 조상, 작업 트리 깨끗, 병합 중 아님. 마지막 fetch 기준 origin보다 앞섬(push 전). stash@{0} 미조작. 공통 inspect_pdf·generate_structured_from_pdf·오류 클래스·Blueprint 등록을 실제 파일로 다시 읽음
- 지시 요약: PDF 1개 → 8개 항목(key·value·status·evidence·marked_virtual·note)+PDF 정보·모델명·multiple_products·검토 사항. POST /api/product-brochure/analyze, multipart source_file 1개, 10 MiB·20쪽 공통 설정 재사용, request.files 전 요청 전체 제한, 파일은 상한+1바이트만 읽기, 413도 JSON, Werkzeug 임시 파일 확인·정리. 후처리(근거 없는 found 강등, 범위 밖 페이지, 상태 모순, 가상 표시 보존). HTML·CSS·JS·공통 파일·app.py·패키지 변경 금지
- 서비스 프롬프트(features/product_brochure/prompts/brochure_extract_v1.md) 설계 이유와 할루시네이션 제어
  - 업무 지시는 instructions로만 전달, PDF는 입력 데이터(문서 속 명령 무시 명시)
  - 외부 지식·추측 금지, 특히 인증·수치·공급 조건은 PDF 내용만 사용
  - 상태 3단계(found/unclear/not_found)와 found의 근거 필수, 없는 정보는 null
  - 가상·시연 표시 보존(marked_virtual), 다른 제품 정보 이동·복수 제품 병합 금지, 귀속 불명확은 unclear
  - 번역·문구 생성 없음(추출 단계와 생성 단계 분리)
  - 프롬프트만으로 사실 정확성을 보장하지 않으므로 서버 후처리와 사람 확인(confirmed=false)을 함께 둠
- 서버 후처리: 빈 값·유효 근거 없는 found → unclear(ai_status 보존), not_found+값 → unclear, 범위 밖 페이지 표시, 페이지 null은 유효 근거 아님, 중복 key는 후보 값 보존 후 unclear, 누락 key는 unclear로 채움, check="not_checked", 가상 표시 유지
- 실제 실패와 수정
  - 처음 구현에서 request.max_form_memory_size=16 KiB를 지정 → 500 KB 이상 정상 PDF까지 413(UPLOAD_TOO_LARGE)으로 거부됨(테스트 4건 실패)
  - 원인 확인: Werkzeug 문서 문구("파일 파트는 더 클 수 있음")와 달리 3.1.9 MultipartDecoder.receive_data가 파트 종류와 무관하게 수신 버퍼 크기를 이 값과 비교(sansio/multipart.py). 별도 실험으로 재현
  - 수정: max_form_memory_size 재정의 제거(기본 500 KB 유지), 요청 전체 max_content_length와 max_form_parts만 적용. 재실행 후 통과
- Werkzeug 임시 파일: 기본 stream factory가 SpooledTemporaryFile(500 KB)을 사용해 큰 업로드가 OS 임시 파일로 넘어감을 소스와 테스트로 확인 → finally에서 request.close(), 테스트로 닫힘 확인
- 변경: features/product_brochure/routes.py, service.py, prompts/brochure_extract_v1.md(신규), feature_spec.md(§12·§13·§16·§17 후속·§18), tests/test_product_brochure/test_analyze_api.py(신규)
- 서비스 프롬프트 실험: 미실행(실제 PDF로 v1 실행·결과 대조 없음) / OpenAI 실제 호출: 없음
- 담당자 판단: 검토 대기
- 남은 한계: 화면 연결 미구현, 실제 텍스트·스캔 PDF 추출 품질·할루시네이션 발생률·비용·시간 미검증, 근거 원문 대조 미구현

## DI-2026_10_25-11 제품소개서 화면과 PDF 분석 API 연결
- 유형: development_instruction / 서비스 프롬프트 실험: 미실행(OpenAI 호출 없음)
- 날짜/시간: 2026-10-25 10:55 (Asia/Seoul) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 사전 확인: HEAD 0800d51, 작업 트리 깨끗, 병합 중 아님, develop이 HEAD의 조상. stash@{0} 미조작. panel.html·JS·CSS·분석 API 응답 스키마·AppShell.work(app_shell.js) 실제 코드를 다시 읽음
- 지시 요약: PDF 선택 → 분석 요청 → 결과 확인·수정 연결. 10 MiB 화면 검사, 유효 PDF일 때만 분석 버튼, FormData source_file 1개 POST, 교체 확인·취소 시 요청 없음, 진행 중 조작 잠금·aria-busy·중복 방지·오래된 응답 무시, draft 보호(setResult 미사용), 실패 종류별 안전한 안내, 응답 전체 검사 후 한 번에 교체, 상태 매핑(confirmed false·marked_virtual·provided·unclear 보존·not_found 구분), 근거·note·server_notes·candidates·review_notes 표시(textContent). 서버 계약·공통 파일 변경 금지
- 설계 판단과 변경 이유
  - 기존 "사용자 추가" 판정(!provided)은 unclear 값 수정을 "사용자 추가"로 잘못 표시 → 자료 값 유무(sourceValue) 기준으로 변경. 예시 데이터에서는 결과 동일(로직 점검으로 확인)
  - AppShell 입력 자동 감지는 disabled 입력을 건너뜀(app_shell.js panelHasInput) → 분석 중에는 setDraft(true)로 보호하고 끝난 뒤 recheckInputs
  - 분석 결과는 재요청 비용이 있어 수정 전에도 draft로 보호, 예시는 기존대로 수정 시에만
  - candidates가 있으면 값 칸을 비워 단일 확정값처럼 보이지 않게 함
  - 요청 실행기·응답 검사·실패 분류를 DOM 없는 Review 객체로 분리해 Node로 점검
  - 서버 JSON 오류 message는 고정 문장이지만, code 형식(PDF_|AI_|UPLOAD_)·길이 조건을 만족할 때만 표시하고 나머지는 일반 안내. 비JSON 본문은 읽지 않음
- 실제 실패와 수정
  - 정적 테스트가 JS 주석의 "Content-Type" 단어에 걸려 실패 → 헤더 지정 형태(`Content-Type:`)만 검사하도록 수정
  - CSS에 존재하지 않는 토큰 --font-weight-semibold를 썼다가 tokens.css 확인 후 --font-weight-medium으로 수정
- 기록 표현 정정: 직전 작업(DI-10)의 Claude 완료 보고에 "응답·오류·로그에 문서 내용 비노출"처럼 범위를 넓힌 표현이 있었음. 정상 응답에는 추출값·근거 발췌가 들어가는 것이 맞고, 테스트가 확인한 범위는 "오류 응답·로그의 키·문서 표지·공급자 원문·원본 파일명 비노출"과 "성공 요청·응답의 원본 파일명 비포함"임. validation.md의 DI-10 기록 문장은 이 범위와 일치하여 수정하지 않음
- 변경: panel.html, static/product_brochure.js, static/product_brochure.css, feature_spec.md(머리말·§16·§17·§18·§19), tests/test_product_brochure/test_panel.py(갱신), review_logic_check.js·test_review_logic.py(신규)
- 담당자 판단: 검토 대기
- 남은 한계: 브라우저 동작 미확인, 실제 서버·OpenAI 종단 동작 미확인, 추출 품질 미검증

## SPE-2026_10_25-01 제품소개서 서비스 프롬프트 brochure_extract_v1 첫 실제 실행(화면)
- 유형: service_prompt_experiment
- 날짜: 2026-10-25 (Asia/Seoul, 실행 시각은 전달받지 못함) / 작업자: 유정현 / 기능: 제품소개서
- 실행 주체: 사용자(실제 브라우저, 제품소개서 화면 → POST /api/product-brochure/analyze). **Claude는 실행·관측하지 않았고 사용자 보고를 전달받아 기록함**
- 이력: DI-2026_10_25-10·11에 기록한 "서비스 프롬프트 실험 미실행"은 당시 상태로 보존하며, 이 항목이 후속 첫 실제 실행임
- 모델/설정: 응답 모델명·사용량은 전달받지 못함(미확인). 코드 기준 설정은 OPENAI_MODEL, PDF timeout 120초, 재시도 0, max_output_tokens 4096, store=False, detail high(실행 시점 작업 트리 기준, 환경변수 값은 미확인)
- 프롬프트 경로·버전: features/product_brochure/prompts/brochure_extract_v1.md(변경 없음)
- 테스트 입력: 더미 PDF(사용자 제작 시연용 가상 자료로 보고됨). 파일·경로·원문은 기록하지 않음. 텍스트/스캔 여부는 전달받지 못함(미확인)
- 실제 응답: 결과 원문은 기록하지 않음. 사용자 보고 요약만 기록
  - 분석 결과가 화면에 표시됨
  - MOQ·샘플·납기에 가상 정보 표시와 AI 제시 근거가 표시됨
- 발견 문제: 보고된 범위에서는 없음
- 변경 이유·제어 방법·재실행: 해당 없음(첫 실행, 프롬프트 변경 없음)
- 담당자 판단: 연결 확인 수준. 품질 판단 전
- 남은 한계: 8개 항목 전체 정확성(원문 대조), 문서에 없는 값 생성 여부, 스캔 PDF, 비용·소요 시간은 미검증

## DI-2026_10_25-12 제품소개서 화면 브라우저 확인 결과 기록
- 유형: development_instruction / 날짜: 2026-10-25 11:05 (Asia/Seoul) / 작업자: 유정현
- 도구·모델: Claude Code (Opus 5.5). 서비스 코드 수정·API 재호출·테스트 재실행 없음
- 사전 확인: 브랜치 feature/product_brochure, HEAD 0800d51, 병합 중 아님. DI-11 화면 연결 변경은 미커밋 상태로 보존
- 지시: 사용자가 실제 브라우저에서 확인한 결과를 후속 검증으로 기록(Claude 미관측 명시), 서비스 프롬프트 첫 실제 실행을 SPE-2026_10_25-01로 기록, 확인되지 않은 범위는 미검증 유지
- 변경: docs/worklogs/yu_jeonghyeon/prompt_log.md, validation.md

## DI-2026_10_25-13 제품소개서 4페이지 카탈로그 디자인 시안
- 유형: development_instruction / 서비스 프롬프트 실험: 해당 없음 / **AI API 호출 없음(OpenAI·이미지 생성 미호출)**
- 날짜/시간: 2026-10-25 11:16 (Asia/Seoul) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 사전 확인: HEAD dc25bc7(화면 연결 커밋), 작업 트리 깨끗, 병합 중 아님, develop이 HEAD의 조상. stash@{0} 미조작. static/assets·resources/brand·resources/product에는 README만 있어 사용권 확인된 이미지 없음, resources/design/dashboard_reference.png는 화면 참고용이라 미사용
- 지시 요약: 고정 더미 데이터 기반 pt-BR A4 세로 4페이지 카탈로그 미리보기. "디자인 시안 보기" 진입점(카탈로그 생성과 구분), 열고 닫아도 분석 결과·수정값 유지, 미다운로드 결과 상태 만들지 않음. 오프화이트·딥그린, 큰 이미지·명확한 위계·여백, 상투적 아이콘 금지, 텍스트는 HTML, CSS 범위 제한, 새 폰트·CDN·프레임워크 금지, 이미지 없으면 CSS/SVG 패턴과 "실제 제품 사진 아님" 표시. 페이지마다 시연·비공식 안내와 번호, 공급 조건 가상 표시, 연락처·인증·수치 창작 금지
- 설계 판단
  - 공통 tokens.css에 오프화이트·딥그린이 없음 → 조작 UI는 공통 토큰, 카탈로그 문서 영역에서만 지역 팔레트(--catalog-*) 정의(.feature-product_brochure 범위). 토큰 편입 여부는 공통 담당과 추후 결정(보고)
  - 네이티브 dialog(showModal)로 초점 가두기·Esc 닫기, 닫으면 연 버튼으로 초점 복귀, AppShell.onHide로 탭 숨김 시 닫기
  - A4 794x1123 CSS px 페이지를 transform으로 축소해 원래 배치 유지, 화면 맞춤(2쪽/1쪽)·실제 크기 전환, 내부 스크롤
  - CSS 범위 테스트가 @media를 허용하지 않는 구조라 반응형 배치는 JS 배율 계산으로 처리
  - 페이지 넘침을 화면에서 알 수 있도록 scrollHeight 기반 경고 표시
  - 시안 코드는 별도 블록으로 두고 검토 상태·작업 상태 API를 참조하지 않음
- 실제 실패와 수정
  - 셸 heredoc으로 CSS를 추가하려다 따옴표 해석 오류로 실행되지 않음(파일 변경 없음 확인) → Edit 도구로 추가
  - 테스트 1차: 대화상자 설명의 "바이어" 단어가 기존 "바이어 입력 없음" 검사에 걸림 → 문구를 "브라질 시장 제안용"으로 변경(기존 테스트 의도 유지)
  - 테스트 1차: 시안 테스트 클래스가 기존 화면 테스트 클래스를 상속해 기존 테스트가 중복 실행됨 → 공통 준비 클래스(RenderedPanel)로 분리
- 변경: templates/product_brochure/catalog_preview.html(신규), panel.html(진입 카드·include), static/product_brochure.js(시안 블록), static/product_brochure.css(시안 스타일), feature_spec.md(§4 표시·§19 후속 메모·§20), tests/test_product_brochure/test_panel.py(시안 검사 4개·클래스 정리)
- 담당자 판단: 사용자 시각 검토 대기
- 남은 한계: 시각 검증(넓은·좁은 화면·넘침·초점) 미실행, pt-BR 번역 검수 전, 인쇄·PDF 일치 미검증

## DI-2026_10_25-14 카탈로그 시안에 콘셉트 이미지 적용·편집 디자인 개선
- 유형: development_instruction / 서비스 프롬프트 실험: 해당 없음 / **AI API 호출 없음(OpenAI·이미지 생성 미호출, 이미지 재생성·외부 검색 없음)**
- 날짜/시간: 2026-10-25 11:44 (Asia/Seoul) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 사전 확인: HEAD dc25bc7, 병합 중 아님. DI-13 시안 작업 미커밋 상태와 사용자가 추가한 이미지 2개(미추적)를 보존. stash@{0} 미조작
- 이미지 확인: `file`로 PNG 형식·해상도 확인(cover 1024×1536, material 1448×1086), 이미지 보기로 구도 확인(cover: 왼쪽 위 밝은 여백·대각선 곡선·오른쪽 아래 딥그린 / material: 왼쪽 위 실타래·오른쪽 조직·아래 딥그린). 원본 미변경
- 지시 요약: 표지 패턴을 cover 이미지로 교체(밝은 여백에 HTML 제목), 2쪽 비대칭 material 배치, 3쪽 이미지·정보 균형과 "Informações técnicas a confirmar.", 4쪽 숫자 위계 유지·빈 공간 축소·연락처 비노출, 제작 안내·점선 자리표시자는 문서 밖으로, 이미지 쪽마다 AI 콘셉트 안내, object-fit/position·로딩 실패 대체·alt·로드 후 넘침 검사
- 설계 판단
  - 이미지 영역 크기를 CSS로 고정(표지 높이 940px, 2쪽 680×510, 3쪽 340×960, 4쪽 남은 높이) → 로딩 전후 배치가 같아 넘침 검사가 이미지에 좌우되지 않음. 그래도 load·error 때 검사를 다시 실행
  - 2쪽은 4:3 이미지를 크롭 없이 써서 실타래·조직이 모두 보이게 하고, 3쪽은 같은 이미지의 조직 부분 크롭에 "Recorte ampliado da imagem da página 2." 표기
  - AI 안내는 이미지 위가 아닌 종이 바탕에 배치해 가독성 확보
  - 제작 안내는 `<details>` "시안 제작 메모"로 이동, 문서 안에는 가상·비공식 안내만
  - loading="lazy"로 시안을 열 때만 약 5.9 MB 이미지를 불러옴(원본 최적화는 하지 않음)
- 실제 실패와 수정: 이번 작업 중 테스트 실패 없음. 이전 heredoc 문제를 피하려고 CSS 섹션은 스크래치패드 파일로 작성 후 표시줄 이후만 교체
- 변경: templates/product_brochure/catalog_preview.html, static/product_brochure.css(시안 섹션 교체), static/product_brochure.js(이미지 실패·로드 처리), feature_spec.md(§20 1차 표기 정리·§20-2), tests/test_product_brochure/test_panel.py(CSS 패턴 전제 검사를 이미지 요구 검사로 교체), docs/worklogs/yu_jeonghyeon/assets.md(이미지 2개)
- 담당자 판단: 사용자 시각 검토 대기
- 남은 한계: 시각 검증 미실행, 이미지 사용권 조건·생성 설정 미확인, pt-BR 번역 검수 전, 인쇄·PDF 일치 미검증

## DI-2026_10_25-15 pt-BR 카탈로그 문구 생성 서버(스키마·서비스 프롬프트·API·모의 테스트)
- 유형: development_instruction(코딩 도구 지시). 서비스 프롬프트 brochure_generate_v1은 작성만 했고 **service_prompt_experiment는 미실행(OpenAI 실제 호출 없음)**
- 날짜/시간: 2026-10-25 12:04 (Asia/Seoul) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 사전 확인: HEAD cfdb8c4, 작업 트리 깨끗, 병합 중 아님, develop이 HEAD의 조상. stash@{0} 미조작. 공통 generate_structured(instructions·input_text 문자열·schema, timeout 60초·재시도 0), 기존 service.py(FIELD_KEYS·FieldKey), routes.py(analyze만 존재), 화면 상태(userAdded·userModified·source)를 실제 파일로 확인
- 지시 요약: 확인·적용된 8개 항목(JSON) → 4페이지용 구조화 pt-BR 문구. 필수 제품명·설명 confirmed, 미확인·빈 선택 항목 제외, 엄격한 형·key 검증, 길이·본문 한도, 출처·가상 보존·전파, 서버 고정 안내, 출력 상한·key 검증, 빈 페이지 상태, 재시도 없음. HTML·CSS·JS·이미지·공통 파일 변경 금지
- 설계 이유
  - 입력 8개 key 전부 필수: 화면이 항상 8개를 가지므로 누락을 모호하게 두지 않음
  - pydantic strict + extra forbid: "true" 문자열 등 느슨한 변환과 원문·지시문 등 추가 필드 차단. 오류 메시지 위치에서 클라이언트가 보낸 필드명은 "?"로 바꿔 반사 방지
  - 모델 입력에는 사용 항목의 key·라벨·값만. 확인·가상·출처는 서버가 다루므로 모델에 맡기지 않음
  - 제품명은 AI가 만들지 않고 입력 그대로, 가상 표시는 source_keys의 입력 virtual로 서버 계산·전파, 비공식·가상 안내는 서버 고정 문구
  - 3·4쪽은 사용한 key 집합과 정확히 같아야 함(미제공 항목 추가·중복·누락·다른 쪽 항목 거부), 빈 경우 서버가 빈 상태 문구 제공
  - 출력 상한은 프롬프트와 같은 값으로 서버가 검증하고 위반 시 실패(자르지 않음)
  - 숫자·평가 어휘는 review_flags로 표시만(번역 시 1,000/1.000 등 표기 차이로 오탐 가능해 거부 기준으로 쓰지 않음). 정확성 보장 아님
- 할루시네이션 제어: 프롬프트(입력 외 정보·인증·수치·가격·원산지·평가 표현 금지, 입력 속 지시 무시, 짧게) + 입력 축소(사용 항목만) + 출력 key 집합 검증 + 제품명 서버 고정 + 서버 계산 가상 표시 + review_flags + 사람 검토 상태(draft_needs_review)
- 실제 실패와 수정: 이번 작업 중 테스트 실패 없음(신규 14개 첫 실행 통과)
- 변경: features/product_brochure/generation.py(신규), prompts/brochure_generate_v1.md(신규), routes.py(generate 라우트), feature_spec.md(§13 메모·§21), tests/test_product_brochure/test_generate_api.py(신규)
- 담당자 판단: 검토 대기
- 남은 한계: 화면 연결·문구 수정 UI 미구현, 실제 생성 품질·번역 의미·수치 보존 실제 비율·비용·시간 미검증, 무저장 구조라 확인 이력 서버 인증 불가

## DI-2026_10_25-16 카탈로그 생성 API 화면 연결·결과 미리보기
- 유형: development_instruction / 서비스 프롬프트 실험: 미실행 / **실제 생성 API·OpenAI 호출 없음**
- 날짜/시간: 2026-10-25 12:23 (Asia/Seoul) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 사전 확인: HEAD a0bdec4, 작업 트리 깨끗, 병합 중 아님, develop이 HEAD의 조상. stash@{0} 미조작. product_brochure.js 전체(확인 내용 적용·상태 필드 userAdded/userModified/source)·generation.py 계약·시안 템플릿·AppShell.work를 다시 읽음
- 지시 요약: 적용 스냅샷 기반 생성 버튼(조건부 활성)·요청·진행/실패 처리·재생성 확인, 응답 검사 후 4페이지 결과 미리보기(시안과 분리), 이전 결과 경고, draft 보호, 2쪽 간격 축소. 개발용 예시로는 생성하지 않음. 서버·공통 변경 금지
- 설계 이유
  - "확인 내용 적용"이 요약만 저장하던 구조 → 생성 입력 독립 복사본 + 입력 서명 + 입력 버전(파일 교체·새 분석·예시 시 증가)으로 "다시 적용 필요"와 이전 결과 판정을 같은 기준으로 계산
  - 분석 요청 실행기를 createRunner로 일반화해 생성에도 사용(중복·오래된 응답·자동 재시도 없음 동작 공유), 서로 blocked로 동시 실행 차단. 기존 createAnalyzer 동작 유지(Node 점검 13개 그대로 통과)
  - fetch는 공통 postRequest 한 곳. JSON은 Blob(type application/json)으로 보내 Content-Type 헤더를 직접 지정하지 않는 기존 규칙 유지
  - 서버 오류 메시지 대신 알려진 코드 → 화면 고정 안내 표(생성 오류는 서버 메시지에 위치 정보가 들어갈 수 있어 직접 표시하지 않음)
  - 결과 미리보기를 별도 dialog + data-slot으로 만들어 시안 문구와 섞이지 않게 하고, 공통 미리보기 컨트롤러(createPreview)로 배율·넘침 검사·이미지 처리를 공유
  - 화면 JS 요청 본문과 서버 엄격 스키마가 따로 구현되어 어긋날 위험 → Node가 만든 본문을 Python parse_request에 넣는 교차 테스트 추가
- 실제 실패와 수정
  - 구조 변경으로 기존 정적 테스트 4건 실패(dialog 수 1→2, 처음 비활성 버튼 3→4, 주석의 "setResult" 글자, 분석 전용 fetch 위치 검사) → 각 테스트의 보호 의도를 유지한 채 새 구조 기준으로 수정(setResult는 호출 형태만 검사, 요청은 fetch 1곳·URL 2개·run 각 1곳)
  - 결과 템플릿 초안에서 빈 상태 문구 칸이 hidden 상자 안에 있어 표시될 수 없는 구조였음(코드 검토로 발견) → 상자 자체를 slot으로 바꾸고 JS가 내용·hidden을 함께 설정
- 변경: static/product_brochure.js, templates/product_brochure/panel.html, templates/product_brochure/catalog_preview.html(결과 dialog 추가), static/product_brochure.css, feature_spec.md(§21 메모·§22), tests/test_product_brochure/test_panel.py, review_logic_check.js, test_review_logic.py
- 담당자 판단: 브라우저 확인 대기
- 남은 한계: DOM·시각 미확인, 상한 길이 배치·넘침 미확인, 생성 품질 미검증, 생성 문구 편집·PDF 다운로드 미구현

## SPE-2026_10_25-02 카탈로그 생성 프롬프트 brochure_generate_v1 실제 실행(화면)
- 유형: service_prompt_experiment
- 날짜: 2026-10-25 (Asia/Seoul, 실행 시각은 전달받지 못함) / 작업자: 유정현 / 기능: 제품소개서
- 실행 주체: 사용자(실제 화면에서 생성 → 결과 미리보기). **Claude는 호출·관측하지 않았고 사용자가 전달한 화면 정보를 기록함**
- 이력: DI-2026_10_25-15·16의 "v1 실험 미실행"은 당시 상태로 보존하며, 이 항목이 v1의 후속 첫 실제 실행
- 모델/설정: 응답 모델 gpt-5.4-mini-2026-03-17(전달받음). 코드 기준 설정 timeout 60초·재시도 0·store=False·max_output_tokens 4096
- 프롬프트: features/product_brochure/prompts/brochure_generate_v1.md(실행 당시 버전, 이후 수정하지 않고 v2 생성)
- 입력: 사용자가 적용한 제품 정보(원문·생성 결과 전문은 기록하지 않음). 원본 제품명은 한글·라틴 혼합 표기
- 관측(사용자 전달): 실제 결과 미리보기 표시됨
- 발견 문제(유형)
  - 표지 제품명에 한글 원본 표기 노출(v1 규칙 "입력 표기 그대로"의 결과)
  - 샘플 조건이 평가용 샘플 요청 의도와 달리 "revisão de amostra"(수정·개정 의미)로 번역됨
  - 표지 소개 문구와 2쪽 소개 문단이 거의 반복
- 변경 이유·제어 방법: DI-2026_10_25-17(표시명 분리·서버 한글 검사·반복 검토 표시·프롬프트 v2)
- 재실행 결과: v2 실제 실행 미실행
- 담당자 판단: 수정 필요(이번 작업으로 반영)
- 남은 한계: 전체 번역 정확성, 다른 항목 문구, 페이지 넘침, 비용·소요 시간 미검증

## DI-2026_10_25-17 카탈로그 표시명 분리·언어 검사·생성 프롬프트 v2
- 유형: development_instruction / 서비스 프롬프트 v2 작성, **v2 실제 실행(service_prompt_experiment)은 미실행** / 실제 API 호출 없음
- 날짜/시간: 2026-10-25 12:42 (Asia/Seoul) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 사전 확인: HEAD f4e5083, 작업 트리 깨끗, 병합 중 아님. stash@{0} 미조작. generation.py·brochure_generate_v1.md·화면 생성 로직을 실제로 다시 읽음
- 지시 요약: SPE-02 문제 수정. 원본 제품명 보존 + 카탈로그 표시명(display_name) 별도 입력·확인·검증(빈 값·길이·한글), 명확한 라틴 후보만 제안, 서버가 표지에 그대로 사용. 문서 문자열 한글 잔존 서버 검사(위치만 반환), 샘플 표현·표지/소개 역할 프롬프트 개선, 프롬프트 버전 갱신
- 결정 변경과 이유: §21 "표지 제품명 = 입력 표기 그대로" → 확인한 표시명 사용. 원본 그대로 쓰면 pt-BR 카탈로그에 한국어 원본이 노출됨(SPE-02). 원본은 분석·검토 화면과 요청 product_name에 그대로 보존
- 설계 이유
  - 표시명 후보는 "한글 + 괄호 안 라틴 표기 1개 + 괄호 밖 라틴 단어 포함 관계"처럼 명확할 때만 제안. 괄호 속 문구 무조건 선택·한글 삭제·영문명 창작을 피함
  - 모델 입력의 product_name을 표시명으로 대체해 원본 한글이 생성 문구로 들어갈 경로 축소
  - 한글 잔존은 거부(502)하되 원문을 지우지 않고 위치만 안내. 반복은 정상 반복과 구분이 어려워 검토 표시만
  - v1은 실험 기록이 있어 수정하지 않고 v2 새 파일 생성(recording_rules)
- 할루시네이션·언어 제어: 프롬프트(한국어 금지, 표시명 그대로, 샘플 avaliação 의미, 무상·즉시·재고 보장 금지, 표지/소개 역할, 새 특징 금지) + 서버 한글 검사 + 표시명 서버 고정 + repeated_text 표시 + 사람 검토 초안 상태
- 실제 실패와 수정: 요청 계약 변경(display_name 필수)으로 기존 테스트 31건 실패·2건 오류 → 테스트 준비 코드(요청 본문·Node 고정 데이터·교차 테스트)를 새 계약에 맞게 갱신. 이후 프롬프트 버전 기대값(v1→v2) 1건 갱신
- 변경: generation.py, prompts/brochure_generate_v2.md(신규), static/product_brochure.js, templates/product_brochure/panel.html, feature_spec.md(§21 표시·§23), tests/test_product_brochure/test_generate_api.py·review_logic_check.js·test_review_logic.py
- 남은 한계: v2 실제 번역·반복 개선 미검증, 표시명 입력 DOM 미확인, 페이지 넘침·비용·시간 미검증

## SPE-2026_10_26-01 카탈로그 생성 프롬프트 brochure_generate_v2 실제 실행(화면, 재실행)
- 유형: service_prompt_experiment
- 날짜: 2026-10-26 (Asia/Seoul, 실행 시각은 전달받지 못함) / 작업자: 유정현 / 기능: 제품소개서
- 실행 주체: 사용자(실제 화면에서 생성 → 결과 미리보기). **Claude는 호출·관측·검증하지 않았고 사용자 보고를 전달받아 기록함**
- 이력: DI-2026_10_25-17의 "v2 실제 실행 미실행"과 SPE-2026_10_25-02(v1 문제 발견)는 당시 상태로 보존하며, 이 항목이 v2의 후속 첫 실제 실행
- 모델/설정: 응답 모델명·사용량 전달받지 못함(미확인). 코드 기준 설정은 커밋 cf81010(timeout 60초·재시도 0·store=False·max_output_tokens 4096)
- 프롬프트: features/product_brochure/prompts/brochure_generate_v2.md
- 입력: 사용자가 적용한 제품 정보와 확인한 카탈로그 표시명(원문·생성 결과 전문은 기록하지 않음)
- 비교 기준: SPE-2026_10_25-02(v1)에서 발견한 세 문제. 같은 입력이었는지는 전달받지 못함(미확인)
- 관측(사용자 보고, 세 항목 모두 정상)
  1. 표지 제품명이 한글 없이 "regen T2T"로 표시됨(표시명 분리, 제어: 서버가 확인된 display_name 사용)
  2. 샘플 문구가 평가용 샘플 요청 의미로 표현됨(제어: v2 프롬프트 샘플 표현 지침)
  3. 표지 소개와 2쪽 설명이 그대로 반복되는 문제가 개선됨(제어: v2 표지/소개 역할 구분 지침, repeated_text 검토 표시)
- 재실행 결과: v1 대비 위 세 문제는 이번 실행에서 정상으로 보고됨
- 담당자 판단: 세 문제는 이번 실행 기준 해결로 보고
- 남은 한계: 응답 모델명·사용량·비용·소요 시간 미확인, 전체 번역 정확성·다른 항목 문구·페이지 넘침 미검증, 다른 입력에서도 같은 품질이 유지되는지 미검증(1회 실행)

## DI-2026_10_26-01 v2 실제 실행 결과 기록
- 유형: development_instruction / 날짜: 2026-10-26 00:40 (Asia/Seoul) / 작업자: 유정현
- 도구·모델: Claude Code (Opus 5.5). 서비스 코드 수정·API 재호출·테스트 재실행 없음
- 사전 확인: 브랜치 feature/product_brochure, HEAD cf81010, 작업 트리 깨끗, 병합 중 아님
- 지시: 사용자 보고 v2 실행 결과를 SPE-2026_10_26-01로 기록(사용자 보고·Claude 미검증 명시), 기존 미실행·실패 기록 보존, 미확인·미검증 범위 유지
- 변경: docs/worklogs/yu_jeonghyeon/prompt_log.md, validation.md

## DI-2026_10_26-02 생성 결과 문구 편집·4쪽 "샘플·거래 상담" 정리
- 유형: development_instruction / **서비스 프롬프트 변경 없음, 실제 API 실험 없음**
- 날짜/시간: 2026-10-26 00:48 (Asia/Seoul) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 사전 확인: HEAD 4398d95, 작업 트리 깨끗, 병합 중 아님. stash@{0} 미조작. 생성 API 계약·표시명 처리·입력 스냅샷·결과 미리보기·이전 결과 경고·AppShell.work 실제 코드 확인. 서버 출력 상한(generation.py)을 실제 값으로 확인해 편집 검증에 사용
- 지시 요약: 결과 문구 편집(표시명·소개·문단·3/4쪽 값), 원본·적용본·임시 값 분리, 적용(전체 검증·일괄 반영)·취소·원문 복원, 서버와 같은 길이·한글·제어 문자 검사, 사용자 수정 · 재검토 필요 표시, 메타데이터·고정 안내 보존, 재생성 확인, 탭 이동 보존, 4쪽 제목·중립 마무리. 서버·프롬프트 변경 금지
- 설계 이유
  - 편집본은 응답 데이터 구조를 그대로 복제하고 텍스트·값 칸만 교체 → 렌더링 코드 재사용, 메타데이터 자동 보존
  - 사용자 수정 위치는 데이터에 넣지 않고 원본과 비교해 계산(editedIds) → 손으로 원래 문구로 되돌리면 수정 표시도 사라짐
  - 표시명 편집은 결과 적용본의 display_name과 cover.product_name을 함께 갱신, 생성 요청용 표시명·스냅샷은 별도 유지
  - 미리보기 공통 컨트롤러에 beforeClose를 추가해 닫기·Esc만 확인하고, 탭 숨김 닫기는 확인 없이 임시 값 보존
  - 재생성 확인 문구를 상황별로 바꾸도록 요청 실행기에 confirmMessage 선택 의존성 추가(기존 동작 유지)
  - maxlength를 쓰지 않아 붙여넣기 시 조용히 잘리지 않게 함
- 4쪽: 제목 "Amostras e condições comerciais", 마무리 상담 문구(번역 검수 전). 고정 시안의 "Disponível mediante solicitação" 등 제공 약속 표현과 도착일로 오해될 수 있는 납기 설명 조정
- 실제 실패와 수정
  - 정적 테스트: 처음 비활성 버튼 수 4→5("AI 생성 원문으로 되돌리기") → 개수와 함께 버튼 이름을 확인하도록 수정
  - Node 점검 1건: 고정 데이터의 원래 소개 문구가 이미 HTML 형태 문자열이라 같은 값 입력이 "수정 아님"으로 계산됨(로직은 정상) → 테스트 값을 원본과 다르게 수정
- 변경: static/product_brochure.js, static/product_brochure.css, templates/product_brochure/catalog_preview.html, feature_spec.md(§23 후속 메모·§24), tests/test_product_brochure/test_panel.py·review_logic_check.js
- 남은 한계: 편집 UI DOM·시각 미확인, 편집 후 넘침 실제 표시 미확인, pt-BR 문구 검수 전

## DI-2026_10_26-03 카탈로그 PDF 렌더러(ReportLab) 구현·모의 데이터 검증
- 유형: development_instruction / **서비스 프롬프트 실험 없음, 실제 API 호출 없음**
- 날짜/시간: 2026-10-26 01:32 (Asia/Seoul, 기록 시각) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 선행: 같은 날 PDF 다운로드 사전 점검(파일 수정 금지 지시로 당시 기록하지 않음). ReportLab 추천, 팀 결정 확인
- 사전 확인: HEAD 63b1ac0, 작업 트리 깨끗, 병합 중 아님, stash@{0} 미조작. generation.current 구조·편집 검증·4쪽 템플릿·CSS·이미지·고정 안내를 다시 읽음
- 지시 요약: reportlab==5.1.0 설치, 기능 폴더에 글꼴 임시 배치, pdf_catalog.py 렌더러(구조화 입력만, 서버 상수 안내, 넘침·자산 오류, 4쪽 확인), 가상 데이터 검증 PDF, 라우트·화면 연결 금지
- 설치: jasonenv(C:\Users\user\miniforge3\envs\jasonenv\python.exe, 3.11.17)에 reportlab 5.1.0·pillow 13.0.0(green_claim 브랜치와 같은 버전)·charset-normalizer 3.5.2 추가. dry-run으로 위 3개만 설치됨을 먼저 확인, 그 밖의 패키지 변경 없음(pip freeze 전후 비교), pip check 이상 없음
- 설계 이유
  - 입력은 화면 편집본 pages 구조에서 문구·key·virtual만. 항목명·안내는 서버 상수 → 임의 HTML·문구 주입 방지
  - 브라우저와 다른 렌더러라 화면 CSS px 값을 상수로 옮기고 측정 기반 넘침 검사(자르지 않음)
  - 글꼴은 ReportLab 전역 등록부 충돌을 피하려 다른 기능과 다른 이름(PBCatalogSans)으로 등록, 렌더링 시점 등록(앱 시작 무관)
  - 이미지는 PNG 그대로면 PDF 약 8.9 MB·2초 → 메모리 JPEG(품질 88)로 약 0.88 MB·0.2초
- 실제 실패와 수정
  - 첫 생성 PDF 8.9 MB → JPEG 포함으로 변경
  - "문단 2×600자" 넘침 예시가 실제로는 들어감(축소 배치) → 경계 통과 예시로 바꾸고 3쪽 상세 넘침 예시 추가
  - 4쪽은 상한 이내 값으로 넘침이 나지 않음(마무리 영역 약 440px 남음) → 최소 높이를 올린 모의로 검사 동작만 확인
  - 소스 검사 테스트가 문서 문자열 단어·PIL Image.open을 잡음 → AST 기반으로 수정
  - 기본 Helvetica 참조가 남음 → 초기 글꼴을 내장 글꼴로 지정
  - 검증 PDF 폴더를 비우려던 rm 명령이 안전 경고로 거부됨(실행 안 됨, 파일 6개 그대로 확인). 이후 삭제 없이 새 폴더·덮어쓰기 금지(xb)로 생성
  - Edge headless 스크린샷으로 쪽 렌더링 시도 → 빈 화면(PDF 뷰어 미렌더) → 시각 검증 미실행으로 남김
- 변경: features/product_brochure/pdf_catalog.py(신규), fonts/(신규 3파일), feature_spec.md §25, requirements.txt(reportlab·pillow), tests/test_product_brochure/test_pdf_catalog.py·pdf_fixtures.py·make_pdf_samples.py(신규)
- 남은 한계: 쪽별 육안 확인 전, 화면 미리보기 라벨(AI)과 PDF 라벨(상수) 불일치 [미정], 다운로드 API·동시 실행 제한 미구현

## DI-2026_10_26-04 카탈로그 PDF 가로 넘침·글자 잘림 수정
- 유형: development_instruction / **서비스 프롬프트 실험 없음, OpenAI 호출 없음**
- 날짜/시간: 2026-10-26 01:48 (Asia/Seoul, 기록 시각) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 사전 확인: HEAD c8b076b(렌더러 커밋), 작업 트리 깨끗, 병합 중 아님, stash@{0} 미조작
- 계기(외부 전달, Claude 미관찰): 사용자가 ChatGPT로 catalog_base.pdf·catalog_max_paragraphs.pdf 8쪽을 렌더링해 확인 — 1쪽 정상, 2쪽 본문이 오른쪽 경계에서 잘림(긴 문단형은 여러 줄이 쪽 밖), 3쪽 일부 문장 오른쪽 여백 침범, 4쪽 상담 문구 일부 영역 이탈
- 원인 확인(Claude 직접): 2쪽 내용 스트림에 `1.469446 Tc`(머리말 자간 0.14em)가 q/Q 밖에 기록되고 이후 BT 블록이 Tc를 다시 설정하지 않음. PDF 글자 간격은 그래픽 상태라 BT/ET로 초기화되지 않아, 같은 쪽의 이후 본문·하단 쪽 번호가 글자마다 약 1.47pt 넓게 그려짐. 줄바꿈 측정(Paragraph)은 자간 0 기준이라 불일치. Tw·Tz는 사용 안 함, 글꼴·크기·좌표(cm은 q/Q 안)는 일치. 쪽이 바뀌면 상태가 초기화되므로 머리말 이전에 그린 문구(1쪽 이미지 띠·3쪽 캡션)는 영향 없음
  - 1쪽도 표지 머리말 자간이 제목에 남아 제목 줄이 표지 문구 칸(504px)을 4.6px 넘었음(외부 보고에는 "정상", 쪽 경계 안이라 눈에 띄지 않았던 것으로 보임)
- 수정: 머리말 그리기를 saveState/restoreState로 가두고 끝에 setCharSpace(0), 하단 안내도 상태 격리 + charSpace=0 명시. 머리말 폭(자간 포함)이 영역을 넘으면 넘침 오류. 배치·글자 크기·문구 변경 없음(자르기·축소 없음)
- 회귀 테스트: tests/test_product_brochure/pdf_geometry.py(내용 스트림의 q/Q·cm·Tc·Tw·Tz·Tf·Tm/Td/T*와 글꼴 /Widths로 실제 줄 폭 계산) + GeometryTests 3개(쪽별 영역 대조 7개 예시, 2쪽 본문 줄 폭 = 글꼴 측정 폭·Tc가 q/Q 밖에 없음, 긴 단어 줄바꿈 시 글자 누락 없음). 새 예시 wide_words(띄어쓰기 없는 긴 단어·악센트·기호·URL 형태)
- 수정 전 재현: HEAD 버전 pdf_catalog.py를 저장소 밖에 복사해 같은 테스트 실행 → 영역 검사 실패(1쪽 제목 508.6px), 줄 폭 검사 실패(2쪽 첫 줄 592.2pt vs 측정 482.0pt). 수정 전 측정: 2쪽 최대 x 644.0pt(기본)·666.5pt(긴 문단), 쪽 폭 595.3pt
- 테스트 실패와 수정(작성 중): 줄 폭 테스트가 캡션 줄을 본문으로 잘못 고름 → 글꼴 크기로 본문 줄 선택
- 변경: features/product_brochure/pdf_catalog.py, feature_spec.md §25 후속 메모, tests/test_product_brochure/test_pdf_catalog.py·pdf_fixtures.py·make_pdf_samples.py, pdf_geometry.py(신규)
- 이전 기록(DI-2026_10_26-03·validation의 103개 통과)은 당시 상태로 보존. 당시 테스트는 텍스트·페이지 수·자체 측정만 확인해 실제 그려진 폭의 누적 자간을 잡지 못했음
- 남은 한계: 수정 후 쪽별 육안 확인 미실행(렌더링 도구 없음)

## DI-2026_10_26-05 카탈로그 PDF 다운로드 API 연결(서버·테스트)
- 유형: development_instruction / **서비스 프롬프트 변경·실험 없음, OpenAI 호출 없음**
- 날짜/시간: 2026-10-26 02:03 (Asia/Seoul, 기록 시각) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 사전 확인: HEAD 7b38daf, 작업 트리 깨끗, 병합 중 아님, develop 로컬·원격 존재(이번 작업에 사용하지 않음), stash@{0} 미조작. routes.py·pdf_catalog(parse_catalog/build_pdf·오류 클래스)·generation 구조·기존 API 테스트 패턴을 읽고 재사용
- 이전 작업 후속(외부 전달, Claude 미관찰): 사용자가 ChatGPT로 수정 후 기본형·긴 문단형·긴 단어형 PDF 3개(12쪽)를 렌더링해 확인 — 글자 잘림·의도하지 않은 겹침 없음, 긴 문단·가상 안내가 하단 안내와 겹치지 않음, 긴 단어 줄바꿈·악센트·특수문자 표시 확인. 실제 생성·편집 결과 다운로드, 다른 뷰어·인쇄는 미검증
- 지시 요약: POST /api/product-brochure/pdf, {"catalog": parse_catalog 계약}, 라우트 전용 32 KiB, 일관된 JSON 오류, 렌더러 오류 코드 유지, 고정 파일명·no-store, 동시 렌더링 프로세스당 2건·즉시 429, 화면 연결 금지
- 설계 이유
  - catalog 내부는 기존 parse_catalog를 그대로 쓰고 최상위만 별도 검사(중복 스키마 없음)
  - 형식 검사를 슬롯 획득 전에 해 잘못된 요청이 렌더링 자리를 차지하지 않게 함(build_pdf도 다시 검사)
  - 응답은 완성된 bytes를 Response로 반환해 버퍼 수명 문제를 없앰(send_file+BytesIO 대신)
  - 예상하지 못한 오류는 CatalogPdfRenderError의 고정 문구, 로그에는 예외 종류만
- 실제 실패와 수정(테스트 작성 중)
  - 파일명 테스트용 표시명이 표지 칸보다 긴 한 단어여서 422(렌더러 넘침 검사 정상 동작) → 짧은 단어 값으로 교체
  - 라우트 소스 검사 금지어 "exc)"가 type(exc).__name__에 걸림 → 예외 원문 노출 패턴(str(exc·repr(exc·exc_info 등)으로 수정
- 변경: features/product_brochure/routes.py, pdf_download.py(신규), feature_spec.md §26, tests/test_product_brochure/test_pdf_download_api.py(신규)·test_pdf_catalog.py(라우트 미연결 단언 제거, 소스 검사 대상에 pdf_download 추가)
- 남은 한계: 화면 다운로드 미구현, 여러 워커 전역 동시 제한 없음, 렌더링 강제 시간 제한 없음

## DI-2026_10_26-06 화면 "PDF 다운로드" 버튼 연결
- 유형: development_instruction / **서비스 프롬프트 변경·실험 없음, OpenAI 호출 없음**
- 날짜/시간: 2026-10-26 02:17 (Asia/Seoul, 기록 시각) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 사전 확인: HEAD b63ae74, 작업 트리 깨끗, 병합 중 아님, stash@{0} 미조작. app_shell.js의 work API(downloadBlob → markDownloadRequested가 inputs·draft·result 모두 해제, setDraft는 downloadRequested 해제), product_brochure.js의 generation·editing·syncWork·createRunner, pdf_download.py·parse_catalog 계약을 실제 코드로 확인
- 지시 요약: 적용된 최신 편집본으로 PDF 다운로드, 가능 조건(결과·미적용 편집·진행 중), 이전 결과 확인창, 허용 필드만 요청, 32 KiB 사전 검사, 30초 대기, MIME·서명 확인, 고정 파일명, 오류 매핑, 결과 버전별 다운로드 표시, 이탈 보호 재반영, 화면 항목명을 PDF 상수로 정렬, ResourceWarning 보고 표현 확인
- 설계 이유
  - 기존 공통 실행기(createRunner)를 재사용해 중복 방지·오래된 응답 무시·재시도 없음 규칙을 분석·생성과 같게 유지
  - 결과 버전(resultRevision)을 생성·편집 적용·원문 복원마다 올려 다운로드 표시가 이후 내용에 붙지 않게 함
  - downloadBlob이 탭 보호를 모두 해제하는 공통 계약이라, 공통 파일을 바꾸지 않고 직후 recheckInputs·syncWork로 재반영
  - 버튼을 미리보기 카드로 옮겨 결과 보기와 같은 위치에서 대상(생성 결과)을 분명히 함
- 실제 실패와 수정
  - Python heredoc 일괄 수정 명령이 셸 따옴표 오류로 실행되지 않음(변경 0 확인) → Edit 도구로 개별 수정
  - test_panel 3건 실패: 새 테스트가 시안에 없는 항목명을 기대(시안은 4쪽 항목명만 있음) → 기대값 수정. 이전 단계 규칙("downloadBlob 없음", "fetch 1곳", "arrayBuffer 금지")이 남아 실패 → 현재 규칙(성공 경로 downloadBlob 1회, fetch 2곳, 응답 서명 확인용 arrayBuffer 1곳만)으로 갱신
  - downloadBlob 개수 검사가 주석의 단어까지 셈 → 호출 형태 "downloadBlob("로 수정
- ResourceWarning 보고 정정(DI-2026_10_26-05·validation 해당 항목): "-W error::ResourceWarning 전체 실행 통과"는 GC 정리 중 발생한 ResourceWarning이 "Exception ignored"로 출력될 뿐 테스트를 실패시키지 않는 상태였음(경고 0건이라는 뜻 아님). "기존 경고 10건"은 경고 줄+"Enable tracemalloc" 줄을 함께 센 줄 수였고 실제 경고는 5건. 파일별 -W always 측정에서 5건 모두 test_analyze_api.py, PDF 테스트 파일은 0건
- 변경: static/product_brochure.js, static/product_brochure.css, templates/product_brochure/panel.html, feature_spec.md §27, tests/test_product_brochure/review_logic_check.js·test_panel.py·test_review_logic.py
- 남은 한계: 브라우저 DOM·실제 저장 미확인, 공통 탭 상태 표시가 "다운로드 요청됨" 대신 보호 상태로 보일 수 있음(공통 계약 그대로)

## DI-2026_10_26-07 PDF 다운로드 이전 결과 확인창 미표시 보고 조사
- 유형: development_instruction / **서비스 프롬프트 변경·실험 없음, OpenAI 호출 없음**
- 날짜/시간: 2026-10-26 02:40 (Asia/Seoul, 기록 시각) / 작업자: 유정현 / 기능: 제품소개서 / 브랜치 feature/product_brochure
- 도구·모델: Claude Code (Opus 5.5)
- 사전 확인: HEAD a6d4fe9, 작업 트리 깨끗, 병합 중 아님, stash@{0} 미조작
- 사용자 보고(Claude 미관찰): 생성 결과가 있는 상태에서 분석·검토 화면 MOQ 단위 kg 수정 → PDF 다운로드 → "현재 입력과 다를 수 있습니다" 확인창 없이 다운로드됨
- 코드 확인: 입력 칸 input → setValue → changed() → syncGenerate·syncResultStatus·syncPdf. 다운로드 클릭 시 needsConfirm이 isResultStale(generation, generationContext())를 매번 계산하고, generationContext의 currentSignature는 현재 fields·표시명으로 새로 만든 서명(마지막 적용 스냅샷이 아님). 생성 결과의 signature는 생성 당시 적용 스냅샷 서명
- 직접 재현(Claude): 로컬 서버(FLASK_SKIP_DOTENV=1, OPENAI_API_KEY 비움, 포트 5091)와 Edge headless를 CDP(Node 24 내장 WebSocket)로 조작. 분석·생성 API는 브라우저에서 가로채 모의 응답, PDF는 실제 서버 렌더러. 스크립트: 저장소 밖 C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Desktop-fionex\36d7c2bf-67d2-469c-9a14-643e83056de0\scratchpad\cdp_repro\repro.mjs
  - 시나리오별(취소 후 PDF 요청/다운로드 → 확인 후): moq 합성 입력 "500 kgs" 0/0 → 1/1, moq 실제 키 입력(Backspace·문자 입력)+실제 마우스 클릭 "500 KG" 0/0 → 1/1, 실제 키로 원래 값 "500 kg" 복원 0/0 → 1/1(값 변경 때 확인 해제됨), 제품 설명·표시명·확인 해제 모두 0/0 → 1/1, 모든 경우 확인창 문구 일치. 결과 문구 편집·적용만: 확인창 0회, 바로 다운로드
  - 결론: 현재 코드에서 보고 증상 재현 안 됨. 원인 미확인이므로 코드 수정하지 않음(추측성 변경 회피)
  - 서버 로그: 분석·생성 요청 0건(모두 브라우저에서 가로챔), PDF 요청 200만 기록. 강제 종료로 로그가 일부 누락된 것으로 보임(실행 횟수보다 적은 16줄)
  - 정적 JS 응답은 Cache-Control: no-cache(오래된 스크립트 캐시 가능성 낮음)
- 가능성(미확인): 결과 대화상자 "문구 수정"의 4쪽 MOQ 값을 고친 경우(정상적으로 확인창 없음), 수정 뒤 "확인 내용 적용"과 "카탈로그 생성"까지 진행해 새 결과가 된 경우, 이전 코드로 실행 중이던 서버·탭. 사용자에게 정확한 단계 확인 필요
- 변경: tests/test_product_brochure/review_logic_check.js(회귀 2개), test_panel.py(이벤트 연결·판정 재사용 정적 검사 1개), feature_spec.md 후속 메모. JS·서버 변경 없음
- 실제 실패와 수정: 정적 검사에서 isResultStale 호출 수를 3으로 예상했으나 실제 4곳(결과 대화상자 경고 포함) → 기대값 수정
- 남은 한계: 사용자 환경의 정확한 재현 단계 미확인, 실제 사용자 브라우저(창 모드)에서 미확인

### DI-2026_10_26-07 후속(원인 확인, 사용자 보고)
- 사용자 확인: MOQ를 바꾼 위치는 분석·검토 화면이 아니라 "생성 결과 보기 → 문구 수정 → 미리보기에 적용"이었음
- 결론: 결과 문구 편집·적용만으로는 입력 불일치 확인창을 띄우지 않는 것이 명세(§24·§27)대로의 정상 동작. 기존 보고의 원인은 편집 위치 혼동으로 확인됨(위 "가능성" 1번과 일치). 코드 결함 아님, 서비스 코드 변경 없음
- 남은 확인: 결과 편집으로 바꾼 MOQ 값이 내려받은 PDF에 반영됐는지는 사용자 확인 전(Claude는 모의 데이터로 요청 본문에 수정본 값이 들어가는 것만 확인)
