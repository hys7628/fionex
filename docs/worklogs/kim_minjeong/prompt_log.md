# 프롬프트 로그

현재 기록 없음. 아래 항목을 실제 작업 후 추가하세요.

유형 / 실험 ID / 날짜 / 기능 / 모델·설정 / 프롬프트 경로·버전 / 입력·근거 / 실제 출력 / 문제 / 변경 이유 / 제어 / 재검증 / 한계

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

## DEV-2026_10_25-01 그린 클레임 문구 검수 명세 구체화
- 유형: development_instruction (서비스 프롬프트 실험 아님)
- 날짜/시간: 2026-10-25 16:06~ (Asia/Seoul)
- 작업자: 김민정 / 기능: green_claim / 브랜치: feature/green_claim (HEAD 05ac128 = origin/develop, 마지막 fetch 2026-10-25 15:43 기준)
- 도구·모델/설정: Claude Code(VS Code 확장). 세션 시스템 정보상 모델 ID claude-opus-5-5. 그 밖의 설정 미확인. 서비스 OpenAI 호출 없음
- 프롬프트 경로·버전: 해당 없음(서비스 프롬프트 미작성)
- 지시 요약: 담당자 합의 내용으로 features/green_claim/feature_spec.md를 구체화. 기능 코드·공통 파일 수정 금지, 명세와 개인 기록만 수정. 지시 원문은 담당자 대화에 있으며 여기에는 요약만 기록
  - 사용자·문제, 1단계 포함/제외 범위, 인증 갭 분석은 후속 단계로 유지
  - 입력(3개 언어, PDF·스캔 PDF·docx·JPG/PNG, 1개·10MB, 20,000자, 자르지 않음), 사용 순서, 결과 화면, 조치 3종, PDF
  - CDC·CONAR 기준 자료와 갱신 원칙, 코드/OpenAI 역할, AI 제어, 수정·실패·재시도, 공통 동작
  - 기술 후보·협의 사항, 완료 기준·검증 계획
- 변경 차이: feature_spec.md 245줄 추가·11줄 삭제(git diff --stat). 최상위 5개 절(목적/범위, 입력·출력·데이터, 공통 조건, 구현 전 작성, 검증) 유지
  - "입력·출력·데이터: 채울 항목" 제목을 "입력·출력·데이터"로 변경
  - 기존 인증 갭 분석 원칙 문장은 "단계 > 후속 단계"로 옮김
  - 표기 [확정]/[후보]/[협의]/[구현 전 결정]/[미검증] 추가
- 작성 이유: 구현 전에 범위·입력·출력·실패 처리·검증 계획을 확정 요구사항과 기술 후보/협의/미검증으로 구분해 두기 위함
- 교차검증: common/ai_client.py, config.py, errors.py, requirements.txt, .env.example(비밀값 미출력), README.md, docs/decisions.md, docs/data_contracts.md와 대조. 결과는 validation.md 참고
- 결과: 명세 문서만 갱신. 기능 코드·엔드포인트·서비스 프롬프트 미구현
- 한계·미정:
  - 10MB 바이트 기준, 20,000자 계산 방식, 언어 감지, 입력 전환 동작, 페이지·해상도 제한, Word 추출 범위
  - 결과 스키마, 엔드포인트 상세, 기준 자료 파일 구조·변경 감지·동시 갱신 방지
  - 추출 등 60초 외 시간 제한, 출력 토큰 상한 충분 여부, 모델 최종 선정, 패키지 버전
  - 스캔 PDF·이미지 판독 공통 확장(유정현 협의), 인증 갭 분석 일정(팀 조율)
  - CDC·CONAR URL은 전달받은 출처이며 이번에 조회하지 않음

## DEV-2026_10_25-02 브라질 그린 클레임 기준 자료(CDC·CONAR) 확보·정리
- 유형: development_instruction (서비스 프롬프트 실험 아님)
- 날짜/시간: 2026-10-25 16:31~16:40 (Asia/Seoul)
- 작업자: 김민정 / 기능: green_claim / 브랜치: feature/green_claim (HEAD 8aab175 = origin/feature/green_claim, 작업 전 변경 없음. 원격 최신성은 마지막 fetch 2026-10-25 15:43 이후 미확인)
- 도구·모델/설정: Claude Code(VS Code 확장). 세션 시스템 정보상 모델 ID claude-opus-5-5. 그 밖의 설정 미확인. 서비스 OpenAI·유료 번역 API 호출 없음
- 지시 요약(팀 합의에 따라 요약본 기록)
  - CDC·CONAR 공식 출처를 실제로 열어 관련 조항, 원문, 개정일·버전을 확인
  - features/green_claim/data/에 원문 또는 정확한 발췌, 출처 목록, 한국어 검토 기준 정리 저장
  - 사용권은 확인 가능한 범위만 기록하고, 저장 범위를 정할 수 없는 제한이 있으면 저장 보류 후 보고
  - 기능 코드·자동 갱신·공통 파일 수정·패키지 설치·Git 변경 금지
- 작업 이유: 문구 검수의 근거 조항을 공식 원문 기준으로 준비하고, 버전·사용권 한계를 구현 전에 파악하기 위함
- 실제 결과
  - CDC(Planalto) 통합본 조회 성공. Art. 2·3, 6(III·IV), 29, 30, 31, 36, 37, 38, 60, 66·67·69, 118 원문 발췌 저장
  - CONAR 코드 웹 게시본과 PDF("Edição 2025") 조회 성공. Seção 10(Artigo 36·36-A·36-B), Anexo "U", Artigo 8·17·18·27 원문 확인
  - CONAR 이용약관(2026년 5월)이 상업·광고 목적 이용, 체계적 복제, AI 시스템 입력용 이용·자동 수집을 사전 허가 없이 금지함을 확인 → CONAR 원문 발췌·번역 저장 보류, 조항 번호·제목만 기록
  - 웹 게시본과 PDF의 Seção 10·Anexo U는 단어 단위 비교에서 실질 차이 없음(서식·추출 차이만)
  - 저장: features/green_claim/data/brazil_claim_criteria/ 3개 파일, data/README.md 갱신
- 실패·미확인
  - 접속 실패 없음
  - Anexo U 개정의 정확한 승인일(2025년 11월까지만 확인)·시행일 미확인
  - MP nº 1.393/2026 효력 상태 미확인(광고 조항과 무관)
  - 영문 PDF 미조회, Planalto 이용약관 미확인
  - CDC·CONAR의 B2B 적용 범위: 법률 해석 미확인
- 남은 한계·팀 결정 필요
  - CONAR 내용을 서비스에서 OpenAI에 제공하고 자동 조회하는 feature_spec.md 구조가 CONAR 이용약관과 충돌할 수 있음. 허가 요청·사용 방식 변경·프로젝트 성격 확인 등 팀 결정 필요(명세는 변경하지 않음)
  - 이번 확인 과정에서 CONAR 페이지·PDF·약관을 프로그램으로 1회씩 내려받았고 개발 도구 AI가 내용을 읽었음. 사본은 저장소 밖 세션 임시 폴더에만 있음
  - 한국어 번역은 개발 도구로 작성한 비공식 번역이며 사람·법률 검토 전

## DEV-2026_10_25-03 CONAR 표현 검수 기준 자료 보완
- 유형: development_instruction (서비스 프롬프트 실험 아님)
- 날짜/시간: 2026-10-25 16:58~17:06 (Asia/Seoul)
- 작업자: 김민정 / 기능: green_claim / 브랜치: feature/green_claim (HEAD f7ab5f3 = origin/feature/green_claim, 작업 전 변경 없음. 원격 최신성은 마지막 fetch 2026-10-25 15:43 이후 미확인)
- 도구·모델/설정: Claude Code(VS Code 확장). 세션 시스템 정보상 모델 ID claude-opus-5-5. 그 밖의 설정 미확인. 서비스 OpenAI·유료 API 호출 없음
- 지시 요약(팀 합의에 따라 요약본 기록)
  - 담당자 결정: CDC와 CONAR·부속서 U를 모두 AI 검수 기준에 포함하는 요구사항 유지. 이 결정은 CONAR 이용 허가가 아니며, 허가 미확인 상태를 그대로 기록
  - CONAR 환경 관련 조항·부속서 U의 원문 발췌(conar_excerpt.md), 비공식 번역·검토 지침(review_criteria_ko.md), 출처·이용 조건(source_register.md) 보완
  - 직전 저장 보류 기록은 삭제하지 않고 후속 경위 추가. CDC 자료·feature_spec.md·공통 파일 수정 금지
- 변경 이유: 담당자가 CONAR를 검수 기준에 포함하기로 해, 구현 전에 정확한 조항 원문과 한국어 검토 기준을 준비하기 위함
- 실제 결과
  - 직전 확보본(웹 16:31:51, PDF 16:33:58, 약관 16:34:00)을 사용. 다시 접속하지 않음
  - conar_excerpt.md 추가: 기준 ID 15개, 원문 103줄. Artigo 8º·17·18·27(caput, §1º, §2º, §7º, §8º)·36·36-A·36-B, Anexo "U" 서문 일부·I·II.1~II.9·각주 1~4
  - review_criteria_ko.md에 "CONAR 후속 경위", "CONAR 상세 기준"(15개 항목: 조항, 원문 발췌, 비공식 번역, 원문 요구, 검토 지침, 적용 범위와 해석 한계, 제품 증빙) 추가. 기존 보류 표는 유지
  - source_register.md에 후속 경위, 상태 구분, 이용 조건과 남은 위험, 웹·PDF 대조 추가 결과 추가
  - data/README.md에 conar_excerpt.md 안내와 후속 한 줄 추가(기존 줄 유지)
  - 번역 자체 점검에서 2곳 수정: "pontuais"(일시적→단발적), 9.2.3 c의 역물류·공급자 회수 조건 누락 보완
- 한계·미정
  - CONAR AI 이용 허가 미확인. 발췌를 서비스 OpenAI 입력에 쓰는 것과 공식 출처 자동 조회는 허가 확인 전까지 해결되지 않은 위험
  - 원격 저장소 공개 여부 미확인(공개라면 재배포 범위 추가 검토 필요)
  - 번역은 개발 도구가 작성한 비공식 번역, 사람·법률 전문가 검토 전
  - Anexo U 정확한 승인일·시행일, 내용위원회 결의·기술 노트, Artigo 1º·32 미발췌, 각주 법령 원문 미조회
  - B2B 적용 범위, 36-B와 부속서 U 문구 차이의 우선순위 해석 미확인

## DEV-2026_10_25-03 후속: "pontuais" 번역 보완 (같은 작업 범위, 커밋 전)
- 유형: development_instruction
- 날짜/시간: 2026-10-25 17:10 무렵 (Asia/Seoul)
- 도구·모델/설정: Claude Code, 모델 ID claude-opus-5-5(세션 시스템 정보), 그 밖의 설정 미확인. 외부 API 호출 없음
- 지시 요약: review_criteria_ko.md의 CONAR-36B·CONAR-U-2에서 "단발적(pontuais)"을 원문 전체 문맥과 대조해, 시간적 일회성으로 오해되지 않도록 문맥에 맞게 수정. 원문 발췌·명세·공통 파일 수정 금지
- 변경 이유: 원문 "ações ou atributos socioambientais pontuais, específicos ou relacionados a determinadas partes do produto ou etapas isoladas do ciclo de vida"에서 pontuais는 específicos, 제품 일부, 수명주기의 개별 단계와 나란히 놓여 이익이 특정 범위에 국한됨을 뜻한다. 직전 수정("일시적"→"단발적")도 시간적 일회성으로 읽힐 수 있었다
- 변경 차이(review_criteria_ko.md, 두 곳)
  - CONAR-36B b: "단발적(pontuais)·특정한 활동이나 속성, 제품의 일부 또는 수명주기의 일부 단계에만 관련된 주장은" → "특정 범위에 한정된(pontuais)·특정한(específicos) 활동이나 속성, 또는 제품의 일부나 수명주기의 개별 단계(etapas isoladas)에 관련된 주장은"
  - CONAR-U-2: "단발적(pontuais)·특정한 활동이나 속성, 제품 일부 또는 수명주기의 일부 단계에 관련된 주장은" → 위와 같은 문구
  - 36-B b에서 원문에 없는 "~에만"을 함께 삭제(원문 "relacionados a"에 "오직"의 뜻 없음)
- 결과: 번역 2곳 수정. conar_excerpt.md(포르투갈어 원문) 변경 없음
- 한계: 비공식 번역이며 사람·전문가 검토 전. 위 이전 기록의 "일시적→단발적" 수정 내역은 당시 기록으로 유지

## DEV-2026_10_25-04 그린 클레임 문구 직접 입력 화면 구현
- 유형: development_instruction (서비스 프롬프트 실험 아님, 기능 전체 완성 아님)
- 날짜/시간: 2026-10-25 17:10~17:22 (Asia/Seoul)
- 작업자: 김민정 / 기능: green_claim / 브랜치: feature/green_claim (HEAD d8881b2 = origin/feature/green_claim, 작업 전 변경 없음. 원격 최신성은 마지막 fetch 2026-10-25 15:43 이후 미확인)
- 도구·모델/설정: Claude Code(VS Code 확장), 모델 ID claude-opus-5-5(세션 시스템 정보), 그 밖의 설정 미확인. OpenAI·외부 유료 API 호출 없음
- 지시 요약(팀 합의에 따라 요약본 기록)
  - 문구 직접 입력 화면만 구현: textarea, 20,000자 글자 수, 빈 입력·초과 안내. AI 검수·파일 추출·PDF 미구현
  - 글자 수: CRLF·CR→LF 정규화 후 Unicode 코드 포인트(Array.from) 기준, 공백·줄바꿈 포함
  - maxlength·자동 자르기 금지, 조합 입력 중 오류 반복 금지, aria-invalid·안내 연결, 글자 수 과다 낭독 방지
  - 검수 실행·PDF·파일 업로드는 비활성과 준비 중 안내 유지, 결과는 빈 상태
  - 공통 AppShell 입력 감지·탭 유지 사용, 저장소·서버 저장 금지, 공통 파일 수정 금지
- 변경 이유: 명세의 1단계 입력 조건 중 화면에서 확인 가능한 부분을 먼저 구현하기 위함
- 변경 파일과 내용
  - templates/green_claim/panel.html: 입력 방식(문구 직접 입력 선택, 홍보물 파일 업로드 준비 중·비활성), 문구 textarea(maxlength 없음, autocomplete="off"), 안내·글자 수·오류·화면낭독기 알림 영역, 홍보물 파일 입력 비활성, 검수 실행·PDF 비활성과 준비 중 안내, 결과 빈 상태. 기존 "보유 증빙을 넣습니다" 예시 문구 제거
  - static/green_claim.js: 글자 수 계산·표시, 입력 상태(empty/over) 판단, 오류 표시·해제, 조합 입력(compositionstart/end) 중 오류 보류
  - static/green_claim.css: .feature-green_claim 범위 스타일(입력칸 높이, 초과 글자 수 색, 비활성 표시, 결과 머리글 안내 배치)
  - feature_spec.md: 글자 계산 방식 결정과 구현 상태 6줄 추가(기존 줄 유지)
- 설계 선택(개발 판단)
  - 첫 화면에서는 오류를 띄우지 않음. 공백만 입력 중에는 오류를 보류하고 입력칸을 떠나거나 내용을 모두 지웠을 때 "입력 필요" 안내
  - 초과는 즉시 안내(조합 중이면 조합 확정 후). 오류 문장에 변하는 숫자를 넣지 않아 알림이 상태 변화 때만 갱신됨
  - 글자 수는 aria-live가 아닌 aria-describedby로 연결(입력칸 초점 시 읽힘)
  - Firefox 등의 새로고침 시 폼 값 복원을 막으려고 autocomplete="off" 지정(Firefox 실제 동작은 미확인)
- 결과: 헤드리스 Chrome 51개 확인 항목 통과(validation.md). 작업 상태는 공통 자동 감지만 사용, setResult 호출 없음
- 한계·남은 사항
  - 글자 수는 코드 포인트 기준이라 화면에 보이는 글자 묶음과 다름(예: 👍🏽=2, 👨‍👩‍👧=5, e+결합 악센트=2). 사용자 화면에는 "공백·줄바꿈 포함"만 안내
  - JS trim 기준 공백 판정이라 폭 없는 공백(U+200B) 등은 글자로 취급됨
  - 서버 측 입력 검사는 미구현(현재 서버로 보내는 요청 없음)
  - 화면 머리글 설명(routes.py FEATURE description)에 "인증 요건 대비 보유 증빙의 차이"가 남아 1단계 범위와 어긋남. routes.py는 이번 수정 허용 범위 밖이라 보류, 담당자 확인 필요
  - 실제 브라우저(사람 조작)·Firefox·Safari·Edge·실제 IME·화면낭독기 미확인

## DEV-2026_10_25-04 후속: 사용자 수동 확인 결과 기록
- 유형: development_instruction (기록 추가만, 코드 변경 없음)
- 날짜/시간: 2026-10-25 17:32 (Asia/Seoul)
- 도구·모델/설정: Claude Code, 모델 ID claude-opus-5-5(세션 시스템 정보), 그 밖의 설정 미확인
- 지시 요약: 사용자가 실제 브라우저에서 확인한 4개 결과를 validation.md·prompt_log.md에 사용자 수동 확인으로 추가. Claude 직접 테스트와 구분하고, 확인하지 않은 항목을 검증 완료로 바꾸지 않음. 코드·공통 파일·Git 변경 금지
- 결과: validation.md에 사용자 보고 4건(14자 표시, 홈 탭 왕복 유지, 전체 삭제 시 빈 입력 오류, "테스트" 입력 시 해제·3자)을 "사용자 보고"로 기록. 보고된 글자 수는 구현 계산식과 일치함을 Node로 재계산해 확인
- 한계: 브라우저 종류·버전·확인 시각 미전달로 미확인. 나머지 실제 브라우저 항목은 미검증 유지

## DEV-2026_10_25-05 일반 PDF 홍보물 텍스트 추출 추가
- 유형: development_instruction (서비스 프롬프트 실험 아님, 기능 전체 완성 아님)
- 날짜/시간: 2026-10-25 17:35~18:01 (Asia/Seoul)
- 작업자: 김민정 / 기능: green_claim / 브랜치: feature/green_claim (HEAD c4c85a9 = origin/feature/green_claim, 작업 전 변경 없음. 원격 최신성은 마지막 fetch 2026-10-25 15:43 이후 미확인)
- 도구·모델/설정: Claude Code(VS Code 확장), 모델 ID claude-opus-5-5(세션 시스템 정보), 그 밖의 설정 미확인. OpenAI·외부 유료 API 호출 없음
- 지시 요약(팀 합의에 따라 요약본 기록)
  - 일반 PDF 선택 → 글자 추출 → 추출 범위·문구 확인 → 사용자 수정. 직접 입력 유지. OCR·이미지·Word·AI 검수·결과 PDF 제외
  - 팀 협의 공통 변경: pypdf를 jasonenv에 설치하고 검증 버전을 requirements.txt에 고정(다른 패키지·공통 파일 제외)
  - 제한: PDF 1개, 10,000,000바이트, 20페이지, 추출 30초, 추출 텍스트 20,000 코드 포인트(페이지 구분 줄바꿈 포함)
  - POST /api/green-claim/extract, routes=요청·응답, service=처리, 명세에 계약 먼저 기록. 메모리 처리 우선·스풀링 확인, Windows에서 실제 작업 종료
- 변경 이유: 명세 1단계의 파일 입력 중 일반 PDF를 먼저 지원하기 위함
- 실제 결과
  - pypdf 6.21.2 설치(추가 패키지 없음), pip check "No broken requirements found.", requirements.txt에 고정
  - feature_spec.md: "일반 PDF 텍스트 추출" 계약(제한·이유·요청·응답·오류 코드·처리 방식)을 구현 전에 추가, 구현 후 "구현 상태 갱신" 추가
  - routes.py: 엔드포인트 추가. Werkzeug FormDataParser에 메모리 stream_factory 지정(기본은 500KB 초과 시 임시 파일 스풀링), 요청 본문 상한 10,000,000+65,536바이트
  - service.py: 확장자·%PDF- 헤더 검사, multiprocessing spawn 별도 프로세스 실행, 30초 초과 시 terminate→kill·회수, 동시 2건 제한, 페이지 결합·범위 계산·20,000자 검사(자르지 않음)
  - pdf_worker.py(신규): pypdf 추출, 암호화·손상·페이지 수 판정, pypdf 경고 출력 억제
  - panel.html·JS·CSS: 입력 방식 전환, PDF 선택·추출·처리 중 표시·오류 안내, 추출 문구 편집칸(기존 글자 수·빈 입력·초과 안내 재사용), 교체 확인, 처리 중 파일 교체 시 요청 취소, 수정 후 위치 안내
  - tests/test_pdf_extract.py(신규): 17개 테스트
- 작업 중 발견·수정한 문제
  - max_form_memory_size를 4KB로 두어 작은 PDF도 413이 남 → Werkzeug가 수신 버퍼에도 이 값을 적용함을 소스로 확인, Flask 기본값 500,000으로 수정
  - 시간 초과 시 프로세스를 2초 기다린 뒤 종료해 자식이 끊긴 파이프에 쓰며 트레이스백 출력 → 시간 초과는 즉시 종료, 자식 전송 실패는 조용히 처리
  - 처리 중 파일 교체 시 "취소" 안내가 "새 파일 선택" 안내로 덮임 → 취소 안내 우선 표시
- 한계·남은 사항
  - 30초 실제 초과 사례(무거운 PDF)는 만들지 못함. 시간 초과는 제한 시간을 0.05초로 줄인 실제 프로세스 테스트로만 확인
  - 10MB 제한은 파싱 중 메모리 사용량을 보장하지 않음. Windows에서 자식 프로세스 메모리 상한은 설정하지 않음
  - 복잡한 표·다단 문서 읽기 순서 미보장, 텍스트가 나온 페이지의 이미지 속 문구 누락 가능
  - 공통 AI 회귀 테스트(tests/test_common)는 jasonenv에 openai·pydantic·httpx2가 설치되어 있지 않아(pypdf 설치 전부터) 실행 불가. 설치는 승인 범위 밖이라 하지 않음
  - 사용자가 5003에서 실행 중인 서버(debug 재시작기)는 건드리지 않았으나 코드 변경으로 자동 재시작되어 새 코드가 반영됨
  - routes.py의 FEATURE description("인증 요건 대비 보유 증빙의 차이")은 이번 범위 밖이라 그대로 둠(이전 보고와 같음)

## DEV-2026_10_25-05 후속: PDF 추출 차이 원인 확인(읽기 전용)
- 유형: development_instruction (코드 변경 없음)
- 날짜/시간: 2026-10-25 19:31 (Asia/Seoul)
- 도구·모델/설정: Claude Code, 모델 ID claude-opus-5-5(세션 시스템 정보), 그 밖의 설정 미확인
- 지시 요약: 사용자 비교 결과(내부 공백 추가, fi/fl 합자 차이, 일부 단계 번호 순서 차이, 주요 누락 미확인)를 기록하고, 현재 추출 코드가 공백·문자·순서를 바꾸는지 읽기 전용으로 확인. 자동 보정 금지, 코드·공통 파일·Git 변경 금지
- 결과
  - 우리 코드의 문구 변경은 줄바꿈 정규화(CRLF·CR→LF)뿐이며, 공백·합자·순서 변경은 하지 않음을 코드로 확인
  - 원인 후보는 pypdf 기본 추출 방식: 자간 기준 공백 삽입, 합자 글리프의 U+FB01/FB02 매핑, 콘텐츠 스트림 순서 추출(설치본 소스·문서 설명으로 확인)
  - validation.md에 사용자 보고·직접 확인·원문 없이 판단 불가 항목을 구분해 기록
- 수정 필요 여부 판단(제안, 미구현)
  - 지금 코드 결함으로 보이지 않음. 이미 화면에 "원본과 비교해 확인", "읽는 순서가 다를 수 있음" 안내와 수정 기능이 있음
  - 안내 문구에 공백·합자 차이 가능성을 추가할지, layout 모드·합자 표시 방식 검토를 할지는 담당자 결정 필요. 공백 일괄 삭제·NFKC·번호 재배치 같은 자동 보정은 원문 의미를 바꿀 수 있어 하지 않음
- 한계: 해당 PDF·추출본을 직접 보지 않아 원인을 확정하지 못함

## DEV-2026_10_25-06 Word 홍보물 텍스트 추출 추가
- 유형: development_instruction (서비스 프롬프트 실험 아님, 기능 전체 완성 아님)
- 날짜/시간: 2026-10-25 19:40~20:16 (Asia/Seoul)
- 작업자: 김민정 / 기능: green_claim / 브랜치: feature/green_claim (HEAD eeece71 = origin/feature/green_claim, 담당자가 develop 9e2066c를 병합한 상태, 작업 전 변경·병합 중·충돌 없음. 원격 최신성은 마지막 fetch 2026-10-25 19:38 이후 미확인)
- 도구·모델/설정: Claude Code(VS Code 확장), 모델 ID claude-opus-5-5(세션 시스템 정보), 그 밖의 설정 미확인. OpenAI·외부 유료 API 호출 없음
- 지시 요약(팀 합의에 따라 요약본 기록)
  - Word(.docx) 선택 → 글자 추출 → 본문·표 문구 확인·수정. 직접 입력·일반 PDF 유지. OCR·이미지·Word 속 이미지 글자·AI·결과 PDF 제외
  - 승인 공통 변경: python-docx와 필수 하위 의존성 설치, requirements.txt에 python-docx와 설명만 추가(기존 항목·pypdf 버전 변경 금지)
  - 문단·표를 문서 순서대로, 병합 셀 반복 없이, 중첩 표 지원 여부 명시, 하이퍼링크 글자 확인, 자동 보정 없음
  - 제한: 파일 1개·10,000,000바이트·30초·ZIP 항목 1,000개·압축 해제 50,000,000바이트·20,000자. 실제 읽기 중에도 제한 적용
  - 처리 중 파일 교체·입력 방식 전환 시 오래된 응답 반영 금지
- 작업 전 확인한 공통 변경(develop 병합분, 읽기 전용): common/pdf_utils.py(inspect_pdf, 하위 클래스로 pypdf 암호 해제 차단), ai_client PDF 입력, config PDF_*, data_contracts·decisions·README. 담당 PDF 코드와 합치거나 교체하지 않음
  - 차이 보고(변경 안 함): 공통 PDF 상한 10 MiB(10,485,760) vs green_claim 10,000,000바이트, 손상 코드 PDF_CORRUPT(400) vs PDF_DAMAGED(422)
  - 공통 문서상 pypdf는 암호화 PDF에 빈 비밀번호 해제를 시도함 → green_claim PDF worker에서 AES 암호화 PDF는 cryptography 미설치 시 PDF_DAMAGED로 안내될 가능성(미검증, 이번 범위 밖)
  - 병합으로 requirements.txt의 green_claim pypdf 주석 2줄이 공통 PDF 설명으로 바뀐 상태(담당자 병합 결과, 수정하지 않음)
- 변경 이유: 명세 1단계 파일 입력 중 Word(.docx)를 지원하기 위함
- 실제 결과
  - python-docx 1.2.0 설치, 필수 하위 의존성 lxml 6.1.3·typing_extensions 4.16.0 신규 설치, 기존 패키지 버전 변경 없음(pypdf 6.21.2 유지), pip check 정상
  - requirements.txt 끝에 3줄 추가(주석 2줄 + python-docx==1.2.0), 기존 내용 바이트 동일
  - feature_spec.md: "Word(.docx) 텍스트 추출" 계약을 구현 전에 추가, 구현 후 "구현 상태 갱신 (Word 추출)" 추가
  - docx_worker.py(신규): ZIP 검사(항목 수·선언 크기·실제 압축 해제량·항목 암호화), [Content_Types] 주 문서 형식 확인, 미지원 요소 감지, 문단·표 순서 추출(tc 단위로 병합 셀 1회, 중첩 표 재귀), 20,000자 초과 시 조기 중단
  - service.py: run_worker에 target·options 추가(PDF 기본값 유지), validate_docx_upload(ZIP·OLE 서명, EncryptedPackage), build_docx_result, extract_docx, extract_file(확장자 분기), DOCX 오류 코드 7개, 파일 공통 오류 문장 일반화, PDF 결과에 format 추가
  - routes.py: extract_file 호출로 변경(파서·상한 유지)
  - panel.html·JS: PDF·Word 선택 안내, Word 블록 기준 요약, 감지 요소·일반 안내 구분, 처리 중 방식 전환 시 취소
  - tests: test_docx_extract.py(신규 18개), test_pdf_extract.py 기대값 변경(format 필드, PDF 내용 .docx → DOCX_INVALID, FILE_TYPE_UNSUPPORTED 확인은 .doc 사용)
- 작업 중 발견·수정한 문제: python-docx 요소의 xpath()는 namespaces 인자를 받지 않아 lxml XPath로 평가하도록 수정, 테스트 XML의 VML 네임스페이스 선언 누락 수정, 긴 문서 가상 자료가 20,000자에 못 미쳐 분량 조정, 기록 추가 중 셸 heredoc 구문 오류(기록 미추가 상태 확인 후 다른 방법으로 추가)
- 한계·남은 사항
  - 실제 Office 암호화 .docx는 만들 수 없어 EncryptedPackage 판별은 모의 바이트로만 확인
  - 실제 30초 초과 Word 문서는 만들지 못함(제한 0.05초로 줄인 실제 프로세스 테스트만)
  - 미지원 요소 감지는 알려진 XML 요소 기준이며 모든 누락을 찾는다고 보장하지 않음. w:ins 등 감싸인 글자는 추출되지 않음(감지 시 안내)
  - 병합 셀 처리는 python-docx 표 요소 API(tr_lst·tc_lst·vMerge)에 의존(버전 고정)
  - 공통 회귀 테스트는 jasonenv에 httpx2·openai·pydantic이 없어 import 실패로 실행 불가(승인 범위 밖이라 설치 안 함)
  - routes.py FEATURE description("보유 증빙의 차이")은 범위 밖이라 그대로

## DEV-2026_10_25-06 후속: Word 추출 사용자 수동 확인 결과 기록
- 유형: development_instruction (기록 추가만, 코드 변경 없음)
- 날짜/시간: 2026-10-25 20:23 (Asia/Seoul)
- 도구·모델/설정: Claude Code, 모델 ID claude-opus-5-5(세션 시스템 정보), 그 밖의 설정 미확인
- 지시 요약: 사용자가 실제 브라우저에서 확인한 Word 추출 결과 8건(3개 언어 보존, 문단→표→문단 순서, 행·셀 구분과 병합 셀 1회, 하이퍼링크 표시 글자, 머리글 제외, "머리글·바닥글" 감지 안내, 편집 후 탭 왕복 유지, 수정 후 위치 안내)을 validation.md·prompt_log.md에 사용자 수동 확인으로 추가. Claude 직접 테스트와 구분, 나머지 미검증 유지, 문서 전체 본문 기록 금지. 코드·공통 파일·Git 변경 금지
- 결과: validation.md에 사용자 보고 8건을 "통과(사용자 보고)"로 기록하고 미검증 항목을 유지. 문서 본문은 기록하지 않음(사용자가 전달한 링크 표시 글자·추가 문구만 기록)
- 한계: 사용자 브라우저 종류·버전·확인 시각과 사용 문서의 출처는 미확인. Claude는 사용자 화면·문서를 직접 보지 않음
