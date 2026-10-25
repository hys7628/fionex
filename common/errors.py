"""공통 AI 오류. 기능 라우트가 docs/data_contracts.md의 실패 응답으로 변환합니다.

메시지는 사용자에게 보여도 되는 고정 문장입니다. 공급자 예외 원문·키·사용자 입력·
모델 응답·이미지 데이터를 담지 않습니다. Flask 응답은 여기서 만들지 않습니다.

    try:
        result = generate_structured(...)
    except AIError as err:
        return jsonify({"ok": False, "error": err.to_dict()}), err.http_status
"""


class AIError(Exception):
    """공통 AI 오류의 기반 클래스. code는 기능 코드가 분기에 사용하는 고정 문자열입니다."""

    code = "AI_UNKNOWN_ERROR"
    message = "AI 처리 중 알 수 없는 오류가 발생했습니다."
    http_status = 500
    retryable = False

    def __init__(self, *, code=None, message=None, http_status=None, retryable=None, status_code=None):
        if code is not None:
            self.code = code
        if message is not None:
            self.message = message
        if http_status is not None:
            self.http_status = http_status
        if retryable is not None:
            self.retryable = retryable
        # 공급자가 돌려준 HTTP 상태(진단용). 공급자 응답 본문은 보관하지 않습니다.
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self):
        """{"code", "message"} 형태. 실패 응답의 error 값으로 사용합니다."""
        return {"code": self.code, "message": self.message}


# 설정 누락·입력값 오류: API를 호출하기 전에 발생합니다.
class AIConfigError(AIError):
    code = "AI_CONFIG_MISSING"
    message = "AI 기능 설정이 준비되지 않았습니다. 관리자에게 문의하세요."
    http_status = 503


class AIInputError(AIError):
    code = "AI_INVALID_INPUT"
    message = "AI 요청 입력값이 올바르지 않습니다."
    http_status = 400


# 인증·권한·모델 접근
class AIAuthError(AIError):
    code = "AI_AUTH_FAILED"
    message = "AI 서비스 인증에 실패했습니다. 관리자에게 문의하세요."
    http_status = 502


class AIPermissionError(AIError):
    code = "AI_PERMISSION_DENIED"
    message = "AI 서비스 사용 권한이 없습니다. 관리자에게 문의하세요."
    http_status = 502


class AIModelUnavailableError(AIError):
    code = "AI_MODEL_UNAVAILABLE"
    message = "설정된 AI 모델을 사용할 수 없습니다. 관리자에게 문의하세요."
    http_status = 502


# 호출 제한
class AIRateLimitError(AIError):
    code = "AI_RATE_LIMITED"
    message = "AI 호출 한도에 도달했습니다. 잠시 후 다시 시도하세요."
    http_status = 429
    retryable = True


# 연결 실패·시간 초과·공급자 서버 오류
class AIConnectionError(AIError):
    code = "AI_CONNECTION_FAILED"
    message = "AI 서비스에 연결하지 못했습니다. 잠시 후 다시 시도하세요."
    http_status = 502
    retryable = True


class AITimeoutError(AIError):
    code = "AI_TIMEOUT"
    message = "AI 응답 시간이 초과되었습니다. 잠시 후 다시 시도하세요."
    http_status = 504
    retryable = True


class AIProviderError(AIError):
    code = "AI_PROVIDER_ERROR"
    message = "AI 서비스에서 오류가 발생했습니다. 잠시 후 다시 시도하세요."
    http_status = 502
    retryable = True


class AIBadRequestError(AIError):
    """공급자가 요청 형식·파라미터를 거부한 경우(정책 거절 제외)."""

    code = "AI_BAD_REQUEST"
    message = "AI 서비스가 요청을 처리하지 못했습니다. 관리자에게 문의하세요."
    http_status = 502


# 정책상 거절
class AIRefusalError(AIError):
    code = "AI_REFUSED"
    message = "AI가 요청을 처리하지 않았습니다. 입력 내용을 확인한 뒤 다시 시도하세요."
    http_status = 422


# 텍스트 결과
class AIIncompleteError(AIError):
    code = "AI_INCOMPLETE"
    message = "AI 응답이 완료되지 않았습니다. 입력을 줄이거나 다시 시도하세요."
    http_status = 502
    retryable = True


class AIOutputInvalidError(AIError):
    code = "AI_OUTPUT_INVALID"
    message = "AI 응답을 결과 형식으로 해석하지 못했습니다. 다시 시도하세요."
    http_status = 502
    retryable = True


# 이미지 결과
class AIImageEmptyError(AIError):
    code = "AI_IMAGE_EMPTY"
    message = "AI가 이미지를 반환하지 않았습니다. 다시 시도하세요."
    http_status = 502
    retryable = True


class AIImageDecodeError(AIError):
    code = "AI_IMAGE_DECODE_FAILED"
    message = "AI가 반환한 이미지 데이터를 읽지 못했습니다. 다시 시도하세요."
    http_status = 502
    retryable = True


class AIImageInvalidError(AIError):
    code = "AI_IMAGE_INVALID"
    message = "AI가 반환한 이미지가 요청 형식과 맞지 않습니다. 다시 시도하세요."
    http_status = 502
    retryable = True
