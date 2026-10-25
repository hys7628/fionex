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
