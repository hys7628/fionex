# 프롬프트 로그

현재 기록 없음. 아래 항목을 실제 작업 후 추가하세요.

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
