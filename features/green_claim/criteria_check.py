"""공식 출처 변경 확인(feature_spec.md "기준 자료 변경 확인과 갱신 관리" — 공식 출처 확인·변경 판별·출처별 상태).

- 개발자가 실행할 때만 조회합니다(백그라운드·서버 시작 시 자동 조회 없음). 출처 목록은 아래 고정 정책뿐이며 사용자 입력 URL을 받지 않습니다.
- 표준 라이브러리 urllib, TLS 인증서 검증 유지. 요청당 10초·전체 30초·출처별 최대 2요청(robots.txt·리다이렉트 포함)·
  1건 최대 5,000,000바이트, 자동 재시도 없음, 다른 호스트·https 아닌 리다이렉트 거부. 소켓 단위 대기라 정확한 상한은 보장하지 않습니다.
- 변경 판별: 활성 기준의 원문 발췌 각 줄이 본문 텍스트에 순서대로 있는지만 봅니다. HTTP 200·ETag·Last-Modified·
  전체 HTML 해시로 개정·최신을 판단하지 않습니다. 대상 외 조항(새 조항 추가 등)은 확인하지 않습니다.
- 변경을 찾아도 활성 기준·md를 바꾸지 않습니다. 감지 기록만 data/criteria_work/detected/에 남기고 미반영 변경으로 표시합니다.
- 로그에는 출처 ID와 상태 코드만 남깁니다.
"""
import hashlib
import json
import logging
import re
import socket
import ssl
import time
import unicodedata
import urllib.error
import urllib.request
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from features.green_claim import criteria_build as cb
from features.green_claim import criteria_loader as cl
from features.green_claim import criteria_store as cs

logger = logging.getLogger(__name__)

# 이번 단계 초기 제한(feature_spec.md와 같은 값, 공통 설정 아님)
REQUEST_TIMEOUT_SECONDS = 10.0
TOTAL_TIMEOUT_SECONDS = 30.0
MAX_REQUESTS_PER_SOURCE = 2
MAX_DOWNLOAD_BYTES = 5_000_000
READ_CHUNK = 64 * 1024
USER_AGENT_TOKEN = "fionex-green-claim-criteria-check"
USER_AGENT = f"{USER_AGENT_TOKEN}/1 (manual developer check)"
REDIRECT_CODES = (301, 302, 303, 307, 308)
DETECTED_DIR_NAME = "detected"

STATUS_NO_CHANGE = "no_change_found"
STATUS_CHANGED = "change_detected"
STATUS_FAILED = "failed"
STATUS_DEFERRED = "deferred"
STATUS_BASELINE_MISSING = "baseline_missing"
STATUS_PARTIAL = "partial_checked"  # 읽고 비교했지만 일부 조항은 발췌가 조항 전체가 아니거나 경계를 못 찾아 완전 비교 못 함
STATUS_NOT_CHECKED = "not_checked"  # criteria_status(): 아직 확인 기록 없음
COMPARED = (STATUS_NO_CHANGE, STATUS_CHANGED, STATUS_PARTIAL)
COVERAGE_FILE = "comparison_units.json"
COVERAGE_VALUES = ("full", "partial", "unbounded")
CONTEXT_UNIT = "_context"

# 조항 단위 규칙. starts: 발췌 줄에서 조항 시작을 찾는 정규식(key 그룹)과 본문에서 같은 조항 시작을 찾는 정규식({key} 자리).
# boundaries: 본문에서 조항이 끝나는 줄(다음 조항·절·장·부속서 제목). scopes: 검색 범위(시작 줄 정규식, 끝 줄 정규식).
UNIT_RULES = {
    "SRC-CDC": {
        "starts": [{"excerpt": r"^Art\. ?(?P<key>\d+(?:-[A-Z])?)(?![\d-])", "label": "Art. {key}",
                    "page": r"^Art\. ?{key}(?![\d-])"}],
        "boundaries": [r"^Art\. ?\d+", r"^(?:CAPÍTULO|SEÇÃO|TÍTULO)\b"],
        "scopes": {},
    },
    "SRC-CONAR-WEB": {
        "starts": [
            {"excerpt": r"^Artigo (?P<key>\d+(?:-[A-Z])?)º?$", "label": "Artigo {key}", "page": r"^Artigo {key}º?$"},
            {"excerpt": r"^(?P<key>\d+)\. (?=[A-ZÀ-Ý]{3})", "label": "Anexo U {key}.", "page": r"^{key}\. [A-ZÀ-Ý]{3}",
             "scope": "annex_u"},
            {"excerpt": r"^(?P<key>[IVX]+)\. (?=[A-ZÀ-Ý]{3})", "label": "Anexo U {key}.", "page": r"^{key}\. [A-ZÀ-Ý]{3}",
             "scope": "annex_u"},
        ],
        "boundaries": [r"^Artigo \d+", r"^SEÇÃO \d+", r"^(?:Capítulo|CAPÍTULO)\b", r"^ANEXO\b", r"^\d+\. [A-ZÀ-Ý]{3}",
                       r"^[IVX]+\. [A-ZÀ-Ý]{3}"],
        "scopes": {"annex_u": (r'^ANEXO "U"', r'^ANEXO "(?!U")')},
    },
}

# 출처별 고정 정책. URL은 활성 기준의 sources[].url(source_register.md 기록)을 쓰고 host가 일치해야 합니다.
POLICIES = {
    "SRC-CDC": {
        "auto_fetch": True,
        "host": "www.planalto.gov.br",
        "charset": "windows-1252",  # 2026-10-25 확보본에 문자셋 선언 없음, windows-1252로 정상 해석됨(source_register.md)
        "markers": ("LEI Nº 8.078, DE 11 DE SETEMBRO DE 1990",),
        "strip_list_markers": False,
        "check_robots": True,
        "store_page_text": True,  # 법령 텍스트(Lei 9.610 Art. 8º IV 기록)
    },
    "SRC-CONAR-WEB": {
        "auto_fetch": False,
        "deferred_code": "terms_permission_unconfirmed",
        "deferred_reason": "CONAR 이용약관상 AI 시스템 입력 목적의 자동 수집은 사전 명시 허가가 필요하며 AI 이용 허가가 확인되지 않아 "
                           "자동 조회를 보류함(담당자의 기준 포함 결정은 허가가 아님)",
        "host": "www.conar.org.br",
        "charset": "utf-8",
        "markers": ("Código Brasileiro de Autorregulamentação Publicitária",),
        "strip_list_markers": True,  # 발췌 때 HTML 목록 기호 a.~h.를 덧붙였음(conar_excerpt.md)
        "check_robots": True,
        "store_page_text": False,
    },
    "SRC-CONAR-PDF": {
        "auto_fetch": False,
        "deferred_code": "pdf_other_host_unvalidated",
        "deferred_reason": "공식 페이지가 연결한 다른 호스트의 대조용 PDF이며, PDF 조항 단위 비교를 검증하지 않았고 CONAR 이용 조건도 "
                           "확인 전이라 보류함",
    },
}

REASONS = {
    "timeout": "요청 시간 제한(10초)을 넘었습니다.",
    "deadline": "확인 전체 시간 제한(30초)을 넘었습니다.",
    "too_large": "응답이 5,000,000바이트를 넘습니다.",
    "too_many_requests": "출처별 요청 수 제한(2회)을 넘었습니다(리다이렉트·robots.txt 포함).",
    "redirect_refused": "다른 호스트 또는 https가 아닌 주소로의 리다이렉트를 따르지 않았습니다.",
    "http_error": "공식 페이지가 정상 응답(200)을 주지 않았습니다.",
    "not_html": "HTML 문서가 아닌 응답입니다.",
    "decode_error": "본문 문자 인코딩을 해석하지 못했습니다.",
    "page_unrecognized": "출처 식별 문구가 없어 오류·로그인·다른 페이지로 보고 비교하지 않았습니다.",
    "extraction_failed": "대상 조항을 하나도 찾지 못해 본문 추출 실패로 처리했습니다(변경으로 단정하지 않음).",
    "network_error": "연결하지 못했습니다.",
    "tls_error": "TLS 인증서 검증 또는 연결에 실패했습니다.",
    "robots_unavailable": "robots.txt를 확인하지 못해 조회하지 않았습니다.",
    "robots_disallowed": "robots.txt가 이 경로의 자동 조회를 허용하지 않아 보류했습니다.",
    "url_not_allowed": "활성 기준의 출처 URL이 고정 정책의 공식 호스트와 다릅니다.",
    "baseline_missing": "이 자료에는 비교할 저장 원문 발췌가 없습니다(비교 기준 부족).",
    "no_change_found": "대상 조항 전체를 읽고 비교해 변경을 발견하지 못했습니다(대상 외 조항·공식 개정 여부는 확인 범위 밖).",
    "partial_checked": "부분 확인: 일부 대상 조항은 저장 발췌가 조항 전체가 아니거나 조항 경계를 찾지 못해, 발췌 문장이 그대로인지만 확인했습니다"
                       "(조항 전체 변경 없음으로 보지 않음).",
    "change_detected": "대상 조항이 저장 원문과 다릅니다. 번역·해석 검토가 필요하며 아직 반영하지 않았습니다.",
}


class FetchFailure(Exception):
    def __init__(self, code, http_status=None):
        self.code = code
        self.http_status = http_status
        super().__init__(code)


# ---------- 조회 ----------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 리다이렉트는 _Session이 요청 수·호스트 제한 안에서 직접 처리


def default_open(url, timeout):
    """실제 HTTPS 요청 1회(리다이렉트 자동 추적 없음, 기본 SSL 컨텍스트 = 인증서 검증)."""
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/plain;q=0.9"})
    try:
        return opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as err:
        return err  # 상태·헤더를 읽기 위해 응답처럼 다룸


class _Session:
    """출처 1개의 요청 묶음. 요청 수·시간·크기·리다이렉트 제한을 적용합니다."""

    def __init__(self, opener, clock, deadline):
        self.opener = opener
        self.clock = clock
        self.deadline = deadline
        self.requests = 0
        self.last_headers = None

    def get(self, url):
        origin = urlsplit(url)
        while True:
            if self.requests >= MAX_REQUESTS_PER_SOURCE:
                raise FetchFailure("too_many_requests")
            remaining = self.deadline - self.clock()
            if remaining <= 0:
                raise FetchFailure("deadline")
            timeout = min(REQUEST_TIMEOUT_SECONDS, remaining)
            self.requests += 1
            started = self.clock()
            try:
                response = self.opener(url, timeout)
            except (socket.timeout, TimeoutError):
                raise FetchFailure("timeout") from None
            except ssl.SSLError:
                raise FetchFailure("tls_error") from None
            except urllib.error.URLError as err:
                reason = getattr(err, "reason", None)
                code = "tls_error" if isinstance(reason, ssl.SSLError) else (
                    "timeout" if isinstance(reason, (socket.timeout, TimeoutError)) else "network_error")
                raise FetchFailure(code) from None
            except OSError:
                raise FetchFailure("network_error") from None
            try:
                status = getattr(response, "status", None) or getattr(response, "code", None)
                headers = response.headers
                self.last_headers = headers
                if status in REDIRECT_CODES:
                    location = headers.get("Location") if headers is not None else None
                    target = urlsplit(urljoin(url, location or ""))
                    if not location or target.scheme != "https" or target.hostname != origin.hostname:
                        raise FetchFailure("redirect_refused", status)
                    url = target.geturl()
                    continue
                body = self._read(response, headers, started, timeout)
                return status, headers, body
            finally:
                try:
                    response.close()
                except Exception:
                    pass

    def _read(self, response, headers, started, timeout):
        length = headers.get("Content-Length") if headers is not None else None
        if length is not None:
            try:
                if int(length) > MAX_DOWNLOAD_BYTES:
                    raise FetchFailure("too_large")
            except ValueError:
                pass
        chunks, total = [], 0
        while True:
            if self.clock() - started > timeout:
                raise FetchFailure("timeout")
            if self.clock() > self.deadline:
                raise FetchFailure("deadline")
            try:
                chunk = response.read(READ_CHUNK)
            except (socket.timeout, TimeoutError):
                raise FetchFailure("timeout") from None
            except OSError:
                raise FetchFailure("network_error") from None
            if not chunk:
                return b"".join(chunks)
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise FetchFailure("too_large")
            chunks.append(chunk)


def _robots_allows(session, page_url):
    parts = urlsplit(page_url)
    status, _, body = session.get(f"https://{parts.hostname}/robots.txt")
    if status in (404, 410):
        return True  # robots.txt 없음 = 제한 없음(관례)
    if status in (401, 403):
        return False
    if status != 200:
        raise FetchFailure("robots_unavailable", status)
    parser = RobotFileParser()
    parser.parse(body.decode("utf-8", errors="replace").splitlines())
    return parser.can_fetch(USER_AGENT_TOKEN, page_url)


# ---------- 본문 추출·비교 ----------

class _TextParser(HTMLParser):
    BLOCK = ("p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "table")
    SKIP = ("script", "style", "noscript")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def normalize(text):
    text = unicodedata.normalize("NFC", text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def html_lines(body, charset):
    """HTML bytes → 공백 정규화한 본문 줄 목록(빈 줄 제외). 엄격 디코딩, 실패 시 decode_error.
    정규화는 HTML 태그 제거·script/style 제외·공백 압축·Unicode NFC뿐이며 글자·숫자·부정어·문장부호는 지우지 않습니다."""
    try:
        decoded = body.decode(charset)
    except (UnicodeDecodeError, LookupError):
        raise FetchFailure("decode_error") from None
    parser = _TextParser()
    parser.feed(decoded)
    parser.close()
    lines = [normalize(line) for line in "".join(parser.parts).split("\n")]
    return [line for line in lines if line]


def _in_order(lines, text):
    """줄들이 text 안에 순서대로 있는지(부분 확인용)."""
    position = 0
    for line in lines:
        found = text.find(line, position)
        if found < 0:
            return False
        position = found + len(line)
    return True


def excerpt_units(text_pt, rules, strip_list_markers):
    """저장 원문 발췌 → [(단위 이름, 규칙, 키, 줄 목록)]. 첫 조항 시작 앞의 줄(절 제목 등)은 "_context" 단위.
    CONAR는 발췌 때 덧붙인 목록 기호 a.~h.만 떼어 원문 표기로 되돌립니다(그 밖의 글자는 그대로)."""
    lines = [normalize(line) for line in text_pt.split("\n")]
    lines = [line for line in lines if line]
    if strip_list_markers:
        lines = [re.sub(r"^[a-h]\. ", "", line) for line in lines]
    units = [[CONTEXT_UNIT, None, None, []]]
    for line in lines:
        for rule in rules["starts"]:
            match = re.match(rule["excerpt"], line)
            if match:
                units.append([rule["label"].replace("{key}", match["key"]), rule, match["key"], [line]])
                break
        else:
            units[-1][3].append(line)
    return [tuple(unit) for unit in units if unit[3]]


def _scope(lines, rules, rule):
    """규칙의 검색 범위(예: 부속서 U). 시작 줄이 정확히 1개가 아니면 None."""
    if not rule.get("scope"):
        return 0, len(lines)
    start_pattern, end_pattern = rules["scopes"][rule["scope"]]
    starts = [index for index, line in enumerate(lines) if re.match(start_pattern, line)]
    if len(starts) != 1:
        return None
    end = next((index for index in range(starts[0] + 1, len(lines)) if re.match(end_pattern, lines[index])), len(lines))
    return starts[0], end


def locate_unit(lines, rules, rule, key):
    """본문에서 조항 단위의 [시작, 끝). 시작 줄이 없으면 'missing', 여러 개거나 범위를 못 찾으면 'ambiguous'."""
    scope = _scope(lines, rules, rule)
    if scope is None:
        return None, "ambiguous"
    low, high = scope
    pattern = re.compile(rule["page"].replace("{key}", re.escape(key)))
    starts = [index for index in range(low, high) if pattern.match(lines[index])]
    if not starts:
        return None, "missing"
    if len(starts) > 1:
        return None, "ambiguous"
    end = starts[0] + 1
    boundaries = [re.compile(value) for value in rules["boundaries"]]
    while end < high and not any(boundary.match(lines[end]) for boundary in boundaries):
        end += 1
    return (starts[0], end), None


def _evaluate_units(item, lines, rules, strip_list_markers):
    """기준 1개의 단위별 (이름, 위치 오류, 본문 텍스트, 발췌 줄, 부분 확인 검색 범위).
    위치 오류: None / missing / ambiguous / unbounded. 조항 단위의 검색 범위는 그 조항 본문,
    _context(첫 조항 앞 줄)의 본문 텍스트는 첫 조항 바로 앞의 같은 줄 수, 검색 범위는 첫 조항 앞 전체."""
    units = excerpt_units(item["excerpt"]["text_pt"], rules, strip_list_markers)
    evaluated, first_start = [], None
    for label, rule, key, unit_lines in units:
        if rule is None:
            continue
        span, error = locate_unit(lines, rules, rule, key)
        if span and first_start is None:
            first_start = span[0]
        text = " ".join(lines[span[0]:span[1]]) if span else None
        evaluated.append((label, error, text, unit_lines, text))
    if units and units[0][0] == CONTEXT_UNIT:
        context = units[0][3]
        if first_start is None or first_start < len(context):
            evaluated.insert(0, (CONTEXT_UNIT, "unbounded", None, context, None))
        else:
            evaluated.insert(0, (CONTEXT_UNIT, None, " ".join(lines[first_start - len(context):first_start]), context,
                                 " ".join(lines[:first_start])))
    return evaluated


def compare_criterion(item, lines, rules, strip_list_markers, coverage):
    """기준 1개를 조항 단위로 비교. coverage: {단위 이름: full/partial/unbounded} (2026-10-25 확보본 기준 발췌 범위).
    단위 결과: unchanged(발췌가 조항 전체였고 지금 본문 전체가 같음) / partial(발췌 문장은 그대로지만 조항 전체를 비교할 수 없음) /
    changed / missing(조항 시작 없음) / unverifiable(조항 경계 식별 불가).
    기준 결과는 missing·changed > unverifiable > partial > unchanged 순으로 정합니다."""
    page_text = " ".join(lines)
    units = {}
    for label, error, text, unit_lines, search in _evaluate_units(item, lines, rules, strip_list_markers):
        scope = coverage.get(label, "unknown")
        excerpt_text = " ".join(unit_lines)
        if error == "missing":
            outcome = "missing"
        elif error in ("ambiguous", "unbounded"):
            outcome = "unverifiable" if _in_order(unit_lines, page_text) else "changed"
        elif scope == "full":
            outcome = "unchanged" if text == excerpt_text else "changed"
        elif scope == "partial" and text == excerpt_text:
            outcome = "changed"  # 확보 당시 조항에 있던 발췌 밖 문장이 사라짐
        else:
            outcome = "partial" if _in_order(unit_lines, search) else "changed"
        units[label] = {"result": outcome, "coverage": scope}
    results = [unit["result"] for unit in units.values()]
    article_results = [unit["result"] for label, unit in units.items() if label != CONTEXT_UNIT]
    if article_results and all(result == "missing" for result in article_results):
        overall = "missing"  # 조항 시작을 하나도 못 찾음(절 제목 비교 결과와 무관)
    elif "missing" in results or "changed" in results:
        overall = "changed"
    elif "unverifiable" in results:
        overall = "unverifiable"
    elif "partial" in results or not results:
        overall = "partial"
    else:
        overall = "unchanged"
    return {"result": overall, "units": units}


def measure_coverage(criteria, lines, rules, strip_list_markers):
    """개발용: 확보 당시 본문(줄 목록)으로 각 발췌 단위가 조항 전체인지(full)·일부인지(partial)·경계를 못 찾는지(unbounded) 판정.
    발췌 문장이 그 본문에 순서대로 없으면 비교 기준으로 쓸 수 없어 CRITERIA_EVIDENCE_MISMATCH."""
    coverage = {}
    page_text = " ".join(lines)
    for item in criteria:
        result = {}
        for label, error, text, unit_lines, search in _evaluate_units(item, lines, rules, strip_list_markers):
            if error:
                if not _in_order(unit_lines, page_text):
                    raise cl.CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"{item['id']} {label}")
                result[label] = "unbounded"
            elif text == " ".join(unit_lines):
                result[label] = "full"
            elif _in_order(unit_lines, search):
                result[label] = "partial"
            else:
                raise cl.CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"{item['id']} {label}")
        coverage[item["id"]] = result
    return coverage


def read_coverage(directory):
    """활성 기준 폴더의 comparison_units.json. 없거나 손상되면 ({}, 경고)."""
    try:
        data = json.loads((Path(directory) / COVERAGE_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, "조항 비교 범위 정보(comparison_units.json)가 없어 모든 조항을 부분 확인으로만 다룹니다."
    except (OSError, ValueError):
        return {}, "조항 비교 범위 정보를 읽지 못해 모든 조항을 부분 확인으로만 다룹니다."
    coverage = data.get("coverage") if isinstance(data, dict) and data.get("schema_version") == 1 else None
    if not isinstance(coverage, dict) or not all(
            isinstance(units, dict) and all(value in COVERAGE_VALUES for value in units.values())
            for units in coverage.values()):
        return {}, "조항 비교 범위 정보 형식이 맞지 않아 모든 조항을 부분 확인으로만 다룹니다."
    return coverage, None


def _charset(headers, default):
    content_type = headers.get("Content-Type", "") if headers is not None else ""
    message = Message()
    message["Content-Type"] = content_type or "text/html"
    return message.get_content_charset() or default, message.get_content_type()


# ---------- 출처 1개 확인 ----------

def _check_source(source, criteria, policy, opener, clock, deadline, coverage=None):
    """반환: (결과 dict, 감지 기록용 본문 텍스트 또는 None). coverage: 기준 ID → 단위별 발췌 범위."""
    coverage = coverage or {}
    ids = [item["id"] for item in criteria]
    result = {"requests_used": 0, "http_status": None, "server_last_modified": None,
              "checked_criteria": [], "partially_checked_criteria": [], "unverifiable_criteria": [],
              "unchecked_criteria": ids, "changed_criteria": []}
    if policy is None or not policy.get("auto_fetch"):
        code = (policy or {}).get("deferred_code", "no_policy")
        reason = (policy or {}).get("deferred_reason", "자동 확인 정책이 없는 자료라 보류함")
        return dict(result, status=STATUS_DEFERRED, reason_code=code, reason=reason), None
    if source["excerpt_file"] is None or not criteria:
        return dict(result, status=STATUS_BASELINE_MISSING, reason_code="baseline_missing",
                    reason=REASONS["baseline_missing"]), None
    parts = urlsplit(source["url"])
    if parts.scheme != "https" or parts.hostname != policy["host"]:
        return dict(result, status=STATUS_FAILED, reason_code="url_not_allowed", reason=REASONS["url_not_allowed"]), None
    session = _Session(opener, clock, deadline)
    try:
        if policy.get("check_robots") and not _robots_allows(session, source["url"]):
            return dict(result, requests_used=session.requests, status=STATUS_DEFERRED, reason_code="robots_disallowed",
                        reason=REASONS["robots_disallowed"]), None
        status, headers, body = session.get(source["url"])
        result["requests_used"] = session.requests
        result["http_status"] = status
        result["server_last_modified"] = headers.get("Last-Modified") if headers is not None else None
        if status != 200:
            raise FetchFailure("http_error", status)
        charset, content_type = _charset(headers, policy["charset"])
        if "html" not in content_type:
            raise FetchFailure("not_html", status)
        lines = html_lines(body, charset)
        page_text = " ".join(lines)
        if not page_text or not all(normalize(marker) in page_text for marker in policy["markers"]):
            raise FetchFailure("page_unrecognized", status)
    except FetchFailure as failure:
        result["requests_used"] = session.requests
        result["http_status"] = failure.http_status or result["http_status"]
        code = failure.code
        return dict(result, status=STATUS_FAILED, reason_code=code, reason=REASONS[code]), None

    rules = UNIT_RULES[source["id"]]
    outcomes = {item["id"]: compare_criterion(item, lines, rules, policy["strip_list_markers"], coverage.get(item["id"], {}))
                for item in criteria}
    if all(outcome["result"] == "missing" for outcome in outcomes.values()):
        return dict(result, status=STATUS_FAILED, reason_code="extraction_failed", reason=REASONS["extraction_failed"]), None
    by_result = {name: [cid for cid, outcome in outcomes.items() if outcome["result"] in names]
                 for name, names in (("changed", ("changed", "missing")), ("partial", ("partial",)),
                                     ("unverifiable", ("unverifiable",)), ("unchanged", ("unchanged",)))}
    result.update(checked_criteria=by_result["unchanged"], partially_checked_criteria=by_result["partial"],
                  unverifiable_criteria=by_result["unverifiable"], unchecked_criteria=by_result["unverifiable"],
                  changed_criteria=by_result["changed"], comparison=outcomes,
                  page_text_sha256=hashlib.sha256(page_text.encode("utf-8")).hexdigest())
    if by_result["changed"]:
        return dict(result, status=STATUS_CHANGED, reason_code="change_detected", reason=REASONS["change_detected"]), page_text
    if by_result["partial"] or by_result["unverifiable"]:
        return dict(result, status=STATUS_PARTIAL, reason_code="partial_checked", reason=REASONS["partial_checked"]), None
    return dict(result, status=STATUS_NO_CHANGE, reason_code="no_change_found", reason=REASONS["no_change_found"]), None


# ---------- 전체 결과 ----------

def _active_info(loaded):
    if loaded is None:
        return None
    bundle = loaded["bundle"]
    return {
        "active_version": loaded.get("active_version"),
        "bundle_version": bundle["bundle_version"],
        "schema_version": bundle["schema_version"],
        "content_hash": bundle["content_hash"]["value"],
        "sources_retrieved_at": {source["id"]: source["retrieved_at"] for source in loaded["sources"]},
        "freshness_mode": loaded["freshness"]["mode"],
    }


def _overall(usable, statuses, unresolved):
    if not usable:
        return "not_ready"
    if unresolved or STATUS_CHANGED in statuses:
        return "change_pending_review"
    if statuses and all(status == STATUS_NO_CHANGE for status in statuses):
        return "no_change_found"
    return "partial"


def _warnings(loaded, results, unresolved, extra):
    warnings = list(extra)
    if loaded is None:
        warnings.append("사용할 수 있는 정상 기준이 없어 검수 기준이 준비되지 않았습니다.")
    for item in results:
        if item["status"] not in (STATUS_NO_CHANGE, STATUS_CHANGED):
            warnings.append(f"{item['source_id']}: {item['reason']}")
    if loaded is not None and any(item["status"] not in (STATUS_NO_CHANGE,) for item in results):
        warnings.append(f"기존 기준(버전 {loaded.get('active_version')}, {loaded['bundle']['bundle_version']})을 그대로 사용합니다. "
                        "확인하지 못한 출처의 최신성은 알 수 없습니다.")
    if unresolved:
        warnings.append("감지된 원문 변경이 검토·반영되지 않았습니다: "
                        + ", ".join(sorted({item["source_id"] for item in unresolved})))
    warnings.append("이 확인은 저장 원문 발췌와 같은 문장이 공식 페이지에 있는지 본 것이며, 공식 개정일·시행일과 대상 외 조항은 확인하지 않습니다.")
    return warnings


def _load_or_none(root):
    try:
        return cl._load_active(root), None
    except cl.CriteriaError as err:
        return None, f"활성 기준을 불러오지 못했습니다({err.code})."


def criteria_status(root=cl.DATA_ROOT):
    """네트워크 없이 활성 기준과 마지막 확인 상태를 돌려줍니다(향후 검수 실행이 호출할 경계)."""
    loaded, load_warning = _load_or_none(root)
    state = cs.read_check_state(root)
    results = []
    for source_id, policy in POLICIES.items():
        last = state["sources"].get(source_id)
        if last is None and not policy.get("auto_fetch"):
            results.append({"source_id": source_id, "status": STATUS_DEFERRED, "reason_code": policy["deferred_code"],
                            "reason": policy["deferred_reason"], "attempted_at": None, "success": False,
                            "last_success_at": None})
        elif last is None:
            results.append({"source_id": source_id, "status": STATUS_NOT_CHECKED, "reason_code": "not_checked",
                            "reason": "아직 확인 기록이 없습니다.", "attempted_at": None, "success": False,
                            "last_success_at": None})
        else:
            results.append({"source_id": source_id, "status": last.get("last_status"),
                            "reason_code": last.get("last_reason_code"), "reason": last.get("last_reason"),
                            "attempted_at": last.get("last_attempt_at"),
                            "success": last.get("last_status") in COMPARED, "last_success_at": last.get("last_success_at")})
    unresolved = state["unresolved_changes"]
    return {
        "overall": _overall(loaded is not None, [item["status"] for item in results], unresolved),
        "criteria_usable": loaded is not None,
        "active": _active_info(loaded),
        "sources": results,
        "unresolved_changes": unresolved,
        "warnings": _warnings(loaded, results, unresolved, [w for w in (load_warning,) if w] + state["warnings"]),
        "network_checked": False,
    }


def check_sources(root=cl.DATA_ROOT, opener=None, clock=time.monotonic, now=None, policies=None):
    """개발자 실행용: 고정 정책의 공식 출처를 제한 안에서 확인하고 확인 상태를 기록합니다.
    opener·clock·now·policies는 테스트용 내부 인자이며 사용자 요청 값을 받지 않습니다."""
    opener = opener or default_open
    policies = POLICIES if policies is None else policies
    attempted_at = now or cs.now_iso()
    try:
        with cs.criteria_lock(root):
            loaded, load_warning = _load_or_none(root)  # 잠금 안에서 읽어 확인 중 교체와 섞이지 않게 함
            coverage, coverage_warning = ({}, None) if loaded is None else read_coverage(
                cl.version_directory(root, loaded["active_version"]))
            state = cs.read_check_state(root)
            results = []
            deadline = clock() + TOTAL_TIMEOUT_SECONDS
            for source_id, policy in policies.items():
                source = None if loaded is None else next((s for s in loaded["sources"] if s["id"] == source_id), None)
                if source is None:
                    result = {"status": STATUS_BASELINE_MISSING, "reason_code": "baseline_missing",
                              "reason": REASONS["baseline_missing"], "requests_used": 0, "http_status": None,
                              "server_last_modified": None, "checked_criteria": [], "unchecked_criteria": [],
                              "changed_criteria": []}
                    page_text = None
                else:
                    criteria = [item for item in loaded["criteria"] if item["source_id"] == source_id]
                    result, page_text = _check_source(source, criteria, policy, opener, clock, deadline, coverage)
                previous = state["sources"].get(source_id, {})
                success = result["status"] in COMPARED
                last_success = attempted_at if success else previous.get("last_success_at")
                result.update(source_id=source_id, attempted_at=attempted_at, success=success, last_success_at=last_success)
                state["sources"][source_id] = {
                    "last_attempt_at": attempted_at, "last_status": result["status"],
                    "last_reason_code": result["reason_code"], "last_reason": result["reason"],
                    "last_success_at": last_success, "last_page_text_sha256": result.get("page_text_sha256"),
                    "server_last_modified": result["server_last_modified"],
                }
                if result["status"] == STATUS_CHANGED:
                    _record_change(root, state, source_id, attempted_at, result,
                                   page_text if policy.get("store_page_text") else None)
                logger.info("기준 출처 확인: source=%s status=%s code=%s", source_id, result["status"], result["reason_code"])
                results.append(result)
            cs.write_check_state(root, state)
    except cl.CriteriaError as err:
        if err.code != "CRITERIA_BUSY":
            raise
        status = criteria_status(root)
        status.update(overall="busy", attempted_at=attempted_at)
        status["warnings"].insert(0, cl.ERRORS["CRITERIA_BUSY"])
        return status
    unresolved = state["unresolved_changes"]
    return {
        "overall": _overall(loaded is not None, [item["status"] for item in results], unresolved),
        "criteria_usable": loaded is not None,
        "active": _active_info(loaded),
        "attempted_at": attempted_at,
        "sources": results,
        "unresolved_changes": unresolved,
        "warnings": _warnings(loaded, results, unresolved,
                              [w for w in (load_warning, coverage_warning) if w] + state["warnings"]),
        "network_checked": True,
        "limits": {"request_timeout_seconds": REQUEST_TIMEOUT_SECONDS, "total_timeout_seconds": TOTAL_TIMEOUT_SECONDS,
                   "max_requests_per_source": MAX_REQUESTS_PER_SOURCE, "max_download_bytes": MAX_DOWNLOAD_BYTES},
    }


def _record_change(root, state, source_id, detected_at, result, page_text):
    """감지 기록을 작업 폴더에 남기고 미반영 변경 목록에 추가(같은 본문·같은 기준이면 중복 추가 안 함)."""
    page_hash = result.get("page_text_sha256")
    for item in state["unresolved_changes"]:
        if item.get("source_id") == source_id and item.get("page_text_sha256") == page_hash:
            return
    detected_dir = Path(root) / cb.WORK_DIR_NAME / DETECTED_DIR_NAME
    detected_dir.mkdir(parents=True, exist_ok=True)
    name = f"{detected_at[:19].replace(':', '').replace('-', '')}_{source_id}.json"
    cb.write_json_atomic(detected_dir / name, {
        "source_id": source_id,
        "detected_at": detected_at,
        "note": "자동 감지 기록. 번역·해석 검토 전이며 활성 기준에 반영하지 않음. 공식 개정 여부를 확정한 것이 아님",
        "changed_criteria": result["changed_criteria"],
        "comparison": result.get("comparison"),
        "page_text_sha256": page_hash,
        "page_text": page_text,
    })
    state["unresolved_changes"].append({"source_id": source_id, "detected_at": detected_at,
                                        "criteria_ids": result["changed_criteria"], "page_text_sha256": page_hash,
                                        "detail_file": name})
