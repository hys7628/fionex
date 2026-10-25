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

## 2026-10-25 PDF AI 판독 검증 자료·캡처 (DEV-2026_10_25-07)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-25 | 모의 서버 스크립트(가짜 판독 함수) | 저장소 밖 세션 임시 폴더: C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/tools/mock_ocr_server.py | 직접 작성 | validation DEV-2026_10_25-07 | 가상 응답(MOCK 문구). 실제 판독 아님. 저장소에 넣지 않음 |
| 2026-10-25 | 화면 캡처 PNG(1440 전체, 모의 판독 결과) | C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/green_claim_ocr_mock_1440.png | Chrome 헤드리스 CDP | 같음 | 모의 결과 화면. 저장소에 넣지 않음 |
- PDF 자료는 이전 작업에서 만든 가상 PDF(fixtures/) 재사용. 실제 홍보물·스캔 문서 사용 안 함

## 2026-10-25 이미지 AI 판독 검증 자료·캡처 (DEV-2026_10_25-08)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-25 | 가상 이미지(한·영·포 가상 문구 JPG·PNG·팔레트 PNG·RGBA PNG·GIF) | 저장소 밖 세션 임시 폴더: C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/fixtures/img/ | .NET System.Drawing | validation DEV-2026_10_25-08 | 직접 만든 가상 문구(실제 홍보물 아님). 저장소에 넣지 않음 |
| 2026-10-25 | EXIF 방향 1~8 가상 JPEG·PDF | 같은 임시 폴더 fixtures/img/orient/ | 위 JPEG에 EXIF 추가(스크립트) | 같음 | 가상 자료. 저장소에 넣지 않음 |
| 2026-10-25 | 브라우저 흐름용 가상·손상 이미지 | 같은 임시 폴더 fixtures/img2/ | 스크립트(테스트 생성 함수 재사용) | 같음 | 가상 자료. 저장소에 넣지 않음 |
| 2026-10-25 | PDF 화면·<img> 대조 캡처 PNG | 같은 임시 폴더 fixtures/img/out/shot_*.png | Chrome 헤드리스 CDP | 같음 | 가상 자료 캡처. 저장소에 넣지 않음 |
| 2026-10-25 | 화면 캡처 PNG(1440 전체, 모의 이미지 판독 결과) | 같은 임시 폴더 green_claim_image_ocr_mock_1440.png | Chrome 헤드리스 CDP | 같음 | 모의 결과 화면. 저장소에 넣지 않음 |
| 2026-10-25 | 모의 서버·검증 스크립트 | 같은 임시 폴더 tools/mock_image_ocr_server.py, cdp_check_image_flow.mjs 등 | 직접 작성 | 같음 | 가짜 판독 함수(실제 판독 아님). 저장소에 넣지 않음 |
- 저장소 테스트(tests/test_image_ocr.py)는 가상 이미지를 메모리에서 생성하며 파일 자료를 추가하지 않음

## 2026-10-25 이미지 판독 보완 자료·캡처 (DEV-2026_10_25-08 후속)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-25 | 투명 배경 가상 문구 PNG(검정·흰색·반투명 빨강 글자) | 저장소 밖 세션 임시 폴더: C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/fixtures/img/alpha_*.png | Pillow(맑은 고딕 시스템 글꼴로 그림) | validation DEV-2026_10_25-08 후속 | 직접 만든 가상 문구. 글꼴은 로컬 렌더링에만 사용. 저장소에 넣지 않음 |
| 2026-10-25 | 판독용 사본 PDF와 Chrome PDF 화면 캡처 | 같은 임시 폴더 fixtures/img/out2/ | image_worker·image_input, Chrome 헤드리스 CDP | 같음 | 가상 자료. 저장소에 넣지 않음 |
| 2026-10-25 | 16비트 회색조 가상 PNG, 투명 PNG(브라우저 흐름용) | 같은 임시 폴더 fixtures/img2/gray16.png, alpha_black_text.png | 스크립트 | 같음 | 가상 자료. 저장소에 넣지 않음 |
| 2026-10-25 | 화면 캡처 PNG(1440 전체, 모의 이미지 판독 결과, 2차 갱신) | 같은 임시 폴더 green_claim_image_ocr_mock_1440.png(1차 파일을 덮어씀) | Chrome 헤드리스 CDP | 같음 | 모의 결과 화면. 저장소에 넣지 않음 |
- 저장소 테스트(tests/test_image_ocr.py)는 가상 이미지를 메모리에서 생성하며 파일 자료를 추가하지 않음

## 2026-10-26 구조화 기준 묶음 (DEV-2026_10_26-01)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-26 | 구조화 기준 묶음 JSON(CDC·CONAR 원문 발췌·비공식 번역·검토 지침 포함) | features/green_claim/data/brazil_claim_criteria/criteria_bundle.json | 저장소 밖 생성 스크립트(scratchpad/tools/build_criteria_bundle.py)가 기존 md 칸을 그대로 옮김 | validation DEV-2026_10_26-01 | CDC는 법령 텍스트 저장(법률 검토 없음). **CONAR 발췌 포함, AI 이용 허가 미확인**(source_register.md). 번역은 비공식 |
| 2026-10-26 | 묶음 생성 스크립트 | 저장소 밖 세션 임시 폴더: C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/tools/build_criteria_bundle.py | 직접 작성 | 같음 | 저장소에 넣지 않음. 갱신 기능에서 정식화 필요 |

## 2026-10-26 기준 갱신 관리 자료 (DEV-2026_10_26-02)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-26 | 묶음 생성 입력(자료 메타데이터 JSON) | features/green_claim/data/brazil_claim_criteria/sources_meta.json | 기존 criteria_bundle.json의 sources 값을 스크립트로 그대로 옮김 | validation DEV-2026_10_26-02 | CONAR 자료의 AI 이용 허가 미확인 메모 포함(기존 기록 유지) |
| 2026-10-26 | 실행 상태·작업 폴더 Git 제외 설정 | features/green_claim/data/criteria_state/.gitignore, data/criteria_work/.gitignore | 직접 작성 | 같음 | 사용자 자료 저장 없음 |
| 2026-10-26 | 실제 페이지 구조 비교 스크립트 | 저장소 밖 세션 임시 폴더: C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/010a049a-1a72-42db-bb4c-cb26f412c3b5/scratchpad/tools/check_real_copies.py | 직접 작성 | 같음 | 2026-10-25 공식 페이지 사본 사용(네트워크 없음). 저장소에 넣지 않음 |
- 이번 작업에서 활성화한 기준 버전(criteria_versions/)·포인터(active.json)는 없다.

## 2026-10-26 후속: 조항 비교 범위 정보 (DEV-2026_10_26-02 후속)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-26 | 조항 단위 비교 범위 JSON(단위 이름·full/partial/unbounded만, 원문 없음) | features/green_claim/data/brazil_claim_criteria/comparison_units.json | 저장소 밖 스크립트(scratchpad/tools/make_comparison_units.py)가 criteria_check.measure_coverage로 2026-10-25 사본 판정 | validation DEV-2026_10_26-02 후속 | CONAR 조항 이름 포함(원문 텍스트 없음). CONAR AI 이용 허가 미확인 유지 |

## 2026-10-26 검수 실행·결과 화면 확인 자료 (DEV-2026_10_26-04)
| 날짜 | 종류 | 경로 | 생성 도구 | 관련 기록 | 사용권·검토 상태 |
|---|---|---|---|---|---|
| 2026-10-26 | 모의 결과 화면 캡처(1440px·390px) | 저장소 밖 세션 임시 폴더: C:/Users/user/AppData/Local/Temp/claude/c--Users-user-Desktop-2nd-project/c1b73469-0709-47ec-9be6-9389670902ea/scratchpad/review_desktop_1440.png, review_mobile_390.png | 헤드리스 Chrome CDP 캡처 | validation DEV-2026_10_26-04 | 가상 문구·가짜 응답 화면(실제 검수 결과 아님). 저장소에 넣지 않음 |
| 2026-10-26 | 검수 화면 확인 스크립트·외부 통신 차단 서버 실행 파일 | 같은 폴더 tools/cdp_check_review_flow.mjs, net_guard.py, real_server.py | 직접 작성 | 같음 | 저장소에 넣지 않음 |
| 2026-10-26 | 회귀 스크립트·모의 판독 서버 복사본 | 같은 폴더 tools/cdp_check_{green_claim,pdf_flow,word_flow,ocr_flow,image_flow}.mjs, mock_ocr_server.py, mock_image_ocr_server.py (원본: 세션 010a049a… scratchpad/tools, 원본은 수정하지 않음) | 복사 후 검수 버튼 기대값·차단 장치만 수정 | 같음 | 공개·가상 fixture만 사용(같은 원본 세션 fixtures 복사) |
