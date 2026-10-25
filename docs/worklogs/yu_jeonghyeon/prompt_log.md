# 프롬프트 로그

현재 기록 없음. 아래 항목을 실제 작업 후 추가하세요.

유형 / 실험 ID / 날짜 / 기능 / 모델·설정 / 프롬프트 경로·버전 / 입력·근거 / 실제 출력 / 문제 / 변경 이유 / 제어 / 재검증 / 한계

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

---

## DI-2026_10_25-02 공통 OpenAI 연결 첫 구현(텍스트 구조화·이미지 1장)
- 유형: development_instruction
- 날짜/시간: 2026-10-25 (Asia/Seoul). 작업 중 "Connection lost mid-response"로 중단 후 같은 날 재개
- 작업자: 유정현 / 범위: 공통(common/ai_client.py 등), 브랜치 feature/openai_common
- 도구·모델: Claude Code (Opus 5.5). 서비스 모델(OpenAI) 호출 없음
- 서비스 프롬프트: 해당 없음(기능별 프롬프트 미작성)
- 지시 요약: 텍스트 → 구조화 결과(Responses API `responses.parse` + Pydantic), 텍스트 프롬프트 → PNG 1장(Images API `images.generate`)의 공통 Python 연결만 구현. 모의 응답으로 검증. 모델은 환경변수(`OPENAI_MODEL`, `OPENAI_IMAGE_MODEL`). timeout 60/180초, max_retries 0, max_output_tokens 4096, store=False(텍스트만). 크기 3종·품질 low/medium/high·PNG. 실제 API 호출·Git 변경 금지
- 확인한 근거: 공식 문서 5개(structured-outputs, image-generation, models/gpt-5.4-mini, models/gpt-image-2.5-sunburst, your-data) 조회 2026-10-25. 설치한 SDK(openai 3.37.0) 시그니처·소스(`responses.parse`, `images.generate`, 예외 계층, parse 단계 검증) 직접 확인
- 중단 전 완료: openai 3.37.0 설치(jasonenv), common/errors.py, common/config.py 작성
- 재개 후 확인: 브랜치·status·diff, 두 파일이 끝까지 작성되어 import되는 것 확인. 남은 python 프로세스 3개는 사용자가 띄운 `app.py`(이번 작업과 무관, 종료하지 않음)
- 재개 후 작성: common/ai_client.py, tests/test_common/test_ai_client.py, requirements.txt, .env.example, docs/data_contracts.md, docs/decisions.md, README.md
- 발견 사항
  - openai 3.37.0의 HTTP 의존성은 httpx가 아니라 httpx2 2.16.0
  - 잘린 JSON은 SDK `responses.parse` 내부에서 pydantic ValidationError가 발생해 `AI_INCOMPLETE`가 아닌 `AI_OUTPUT_INVALID`로 보고됨(문서화)
  - jasonenv에 python-dotenv 1.1.1이 이미 설치되어 있어 Flask app.run / flask run이 `.env`를 자동 로드할 수 있음(requirements에는 없음). README에 명시
  - 공식 이미지 가이드는 Sunburst가 xhigh·max·auto 품질과 사용자 지정 크기도 지원한다고 설명 → 첫 버전 제한은 프로젝트 범위로만 표기
- 서비스 프롬프트 실험: 미실행 / OpenAI 실제 호출: 미실행
- 담당자 판단: 검토 대기
- 남은 한계: 실제 모델 접근 권한·응답 형식·품질·비용 미검증. PDF·스캔 PDF 입력은 후속 작업

## DI-2026_10_25-03 공통 OpenAI 연결 커밋 전 최종 검증·문서 정정
- 유형: development_instruction
- 날짜: 2026-10-25 (Asia/Seoul) / 작업자: 유정현 / 범위: 공통 OpenAI 연결
- 도구·모델: Claude Code (Opus 5.5). 서비스 모델(OpenAI) 호출 없음
- 지시 1(최종 검증): git 상태·diff, `pip check`, 공통 unittest 실행. 패키지·파일 변경 금지
  - Claude 실행 결과: 자동 승인 판정 오류로 Bash 명령이 차단되어 **미실행**. 우회하지 않고 보고함
  - Claude가 파일 읽기로 확인: requirements.txt 직접 의존성 4개 버전 = 설치 dist-info 버전. Flask·python-dotenv 소스로 `.env` 로드 경로 분석 → `common/config.py` docstring이 실제 동작과 다름을 발견
  - 정정: 이전 보고의 "SDK 로그 노출을 막았다"는 표현을 정정함. SDK 로그 억제 코드는 없고, 공통 코드 자체 로그 최소화·예외 체인 제거·`__repr__` 축약만 적용
- 사용자 직접 실행 결과를 전달받음(Claude 미관측): jasonenv python에서 `pip check` → No broken requirements found., unittest → Ran 32 tests in 0.465s OK
- 지시 2(문서·주석): config.py docstring을 "모듈은 .env를 직접 로드하지 않음, Flask 실행 경로·python-dotenv 여부에 따라 로드될 수 있음"으로 수정. README의 `.env` 설명을 소스 기준·실제 로드 미검증으로 수정, 밀려난 안내 문장 위치 복원. 실행 로직·테스트·패키지·환경변수 변경 없음. 테스트 재실행 안 함
- 이번 턴에도 git 확인 명령이 승인 판정 오류로 차단되어 현재 브랜치·변경 상태 미확인
- 서비스 프롬프트 실험: 미실행 / OpenAI 실제 호출: 미실행
- 남은 한계: 실제 OpenAI API 호출·모델 접근·품질·비용, 실제 `.env` 로드 동작 미검증
