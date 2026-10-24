# Claude Code 진입 규칙

규칙 본문을 여기에 중복하지 않습니다. 작업 전 다음 문서를 읽고 적용하세요.
- README.md
- AGENTS.md
- docs/development.md
- docs/git_rules.md
- docs/recording_rules.md
- docs/decisions.md
- docs/design_system.md

## 매 작업 절차
1. 작업자·담당 기능·개인 기록 경로가 불명확하면 처음에 확인한다.
2. 확인한 작업자 정보를 현재 대화에서 유지한다. 새 대화에서 알 수 없으면 다시 확인하며, 공용 파일에 현재 사용자를 고정하지 않는다.
3. Git 저장소 여부·현재 브랜치·변경 파일을 읽기 전용으로 확인한다. 저장소가 아니면 알리고 초기화하지 않는다. main/develop이면 코드 수정 전에 알리고 사람의 기능 브랜치 준비를 기다린다. 최초 환경 패키지 작성 예외는 docs/git_rules.md 참고.
4. 담당 features/<기능>/feature_spec.md를 읽고 범위와 미정 사항을 확인한다.
5. 승인된 담당 범위 내에서 작업하고 실제 검증을 수행한다.
6. 작업 종료 전에 개인 prompt_log.md와 관련 validation/sources/efficiency/assets 기록을 갱신한다. 실행하지 않은 실험은 미실행으로 남긴다.
7. 변경 파일·실제 검증·미검증·갱신한 기록 경로·커밋 제목 제안을 보고한다.

Git 변경 작업은 사람이 한다. 자동 기록은 매 작업의 파일 갱신 절차를 의미하며 모든 대화/외부 도구 실행의 포착을 보장하지 않는다.
