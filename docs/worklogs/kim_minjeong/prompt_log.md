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
