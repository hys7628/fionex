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

## DEV-PS-2026_10_25-05 · development_instruction

- 날짜/시간: 2026-10-25 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오 (브랜치 feature/promotion_studio)
- 유형: development_instruction (서비스 모델 호출 없음)
- 도구/모델: Claude Code (Opus 5.5)
- 지시 원문: "그래 다 기능구현 확인했어 이제http://127.0.0.1:5003/#promotion_studio 이거를 pdf파일로 저장해줘" → Claude 질문(화면 인쇄 / 새로 생성해 저장 / PDF 기능 개발) → "지금 화면 그대로 저장" 선택 → Ctrl+P 방법 안내
  → 담당자 스크린샷과 함께 "내가 체크한 저 pdf다운로드 버튼이 활성화가 안돼" → Claude 질문(브라우저 인쇄형 권장 / 서버 PDF 생성, 패키지·글꼴·팀 합의 필요 안내) → "서버에서 PDF 파일 생성" 선택
- 판단: PDF 도구 fpdf2 2.8.9(순수 Python, 유니코드 TTF 지원). A4 가로·파일명은 임시 결정. 결과 저장 없이 브라우저가 결과 JSON을 다시 보내고 서버가 재검증
- 시행착오
  1. 나눔고딕은 포르투갈어 악센트 문자가 없어 cmap 확인 후 제외 → Noto Sans KR
  2. Noto Sans KR 가변 글꼴을 fpdf2 variations로 직접 쓰니 PDF 1개 15.5초 → fontTools로 Regular/Bold 고정 인스턴스를 만들어 0.45초
  3. 첫 인스턴스는 내부 이름이 "Thin"으로 남음 → updateFontNames=True로 재생성
  4. 실험 결과의 힌디어 글자가 PDF에서 빈칸이 되고 fpdf2가 해당 글자를 경고 로그에 남김 → 글꼴에 없는 문자를 □로 바꾸고 위치를 마지막 페이지에 표시(로그에 콘티 글자가 남지 않게 됨)
  5. 글꼴 cmap 확인 함수가 파일을 닫지 않아 ResourceWarning → with 문으로 수정
  6. 패널 테스트가 HTML 속성 순서를 잘못 가정해 실패 → 단언 수정
- 공통 파일 변경: requirements.txt에 fpdf2==2.8.9 추가(“팀 공유 필요” 주석). README·decisions.md의 패키지·PDF 도구 문구는 공통 문서라 수정하지 않음 → 팀 공유 후 갱신 필요
- 변경: features/promotion_studio/{pdf_builder.py(신규), fonts/(신규: Regular·Bold TTF, OFL.txt, README.md), service.py, routes.py, panel.html, promotion_studio.js, promotion_studio.css, feature_spec.md}, tests/test_promotion_studio/test_pdf_download.py(신규), requirements.txt
- 검증: validation.md "텍스트 PDF 다운로드" 항목
- 남은 한계: 장면 이미지 없음, 실제 파일 저장·다른 뷰어 미확인, 글꼴 파일 약 12MB가 저장소에 추가됨

## DEV-PS-2026_10_25-06 · development_instruction

- 날짜/시간: 2026-10-25 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오
- 지시 요약(담당자 붙여넣기): 제품 사진 hs.png(51KB) 첨부 후 PDF 버튼이 '준비 중'으로 비활성 → 활성 조건·파일 변경 이벤트·PDF 처리 확인해 원인 수정, 사진이 있어도 텍스트 콘티 PDF 다운로드 가능하게, 사진 삽입 미구현 안내, 사진 없음/PNG 첨부 각각 검증, 입력·결과 유지
- 원인: 스크린샷의 탭은 PDF 기능 반영 전에 열린 탭(버튼 옆 '준비 중', PDF 종류 선택 없음). 서버는 새 버전을 제공 중이었고, 새 코드의 버튼 조건은 사진과 무관
- 수정: 사진 첨부 시 PDF 안내 문구에 "제품 사진은 이미지 생성 단계 구현 전까지 PDF에 넣지 않음(텍스트 PDF는 가능)" 추가, 파일 변경 이벤트에서 안내 갱신(promotion_studio.js)
- 검증: validation.md "PDF 버튼 비활성 신고 확인" 항목
- 담당자 안내: 옛 탭은 새로고침해야 새 화면이 적용됨. 결과는 페이지 메모리에만 있어 새로고침하면 콘티를 다시 생성해야 함(실제 호출 요금 발생)

## DEV-PS-2026_10_25-07 · development_instruction

- 날짜/시간: 2026-10-25 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오
- 지시 원문: "제품 사진, 로고, 보조 문서에 첨부파일 삭제 버튼을 추가해줘. 파일명 옆에 × 버튼을 넣고, 누르면 해당 파일의 첨부만 해제되게 해줘. 내 컴퓨터의 원본 파일은 삭제하지 말고, 다른 입력값과 생성된 콘티는 유지해줘."
- 구현: 파일 목록 항목마다 × 버튼(aria-label "<파일명> 첨부 해제"). 파일 입력은 일부 삭제를 지원하지 않아 DataTransfer로 나머지 파일 목록을 다시 만들고 change 이벤트를 보내 기존 검증·목록·작성 중 감지·PDF 안내 경로를 재사용. 브라우저는 원본 파일에 접근하지 않음. 보조 문서 안내 문구에 × 해제 설명 추가
- 시행착오: 해제 직후 비동기 서명 검사 뒤 목록을 다시 그리며 키보드 초점이 사라짐 → 다시 그릴 때 초점 복원
- 변경: features/promotion_studio/{static/promotion_studio.js, static/promotion_studio.css, templates/promotion_studio/panel.html}
- 검증: validation.md "첨부 파일 × 해제 버튼" 항목

## DEV-PS-2026_10_25-08 · development_instruction (공통 파일 변경 포함)

- 날짜/시간: 2026-10-25 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오
- 지시 원문: (PDF 장면 페이지 스크린샷과 함께) "pdf파일 접속힌거야 콘티조건에서 첨부파일에 이미지사진넣었을떄 내가 체크한부분에 결과예상사진이 나오게 해줘"
- Claude 질문 1(첨부 사진 그대로 배치 권장 / AI 생성·사진 참고 없음 / AI 생성+사진 참고·공통 확장 필요) → 답변: "두번째 옵션으로 하되 각 장면마다 내가 첨부한 이미지 파일을 무조건 참고해서 이미지를 생성해줘"
- Claude 질문 2(사진 참고는 공통 ai_client에 기능이 없어 공통 파일에 추가 / 요청서만 작성) → 답변: "공통 파일에 기능 추가"
- 근거 확인: OpenAI 이미지 생성 가이드·gpt-image-2.5-sunburst 모델 페이지(2026-10-25) — edits 지원, 토큰 단가, 입력 50MB 미만, 장당 가격 표 없음(실측 필요). SDK openai 3.37.0 images.edit 파라미터 확인
- 공통 변경(공통 담당 유정현 검토 대기): common/ai_client.py에 `generate_image_from_references`·ImageUsage·ReferenceImageResult **추가만**, common/config.py에 IMAGE_REF_* 상수 추가, tests/test_common/test_image_reference.py 신규, docs/data_contracts.md·docs/decisions.md에 추가 사실과 검토 대기 기록
- 기능 변경: prompts/scene_image_v1.md(신규 서비스 프롬프트, **실제 모델 실험 미실행**), service.py(generate_scene_image, parse_pdf_scene_images, conditions에 image_style), routes.py(/scene-image, PDF에 장면 이미지), pdf_builder.py(이미지 영역에 삽입·AI 안내), panel.html·promotion_studio.js·css(확인 창·순차 생성·중지·실패 재시도·PDF 연동), feature_spec.md 6장, tests/test_promotion_studio/test_scene_image.py
- 검증: validation.md "첨부 사진 참고 장면 이미지 생성" 항목. 실제 호출은 OPENAI_IMAGE_MODEL 미설정으로 미실행
- 남은 한계: 외형 유지·비용·시간 실측 전, 장당 예상 비용 미표시(실측 후 SCENE_IMAGE_ESTIMATED_USD 갱신 예정), 선택 장면 재생성·비교 미구현

## EXP-PS-2026_10_25-02 · service_prompt_experiment

- 날짜/시간: 2026-10-25 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오 장면 이미지(첨부 사진 참고)
- 지시: 담당자가 OPENAI_IMAGE_MODEL 설정 후 "설정했어"(앞서 Claude가 1장면 실제 호출을 제안)
- 모델/설정: gpt-image-2.5-sunburst, Images API edits(공통 generate_image_from_references), 1536x1024, quality low, n=1, timeout 180초, 재시도 0, 1회
- 프롬프트: features/promotion_studio/prompts/scene_image_v1.md
- 입력: EXP-PS-2026_10_25-01 장면 2(visual_pt·camera_pt), 16:9, 실사형. 참조 이미지 1장 = 코드로 그린 가상 제품(파란 실패·흰 플랜지·흰 라벨에 초록 "regen T2T"·검정 "TEST") — 실제 제품 사진 아님
- 실제 응답 파일: docs/worklogs/jeong_eunjin/experiments/exp_ps_2026_10_25_02.json, _reference.png, _output.jpg(원본 PNG 2.1MB의 JPEG 사본)
- 측정: 22.2초, 토큰 입력 1,281 / 출력 158, 공식 단가 기준 추정 $0.0142(실제 청구액 미확인)
- 관측(사람이 이미지 확인): 참조 사진의 파란 실패 형태·흰 플랜지·라벨 위치와 문구·글자색이 유지되고 질감만 실사 원사로 바뀜. 배경은 장면 설명대로 나무 테이블·뉴트럴 톤 원단 스와치. 추가 글자·인증 마크·로고 없음
- 발견 문제: 생성 크기 1536x1024(3:2)가 16:9와 달라 PDF 이미지 칸에 좌우 여백 → 콘티 비율로 가운데 자르기(화면 object-fit: cover, PDF는 Pillow 크롭)로 수정. 원본 PNG 그대로 넣으면 장당 PDF 약 3MB → JPEG(품질 85)로 변환해 6장 PDF 226KB
- 담당자 판단: 대기(보고 후 결정)
- 남은 한계: 1회·가상 단순 도형 사진이라 실제 제품 사진(복잡한 질감·로고)의 외형 유지는 미확인, 사진 여러 장일 때 비용·시간, 4:5·9:16 실제 생성, 6장면 전체 실행 시간 미측정. SCENE_IMAGE_ESTIMATED_USD를 이 1회 값(0.0142)으로 설정

## DEV-PS-2026_10_25-09 · development_instruction

- 날짜/시간: 2026-10-25 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오
- 지시 원문: "아니 내말은 pdf다운로드 하고 pdf파일을 열었을떄 이미지 미생성 칸 대신에 이미지가 업로드가 되었으면 좋겠다고"
- 해석: 별도 '장면 이미지 생성' 단계 없이 PDF 다운로드만으로 이미지 칸이 채워져야 함(앞선 구현은 생성 버튼을 따로 눌러야 했음)
- 구현: 제품 사진이 있고 이미지 없는 장면이 있으면 PDF 버튼에서 선택 창 — 'AI 장면 이미지 생성 후 PDF'(비용·시간 안내, 생성 후 자동 다운로드, 실패 장면은 첨부 사진) / '첨부 사진 그대로 넣어 PDF'(무료) / 취소. 사진이 없으면 기존처럼 텍스트 PDF. 서버 PDF에 use_photos·photos 필드, 장면 순서대로 사진 배치·"첨부한 제품 사진(AI 생성 아님)" 표시. 중지하면 PDF를 받지 않음
- 변경: features/promotion_studio/{service.py(parse_pdf_photos), routes.py, pdf_builder.py, panel.html, promotion_studio.js}, tests/test_promotion_studio/test_scene_image.py
- 검증: validation.md "PDF 다운로드 때 이미지 칸 채우기" 항목

## DEV-PS-2026_10_26-01 · development_instruction

- 날짜/시간: 2026-10-26 (Asia/Seoul), 시각 미기록
- 작업자: 정은진 / 기능: 홍보 스튜디오 (feature/promotion_studio에 develop 1adc8a2 병합 중)
- 지시 흐름: "pdf5.1.0버전이야?" → requirements.txt에 5.1.0 없음 안내 → "5.1.0으로 바꿀 수 있을까?" → fpdf2엔 5.1.0 없음·pypdf 5.1.0은 하향이라 공통 위험 안내 → "바꾸지마 일단냅둬" → "requirement.txt에서 pdf출력하는 reportlab 5.1.0인지 확인해주고 내것이 아니면 그걸로 가능한지 알려줘" → 다른 브랜치(home·market_analysis)가 reportlab 5.1.0 사용 확인·전환 가능 안내 → "깃 충돌 뭐가 있어?" → requirements.txt 1개 충돌 안내(둘 다 유지 / reportlab 통일) → "2번으로 해"
- 처리: requirements.txt 충돌을 develop 쪽으로 정리(fpdf2 삭제, reportlab 사용처 주석에 홍보 스튜디오 추가), jasonenv에 병합 requirements 설치 후 fpdf2 제거, pdf_builder.py를 reportlab 캔버스로 재작성(위쪽 기준 mm 좌표 도우미, 공백·글자 단위 줄바꿈, 저장 시 "n/전체" 쪽 번호, 글꼴 문자 집합은 reportlab TTFont로 확인해 fontTools 의존 제거, 글꼴 이름에 기능 접두어)
- 문서: feature_spec.md 7장 도구, docs/decisions.md 내 기록 문장, fonts/README.md
- Git: 충돌 파일 정리까지만 함. `git add`·병합 커밋은 담당자가 수행
- 검증: validation.md 2026-10-26 항목
