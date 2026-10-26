# 검증 기록

현재 기록 없음. 아래 항목을 실제 작업 후 추가하세요.

날짜 / 변경 내용 / 검증 절차 / 기대 / 실제 / 판정 / 미검증

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

---

## 2026-10-25 제품소개서 기능 명세 구체화 (문서 검토)
- 변경 내용: features/product_brochure/feature_spec.md 재작성
- 검증 절차: 수정 명세를 README.md, AGENTS.md, docs/decisions.md, docs/development.md, docs/design_system.md, docs/data_contracts.md, docs/recording_rules.md와 수동 대조
- 기대/실제
  - 공통 규칙 일치(로그인·영구 저장·탭 간 연동 없음, 메모리 유지·새로고침 미복원, AppShell.work 사용, 서버 측 OpenAI 호출, 오류 응답 형식, 사용자 자료 비저장): 일치 확인
  - 확정/제안/미정 구분: 항목마다 [확정]/[제안]/[미정] 표기 확인
  - 미구현 기능을 완료로 표현하지 않음: 상태·검증 현황·오류 사례·완료 기준을 미구현/미실행으로 표기 확인
  - 금지 항목 임의 확정 여부(모델·SDK·PDF 라이브러리·상한·타임아웃·재시도·비용·엔드포인트 스키마·실제 제품 수치·정보 부족 정책·4페이지 초과·이미지 없을 때 배치): 모두 [미정]으로 표기 확인
- 판정: 문서 검토 통과(사람 최종 검토 전)
- 불일치·조율 필요: docs/decisions.md의 제품소개서 미정 항목 갱신 필요(공통 문서라 미수정). 회사명 표기 "효성티앤씨"(decisions.md)와 "효성TNC"(지시) 병기
- 미검증: 앱 실행·API 호출·PDF 출력·브라우저 동작(이번 작업은 문서만 수정하여 실행하지 않음)

## 2026-10-25 공통 OpenAI 연결 첫 구현 (모의 테스트)
- 변경 내용: common/ai_client.py, common/config.py, common/errors.py, tests/test_common/test_ai_client.py
- 환경: Conda jasonenv, Python 3.11.17, openai 3.37.0, pydantic 2.14.1, httpx2 2.16.0, Flask 3.1.2
- 절차: `python -m unittest discover -s tests/test_common` (프로젝트 루트). `_create_client`를 httpx2.MockTransport 클라이언트로 교체해 외부 요청 차단. 가짜 키·가짜 모델명, 코드로 만든 PNG 사용
- 실제 결과: 32개 테스트 실행, 전부 통과(OK). 실행 시점은 코드·테스트 작성 직후이며 이후 코드·테스트 파일은 변경하지 않음(문서·requirements·.env.example만 변경)
- 확인 항목
  - 텍스트 정상: Pydantic 인스턴스·모델명·usage 반환
  - 요청 옵션: timeout 60/180, max_retries 0, model, max_output_tokens 4096, store=false, strict json_schema, 이미지 n=1·size·quality·output_format=png, temperature 등 미전달, 이미지 요청에 store 미전달
  - 입력 오류(빈 지시문·입력·프롬프트, 잘못된 스키마·토큰 값·크기·품질)에서 클라이언트 미생성
  - 텍스트 거절·incomplete(max_output_tokens, content_filter)·failed·스키마 불일치·비JSON·출력 없음 → 오류
  - 이미지 빈 결과·잘못된 base64·PNG 아님·잘린 PNG·크기 불일치·2장 반환·base64 상한 초과(디코딩 전 차단)·moderation_blocked → 오류
  - 401/403/404/429/400/500/503·시간 초과·연결 실패 → 공통 코드, 요청 1회(재시도 없음)
  - 설정: 키·모델 누락 시 미호출, 텍스트/이미지 설정 독립, 호출 시점에 환경변수 읽음
  - 키 없이 `app` import 및 `GET /` 200
  - 오류 메시지·to_dict·예외 체인·수집 로그에 가짜 키·입력·공급자 원문 미포함
- 추가 확인: 루트 로거 DEBUG에서 SDK 3.37.0이 남기는 로그 5줄에 요청 본문·키가 없음을 별도 스크립트로 확인
- 판정: 모의 테스트 통과. **실제 OpenAI 연결 성공을 뜻하지 않음**
- 미검증: 실제 API 호출, 모델 접근 권한, 실제 응답 형식과 SDK 파싱의 일치, 이미지 품질·소요 시간·비용, `OPENAI_LOG` 사용 시 로그 내용, 브라우저 동작(기능 화면 연결 없음), python-dotenv 자동 로드 실제 동작

## 2026-10-25 커밋 전 최종 검증
### Claude 실행 시도 (미실행)
- 대상: `git branch/status/diff`, jasonenv python 확인 → `python -m pip check` → `python -m unittest discover -s tests/test_common -v`
- 결과: 자동 승인 판정 오류("server-side auto mode classifier gave no verdict")로 명령이 차단되어 **실행되지 않음**. 우회하지 않음
- Claude가 명령 없이 확인한 것: jasonenv `site-packages`의 dist-info 이름으로 Flask 3.1.2·openai 3.37.0·pydantic 2.14.1·httpx2 2.16.0이 requirements.txt와 일치. Flask 3.1.2·python-dotenv 1.1.1 소스를 읽어 `.env` 로드 경로 분석(실제 로드는 미검증)

### 사용자 직접 실행 결과를 전달받음
- 실행 주체: 사용자(VS Code CMD). Claude는 실행 결과를 직접 관측하지 않았고 전달받은 내용을 그대로 기록함
- 실행 환경: `C:\Users\user\miniforge3\envs\jasonenv\python.exe`
- `python -m pip check` → `No broken requirements found.`
- `python -m unittest discover -s tests/test_common -v` → `Ran 32 tests in 0.465s` / `OK`
- 판정: 사용자 실행 기준 의존성 충돌 없음, 모의 테스트 32개 통과. **실제 OpenAI 연결 성공을 뜻하지 않음**

### 이후 변경 (문서·주석만)
- common/config.py 모듈 docstring의 `.env` 설명 수정(실행 로직 변경 없음), README.md의 `.env` 로드 설명을 소스 기준·미검증으로 수정
- 문서·주석만 바꿔 테스트를 다시 실행하지 않음(사용자 지시)
- 미검증 유지: 실제 OpenAI API 호출, 모델 접근 권한, 품질, 비용, 실제 `.env` 로드 동작, Git 브랜치·변경 상태(이번 턴 명령 차단으로 미확인)

## 2026-10-25 후속 검증: 실제 OpenAI 호출 (사용자가 직접 실행한 결과를 전달받음)
- 실행 주체: 사용자(같은 VS Code CMD, jasonenv python). Claude는 API를 호출하지 않았고 출력을 직접 관측하지 않음. 키·`.env`는 Claude가 읽지 않음
- 대상 커밋: 879f015 (feature/openai_common)
- 모델·설정: 사용자 환경변수 값은 전달받지 못함(미확인). 코드 기본값은 timeout 60/180초, max_retries 0, max_output_tokens 4096, store=False(텍스트)

### generate_structured
- 입력: `message` 필드에 OK를 반환하도록 요청(지시문·스키마 원문은 전달받지 않음)
- 사용자 보고: OK 출력
- 전달받지 못함: 응답 모델명(`result.model`), 사용량(`result.usage`)
- 판정(연결·반환 형식): 실제 호출로 구조화 결과가 반환된 것으로 보고됨

### generate_image
- 프롬프트: `A simple blue circle centered on a plain white background, no text.`
- 옵션: size 1024x1024, quality low
- 실제 출력(사용자 전달): `Image OK: image/png 1024 1024 bytes: 756767`
- 이미지 파일 미저장, 육안 확인 안 함
- 판정(연결·반환 형식): 실제 호출로 PNG bytes·MIME·요청 크기와 일치하는 가로·세로가 반환되었고 공통 검증(base64·PNG 서명·IHDR·IEND·크기)을 통과한 것으로 보고됨. 크기 756,767 bytes는 상한 16 MiB 이내

### 구분
- 확인된 것(연결·반환 형식, 사용자 보고 기준): 사용자 환경의 키·모델 설정으로 텍스트·이미지 공통 함수가 오류 없이 반환
- 미검증(업무 품질): 이미지 내용이 프롬프트와 맞는지(육안 미확인), 구조화 결과의 사실 정확성, 실제 기능 프롬프트·스키마에서의 결과 품질
- 미검증 유지: 비용, 소요 시간, 스캔 PDF 판독(미구현), 번역 품질, 응답 모델명·사용량, 오류 경로의 실제 공급자 응답(모의 테스트로만 확인), 실제 `.env` 로드 동작
- 이전 기록(모의 테스트 통과·실제 연결 미검증)은 당시 상태로 유지하며 이 항목으로 후속 보완함
- 공통 문서 반영(2026-10-25): docs/data_contracts.md, README.md, docs/decisions.md의 "실제 호출 미검증" 표현을 위 결과에 맞게 정정. 실행 검증 아님(문서 수정만, 테스트 재실행 없음)

## 2026-10-25 제품소개서 첫 화면 (PDF 선택·결과 확인·수정)
- 변경 내용: panel.html, product_brochure.js, product_brochure.css, feature_spec.md, tests/test_product_brochure/test_panel.py
- 환경: Conda jasonenv Python 3.11.17, Flask 3.1.2, Node v24.20.0(로직 점검용, 프로젝트 의존성 아님)

### Claude가 직접 실행한 검증
- `python -m unittest discover -s tests/test_product_brochure -v` → 12개 실행, OK
  - Flask test_client로 `GET /` 200, 5개 탭 패널 모두 렌더링
  - 파일 입력 1개(`multiple` 없음, accept .pdf), 스캔 PDF·상한 미정 안내 문구
  - 분석 버튼 비활성 + "PDF 분석 연결 준비 중", 카탈로그 생성·PDF 다운로드 비활성(비활성 버튼 3개)
  - 예시 버튼은 type=button·활성, 검토 영역은 처음 hidden, 예시 안내 문장 존재, 검토 영역 `data-work-ignore`
  - 이전 예시 입력(요청 사항 textarea)·바이어 입력 없음
  - JS 정적 검사: fetch·XMLHttpRequest·sendBeacon·localStorage·sessionStorage·indexedDB·FileReader·파일 읽기 메서드 없음, innerHTML 등 HTML 삽입 없음, setResult·downloadBlob 없음
  - CSS 선택자 모두 `.feature-product_brochure ` 범위
- `python -m unittest discover -s tests/test_common` → 32개 실행, OK(기존 공통 테스트 영향 없음 확인)
- `node --check product_brochure.js` → 문법 오류 없음
- Node 상태 로직 점검(스크래치패드 스크립트, 저장소 미포함) → 11개 통과
  - 예시 8개 항목 미확인 시작·dirty 아님, MOQ·샘플·납기 제공+가상, 원사 규격·탄소 저감률·인증 미제공
  - 값 수정 시 확인 해제·사용자 수정, 같은 값 입력은 확인 유지, 원래 값 복귀 시 사용자 수정 해제
  - 미제공 항목 입력 → 사용자 추가(제공 여부는 false 유지), 공백만 입력은 추가 아님
  - 미제공+가상 동시 성립, 예시의 가상 조건 해제 불가, 요약 집계
  - 파일 검사: 미선택·확장자 오류(MIME이 application/pdf여도 .docx·.pdf.exe 거부)·빈 파일·대문자 .PDF 허용

### 미검증(브라우저 미실행)
- 실제 브라우저에서의 파일 선택·안내 표시, 확인 대화상자(예시 재불러오기·새 PDF 선택), 취소 시 이전 파일 복원(DataTransfer)
- 탭 이동 후 상태 유지, 머리글 "작성 중" 표시·새로고침 경고, 새로고침 후 미복원
- 네트워크 요청이 실제로 발생하지 않는지(정적 검사로만 확인)
- 화면 배치·반응형·키보드 접근성·화면낭독기 안내
- 코드 검토와 단위 점검은 브라우저 동작 확인이 아님

## 2026-10-25 제품소개서 첫 화면 후속: 사용자 직접 확인 결과를 전달받음
- 실행 주체: 사용자(브라우저). Claude는 직접 관측하지 않았고 전달받은 내용을 그대로 기록함
- 대상: DI-2026_10_25-06 화면(배치 정리 전)
- 사용자 보고(정상)
  - 값 수정 시 사용자 확인 체크 해제
  - 다른 탭 이동 후 수정값 유지
  - 수정 후 예시 재불러오기에서 취소하면 수정값 유지
  - 새로고침 경고에서 취소하면 값 유지
  - 새로고침을 진행하면 작업 내용 초기화(미복원)
- 여전히 미검증: 파일 선택 안내(미선택·빈 파일·확장자), 새 PDF 선택 시 확인 대화상자와 취소 시 이전 파일 복원, 예시 재불러오기 확인 후 초기화, "확인 내용 적용" 요약 표시, 네트워크 요청 미발생(정적 검사만), 머리글 "작성 중" 표시, 반응형·키보드·화면낭독기

## 2026-10-25 제품소개서 확인·수정 화면 배치·문구 정리
- 변경 내용: panel.html, product_brochure.js(렌더링 부분만), product_brochure.css, feature_spec.md
- Claude가 직접 실행한 검증
  - `python -m unittest discover -s tests/test_product_brochure` → 12개 실행, OK
  - `python -m unittest discover -s tests/test_common` → OK
  - `node --check product_brochure.js` → 문법 오류 없음
  - Node 상태 로직 점검(스크래치패드 스크립트, 저장소 미포함) → 11개 통과. 상태 로직은 이번에 변경하지 않음
- 코드 확인: 입력·체크박스 이벤트 처리, setDraft 연동, 파일 교체·예시 재불러오기 확인 로직은 변경하지 않음(렌더링 문구·감싸는 요소만 변경)
- 미검증(브라우저 미실행): 2열/1열 전환이 실제 카드 폭에서 의도대로 되는지, 제품 설명 전체 폭, 화면 길이 감소 정도, 숨긴 안내와 aria-describedby의 화면낭독기 동작, 배치 변경 후 사용자 보고 항목(확인 해제·탭 유지 등)의 재확인

## 2026-10-25 공통 OpenAI 연결 PDF 입력 지원 (모의 테스트)
- 변경 내용: common/ai_client.py(generate_structured_from_pdf, PdfStructuredResult, 결과 검증 공통화), common/pdf_utils.py(inspect_pdf), common/errors.py(PDF_* 오류), common/config.py(PDF_* 설정), requirements.txt(pypdf==6.21.2), tests/test_common/test_pdf.py
- 환경: Conda jasonenv, Python 3.11.17, openai 3.37.0, pydantic 2.14.1, httpx2 2.16.0, pypdf 6.21.2

### Claude가 직접 실행한 검증
- `python -m pip check` → No broken requirements found.
- `python -m unittest discover -s tests/test_common -v` → 56개 실행, OK(기존 32 + PDF 24)
  - inspect_pdf: 정상 3쪽, bytes 아님(None·str·bytearray·memoryview), 빈 파일, 크기 경계(정확히 10 MiB 통과·+1 byte PDF_TOO_LARGE), 크기 초과는 파싱 전 거부, 페이지 경계(20쪽 통과·21쪽 거부), 0쪽, 위장 파일(PNG 서명, 1024바이트 이후 서명), 서명만 있고 구조 없음, 잘린 PDF, 암호화(RC4-40·RC4-128, Encryption.read·verify 미호출 확인), 상한 인자 오류
  - 로그: 앞 5바이트 표지·"invalid pdf header"·"startxref"가 로그에 없음 + 대조(차단 해제 시 표지가 로그에 나타남)
  - 대조: 일반 PdfReader는 해제를 시도함(전용 리더 필요성·버전 변경 감지)
  - generate_structured_from_pdf: 요청 1회, timeout 120·max_retries 0, model=OPENAI_MODEL, store=false, max_output_tokens 4096·재정의, strict json_schema, 미지원 파라미터 미전달, input 1개 user 메시지, input_file(filename document.pdf, detail high, file_data prefix·디코딩 결과=원본, file_id·file_url 없음), input_text 선택 포함·미포함, 지시문은 instructions에만, PdfStructuredResult(pdf=PdfInfo)
  - PDF 검사 실패 8종·인자 오류·설정 누락에서 클라이언트 미생성(요청 0회)
  - 거절·incomplete(max_output_tokens·content_filter)·스키마 불일치·비JSON·failed → 오류
  - 401·429·400·500·시간 초과 → 공통 코드, 요청 1회(재시도·모델/detail 변경 없음)
  - 오류 메시지·예외 체인·로그에 키·입력·공급자 원문·PDF 표지 미포함
  - 기존 generate_structured 요청(input 문자열, timeout 60) 유지
- 대조 실험(스크래치패드): 처음 로그 테스트가 5바이트 누출을 잡지 못함을 확인하고 테스트를 수정(prompt_log DI-08 참고)
- 판정: 모의 테스트 통과. **실제 PDF·스캔 PDF 판독 성공이나 실제 OpenAI 연결 성공을 뜻하지 않음**

### 미검증
- 실제 OpenAI 호출(gpt-5.4-mini의 PDF input_file·detail high 수용 여부), 텍스트 PDF·스캔 PDF 판독 품질, 토큰·비용·소요 시간
- AES 암호화 PDF 검출(테스트 PDF 생성 불가), 악성·과도한 자원 사용 PDF 대응
- 업로드 라우트의 요청 전체 제한·Werkzeug 임시 파일 동작(라우트 미구현)
- 이 브랜치에는 tests/test_product_brochure/test_panel.py가 없어 제품소개서 화면 테스트는 0개 실행(해당 파일은 feature/product_brochure에 있음)

## 2026-10-25 후속 검증: PDF 공통 함수 실제 호출 (사용자가 직접 실행한 결과를 전달받음)
- 실행 주체: 사용자(jasonenv CMD). Claude는 API를 호출하지 않았고 출력을 직접 관측하지 않음. 키·`.env`·문서 원문·로컬 경로는 Claude가 읽거나 기록하지 않음
- 대상 커밋: a7b940e (feature/openai_common). 실행 시점 작업 트리 변경 없음을 Claude가 git status로 확인 → 설정은 커밋 값(timeout 120초, 재시도 0, max_output_tokens 4096, store=False, detail high, 파일명 document.pdf)으로 판단
- 입력: 텍스트 PDF 1개, 104,195 bytes, 3쪽(inspect_pdf 통과). 연결 확인용 최소 스키마(product_name, moq_text, moq_is_virtual)
- 실제 출력(사용자 전달)
  - 결과: {"product_name":"리젠 T2T (regen T2T)","moq_text":"500 kg / 시연용 가상 값","moq_is_virtual":true}
  - 모델: gpt-5.4-mini-2026-03-17
  - 사용량: input 10,239 / output 46 / total 10,285 tokens

### 확인된 것(사용자 보고 기준)
- gpt-5.4-mini-2026-03-17에서 이번 텍스트 PDF 입력 요청이 처리되고 스키마 검증된 구조화 응답이 반환됨(오류 없음)
- 제품명·MOQ 값 추출, MOQ의 가상 표시가 별도 필드(true)로 구분되어 반환됨
- 위 토큰 사용량

### 미검증 유지
- 추출값이 문서 원문과 일치하는지에 대한 대조(Claude는 문서를 보지 않음)
- 스캔 PDF 판독
- 나머지 추출 항목과 전체 문서 정확성, 문서에 없는 값 생성 여부
- 비용 금액, 소요 시간, detail high/low 차이
- 제품소개서 화면·분석 라우트 연결(미구현)
- 이번 결과는 연결 확인용 최소 추출이며 제품소개서 서비스 프롬프트 품질 검증이 아님

## 2026-10-25 제품소개서 PDF 분석 서버 (모의 테스트)
- 변경 내용: features/product_brochure/routes.py(분석 API), service.py(스키마·후처리·업로드 오류), prompts/brochure_extract_v1.md, tests/test_product_brochure/test_analyze_api.py
- 환경: Conda jasonenv, Python 3.11.17, Flask 3.1.2, Werkzeug 3.1.9, openai 3.37.0, pydantic 2.14.1, httpx2 2.16.0, pypdf 6.21.2

### Claude가 직접 실행한 검증
- 1차 `python -m unittest discover -s tests/test_product_brochure` → 45개 중 4개 실패(500 KB 이상 정상 업로드가 413). 원인: max_form_memory_size 16 KiB 지정(prompt_log DI-10). 수정 후 재실행
- 최종 `python -m unittest discover -s tests/test_product_brochure` → 45개 실행, OK(기존 화면 12 + 분석 33)
- `python -m unittest discover -s tests/test_common` → 56개 실행, OK(공통 회귀 없음)
- 확인 항목(모의 전송 MockTransport, 라우트→서비스→공통 함수 전체 경로, 가짜 키·가상 PDF)
  - 정상 multipart → 200, 8개 항목 고정 순서, confirmed false, check not_checked, extraction_status unconfirmed, source·model·prompt_version, MOQ 값·found·가상 true
  - 공급자 요청 1회, instructions = 프롬프트 v1 파일, input_file 파일명 document.pdf·detail high·store false, 원본 파일명이 요청·응답에 없음
  - 정확히 10 MiB 통과, 10 MiB+1·+1000 bytes는 PDF_TOO_LARGE(413), 파일 스트림은 상한+1바이트로만 읽음(전체 읽기 없음), 요청 전체 상한 초과 UPLOAD_TOO_LARGE(413), 파트 수 초과 413
  - 파일 누락·빈 파일명·중복 파일·다른 파일 필드·빈 파일·위장(PNG)·손상·암호화(RC4)·0쪽·21쪽 → 각 코드, 외부 요청 0회
  - 키가 없어도 잘못된 PDF는 PDF_* 우선, 정상 PDF는 AI_CONFIG_MISSING(503)
  - 401·429·500·시간 초과·거절·incomplete·비JSON·알 수 없는 key → 기존 JSON 오류 형식, 요청 1회(기능 재시도 없음), 예기치 않은 예외 → AI_UNKNOWN_ERROR(500)
  - 후처리: 근거 없음·공백 발췌·빈 값 found 강등, 범위 밖 페이지(0·9) 표시와 유효 근거 유무에 따른 상태, 페이지 null, not_found+값 모순, 누락 key 채움, 중복 key 후보 보존, 가상 표시 유지(강등·미제공 포함), 복수 제품 서버·AI 검토 사항, 긴 발췌 자르기
  - 700 KB 업로드가 SpooledTemporaryFile에서 디스크 임시 파일로 넘어가고(_rolled True) 요청 후 닫힘
  - 오류 응답·로그에 가짜 키·문서 표지·공급자 원문·원본 파일명(경로) 없음
  - 화면 key와 스키마 key 일치, 프롬프트 파일 규칙 문구, GET / 200·앱 전역 MAX_CONTENT_LENGTH 변경 없음·GET 분석 경로 405
- 판정: 모의 테스트 통과. **실제 PDF 추출 품질·스캔 판독·실제 OpenAI 연결 성공을 뜻하지 않음**

### 미검증
- 서비스 프롬프트 v1의 실제 실행(텍스트·스캔 더미 PDF), 추출 정확성, 할루시네이션 발생 여부, 비용·소요 시간
- 근거 발췌의 원문 대조(미구현)
- 실제 브라우저·개발 서버에서의 업로드, 413 시 연결 끊김 여부, 프로세스 비정상 종료 시 임시 파일 정리
- 화면과 분석 API 연결(미구현)

## 2026-10-25 제품소개서 화면 ↔ PDF 분석 API 연결
- 변경 내용: panel.html, product_brochure.js, product_brochure.css, test_panel.py(갱신), review_logic_check.js·test_review_logic.py(신규)
- 환경: Conda jasonenv Python 3.11.17, Node v24.20.0(로직 점검용, 프로젝트 의존성 아님)

### Claude가 직접 실행한 검증
- `node --check product_brochure.js` → 문법 오류 없음
- `node tests/test_product_brochure/review_logic_check.js` → 13개 점검 통과
  - 파일 크기 경계(10 MiB 통과·+1 byte too_large)·빈 파일·확장자·미선택
  - 성공 응답 → 8개 항목 고정 순서, confirmed false, marked_virtual 보존(미제공+가상 포함, 해제 불가), provided = found+값, unclear 값 보존·사용자 추가 아님, not_found 구분, 범위 밖 페이지 표시값, candidates 시 값 비움
  - unclear 수정 → 사용자 수정·확인 해제, not_found 입력 → 사용자 추가
  - 잘못된 성공 응답(7개·중복 key·알 수 없는 key·잘못된 status·confirmed true·page 형식·extraction_status 누락·review_notes 형식) 거부
  - 실패 구분(네트워크·시간 초과·413·비JSON·안전한 서버 오류·안전하지 않은 서버 오류·형식 오류·비2xx 성공 형식)
  - 요청 실행기: 정상 1회·진행 on/off, 중복 요청 무시, 교체 확인 취소 시 요청 0회·진행 상태 변화 없음, 승인 후 실패 시 성공 콜백 없음, 잘못된 파일 요청 없음, 예외 → 네트워크 실패·자동 재시도 없음·재요청 가능, 오래된 응답 무시
  - AI 문자열(`<img …>`)이 상태에 문자열 그대로 보관됨(렌더링은 textContent, 정적 검사)
  - 기존 예시 동작(가상 고정·수정 시 확인 해제·사용자 추가)
- `python -m unittest discover -s tests/test_product_brochure` → 47개 실행, OK(분석 API 33, 화면·정적 13, Node 래퍼 1)
  - 1차 실행에서 정적 테스트 1건 실패(주석의 "Content-Type" 단어) → 테스트 수정 후 통과
  - 갱신한 정적 검사: fetch 1곳·분석 URL·POST·source_file append 1곳·Content-Type 헤더 미지정·analyzer.run 1곳(사용자 submit)·AppShell.onShow 미사용·브라우저 저장소/파일 읽기/XHR/sendBeacon/setInterval 없음·HTML 삽입 없음·setResult 없음
  - 화면: 분석 버튼 처음 비활성·data-analyze, 오류 영역 hidden, 출처 안내 2종 분리·원문 대조 미실시 문구, 검토 카드 aria-busy
- `python -m unittest discover -s tests/test_common` → 56개 실행, OK
- 참고: 테스트 중 ResourceWarning은 werkzeug 테스트 클라이언트가 multipart 요청 본문을 만들 때 쓰는 클라이언트 쪽 임시 파일에서 발생(tracemalloc으로 출처 확인). 서버 라우트의 업로드 정리 확인은 기존 테스트 범위 그대로

### 미검증(브라우저 미실행, 브라우저 도구 없음)
- 실제 브라우저에서 파일 선택·버튼 활성화·진행 표시·조작 잠금·확인 대화상자·오류 안내·결과 렌더링·후보·근거 표시·탭 이동 후 유지·새로고침 경고
- DOM 연결 코드(send·syncControls·renderField 등) 자체의 실행. Node 점검은 DOM 없는 로직만 다룸
- 실제 서버·OpenAI와의 종단 동작, 413 시 연결 끊김 안내, 반응형·키보드·화면낭독기
- 서비스 프롬프트 v1의 추출 품질(실험 미실행)

## 2026-10-25 후속 검증: 제품소개서 화면 실제 브라우저 확인 (사용자 직접 확인 결과를 전달받음)
- 실행 주체: 사용자(실제 브라우저). **Claude는 브라우저에서 직접 검증하거나 관측하지 않았고 전달받은 내용을 그대로 기록함**
- 대상: DI-2026_10_25-11 화면 연결(미커밋 작업 트리 상태), 서비스 프롬프트 brochure_extract_v1(SPE-2026_10_25-01)
- 입력: 더미 PDF(시연용 가상 자료로 보고됨). 파일·원문·결과 원문은 기록하지 않음

### 확인됨(사용자 보고 기준)
- 더미 PDF 분석 후 결과가 화면에 표시됨(화면 → 분석 API → 공통 PDF 함수 → 응답 표시 경로가 실제로 동작)
- MOQ·샘플·납기에 "가상 정보" 표시와 AI 제시 근거가 표시됨
- MOQ의 사용자 확인을 체크한 뒤 값을 수정하면 확인 체크가 해제됨
- 다른 탭으로 이동했다 돌아와도 분석 결과와 수정값이 유지됨

### 미검증 유지
- 8개 항목 전체의 정확성(원문 대조), 문서에 없는 값 생성 여부, 근거 페이지·발췌의 정확성
- 스캔 PDF 판독
- 오류 화면(네트워크·413·서버 오류·잘못된 응답), 교체 확인 대화상자, 파일 교체 취소 시 복원
- 분석 중 조작 잠금·진행 표시·중복 요청 방지의 브라우저 동작
- 응답 모델명·사용량, 비용 금액, 소요 시간
- 새로고침 경고(분석 결과 상태), 반응형·키보드·화면낭독기
- 이전 기록(브라우저 미확인, 서비스 프롬프트 실험 미실행)은 당시 상태로 보존하며 이 항목으로 후속 보완함

## 2026-10-25 제품소개서 4페이지 카탈로그 디자인 시안
- 변경 내용: catalog_preview.html(신규), panel.html, product_brochure.js(시안 블록), product_brochure.css, test_panel.py
- AI API 호출 없음(OpenAI·이미지 생성 미호출)

### Claude가 직접 실행한 검증
- `node --check product_brochure.js` → 문법 오류 없음
- `python -m unittest discover -s tests/test_product_brochure` → 1차 2건 실패(기존 "바이어" 검사에 시안 설명 문구가 걸림, 상속으로 기존 테스트 중복 실행) → 수정 후 51개 실행, OK
  - 시안 검사 4개: 진입 버튼(type=button·활성)·dialog 1개(자동 열림 없음·data-work-ignore), 4쪽(data-page 1~4·lang pt-BR) 각각 비공식 안내와 "n / 4", 공급 조건 3개 각각 가상 안내, 규격·인증·탄소 자리표시자에 숫자·% 없음, img·외부 URL·@·+55·회사 표기 없음, "não é foto real do produto" 표시, 시안 JS 블록이 검토 상태·작업 상태·fetch·저장소를 참조하지 않음
  - 기존 화면·분석 API·Node 로직 점검(13개) 회귀 없음, CSS 선택자 범위 검사 통과
- `python -m unittest discover -s tests/test_common` → 56개 실행, OK

### 미실행·미검증
- 시각 검증 전체(브라우저 도구 없음): 넓은 화면 2쪽 배치, 좁은 화면 축소, 실제 크기 전환, 페이지 넘침 여부(경고 표시 동작 포함), 대화상자 초점·Esc·초점 복귀, 화면 전체 가로 스크롤 여부
- 시안을 열고 닫은 뒤 분석 결과·수정값 유지(코드 정적 검사로만 확인, 브라우저 미확인)
- 색 대비 실측, pt-BR 문구 검수, 인쇄·PDF 출력 일치

## 2026-10-25 카탈로그 시안 콘셉트 이미지 적용·편집 디자인 개선
- 변경 내용: catalog_preview.html, product_brochure.css(시안 섹션), product_brochure.js(이미지 처리), test_panel.py, assets.md
- AI API 호출 없음(이미지 생성·재생성 없음)

### Claude가 직접 실행한 검증
- 이미지 파일: `file`로 PNG 1024×1536(cover)·1448×1086(material), 8-bit RGB 확인. 이미지 보기 도구로 두 이미지 구도 확인(디자인 배치 판단용, 육안 품질 검토는 사용자 몫)
- Flask test_client: 두 정적 URL `/features/product_brochure/static/images/…` → 200, image/png, PNG 서명 일치. 렌더링 HTML에 로컬 절대 경로 없음
- `node --check product_brochure.js` → 문법 오류 없음
- `python -m unittest discover -s tests/test_product_brochure` → 52개 실행, OK
  - 시안 검사 5개: 진입·dialog, 렌더링된 4쪽 각각 비공식 안내·"n / 4"·콘셉트 이미지(로컬 정적 경로)·alt "conceitual"·AI 이미지 안내·로딩 실패 대체 요소, 이미지 정적 응답, 4쪽 공급 조건 3개 가상 안내, 3쪽 "Informações técnicas a confirmar."·규격·인증 수치 없음, 문서 안 제작 안내·점선 자리표시자·연락처 자리 없음, "시안 제작 메모"는 대화상자에 존재, 시안 JS 블록이 검토 상태를 참조하지 않음
  - CSS 범위 검사(모든 선택자 .feature-product_brochure 시작), 기존 화면·분석 API·Node 로직 점검 회귀 없음
- `python -m unittest discover -s tests/test_common` → 56개 실행, OK

### 미실행·미검증
- 시각 검증 전체(브라우저 도구 없음): 이미지 로딩 후 각 쪽 크롭·제목과 이미지의 위계·가독성, 넓은 화면 2쪽 배치·좁은 화면 축소·100% 전환, 페이지 넘침(경고 동작 포함), 대화상자 내부 스크롤, 초점 복귀
- 이미지 로딩 실패 시 대체 안내의 실제 표시(코드·정적 검사만)
- 이미지 사용권 조건·생성 설정(미확인), 색 대비 실측, pt-BR 검수, 인쇄·PDF 일치, 약 5.9 MB 이미지 로딩 시간

## 2026-10-25 pt-BR 카탈로그 문구 생성 서버 (모의 테스트)
- 변경 내용: generation.py, prompts/brochure_generate_v1.md, routes.py(generate), test_generate_api.py
- 환경: Conda jasonenv Python 3.11.17, Flask 3.1.2, openai 3.37.0, pydantic 2.14.1. 실제 OpenAI 호출 없음(MockTransport)

### Claude가 직접 실행한 검증
- `python -m unittest discover -s tests/test_product_brochure -p test_generate_api.py` → 14개 실행, OK(첫 실행)
  - 정상: 4쪽 구조(page 1~4), 제품명 입력 표기 보존, used_keys·excluded(empty·unconfirmed)·input_meta, 서버 고정 안내, 소개 문구 가상 전파(+고정 안내), 3·4쪽 출처·가상·고정 가상 안내, 모델 입력에 사용 항목만·메타데이터·제외 항목 없음, 지시문 = 프롬프트 파일, 요청 1회
  - 선택 항목 전부 없음 → 3·4쪽 items 빈 목록·empty true·빈 상태 문구, 모델 입력 details/supply_keys 빈 목록
  - review_flags: 입력에 없는 숫자·평가 어휘(new_number·claim_term), 수치 변경(number_not_preserved) 표시만 하고 성공 응답
  - 입력 오류(외부 호출 0회): 제품명·설명 비어 있음/공백/미확인, 중복·누락·알 수 없는 key, "true"·1·"false"·숫자 value·null value·잘못된 origin, 추가 최상위·항목 필드(필드명이 오류 메시지에 반사되지 않음), 잘못된 JSON·Content-Type·배열 본문·fields 없음, 8개 항목별 길이 초과(경계값은 허용), 본문 32 KiB 초과 413
  - 출력 오류(요청 1회, 재시도 없음): 제외된 key 참조·빈 source_keys·미제공 3쪽 항목 추가·3쪽 누락·4쪽 중복/누락·다른 쪽 항목·tagline 초과·문단 0/3개·빈 값·라벨 초과 → GENERATE_OUTPUT_INVALID 502, 거절 422·미완료·비JSON·스키마 밖 key → 공통 AI_* 코드
  - 429·키 없음(503, 요청 0회), 오류 응답·로그에 입력 표지·공급자 원문·가짜 키 없음
  - 프롬프트 규칙 문구와 출력 상한 숫자가 서버 상수와 일치
- `python -m unittest discover -s tests/test_product_brochure` → 66개 실행, OK(분석 API·화면·시안·Node 로직 회귀 없음)
- `python -m unittest discover -s tests/test_common` → 56개 실행, OK

### 미검증
- 서비스 프롬프트 brochure_generate_v1 실제 실행(실험 미실행): pt-BR 문구 품질·번역 의미·문체, 수치·단위 보존, 근거 없는 주장 발생 여부, 비용·소요 시간
- review_flags 오탐·미탐 비율(단순 숫자·어휘 검사)
- 화면 연결(미구현), 생성 결과의 브라우저 표시

## 2026-10-25 카탈로그 생성 API 화면 연결·결과 미리보기
- 변경 내용: product_brochure.js, panel.html, catalog_preview.html(결과 dialog), product_brochure.css, test_panel.py, review_logic_check.js, test_review_logic.py
- 실제 생성 API·OpenAI 호출 없음(모의 응답·정적 검사·Node 로직 점검만)

### Claude가 직접 실행한 검증
- `node --check product_brochure.js` → 문법 오류 없음
- `node tests/test_product_brochure/review_logic_check.js` → 22개 점검 통과(기존 13 + 생성 9)
  - origin 변환(추출·사용자 수정·사용자 추가, 사용자 추가 재수정 시 유지)
  - 적용 스냅샷 독립성(원본 수정 후 스냅샷 불변, 객체 참조 미공유, 필드 5개만)
  - 생성 가능 조건: 개발용 예시 → 불가, 미적용·새 입력 버전 → not_applied, 확인 체크 변경 → reapply, 필수 미확인 → required, 길이 초과 → too_long(요청 본문 값은 자르지 않음), 진행 중 → busy, 정상 시 포함·제외(미확인·빈 값)
  - 요청 본문: 최상위 fields만, 8개 key 순서, 항목 필드 5개·boolean·문자열, 근거 발췌 미포함
  - 응답 검사: 정상 통과, 상태·쪽 누락·사용하지 않은 key·다른 쪽 항목·중복·empty 불일치·문단 0/3개·source_keys 이상·review_flags 형식·used_keys 필수 누락·notices 누락 → 거부
  - 실패 해석: 알려진 코드만 고정 안내(서버 원문 미표시), 미지 코드·비JSON·413·시간 초과("과금 취소 보장 아님" 문구)·비2xx 성공 형식 구분
  - 생성 실행기: 정상 1회, 조건 미충족·분석 중·재생성 취소·스냅샷 없음 → 요청 0회·진행 상태 변화 없음, 중복 클릭 무시, 실패 시 성공 콜백 없음, 오래된 응답 무시
  - 이전 결과 판정(입력 수정·재분석 → 다를 수 있음), review_flags 위치 설명(한국어 항목 이름), HTML 형태 AI 문자열이 데이터에 그대로 보관
- `python -m unittest discover -s tests/test_product_brochure` → 1차 4건 실패(구조 변경에 따른 정적 테스트, prompt_log DI-16) → 수정 후 68개 실행, OK
  - 화면 요청 본문 ↔ 서버 스키마 교차 확인: Node(화면 JS)가 만든 본문을 generation.parse_request·select_inputs가 그대로 받고 used/excluded·origin·virtual이 기대와 일치
  - 정적: dialog 2개(시안·결과) 자동 열림 없음, 결과 dialog에 예시 값·예시 문구 없음·slot 존재·4쪽·검토 초안 안내·AI 이미지 안내, 처음 비활성 버튼 4개(생성 포함), fetch 1곳·분석/생성 URL·run 각 1곳·Content-Type 직접 지정 없음·브라우저 저장소 없음·onShow 없음, setResult 호출 없음, 미리보기 공통·시안 블록이 검토/생성 상태를 참조하지 않음, HTML 삽입 없음, CSS 범위
- `python -m unittest discover -s tests/test_common` → 56개 실행, OK

### 미실행·미검증(브라우저 도구 없음)
- DOM 연결 코드 실행 전반: 버튼 활성/비활성 전환, 안내 문구, 잠금·aria-busy, 교체 확인 대화상자, 결과 dialog 렌더링, 점선 검토 표시, "현재 입력과 다를 수 있음" 표시, 탭 이동 후 유지, 새로고침 경고
- 상한 길이 문구(소개 140자·문단 600자×2·공급 값 200자)와 빈 상세·공급의 실제 배치·넘침(넘침 검사 코드는 있으나 실행 미확인)
- 실제 서버·OpenAI 종단 동작, 생성 품질(서비스 프롬프트 실험 미실행)

## 2026-10-25 후속 검증: 카탈로그 생성 v1 실제 실행 (사용자 실행 결과를 전달받음)
- 실행 주체: 사용자(실제 화면). Claude는 호출·관측하지 않음. 원문·생성 결과 전문은 기록하지 않음
- 전달받은 범위: 응답 모델 gpt-5.4-mini-2026-03-17, 프롬프트 brochure_generate_v1, 실제 결과 미리보기 표시
- 발견 문제: 표지 한글 제품명 노출, 샘플 번역("revisão de amostra") 개선 필요, 표지·2쪽 소개 반복 (prompt_log SPE-2026_10_25-02)
- 확인된 것(사용자 보고 기준): 화면 → 생성 API → 결과 미리보기 경로가 실제로 동작
- 미검증: 전체 번역 정확성, 다른 항목 문구, 페이지 넘침, 비용·소요 시간

## 2026-10-25 카탈로그 표시명 분리·언어 검사·프롬프트 v2 (모의 테스트)
- 변경 내용: generation.py, brochure_generate_v2.md, product_brochure.js, panel.html, 테스트 3개
- 실제 API 호출 없음

### Claude가 직접 실행한 검증
- `node --check product_brochure.js` → 문법 오류 없음
- `node tests/test_product_brochure/review_logic_check.js` → 26개 통과(기존 22 + 표시명 4)
  - 제안: "리젠 T2T (regen T2T)" → "regen T2T", 라틴만·악센트 이름은 그대로, 다른 제품의 괄호 라틴 표기는 그 표기(regen T2T 강제 없음), 한글만·괄호 밖 라틴만·불일치·괄호 후보 2개·괄호 안 한글 → 비움(none/ambiguous)
  - 검사: 빈 값·한글 음절·자모·81자·제어 문자 거부, 80자·악센트·숫자·®·-·&·/·괄호 허용
  - 스냅샷·서명·판정: 표시명 미확인·한글 → display_name 사유, 표시명 변경 → reapply, 이전 결과 경고, 스냅샷 독립, 요청 본문 trim
  - 응답: 표지 제품명 ≠ 표시명·display_name 누락 거부, 한글 잔존 오류는 알려진 위치만 표시, repeated_text 안내 문구
- `python -m unittest discover -s tests/test_product_brochure` → 1차 31건 실패·2건 오류(요청 계약 변경), 준비 코드 갱신 후 74개 실행, OK
  - 생성 API: 표시명 누락·미확인·공백·한글 음절/자모·81자·제어 문자·형 오류 → 400(AI 호출 0회), 악센트·숫자·기호 표시명 4종 허용 및 표지·모델 입력에 그대로 사용(regen T2T 강제 없음), 모델 입력 product_name = 표시명·원본 한글 미포함, 응답 display_name·prompt_version v2
  - 한글 잔존: 1쪽 소개·2쪽 문단(자모)·4쪽 샘플 값·3쪽 항목명 → 502 GENERATE_OUTPUT_LANGUAGE, 메시지에 위치만(생성 문구 원문 미포함), 요청 1회(재시도 없음), pt-BR 악센트 문구는 통과
  - repeated_text: 거의 같은 문단에만 표시, 제품명·핵심 용어 반복은 미표시
  - 프롬프트 v2 규칙 문구 포함·특정 제품명 미포함·v1 파일 존재(git diff로 v1 무변경 확인)
  - 교차: 화면 제안 표시명 → 서버 parse_request 통과, 원본 제품명 보존, used/excluded·origin·virtual 기존과 동일
  - 기존 가상 표시·수치/단위 review_flags·분석 API·화면·시안 테스트 회귀 없음
- `python -m unittest discover -s tests/test_common` → 56개 실행, OK

### 미검증
- v2 프롬프트 실제 실행(번역·샘플 표현·반복 개선 여부) — 프롬프트에 지침을 넣은 것과 실제 개선은 별개
- 표시명 입력·체크·제안 갱신·재적용 표시의 브라우저 동작(DOM)
- 한글 검사 통과가 pt-BR 품질을 뜻하지 않음, 페이지 넘침, 비용·소요 시간

## 2026-10-26 후속 검증: 카탈로그 생성 v2 실제 실행 (사용자 실행 결과를 전달받음)
- 실행 주체: 사용자(실제 화면). **Claude는 호출·관측·검증하지 않음.** 결과 전문·사용자 문서는 기록하지 않음
- 대상: 커밋 cf81010, 프롬프트 brochure_generate_v2 (prompt_log SPE-2026_10_26-01)
- 확인됨(사용자 보고 기준, v1에서 발견한 세 문제)
  - 표지 제품명이 한글 없이 "regen T2T"로 표시됨
  - 샘플 문구가 평가용 샘플 요청 의미로 표현됨
  - 표지 소개와 2쪽 설명의 그대로 반복되는 문제가 개선됨
- 판정: 위 세 항목은 이번 1회 실행 기준 정상(사용자 보고)
- 미확인: 응답 모델명, 사용량, 비용, 소요 시간
- 미검증 유지: 전체 번역 정확성·다른 항목 문구, 페이지 넘침, 다른 입력에서도 같은 품질이 유지되는지, 표시명 입력 외 DOM 동작 전반
- 이전 기록(v2 실제 실행 미실행, v1 문제 발견)은 당시 상태로 보존하며 이 항목으로 후속 보완함

## 2026-10-26 생성 결과 문구 편집·4쪽 "샘플·거래 상담" 정리
- 변경 내용: product_brochure.js, product_brochure.css, catalog_preview.html, test_panel.py, review_logic_check.js
- 실제 API 호출·서비스 프롬프트 변경 없음. 서버 파일(generation.py·routes.py·service.py·prompts) 무변경을 git diff로 확인

### Claude가 직접 실행한 검증
- `node --check product_brochure.js` → 문법 오류 없음
- `node tests/test_product_brochure/review_logic_check.js` → 1차 31/32(테스트 데이터 문제, prompt_log DI-2026_10_26-02) → 수정 후 32개 통과(기존 26 + 편집 6)
  - 편집 칸 5종 id·위치 이름·상한(80/140/600/300/200, 서버 값과 동일)
  - 적용: 원본·적용본·임시 값 독립(적용 후 임시 값 변경이 적용본에 영향 없음), 표시명 trim·display_name과 표지 제품명 동시 변경, 라벨·source_keys·origin·virtual·가상 안내·notices·used_keys 보존, 원래 review_flags 유지, 사용자 수정 칸 계산, HTML 형태 문자열은 문자열로 보관, 줄바꿈·악센트 허용
  - 검증: 141자·공백만·한글 음절·자모·제어 문자·한글 표시명 → 위치별 오류, 하나라도 틀리면 적용본 미생성(부분 적용 없음), 140자 경계 허용
  - 복원·변경 감지: 원래 문구로 되돌리면 사용자 수정 아님, 원본 복제 시 수정 없음, 임시 값 dirty 감지
  - 출력 편집 후에도 이전 결과 경고 아님, 입력 변경 시 경고 유지
  - 재생성: 수정본이 있으면 "직접 수정한 문구" 대체 안내, 취소 시 요청 0회·성공 콜백 없음(기존 실패 시 결과 유지 점검도 통과)
- `python -m unittest discover -s tests/test_product_brochure` → 1차 1건 실패(비활성 버튼 수 4→5) → 수정 후 77개 실행, OK
  - 신규 정적 검사: 4쪽 제목·상담 마무리 문구가 시안·결과 모두 존재, 제공 가능·무료·즉시 발송 표현 없음, 결과 dialog에만 편집 UI(시안 제외), contenteditable·execCommand 없음, 편집 코드에 요청·스냅샷/표시명 대입·setResult·저장소·innerHTML 없음
  - 화면 요청 본문 ↔ 서버 스키마 교차 확인 포함 기존 테스트 회귀 없음
- `python -m unittest discover -s tests/test_common` → 56개 실행, OK

### 미실행·미검증(브라우저 도구 없음)
- 편집 영역 열기·입력·적용·취소·되돌리기·오류 표시, 닫기/Esc 확인 대화상자, 초점 이동, 탭 이동 후 임시 값 복원의 DOM 동작
- 편집·복원 후 미리보기 갱신과 페이지 넘침 경고의 실제 표시
- 4쪽 새 제목·문구의 배치, pt-BR 문구 검수


## 2026-10-26 카탈로그 PDF 렌더러(ReportLab) — 모의 데이터 검증
- 변경 내용: pdf_catalog.py, fonts/, requirements.txt, feature_spec.md §25, test_pdf_catalog.py·pdf_fixtures.py·make_pdf_samples.py
- 실제 API 호출·서비스 프롬프트 실험·라우트/화면 연결 없음

### Claude가 직접 실행한 검증
- 설치: `pip install --dry-run` → reportlab 5.1.0·pillow 13.0.0·charset-normalizer 3.5.2만 설치 예정 확인 → 설치 → pip freeze 전후 차이 3줄 → `pip check` "No broken requirements found."
- 글꼴 복사본 git blob 해시가 팀 브랜치 원본과 동일함을 확인
- `python -m unittest discover -s tests/test_product_brochure` → 1차 26개 중 2개 실패(소스 검사 테스트 오탐, 4쪽 넘침 예시가 실제로 넘치지 않음) → 수정 후 전체 103개 OK
  - 4쪽·A4 세로·%PDF, 모든 쪽 비공식 안내·쪽 번호·AI 이미지 안내 텍스트 추출, 쪽별 제목, 항목명 서버 상수
  - 이미지 4곳 배치(폭 1024/1448/1448/1024), 이미지 객체 2개만, 글꼴은 내장 글꼴만(Helvetica 없음), 3 MB 미만
  - 편집값 반영(표시명·소개·문단·공급 값), & < > " ' 와 악센트가 글자 그대로 추출, 마크업 형태 입력 미해석·이미지 추가 없음, 시안 문구 미혼입, 한글 없음
  - 빈 상세·공급 → 서버 빈 상태 문구, 가상 안내 수(표지 2·2쪽 1·3쪽 3·4쪽 3), 기본 데이터에서 가상 표시 항목만 안내
  - 상한 근처 긴 문구 통과(long_max, 문단 2×600자), 24자 이하 넓은 단어 값의 글자 크기 전환
  - 넘침: 3쪽 상세(300자×3+가상), 1쪽 긴 한 단어 표시명 → 422·쪽 번호, 오류 문구에 사용자 문자열 없음. 4쪽은 최소 높이 상향 모의로 검사 동작 확인
  - 입력 검사: 상한±1, 공백만, 한글 음절·자모, 탭, 표시명 줄바꿈, 다른 쪽 key, 중복, 미허용 key, 라벨·html·image_url·font_path·color·notice 필드, 문자열 virtual, 문단 0/3개, language≠pt-BR, 배열 입력
  - 자산: 이미지 없음·잘린 PNG·다른 크기, 글꼴 없음·손상 → 자산 오류. 자산 문제 상태에서도 앱 첫 화면 200
  - 이모지 → 글리프 없음 오류
  - 생성 함수·소켓 연결을 금지 모의로 바꾼 상태에서 성공·실패 렌더링 모두 호출 없음, 로그 없음(assertNoLogs), 소스에 AI·네트워크·logging·tempfile·내장 open·pdf_utils 사용 없음(AST), routes.py 미연결
- `python -m unittest discover -s tests/test_common` → 56개 OK
- `node --check product_brochure.js` → 오류 없음(JS 변경 없음)
- 개발 검증 PDF 생성(`make_pdf_samples.py`, 저장소 밖 폴더, 덮어쓰기 금지): 정상 6건 각 약 877 KB, 0.17~0.43초(첫 건은 글꼴·이미지 준비 포함). 넘침 2건은 의도대로 실패. 시간은 측정값이며 강제 타임아웃이 아님
- pypdf 텍스트·메타데이터 추출로 edited 예시의 쪽별 문구 순서 확인

### 미실행·미검증
- **쪽별 시각 확인 미실행**: Read 도구는 pdftoppm 없음으로 실패, Edge headless 스크린샷은 빈 화면. 새 시각화 패키지는 설치하지 않음. 텍스트 추출·페이지 수 검사는 시각 검증이 아님
  - 사람이 열어 볼 파일: C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Desktop-fionex\36d7c2bf-67d2-469c-9a14-643e83056de0\scratchpad\pdf_samples_v3\catalog_*.pdf
- 겹침 여부는 측정 기반 배치 계산으로만 확인(실제 그림 비교 아님), 다른 뷰어·인쇄 결과, 실제 생성 결과 데이터, 동시 요청 시 메모리·시간
- 삭제 시도 기록: `rm -f $S/*.pdf`는 사용자 승인 거부로 실행되지 않음. 이후 ls로 pdf_samples의 6개 파일(크기·시각 동일) 보존 확인

## 2026-10-26 카탈로그 PDF 가로 넘침 수정 — 후속 검증
### 외부 전달 결과(Claude 미관찰)
- 사용자가 ChatGPT로 이전 검증 PDF(catalog_base, catalog_max_paragraphs) 8쪽을 렌더링해 확인: 2쪽 본문 오른쪽 잘림·쪽 밖 이탈, 3쪽 여백 침범, 4쪽 상담 문구 영역 이탈, 1쪽 정상
- 이전 항목(렌더러 103개 테스트 통과)은 텍스트·페이지 수·자체 측정 기반이라 이 문제를 잡지 못했음. 이 후속 시각 검증에서 잘림이 발견됨

### Claude가 직접 실행한 검증
- 내용 스트림 확인: 머리말의 `1.469446 Tc`가 q/Q 밖에 남는 것을 확인(원인)
- 내용 스트림 기반 줄 폭 계산(pdf_geometry): 수정 전 2쪽 최대 644.0pt(기본)·666.5pt(긴 문단), 쪽 폭 595.3pt, 1·3·4쪽도 오른쪽 여백선(547.3pt) 초과 줄 있음 → 수정 후 모든 예시 최대 547.3pt(쪽 번호 오른쪽 정렬 끝), 최소 18.0pt(3쪽 캡션 시작)
- 수정 전 코드(HEAD 복사본)에 새 회귀 테스트 적용 → 2개 실패(1쪽 제목 508.6px > 504px, 2쪽 줄 592.2pt vs 482.0pt). 수정 후 통과
- `unittest discover -s tests/test_product_brochure` → 106개 OK(신규 GeometryTests 3개, 영역 대조 예시 7개: base·edited·empty_info·virtual_all·long_max·max_paragraphs·wide_words)
- `unittest discover -s tests/test_common` → 56개 OK, pip check 이상 없음
- 새 검증 PDF 생성(새 폴더, 기존 파일 삭제·덮어쓰기 없음): 정상 7건 각 약 877 KB, 넘침 예시 2건은 의도대로 실패
  - C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Desktop-fionex\36d7c2bf-67d2-469c-9a14-643e83056de0\scratchpad\pdf_samples_v4_fix_hoverflow

### 미실행·미검증
- **수정 후 쪽별 육안 확인 미실행**: 렌더링 도구 없음(pdftoppm 미설치, Edge headless는 이전에 빈 화면). 새 패키지 미설치. 영역 대조는 글자 줄의 가로 범위·기준선만 보며 글자 높이·이미지와의 겹침·시각 품질은 확인하지 않음
- 이전 검증 PDF 폴더(pdf_samples, _v2, _v3)는 삭제하지 않고 보존(수정 전 코드로 만든 파일이라 잘림 포함)

## 2026-10-26 가로 넘침 수정 후 외부 시각 검증(전달받은 결과, Claude 미관찰)
- 사용자가 ChatGPT로 pdf_samples_v4_fix_hoverflow의 기본형·긴 문단형·긴 단어형 PDF 3개(12쪽)를 렌더링해 확인
  - 글자 잘림·의도하지 않은 겹침 없음, 긴 문단·가상 안내와 하단 안내 겹침 없음, 긴 단어 줄바꿈·악센트·특수문자 표시 정상
  - 미검증: 실제 생성·편집 결과의 다운로드, 다른 PDF 뷰어·인쇄
- Claude는 이 시각 확인을 직접 수행하지 않음(렌더링 도구 없음)

## 2026-10-26 카탈로그 PDF 다운로드 API — 서버·테스트
- 변경 내용: routes.py(POST /api/product-brochure/pdf), pdf_download.py(신규), test_pdf_download_api.py(신규), test_pdf_catalog.py, feature_spec.md §26
- 실제 API 호출·서비스 프롬프트 실험·화면 수정 없음

### Claude가 직접 실행한 검증
- `python -W error::ResourceWarning -m unittest discover -s tests/test_product_brochure` → 1차 45개 중 2개 실패(테스트 측 문제, prompt_log DI-2026_10_26-05) → 수정 후 전체 122개 OK
  - 신규 API 테스트 16개: 실제 렌더러 경유 200·%PDF·고정 파일명·no-store·nosniff·Content-Length·4쪽 A4, 편집값·가상 안내 출력·시안 문구 미혼입, 사용자 값이 헤더에 들어가지 않음, 키 없이 첫 화면 200·PDF 200
  - 잘못된 Content-Type 2종·손상 JSON·빈 본문·최상위 형식 11종·catalog 내부 6종·32 KiB 초과 → 지정 코드, 렌더러 실행 0회·슬롯 반환, 앱 전역 MAX_CONTENT_LENGTH 미설정 유지
  - 렌더러 오류: 넘침·글리프 422, 자산 500(내부 경로 미노출)
  - 예상하지 못한 오류: 500 고정 문구, 응답·로그에 입력·경로·키 형태 문자열·Traceback 없음, 로그에는 예외 종류만
  - 동시 실행: 슬롯 2개 점유 시 렌더링 없이 429, 실제 요청 2건 진행 중 세 번째 즉시 429 후 두 요청 200, 예상 외 오류 3회 연속에도 슬롯 누수 없음
  - OpenAI 클라이언트 생성·생성 함수·소켓 연결 금지 모의, 쓰기 모드 open 0회, 새 ResourceWarning 0건
- `python -W error::ResourceWarning -m unittest discover -s tests/test_common` → 56개 OK
- `pip check` 이상 없음, `node --check product_brochure.js` 오류 없음(JS 변경 없음)
- ResourceWarning 출처 확인: 전체 실행 중 경고 10건은 기존 test_analyze_api.py(분석 업로드 임시 파일, 이번 미변경)에서만 발생, 신규·변경 PDF 테스트 파일은 0건. 기존 경고는 이번 범위에서 수정하지 않음

### 미실행·미검증
- 화면 다운로드 버튼(미구현), 실제 브라우저 다운로드·저장, 실제 생성·편집 결과로 만든 PDF
- 여러 워커 환경의 동시 제한(프로세스당 제한만 구현), 큰 부하에서 메모리·시간, 렌더링 강제 시간 제한(없음)
- 이번 단계 PDF 육안 확인(새 샘플 미생성, 기존 샘플 삭제·덮어쓰기 없음)

## 2026-10-26 화면 "PDF 다운로드" 연결 — 모의·정적 검증
- 변경 내용: product_brochure.js(PDF 순수 로직·화면 연결·항목명), panel.html(버튼·안내 위치), product_brochure.css, 테스트 3개 파일, feature_spec.md §27
- 실제 OpenAI 호출·서버 API 변경 없음

### Claude가 직접 실행한 검증
- `node --check product_brochure.js` → 오류 없음
- `node tests/test_product_brochure/review_logic_check.js` → 40개 통과(신규 PDF 8개)
  - 요청 본문: 적용본 값·가상 표시만, 금지 필드(label·source_keys·review_flags·origin·안내·model·display_name 등) 없음, 독립 복사본, 불리언 아닌 virtual 미부풀림
  - 가능 조건: 결과 없음·진행 중·미적용 편집(고정 문구)·32 KiB 초과(UTF-8 바이트) 거부, 경계 32 KiB 허용
  - 응답 해석: 정상 PDF만 통과, 다른 MIME·빈 파일·잘못된 서명·201·HTML(200/502)·413·알려진 오류 7종(서로 다른 고정 안내, 서버 문구 미표시)·알 수 없는 코드·네트워크·시간 초과
  - 실행기: 이전 결과 확인 취소·다른 요청 진행 중·크기 초과 → 요청 0회, 중복 클릭 → 요청 1회·성공 1회(blob·요청 당시 버전), 잘못된 응답·실패 → 다운로드 0회·재시도 없음·이후 재요청 가능, 시간 초과 후 잠금 해제, 무효화 뒤 오래된 응답 무시
- `python -W error::ResourceWarning -m unittest discover -s tests/test_product_brochure` → 1차 test_panel 3건 실패(prompt_log DI-2026_10_26-06) → 수정 후 128개 OK
  - JS가 만든 요청 본문을 실제 서버 parse_request·parse_catalog가 받음(편집값·가상 표시 일치, AI 라벨 미전송), 같은 본문으로 라우트 200·application/pdf·편집값·가상 안내 텍스트 확인
  - 화면 항목명·파일명·32 KiB 상수가 서버 값과 같음
  - 정적: downloadBlob 호출 1곳(성공 경로) 뒤 recheckInputs·syncWork, setResult·innerHTML·저장소 없음, fetch 2곳(postRequest·sendPdf), pdfDownloader.run 1곳, resultRevision 증가 3곳(생성·편집 적용·원문 복원), 편집 적용·원문 복원은 진행 중 잠금, 버튼 초기 비활성·상태/오류 영역 역할, "준비 중" 안내 제거
- `python -W error::ResourceWarning -m unittest discover -s tests/test_common` → 56개 OK, `pip check` 이상 없음

### ResourceWarning 측정(이전 보고 정정)
- 위 제품소개서 전체 실행 출력에 "Exception ignored" 5건과 "ResourceWarning: unclosed file" 5건이 있었고 결과는 OK. GC 정리 중 경고는 -W error에서도 테스트를 실패시키지 않으므로 "경고를 오류로 처리한 실행 통과"가 경고 0건을 뜻하지 않음
- `-W always::ResourceWarning`로 파일별 실행: test_analyze_api.py 5건, test_pdf_download_api.py·test_pdf_catalog.py·test_generate_api.py·test_panel.py·test_review_logic.py 0건
- 이전 기록의 "10건"은 경고 줄과 "Enable tracemalloc" 안내 줄을 함께 센 줄 수(실제 경고 5건). 기존 분석 테스트 경고는 이번 범위에서 수정하지 않음
- 각 경고가 정확히 어느 테스트에서 생겼는지(GC 시점)는 미확인

### 미실행·미검증(브라우저 도구 없음)
- 실제 브라우저의 버튼 활성/비활성 전환, 확인창, "PDF 만드는 중…" 표시, 다운로드 저장, 초점·스크린리더 안내, 탭 이동 중 요청 유지
- 실제 생성 결과·편집본으로 받은 PDF 육안 확인, 다른 뷰어·인쇄

## 2026-10-26 PDF 다운로드 이전 결과 확인창 — 사용자 보고 조사
### 사용자 보고(Claude 미관찰)
- 생성 결과 있음 → 분석·검토 MOQ 단위 kg 수정 → PDF 다운로드 → 확인창 없이 다운로드

### Claude가 직접 실행한 재현(실제 브라우저 엔진, 모의 분석·생성)
- Edge headless + CDP, 로컬 서버(키 비움·.env 미로딩), 분석·생성은 브라우저 가로채기 모의 응답, PDF는 실제 렌더러. 스크립트: C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Desktop-fionex\36d7c2bf-67d2-469c-9a14-643e83056de0\scratchpad\cdp_repro\repro.mjs
- 결과(확인창 취소 후 PDF 요청·다운로드 / 확인 후 누적): MOQ "500 kgs" 0·0 / 1·1, 실제 키·마우스 "500 KG" 0·0 / 1·1, 원래 값 복원 0·0 / 1·1, 제품 설명 0·0 / 1·1, 표시명 0·0 / 1·1, MOQ 확인 해제 0·0 / 1·1, 확인창 문구 모두 "이 결과는 현재 입력과 다를 수 있습니다. 현재 미리보기 내용으로 PDF를 다운로드할까요?"
- 결과 문구 편집·적용만: 확인창 0회, 다운로드 진행(입력 불일치 경고 없음)
- 검토 화면 MOQ 값은 다운로드 후에도 사용자가 입력한 값 유지, 요청에는 기존 적용본 값 사용(Node 회귀로 확인)
- **보고 증상은 현재 코드에서 재현되지 않음. 원인 미확인 → 동작 코드 수정 없음**

### 테스트
- `node --check product_brochure.js` → 오류 없음(JS 변경 없음)
- `node review_logic_check.js` → 42개 통과(신규 2개: MOQ만 수정 시 취소 0회·확인 1회·기존 적용본 값 전송, 설명·표시명·표시명 확인·확인 해제·가상 표시·값 복원 감지, 결과 편집만은 미감지·수정본 전송)
- `unittest discover -s tests/test_product_brochure` → 1차 1건 실패(정적 검사 호출 수 예상 오류) → 수정 후 129개 OK
- `unittest discover -s tests/test_common` → 56개 OK

### 미검증
- 사용자 환경에서의 정확한 단계(결과 문구 편집 여부, 재적용·재생성 여부, 서버·탭 재시작 여부)
- 창 모드 실제 브라우저에서의 확인, 실제 생성 결과 사용

### 원인 확인(2026-10-26, 사용자 보고)
- 사용자 확인: MOQ 수정 위치는 결과 대화상자의 "문구 수정 → 미리보기에 적용". 이 경우 확인창 없이 다운로드되는 것이 정상(Claude 재현의 "결과 문구 편집·적용만: 확인창 0회"와 일치)
- 보고 원인: 편집 위치 혼동. 코드 결함 아님, 서비스 코드 변경 없음
- 미확인: 실제로 내려받은 PDF에 결과 편집 MOQ 값이 반영됐는지(사용자 확인 전). Claude가 확인한 것은 모의 데이터에서 요청 본문·서버 렌더링에 수정본 값이 쓰이는 것까지
