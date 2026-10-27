"""제품소개서 AI 표지 배경 생성(최소 범위): 입력 계약, 서비스 프롬프트 조립, 공통 generate_image 호출.

입력은 카탈로그 표시명·제품 설명·분위기 3개뿐입니다. 서버는 저장하지 않으므로(stateless) 이 값이
사용자가 실제로 확인·적용한 스냅샷인지 인증하지 못합니다(형식·길이·문자만 검사).
출력은 글자·로고 없는 세로형 AI 콘셉트 이미지 1장(PNG bytes, 메모리)이며 실제 제품 사진이 아닙니다.
제품 정보·문구·4페이지 구성은 바꾸지 않습니다. 화면 연결·PDF 반영은 아직 없습니다(명세 §28).

공통 generate_image는 프롬프트 문자열 하나만 받으므로, 신뢰된 지시(프롬프트 파일)와 사용자 입력(JSON 참고 데이터 블록)을
문자열 안에서 구획으로 나눕니다. 이것은 프롬프트 주입을 완전히 막는 장치가 아니며, 결과는 사용자가 보고 적용해야 합니다.
이미지 품질·글자 혼입 여부는 지침만으로 보장되지 않습니다. 자동 재시도·결과 저장·입력/이미지 로그는 없습니다.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError

from common.ai_client import generate_image
from common.errors import AIInputError
from features.product_brochure.generation import HANGUL, MAX_DISPLAY_NAME_CHARS, MAX_VALUE_CHARS

PROMPT_VERSION = "brochure_cover_image_v1"
_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / (PROMPT_VERSION + ".md")

MOODS = ("minimal", "premium", "soft_texture")
MOOD_LABELS = {"minimal": "미니멀", "premium": "프리미엄", "soft_texture": "부드러운 소재감"}
IMAGE_SIZE = "1024x1536"     # 세로형(공통 config.IMAGE_SIZES 중 하나)
IMAGE_QUALITY = "medium"     # 공통 config.IMAGE_QUALITIES 중 하나. 모델은 공통 OPENAI_IMAGE_MODEL
MAX_REQUEST_BYTES = 16 * 1024
MAX_DESCRIPTION_CHARS = MAX_VALUE_CHARS["description"]  # 생성 입력 한도 재사용(1500)

_CONTROL_ALL = re.compile("[\u0000-\u001f\u007f]")
_CONTROL_TEXT = re.compile("[\u0000-\u0008\u000b-\u001f\u007f]")  # 설명은 줄바꿈·탭만 허용


# ---------- 입력 스키마(엄격: 알 수 없는 필드·형 변환 거부) ----------
class CoverImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    display_name: StrictStr
    description: StrictStr
    mood: Literal["minimal", "premium", "soft_texture"]


# ---------- 기능 전용 오류(공통 오류 계약) ----------
class CoverImageInvalidJsonError(AIInputError):
    code = "COVER_IMAGE_INVALID_JSON"
    message = "JSON 형식(application/json)의 요청 본문이 필요합니다."


class CoverImageRequestTooLargeError(AIInputError):
    code = "COVER_IMAGE_REQUEST_TOO_LARGE"
    message = "요청 크기가 허용 범위를 넘습니다."
    http_status = 413


class CoverImageInvalidInputError(AIInputError):
    code = "COVER_IMAGE_INVALID_INPUT"
    message = "표지 배경 생성 요청 형식이 올바르지 않습니다."


@lru_cache(maxsize=1)
def load_template():
    return _PROMPT_PATH.read_text(encoding="utf-8")


def parse_request(payload):
    """JSON 객체 → (표시명, 설명, 분위기). API 호출 전에 형식·빈 값·길이·문자를 검사합니다(자르지 않음)."""
    if not isinstance(payload, dict):
        raise CoverImageInvalidJsonError()
    try:
        req = CoverImageRequest.model_validate(payload)
    except ValidationError:
        raise CoverImageInvalidInputError() from None  # 오류 위치에 사용자 문자열을 넣지 않음
    name = req.display_name.strip()
    description = req.description.strip()
    if not name or not description:
        raise CoverImageInvalidInputError(message="카탈로그 표시명과 제품 설명을 입력하세요.")
    # 표시명: 생성 기능과 같은 기준(80자 이하, 한글·제어 문자 불가)
    if len(name) > MAX_DISPLAY_NAME_CHARS or HANGUL.search(name) or _CONTROL_ALL.search(name):
        raise CoverImageInvalidInputError(
            message=f"카탈로그 표시명 형식이 올바르지 않습니다(한글·제어 문자 불가, {MAX_DISPLAY_NAME_CHARS}자 이하).")
    # 설명: 생성 입력과 같은 길이 한도. 한국어 허용, 줄바꿈·탭 외 제어 문자 불가
    if len(description) > MAX_DESCRIPTION_CHARS or _CONTROL_TEXT.search(description):
        raise CoverImageInvalidInputError(
            message=f"제품 설명 형식이 올바르지 않습니다({MAX_DESCRIPTION_CHARS}자 이하, 쓸 수 없는 문자 불가).")
    return name, description, req.mood


def build_prompt(name, description, mood):
    """신뢰된 지시(템플릿) + 분위기 키 + 참고 데이터(JSON). 사용자 값은 JSON 문자열로만 넣어 지시 구역과 분리합니다."""
    data = json.dumps({"display_name": name, "product_description": description}, ensure_ascii=False, indent=2)
    return load_template().replace("{{MOOD}}", mood).replace("{{PRODUCT_DATA}}", data)


def generate_cover(payload):
    """검증된 입력 → 공통 generate_image(1024x1536, medium, n=1, 공통 재시도 0회) → GeneratedImage.
    결과를 저장·로깅하지 않습니다. 기능 쪽 추가 재시도 없음."""
    name, description, mood = parse_request(payload)
    return generate_image(prompt=build_prompt(name, description, mood), size=IMAGE_SIZE, quality=IMAGE_QUALITY)
