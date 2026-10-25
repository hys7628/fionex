"""홈 업계 소식의 포르투갈어 제목 → 한국어 한 줄 AI 요약.

- 대상: origin google·abit, 포르투갈어(lang "pt…"), 세 낱말 이상의 제목. KOTRA는 이용 조건(변경금지)상 요약하지 않습니다.
- 입력: id와 제목만. RSS description은 제목·매체명 반복이라(2026-10-25 111건 확인) 쓰지 않고, 본문은 가져오지 않습니다.
- 여러 항목을 한 번에 common.ai_client.generate_structured로 요청하고, 결과를 코드에서 다시 검증합니다.
- 결과(요약 또는 빈 값)는 (id, 제목) 기준으로 1시간 메모리 캐시합니다. 실패하면 요약 없이 제목만 보입니다.
"""
import json
import logging
import re
import threading
from collections import Counter
from pathlib import Path
from time import monotonic

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
# 채택 버전. v1(규칙만)·v2(규칙+few-shot) 비교 기록: docs/worklogs/hong_eunju/prompt_log.md
PROMPT_FILE = "news_summary_v1.md"
PROMPT_MARKER = "## instructions"

TARGET_ORIGINS = ("google", "abit")
MIN_TITLE_WORDS = 3
BATCH_SIZE = 40
TARGET_CHARS = 60  # 프롬프트 목표
MAX_CHARS = 80     # 이보다 길면 자르지 않고 버립니다(자르면 뜻이 바뀔 수 있음).
CACHE_SECONDS = 60 * 60

STATUS_MESSAGES = {
    "unavailable": "AI 요약을 사용할 수 없습니다. 원문 제목만 표시합니다.",
    "error": "AI 요약을 만들지 못했습니다. 원문 제목만 표시합니다.",
}

# (id, 제목) → {"summary": str, "expires": float}. "" 은 요약 없음(정보 부족·검증 탈락)으로 다시 요청하지 않습니다.
_cache = {}
_lock = threading.Lock()

_NUMBER = re.compile(r"[0-9]+(?:[.,][0-9]+)*")
_HANGUL = re.compile(r"[가-힣]")


def is_target(item):
    return (item.get("origin") in TARGET_ORIGINS
            and str(item.get("lang") or "").lower().startswith("pt")
            and len(str(item.get("title") or "").split()) >= MIN_TITLE_WORDS)


def cached(item):
    """요약 문자열, 요약 없음이면 "", 아직 결과가 없거나 만료면 None."""
    entry = _cache.get((item["id"], item["title"]))
    if entry is None or entry["expires"] <= monotonic():
        return None
    return entry["summary"]


def pending_count(items):
    return sum(1 for item in items if is_target(item) and cached(item) is None)


def summarize(items):
    """결과가 없는 대상 항목만 묶어 요청합니다.

    반환 {"status": "ok"|"unavailable"|"error", "message"?, "summaries": {id: 요약}}
    summaries에는 이번에 만든 것과 캐시에 있던 것을 모두 담습니다(빈 값 제외).
    """
    status = "ok"
    with _lock:  # 같은 기사를 동시에 두 번 요청하지 않게 합니다.
        _prune()
        targets = [item for item in items if is_target(item) and cached(item) is None]
        if targets:
            status = _request(targets)
    result = {"status": status, "summaries": {}}
    if status != "ok":
        result["message"] = STATUS_MESSAGES[status]
    for item in items:
        summary = cached(item) if is_target(item) else None
        if summary:
            result["summaries"][item["id"]] = summary
    return result


def _request(targets):
    try:
        from common.ai_client import generate_structured
        from common.errors import AIConfigError, AIError
    except ImportError:  # openai·pydantic 미설치 환경에서도 뉴스는 보여야 합니다.
        logger.warning("AI 요약 사용 불가: 공통 AI 패키지를 불러오지 못함")
        return "unavailable"

    instructions = load_prompt()
    for start in range(0, len(targets), BATCH_SIZE):
        chunk = targets[start:start + BATCH_SIZE]
        requested = [{"id": item["id"], "title": item["title"]} for item in chunk]
        try:
            result = generate_structured(
                instructions=instructions,
                input_text=json.dumps(requested, ensure_ascii=False),
                schema=_schema(),
            )
        except AIConfigError:
            return "unavailable"
        except AIError as err:
            # 실패는 캐시하지 않아 다음 요청에서 다시 시도합니다. 공통 클라이언트가 code만 로그에 남깁니다.
            logger.warning("뉴스 요약 실패: code=%s", err.code)
            return "error"
        summaries, reasons = validate_summaries(requested, [item.model_dump() for item in result.data.items])
        if reasons:
            logger.info("뉴스 요약 검증 결과: %s", dict(reasons))  # 사유별 건수만, 내용은 남기지 않음
        expires = monotonic() + CACHE_SECONDS
        for item in chunk:
            _cache[(item["id"], item["title"])] = {"summary": summaries[item["id"]], "expires": expires}
    return "ok"


def validate_summaries(requested, output):
    """requested [{id, title}] · output [{id, summary_ko}] → ({id: 요약 또는 ""}, Counter(사유))

    요청하지 않은 id는 무시합니다. 같은 id가 서로 다른 값으로 여러 번 오면 그 id는 요약 없음으로 둡니다.
    """
    titles = {r["id"]: r["title"] for r in requested}
    reasons = Counter()
    answers = {}
    for entry in output:
        if not isinstance(entry, dict):
            reasons["invalid_entry"] += 1
            continue
        entry_id = entry.get("id")
        if entry_id not in titles:
            reasons["unknown_id"] += 1
            continue
        if entry_id in answers:
            reasons["duplicate_id"] += 1
            if answers[entry_id] != entry.get("summary_ko"):
                answers[entry_id] = None
            continue
        answers[entry_id] = entry.get("summary_ko")

    summaries = {}
    for entry_id, title in titles.items():
        if entry_id not in answers:
            reasons["missing_id"] += 1
            summaries[entry_id] = ""
            continue
        summary, reason = check_summary(answers[entry_id], title)
        if reason:
            reasons[reason] += 1
        summaries[entry_id] = summary
    return summaries, reasons


def check_summary(value, source):
    """(사용할 요약 또는 "", 탈락 사유 또는 None)"""
    if value is None:
        return "", "conflicting_id"
    if not isinstance(value, str):
        return "", "not_string"
    text = value.strip()
    if not text:
        return "", "empty"
    if "\n" in text or "\r" in text:
        return "", "multiline"
    if len(text) > MAX_CHARS:
        return "", "too_long"
    if not _HANGUL.search(text):
        return "", "not_korean"
    if unverified_numbers(text, source):
        return "", "unverified_number"
    return text, None


def unverified_numbers(summary, source):
    """요약의 숫자 중 원문에 없는 것. 2027·2.5·2,5·15%·1.200 형식을 숫자 덩어리로 비교합니다.

    소수점·자릿수 구분 기호는 쉼표와 점을 같은 것으로 봅니다(포르투갈어 2,5 = 2.5).
    단위 변환·계산된 숫자(예: 1,2 bilhão → 12억)는 원문에 없으므로 탈락합니다.
    """
    if any(ch.isdigit() and ch not in "0123456789" for ch in summary):
        return ["non_ascii_digit"]
    allowed = {_normalize(n) for n in _NUMBER.findall(source)}
    return [n for n in _NUMBER.findall(summary) if _normalize(n) not in allowed]


def _normalize(number):
    return number.replace(",", ".")


def load_prompt(name=PROMPT_FILE):
    text = (PROMPT_DIR / name).read_text(encoding="utf-8")
    head, marker, body = text.partition("\n" + PROMPT_MARKER + "\n")
    if not marker or not body.strip():
        raise ValueError(f"{name}에 '{PROMPT_MARKER}' 구역이 없습니다")
    return body.strip()


_schema_class = None


def _schema():
    # pydantic은 요약을 쓸 때만 불러옵니다(미설치 환경에서도 앱·뉴스는 동작).
    global _schema_class
    if _schema_class is None:
        import pydantic

        class NewsSummary(pydantic.BaseModel):
            id: str
            summary_ko: str

        class NewsSummaryBatch(pydantic.BaseModel):
            items: list[NewsSummary]

        _schema_class = NewsSummaryBatch
    return _schema_class


def _prune():
    now = monotonic()
    for key in [k for k, v in _cache.items() if v["expires"] <= now]:
        del _cache[key]
