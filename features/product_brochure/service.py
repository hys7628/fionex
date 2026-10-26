"""제품소개서 PDF 분석 서비스: 추출 스키마, 서비스 프롬프트, 공통 함수 호출, 결과 후처리.

결과는 사용자가 확인하기 전의 AI 추출 초안입니다. 확정 제품 정보로 취급하지 않습니다.
페이지·발췌는 AI가 제시한 근거이며 원문과 자동 대조하지 않습니다(check="not_checked").
"""
from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel

from common.ai_client import generate_structured_from_pdf
from common.errors import AIInputError

PROMPT_VERSION = "brochure_extract_v1"
_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / (PROMPT_VERSION + ".md")

# 화면(static/product_brochure.js)의 항목 key와 같아야 합니다. 순서는 응답 순서입니다.
FIELDS = (
    ("product_name", "제품명"),
    ("description", "제품 설명"),
    ("yarn_spec", "원사 규격"),
    ("carbon_reduction", "탄소 저감률"),
    ("certification", "인증"),
    ("moq", "MOQ"),
    ("sample", "샘플"),
    ("lead_time", "납기"),
)
FIELD_KEYS = tuple(k for k, _ in FIELDS)
FIELD_LABELS = dict(FIELDS)

FieldKey = Literal["product_name", "description", "yarn_spec", "carbon_reduction",
                   "certification", "moq", "sample", "lead_time"]
Status = Literal["found", "unclear", "not_found"]

# 응답 크기 보호용. 넘으면 잘라 내고 검토 사항으로 알립니다.
MAX_QUOTE_CHARS = 300
MAX_TEXT_CHARS = 2000


# ---------- AI 결과 스키마(Structured Outputs) ----------
class Evidence(BaseModel):
    page: Optional[int]
    quote: str


class ExtractedField(BaseModel):
    key: FieldKey
    value: Optional[str]
    status: Status
    evidence: List[Evidence]
    marked_virtual: bool
    note: Optional[str]


class BrochureExtraction(BaseModel):
    fields: List[ExtractedField]
    multiple_products: bool
    review_notes: List[str]


assert set(FieldKey.__args__) == set(FIELD_KEYS)  # 스키마와 화면 key 목록 일치


# ---------- 기능 전용 업로드 오류(공통 오류 계약을 그대로 따름) ----------
class UploadTooLargeError(AIInputError):
    code = "UPLOAD_TOO_LARGE"
    message = "업로드 요청이 허용 용량을 넘습니다. PDF 파일 1개만 첨부하세요."
    http_status = 413


class UploadFileMissingError(AIInputError):
    code = "UPLOAD_FILE_MISSING"
    message = "PDF 파일이 첨부되지 않았습니다."


class UploadFilenameMissingError(AIInputError):
    code = "UPLOAD_FILENAME_MISSING"
    message = "선택된 파일이 없습니다. PDF 파일을 선택하세요."


class UploadMultipleFilesError(AIInputError):
    code = "UPLOAD_MULTIPLE_FILES"
    message = "PDF 파일은 1개만 첨부할 수 있습니다."


class UploadUnexpectedFieldError(AIInputError):
    code = "UPLOAD_UNEXPECTED_FIELD"
    message = "허용되지 않은 파일 항목이 포함되어 있습니다."


# ---------- 프롬프트 ----------
@lru_cache(maxsize=1)
def load_instructions():
    return _PROMPT_PATH.read_text(encoding="utf-8")


# ---------- 후처리 ----------
def _clean_text(value, limit, notes, label, what):
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > limit:
        notes.append(f"{label}: {what}이 길어 {limit}자까지만 표시합니다.")
        text = text[:limit]
    return text


def _normalize_field(key, raw, page_count, notes):
    label = FIELD_LABELS[key]
    value = _clean_text(raw.value, MAX_TEXT_CHARS, notes, label, "값")
    note = _clean_text(raw.note, MAX_TEXT_CHARS, notes, label, "설명")
    status = raw.status
    server_notes = []

    evidence = []
    out_of_range = False
    for ev in raw.evidence:
        quote = _clean_text(ev.quote, MAX_QUOTE_CHARS, notes, label, "근거 발췌")
        page_ok = ev.page is not None and 1 <= ev.page <= page_count
        if ev.page is not None and not page_ok:
            out_of_range = True
        evidence.append({"page": ev.page, "quote": quote, "page_in_range": page_ok, "check": "not_checked"})
    if out_of_range:
        server_notes.append("AI가 제시한 페이지 번호가 PDF 페이지 범위를 벗어납니다.")

    has_valid_evidence = any(e["quote"] and e["page_in_range"] for e in evidence)
    if status == "found" and value is None:
        status = "unclear"
        server_notes.append("값이 비어 있어 확인 필요로 바꿨습니다.")
    elif status == "found" and not has_valid_evidence:
        status = "unclear"
        server_notes.append("유효한 근거(페이지·발췌)가 없어 확인 필요로 바꿨습니다.")
    elif status == "not_found" and value is not None:
        status = "unclear"
        server_notes.append("찾지 못함으로 표시됐지만 값이 있어 확인 필요로 바꿨습니다.")

    for msg in server_notes:
        notes.append(f"{label}: {msg}")
    return {
        "key": key,
        "label": label,
        "value": value,
        "status": status,
        "ai_status": raw.status,
        "evidence": evidence,
        "marked_virtual": raw.marked_virtual,  # 가상 표시는 후처리에서 제거하지 않음
        "note": note,
        "server_notes": server_notes,
        "confirmed": False,  # 사용자 확인 전. found도 확인 완료가 아님
    }


def normalize_extraction(extraction, page_count):
    """AI 결과를 8개 항목 응답으로 정리합니다. 사실 정확성을 보장하지 않습니다."""
    notes = []  # 서버가 덧붙이는 고정 문장(문서 내용 미포함)
    by_key = {}
    for raw in extraction.fields:
        by_key.setdefault(raw.key, []).append(raw)

    fields = []
    for key in FIELD_KEYS:
        label = FIELD_LABELS[key]
        items = by_key.get(key, [])
        if not items:
            notes.append(f"{label}: AI 응답에 항목이 없어 확인 필요로 표시합니다.")
            fields.append({
                "key": key, "label": label, "value": None, "status": "unclear", "ai_status": None,
                "evidence": [], "marked_virtual": False, "note": None,
                "server_notes": ["AI 응답에 항목이 없습니다."], "confirmed": False,
            })
            continue
        field = _normalize_field(key, items[0], page_count, notes)
        if len(items) > 1:
            # 중복 항목은 한쪽을 버리지 않고 후보 값을 보존한 채 확인 필요로 둡니다.
            others = [_normalize_field(key, extra, page_count, []) for extra in items[1:]]
            candidates = [field["value"]] + [o["value"] for o in others]
            for o in others:
                field["evidence"].extend(o["evidence"])
                field["marked_virtual"] = field["marked_virtual"] or o["marked_virtual"]
            field["candidates"] = candidates
            field["status"] = "unclear"
            field["server_notes"].append("AI가 같은 항목을 여러 번 반환했습니다. 후보 값을 확인하세요.")
            notes.append(f"{label}: AI가 같은 항목을 여러 번 반환해 확인 필요로 표시합니다.")
        fields.append(field)

    if extraction.multiple_products:
        notes.append("PDF에 복수 제품이 있을 수 있습니다. 각 값이 대상 제품의 정보인지 확인하세요.")

    review_notes = [{"source": "server", "message": m} for m in notes]
    review_notes += [{"source": "ai", "message": t}
                     for t in (_clean_text(n, MAX_TEXT_CHARS, [], "", "") for n in extraction.review_notes) if t]
    return {"fields": fields, "multiple_products": extraction.multiple_products, "review_notes": review_notes}


def analyze_pdf(pdf_bytes):
    """PDF bytes → 응답 data. 공통 함수의 검사·설정·재시도 정책을 그대로 사용합니다(추가 재시도 없음)."""
    result = generate_structured_from_pdf(
        instructions=load_instructions(),
        pdf_bytes=pdf_bytes,
        schema=BrochureExtraction,
    )
    data = normalize_extraction(result.data, result.pdf.page_count)
    return {
        "extraction_status": "unconfirmed",
        "prompt_version": PROMPT_VERSION,
        "source": {"size_bytes": result.pdf.size_bytes, "page_count": result.pdf.page_count},
        "model": result.model,
        **data,
    }
