"""공통 OpenAI 연결. 서버에서만 호출합니다.

- generate_structured: 텍스트 입력 → 기능 담당자 스키마(Pydantic)로 검증된 결과 (Responses API)
- generate_structured_from_pdf: PDF 1개(+선택 부가 텍스트) → 스키마 검증 결과 (Responses API, input_file)
- generate_image: 텍스트 프롬프트 → PNG 이미지 1장 bytes (Images API)

업무 프롬프트·결과 필드·판단 로직은 각 기능에서 정의합니다. 이 모듈은 Flask 응답을 만들지 않고
common.errors의 AIError를 발생시킵니다. 사용법: docs/data_contracts.md

클라이언트 생성과 설정 검증은 함수 호출 시점에 합니다. 키가 없어도 import는 실패하지 않습니다.
SDK 재시도는 0회이며 이 모듈도 재시도·다른 모델 자동 전환을 하지 않습니다.
프롬프트·입력·모델 응답·이미지 데이터를 디스크·DB·로그에 남기지 않습니다.
"""
import base64
import binascii
import logging
import struct
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

import openai
import pydantic
from openai import OpenAI

from common import config
from common.pdf_utils import PdfInfo, inspect_pdf
from common.errors import (
    AIAuthError,
    AIBadRequestError,
    AIConfigError,
    AIConnectionError,
    AIError,
    AIImageDecodeError,
    AIImageEmptyError,
    AIImageInvalidError,
    AIIncompleteError,
    AIInputError,
    AIModelUnavailableError,
    AIOutputInvalidError,
    AIPermissionError,
    AIProviderError,
    AIRateLimitError,
    AIRefusalError,
    AITimeoutError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=pydantic.BaseModel)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_IEND = b"\x00\x00\x00\x00IEND\xaeB`\x82"
# base64 4글자 = 3바이트. 디코딩 전에 문자열 길이로 메모리 상한을 먼저 검사합니다.
_IMAGE_MAX_B64_CHARS = (config.IMAGE_MAX_BYTES + 2) // 3 * 4


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class StructuredResult(Generic[T]):
    """data: schema 인스턴스(검증 완료). model: 공급자가 응답한 모델명. usage: 없으면 None."""

    data: T
    model: str
    usage: Optional[TokenUsage]


@dataclass(frozen=True)
class PdfStructuredResult(StructuredResult[T]):
    """StructuredResult + pdf: 요청 전에 검사한 PdfInfo(size_bytes, page_count)."""

    pdf: PdfInfo


@dataclass(frozen=True)
class GeneratedImage:
    """data: PNG bytes(메모리). model: 요청에 사용한 모델명(Images API 응답에는 모델명이 없음)."""

    data: bytes
    mime_type: str
    width: int
    height: int
    model: str

    def __repr__(self):
        # 이미지 bytes가 로그·디버그 출력에 찍히지 않도록 크기만 표시합니다.
        return (f"GeneratedImage(mime_type={self.mime_type!r}, width={self.width}, "
                f"height={self.height}, model={self.model!r}, bytes={len(self.data)})")


def _create_client(api_key, timeout, max_retries):
    """OpenAI 클라이언트 생성. 테스트는 이 함수를 교체해 외부 요청을 막습니다."""
    return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)


def _require_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise AIInputError(message=f"AI 요청의 {field} 값이 비어 있거나 문자열이 아닙니다.")


def _require_settings(model_env, model):
    """API 키와 모델 설정 확인. 값은 메시지·로그에 넣지 않고 환경변수 이름만 기록합니다."""
    missing = []
    api_key = config.get_openai_api_key()
    if not api_key:
        missing.append(config.ENV_OPENAI_API_KEY)
    if not model:
        missing.append(model_env)
    if missing:
        logger.warning("AI 설정 누락: %s", ", ".join(missing))
        raise AIConfigError()
    return api_key


def _translate_sdk_error(exc):
    """SDK 예외 → 공통 AIError. 공급자 메시지·요청 본문은 옮기지 않습니다."""
    status = getattr(exc, "status_code", None)
    if isinstance(exc, openai.APITimeoutError):  # APIConnectionError의 하위 클래스라 먼저 검사
        return AITimeoutError()
    if isinstance(exc, openai.APIConnectionError):
        return AIConnectionError()
    if isinstance(exc, openai.AuthenticationError):
        return AIAuthError(status_code=status)
    if isinstance(exc, openai.PermissionDeniedError):
        return AIPermissionError(status_code=status)
    if isinstance(exc, openai.NotFoundError):
        return AIModelUnavailableError(status_code=status)
    if isinstance(exc, openai.RateLimitError):
        return AIRateLimitError(status_code=status)
    if isinstance(exc, openai.APIStatusError):
        # 이미지 정책 차단은 400 + code "moderation_blocked"(공식 이미지 생성 가이드)
        if getattr(exc, "code", None) == "moderation_blocked":
            return AIRefusalError(status_code=status)
        if status is not None and status >= 500:
            return AIProviderError(status_code=status)
        return AIBadRequestError(status_code=status)
    return AIError(status_code=status)


def _call(api_key, timeout, max_retries, kind, request):
    """클라이언트를 만들어 request(client)를 1회 실행하고 SDK 예외를 공통 오류로 바꿉니다."""
    try:
        with _create_client(api_key, timeout, max_retries) as client:
            return request(client)
    except AIError:
        raise
    except openai.OpenAIError as exc:
        err = _translate_sdk_error(exc)
    # 잘린 JSON 등 SDK가 parse 단계에서 스키마 검증에 실패한 경우
    except pydantic.ValidationError:
        err = AIOutputInvalidError()
    # 원 예외는 체인하지 않습니다(from None). 트레이스백에 공급자 메시지·입력이 남지 않게 합니다.
    logger.warning("AI %s 호출 실패: code=%s status=%s", kind, err.code, err.status_code)
    raise err from None


def _usage_of(response):
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return TokenUsage(usage.input_tokens, usage.output_tokens, usage.total_tokens)


def _has_refusal(response):
    for item in response.output or []:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", None) or []:
            if getattr(content, "type", None) == "refusal":
                return True
    return False


def _check_structured_args(instructions, schema, max_output_tokens, default_tokens):
    _require_text(instructions, "instructions")
    if not (isinstance(schema, type) and issubclass(schema, pydantic.BaseModel)):
        raise AIInputError(message="AI 결과 스키마는 Pydantic BaseModel 하위 클래스여야 합니다.")
    if max_output_tokens is None:
        max_output_tokens = default_tokens
    if isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
        raise AIInputError(message="max_output_tokens는 1 이상의 정수여야 합니다.")
    return max_output_tokens


def generate_structured(*, instructions, input_text, schema, max_output_tokens=None):
    """텍스트를 schema(Pydantic BaseModel 하위 클래스) 결과로 받습니다.

    instructions: 기능 담당자가 작성한 지시문. input_text: 처리할 텍스트.
    max_output_tokens: 생략하면 config.TEXT_MAX_OUTPUT_TOKENS.
    반환: StructuredResult(data=schema 인스턴스, model, usage)
    오류: AIError 하위 클래스(거절·미완료·파싱 실패는 정상 결과로 반환하지 않음)
    """
    _require_text(instructions, "instructions")
    _require_text(input_text, "input_text")
    max_output_tokens = _check_structured_args(instructions, schema, max_output_tokens, config.TEXT_MAX_OUTPUT_TOKENS)

    model = config.get_text_model()
    api_key = _require_settings(config.ENV_OPENAI_MODEL, model)

    response = _call(
        api_key, config.TEXT_TIMEOUT_SECONDS, config.TEXT_MAX_RETRIES, "text",
        lambda client: client.responses.parse(
            model=model,
            instructions=instructions,
            input=input_text,
            text_format=schema,
            max_output_tokens=max_output_tokens,
            store=config.TEXT_STORE,
        ),
    )
    return _structured_result(response, schema, model, "text")


def generate_structured_from_pdf(*, instructions, pdf_bytes, schema, input_text=None, max_output_tokens=None):
    """PDF 1개를 schema(Pydantic BaseModel 하위 클래스) 결과로 받습니다. 모델은 OPENAI_MODEL.

    instructions: 기능 담당자가 작성한 신뢰된 지시문. PDF와 input_text는 입력 데이터로만 전달합니다.
    pdf_bytes: PDF 파일 bytes. common.pdf_utils.inspect_pdf 검사를 통과해야 요청을 보냅니다.
    input_text: 선택. PDF와 함께 보낼 부가 텍스트(입력 데이터). None이면 보내지 않습니다.
    max_output_tokens: 생략하면 config.PDF_MAX_OUTPUT_TOKENS.
    반환: PdfStructuredResult(data, model, usage, pdf=PdfInfo(size_bytes, page_count))
    오류: AIError 하위 클래스. PDF 검사 실패는 PdfValidationError(PDF_*)이며 API를 호출하지 않습니다.

    PDF는 base64 data URL의 input_file로 요청에 직접 포함합니다(Files API·URL 미사용).
    공급자에는 원본 파일명 대신 config.PDF_PROVIDER_FILENAME을 보냅니다.
    """
    max_output_tokens = _check_structured_args(instructions, schema, max_output_tokens, config.PDF_MAX_OUTPUT_TOKENS)
    if input_text is not None:
        _require_text(input_text, "input_text")
    try:
        pdf_info = inspect_pdf(pdf_bytes)
    except AIError as err:
        logger.warning("AI pdf 입력 거부: code=%s", err.code)
        raise

    model = config.get_text_model()
    api_key = _require_settings(config.ENV_OPENAI_MODEL, model)

    content = [{
        "type": "input_file",
        "filename": config.PDF_PROVIDER_FILENAME,
        "file_data": "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode("ascii"),
        "detail": config.PDF_DETAIL,
    }]
    if input_text is not None:
        content.append({"type": "input_text", "text": input_text})

    response = _call(
        api_key, config.PDF_TIMEOUT_SECONDS, config.PDF_MAX_RETRIES, "pdf",
        lambda client: client.responses.parse(
            model=model,
            instructions=instructions,
            input=[{"role": "user", "content": content}],
            text_format=schema,
            max_output_tokens=max_output_tokens,
            store=config.PDF_STORE,
        ),
    )
    result = _structured_result(response, schema, model, "pdf")
    return PdfStructuredResult(data=result.data, model=result.model, usage=result.usage, pdf=pdf_info)


def _structured_result(response, schema, model, kind):
    """Responses API 결과 검증. 거절·미완료·실패·스키마 불일치는 오류로 발생합니다."""
    status = getattr(response, "status", None)
    err = None
    if status == "incomplete":
        details = getattr(response, "incomplete_details", None)
        reason = getattr(details, "reason", None)
        err = AIRefusalError() if reason == "content_filter" else AIIncompleteError()
    elif status == "failed":
        err = AIProviderError()
    elif status != "completed":
        err = AIIncompleteError()
    elif _has_refusal(response):
        err = AIRefusalError()
    else:
        parsed = response.output_parsed
        if not isinstance(parsed, schema):
            err = AIOutputInvalidError()
    if err is not None:
        logger.warning("AI %s 결과 거부: code=%s", kind, err.code)
        raise err

    return StructuredResult(data=parsed, model=getattr(response, "model", "") or model, usage=_usage_of(response))


def _png_size(data):
    """PNG 서명·IHDR·IEND를 확인하고 (width, height)를 돌려줍니다. 형식이 아니면 None."""
    if len(data) < 33 + len(_PNG_IEND) or not data.startswith(_PNG_SIGNATURE):
        return None
    length, chunk_type = struct.unpack(">I4s", data[8:16])
    if chunk_type != b"IHDR" or length != 13:
        return None
    if not data.endswith(_PNG_IEND):  # 잘린 데이터
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def generate_image(*, prompt, size=config.IMAGE_DEFAULT_SIZE, quality=config.IMAGE_DEFAULT_QUALITY):
    """텍스트 프롬프트로 PNG 이미지 1장을 생성합니다. 텍스트 모델을 먼저 호출하지 않습니다.

    size: config.IMAGE_SIZES 중 하나. quality: config.IMAGE_QUALITIES 중 하나.
    반환: GeneratedImage(data=PNG bytes, mime_type="image/png", width, height, model)
    오류: AIError 하위 클래스. 입력·설정 오류는 API 호출 전에 발생합니다.
    """
    _require_text(prompt, "prompt")
    if size not in config.IMAGE_SIZES:
        raise AIInputError(message="지원하지 않는 이미지 크기입니다.")
    if quality not in config.IMAGE_QUALITIES:
        raise AIInputError(message="지원하지 않는 이미지 품질입니다.")

    model = config.get_image_model()
    api_key = _require_settings(config.ENV_OPENAI_IMAGE_MODEL, model)

    result = _call(
        api_key, config.IMAGE_TIMEOUT_SECONDS, config.IMAGE_MAX_RETRIES, "image",
        lambda client: client.images.generate(
            model=model,
            prompt=prompt,
            n=1,
            size=size,
            quality=quality,
            output_format=config.IMAGE_OUTPUT_FORMAT,
        ),
    )

    try:
        data = _decode_image(result, size)
    except AIError as err:
        logger.warning("AI image 결과 거부: code=%s", err.code)
        raise
    width, height = data[1]
    return GeneratedImage(data=data[0], mime_type=config.IMAGE_MIME_TYPE, width=width, height=height, model=model)


def _decode_image(result, size):
    items = getattr(result, "data", None) or []
    if not items:
        raise AIImageEmptyError()
    if len(items) != 1:
        raise AIImageInvalidError()
    b64 = getattr(items[0], "b64_json", None)
    if not isinstance(b64, str) or not b64.strip():
        raise AIImageEmptyError()
    if len(b64) > _IMAGE_MAX_B64_CHARS:
        raise AIImageInvalidError()
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise AIImageDecodeError() from None
    if not raw:
        raise AIImageEmptyError()
    if len(raw) > config.IMAGE_MAX_BYTES:
        raise AIImageInvalidError()
    dims = _png_size(raw)
    expected = tuple(int(v) for v in size.split("x"))
    if dims is None or dims != expected:
        raise AIImageInvalidError()
    return raw, dims
