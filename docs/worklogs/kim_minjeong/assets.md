# 결과물 경로

현재 기록 없음. 아래 항목을 실제 작업 후 추가하세요.

날짜 / 종류 / 경로 / 생성 도구 / 관련 실험 / 사용권·검토 상태

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

## 2026-10-25 기준 자료 (DEV-2026_10_25-02)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-25 | 출처 목록(md) | features/green_claim/data/brazil_claim_criteria/source_register.md | Claude Code 작성 | prompt_log DEV-2026_10_25-02 | 자체 작성. 담당자 검토 전 |
| 2026-10-25 | CDC 원문 발췌(md) | features/green_claim/data/brazil_claim_criteria/cdc_l8078_excerpt.md | Planalto HTML에서 프로그램으로 줄 단위 추출 | 같음 | 법률 텍스트(Lei 9.610/98 Art. 8º IV). 법률 검토 없음 |
| 2026-10-25 | 한국어 기준 정리(md) | features/green_claim/data/brazil_claim_criteria/review_criteria_ko.md | Claude Code 작성(비공식 번역) | 같음 | CDC 부분만 번역. CONAR 부분은 번호·제목만. 사람 검토 전 |
| 2026-10-25 | CONAR 웹 본문·PDF·약관 사본 | 저장소에 넣지 않음(세션 임시 폴더에만 존재) | curl 1회 조회 | 같음 | CONAR 이용약관 제한으로 저장 보류 |

## 2026-10-25 CONAR 발췌 보완 (DEV-2026_10_25-03)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-25 | CONAR 원문 발췌(md) | features/green_claim/data/brazil_claim_criteria/conar_excerpt.md | 웹 확보본(16:31:51)에서 프로그램으로 줄 단위 추출 | prompt_log DEV-2026_10_25-03 | CONAR 저작물. 출처 표시함. 약관상 일부 복제 조건 있음. **AI 이용 허가 미확인**, 상업 목적 해당 여부 미확인 |
| 2026-10-25 | CONAR 비공식 번역·검토 지침(md 내 절 추가) | features/green_claim/data/brazil_claim_criteria/review_criteria_ko.md | Claude Code 작성 | 같음 | 비공식 번역. 사람·전문가 검토 전. AI 이용 허가 미확인 |
- 직전 항목의 "CONAR 사본 저장 보류" 기록은 그 시점 판단으로 유지한다. 웹·PDF·약관 사본 원본은 이번에도 저장소에 넣지 않았다(세션 임시 폴더에만 존재).

## 2026-10-25 문구 직접 입력 화면 캡처 (DEV-2026_10_25-04)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-25 | 화면 캡처 PNG(1440×900) | 저장소 밖 세션 임시 폴더: C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/green_claim_desktop_1440.png | Chrome 헤드리스 CDP | validation 2026-10-25 문구 직접 입력 | 자체 화면, 가상 입력 문구. 저장소에 넣지 않음(임시 파일이라 사라질 수 있음) |
| 2026-10-25 | 화면 캡처 PNG(390×844) | 같은 폴더의 green_claim_mobile_390.png | 같음 | 같음 | 같음 |

## 2026-10-25 일반 PDF 추출 테스트 자료·캡처 (DEV-2026_10_25-05)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-25 | 가상 테스트 PDF 12개(3개 언어, 일부 텍스트 없음, 텍스트 없음, 20/21페이지, 20,000자 초과, 암호화, 손상, 가짜 PDF, .docx, 10,000,000/10,000,001바이트) | 저장소 밖 세션 임시 폴더: C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/fixtures/ | Chrome 헤드리스 printToPDF, pypdf, 표준 라이브러리 | validation DEV-2026_10_25-05 | 직접 만든 가상 문구. 실제 홍보물 아님. 저장소에 넣지 않음(임시 파일이라 사라질 수 있음) |
| 2026-10-25 | 화면 캡처 PNG(1440 전체, 390 모바일) | C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/green_claim_pdf_desktop_1440.png, green_claim_pdf_mobile_390.png | Chrome 헤드리스 CDP | 같음 | 자체 화면, 가상 입력. 저장소에 넣지 않음 |
- 저장소 안 테스트 자료는 features/green_claim/tests/test_pdf_extract.py가 실행 중에 메모리에서 만드는 가상 PDF뿐(파일로 저장하지 않음)

## 2026-10-25 Word 추출 테스트 자료·캡처 (DEV-2026_10_25-06)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-25 | 가상 Word 테스트 자료 12개(다국어·병합·중첩·링크, 미지원 요소, 이미지만, 20,000자 초과, docm형, 다른 ZIP, 손상, .doc, 항목 1,001, 해제 초과, 10,000,000/10,000,001바이트) | 저장소 밖 세션 임시 폴더: C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/fixtures/ (word_*.docx, legacy.doc) | python-docx, zipfile | validation DEV-2026_10_25-06 | 직접 만든 가상 문구. 실제 홍보물 아님. 저장소에 넣지 않음(임시) |
| 2026-10-25 | 화면 캡처 PNG(1440 전체) | C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/green_claim_word_desktop_1440.png | Chrome 헤드리스 CDP | 같음 | 자체 화면, 가상 입력. 저장소에 넣지 않음 |
- 저장소 안 테스트 자료는 features/green_claim/tests/test_docx_extract.py가 실행 중에 메모리에서 만드는 가상 문서뿐
