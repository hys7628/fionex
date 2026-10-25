# 출처

현재 기록 없음. 아래 항목을 실제 작업 후 추가하세요.

자료명 / 기관 / URL·파일 경로 / 조회일 / 적용 제품·범위 / 사용권

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

## 2026-10-25 그린 클레임 명세 기준 자료 (전달받은 출처, 미조회)
| 자료명 | 기관 | URL | 조회일 | 적용 범위 | 상태 |
|---|---|---|---|---|---|
| CDC 브라질 소비자보호법(Lei nº 8.078) 통합본 | 브라질 연방정부 Planalto | https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm | 미조회 | 관련 광고 조항(정확한 조항 미확인) | 담당자 합의 내용으로 전달받음. 접근·최신성·조항 미검증 |
| CONAR 광고 자율규제 코드(환경 관련 조항, 부속서 U) | CONAR | https://www.conar.org.br/codigos | 미조회 | 환경 관련 조항·부속서 U(정확한 조항 미확인) | 담당자 합의 내용으로 전달받음. 접근·최신성·조항 미검증 |

- 사용권: 미확인. 자료 준비 단계에서 확인
- 직접 확인한 로컬 자료: docs/decisions.md, docs/data_contracts.md, common/ai_client.py, common/config.py, common/errors.py, requirements.txt, .env.example(변수 이름·모델 후보만 확인, 비밀값 미출력)

## 2026-10-25 기준 자료 실제 조회 (DEV-2026_10_25-02)
이전 항목의 "미조회" 기록은 그 시점 상태로 유지하고, 이번 실제 조회 결과를 추가한다. 상세: features/green_claim/data/brazil_claim_criteria/source_register.md
| 자료명 | 기관 | URL | 조회 시각(KST) | 결과 | 적용 범위·버전 | 사용권 |
|---|---|---|---|---|---|---|
| CDC Lei nº 8.078/1990 통합본 | Planalto(Casa Civil) | https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm | 2026-10-25 16:31:44 | HTTP 200, 본문 확인 | Art. 2·3·6·29·30·31·36·37·38·60·66·67·69·118. 최근 개정 표기 MP 1.393/2026(Art. 57). 시행 Art. 118 | Lei 9.610/98 Art. 8º IV(법률 텍스트 비보호) 원문 확인. 법률 검토 없음. 사이트 약관 미확인 |
| CONAR 코드 웹 게시본 | CONAR | https://www.conar.org.br/codigos | 2026-10-25 16:31:51 | HTTP 200, 본문 확인 | Artigo 8·17·18·27·36·36-A·36-B, Anexo "U" | 이용약관상 제한 → 저장 보류 |
| CONAR 코드 PDF "Edição 2025" | CONAR | https://conar.wpenginepowered.com/wp-content/uploads/2026/08/Codigo_CONAR_2026.pdf | 2026-10-25 16:33:58 | HTTP 200, 텍스트 추출 확인 | Anexo U 개정 2025년 11월 승인(각주). 시행일 미확인 | 이용약관상 제한 → 저장 보류 |
| CONAR 이용약관 | CONAR | https://www.conar.org.br/termos-de-uso | 2026-10-25 16:34:00 | HTTP 200, 본문 확인 | 2026년 5월 이사회 제정 | - |
| Lei nº 9.610/1998 | Planalto(Casa Civil) | https://www.planalto.gov.br/ccivil_03/leis/l9610.htm | 2026-10-25 16:35:20 | HTTP 200, Art. 8º 확인 | 사용권 판단 근거 | - |
- 미조회: 영문 PDF(Brazilian_Advertising_Self-Regulation.pdf, 링크만 확인)

## 2026-10-25 CONAR 발췌 보완 (DEV-2026_10_25-03)
이전 항목(미조회, 저장 보류)은 그대로 유지하고 후속 내용을 추가한다. 이번에는 새로 접속하지 않았다.
| 자료 | 기관 | URL | 확인 시각(KST) | 자료 경로 | 버전 | 이용 조건 |
|---|---|---|---|---|---|---|
| CONAR 코드 웹 게시본 | CONAR | https://www.conar.org.br/codigos | 2026-10-25 16:31:51(직전 확보본 사용) | features/green_claim/data/brazil_claim_criteria/conar_excerpt.md | PDF "Edição 2025"와 대조. Anexo U 개정 2025년 11월 승인(PDF 각주) | 일부 복제는 의미 유지·비상업·출처 표시 조건으로 허용. AI 입력·자동 수집·상업 이용은 사전 허가 필요. **AI 이용 허가 미확인** |
| CONAR 코드 PDF | CONAR | https://conar.wpenginepowered.com/wp-content/uploads/2026/08/Codigo_CONAR_2026.pdf | 2026-10-25 16:33:58(직전 확보본 사용) | 저장소에 넣지 않음(대조용) | 같음 | 같음 |
| CONAR 이용약관 | CONAR | https://www.conar.org.br/termos-de-uso | 2026-10-25 16:34:00(직전 확보본, 재확인 안 함) | source_register.md 요약 | 2026년 5월 제정 | - |
- 담당자의 요구사항 유지 결정은 이용 허가가 아님

## 2026-10-25 일반 PDF 추출 구현 참고 (DEV-2026_10_25-05)
| 자료 | 위치 | 확인 시각(KST) | 확인 내용 | 상태 |
|---|---|---|---|---|
| pypdf 6.21.2 패키지 메타데이터 | PyPI(pip index·pip install --dry-run --report), https://files.pythonhosted.org/packages/1b/4d/c9d2d67f204eff463237a1a8f5e25a6923b7b1043982b91fcaf104c8ef60/pypdf-6.21.2-py3-none-any.whl | 2026-10-25 17:40 무렵 | Requires-Python >=3.9, Python 3.11 필수 의존성 없음(typing_extensions는 3.11 미만만), crypto extra 선택 | pip로 직접 확인. 공식 문서 웹페이지는 조회하지 않음 |
| pypdf 설치본 API | jasonenv site-packages/pypdf (inspect) | 2026-10-25 17:43 무렵 | PdfReader(strict, password), is_encrypted, extract_text, PdfWriter.encrypt(algorithm), errors 목록 | 설치본에서 직접 확인 |
| Werkzeug 3.1.9 소스 | jasonenv site-packages/werkzeug/formparser.py, sansio/multipart.py, wsgi.py | 2026-10-25 17:38~17:48 | default_stream_factory가 500KB 초과 시 SpooledTemporaryFile, FormDataParser(stream_factory, max_content_length, max_form_memory_size, max_form_parts), max_form_memory_size가 수신 버퍼에도 적용 | 설치본 소스 직접 확인 |
| Flask 3.1.2 소스 | jasonenv site-packages/flask/wrappers.py | 2026-10-25 17:38 무렵 | Request.max_content_length 요청별 설정 가능(이번에는 FormDataParser로 처리) | 설치본 소스 직접 확인 |
- 사용권: pypdf 라이선스는 이번에 확인하지 않음(미확인)

## 2026-10-25 Word 추출 구현 참고 (DEV-2026_10_25-06)
| 자료 | 위치 | 확인 시각(KST) | 확인 내용 | 상태 |
|---|---|---|---|---|
| python-docx 1.2.0 | PyPI JSON API https://pypi.org/pypi/python-docx/1.2.0/json, pip --dry-run --report | 2026-10-25 19:59 | Requires-Python >=3.9, requires lxml>=3.1.0·typing_extensions>=4.9.0, MIT, 2025-06-16 업로드, yanked 아님 | 직접 조회 |
| lxml 6.1.3 | https://pypi.org/pypi/lxml/6.1.3/json | 2026-10-25 19:59 | Requires-Python >=3.8, BSD-3-Clause, cp311 win_amd64 wheel, 2026-09-02 업로드, yanked 아님 | 직접 조회 |
| typing_extensions 4.16.0 | https://pypi.org/pypi/typing_extensions/4.16.0/json | 2026-10-25 19:59 | Requires-Python >=3.9, PSF-2.0, 2026-07-02 업로드, yanked 아님 | 직접 조회 |
| python-docx 1.2.0 설치본 소스 | jasonenv site-packages/docx (oxml/parser.py, document.py, blkcntnr.py, table.py, text/paragraph.py, oxml/text/paragraph.py) | 2026-10-25 20:00 무렵 | XMLParser(resolve_entities=False), iter_inner_content 문서 순서·감싸인 요소 제외, Paragraph.text = w:r·w:hyperlink, row.cells가 병합 셀 반복, _Cell.iter_inner_content | 설치본 직접 확인 |
| 공통 PDF 연결(develop 병합분) | common/pdf_utils.py, common/config.py, docs/data_contracts.md | 2026-10-25 19:45 무렵 | inspect_pdf 순서·상한(10 MiB, 20쪽), 하위 클래스 암호 해제 차단, pypdf 로거 전파 차단 | 로컬 파일 읽기 전용 |
- 사용권: python-docx·lxml·typing_extensions 라이선스는 PyPI 메타데이터 표기만 확인(라이선스 원문 검토 안 함)

## 2026-10-25 PDF AI 판독 구현 참고 (DEV-2026_10_25-07)
| 자료 | 위치 | 확인 시각(KST) | 확인 내용 | 상태 |
|---|---|---|---|---|
| 공통 PDF 입력 연결 | common/ai_client.py generate_structured_from_pdf, _check_structured_args, _structured_result | 2026-10-25 20:27 무렵 | inspect_pdf 선행, OPENAI_MODEL, input_file(base64, 고정 파일명, detail), responses.parse, incomplete·failed·refusal·스키마 불일치 오류 처리, 스키마는 pydantic BaseModel | 로컬 파일 읽기 전용 |
| 공통 설정 | common/config.py | 같음 | PDF_TIMEOUT_SECONDS 120, PDF_MAX_RETRIES 0, PDF_MAX_OUTPUT_TOKENS 4096, PDF_STORE False, PDF_DETAIL high, PDF_MAX_BYTES 10 MiB, PDF_MAX_PAGES 20 | 로컬 파일 읽기 전용 |
| 공통 오류 | common/errors.py | 같음 | AIError 계열 code·http_status·retryable, PdfValidationError 계열 | 로컬 파일 읽기 전용 |
| 공통 연결 문서 | docs/data_contracts.md(develop 병합분) | 같음 | 공식 file-inputs 가이드 근거(detail, 공급자 상한 50 MB), 스캔 PDF 처리는 가이드에 명시 없음, store=False가 모든 보관을 없애지 않음 | 공통 문서 내용 확인(공식 가이드는 이번에 직접 조회하지 않음) |
| .env.example | 저장소 루트 | 같음 | 변수 이름 OPENAI_API_KEY·OPENAI_MODEL·OPENAI_IMAGE_MODEL만 확인 | 값 미확인·미출력 |
- OpenAI 공식 문서는 이번에 직접 조회하지 않음(공통 문서의 기록만 참고)

## 2026-10-25 이미지 AI 판독 구현 참고 (DEV-2026_10_25-08)
| 자료 | 위치 | 확인 시각(KST) | 확인 내용 | 상태 |
|---|---|---|---|---|
| 공통 AI 연결 | common/ai_client.py | 2026-10-25 21:25 무렵 | 이미지 입력 함수 없음(generate_image는 Images API 생성 전용). generate_structured_from_pdf는 PDF bytes·inspect_pdf 통과·고정 파일명 document.pdf | 로컬 파일 읽기 전용 |
| 공통 설정·PDF 검사 | common/config.py, common/pdf_utils.py | 같음 | PDF 10 MiB·20쪽, timeout 120초, 재시도 0, 출력 4,096토큰, store=False, detail high | 로컬 파일 읽기 전용 |
| 공통 결정 | docs/decisions.md, docs/data_contracts.md | 같음 | "이미지 분석 입력" 공통 첫 범위 제외, 스캔·이미지 전용 PDF 처리는 공식 가이드에 명시 없음(공통 문서 기록) | 로컬 문서 확인 |
| 설치 패키지 | jasonenv pip list | 같음 | Pillow 등 이미지 디코더 없음. 사용: 파이썬 표준 라이브러리(zlib·struct), 기존 pypdf(검증용 PDF 읽기) | 패키지 추가·변경 없음 |
| PNG·JPEG·EXIF·PDF 형식 | 공개 형식 사양(PNG 청크·CRC·필터, JPEG 마커·SOF, EXIF Orientation 1~8, PDF 이미지 XObject·DCTDecode·FlateDecode 예측기·색상 키 마스크) | 같음 | 일반 지식으로 구현. 이번에 공식 사양 문서를 직접 조회하지 않음. 동작은 Chrome 디코딩·PDF 화면 대조와 단위 테스트로만 확인 | 공식 문서 미조회 |
| Windows 기본 그래픽(가상 자료 생성) | .NET System.Drawing(Windows PowerShell 5.1) | 같음 | 가상 문구 JPG·PNG·팔레트 PNG·GIF 생성. 저장소에 넣지 않음 | 설치 없음 |
- OpenAI 공식 문서(이미지 입력·PDF 렌더링 방식)는 이번에 조회하지 않음

## 2026-10-25 이미지 판독 보완 참고 (DEV-2026_10_25-08 후속)
| 자료 | 위치 | 확인 시각(KST) | 확인 내용 | 상태 |
|---|---|---|---|---|
| PyPI Pillow JSON | https://pypi.org/pypi/pillow/json | 2026-10-25 22:00 무렵 | 최신 13.0.0(2026-10-16 공개, requires_python >=3.11, cp311 win_amd64 wheel), 12.3.0(2026-07-01, >=3.10, cp311 wheel). 철회 없음 | 공식 배포처 조회 |
| Pillow 13.0.0 릴리스 노트 | https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html | 같음 | Python 3.10 지원 종료, JPEG 디코더 버퍼 오버플로 등 보안 수정, APNG·MPO 압축 폭탄 우회 수정, I;16N 변환 수정, getdata 폐기 예정 | 공식 문서 조회(요약 도구로 읽음) |
| Pillow Python 지원 표 | https://pillow.readthedocs.io/en/stable/installation/python-support.html | 같음 | Pillow 13.0: Python 3.11~3.15, 12.x: 3.10~3.14 | 공식 문서 조회 |
| 설치 결과 | jasonenv pip install pillow==13.0.0 | 같음 | 설치 1개, 하위 의존성 없음, pip check 정상, License-Expression MIT-CMU, 내장 libjpeg-turbo 8.0·zlib-ng 확인 | 실제 설치 |
| Pillow 동작 | 로컬 확인 스크립트(저장소 밖) | 같음 | 16비트 회색 변환 잘림, verify/load 차이, MPO·APNG 프레임, exif_transpose 후 info 유지 등(validation 기록) | 실제 실행 |
- 이미지 형식 사양(PNG·JPEG·EXIF) 원문은 이번에도 직접 조회하지 않음. OpenAI 공식 문서도 조회하지 않음

## 2026-10-26 기준 자료 로더 재사용 자료 (DEV-2026_10_26-01)
- 이번에는 공식 사이트(Planalto·CONAR)를 새로 조회하지 않았다. 저장소의 기존 자료만 재사용했다.
| 재사용 자료 | 위치 | 원래 조회 정보 | 이번 사용 |
|---|---|---|---|
| CDC 원문 발췌 | features/green_claim/data/brazil_claim_criteria/cdc_l8078_excerpt.md | SRC-CDC, 2026-10-25 16:31:44 조회 | 구조화 기준 text_pt, 미수정 |
| CONAR 원문 발췌 | 같은 폴더 conar_excerpt.md | SRC-CONAR-WEB 2026-10-25 16:31:51 확보본, SRC-CONAR-PDF 16:33:58 대조 | 구조화 기준 text_pt, 미수정 |
| 한국어 비공식 번역·검토 지침 | 같은 폴더 review_criteria_ko.md | 2026-10-25 작성(개발 도구 비공식 번역, pontuais 정정 반영본) | 번역·지침·한계 칸, 미수정 |
| 출처 목록·사용권 | 같은 폴더 source_register.md | 2026-10-25 기록(CONAR 이용약관 16:34:00 확인, AI 이용 허가 미확인) | 자료 정보·대조, 미수정 |
- 구조화 파일의 retrieved_at은 위 원래 조회 시각이며, bundle_created_at(2026-10-26 00:35:43)은 구조화 파일 작성 시각이다.

## 2026-10-26 기준 변경 확인 기능의 자료 사용 (DEV-2026_10_26-02)
- 실제 조회: 없음. Planalto·CONAR 공식 사이트에 이번 작업에서 접속하지 않았다(조회 보류 이유는 prompt_log 같은 ID 참고).
- 기존 자료 재사용
| 자료 | 위치 | 원래 조회 | 이번 사용 |
|---|---|---|---|
| 출처 URL·조회 시각 | features/green_claim/data/brazil_claim_criteria/source_register.md | 2026-10-25 16:31:44(CDC)·16:31:51(CONAR 웹)·16:33:58(CONAR PDF)·16:34:00(CONAR 약관) | 확인 대상 URL·정책 근거, 미수정 |
| 기존 기준 묶음 sources | 같은 폴더 criteria_bundle.json | 2026-10-26 00:35:43 작성 | sources_meta.json으로 값 그대로 옮김, 묶음 미수정 |
| 공식 페이지 사본 | 저장소 밖 세션 임시 폴더 C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/src/cdc.htm, conar_codigos.html | 2026-10-25 16:31 무렵 내려받은 사본(source_register.md의 조회와 같은 사본) | 비교 기능을 실제 페이지 구조로 확인(네트워크 없음). 저장소에 넣지 않음. CONAR 사본은 개발 도구가 다시 읽었음 |
- 이번 결과의 "변경 없음"은 위 2026-10-25 사본 기준이며, 현재 공식 페이지의 최신성을 확인한 것이 아니다.

## 2026-10-26 후속: 조항 비교 범위 판정 자료 (DEV-2026_10_26-02 후속)
- 실제 조회: 없음.
- 재사용: 저장소 밖 세션 임시 폴더의 2026-10-25 공식 페이지 사본(cdc.htm 16:31 무렵 SRC-CDC 확보본, conar_codigos.html SRC-CONAR-WEB 확보본)을 comparison_units.json 판정과 비교 확인에만 사용. 사본 원문은 저장소에 넣지 않았고 comparison_units.json에는 단위 이름과 범위 표시만 있다.

## 2026-10-26 문구 검수 서버 재사용 자료 (DEV-2026_10_26-03)
- 실제 조회: 없음(공식 사이트·OpenAI 모두).
| 재사용 | 위치 | 확인 상태 |
|---|---|---|
| 기준 묶음(활성 base, 2026-10-26.1) | features/green_claim/data/brazil_claim_criteria/ | 원문 확보 2026-10-25, 최신성 재확인 없음, CONAR AI 이용 허가 미확인 |
| 기준 확인·상태 | criteria_check.check_sources·criteria_status | 2026-10-26 구현, 가짜 응답으로만 확인 |
| 공통 텍스트 연결 | common/ai_client.py generate_structured, common/config.py TEXT_* | 로컬 코드 읽기 전용 확인: timeout 60초, 재시도 0, 출력 상한 4,096, store=False. 공통 문서상 텍스트 함수 실제 호출은 사용자 실행으로 확인됨, 이 기능의 실제 호출은 미검증 |
