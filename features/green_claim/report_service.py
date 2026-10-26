"""검수 결과 PDF 보고서 다운로드(feature_spec.md "검수 결과 PDF 다운로드").

- 브라우저가 보관한 마지막 유효 검수 결과(POST /api/green-claim/review 성공 응답의 data)를 받아
  형식·내부 일관성을 확인한 뒤, 별도 프로세스(report_worker.run, multiprocessing spawn)에서 PDF를 메모리로 만듭니다.
- OpenAI 검수·공식 출처 확인·기준 로드를 하지 않습니다. 기준 버전·해시·근거는 받은 결과의 값만 쓰고 보충하지 않습니다.
- 형식 확인은 받은 결과가 실제 AI 응답·서버 검수 결과와 같다는 증명이 아닙니다(서명·진위 확인 없음).
- 사용자 문구·결과·PDF를 디스크·DB·로그에 남기지 않습니다. 로그에는 오류 code만 남깁니다.
"""
import json
import logging
import multiprocessing
import re
import threading
import time
from datetime import datetime
from urllib.parse import urlsplit

from features.green_claim import criteria_check as cc
from features.green_claim import criteria_loader as cl
from features.green_claim import report_worker
from features.green_claim import review_service as rs
from features.green_claim import service
from features.green_claim.criteria_build import KST
from features.green_claim.service import ExtractError

logger = logging.getLogger(__name__)

# 이번 단계 초기값(실측 성능 보장 아님). feature_spec.md와 같은 값.
MAX_REQUEST_BYTES = 4_194_304
REPORT_TIMEOUT_SECONDS = 30.0
MAX_CONCURRENT_REPORTS = 1
MAX_PDF_BYTES = 20_000_000
MAX_EXCERPT_CHARS = 20_000
MAX_SHORT_CHARS = 200
MAX_URL_CHARS = 2_048
MAX_SOURCES = 10
MAX_WARNINGS = 50
MAX_CHANGES = 50
MAX_SERVER_CHECKS = 10
REPORT_FILENAME = "green_claim_review_report.pdf"
# 검수 때 공식 출처를 자동 확인하지 않음(2026-10-26 팀 합의, review_service와 같은 값)
CHECK_MODE_STORED_ONLY = rs.CHECK_MODE_STORED_ONLY
CHECK_STATUS_AUTO_OFF = rs.CHECK_STATUS_AUTO_OFF

# 검수 응답(review_service.run_review_request)과 정확히 같은 키. 검수 응답 계약이 바뀌면 함께 바꿉니다.
REQUEST_KEYS = {"review", "input_mode", "displayed_at"}
TOP_KEYS = {"text", "char_count", "position_unit", "items", "criteria_refs", "summary", "model_limitations", "model",
            "prompt_version", "criteria", "notices", "limits"}
ITEM_KEYS = {"id", "quote", "start", "end", "occurrence", "occurrences_in_text", "quote_language", "interpretation_ko",
             "action", "action_label_ko", "reason_ko", "direction_ko", "criteria_ids", "alternative", "alternative_note_ko",
             "server_checks"}
ALTERNATIVE_KEYS = {"original_text", "pt_br_text", "ko_interpretation"}
REF_KEYS = {"source_id", "legal_nature", "title_ko", "provisions", "official_url", "retrieved_at", "excerpt_pt",
            "translation_ko", "translation_official", "requirement_ko", "review_guidance_ko", "scope_limits_ko",
            "usage_rights_status"}
SUMMARY_KEYS = {"total", "by_action", "item_ids_by_action", "no_items_message", "model_summary_ko"}
CRITERIA_KEYS = {"bundle_id", "bundle_version", "schema_version", "content_hash", "active_version", "criteria_updated_on",
                 "freshness_mode", "check_mode", "check_overall", "unresolved_changes", "sources", "warnings"}
SOURCE_KEYS = {"id", "title", "legal_nature", "official_url", "retrieved_at", "usage_rights_status", "check_status",
               "check_reason", "check_attempted_at", "check_last_success_at", "previous_check_status",
               "previous_check_attempted_at"}
CHANGE_KEYS = {"source_id", "detected_at", "criteria_ids"}
LIMIT_KEYS = {"max_chars", "max_request_bytes", "ai_timeout_seconds", "ai_max_output_tokens"}

INPUT_MODES = ("text", "file")
LEGAL_NATURES = ("law", "advertising_self_regulation")
CHECK_MODES = (CHECK_MODE_STORED_ONLY,)
CHECK_STATUSES = (cc.STATUS_NO_CHANGE, cc.STATUS_CHANGED, cc.STATUS_FAILED, cc.STATUS_DEFERRED,
                  cc.STATUS_BASELINE_MISSING, cc.STATUS_PARTIAL, cc.STATUS_NOT_CHECKED)

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_CODE = re.compile(r"[a-z0-9_]{1,64}")
_HASH = re.compile(r"[0-9a-f]{16,128}")
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:[+-]\d{2}:\d{2}|Z)")
_URL_BAD = re.compile(r"[\s\x00-\x1f\x7f\"'<>\\`]")

_slots = threading.BoundedSemaphore(MAX_CONCURRENT_REPORTS)


class _Invalid(Exception):
    """내부: 결과 형식·일관성 위반(사용자 응답에는 고정 문장만)."""


# ---------- 값 검사 도구 ----------

def _check(condition):
    if not condition:
        raise _Invalid()


def _exact_keys(value, keys):
    _check(isinstance(value, dict) and set(value) == keys)


def _int(value, low=0, high=None):
    _check(isinstance(value, int) and not isinstance(value, bool) and value >= low and (high is None or value <= high))
    return value


def _str(value, limit, nullable=False, allow_blank=False):
    if value is None and nullable:
        return None
    _check(isinstance(value, str) and len(value) <= limit and (allow_blank or value.strip() != ""))
    try:
        value.encode("utf-8")  # 짝 없는 서로게이트 거부
    except UnicodeEncodeError:
        raise _Invalid() from None
    return value


def _list(value, limit):
    _check(isinstance(value, list) and len(value) <= limit)
    return value


def _iso(value, nullable=True):
    if value is None and nullable:
        return None
    _check(isinstance(value, str) and _ISO.fullmatch(value))
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _Invalid() from None
    return value


def safe_url(value):
    """http/https, 호스트 있음, 공백·제어문자·따옴표·꺾쇠 없음, 2,048자 이하만 허용."""
    if not isinstance(value, str) or not value or len(value) > MAX_URL_CHARS or _URL_BAD.search(value):
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


# ---------- 검수 결과 검증 ----------

def _validate_items(text, items, ref_ids):
    used = []
    previous = None
    spans = set()
    for number, item in enumerate(_list(items, rs.MAX_ITEMS), start=1):
        _exact_keys(item, ITEM_KEYS)
        _check(item["id"] == f"R{number}")
        start, end = _int(item["start"]), _int(item["end"])
        _check(start < end <= len(text) and (start, end) not in spans)
        _check(previous is None or (start, end) >= previous)  # 서버는 위치 순으로 R1…을 붙임
        spans.add((start, end))
        previous = (start, end)
        quote = _str(item["quote"], rs.MAX_QUOTE_CHARS)
        _check(text[start:end] == quote)  # Python 문자열 위치 = Unicode 코드 포인트
        starts = rs._occurrences(text, quote)
        _check(item["occurrences_in_text"] == len(starts))
        occurrence = _int(item["occurrence"], low=1, high=len(starts))
        _check(starts[occurrence - 1] == start)
        _check(item["action"] in rs.ACTIONS and item["action_label_ko"] == rs.ACTIONS[item["action"]])
        _check(item["quote_language"] in rs.LANGUAGES)
        for name in ("interpretation_ko", "reason_ko", "direction_ko"):
            _str(item[name], rs.MAX_FIELD_CHARS)
        ids = _list(item["criteria_ids"], rs.MAX_LIST)
        _check(all(isinstance(value, str) and _ID.fullmatch(value) for value in ids) and len(set(ids)) == len(ids))
        _check(item["action"] == "judgment_withheld" or ids)  # 관련 기준 없는 수정 권고·검토 필요 없음
        _check(all(value in ref_ids for value in ids))  # 필요한 근거가 빠지면 실패(보충하지 않음)
        used.extend(ids)
        alternative = item["alternative"]
        if alternative is not None:
            _exact_keys(alternative, ALTERNATIVE_KEYS)
            original = _str(alternative["original_text"], rs.MAX_FIELD_CHARS, nullable=True)
            pt_br = _str(alternative["pt_br_text"], rs.MAX_FIELD_CHARS, nullable=True)
            _check(original is not None or pt_br is not None)
            _check(item["quote_language"] != "pt-BR" or original is None)  # 포르투갈어 구절은 포르투갈어 예시 하나만(검수 응답 계약)
            _str(alternative["ko_interpretation"], rs.MAX_FIELD_CHARS, nullable=True)
        _str(item["alternative_note_ko"], rs.MAX_FIELD_CHARS, nullable=True)
        checks = _list(item["server_checks"], MAX_SERVER_CHECKS)
        _check(all(isinstance(value, str) and _CODE.fullmatch(value) for value in checks))
    return set(used)


def _validate_refs(refs, sources):
    _check(isinstance(refs, dict))
    for criterion_id, ref in refs.items():
        _check(_ID.fullmatch(criterion_id))
        _exact_keys(ref, REF_KEYS)
        source = sources.get(ref["source_id"])
        _check(source is not None)
        _check(ref["legal_nature"] in LEGAL_NATURES and ref["legal_nature"] == source["legal_nature"])
        _check(safe_url(ref["official_url"]) and ref["official_url"] == source["official_url"])
        _check(_iso(ref["retrieved_at"]) == source["retrieved_at"])
        _check(ref["translation_official"] is False)
        # 필수·선택 칸은 기준 로더(criteria_loader.REQUIRED_TEXT_FIELDS)와 같음: 원문 요구만 비어 있을 수 있음
        for name in ("title_ko", "provisions", "review_guidance_ko", "scope_limits_ko"):
            _str(ref[name], rs.MAX_FIELD_CHARS)
        _str(ref["requirement_ko"], rs.MAX_FIELD_CHARS, nullable=True)
        _str(ref["excerpt_pt"], MAX_EXCERPT_CHARS)
        _str(ref["translation_ko"], MAX_EXCERPT_CHARS)
        _str(ref["usage_rights_status"], MAX_SHORT_CHARS)


def _validate_summary(summary, items):
    _exact_keys(summary, SUMMARY_KEYS)
    ids_by_action = {action: [item["id"] for item in items if item["action"] == action] for action in rs.ACTIONS}
    _check(summary["total"] == len(items) and not isinstance(summary["total"], bool))
    _check(summary["by_action"] == {action: len(ids) for action, ids in ids_by_action.items()})
    _check(summary["item_ids_by_action"] == ids_by_action)
    _check(summary["no_items_message"] == (None if items else rs.NO_ITEMS_MESSAGE))
    _str(summary["model_summary_ko"], rs.MAX_SUMMARY_CHARS)


def _validate_criteria(criteria):
    _exact_keys(criteria, CRITERIA_KEYS)
    _str(criteria["bundle_id"], MAX_SHORT_CHARS)
    _str(criteria["bundle_version"], MAX_SHORT_CHARS)
    _int(criteria["schema_version"], high=1000)
    _check(isinstance(criteria["content_hash"], str) and _HASH.fullmatch(criteria["content_hash"]))
    _str(criteria["active_version"], MAX_SHORT_CHARS, nullable=True)
    _str(criteria["freshness_mode"], MAX_SHORT_CHARS, nullable=True)
    updated = criteria["criteria_updated_on"]
    _check(updated is None or (isinstance(updated, str) and cl._DATE.match(updated) and cl._valid_date(updated)))
    mode = criteria["check_mode"]
    _check(mode in CHECK_MODES)
    _check(criteria["check_overall"] is None or (isinstance(criteria["check_overall"], str)
                                                  and _CODE.fullmatch(criteria["check_overall"])))
    for text in _list(criteria["warnings"], MAX_WARNINGS):
        _str(text, rs.MAX_FIELD_CHARS)
    for change in _list(criteria["unresolved_changes"], MAX_CHANGES):
        _exact_keys(change, CHANGE_KEYS)
        _str(change["source_id"], MAX_SHORT_CHARS)
        _iso(change["detected_at"])
        if change["criteria_ids"] is not None:
            ids = _list(change["criteria_ids"], MAX_CHANGES)
            _check(all(isinstance(value, str) and _ID.fullmatch(value) for value in ids))
    sources = {}
    _check(isinstance(criteria["sources"], list) and 1 <= len(criteria["sources"]) <= MAX_SOURCES)
    for source in criteria["sources"]:
        _exact_keys(source, SOURCE_KEYS)
        _check(isinstance(source["id"], str) and _ID.fullmatch(source["id"]) and source["id"] not in sources)
        _str(source["title"], MAX_SHORT_CHARS)
        _check(source["legal_nature"] in LEGAL_NATURES and safe_url(source["official_url"]))
        _iso(source["retrieved_at"])
        _str(source["usage_rights_status"], MAX_SHORT_CHARS)
        _str(source["check_reason"], rs.MAX_FIELD_CHARS, nullable=True)
        _iso(source["check_last_success_at"])
        # 이번 검수는 자동 확인 안 함: 상태만, 시도 시각·이유를 만들지 않음. 이전 수동 확인 기록은 previous_*로만
        _check(source["check_status"] == CHECK_STATUS_AUTO_OFF and source["check_attempted_at"] is None
               and source["check_reason"] is None)
        _check(source["previous_check_status"] is None or source["previous_check_status"] in CHECK_STATUSES)
        _iso(source["previous_check_attempted_at"])
        sources[source["id"]] = source
    return sources


def validate_review(review):
    """검수 응답 data의 형식·일관성 확인. 위반은 _Invalid. 값은 바꾸지 않습니다."""
    _exact_keys(review, TOP_KEYS)
    text = _str(review["text"], rs.MAX_CHARS)
    _check("\r" not in text and review["char_count"] == len(text) and not isinstance(review["char_count"], bool))
    _check(review["position_unit"] == rs.POSITION_UNIT)
    sources = _validate_criteria(review["criteria"])
    refs = review["criteria_refs"]
    _validate_refs(refs, sources)
    used = _validate_items(text, review["items"], refs)
    _check(set(refs) == used)  # 참조하지 않은 근거가 섞이거나 필요한 근거가 빠지지 않음
    _validate_summary(review["summary"], review["items"])
    for text_value in _list(review["model_limitations"], rs.MAX_LIST):
        _str(text_value, rs.MAX_FIELD_CHARS)
    _str(review["model"], MAX_SHORT_CHARS, nullable=True)
    _check(isinstance(review["prompt_version"], str) and _CODE.fullmatch(review["prompt_version"]))
    _check(isinstance(review["notices"], list) and 1 <= len(review["notices"]) <= rs.MAX_LIST)
    for text_value in review["notices"]:
        _str(text_value, rs.MAX_FIELD_CHARS)
    _exact_keys(review["limits"], LIMIT_KEYS)
    _check(all(isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
               for value in review["limits"].values()))


def parse_request(raw):
    """요청 본문 bytes → 보고서 입력 dict. 실패는 ExtractError(REPORT_*)."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ExtractError("REPORT_JSON_INVALID") from None
    if not isinstance(payload, dict) or set(payload) != REQUEST_KEYS:
        raise ExtractError("REPORT_FIELDS_INVALID")
    if payload["input_mode"] not in INPUT_MODES:
        raise ExtractError("REPORT_FIELDS_INVALID")
    try:
        _iso(payload["displayed_at"])
    except _Invalid:
        raise ExtractError("REPORT_FIELDS_INVALID") from None
    try:
        validate_review(payload["review"])
    except (_Invalid, RecursionError):
        logger.warning("보고서 입력 거부: code=REPORT_RESULT_INVALID")
        raise ExtractError("REPORT_RESULT_INVALID") from None
    return payload


# ---------- 실행 ----------

def run_report_worker(data, timeout=REPORT_TIMEOUT_SECONDS, target=None):
    """target(기본 report_worker.run)을 별도 프로세스에서 실행하고 결과 dict를 돌려줍니다.
    시작 시간을 포함해 timeout을 넘으면 프로세스를 종료합니다(service.run_worker와 같은 방식, 슬롯은 별도)."""
    target = target or report_worker.run
    if not _slots.acquire(blocking=False):
        raise ExtractError("REPORT_BUSY")
    try:
        deadline = time.monotonic() + timeout
        ctx = multiprocessing.get_context("spawn")
        in_recv, in_send = ctx.Pipe(duplex=False)
        out_recv, out_send = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=target, args=(in_recv, out_send, None), daemon=True)
        proc.start()
        in_recv.close()
        out_send.close()
        sender = threading.Thread(target=service._send_bytes, args=(in_send, data), daemon=True)
        sender.start()
        finished = False
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not out_recv.poll(remaining):
                raise ExtractError("REPORT_TIMEOUT")
            result = out_recv.recv()
            finished = True
            return result
        except (EOFError, OSError):
            raise ExtractError("REPORT_FAILED") from None
        finally:
            service._stop(proc, wait=finished)
            out_recv.close()
            sender.join(2)
    finally:
        _slots.release()


def build_report(raw, timeout=REPORT_TIMEOUT_SECONDS, now=None):
    """요청 본문 bytes → PDF bytes. now는 테스트용 내부 인자(사용자 요청 값 아님)."""
    payload = parse_request(raw)
    now = now or datetime.now(KST).replace(microsecond=0)
    job = json.dumps({**payload, "generated_at": now.isoformat()}, ensure_ascii=False).encode("utf-8")
    try:
        result = run_report_worker(job, timeout)
    except ExtractError as err:
        logger.warning("보고서 생성 실패: code=%s", err.code)
        raise
    if not isinstance(result, dict) or result.get("status") != "ok":
        code = result.get("code") if isinstance(result, dict) else None
        code = code if code in ("REPORT_DEPENDENCY_MISSING", "REPORT_FAILED") else "REPORT_FAILED"
        logger.warning("보고서 생성 실패: code=%s", code)
        raise ExtractError(code)
    pdf = result.get("pdf")
    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-"):
        logger.warning("보고서 생성 실패: code=REPORT_FAILED")
        raise ExtractError("REPORT_FAILED")
    if len(pdf) > MAX_PDF_BYTES:
        logger.warning("보고서 생성 실패: code=REPORT_OUTPUT_TOO_LARGE")
        raise ExtractError("REPORT_OUTPUT_TOO_LARGE")
    return pdf
