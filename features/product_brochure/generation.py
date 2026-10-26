"""제품소개서 카탈로그 문구 생성: 입력·출력 스키마, 서비스 프롬프트, 공통 generate_structured 호출, 서버 검증.

입력은 사용자가 확인·수정 후 적용한 8개 항목입니다. 서버는 저장하지 않으므로 이전 분석 결과와 대조할 수 없고,
요청에 담긴 confirmed·virtual·origin은 형식만 검증해 보존합니다(서버가 사용자 확인 이력을 인증하지 않음).
출력은 4페이지 템플릿에 넣을 pt-BR 문구 초안이며, 번역 의미·사실 정확성은 사용자 검토 대상입니다.

표지 제품명은 원본 product_name이 아니라 사용자가 확인한 카탈로그 표시명(display_name)을 그대로 씁니다(명세 §23).
문서에 들어갈 생성 문자열에 한글이 남으면 실패로 처리합니다. 한글이 없다는 사실이 pt-BR 품질을 보장하지는 않습니다.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, ValidationError

from common.ai_client import generate_structured
from common.errors import AIInputError, AIOutputInvalidError
from features.product_brochure.service import FIELD_KEYS, FIELD_LABELS, FieldKey

# v1: 첫 버전(실제 실행 기록 SPE-2026_10_25-02, 파일 보존). v2: 표시명·한국어 금지·샘플 표현·표지/소개 역할 구분
PROMPT_VERSION = "brochure_generate_v2"
_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / (PROMPT_VERSION + ".md")

REQUIRED_KEYS = ("product_name", "description")
DETAIL_KEYS = ("yarn_spec", "certification", "carbon_reduction")  # 3쪽
SUPPLY_KEYS = ("moq", "sample", "lead_time")                        # 4쪽
ORIGINS = ("extracted", "user_modified", "user_added")

# 입력 한도(구현 한도, 명세 §21). 넘으면 자르지 않고 거부합니다.
MAX_REQUEST_BYTES = 32 * 1024
MAX_VALUE_CHARS = {
    "product_name": 120,
    "description": 1500,
    "yarn_spec": 300, "certification": 300, "carbon_reduction": 300,
    "moq": 200, "sample": 200, "lead_time": 200,
}
MAX_DISPLAY_NAME_CHARS = 80

# 한글 음절·자모(호환 자모·확장 A/B·반각 포함). 카탈로그 표시명과 문서 문자열 검사에 사용
HANGUL = re.compile("[ᄀ-ᇿ㄰-㆏ꥠ-꥿가-힣ힰ-퟿ﾠ-ￜ]")
_CONTROL = re.compile("[\u0000-\u001f\u007f]")
_WORD = re.compile(r"[^\W\d_]{4,}")
REPEAT_RATIO = 0.8  # 표지 소개 단어(4자 이상, 표시명 제외)의 80% 이상이 문단에 다시 나오면 검토 표시

# 출력 상한(프롬프트와 같은 값). 넘으면 실패로 처리합니다(잘라서 성공 처리하지 않음).
MAX_TAGLINE_CHARS = 140
MAX_INTRO_PARAGRAPHS = 2
MAX_PARAGRAPH_CHARS = 600
MAX_LABEL_CHARS = 40
MAX_DETAIL_VALUE_CHARS = 300
MAX_SUPPLY_VALUE_CHARS = 200

# 서버 고정 안내(AI가 제거하거나 바꾸지 못함)
NOTICE_UNOFFICIAL = "Material demonstrativo — não é um catálogo oficial."
NOTICE_FICTITIOUS = "Condições fictícias para demonstração."
NOTICE_FICTITIOUS_CONTENT = "Inclui informações fictícias para demonstração."
EMPTY_DETAILS = "Informações técnicas a confirmar."
EMPTY_SUPPLY = "Condições de fornecimento a confirmar."

# 사용자 검토용 표시(자동 거부 아님). 근거 없는 평가 표현일 수 있는 pt-BR 어휘
_CLAIM_TERMS = re.compile(
    r"sustent[aá]ve|sustentabilidade|ecol[oó]gic|eco-?friendly|amig[aá]vel ao meio ambiente|"
    r"alt[oa] (desempenho|performance)|certificad|neutr[oa] em carbono|pegada de carbono|biodegrad|garantid",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


# ---------- 입력 스키마(엄격: 알 수 없는 필드·느슨한 형 변환 거부) ----------
class InputField(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    key: FieldKey
    value: StrictStr
    confirmed: StrictBool
    virtual: StrictBool
    origin: Literal["extracted", "user_modified", "user_added"]


class DisplayName(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: StrictStr
    confirmed: StrictBool


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    fields: List[InputField]
    display_name: DisplayName


# ---------- AI 출력 스키마(Structured Outputs) ----------
class CopyText(BaseModel):
    text: str
    source_keys: List[FieldKey]


class InfoItem(BaseModel):
    key: FieldKey
    label: str
    value: str


class CatalogCopy(BaseModel):
    tagline: CopyText
    intro_paragraphs: List[CopyText]
    details: List[InfoItem]
    supply: List[InfoItem]


# ---------- 기능 전용 오류(공통 오류 계약) ----------
class GenerateInvalidJsonError(AIInputError):
    code = "GENERATE_INVALID_JSON"
    message = "JSON 형식(application/json)의 요청 본문이 필요합니다."


class GenerateRequestTooLargeError(AIInputError):
    code = "GENERATE_REQUEST_TOO_LARGE"
    message = "요청 크기가 허용 범위를 넘습니다."
    http_status = 413


class GenerateInvalidInputError(AIInputError):
    code = "GENERATE_INVALID_INPUT"
    message = "입력 형식이 올바르지 않습니다."


class GenerateDuplicateKeyError(AIInputError):
    code = "GENERATE_DUPLICATE_KEY"
    message = "같은 항목(key)이 여러 번 포함되어 있습니다."


class GenerateMissingKeyError(AIInputError):
    code = "GENERATE_MISSING_KEY"
    message = "8개 항목이 모두 포함되어야 합니다."


class GenerateFieldTooLongError(AIInputError):
    code = "GENERATE_FIELD_TOO_LONG"
    message = "항목 값이 허용 길이를 넘습니다."


class GenerateRequiredMissingError(AIInputError):
    code = "GENERATE_REQUIRED_MISSING"
    message = "제품명과 제품 설명을 입력하고 사용자 확인한 뒤 생성할 수 있습니다."


class GenerateDisplayNameRequiredError(AIInputError):
    code = "GENERATE_DISPLAY_NAME_REQUIRED"
    message = "카탈로그 표시명을 입력하고 확인한 뒤 생성할 수 있습니다."


class GenerateDisplayNameInvalidError(AIInputError):
    code = "GENERATE_DISPLAY_NAME_INVALID"
    message = "카탈로그 표시명 형식이 올바르지 않습니다."


class GenerateOutputInvalidError(AIOutputInvalidError):
    code = "GENERATE_OUTPUT_INVALID"
    message = "생성된 문구가 형식·범위 검증을 통과하지 못했습니다. 다시 시도하세요."


class GenerateOutputLanguageError(AIOutputInvalidError):
    code = "GENERATE_OUTPUT_LANGUAGE"
    message = "생성된 카탈로그 문구에 한국어가 남아 있어 결과를 표시하지 않았습니다. 다시 시도하세요."


@lru_cache(maxsize=1)
def load_instructions():
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _safe_loc(loc):
    """오류 위치에서 클라이언트가 보낸 임의 문자열(알 수 없는 필드명 등)을 제외합니다."""
    known = {"fields", "key", "value", "confirmed", "virtual", "origin", "display_name"}
    return ".".join(str(p) if isinstance(p, int) or p in known else "?" for p in loc)


# ---------- 입력 검증 ----------
def parse_request(payload):
    """JSON 객체 → {key: InputField}. 형식·key·길이·필수 항목을 검사합니다(AI 호출 전)."""
    if not isinstance(payload, dict):
        raise GenerateInvalidJsonError()
    try:
        req = GenerateRequest.model_validate(payload)
    except ValidationError as exc:
        locs = sorted({_safe_loc(e["loc"]) for e in exc.errors()})[:3]
        raise GenerateInvalidInputError(message="입력 형식이 올바르지 않습니다: " + ", ".join(locs)) from None
    by_key = {}
    for f in req.fields:
        if f.key in by_key:
            raise GenerateDuplicateKeyError(message=f"같은 항목(key)이 여러 번 포함되어 있습니다: {f.key}")
        by_key[f.key] = f
    missing = [k for k in FIELD_KEYS if k not in by_key]
    if missing:
        raise GenerateMissingKeyError(message="8개 항목이 모두 포함되어야 합니다. 누락: " + ", ".join(missing))
    for k, f in by_key.items():
        if len(f.value) > MAX_VALUE_CHARS[k]:
            raise GenerateFieldTooLongError(message=f"{k} 값이 {MAX_VALUE_CHARS[k]}자를 넘습니다.")
    for k in REQUIRED_KEYS:
        if not by_key[k].value.strip() or by_key[k].confirmed is not True:
            raise GenerateRequiredMissingError()
    return by_key, check_display_name(req.display_name)


def check_display_name(display):
    """카탈로그 표시명: 비어 있지 않고 확인됨, 80자 이하, 한글·제어 문자 없음. 악센트·숫자·일반 기호는 허용."""
    value = display.value.strip()
    if not value or display.confirmed is not True:
        raise GenerateDisplayNameRequiredError()
    if len(value) > MAX_DISPLAY_NAME_CHARS:
        raise GenerateDisplayNameInvalidError(message=f"카탈로그 표시명이 {MAX_DISPLAY_NAME_CHARS}자를 넘습니다.")
    if HANGUL.search(value):
        raise GenerateDisplayNameInvalidError(message="카탈로그 표시명에 한글을 쓸 수 없습니다. 원문의 라틴 문자 표기를 입력하세요.")
    if _CONTROL.search(value):
        raise GenerateDisplayNameInvalidError(message="카탈로그 표시명에 쓸 수 없는 문자가 있습니다.")
    return value


def select_inputs(by_key):
    """사용할 항목(확인됨·값 있음)과 제외 목록. 미확인·빈 선택 항목은 모델에 보내지 않습니다."""
    used, excluded = [], []
    for k in FIELD_KEYS:
        f = by_key[k]
        if not f.value.strip():
            excluded.append({"key": k, "reason": "empty"})
        elif not f.confirmed:
            excluded.append({"key": k, "reason": "unconfirmed"})
        else:
            used.append(k)
    return used, excluded


def build_model_input(by_key, used, display_name):
    """모델 입력(데이터). 확인·가상·출처 메타데이터와 제외 항목은 보내지 않습니다.
    product_name은 원본(한국어가 섞일 수 있음) 대신 사용자가 확인한 카탈로그 표시명을 보냅니다."""
    def value(k):
        return display_name if k == "product_name" else by_key[k].value.strip()
    return json.dumps({
        "display_name": display_name,
        "fields": [{"key": k, "label_ko": FIELD_LABELS[k], "value": value(k)} for k in used],
        "details_keys": [k for k in DETAIL_KEYS if k in used],
        "supply_keys": [k for k in SUPPLY_KEYS if k in used],
    }, ensure_ascii=False)


# ---------- 출력 검증과 서버 통제 ----------
def _digits(text):
    return {re.sub(r"\D", "", n) for n in _NUMBER.findall(text)}


def _text(value, limit):
    text = value.strip()
    if not text or len(text) > limit:
        raise GenerateOutputInvalidError()
    return text


def _meta(by_key, keys):
    return {
        "virtual": any(by_key[k].virtual for k in keys),
        "origins": {k: by_key[k].origin for k in keys},
    }


def _copy(item, by_key, used, limit):
    text = _text(item.text, limit)
    keys = list(dict.fromkeys(item.source_keys))
    if not keys or any(k not in used for k in keys):
        raise GenerateOutputInvalidError()
    used_digits = set().union(*(_digits(by_key[k].value) for k in used))
    flags = []
    if _digits(text) - used_digits:
        flags.append("new_number")       # 입력에 없는 수치
    if _CLAIM_TERMS.search(text):
        flags.append("claim_term")       # 근거 확인이 필요한 평가 표현
    meta = _meta(by_key, keys)
    out = {"text": text, "source_keys": keys, "virtual": meta["virtual"], "origins": meta["origins"],
           "review_flags": flags}
    if meta["virtual"]:
        out["fictitious_notice"] = NOTICE_FICTITIOUS_CONTENT
    return out


def _items(items, expected_keys, by_key, value_limit, empty_message):
    seen = [i.key for i in items]
    if sorted(seen) != sorted(expected_keys) or len(set(seen)) != len(seen):
        raise GenerateOutputInvalidError()  # 미제공 항목 추가·중복·누락·다른 페이지 항목
    order = {k: n for n, k in enumerate(expected_keys)}
    out = []
    for item in sorted(items, key=lambda i: order[i.key]):
        source = by_key[item.key]
        value = _text(item.value, value_limit)
        flags = []
        if _digits(source.value) - _digits(value):
            flags.append("number_not_preserved")  # 입력 수치가 출력에 보이지 않음(정확성 보장 아님)
        if _CLAIM_TERMS.search(value):
            flags.append("claim_term")
        entry = {"key": item.key, "label": _text(item.label, MAX_LABEL_CHARS), "value": value,
                 "source_keys": [item.key], "virtual": source.virtual, "origin": source.origin,
                 "review_flags": flags}
        if source.virtual:
            entry["fictitious_notice"] = NOTICE_FICTITIOUS
        out.append(entry)
    return {"items": out, "empty": not out, "empty_message": None if out else empty_message}


def check_output_language(copy):
    """문서에 들어갈 생성 문자열의 한글 잔존 검사. 위치만 모아 실패로 처리합니다(원문을 지우거나 통과시키지 않음).
    모델명·메타데이터·한국어 UI 안내는 검사 대상이 아닙니다."""
    places = []
    if HANGUL.search(copy.tagline.text):
        places.append("1쪽 소개 문구")
    for n, p in enumerate(copy.intro_paragraphs, start=1):
        if HANGUL.search(p.text):
            places.append(f"2쪽 소개 문단 {n}")
    for page, items in (("3쪽", copy.details), ("4쪽", copy.supply)):
        for item in items:
            for part, text in (("항목명", item.label), ("값", item.value)):
                if HANGUL.search(text):
                    places.append(f"{page} {FIELD_LABELS.get(item.key, '항목')} {part}")
    if places:
        raise GenerateOutputLanguageError(
            message="생성된 카탈로그 문구에 한국어가 남아 있어 결과를 표시하지 않았습니다. 위치: " + ", ".join(places[:6]))


def _words(text, exclude):
    return {w for w in _WORD.findall(text.lower()) if w not in exclude}


def _flag_repetition(tagline, paragraphs, display_name):
    """표지 소개와 거의 같은 2쪽 문단에 검토 표시(거부 아님). 표시명 단어는 정상 반복으로 보고 제외합니다."""
    exclude = {w.lower() for w in _WORD.findall(display_name)}
    base = _words(tagline["text"], exclude)
    if len(base) < 3:
        return
    for p in paragraphs:
        if len(base & _words(p["text"], exclude)) / len(base) >= REPEAT_RATIO:
            p["review_flags"].append("repeated_text")


def build_pages(copy, by_key, used, display_name):
    if not 1 <= len(copy.intro_paragraphs) <= MAX_INTRO_PARAGRAPHS:
        raise GenerateOutputInvalidError()
    check_output_language(copy)
    name = by_key["product_name"]
    tagline = _copy(copy.tagline, by_key, used, MAX_TAGLINE_CHARS)
    paragraphs = [_copy(p, by_key, used, MAX_PARAGRAPH_CHARS) for p in copy.intro_paragraphs]
    _flag_repetition(tagline, paragraphs, display_name)
    return {
        "cover": {
            "page": 1,
            # 표지 제품명은 AI가 만들지 않고 사용자가 확인한 카탈로그 표시명을 그대로 사용(원본 product_name은 보존)
            "product_name": {"text": display_name, "source_keys": ["product_name"], "virtual": name.virtual,
                             "origins": {"product_name": name.origin}, "review_flags": []},
            "tagline": tagline,
        },
        "intro": {"page": 2, "paragraphs": paragraphs},
        "details": {"page": 3, **_items(copy.details, [k for k in DETAIL_KEYS if k in used], by_key,
                                         MAX_DETAIL_VALUE_CHARS, EMPTY_DETAILS)},
        "supply": {"page": 4, **_items(copy.supply, [k for k in SUPPLY_KEYS if k in used], by_key,
                                        MAX_SUPPLY_VALUE_CHARS, EMPTY_SUPPLY)},
    }


def generate_catalog(payload):
    """검증된 입력 → 공통 generate_structured(재시도 없음) → 서버 검증 → 응답 data. 결과를 저장·로깅하지 않습니다."""
    by_key, display_name = parse_request(payload)
    used, excluded = select_inputs(by_key)
    result = generate_structured(
        instructions=load_instructions(),
        input_text=build_model_input(by_key, used, display_name),
        schema=CatalogCopy,
    )
    pages = build_pages(result.data, by_key, used, display_name)
    return {
        "status": "draft_needs_review",  # 번역·내용 검토가 필요한 초안
        "language": "pt-BR",
        "prompt_version": PROMPT_VERSION,
        "model": result.model,
        "notices": {"unofficial": NOTICE_UNOFFICIAL, "fictitious": NOTICE_FICTITIOUS},
        "display_name": {"value": display_name, "confirmed": True},
        "pages": pages,
        "used_keys": used,
        "excluded": excluded,
        "input_meta": {k: {"confirmed": by_key[k].confirmed, "virtual": by_key[k].virtual,
                           "origin": by_key[k].origin} for k in FIELD_KEYS},
    }
