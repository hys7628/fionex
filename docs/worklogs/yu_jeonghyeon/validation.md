# 검증 기록

현재 기록 없음. 아래 항목을 실제 작업 후 추가하세요.

날짜 / 변경 내용 / 검증 절차 / 기대 / 실제 / 판정 / 미검증

미실행·미확인은 그대로 표시하고 결과를 추정해 작성하지 않습니다.

---

## 2026-10-25 공통 OpenAI 연결 첫 구현 (모의 테스트)
- 변경 내용: common/ai_client.py, common/config.py, common/errors.py, tests/test_common/test_ai_client.py
- 환경: Conda jasonenv, Python 3.11.17, openai 3.37.0, pydantic 2.14.1, httpx2 2.16.0, Flask 3.1.2
- 절차: `python -m unittest discover -s tests/test_common` (프로젝트 루트). `_create_client`를 httpx2.MockTransport 클라이언트로 교체해 외부 요청 차단. 가짜 키·가짜 모델명, 코드로 만든 PNG 사용
- 실제 결과: 32개 테스트 실행, 전부 통과(OK). 실행 시점은 코드·테스트 작성 직후이며 이후 코드·테스트 파일은 변경하지 않음(문서·requirements·.env.example만 변경)
- 확인 항목
  - 텍스트 정상: Pydantic 인스턴스·모델명·usage 반환
  - 요청 옵션: timeout 60/180, max_retries 0, model, max_output_tokens 4096, store=false, strict json_schema, 이미지 n=1·size·quality·output_format=png, temperature 등 미전달, 이미지 요청에 store 미전달
  - 입력 오류(빈 지시문·입력·프롬프트, 잘못된 스키마·토큰 값·크기·품질)에서 클라이언트 미생성
  - 텍스트 거절·incomplete(max_output_tokens, content_filter)·failed·스키마 불일치·비JSON·출력 없음 → 오류
  - 이미지 빈 결과·잘못된 base64·PNG 아님·잘린 PNG·크기 불일치·2장 반환·base64 상한 초과(디코딩 전 차단)·moderation_blocked → 오류
  - 401/403/404/429/400/500/503·시간 초과·연결 실패 → 공통 코드, 요청 1회(재시도 없음)
  - 설정: 키·모델 누락 시 미호출, 텍스트/이미지 설정 독립, 호출 시점에 환경변수 읽음
  - 키 없이 `app` import 및 `GET /` 200
  - 오류 메시지·to_dict·예외 체인·수집 로그에 가짜 키·입력·공급자 원문 미포함
- 추가 확인: 루트 로거 DEBUG에서 SDK 3.37.0이 남기는 로그 5줄에 요청 본문·키가 없음을 별도 스크립트로 확인
- 판정: 모의 테스트 통과. **실제 OpenAI 연결 성공을 뜻하지 않음**
- 미검증: 실제 API 호출, 모델 접근 권한, 실제 응답 형식과 SDK 파싱의 일치, 이미지 품질·소요 시간·비용, `OPENAI_LOG` 사용 시 로그 내용, 브라우저 동작(기능 화면 연결 없음), python-dotenv 자동 로드 실제 동작

## 2026-10-25 커밋 전 최종 검증
### Claude 실행 시도 (미실행)
- 대상: `git branch/status/diff`, jasonenv python 확인 → `python -m pip check` → `python -m unittest discover -s tests/test_common -v`
- 결과: 자동 승인 판정 오류("server-side auto mode classifier gave no verdict")로 명령이 차단되어 **실행되지 않음**. 우회하지 않음
- Claude가 명령 없이 확인한 것: jasonenv `site-packages`의 dist-info 이름으로 Flask 3.1.2·openai 3.37.0·pydantic 2.14.1·httpx2 2.16.0이 requirements.txt와 일치. Flask 3.1.2·python-dotenv 1.1.1 소스를 읽어 `.env` 로드 경로 분석(실제 로드는 미검증)

### 사용자 직접 실행 결과를 전달받음
- 실행 주체: 사용자(VS Code CMD). Claude는 실행 결과를 직접 관측하지 않았고 전달받은 내용을 그대로 기록함
- 실행 환경: `C:\Users\user\miniforge3\envs\jasonenv\python.exe`
- `python -m pip check` → `No broken requirements found.`
- `python -m unittest discover -s tests/test_common -v` → `Ran 32 tests in 0.465s` / `OK`
- 판정: 사용자 실행 기준 의존성 충돌 없음, 모의 테스트 32개 통과. **실제 OpenAI 연결 성공을 뜻하지 않음**

### 이후 변경 (문서·주석만)
- common/config.py 모듈 docstring의 `.env` 설명 수정(실행 로직 변경 없음), README.md의 `.env` 로드 설명을 소스 기준·미검증으로 수정
- 문서·주석만 바꿔 테스트를 다시 실행하지 않음(사용자 지시)
- 미검증 유지: 실제 OpenAI API 호출, 모델 접근 권한, 품질, 비용, 실제 `.env` 로드 동작, Git 브랜치·변경 상태(이번 턴 명령 차단으로 미확인)
