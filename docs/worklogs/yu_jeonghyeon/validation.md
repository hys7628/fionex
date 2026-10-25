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
