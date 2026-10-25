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
