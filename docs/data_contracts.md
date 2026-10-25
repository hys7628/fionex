# 공통 연결 규칙 (초안)

탭 사이 데이터 자동 전달 없음. 각 탭 입력·결과를 별도 메모리 상태로 관리.
향후 API 접두어: /api/home, /api/market-analysis, /api/product-brochure, /api/green-claim, /api/promotion-studio.
각 엔드포인트와 필드·타입·상한·오류는 구현 전 담당 feature_spec.md에 작성.
권장 성공 응답: {"ok": true, "data": {...}}
권장 실패 응답: {"ok": false, "error": {"code": "...", "message": "..."}}
PDF 응답은 파일 바이너리와 다운로드 헤더 사용. 서버 경로나 키를 오류에 노출하지 않음.
통계는 값·단위·기간·품목코드·출처·조회시각을 함께 전달.
AI 출력에는 근거·미확인 항목을 포함하고 JSON 파싱/필수 필드 검증을 수행.
검수 결과는 제공 근거 범위의 스크리닝이며 법적 적합성 보장이 아님.

## 공통 OpenAI 연결 (common/ai_client.py, 2026-10-25)
서버 Python 코드에서만 호출한다. 공용 HTTP 엔드포인트는 없다. 각 기능 라우트가 아래 함수를 호출하고
실패 시 `AIError`를 위 실패 응답 형식으로 바꾼다. 업무 프롬프트·결과 필드·판단 로직은 기능에서 정의한다.
모의 테스트(tests/test_common) 통과. 2026-10-25 사용자 직접 실행 결과를 전달받아 텍스트·이미지 공통 함수의 실제 호출과 반환 형식을 확인했다.
**업무 결과 품질·비용·소요 시간·응답 모델명·사용량은 미검증**이다. PDF·스캔 PDF 입력은 아직 미구현이며, 각 기능의 OpenAI 연동은 기능별 후속 작업이다.

### 설정
| 환경변수 | 용도 | 초기 후보(.env.example) |
|---|---|---|
| `OPENAI_API_KEY` | 공통 키 | 비움(비밀값) |
| `OPENAI_MODEL` | 텍스트 구조화 결과 | `gpt-5.4-mini` |
| `OPENAI_IMAGE_MODEL` | 이미지 생성 | `gpt-image-2.5-sunburst` |

- 설정은 함수 호출 시점에 읽고 검증한다. 키가 없어도 앱 import·기본 화면은 동작하고, 이미지 모델이 없어도 텍스트 호출은 동작한다.
- 모델 접근 실패 시 다른 모델로 자동 전환하지 않는다. SDK `max_retries=0`, 공통 코드도 재시도하지 않는다.
- 초기 설정값은 common/config.py에 있으며 프로젝트가 조정 가능한 값이다(공급자 공식 상한 아님).
  토큰·크기·품질 제한은 금액 한도를 보장하지 않는다.
- SDK: openai 3.37.0(Responses API `responses.parse`, Images API `images.generate`), pydantic 2.14.1.

### 텍스트 → 구조화 결과
```python
from pydantic import BaseModel
from common.ai_client import generate_structured
from common.errors import AIError

class Extracted(BaseModel):          # 기능 담당자가 정의. 근거·미확인 필드도 여기서 정의
    product_name: str | None         # 선택 값은 None 허용 타입으로(필드 자체는 모두 필수가 됨)
    evidence: list[str]
    unverified: list[str]

result = generate_structured(
    instructions="기능 담당자가 작성한 지시문",   # 필수, 비어 있지 않은 문자열
    input_text=text,                              # 필수, 비어 있지 않은 문자열
    schema=Extracted,                             # 필수, pydantic.BaseModel 하위 클래스
    max_output_tokens=None,                       # 선택, 생략 시 4096
)
result.data    # Extracted 인스턴스(검증 완료)
result.model   # 공급자가 응답한 모델명(스냅샷명일 수 있음)
result.usage   # TokenUsage(input_tokens, output_tokens, total_tokens) 또는 None
```
- 요청: `model=OPENAI_MODEL`, `instructions`, `input`, `text_format=schema`(SDK가 strict JSON Schema로 변환), `max_output_tokens`, `store=False`. timeout 60초.
- temperature·reasoning 등 미확인 파라미터는 전달하지 않는다.
- 스키마 제약(공식 문서): 루트는 object, 모든 필드 required, `additionalProperties: false`, 최대 5000개 속성·10단계 중첩, `allOf`·`not`·`if/then/else` 등 미지원.
- 거절(refusal)·미완료(status incomplete)·실패·파싱/스키마 검증 실패는 결과로 반환하지 않고 오류로 발생한다.
  잘린 JSON은 SDK parse 단계에서 검증 실패가 나므로 `AI_INCOMPLETE`가 아니라 `AI_OUTPUT_INVALID`로 보고될 수 있다.
- 모델 출력은 사실 검증의 근거가 아니다. 근거 대조·사람 확인은 기능에서 설계한다.
- `store=False`는 Responses API의 응답 저장(application state)을 끄는 설정이다. 공식 데이터 문서상
  남용 모니터링 로그는 기본적으로 최대 30일 보관될 수 있어 **공급자 측 모든 보관을 배제하지 않는다**.

### 텍스트 프롬프트 → 이미지 1장
```python
from common.ai_client import generate_image

image = generate_image(
    prompt="기능 담당자가 구성한 이미지 프롬프트",  # 필수
    size="1024x1024",      # 1024x1024 | 1536x1024 | 1024x1536 (기본 1024x1024)
    quality="low",         # low | medium | high (기본 low)
)
image.data        # PNG bytes(메모리)
image.mime_type   # "image/png"
image.width, image.height
image.model       # 요청에 사용한 모델명(Images API 응답에 모델명 없음)
```
- 요청: `images.generate(model=OPENAI_IMAGE_MODEL, prompt, n=1, size, quality, output_format="png")`. timeout 180초.
  텍스트 모델을 먼저 호출하지 않으며 `store`·텍스트 전용 파라미터를 보내지 않는다.
- 위 크기·품질·PNG·1장은 **이번 첫 버전 범위**다. 모델 전체 기능의 제한이 아니다
  (공식 문서상 Sunburst는 xhigh·max·auto 품질, 사용자 지정 크기, jpeg·webp도 지원).
- 크기·품질·프롬프트가 유효하지 않으면 호출 전에 `AI_INVALID_INPUT`.
- 반환 검증: 결과 1장 존재 → base64 문자열 길이 상한 → base64 엄격 디코딩 → 디코딩 크기 ≤ 16 MiB(`IMAGE_MAX_BYTES`)
  → PNG 서명·IHDR·IEND 확인 → 가로·세로가 요청 크기와 일치. 16 MiB는 디코딩 후 1장 기준 상한이며,
  SDK가 응답 JSON 전체를 먼저 메모리에 읽으므로 네트워크 수신 단계의 메모리 상한은 아니다.
- 이미지·base64·프롬프트를 디스크·DB·로그에 저장하지 않는다. 다운로드·PDF 삽입은 기능 담당자 후속 작업.
- 미구현: 이미지 편집, 참조 이미지, 마스크, 다중 생성, 스트리밍. 어느 탭이 어떤 이미지를 만드는지는 미정.

### 오류 (common/errors.py)
기능 라우트 예시:
```python
from flask import jsonify
from common.errors import AIError

try:
    result = generate_structured(...)
except AIError as err:
    return jsonify({"ok": False, "error": err.to_dict()}), err.http_status
return jsonify({"ok": True, "data": result.data.model_dump()})
```
| 구분 | code | http_status(권장) | retryable |
|---|---|---|---|
| 설정 누락 | `AI_CONFIG_MISSING` | 503 | 아니오 |
| 입력값 오류 | `AI_INVALID_INPUT` | 400 | 아니오 |
| 인증 실패(401) | `AI_AUTH_FAILED` | 502 | 아니오 |
| 권한 없음(403) | `AI_PERMISSION_DENIED` | 502 | 아니오 |
| 모델 사용 불가(404) | `AI_MODEL_UNAVAILABLE` | 502 | 아니오 |
| 호출 제한(429) | `AI_RATE_LIMITED` | 429 | 예 |
| 연결 실패 | `AI_CONNECTION_FAILED` | 502 | 예 |
| 시간 초과 | `AI_TIMEOUT` | 504 | 예 |
| 공급자 서버 오류(5xx·status failed) | `AI_PROVIDER_ERROR` | 502 | 예 |
| 기타 요청 거부(400 등) | `AI_BAD_REQUEST` | 502 | 아니오 |
| 정책상 거절(refusal·content_filter·moderation_blocked) | `AI_REFUSED` | 422 | 아니오 |
| 텍스트 미완료 | `AI_INCOMPLETE` | 502 | 예 |
| 텍스트 파싱·스키마 검증 실패 | `AI_OUTPUT_INVALID` | 502 | 예 |
| 이미지 결과 없음 | `AI_IMAGE_EMPTY` | 502 | 예 |
| 이미지 디코딩 실패 | `AI_IMAGE_DECODE_FAILED` | 502 | 예 |
| 유효하지 않은 이미지(형식·크기·개수·용량) | `AI_IMAGE_INVALID` | 502 | 예 |

- `message`는 고정 안내 문장이다. 예외 원문·키·사용자 입력·모델 응답·이미지 데이터를 담지 않고, 원 예외를 체인하지 않는다.
- 로그에는 오류 code·HTTP 상태·누락된 환경변수 이름만 남긴다.
- `retryable`은 사용자에게 재시도 버튼을 보여 줄지 판단하는 참고값이다. 자동 재시도는 하지 않는다.
- 시간 초과는 공급자 쪽 처리 중단이나 미과금을 보장하지 않는다.

### 후속 작업
- PDF·스캔 PDF·이미지 분석 입력, Files API: 제품소개서에 필요한 후속 작업. 이번 이미지 생성 구현은 PDF 판독 구현이 아니다.
- 업무 결과 품질·비용·소요 시간·응답 모델명·사용량 확인(비용 기준과 승인 후). 실제 호출·반환 형식은 2026-10-25 사용자 실행 결과로 확인됨.
