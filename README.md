# fionex 개발 준비 패키지

2026-10-24 기준. 서비스(대시보드)명 fionex.
효성티앤씨 해외영업·마케팅 담당자의 브라질 리젠 T2T 업무 지원.

## 현재 단계
구조·규칙·명세 초안, 공통 UI(사이드바·탭 화면·디자인 토큰)와 공통 동작(새로고침 없는 탭 전환,
탭별 입력·파일 메모리 유지, 새로고침·종료 경고, 작업 상태 API)까지 구현했습니다. 다음은 각 기능 개발입니다.
공통 OpenAI 연결(텍스트 구조화 결과·이미지 1장 생성, common/ai_client.py)을 구현했고 모의 테스트를 통과했습니다.
2026-10-25 사용자 직접 실행 결과를 전달받아 두 공통 함수의 실제 호출과 반환 형식을 확인했습니다. 업무 결과 품질·비용·소요 시간·응답 모델명·사용량은 미검증이며, PDF·스캔 PDF 입력은 아직 미구현입니다.
각 기능의 AI 호출, 뉴스 수집, 시장 분석, 파일·PDF·스캔 PDF 분석, 인증 판정, 소개서·콘티 생성, PDF 출력, 로그 자동 수집은 아직 구현되지 않았습니다.
각 탭의 입력 항목은 공통 UI 확인용 예시이며 버튼은 "준비 중"으로 비활성화되어 있습니다.
Git 초기화·원격 연결·커밋·푸시·배포는 수행하지 않았습니다.

## 실행 (공통 화면)
API 키 없이 실행됩니다. 키와 모델은 AI 함수를 호출할 때 환경변수에서 읽습니다.
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

### OpenAI 환경변수
`OPENAI_API_KEY`, `OPENAI_MODEL`(텍스트), `OPENAI_IMAGE_MODEL`(이미지). 양식은 `.env.example`(비밀값 없음).
앱 코드는 `.env`를 직접 읽지 않습니다. 실행 셸에 환경변수를 설정하세요(PowerShell 예):
```
$env:OPENAI_API_KEY = "<본인 키>"
$env:OPENAI_MODEL = "gpt-5.4-mini"
$env:OPENAI_IMAGE_MODEL = "gpt-image-2.5-sunburst"
python app.py
```
주의: Flask 3.1.2 소스 기준으로, 실행하는 Python에 `python-dotenv`가 있고 `FLASK_SKIP_DOTENV`가 설정되지 않았으면
`python app.py`(app.run 시작 시)와 `flask --app app run`(앱 import 전) 모두 실행 위치에서 상위 폴더 방향으로 찾은 `.env`를 로드할 수 있습니다
(이미 설정된 환경변수가 우선). 실제 로딩 동작은 검증하지 않았습니다. requirements.txt에는 python-dotenv가 없지만,
2026-10-25 확인 시 jasonenv에는 python-dotenv 1.1.1이 별도로 설치되어 있었습니다. `.env`는 Git에서 제외됩니다.
SDK 디버그 로그(`OPENAI_LOG`)는 기록 범위를 검증하지 않았으므로 서비스 실행 시 켜지 않습니다.

### KOTRA 환경변수
`KOTRA_API_KEY`: 홈 업계 소식의 KOTRA 해외시장뉴스 Open API(공공데이터포털) 인증키. 실제 값은 `.env`에만 둡니다(양식은 `.env.example`).
값이 없으면 KOTRA 수집만 "설정 필요"로 표시되고 Google News·ABIT 뉴스는 그대로 동작합니다.
위 OpenAI 환경변수와 같이 앱 코드는 `.env`를 직접 읽지 않으므로, 실행 셸에 설정하거나 python-dotenv가 있는 환경에서 실행해야 반영됩니다.

### 공통 테스트
```
python -m unittest discover -s tests/test_common -v
```
모의 전송으로 외부 요청을 막습니다. 실제 키·유료 API를 사용하지 않습니다.

공통 UI 사용법과 기능 코드가 쓸 작업 상태 API는 docs/design_system.md를 확인하세요.

## 먼저 읽기
1. docs/decisions.md: 확정 범위와 미정 사항
2. docs/development.md, docs/git_rules.md
3. docs/recording_rules.md, docs/design_system.md
4. 담당 features/<기능>/feature_spec.md

## 기술 기준
이 구조는 대화에서 제안한 Flask + HTML/CSS/JavaScript 기준입니다.
로컬 기준 Conda jasonenv / Python 3.11. AI는 서버에서 OpenAI API 호출.
requirements.txt: Flask 3.1.2, openai 3.37.0, pydantic 2.14.1, httpx2 2.16.0(jasonenv 설치 확인). 프런트 프레임워크는 쓰지 않습니다.
OpenAI 모델은 초기 후보(gpt-5.4-mini, gpt-image-2.5-sunburst)이며 최종 선정 전입니다. 실제 호출·반환 형식은 사용자 실행 결과로 확인했고, 품질·비용·소요 시간은 미검증입니다.
PDF 라이브러리·배포 플랫폼은 아직 선정하지 않았습니다. 공통 AI 함수 사용법은 docs/data_contracts.md를 확인하세요.

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
