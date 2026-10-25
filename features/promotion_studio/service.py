"""홍보 스튜디오 service.

현재 구현
- validate_input: 콘티 입력 검증. 화면(panel.html·promotion_studio.js)과 같은 제한값(LIMITS)을 사용합니다.
  파일은 크기·형식만 확인하고 저장하지 않습니다.
- generate_storyboard: 검증된 입력 → 텍스트 콘티(포르투갈어 + 한국어 검토본). 공통 ai_client로 서버에서 호출합니다.
  보조 문서·사진·로고 내용은 아직 생성에 쓰지 않습니다(문서 추출·이미지 단계 미구현).
"""
import json
import os
from pathlib import Path

from pydantic import BaseModel

from common.ai_client import generate_structured
from common.errors import AIOutputInvalidError

# 입력 선택지. 값은 요청 필드 값, 문구는 화면 표시용입니다.
AUDIENCES = (("buyer", "바이어용"), ("consumer", "소비자용"))
PURPOSES = (
    ("product_intro", "제품 소개"),
    ("brand_awareness", "브랜드 인지도 향상"),
    ("eco_value", "친환경 가치 전달"),
    ("buyer_inquiry", "바이어 상담·문의 유도"),
    ("consumer_purchase", "소비자 구매 유도"),
    ("partnership", "협업·파트너십 제안"),
    ("other", "기타 직접 입력"),
)
TONES = (
    ("professional", "전문적·신뢰감"),
    ("emotional", "감성적"),
    ("energetic", "활기찬"),
    ("premium", "고급스러운"),
    ("other", "기타 직접 입력"),
)
DURATIONS = (15, 30, 60, 90)
ASPECT_RATIOS = ("16:9", "9:16", "1:1", "4:5")
IMAGE_STYLES = (
    ("photo", "실사형"),
    ("illustration", "일러스트형"),
    ("sketch", "스케치형"),
    ("render_3d", "3D 렌더형"),
    ("other", "기타 직접 입력"),
)
LOGO_SCOPES = (("image_and_pdf", "장면 이미지 + 콘티·PDF"), ("pdf_only", "콘티·PDF만"))

DOC_EXTENSIONS = (".pdf", ".docx", ".pptx", ".hwp", ".xlsx", ".txt")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
MB = 1024 * 1024

# 2026-10-25 사용자 확정(feature_spec.md 3장). 화면 기본값도 여기서 읽습니다.
LIMITS = {
    "description_max_chars": 3000,
    "cta_max_chars": 200,
    "other_max_chars": 50,
    "revision_request_max_chars": 1000,  # AI 수정 요청(5단계에서 사용)
    "purpose_max": 2,
    "scene_min": 3,
    "scene_max": 15,
    "doc_max_files": 3,
    "doc_max_file_bytes": 20 * MB,
    "doc_max_total_bytes": 60 * MB,
    "photo_max_files": 5,
    "logo_max_files": 1,
    "image_max_file_bytes": 10 * MB,
    "image_max_total_bytes": 60 * MB,  # 제품 사진 + 로고 합계, 문서와 별도
    "wait_min_seconds": 30,
    "wait_max_seconds": 600,
}
DEFAULTS = {
    "duration": 30,
    "scene_count": 6,
    "aspect_ratio": "16:9",
    "image_style": "photo",
    "max_wait_seconds": 180,
}

FIELD_LABELS = {
    "audience": "대상",
    "description": "제품 설명",
    "purposes": "홍보 목적",
    "purpose_other": "홍보 목적 기타",
    "cta": "CTA",
    "tone": "홍보 톤",
    "tone_other": "홍보 톤 기타",
    "duration": "영상 길이",
    "scene_count": "장면 수",
    "aspect_ratio": "화면 비율",
    "image_style": "이미지 스타일",
    "image_style_other": "이미지 스타일 기타",
    "max_wait_seconds": "최대 대기 시간",
    "documents": "보조 문서",
    "photos": "제품 사진",
    "logo": "로고",
    "logo_scope": "로고 적용 범위",
}

# 이미지 파일 앞부분 서명. 확장자만 바꾼 파일을 걸러냅니다(내용 전체 검증은 아님).
_IMAGE_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}


def _values(options):
    return tuple(value for value, _ in options)


def _ext(filename):
    return os.path.splitext(filename or "")[1].lower()


def _file_size(storage):
    """FileStorage 크기(bytes). 스트림을 끝까지 이동한 뒤 원위치로 되돌립니다."""
    stream = storage.stream
    pos = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(pos)
    return size


def _file_head(storage, length=16):
    stream = storage.stream
    pos = stream.tell()
    stream.seek(0)
    head = stream.read(length)
    stream.seek(pos)
    return head


def _image_signature_ok(ext, head):
    if ext == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return any(head.startswith(sig) for sig in _IMAGE_SIGNATURES[ext])


class _Errors:
    def __init__(self):
        self.items = []

    def add(self, field, message):
        self.items.append({"field": field, "message": message})


def _text(form, name):
    return (form.get(name) or "").strip()


def _choice(form, name, options, errors):
    value = _text(form, name)
    if value not in options:
        errors.add(name, f"{FIELD_LABELS[name]}을(를) 선택하세요.")
        return None
    return value


def _other_text(form, name, errors):
    value = _text(form, name)
    if not value:
        errors.add(name, f"{FIELD_LABELS[name]} 내용을 입력하세요.")
    elif len(value) > LIMITS["other_max_chars"]:
        errors.add(name, f"{FIELD_LABELS[name]}은(는) {LIMITS['other_max_chars']}자 이하로 입력하세요.")
    return value


def _int(form, name):
    value = _text(form, name)
    try:
        return int(value)
    except ValueError:
        return None


def _check_files(files, name, extensions, max_files, max_file_bytes, errors, image=False):
    """선택된 파일 목록을 검사하고 (파일 정보 목록, 합계 bytes)를 돌려줍니다."""
    selected = [f for f in files.getlist(name) if f and f.filename]
    label = FIELD_LABELS[name]
    if len(selected) > max_files:
        errors.add(name, f"{label}은(는) 최대 {max_files}개까지 올릴 수 있습니다.")
    infos = []
    total = 0
    for storage in selected:
        filename = storage.filename
        ext = _ext(filename)
        size = _file_size(storage)
        total += size
        if ext not in extensions:
            errors.add(name, f"{filename}: 지원하지 않는 형식입니다.")
        elif size == 0:
            errors.add(name, f"{filename}: 빈 파일입니다.")
        elif size > max_file_bytes:
            errors.add(name, f"{filename}: 파일당 {max_file_bytes // MB}MB 이하만 올릴 수 있습니다.")
        elif image and not _image_signature_ok(ext, _file_head(storage)):
            errors.add(name, f"{filename}: 확장자와 파일 내용이 맞지 않습니다.")
        infos.append({"filename": filename, "size": size})
    return infos, total


def validate_input(form, files):
    """콘티 입력을 검증합니다.

    form: 문자열 값 MultiDict(request.form). files: FileStorage MultiDict(request.files).
    반환: (cleaned, errors). errors가 비어 있으면 cleaned가 유효합니다.
    errors: [{"field": 필드명, "message": 사용자 안내 문장}] (파일 내용·서버 경로를 담지 않음)
    """
    errors = _Errors()
    cleaned = {}

    cleaned["audience"] = _choice(form, "audience", _values(AUDIENCES), errors)

    description = _text(form, "description")
    if not description:
        errors.add("description", "제품 설명을 입력하세요.")
    elif len(description) > LIMITS["description_max_chars"]:
        errors.add("description", f"제품 설명은 {LIMITS['description_max_chars']:,}자 이하로 입력하세요.")
    cleaned["description"] = description

    purposes = list(dict.fromkeys(v.strip() for v in form.getlist("purposes") if v.strip()))
    if not purposes:
        errors.add("purposes", "홍보 목적을 1개 이상 선택하세요.")
    elif len(purposes) > LIMITS["purpose_max"]:
        errors.add("purposes", f"홍보 목적은 최대 {LIMITS['purpose_max']}개까지 선택할 수 있습니다.")
    elif any(p not in _values(PURPOSES) for p in purposes):
        errors.add("purposes", "홍보 목적 선택값이 올바르지 않습니다.")
    cleaned["purposes"] = purposes
    cleaned["purpose_other"] = _other_text(form, "purpose_other", errors) if "other" in purposes else ""

    cta = _text(form, "cta")
    if len(cta) > LIMITS["cta_max_chars"]:
        errors.add("cta", f"CTA는 {LIMITS['cta_max_chars']}자 이하로 입력하세요.")
    cleaned["cta"] = cta  # 비어 있으면 생성 단계에서 CTA를 만들지 않습니다.

    cleaned["tone"] = _choice(form, "tone", _values(TONES), errors)
    cleaned["tone_other"] = _other_text(form, "tone_other", errors) if cleaned["tone"] == "other" else ""

    duration = _int(form, "duration")
    if duration not in DURATIONS:
        errors.add("duration", "영상 길이를 선택하세요.")
    cleaned["duration"] = duration

    scene_count = _int(form, "scene_count")
    if scene_count is None or not LIMITS["scene_min"] <= scene_count <= LIMITS["scene_max"]:
        errors.add("scene_count", f"장면 수는 {LIMITS['scene_min']}~{LIMITS['scene_max']}개 중에서 선택하세요.")
    cleaned["scene_count"] = scene_count

    cleaned["aspect_ratio"] = _choice(form, "aspect_ratio", ASPECT_RATIOS, errors)
    cleaned["image_style"] = _choice(form, "image_style", _values(IMAGE_STYLES), errors)
    cleaned["image_style_other"] = (
        _other_text(form, "image_style_other", errors) if cleaned["image_style"] == "other" else ""
    )

    wait = _int(form, "max_wait_seconds")
    if wait is None or not LIMITS["wait_min_seconds"] <= wait <= LIMITS["wait_max_seconds"]:
        errors.add(
            "max_wait_seconds",
            f"최대 대기 시간은 {LIMITS['wait_min_seconds']}~{LIMITS['wait_max_seconds']}초 사이의 정수로 입력하세요.",
        )
    cleaned["max_wait_seconds"] = wait

    docs, doc_total = _check_files(
        files, "documents", DOC_EXTENSIONS, LIMITS["doc_max_files"], LIMITS["doc_max_file_bytes"], errors)
    if doc_total > LIMITS["doc_max_total_bytes"]:
        errors.add("documents", f"보조 문서 합계는 {LIMITS['doc_max_total_bytes'] // MB}MB 이하여야 합니다.")
    photos, photo_total = _check_files(
        files, "photos", IMAGE_EXTENSIONS, LIMITS["photo_max_files"], LIMITS["image_max_file_bytes"], errors,
        image=True)
    logos, logo_total = _check_files(
        files, "logo", IMAGE_EXTENSIONS, LIMITS["logo_max_files"], LIMITS["image_max_file_bytes"], errors,
        image=True)
    if photo_total + logo_total > LIMITS["image_max_total_bytes"]:
        errors.add("photos", f"제품 사진과 로고 합계는 {LIMITS['image_max_total_bytes'] // MB}MB 이하여야 합니다.")
    cleaned["documents"] = docs
    cleaned["photos"] = photos
    cleaned["logo"] = logos[0] if logos else None

    # 로고가 있을 때만 적용 범위를 받습니다. 기본값을 정하지 않았으므로 사용자가 선택해야 합니다.
    cleaned["logo_scope"] = _choice(form, "logo_scope", _values(LOGO_SCOPES), errors) if logos else None

    return cleaned, errors.items


# ---------- 텍스트 콘티 생성 ----------
PROMPT_VERSION = "storyboard_generate_v1"
_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.md"
# 장면 1개당 두 언어 6개 문장. 추론 토큰을 포함한 출력 상한이며 금액 한도가 아닙니다.
_OUTPUT_TOKENS_BASE = 2000
_OUTPUT_TOKENS_PER_SCENE = 700


class StoryboardScene(BaseModel):
    scene_number: int
    duration_seconds: int
    visual_pt: str
    visual_ko: str
    camera_pt: str
    camera_ko: str
    subtitle_pt: str
    subtitle_ko: str
    narration_pt: str
    narration_ko: str


class Storyboard(BaseModel):
    title_pt: str
    title_ko: str
    scenes: list[StoryboardScene]
    review_notes: list[str]


def _label(options, value, other_text):
    return other_text if value == "other" else dict(options)[value]


def _model_input(cleaned):
    """모델에 보낼 입력 데이터(JSON). 파일명·파일 내용은 보내지 않습니다."""
    return json.dumps({
        "audience": cleaned["audience"],
        "product_description": cleaned["description"],
        "purposes": [_label(PURPOSES, p, cleaned["purpose_other"]) for p in cleaned["purposes"]],
        "tone": _label(TONES, cleaned["tone"], cleaned["tone_other"]),
        "image_style": _label(IMAGE_STYLES, cleaned["image_style"], cleaned["image_style_other"]),
        "cta": cleaned["cta"],
        "duration_seconds": cleaned["duration"],
        "scene_count": cleaned["scene_count"],
        "aspect_ratio": cleaned["aspect_ratio"],
    }, ensure_ascii=False)


def _notices(cleaned):
    """생성에 반영하지 않은 입력을 사용자에게 알립니다."""
    notices = []
    if cleaned["documents"]:
        notices.append("보조 문서 내용은 아직 콘티 생성에 반영하지 않습니다. 제품 설명에 입력한 내용만 사용했습니다.")
    if cleaned["photos"] or cleaned["logo"]:
        notices.append("제품 사진·로고는 이미지 생성·PDF 단계에서 사용할 예정이며, 이번 텍스트 콘티에는 반영하지 않았습니다.")
    return notices


def generate_storyboard(cleaned):
    """validate_input을 통과한 입력으로 텍스트 콘티를 생성합니다.

    반환: 화면 표시용 dict. 장면 시작·종료 시간은 모델이 낸 장면 길이로 코드에서 계산합니다.
    오류: common.errors.AIError 하위 클래스. 장면 수가 요청과 다르거나 길이가 1초 미만이면 AIOutputInvalidError.
    장면 길이 합계가 영상 길이와 다르면 결과는 돌려주되 timing.ok=False로 표시합니다(자동 보정하지 않음).
    """
    scene_count = cleaned["scene_count"]
    result = generate_structured(
        instructions=_PROMPT_PATH.read_text(encoding="utf-8"),
        input_text=_model_input(cleaned),
        schema=Storyboard,
        max_output_tokens=_OUTPUT_TOKENS_BASE + _OUTPUT_TOKENS_PER_SCENE * scene_count,
    )
    board = result.data
    if len(board.scenes) != scene_count:
        raise AIOutputInvalidError(message="생성된 장면 수가 선택한 장면 수와 달라 결과를 표시하지 않았습니다. 다시 시도하세요.")
    if any(scene.duration_seconds < 1 for scene in board.scenes):
        raise AIOutputInvalidError(message="장면 길이가 올바르지 않은 결과가 생성되어 표시하지 않았습니다. 다시 시도하세요.")

    scenes = []
    start = 0
    # 장면 번호는 모델 값 대신 순서대로 다시 매깁니다.
    for number, scene in enumerate(board.scenes, start=1):
        end = start + scene.duration_seconds
        item = scene.model_dump(exclude={"scene_number"})
        item.update(number=number, start_seconds=start, end_seconds=end)
        scenes.append(item)
        start = end

    return {
        "title_pt": board.title_pt,
        "title_ko": board.title_ko,
        "scenes": scenes,
        "review_notes": board.review_notes,
        "notices": _notices(cleaned),
        "timing": {"total_seconds": start, "expected_seconds": cleaned["duration"], "ok": start == cleaned["duration"]},
        "conditions": {
            "audience": dict(AUDIENCES)[cleaned["audience"]],
            "duration": cleaned["duration"],
            "scene_count": scene_count,
            "aspect_ratio": cleaned["aspect_ratio"],
        },
        "model": result.model,
        "prompt_version": PROMPT_VERSION,
    }
