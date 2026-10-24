# fionex 개발 준비 패키지

2026-10-24 기준. 서비스(대시보드)명 fionex.
효성티앤씨 해외영업·마케팅 담당자의 브라질 리젠 T2T 업무 지원.

## 현재 단계
구조·규칙·명세 초안, 공통 UI(사이드바·탭 화면·디자인 토큰)와 공통 동작(새로고침 없는 탭 전환,
탭별 입력·파일 메모리 유지, 새로고침·종료 경고, 작업 상태 API)까지 구현했습니다. 다음은 각 기능 개발입니다.
AI 호출, 뉴스 수집, 시장 분석, 파일 분석, 인증 판정, 소개서·콘티 생성, PDF 출력, 로그 자동 수집은 아직 구현되지 않았습니다.
각 탭의 입력 항목은 공통 UI 확인용 예시이며 버튼은 "준비 중"으로 비활성화되어 있습니다.
Git 초기화·원격 연결·커밋·푸시·배포는 수행하지 않았습니다.

## 실행 (공통 화면)
API 키 없이 실행됩니다. `.env`는 아직 읽지 않습니다.
```
conda activate jasonenv
pip install -r requirements.txt
python app.py
```
브라우저에서 http://127.0.0.1:5003 을 엽니다. 로컬 개발 기본 포트는 5003입니다.
Flask CLI로 실행할 때도 같은 포트를 사용합니다:
```
flask --app app run --port 5003
```
5003 포트를 다른 프로그램이 쓰고 있으면 그 프로그램을 확인한 뒤 실행하세요.
공통 UI 사용법과 기능 코드가 쓸 작업 상태 API는 docs/design_system.md를 확인하세요.

## 먼저 읽기
1. docs/decisions.md: 확정 범위와 미정 사항
2. docs/development.md, docs/git_rules.md
3. docs/recording_rules.md, docs/design_system.md
4. 담당 features/<기능>/feature_spec.md

## 기술 기준
이 구조는 대화에서 제안한 Flask + HTML/CSS/JavaScript 기준입니다.
로컬 기준 Conda jasonenv / Python 3.11. AI는 서버에서 OpenAI API 호출.
requirements.txt에는 실행 확인한 Flask 3.1.2만 있습니다. 프런트 프레임워크는 쓰지 않습니다.
OpenAI 모델·SDK 버전·PDF 라이브러리·배포 플랫폼은 아직 선정하지 않았습니다. 선정·검증 후 추가하세요.

## 개발 순서
폴더·규칙 확인 → 공통 디자인 확정 → 공통 레이아웃·탭 상태 유지 구현 → 기능 개발 → 통합 검증.
현재 기능 개발 단계 직전입니다. 각 담당자는 기능 명세의 미정 항목을 채운 후 구현합니다.
기능별 Blueprint는 features/<기능>/routes.py에 있고 app.py가 등록합니다.
템플릿은 features/<기능>/templates/<기능>/, 정적 파일은 /features/<기능>/static/ 경로로 제공됩니다.

## 기록
개인 worklogs에 개발 지시와 서비스 프롬프트 실험을 구분합니다.
CLAUDE.md는 기록 절차를 지시하는 문서이며 백그라운드 자동 기록 프로그램은 아닙니다.
제출용 로그에는 실제 관측값과 검증 결과만 작성합니다.

## 사용자 데이터
로그인·개인 작업 DB·이전 결과 복원 없음. 결과는 PDF 다운로드.
현재 브라우저 페이지의 메모리에서 탭별 작업 상태 유지. 새로고침·종료 시 복원하지 않음.
공통 기준 자료·시장 캐시·개발 실험 기록은 사용자 결과물 저장과 별개입니다.
