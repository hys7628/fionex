"""공통 설정. 공통 화면 실행에는 API 키가 필요하지 않습니다.

OpenAI 설정은 import 시점이 아니라 AI 함수를 호출할 때 환경변수에서 읽습니다.
이 모듈은 .env를 직접 로드하지 않습니다. `python app.py`(app.run)·`flask run` 시작 시 Flask가
python-dotenv(requirements.txt)로 .env를 환경변수에 넣습니다. 이미 설정된 OS 환경변수가 우선합니다(README.md).
"""
import os
from pathlib import Path

# 서비스(대시보드)명. 2026-10-24 확정(docs/decisions.md).
SERVICE_NAME = "fionex"

# 공통 글꼴 Pretendard(SIL OFL 1.1). 웹(@font-face, woff2)과 모든 탭 PDF(ReportLab, TrueType)가 같은 폴더를 씁니다.
# 파일 목록·출처·해시: static/fonts/pretendard/README.md
FONT_DIR = Path(__file__).resolve().parent.parent / "static" / "fonts" / "pretendard"
PDF_FONT_FILES = {"regular": FONT_DIR / "Pretendard-Regular.ttf", "bold": FONT_DIR / "Pretendard-Bold.ttf"}
PDF_FONT_NAMES = {"regular": "Pretendard", "bold": "Pretendard-Bold"}

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

# 참조 이미지 기반 이미지 생성(Images API edits, OPENAI_IMAGE_MODEL). 2026-10-25 정은진 추가, 공통 담당 검토 대기.
# 공식 가이드상 입력 이미지는 50MB 미만이며 장수 상한은 명시되지 않음(2026-10-25 조회). 아래는 프로젝트 제한입니다.
IMAGE_REF_MAX_FILES = 5
IMAGE_REF_MAX_BYTES = 10 * 1024 * 1024
IMAGE_REF_TOTAL_MAX_BYTES = 50 * 1024 * 1024

# PDF 입력(텍스트 모델 OPENAI_MODEL 사용). 파일 자체 제한이며 HTTP 요청 전체 제한은 라우트에서 별도로 정합니다.
PDF_MAX_BYTES = 10 * 1024 * 1024
PDF_MAX_PAGES = 20
PDF_TIMEOUT_SECONDS = 120.0
PDF_MAX_RETRIES = 0
PDF_MAX_OUTPUT_TOKENS = 4096
PDF_STORE = False
# input_file.detail(auto/low/high). 공식 안내상 GPT-5.6 미만 모델은 auto가 low로 동작하므로 high를 명시합니다.
PDF_DETAIL = "high"
# 원본 파일명에는 경로·민감정보가 있을 수 있어 공급자에는 고정 이름만 보냅니다.
PDF_PROVIDER_FILENAME = "document.pdf"


def _env(name):
    return os.environ.get(name, "").strip()


def get_openai_api_key():
    return _env(ENV_OPENAI_API_KEY)


def get_text_model():
    return _env(ENV_OPENAI_MODEL)


def get_image_model():
    return _env(ENV_OPENAI_IMAGE_MODEL)
