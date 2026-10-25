# 검증 기록

현재 기록 없음. 아래 항목을 실제 작업 후 추가하세요.

날짜 / 변경 내용 / 검증 절차 / 기대 / 실제 / 판정 / 미검증

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

## 2026-10-25 그린 클레임 명세 구체화 (문서 검증만)
- 변경 내용: features/green_claim/feature_spec.md 구체화(prompt_log.md DEV-2026_10_25-01)
- 수행한 검증과 실제 결과
  - Git 상태: 브랜치 feature/green_claim, 작업 전 변경 없음, HEAD = origin/develop(05ac128). 원격 최신성은 마지막 fetch(2026-10-25 15:43 KST) 이후 미확인. 로컬 develop은 origin/develop보다 4커밋 뒤
  - 규칙 문서(CLAUDE.md, AGENTS.md, development.md, git_rules.md, recording_rules.md, design_system.md)는 Initial commit 대비 변경 없음을 git diff로 확인
  - 공통 연결 대조: 담당 유정현, 텍스트 구조화·이미지 생성 구현, OPENAI_MODEL 초기 후보 gpt-5.4-mini, 모델 코드 미고정, 텍스트 timeout 60초, 재시도 0회·자동 모델 전환 없음, 이미지 생성은 판독 기능 아님, PDF·스캔 PDF·이미지 분석 입력 미구현, 실제 호출 확인과 품질·비용·시간 검증 구분 → 전달받은 내용과 로컬 파일 일치
  - 명세 반영 확인: 최상위 5개 절 유지, 합의 핵심 문구 34개를 grep으로 확인해 모두 존재. 120초는 "확정값 아님" 문맥에만 등장
  - 삭제된 기존 줄 5개 확인: 내용은 새 절로 옮기거나 확정 내용으로 대체
  - 범위: git diff --stat 결과 feature_spec.md 외 추적 파일 변경 없음(개인 기록 3개 추가 후 최종 확인은 아래)
- 판정: 문서 검증 통과(문서 범위 한정)
- 미실행: 기능 테스트, 서버 실행, OpenAI API 호출, 파일 추출·PDF 생성, CDC·CONAR URL 조회, 브라우저 확인. 기능 미구현이므로 기능 동작은 검증 대상 아님
- 최종 범위 확인(기록 추가 후): git status 변경 4개(feature_spec.md, prompt_log.md, validation.md, sources.md), 미추적 파일 없음, 개인 기록 파일의 기존 줄 삭제 0건

## 2026-10-25 기준 자료 확인 (DEV-2026_10_25-02, 자료 확인만)
- 변경 내용: features/green_claim/data/brazil_claim_criteria/ 3개 파일 추가, data/README.md 갱신
- 수행한 검증과 실제 결과
  - 오류·로그인 페이지 여부: 5개 URL 모두 HTTP 200. CDC 본문에 "LEI Nº 8.078"과 Art. 1~119, CONAR 본문에 Seção 10·Anexo "U"·Anexo "V" 시작부, PDF는 %PDF-1.7 서명과 표지 "Edição 2025" 확인
  - 글자 깨짐: 추출 텍스트와 저장 파일 3개 모두 대체 문자(U+FFFD) 0건. CDC는 windows-1252로 해독
  - CDC 취소선(폐지 문안) 혼입: 원본 HTML에 <strike>·line-through 0건, 관련 조항 구간 0건
  - 발췌 대응: cdc_l8078_excerpt.md 인용 38줄 모두 원문 텍스트 줄과 정확히 일치
  - 한국어 정리 대응: review_criteria_ko.md의 포르투갈어 인용 10개 모두 발췌본·원문에 존재
  - CONAR 저장 보류 확인: 저장 파일 3개와 CONAR 본문 간 12단어 연속 일치 0건
  - CONAR 웹·PDF 대조: Seção 10·Anexo U 단어 단위 비교. 실질 문구 차이 없음(목록 기호·하이픈·각주 위치 차이만)
  - 조회 시각·출처 일치: source_register.md, review_criteria_ko.md, cdc_l8078_excerpt.md의 URL·시각이 실제 조회 기록과 같음
  - 줄바꿈: 새 파일·README 모두 CRLF
- 판정: 자료 확인 통과(자료 범위 한정)
- 미실행·미검증: 기능 테스트, 검수 품질 검증, 법률 전문가 검토, 번역 사람 검토, CDC·CONAR의 B2B 적용 해석, Anexo U 시행일, 영문 PDF 대조

## 2026-10-25 CONAR 발췌·번역 자료 확인 (DEV-2026_10_25-03, 자료 확인만)
- 변경 내용: conar_excerpt.md 추가, review_criteria_ko.md·source_register.md·data/README.md에 후속 내용 추가
- 수행한 검증과 실제 결과
  - 오류·빈 자료 여부: 사용한 확보본은 직전 작업에서 HTTP 200·본문 포함을 확인한 것. 발췌 103줄 모두 비어 있지 않음
  - 조항 번호와 발췌 일치: 줄 번호 지정 전에 각 줄 앞부분을 출력해 조항 위치를 확인. 발췌 103/103줄이 웹 확보본 텍스트 줄과 정확히 일치
  - 웹·PDF 대조: 98줄 일치, 5줄 비실질 차이(idéias/ideias, ambigüidade/ambiguidade, 제목 구분 기호, 하이픈 추출 손실, 각주 위치). 목록 기호 a.~h.는 웹의 <ol type="a">와 PDF 표기가 같음을 확인
  - 한국어 정리 대응: 상세 기준 15개 항목의 ID가 발췌본·기존 표 ID와 일치. 원문 발췌 인용 16개 모두 발췌본·웹 원문에 존재. 15개 항목 모두 필수 필드(조항, 원문 발췌, 비공식 번역, 원문 요구, 검토 지침, 적용 범위와 해석 한계, 제품 증빙) 포함
  - 번역 검토(개발 도구 자체 점검): 원문 조건·범위를 바꾼 2곳 발견해 수정("pontuais", 9.2.3 c 조건 누락). 사람·전문가 검토는 아님
  - 원문 내용과 서비스 지침 구분: "원문 요구"와 "검토 지침" 필드로 분리
  - 이용 상태 표현: "사용권 확보", "약관 문제 해결", "시연이므로 허용" 등 금지 표현 0건(부정문 1건 확인)
  - 글자 깨짐: 새·수정 파일 모두 U+FFFD 0건, CRLF 통일
  - 범위: CDC 발췌 파일 변경 없음, data 폴더 기존 줄 삭제 0건
- 판정: 자료 확인 통과(자료 범위 한정)
- 미실행·미검증: 기능 테스트, 검수 품질 검증, 번역의 사람 검토, 법률 전문가 검토, CONAR 사이트 재접속(이번에는 하지 않음), 각주 법령 원문 조회, AI 이용 허가 확인

## 2026-10-25 "pontuais" 번역 대조 (DEV-2026_10_25-03 후속, 자료 확인만)
- 대조 대상: conar_excerpt.md CONAR-36B b(Artigo 36-B b), CONAR-U-2(Anexo "U" II.2) 원문 전체 문장
- 실제 대조 결과: 두 원문 모두 "pontuais, específicos ou relacionados a determinadas partes do produto ou etapas isoladas do ciclo de vida"로 같은 구절. 뒤 문장은 "o alcance, condições ou limites do benefício divulgado"를 한정하라는 내용으로, pontuais는 시간이 아니라 범위가 국한된 이익을 가리킨다고 판단(개발 도구 판단, 전문가 검토 아님)
- 수정 후 확인
  - review_criteria_ko.md에 "단발적"·"일시적" 0건
  - conar_excerpt.md 수정 전후 MD5 동일(원문 변경 없음)
  - 상세 기준 ID 15개 일치, 원문 발췌 인용 16개 모두 발췌본·웹 원문에 존재, 금지 표현 0건(부정문 1건 제외), U+FFFD 0건, CRLF 유지
- 미검증: 번역의 사람·법률 전문가 검토

## 2026-10-25 문구 직접 입력 화면 확인 (DEV-2026_10_25-04)
- 환경: jasonenv Python 3.11.17(C:/Users/user/miniforge3/envs/jasonenv/python.exe), Flask 3.1.2, OPENAI_API_KEY 미사용. 기존 5003 서버 없음 확인 후 `-B`·재시작기 끔으로 실행, 확인 후 직접 띄운 서버만 종료. Chrome 헤드리스(--headless=new) + Node 24 내장 WebSocket으로 CDP 제어(설치 없음). 검증 스크립트는 저장소 밖 세션 임시 폴더에 둠
- 서버 응답: / 200, green_claim.js·green_claim.css·home.js·app_shell.js 200, 페이지 HTML에 green_claim-claims 1개, maxlength 0개
- 브라우저 확인(1440×900, 일부 390×844 모바일 에뮬레이션): 51/51 통과. 줄바꿈 형식(CRLF) 변환 후 같은 51개 재실행 통과
  - 초기: 글자 수 "0 / 20,000자 (공백·줄바꿈 포함)", 오류 없음, 작성 상태 없음, 검수 실행·PDF·파일 입력·파일 방식 비활성, 직접 입력 선택, 결과 빈 상태, 기존 "보유 증빙" 문구 없음, aria-describedby 연결
  - 공백·줄바꿈만 입력: 입력 중 오류 없음, 글자 수 6, 작성 상태 감지 → 입력칸을 떠나면 "입력해 주세요" 안내·aria-invalid=true·알림 영역 갱신
  - 한국어·영어·포르투갈어(ã·ç·ê 포함) 입력 보존, 글자 수 119로 기대값 일치, 오류 해제
  - 글자 계산: 👍🏽=2, 👨‍👩‍👧=5, e+U+0301=2, "a\r\nb\rc" 입력 시 5(브라우저가 textarea 값에서 이미 LF로 바꿈) / 정규화 계산식 직접 실행 [3,3,3,3]
  - 경계: 19,999·20,000자 오류 없음, 20,001자 초과 안내·"1자 초과" 표시, 20,001자 그대로 보존(잘림 없음), 초과 상태에서 계속 입력해도 알림 문장 반복 갱신 없음
  - 조합 입력(CDP Input.imeSetComposition): 20,000자에서 조합 중 20,001자가 되어도 오류 보류, 조합 확정 후 초과 안내
  - 수정: 1자 삭제 시 초과 해제, 전체 삭제 시 입력 필요 안내, 다시 입력 시 해제
  - 탭 이동(home 왕복): 문구·글자 수·오류 유지, /api 요청 0건, 미다운로드 결과 상태 꺼짐, 다른 4개 탭 작성 상태 false
  - 폼 requestSubmit: 페이지 이동 없음·입력 유지. localStorage·sessionStorage·IndexedDB 0건
  - 390px 모바일: 가로 스크롤 없음(scrollWidth 390 = innerWidth 390)
  - 입력칸 초점 테두리 solid 2px 유지
  - 새로고침: 헤드리스에서 beforeunload 대화상자 발생, 새로고침 후 입력 0자·오류 없음·작성 상태 없음
  - JS 예외·콘솔 오류 0건
- 기타: CSS 선택자 모두 .feature-green_claim 범위. 프로젝트 __pycache__는 13:58 생성분(이번 실행으로 생성 안 됨, .gitignore 대상)
- 판정: 이번 범위(문구 직접 입력 화면) 확인 통과. 기능 전체 완성 아님
- 미실행·미검증: 사람이 직접 조작하는 실제 브라우저, Edge·Firefox·Safari·실제 모바일 기기, 실제 한글 IME(CDP 시뮬레이션만), 화면낭독기 실제 낭독, Firefox의 autocomplete="off" 복원 방지 효과, 키보드 Tab 순서 전체, AI 검수·파일·PDF(미구현)

## 2026-10-25 문구 직접 입력 화면 사용자 수동 확인 (DEV-2026_10_25-04 후속)
- 구분: **사용자(담당자) 수동 확인 결과**를 전달받아 기록. Claude가 직접 수행한 위 헤드리스 Chrome 확인과 별개
- 환경: 사용자가 실제 브라우저에서 확인. 브라우저 종류·버전·OS·입력기 등은 전달받지 않아 미확인. 확인 시각 미확인(2026-10-25 17:32 기록 이전)
- 사용자 보고 결과
  | 절차 | 기대 | 사용자 보고 결과 | 판정 |
  |---|---|---|---|
  | "리젠 T2T를 소개합니다." 입력 | 14자 표시 | 14자 표시 | 통과(사용자 보고) |
  | 홈 탭 왕복 | 문구·글자 수 유지 | 유지 | 통과(사용자 보고) |
  | 내용을 모두 지움 | 빈 입력 오류 표시 | 표시 | 통과(사용자 보고) |
  | "테스트" 입력 | 오류 해제, 3자 표시 | 해제, 3자 | 통과(사용자 보고) |
- Claude 대조: 같은 문자열을 구현 계산식(CRLF·CR→LF 후 Array.from 길이)으로 Node에서 계산해 14, 3 확인. 사용자 화면을 Claude가 직접 본 것은 아님
- 이번 사용자 확인에 포함되지 않아 여전히 미검증: 공백만 입력 후 안내, 세 언어·이모지 입력, 19,999·20,000·20,001자 경계와 초과 문구 보존, 실제 한글 IME 조합 중 오류 보류, 비활성 버튼·파일 입력, 새로고침 경고·초기화, 다른 탭 영향, 모바일 배치, Edge·Firefox·Safari·실제 모바일 기기, 화면낭독기 낭독(헤드리스로 확인한 항목도 실제 브라우저에서는 이 4개 외 미확인)

## 2026-10-25 일반 PDF 텍스트 추출 확인 (DEV-2026_10_25-05)
- 환경: jasonenv Python 3.11.17, Flask 3.1.2, Werkzeug 3.1.9, pypdf 6.21.2. 사용자 서버(5003, PID 7744)는 유지하고 검증용 서버를 5013에 `-B`·재시작기 끔으로 실행, 확인 후 5013만 종료. 테스트 자료는 모두 가상 문구
- 패키지: pip check "No broken requirements found.", 설치 전후 freeze 차이는 pypdf==6.21.2 1줄
- 구분 A. 자동 테스트(features/green_claim/tests/test_pdf_extract.py, 17개 통과, CRLF 변환 후 재실행 통과)
  - 모의 입력: 페이지 구분 줄바꿈 포함 글자 수(9,999+2+9,999=20,000 통과, 20,001 TEXT_TOO_LONG), 코드 포인트 계산, 페이지 범위, 페이지 오류·전체 오류·텍스트 없음, 오류 코드 전달
  - 실제 pypdf(표준 라이브러리로 만든 가상 PDF): 페이지 순서·영어·포르투갈어, 손상·암호화, 20/21페이지, 페이지 추출 예외(모의 주입)
  - 실제 별도 프로세스: 성공·범위, 시간 초과(0.05초로 축소) 후 프로세스 종료·active_children 0·로그에 code만, 동시 2건 초과 BUSY, 20,000자 초과 시 자르지 않고 실패
  - 라우트(Flask 테스트 클라이언트): 성공 응답 필드, 비multipart·파일 없음·여러 파일·빈 파일, .docx·확장자 없음·가짜 PDF·손상·암호화·텍스트 없음·21/20페이지, 정확히 10,000,000바이트 성공(Werkzeug 기본 스풀링 함수 호출 시 실패하도록 막고 통과), 10,000,001바이트·요청 상한 초과 413, 오류 메시지에 경로·예외 원문 없음
  - 참고: 테스트 중 ResourceWarning(임시 파일 미닫힘)은 tracemalloc으로 확인한 결과 테스트 클라이언트의 요청 본문 생성(flask/testing.py builder.get_request) 쪽이며 서버 처리 아님
- 구분 B. 실제 파일 테스트(Chrome printToPDF로 만든 가상 PDF + service.extract_pdf 실제 프로세스)
  - 3개 언어 3페이지: 한국어·영어·포르투갈어 문장 모두 추출, 페이지 순서 유지, 174자, 페이지별 범위 안에 각 페이지 표지 문구 존재
  - 4페이지(텍스트/빈 도형/텍스트/캔버스 이미지 글자): 2·4페이지 no_text, 이미지 속 글자 미추출, 안내 3개
  - 텍스트 없음 → PDF_NO_TEXT, 21페이지 → PDF_TOO_MANY_PAGES, 23,598자 문서 → TEXT_TOO_LONG, 암호화 → PDF_ENCRYPTED, 절반 잘린 PDF → PDF_DAMAGED, 텍스트 파일 .pdf → PDF_INVALID, PDF 내용 .docx → FILE_TYPE_UNSUPPORTED, 10,000,001바이트 → FILE_TOO_LARGE, 20페이지·10,000,000바이트 성공. 추출 시간 0.14~0.25초(이 PC 1회 관측, 성능 보장 아님)
  - 멈춘 자식 프로세스(time.sleep 120)를 _stop(wait=False)로 종료: 작업 목록에서 사라짐
- 구분 C. 브라우저 확인(Chrome 헤드리스 CDP, 5013): PDF 흐름 64/64 통과, 기존 직접 입력 51/51 통과(파일 방식 기대값만 변경), CRLF 변환 후 두 묶음 재실행 통과
  - 방식 전환 시 두 문구 유지, multiple 없음, 파일 없이 추출 시 안내·요청 없음
  - 추출 후 3개 언어·순서·글자 수 일치, "AI 검수는 아직 실행되지 않음" 표시, 이미지 속 문구 누락 안내, 페이지별 범위, 검수·PDF 버튼 비활성·결과 빈 상태, 미다운로드 결과 상태 꺼짐
  - 추출 문구 수정 시 위치 부정확 안내, 새 파일 추출 시 교체 확인(유지/바꾸기 모두 동작, 확인 전 문구 불변)
  - 오류 6종(텍스트 없음·21페이지·20,000자 초과·암호화·손상·가짜 PDF): 안내 표시, 기존 문구·선택 파일 유지, 오류 문구는 텍스트로만 표시
  - .docx·10,000,001바이트는 브라우저에서 즉시 안내·서버 요청 없음, 10,000,000바이트·20페이지 성공
  - 지연(1.5초) 중 중복 클릭 추가 요청 없음, 처리 중 파일 교체 시 요청 취소(net::ERR_ABORTED)·취소 안내·이전 응답 미반영
  - 탭 왕복 후 파일·두 문구·방식 유지, 재방문 시 추출 재실행 없음, 직접 입력 빈 입력·해제·20,003자 보존, 추출 문구칸 빈 입력·20,001자 초과 안내
  - 브라우저 저장소 0건, 다른 탭 작업 상태 영향 없음, 390px 가로 스크롤 없음, 새로고침 시 beforeunload 대화상자·복원 없음, JS 예외·콘솔 오류 0건
  - 5013 서버 자식 프로세스 0개, 서버 로그는 접속 기록만(문서 내용 없음)
- 실패 후 수정: 첫 실행 2개 테스트 실패(413), 브라우저 1개 실패(취소 안내 덮임) → 원인 수정 후 통과(prompt_log 참고)
- 미실행·미검증
  - 공통 AI 회귀 테스트: jasonenv에 openai·pydantic·httpx2 미설치(설치 전부터)로 import 실패, 실행 불가
  - 실제 30초 초과 PDF, 대용량·복잡한 실제 홍보물, 표·다단 문서 읽기 순서, 메모리 사용량
  - 사람이 직접 조작하는 실제 브라우저, Edge·Firefox·Safari·모바일 기기, 화면낭독기, 실제 한글 IME
  - 스캔 PDF OCR·Word·이미지(미구현), AI 검수(미구현)

## 2026-10-25 PDF 원문·추출본 비교 결과와 코드 처리 확인 (DEV-2026_10_25-05 후속)
- 구분 1. 사용자(담당자) 제공 비교 결과(전달받은 내용, Claude는 해당 PDF·추출본을 보지 않음)
  - 문자열 내부에 공백이 추가된 곳 있음
  - fi/fl 합자 문자 차이 있음
  - 일부 단계 번호의 읽기 순서가 원문과 다름
  - 주요 문장·항목 누락은 확인되지 않았다고 보고(사용자 확인 범위 기준)
  - 사용한 PDF 종류·생성 도구·브라우저·확인 시각은 전달받지 않아 미확인
- 구분 2. Claude가 직접 확인한 코드 처리(읽기 전용, 코드 변경 없음)
  - 우리 코드가 추출 문구를 바꾸는 처리는 pdf_worker._normalize의 CRLF·CR→LF 한 가지뿐. 공백 추가·삭제, 유니코드 정규화(NFC/NFKC), 합자 변환, 순서 재배치 없음
  - service.build_result: strip()은 빈 페이지 판단에만 쓰고 문구 값은 바꾸지 않음. 페이지 사이에 빈 줄("\n\n")만 추가
  - green_claim.js: 받은 text를 textarea.value에 그대로 넣음. normalize·trim은 글자 수·빈 입력·같은 문구 판단에만 사용
  - pypdf 6.21.2 기본 호출(extract_text(), plain 모드, space_width 200) 사용
- 구분 3. pypdf 6.21.2 설치본 소스로 확인한 원인 후보(해당 PDF로 재현하지 않아 확정 아님)
  - 공백: _page.py의 TJ 처리에서 글자 간격 값이 공백 폭의 95% 이상이면 " "를 삽입함 → 자간·커닝이 큰 글자에서 단어 안 공백이 생길 수 있음
  - 합자: _codecs/adobe_glyphs.py에서 글리프 이름 /fi·/fl이 U+FB01·U+FB02(합자 한 글자)로 매핑됨. PDF의 ToUnicode 정보에 따라 합자 문자가 그대로 나오거나 다르게 나올 수 있음. 우리 코드는 이를 변환하지 않음
  - 순서: extract_text 문서 설명상 텍스트 그리기 명령의 콘텐츠 스트림 순서대로 추출하며 "순서에 의존하지 말 것"이라고 명시. 번호를 본문과 따로 그린 문서는 화면 순서와 다르게 나올 수 있음
- 구분 4. PDF 원문 자료 없이는 판단할 수 없는 부분
  - 각 공백이 pypdf 자간 판정에서 왔는지, PDF 안에 실제 공백 문자가 있는지
  - 합자가 PDF의 ToUnicode·글리프 이름에서 어떻게 정의됐는지, 추출본이 U+FB01/FB02인지 분리된 f+i/f+l인지
  - 번호의 콘텐츠 스트림 순서, layout 모드 등 다른 추출 설정에서 달라지는지
  - 사용자가 보고한 "누락 없음"이 문서 전체에 해당하는지
- 판정: 사용자 비교 결과는 "주요 누락 미발견, 공백·합자·순서 차이 있음"으로 기록. 원문과 완전히 일치한다고 기록하지 않음. 원인은 후보 단계이며 해당 PDF로 재현·확인하지 않음
- 미실행: 해당 PDF 재현, layout 모드 비교, 다른 PDF 생성 도구별 비교, 자동 보정 시험(지시에 따라 하지 않음)

## 2026-10-25 Word(.docx) 텍스트 추출 확인 (DEV-2026_10_25-06)
- 환경: jasonenv C:/Users/user/miniforge3/envs/jasonenv/python.exe, Python 3.11.17, Flask 3.1.2, Werkzeug 3.1.9, pypdf 6.21.2, python-docx 1.2.0, lxml 6.1.3. 사용자 서버(5003, PID 7744) 유지, 검증용 5013만 실행·종료. 자료는 모두 가상 문구
- 패키지: 설치 전후 freeze 차이 = lxml==6.1.3, python-docx==1.2.0, typing_extensions==4.16.0 추가(기존 변경 없음). pip check "No broken requirements found."
- requirements.txt: 기존 부분이 설치 전 사본과 바이트 동일, 끝에 3줄 추가만
- 구분 A. 자동 테스트(features/green_claim/tests, 35개 통과 = PDF 17 + Word 18, CRLF 변환 후 재실행 통과)
  - 실제 python-docx 문서: 문단→표→문단 순서·3개 언어·블록/행/셀 범위, 가로·세로 병합 셀 1회만, 중첩 표, 하이퍼링크 보이는 글자, 미지원 요소 감지(머리글·이미지·텍스트 상자·변경 추적·각주 참조·콘텐츠 컨트롤·메모)와 해당 글자 미포함, 이미지만/빈 문서 DOCX_NO_TEXT, 손상·비Word ZIP·xlsx형·docm형·XML 손상, 외부 엔티티 미확장, ZIP 항목 1,000 통과/1,001 초과, 압축 해제 50,000,000 통과/50,000,001 초과, 헤더 크기 위장 ZIP 손상 처리, 9,999+2+9,999=20,000 통과/추가 시 TEXT_TOO_LONG
  - 모의: 실제 읽기 바이트 계산(선언 0바이트·실제 2,000바이트 → 초과), OLE+EncryptedPackage → DOCX_ENCRYPTED, OLE만 → DOCX_UNSUPPORTED_FORMAT, worker 예외 → EXTRACT_FAILED
  - 실제 별도 프로세스: Word 성공(PDF 페이지 필드 없음), 시간 초과(0.05초) 후 자식 0개·로그에 문구 없음
  - 라우트: Word 성공 응답 필드, 빈 파일·.doc·비Word, 정확히 10,000,000바이트 성공·10,000,001바이트 413
- 구분 B. 실제 파일 테스트(python-docx로 만든 가상 .docx 12개 + service.extract_file 실제 프로세스): 기대 코드·결과 모두 일치(문서 순서·병합 반복 없음·중첩·링크, 감지 3종, NO_TEXT, 25,558자 → TEXT_TOO_LONG, docm형·다른 ZIP·손상·항목 1,001·해제 초과·.doc·10,000,001 거부, 10,000,000 성공), 자식 0개
- 구분 C. 브라우저 확인(Chrome 헤드리스 CDP, 5013): Word 흐름 45/45, PDF 흐름 66/66(.docx 관련 기대값만 변경), 직접 입력 51/51. CRLF 변환 후 세 묶음 재실행 통과
  - Word: accept .pdf·.docx·multiple 없음, 지원/준비 중 구분 안내, 순서·언어·병합·중첩·링크, 블록 기준 요약·"블록별 추출 범위"·페이지 표기 없음, 감지 요소 목록과 일반 안내 구분(감지 없으면 목록 숨김), 중첩 표 안내, 편집 후 위치 안내, 교체 확인, 오류 7종 안내와 문구·파일 유지, .doc·10,000,001 즉시 차단(요청 없음), 10,000,000 성공, 처리 중 방식 전환 시 취소·응답 미반영·요청 취소, PDF 페이지 요약 유지, 탭 왕복 유지·재추출 없음, 저장소 0건, 다른 탭 영향 없음, 390px 가로 스크롤 없음, 새로고침 경고·복원 없음, 콘솔 오류 0
  - 서버: 자식 프로세스 0개, 로그는 시작 안내와 접속 기록만
- 구분 D. 공통 확인
  - tests/test_common(README 명령): test_ai_client·test_pdf 모두 "No module named httpx2"로 import 실패, 실행 불가. jasonenv에 openai·pydantic·httpx2 없음(이전 작업 때부터)
  - 대신 임시 확인: common.pdf_utils.inspect_pdf를 가상 PDF 6개로 직접 호출 → 3쪽·20쪽 통과, 21쪽 PDF_TOO_MANY_PAGES, 암호화 PDF_ENCRYPTED, 손상 PDF_CORRUPT, 가짜 PDF_NOT_PDF(정식 공통 테스트 대체 아님)
- 미실행·미검증: 실제 Office 암호화 .docx, 실제 30초 초과 문서, 대용량·복잡한 실제 홍보물 Word, 메모리 사용량, 사람이 조작하는 실제 브라우저·Edge·Firefox·Safari·모바일 기기·화면낭독기, 공통 회귀 테스트(패키지 없음), 이미지·스캔 PDF(미구현)

## 2026-10-25 Word 추출 사용자 수동 확인 (DEV-2026_10_25-06 후속)
- 구분: **사용자(담당자) 수동 확인 결과**를 전달받아 기록. 위 Claude 직접 실행 확인(자동 테스트·실제 파일·헤드리스 브라우저)과 별개
- 자료: 사용자가 사용한 가상 .docx 1개(Claude가 만든 임시 자료와 같은 파일인지는 미확인). 문서 전체 본문은 기록하지 않음
- 환경: 브라우저 종류·버전·확인 시각은 전달받지 않아 미확인(2026-10-25 20:23 기록 이전)
- 사용자 보고 결과
  | 확인 항목 | 기대 | 사용자 보고 | 판정 |
  |---|---|---|---|
  | 한국어·영어·포르투갈어 문구 | 보존 | 보존됨 | 통과(사용자 보고) |
  | 블록 순서 | 시작 문단 → 표 → 종료 문단 | 유지됨 | 통과(사용자 보고) |
  | 표 구조 | 행·셀 구분, 병합 셀 문구 1회 | 확인됨 | 통과(사용자 보고) |
  | 하이퍼링크 | 표시 글자 추출 | "테스트 링크" 추출됨 | 통과(사용자 보고) |
  | 머리글 | 추출 본문에서 제외 | 제외됨 | 통과(사용자 보고) |
  | 감지 안내 | "머리글·바닥글" 미지원 요소 표시 | 표시됨 | 통과(사용자 보고) |
  | 편집 유지 | "수정테스트" 추가 후 홈 탭 왕복 시 유지 | 유지됨 | 통과(사용자 보고) |
  | 위치 안내 | 수정 후 원문 위치 부정확 가능 안내 | 표시됨 | 통과(사용자 보고) |
- Claude가 사용자 화면이나 문서를 직접 본 것은 아님
- 이번 사용자 확인에 포함되지 않아 그대로 미검증: 실제 Office 암호화 .docx, 실제 30초 초과 문서, 대용량·복잡한 실제 홍보물 Word, 메모리 사용량, 텍스트 상자·이미지 등 머리글 외 미지원 요소의 실제 문서 확인, 중첩 표의 사용자 확인, 오류 파일(손상·docm형·ZIP 상한 등)의 실제 브라우저 확인, 처리 중 파일 교체·방식 전환 취소의 실제 브라우저 확인, 새로고침 경고·초기화의 실제 브라우저 확인, Edge·Firefox·Safari·모바일 기기·화면낭독기, 공통 회귀 테스트(jasonenv에 httpx2·openai·pydantic 없음), 이미지·스캔 PDF(미구현)

## 2026-10-25 PDF AI 글자 판독 확인 (DEV-2026_10_25-07)
- 환경: jasonenv Python 3.11.17, Flask 3.1.2, pypdf 6.21.2, python-docx 1.2.0. **openai·pydantic·httpx2 없음** → common.ai_client import 불가. 실행 셸에 OPENAI_API_KEY·OPENAI_MODEL 없음, .env 없음. 사용자 서버(5003, PID 7744) 유지, 검증용 5013(실제 코드)·5014(모의) 실행 후 종료. 실제 OpenAI 호출 0회
- 구분 A. 실제 실행(외부 호출 없음)
  - 앱 시작 시 openai·common.ai_client를 불러오지 않음, /api/green-claim/ocr 등록 확인
  - 실제 코드 서버(5013)에서 AI 판독 클릭 → AI_DEPENDENCY_MISSING(503) 안내, 기존 편집 문구 유지(헤드리스 브라우저)
  - 사전 검사(공통 inspect_pdf 포함) 실패 7종: FILE_EMPTY·FILE_TOO_LARGE·FILE_TYPE_UNSUPPORTED·PDF_INVALID·PDF_ENCRYPTED·PDF_TOO_MANY_PAGES·PDF_CORRUPT, AI 연결을 불러오지도 않음
  - 서버 로그: 접속 기록과 오류 code 줄만, 문서·판독 텍스트 흔적 0건. 서버 자식 프로세스 0개
- 구분 B. 모의 검증(가짜 generate 함수, 실제 판독 아님)
  - 자동 테스트 tests/test_ocr.py 13개 통과, 1개 건너뜀(pydantic 없음: 스키마 필드 확인)
    - 공통 함수 1회 호출, 인자 instructions(프롬프트 파일)·pdf_bytes·schema·input_text(서버 페이지 수, 파일명 미포함)
    - 페이지 번호 범위 밖(0·N+1)·중복·누락·정수 아님·bool → OCR_PAGE_MISMATCH, 정렬·범위·[판독 불가] 수·불확실 수
    - 글자 없음 OCR_NO_TEXT, 9,999+2+9,999=20,000 통과/20,001 TEXT_TOO_LONG(자르지 않음)
    - 의존성 없음 AI_DEPENDENCY_MISSING, 동시 실행 EXTRACT_BUSY(호출 없음), 오류 시 재시도 없음(호출 1회)
    - 라우트: 성공 응답 필드, 공통 오류 8종(설정·인증·요청 제한·연결·시간 초과·거절·미완료·형식) code·HTTP 상태, 예상 밖 예외 AI_UNKNOWN_ERROR(내부 문자열 미노출)
    - 페이지 로딩·일반 추출·텍스트 없음 실패에서 AI 연결 미호출, 거부 로그에 문서 내용 없음, 프롬프트 필수 규칙 포함
  - 브라우저(Chrome 헤드리스, 모의 서버 5014 + 실제 5013) 33/33 통과
    - 버튼 옆 OpenAI 전송·요금·PDF만 안내, 로딩·파일 선택·탭 전환·일반 추출 실패 시 AI 요청 0건
    - 일반 추출 출처·AI 선택 안내, 처리 중 두 버튼 비활성·요금 취소 미보장 안내, 중복 클릭 추가 요청 없음
    - 교체 확인 후 반영, 글자 수 재계산, 출처(AI 판독·모델명)·검수 아님·모델 보고 불확실/한계(측정 정확도 아님)·페이지별 판독 범위 표시, 검수·PDF 다운로드 비활성, 편집 후 위치 안내
    - 모의 출력 잘림(AI_INCOMPLETE)·페이지 누락(OCR_PAGE_MISMATCH) 안내와 기존 문구·파일 유지, Word 선택 시 AI 판독 거부·요청 없음
    - 처리 중 파일 교체·방식 전환 → 취소·이전 응답 미반영, 탭 왕복 재실행 없음, 저장소 0건, 390px 가로 스크롤 없음, 새로고침 경고·복원 없음, 콘솔 오류 0
- 구분 C. 회귀(실제 코드 서버 5013): Word 45/45, PDF 66/66, 직접 입력 51/51. 첫 실행에서 3건 실패 → 원인은 검증 스크립트(PDF 다운로드 버튼을 "PDF" 글자로 찾아 새 AI 판독 버튼을 잡음, Word 안내 기대값이 바뀐 문구와 다름). 실제 PDF 다운로드 버튼 disabled 확인 후 스크립트만 수정해 통과. 담당 자동 테스트 PDF 17·Word 18 통과. CRLF 변환·프롬프트 LF 정규화 후 전체 재실행 통과
- 구분 D. 공통 테스트: tests/test_common 두 모듈 모두 "No module named httpx2"로 import 실패, 실행 불가
- 미실행·미검증: 실제 OpenAI 호출, 실제 스캔 PDF 판독 정확도·비용·소요 시간, 4,096토큰 출력으로 처리 가능한 분량, 공급자의 스캔 PDF 처리 가능 여부, pydantic 스키마의 실제 strict JSON Schema 변환, 사람이 조작하는 실제 브라우저·다른 브라우저·화면낭독기

## 2026-10-25 후속: 패키지 설치 후 재검증 (DEV-2026_10_25-07 후속)
- 사용자 보고(Claude가 직접 실행하지 않음): jasonenv에 기존 requirements.txt 패키지 설치 완료, 사용자가 실행한 pip check 결과 "No broken requirements found."
- Claude 직접 확인(2026-10-25 20:50~21:00 무렵, C:/Users/user/miniforge3/envs/jasonenv/python.exe 명시, Python 3.11.17)
  - import·설치 버전: openai 3.37.0, pydantic 2.14.1, httpx2 2.16.0(requirements.txt 고정 버전과 같음), common.ai_client import 가능. httpx·python-dotenv는 없음(requirements.txt에 없는 패키지). 추가 설치·업데이트 없음
  - 실행 전 외부 호출 여부 확인: tests/test_common은 클라이언트 생성 함수를 기본 차단하고 필요한 테스트만 httpx2 MockTransport로 교체, OPENAI_ 환경변수를 가짜 값으로 대체. test_ocr은 _load_ai를 가짜 함수로 교체. .env 파일 없음, 실행 셸에 OPENAI_ 환경변수 없음(값 미조회)
  - 공통 회귀 tests/test_common(test_ai_client·test_pdf): 56개 실행, 56개 통과, 실패 0, 건너뜀 0. 앞선 "No module named httpx2" 실행 불가 기록(구분 D)의 후속 해결
  - features/green_claim/tests/test_ocr.py: 14개 실행, 14개 통과, 건너뜀 0(앞서 pydantic 없음으로 건너뛴 스키마 필드 테스트 포함)
  - 담당 회귀: test_pdf_extract 17개 통과, test_docx_extract 18개 통과
  - 추가 확인(저장소 밖 임시 스크립트 scratchpad/tools/check_ocr_no_key.py, 외부 호출 없음)
    - OcrResult가 openai 라이브러리의 strict JSON Schema 변환을 통과(required: pages·limitations / page·text·uncertain, additionalProperties false). 앞의 미검증 항목 "strict JSON Schema 변환"은 로컬 변환까지만 확인, 공급자 수락 여부는 미검증
    - 키·모델 없는 상태에서 Flask 테스트 클라이언트로 /api/green-claim/ocr에 가상 1쪽 PDF 전송 → HTTP 503, AI_CONFIG_MISSING("AI 기능 설정이 준비되지 않았습니다…"), 클라이언트 생성 0회(호출 시 실패하도록 막아 둠). 패키지 설치 후에는 AI_DEPENDENCY_MISSING 대신 이 안내가 나옴
- 기능 코드·공통 파일·테스트 코드 수정 없음. 브라우저 회귀는 이번에 다시 실행하지 않음(코드 변경 없음)
- 여전히 미검증: 실제 OpenAI 호출, 실제 스캔 PDF 판독 정확도·비용·소요 시간, 4,096토큰 출력으로 처리 가능한 분량, 공급자의 스캔 PDF 처리 가능 여부와 스키마 수락. 모의 테스트 통과는 실제 판독 성공이 아님
