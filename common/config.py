"""공통 설정. 공통 화면 실행에는 API 키가 필요하지 않습니다.

OpenAI 설정은 import 시점이 아니라 AI 함수를 호출할 때 환경변수에서 읽습니다.
이 모듈은 .env를 직접 로드하지 않습니다. Flask 실행 경로(app.run, flask run)와
python-dotenv 설치 여부에 따라 .env의 값이 환경변수로 로드될 수 있습니다(README.md 실행 안내 참고).
"""
import os

# 서비스(대시보드)명. 2026-10-24 확정(docs/decisions.md).
SERVICE_NAME = "fionex"

# 환경변수 이름. 값은 코드에 고정하지 않습니다.
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_OPENAI_MODEL = "OPENAI_MODEL"              # 텍스트 구조화 결과
ENV_OPENAI_IMAGE_MODEL = "OPENAI_IMAGE_MODEL"  # 이미지 생성

# 프로젝트 초기 설정(2026-10-25). 조정 가능한 값이며 공급자 공식 상한이 아닙니다.
# 토큰·크기·품질 제한은 금액 한도를 보장하지 않습니다.
TEXT_TIMEOUT_SECONDS = 60.0
TEXT_MAX_RETRIES = 0
TEXT_MAX_OUTPUT_TOKENS = 4096
TEXT_STORE = False

IMAGE_TIMEOUT_SECONDS = 180.0
IMAGE_MAX_RETRIES = 0
IMAGE_SIZES = ("1024x1024", "1536x1024", "1024x1536")
IMAGE_QUALITIES = ("low", "medium", "high")
IMAGE_DEFAULT_SIZE = "1024x1024"
IMAGE_DEFAULT_QUALITY = "low"
IMAGE_OUTPUT_FORMAT = "png"
IMAGE_MIME_TYPE = "image/png"
# 디코딩 후 이미지 1장의 메모리 상한. base64 문자열은 디코딩 전에 같은 기준으로 길이를 검사합니다.
IMAGE_MAX_BYTES = 16 * 1024 * 1024


def _env(name):
    return os.environ.get(name, "").strip()


def get_openai_api_key():
    return _env(ENV_OPENAI_API_KEY)


def get_text_model():
    return _env(ENV_OPENAI_MODEL)


def get_image_model():
    return _env(ENV_OPENAI_IMAGE_MODEL)
