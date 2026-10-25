# 프롬프트 로그

아래 항목을 실제 작업 후 추가하세요.

유형 / 실험 ID / 날짜 / 기능 / 모델·설정 / 프롬프트 경로·버전 / 입력·근거 / 실제 출력 / 문제 / 변경 이유 / 제어 / 재검증 / 한계

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

## DEV-PS-2026_10_25-01 · development_instruction

- 날짜/시간: 2026-10-25 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오
- 유형: development_instruction (서비스 프롬프트 실험 아님)
- 도구/모델: Claude Code (Opus 5.5) — 서비스 OpenAI 모델 호출 없음
- 지시 원문: "md 파일에 맞춰서 개발 시작" / "궁금한 점은 전부 물어보고 진행해"
- 확인 질문과 담당자 답변:
  - 범위 → 13장 2단계(입력 폼·검증·탭 상태)만
  - jasonenv에 Flask·openai 미설치 → requirements.txt 설치 실행 승인
  - 미정 기본값·글자 수 → 권장안 확정(feature_spec.md 3장 표)
  - AI 연결(gpt-6.1-sol·참조 이미지 vs 공통 ai_client) → 공통 확장 요청 방식, 제안서 작성은 이번엔 생략
  - 검증 방식 → 브라우저 + 서버 함수 / 로고 적용 범위 → 입력 폼에서 선택
- 변경: features/promotion_studio/{service.py, routes.py, templates/promotion_studio/panel.html, static/promotion_studio.js, static/promotion_studio.css, feature_spec.md}, tests/test_promotion_studio/test_input_validation.py
- 검증: validation.md 2026-10-25 항목 참고
- 남은 한계: 문서 추출·OCR·콘티 생성 미구현, 실제 사용자 브라우저(Edge·Safari·모바일) 미확인, MAX_CONTENT_LENGTH 미설정(공통 조율 필요)

## DEV-PS-2026_10_25-02 · development_instruction

- 날짜/시간: 2026-10-25 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오 (브랜치 feature/promotion_studio, Git 사용자·변경 파일 기준으로 판단)
- 유형: development_instruction (서비스 프롬프트 실험 아님)
- 도구/모델: Claude Code (Opus 5.5) — 서비스 OpenAI 모델 호출 없음
- 지시 원문: "requiremeents.txt 설치하고 지금까지 내용 바탕으로 prompt_log.md 기록해줘"
- 실행: jasonenv(Python 3.11.17)에서 `python -m pip install -r requirements.txt`
  - pip freeze 전후 비교: pypdf==6.21.2 한 줄만 추가(공통 PDF 검사용, 이전 설치 이후 requirements.txt에 추가된 항목). 나머지 Flask 3.1.2·openai 3.37.0·pydantic 2.14.1·httpx2 2.16.0은 이미 설치됨
  - pip check: No broken requirements found
- 확인: import 버전 확인(Flask 3.1.2, openai 3.37.0, pydantic 2.14.1, pypdf 6.21.2)
- 테스트 경과:
  - 1차 `python -m unittest discover -s tests -t .` 전체 실행 → 실패. `ImportError: Start directory is not importable: '...\tests'`(tests 폴더가 패키지가 아님). 테스트 자체 실패가 아니라 탐색 시작 경로 문제
  - 2차 README 방식대로 폴더별 실행: `unittest discover -s tests/test_common` 56개 OK, `-s tests/test_promotion_studio` 29개 OK
- 코드 변경: 없음(이 기록 파일만 갱신)
- 남은 한계: DEV-PS-2026_10_25-01과 동일. 실제 OpenAI 호출·브라우저 재확인은 이번에 실행하지 않음

## DEV-PS-2026_10_25-03 · development_instruction

- 날짜/시간: 2026-10-25 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오 (브랜치 feature/promotion_studio)
- 유형: development_instruction (서비스 프롬프트 실험 아님, 실제 서비스 모델 호출 없음)
- 도구/모델: Claude Code (Opus 5.5)
- 지시 원문: "결론적으로 나는 http://127.0.0.1:5003/#promotion_studio 이 링크 접속했는데 콘티 조건을 모두 입력하면 콘티 결과가 나오게 만들고 싶어"
- 앞선 대화: 서버가 꺼져 ERR_CONNECTION_REFUSED → Claude가 jasonenv로 `python app.py` 재실행, 직접 실행 방법 안내
- 판단(담당자 확인 전 기본값으로 진행, 보고 시 공유):
  - 범위: 13장 4단계 중 텍스트 콘티 생성·표시만. 3단계(문서 추출·OCR)를 건너뛰어 제품 설명 직접 입력만 근거로 사용, 문서·사진·로고는 업로드 시 "미반영" 안내
  - 모델: 공통 `generate_structured`(OPENAI_MODEL) 그대로 사용. gpt-6.1-sol 지정·서버 대기 시간 변경은 공통 확장이 필요해 공통 파일 미수정
  - 시간: 모델은 장면 길이만 내고 시작·종료 시간은 코드 계산. 합계 불일치는 경고만, 장면 수 불일치는 오류
- 서비스 프롬프트: `features/promotion_studio/prompts/storyboard_generate_v1.md` 신규 작성(입력은 데이터로 취급, 제품 설명 밖 사실 금지, 근거 필요한 주장은 review_notes, CTA 공란이면 미작성, 장면 수·합계 규칙, 한국어는 검토용 번역). **실제 모델 실험 미실행**
- 변경: features/promotion_studio/{service.py, routes.py, templates/promotion_studio/panel.html, static/promotion_studio.js, static/promotion_studio.css, feature_spec.md, prompts/storyboard_generate_v1.md}, tests/test_promotion_studio/{test_input_validation.py, test_storyboard.py}
- 시행착오: Bash heredoc 안에서 큰 JS 수정 스크립트를 실행하다 셸 따옴표 해석 오류로 실패(파일 변경 없음 확인) → Edit 도구로 다시 적용
- 검증: validation.md 2026-10-25 "텍스트 콘티 생성" 항목(단위 테스트 40개·공통 56개 OK, 가짜 AI 서버 화면 확인, 키 없는 실제 서버의 설정 오류 안내 확인)
- 남은 한계: 실제 호출·품질·시간·비용 미검증, 서버 timeout 60초 고정, 제목·장면 편집·이미지·PDF 미구현

## EXP-PS-2026_10_25-01 · service_prompt_experiment

- 날짜/시간: 2026-10-25 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오 텍스트 콘티 생성
- 지시 원문: "너가 일단 먼저 테스트 호출 해바" (담당자가 사용자 환경변수에 키·모델 설정 후 "설정했어")
- 모델/설정: OPENAI_MODEL=gpt-5.4-mini → 응답 모델 gpt-5.4-mini-2026-03-17, Responses API(공통 generate_structured), max_output_tokens 6200, store=False, timeout 60초, 재시도 0, 1회 호출
- 프롬프트: features/promotion_studio/prompts/storyboard_generate_v1.md
- 테스트 입력: 가상 입력(바이어용, 제품 소개+친환경 가치 전달, 전문적·신뢰감, CTA 공란, 30초, 6장면, 16:9, 실사형). 근거 없는 "탄소 배출 감소" 주장을 일부러 포함
- 실행: Claude가 저장소 밖 임시 스크립트로 `service.generate_storyboard`를 직접 호출(화면 경유 아님)
- 실제 응답 파일: docs/worklogs/jeong_eunjin/experiments/exp_ps_2026_10_25_01.json
- 측정: 8.7초, 토큰 input 1,077 / output 1,454 / total 2,531. 비용 금액은 계산하지 않음
- 정상 동작
  - 스키마 검증 통과, 6장면, 장면 길이 5초씩 합계 30초(timing.ok=true)
  - CTA 공란 → 마지막 장면 자막·내레이션 비움, review_notes에 "CTA 없음" 명시
  - 근거 없는 탄소 감소 주장 → review_notes에 장면 5 근거 확인 필요로 표시, 화면 설명에 "숫자 없이" 연출
  - 입력에 없는 수치·인증·고객사 추가 없음(사람이 전체 문장을 읽고 확인)
- 발견 문제
  1. 언어 오염: 장면 5 narration_ko에 힌디어 "विकल्प", review_notes에 "दावा"가 섞임
  2. review_notes를 지시(한국어)와 달리 포르투갈어로 작성
  3. 장면 5 subtitle_pt "Menor emissão de carbono…"는 근거 없는 주장을 단정형 자막으로 표시(내레이션은 "홍보됩니다"로 완화). review_notes로 표시는 됐지만 화면에 그대로 노출될 수 있음
  4. 포르투갈어 번역 품질·브라질 바이어 대상 적합성은 원어민 검토 전이라 미확인
- 담당자 판단: 대기(보고 후 결정)
- 다음 버전 후보(미작성·미실행): v2에서 review_notes 한국어 고정 강조, _ko 필드는 한국어(한글)만·_pt는 포르투갈어만 사용 명시, 근거 없는 주장은 자막에 단정형으로 쓰지 않기. 코드 쪽으로는 한글·라틴 외 문자(예: 데바나가리) 감지 시 경고 표시 검토
- 남은 한계: 1회·입력 1종이라 재현성 미확인, 장면 수가 많을 때 시간·토큰 미측정, 화면 경유 호출은 담당자 확인 전

## DEV-PS-2026_10_25-04 · development_instruction (Git 규칙 예외)

- 날짜/시간: 2026-10-25 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오 (브랜치 feature/promotion_studio)
- 지시 원문: "너가 커밋해" → Claude가 팀 규칙(AGENTS.md·CLAUDE.md: Git 변경은 사람이 수행)을 안내하고 명령어 제공 → 담당자가 채팅창에 명령어를 붙여 넣어 미실행 확인 → "이번만 예외로 커밋해"
- 처리: 담당자의 명시적 요청으로 이번 1회만 Claude가 `git add`(features/promotion_studio, tests/test_promotion_studio, docs/worklogs/jeong_eunjin)·`git commit` 실행. 푸시·병합은 하지 않음
- 이후 Git 변경은 다시 규칙대로 사람이 수행
