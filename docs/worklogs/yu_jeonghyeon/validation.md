# 검증 기록

현재 기록 없음. 아래 항목을 실제 작업 후 추가하세요.

날짜 / 변경 내용 / 검증 절차 / 기대 / 실제 / 판정 / 미검증

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

---

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
