"""그린 클레임 검수 기준 자료 로더(feature_spec.md "검수 기준 자료 로더").

- 활성 기준 묶음을 읽고 검증해 돌려줍니다. 활성 위치는 data/criteria_state/active.json 포인터가 정하며,
  포인터가 없으면 기본 기준(data/brazil_claim_criteria/)을 씁니다(feature_spec.md "기준 자료 변경 확인과 갱신 관리").
- 이 모듈 위치 기준의 고정 경로만 읽습니다. 사용자 입력 경로를 받지 않습니다(테스트용 _load_from·_load_active는 내부 전용).
- schema 1(기존 묶음)과 schema 2(criteria_build가 만드는 묶음, 내용 해시에서 작성 시각 제외)를 지원합니다.
- 기준마다 원문 발췌(cdc_l8078_excerpt.md·conar_excerpt.md)와 검토 정리(review_criteria_ko.md)의 해당 구간을 다시 읽어
  JSON 값과 같은지 확인하고, 출처는 source_register.md의 같은 ID 행과 대조합니다.
- 공식 사이트에 접속하지 않습니다. 반환 값은 "저장된 기준 사용, 최신성 재확인 미실행" 상태입니다.
- 하나라도 잘못되면 전체를 실패로 처리합니다(일부 건너뛰기·빈 정상 결과 없음). 로그에는 오류 code만 남깁니다.
"""
import copy
import hashlib
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_ROOT = Path(__file__).resolve().parent / "data"
BASE_DIR_NAME = "brazil_claim_criteria"
DATA_DIR = DATA_ROOT / BASE_DIR_NAME          # 기본(base) 기준
VERSIONS_DIR_NAME = "criteria_versions"       # 활성화한 기준 버전들
STATE_DIR_NAME = "criteria_state"
POINTER_FILE = "active.json"
BASE_VERSION = "base"
BUNDLE_FILE = "criteria_bundle.json"
REGISTER_FILE = "source_register.md"
REVIEW_FILE = "review_criteria_ko.md"
# 활성화한 버전 폴더에 함께 보관되는 검토 기록(criteria_store.REVIEW_FILE과 같은 이름). 여기서는 업데이트 날짜만 읽습니다.
ACTIVATION_RECORD_FILE = "review.json"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCES_META_FILE = "sources_meta.json"
SUPPORTED_SCHEMA_VERSIONS = (1, 2)
VERSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
LEGAL_NATURES = ("law", "advertising_self_regulation")
FRESHNESS_STORED_ONLY = "stored_only"

ERRORS = {
    "CRITERIA_FILE_MISSING": "검수 기준 자료 파일을 찾지 못했습니다. 기준 자료 준비 상태를 확인해 주세요.",
    "CRITERIA_INVALID_JSON": "검수 기준 자료 파일을 읽지 못했습니다. 파일이 손상되었을 수 있습니다.",
    "CRITERIA_SCHEMA_UNSUPPORTED": "지원하지 않는 검수 기준 자료 형식 버전입니다.",
    "CRITERIA_INVALID": "검수 기준 자료의 필수 항목이 비었거나 형식이 맞지 않습니다.",
    "CRITERIA_HASH_MISMATCH": "검수 기준 자료의 내용 확인값이 맞지 않습니다. 자료가 바뀌었을 수 있습니다.",
    "CRITERIA_EVIDENCE_MISSING": "검수 기준의 근거 자료 파일이나 해당 조항을 찾지 못했습니다.",
    "CRITERIA_EVIDENCE_MISMATCH": "검수 기준과 근거 자료의 내용이 서로 맞지 않습니다.",
    "CRITERIA_POINTER_INVALID": "활성 검수 기준 위치 정보가 손상되었거나 가리키는 기준이 없습니다. 기준 관리 상태를 확인해 주세요.",
    "CRITERIA_BUSY": "다른 기준 확인·교체 작업이 진행 중입니다. 잠시 후 다시 시도해 주세요.",
    "CRITERIA_REVIEW_MISSING": "검토 기록이 없거나 번역·지침 검토가 끝나지 않은 후보라 활성화하지 않았습니다.",
    "CRITERIA_BUILD_FAILED": "기준 묶음을 만들지 못했습니다. 원본 자료의 누락·불일치를 확인해 주세요.",
    "CRITERIA_ACTIVATION_FAILED": "기준 교체를 마치지 못했습니다. 기존 활성 기준을 그대로 사용합니다.",
}

# review_criteria_ko.md의 칸 이름 → 기준 필드. CDC는 "### ID", CONAR 상세 기준은 "#### ID" 구간.
REVIEW_LABELS = {
    "law": {
        "원문 조항": "provisions",
        "원문 발췌": "quote_pt",
        "한국어 번역(비공식)": "translation_ko",
        "검토 활용": "review_guidance_ko",
        "적용 범위와 한계": "scope_limits_ko",
        "제품 사실 검증 필요": "evidence_needed_ko",
        "상태": "status_ko",
        "개별 개정 표기": "amendment_note_ko",
    },
    "advertising_self_regulation": {
        "조항": "provisions",
        "원문 발췌": "quote_pt",
        "한국어 번역(비공식)": "translation_ko",
        "원문 요구": "requirement_ko",
        "검토 지침": "review_guidance_ko",
        "적용 범위와 해석 한계": "scope_limits_ko",
        "제품 증빙": "evidence_needed_ko",
    },
}
REVIEW_HEADING_LEVEL = {"law": "###", "advertising_self_regulation": "####"}
TEXT_FIELDS = ("provisions", "quote_pt", "translation_ko", "requirement_ko", "review_guidance_ko", "scope_limits_ko",
               "evidence_needed_ko", "status_ko", "amendment_note_ko")
REQUIRED_TEXT_FIELDS = ("provisions", "quote_pt", "translation_ko", "review_guidance_ko", "scope_limits_ko",
                        "evidence_needed_ko")
_EXCERPT_HEADING = re.compile(r"^## ([A-Z0-9][A-Z0-9-]*) — (.+)$")
_REVIEW_HEADING = re.compile(r"^(#{3,4}) ((?:CDC|CONAR)-[A-Z0-9-]+) (.+)$")
_ID = re.compile(r"^[A-Z][A-Z0-9-]*$")
_DATETIME = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})\+09:00$")


class CriteriaError(Exception):
    """기준 자료 로드 실패. to_dict()는 사용자용 고정 문장만, detail은 개발자 진단용(기준 ID·필드 이름)."""

    def __init__(self, code, detail=""):
        self.code = code
        self.message = ERRORS[code]
        self.detail = detail
        super().__init__(code)

    def to_dict(self):
        return {"code": self.code, "message": self.message}


def load_criteria():
    """활성 기준 묶음을 검증해 돌려줍니다. 실패하면 CriteriaError."""
    return _load_active(DATA_ROOT)


def read_pointer(root):
    """내부: 활성 포인터 dict 또는 None(파일 없음 = base). 손상되면 CRITERIA_POINTER_INVALID."""
    path = Path(root) / STATE_DIR_NAME / POINTER_FILE
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        raise CriteriaError("CRITERIA_POINTER_INVALID", "read") from None
    try:
        pointer = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise CriteriaError("CRITERIA_POINTER_INVALID", "json") from None
    if not isinstance(pointer, dict) or not isinstance(pointer.get("active"), str):
        raise CriteriaError("CRITERIA_POINTER_INVALID", "active")
    return pointer


def version_directory(root, version):
    """내부: 버전 이름(base 또는 버전 ID) → 폴더. 형식이 틀리면 CRITERIA_POINTER_INVALID."""
    if version == BASE_VERSION:
        return Path(root) / BASE_DIR_NAME
    if not isinstance(version, str) or not VERSION_ID.match(version) or version.endswith(".partial"):
        raise CriteriaError("CRITERIA_POINTER_INVALID", "version id")
    return Path(root) / VERSIONS_DIR_NAME / version


def _load_active(root):
    """내부·테스트 전용: root(data 폴더)의 포인터가 가리키는 활성 기준을 검증합니다.
    포인터가 손상되었거나 폴더가 없으면 base로 몰래 돌아가지 않고 실패합니다."""
    try:
        pointer = read_pointer(root)
        version = BASE_VERSION if pointer is None else pointer["active"]
        directory = version_directory(root, version)
        if not directory.is_dir():
            raise CriteriaError("CRITERIA_POINTER_INVALID", "missing directory")
    except CriteriaError as err:
        logger.warning("검수 기준 자료 로드 실패: code=%s", err.code)
        raise
    result = _load_from(directory)
    result["active_version"] = version
    result["criteria_updated_on"] = read_updated_on(directory)
    return result


def read_updated_on(directory):
    """그 버전 기준 자료가 실제로 갱신된 날짜(YYYY-MM-DD). 활성화 때 담당자가 review.json에 적은 값만 쓰며,
    base처럼 기록이 없거나 형식이 맞지 않으면 None(화면·PDF "업데이트 날짜 미기록"). 확보일·생성일·파일 시각으로 채우지 않습니다."""
    try:
        record = json.loads((Path(directory) / ACTIVATION_RECORD_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = record.get("criteria_updated_on") if isinstance(record, dict) else None
    return value if isinstance(value, str) and _DATE.match(value) and _valid_date(value) else None


def _valid_date(value):
    from datetime import date
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _load_from(directory):
    """내부·테스트 전용: 지정 폴더의 기준 묶음을 검증합니다. 사용자 입력 경로에 쓰지 않습니다."""
    try:
        return _load(Path(directory))
    except CriteriaError as err:
        logger.warning("검수 기준 자료 로드 실패: code=%s", err.code)
        raise


def _read_text(directory, name):
    """UTF-8 텍스트(줄바꿈 LF 정규화). 없으면 CRITERIA_EVIDENCE_MISSING."""
    if not isinstance(name, str) or not name or Path(name).name != name:
        raise CriteriaError("CRITERIA_INVALID", "file name")
    try:
        raw = (directory / name).read_bytes()
    except OSError:
        raise CriteriaError("CRITERIA_EVIDENCE_MISSING", name) from None
    try:
        return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", name) from None


def text_sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bundle_hash(bundle):
    """내용 해시(정렬 키·UTF-8 JSON의 SHA-256). schema 1: content_hash를 뺀 묶음 전체.
    schema 2: 작성 시각(bundle_created_at)도 빼서 같은 입력이면 같은 해시가 되게 함."""
    excluded = {"content_hash"} if bundle.get("schema_version") == 1 else {"content_hash", "bundle_created_at"}
    body = {key: value for key, value in bundle.items() if key not in excluded}
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------- md 구간 읽기 ----------

def excerpt_sections(text):
    """원문 발췌 파일 → {기준 ID: (머리글, 인용문 텍스트)}. 인용문은 '> ' 접두를 떼고 줄 단위로 잇습니다."""
    sections, current, lines = {}, None, []

    def close():
        if current is None:
            return
        body = list(lines)
        while body and body[0] == "":
            body.pop(0)
        while body and body[-1] == "":
            body.pop()
        if current[0] in sections:
            raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"duplicate excerpt {current[0]}")
        sections[current[0]] = (current[1], "\n".join(body))

    for line in text.split("\n"):
        match = _EXCERPT_HEADING.match(line)
        if match or line.startswith("## ") or line.startswith("# "):
            close()
            current, lines = ((match.group(1), line) if match else None), []
            continue
        if current is None:
            continue
        if line == ">":
            lines.append("")
        elif line.startswith("> "):
            lines.append(line[2:])
        elif line.strip():
            raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"non-quote line in {current[0]}")
    close()
    return sections


def review_sections(text):
    """검토 정리 파일 → {(머리글 수준, 기준 ID): (머리글, 제목, {칸 이름: 값})}. 하위 목록은 줄바꿈으로 잇습니다."""
    sections, current = {}, None
    for line in text.split("\n"):
        if line.startswith("#"):
            match = _REVIEW_HEADING.match(line)
            current = None
            if match:
                key = (match.group(1), match.group(2))
                if key in sections:
                    raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"duplicate review {key[1]}")
                current = {"heading": line, "title": match.group(3), "fields": {}, "last": None}
                sections[key] = current
            continue
        if current is None or not line.strip():
            continue
        fields = current["fields"]
        if line.startswith("- "):
            label, sep, value = line[2:].partition(": ")
            if not sep:
                label, value = line[2:], None
            if label in fields:
                raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"duplicate field {label}")
            fields[label] = value
            current["last"] = label
        elif line.startswith("  - ") and current["last"] is not None:
            label = current["last"]
            fields[label] = line[4:] if fields[label] is None else fields[label] + "\n" + line[4:]
        else:
            raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", "unexpected review line")
    return {key: (value["heading"], value["title"], value["fields"]) for key, value in sections.items()}


def register_time_iso(value):
    """source_register.md의 조회 시각 칸("YYYY-MM-DD HH:MM:SS", Asia/Seoul) → ISO 문자열. 형식이 다르면 None."""
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})", value)
    return f"{match.group(1)}T{match.group(2)}+09:00" if match else None


def sources_from_meta(meta, rows):
    """sources_meta.json + source_register.md 행 → 묶음의 sources 목록(schema 2 생성·검증 공용).
    이름·기관·조회 시각·버전 단서는 출처 목록 행(열: ID|자료|기관|구분|URL|조회 시각|결과|버전·날짜 단서|…)에서 그대로 읽습니다."""
    if not isinstance(meta, dict) or meta.get("schema_version") != 1 or not isinstance(meta.get("sources"), list):
        raise CriteriaError("CRITERIA_INVALID", "sources_meta")
    sources = []
    for index, item in enumerate(meta["sources"]):
        where = f"sources_meta[{index}]"
        source_id = _field(item, "id", str, where)
        row = rows.get(source_id)
        if row is None:
            raise CriteriaError("CRITERIA_EVIDENCE_MISSING", source_id)
        cells = [cell.strip() for cell in row.split("|")]
        retrieved = register_time_iso(cells[6]) if len(cells) > 8 else None
        if retrieved is None:
            raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"{source_id} register row")
        sources.append({
            "id": source_id,
            "title": cells[2],
            "authority": cells[3],
            "legal_nature": _field(item, "legal_nature", str, where),
            "url": _field(item, "url", str, where),
            "retrieved_at": retrieved,
            "version_clue": cells[8],
            "official_edition": _field(item, "official_edition", str, where, nullable=True),
            "dates": _field(item, "dates", dict, where),
            "role": _field(item, "role", str, where),
            "excerpt_file": _field(item, "excerpt_file", str, where, nullable=True),
            "supporting_excerpt_ids": _field(item, "supporting_excerpt_ids", list, where),
            "usage_rights": _field(item, "usage_rights", dict, where),
        })
    return sources


def register_rows(text):
    """source_register.md 표 → {SRC ID: 행 문자열}."""
    rows = {}
    for line in text.split("\n"):
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) > 2 and cells[1].startswith("SRC-"):
            rows[cells[1]] = line
    return rows


# ---------- 검증 ----------

def _check(value, kinds, where, nullable=False):
    if value is None and nullable:
        return
    kinds = kinds if isinstance(kinds, tuple) else (kinds,)
    if isinstance(value, bool) and bool not in kinds:  # bool은 int의 하위 타입이라 따로 막음
        raise CriteriaError("CRITERIA_INVALID", where)
    if not isinstance(value, kinds) or (isinstance(value, str) and not value.strip()):
        raise CriteriaError("CRITERIA_INVALID", where)


def _field(obj, name, kinds, where, nullable=False):
    if not isinstance(obj, dict) or name not in obj:
        raise CriteriaError("CRITERIA_INVALID", f"{where}.{name}")
    _check(obj[name], kinds, f"{where}.{name}", nullable)
    return obj[name]


def _register_time(value, where):
    match = _DATETIME.match(value)
    if not match:
        raise CriteriaError("CRITERIA_INVALID", where)
    return f"{match.group(1)} {match.group(2)}"


def _load(directory):
    try:
        raw = (directory / BUNDLE_FILE).read_bytes()
    except OSError:
        raise CriteriaError("CRITERIA_FILE_MISSING") from None
    try:
        bundle = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise CriteriaError("CRITERIA_INVALID_JSON") from None
    if not isinstance(bundle, dict):
        raise CriteriaError("CRITERIA_INVALID_JSON")
    version = bundle.get("schema_version")
    if isinstance(version, bool) or version not in SUPPORTED_SCHEMA_VERSIONS:
        raise CriteriaError("CRITERIA_SCHEMA_UNSUPPORTED")

    for name in ("bundle_id", "bundle_version", "bundle_version_note", "bundle_created_at", "bundle_created_note"):
        _field(bundle, name, str, "bundle")
    freshness = _field(bundle, "freshness", dict, "bundle")
    if _field(freshness, "mode", str, "freshness") != FRESHNESS_STORED_ONLY:
        raise CriteriaError("CRITERIA_INVALID", "freshness.mode")
    _field(freshness, "rechecked_at", str, "freshness", nullable=True)
    _field(freshness, "note", str, "freshness")
    content_hash = _field(bundle, "content_hash", dict, "bundle")
    if _field(content_hash, "algorithm", str, "content_hash") != "sha256":
        raise CriteriaError("CRITERIA_SCHEMA_UNSUPPORTED")
    _field(content_hash, "value", str, "content_hash")
    _field(content_hash, "note", str, "content_hash")
    if bundle_hash(bundle) != content_hash["value"]:
        raise CriteriaError("CRITERIA_HASH_MISMATCH")

    # 근거 파일: 존재·해시
    texts = {}
    evidence = _field(bundle, "evidence_files", list, "bundle")
    if not evidence:
        raise CriteriaError("CRITERIA_INVALID", "evidence_files")
    for index, item in enumerate(evidence):
        name = _field(item, "file", str, f"evidence_files[{index}]")
        _field(item, "role", str, f"evidence_files[{index}]")
        digest = _field(item, "sha256", str, f"evidence_files[{index}]")
        if name in texts:
            raise CriteriaError("CRITERIA_INVALID", f"duplicate evidence {name}")
        texts[name] = _read_text(directory, name)
        if text_sha256(texts[name]) != digest:
            raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", name)
    required = (REGISTER_FILE, REVIEW_FILE) + ((SOURCES_META_FILE,) if version >= 2 else ())
    for name in required:
        if name not in texts:
            raise CriteriaError("CRITERIA_INVALID", f"evidence_files missing {name}")

    # 자료(출처). schema 2는 sources가 sources_meta.json + 출처 목록 행으로 다시 만든 값과 같아야 함
    rows = register_rows(texts[REGISTER_FILE])
    if version >= 2:
        try:
            meta = json.loads(texts[SOURCES_META_FILE])
        except ValueError:
            raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", SOURCES_META_FILE) from None
        if sources_from_meta(meta, rows) != bundle.get("sources"):
            raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", "sources vs sources_meta")
    sources = {}
    source_list = _field(bundle, "sources", list, "bundle")
    if not source_list:
        raise CriteriaError("CRITERIA_INVALID", "sources")
    for index, source in enumerate(source_list):
        where = f"sources[{index}]"
        source_id = _field(source, "id", str, where)
        if not _ID.match(source_id) or source_id in sources:
            raise CriteriaError("CRITERIA_INVALID", f"{where}.id")
        for name in ("authority", "title", "url", "retrieved_at", "version_clue", "role"):
            _field(source, name, str, where)
        if _field(source, "legal_nature", str, where) not in LEGAL_NATURES:
            raise CriteriaError("CRITERIA_INVALID", f"{where}.legal_nature")
        _field(source, "official_edition", str, where, nullable=True)
        _field(source, "dates", dict, where)
        rights = _field(source, "usage_rights", dict, where)
        _field(rights, "status", str, f"{where}.usage_rights")
        _field(rights, "note", str, f"{where}.usage_rights")
        excerpt_file = _field(source, "excerpt_file", str, where, nullable=True)
        if excerpt_file is not None and excerpt_file not in texts:
            raise CriteriaError("CRITERIA_INVALID", f"{where}.excerpt_file")
        supporting = _field(source, "supporting_excerpt_ids", list, where)
        if supporting and excerpt_file is None:
            raise CriteriaError("CRITERIA_INVALID", f"{where}.supporting_excerpt_ids")
        for value in supporting:
            _check(value, str, f"{where}.supporting_excerpt_ids")
        row = rows.get(source_id)
        if row is None:
            raise CriteriaError("CRITERIA_EVIDENCE_MISSING", source_id)
        if (source["url"] not in row or _register_time(source["retrieved_at"], f"{where}.retrieved_at") not in row
                or source["version_clue"] not in row):
            raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", source_id)
        sources[source_id] = source

    # 기준
    criteria = _field(bundle, "criteria", list, "bundle")
    if not criteria:
        raise CriteriaError("CRITERIA_INVALID", "criteria empty")
    parsed_excerpts = {name: excerpt_sections(text) for name, text in texts.items() if name.endswith("_excerpt.md")}
    review = review_sections(texts[REVIEW_FILE])
    seen = set()
    for index, item in enumerate(criteria):
        _check_criterion(item, index, seen, sources, parsed_excerpts, review)
    # 근거 파일의 모든 구간이 기준 또는 자료의 보조 발췌(예: 시행 조항)로 설명되어야 함(새 구간이 조용히 빠지지 않게)
    for source in sources.values():
        for supporting_id in source["supporting_excerpt_ids"]:
            if supporting_id in seen or supporting_id not in parsed_excerpts[source["excerpt_file"]]:
                raise CriteriaError("CRITERIA_EVIDENCE_MISSING", f"{source['id']} supporting {supporting_id}")
    covered = seen | {value for source in sources.values() for value in source["supporting_excerpt_ids"]}
    for name, sections in parsed_excerpts.items():
        if set(sections) - covered:
            raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"{name} uncovered excerpt")
    if {criterion_id for _, criterion_id in review} - seen:
        raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", "uncovered review section")

    result = copy.deepcopy(bundle)
    return {
        "status": "ready",
        "bundle": {key: result[key] for key in ("bundle_id", "bundle_version", "bundle_version_note", "schema_version",
                                                 "bundle_created_at", "bundle_created_note", "content_hash")},
        "freshness": result["freshness"],
        "sources": result["sources"],
        "criteria": result["criteria"],
        "counts": {
            "criteria": len(criteria),
            **{nature: sum(1 for item in criteria if item["legal_nature"] == nature) for nature in LEGAL_NATURES},
        },
    }


def _check_criterion(item, index, seen, sources, parsed_excerpts, review):
    where = f"criteria[{index}]"
    criterion_id = _field(item, "id", str, where)
    if not _ID.match(criterion_id) or criterion_id in seen:
        raise CriteriaError("CRITERIA_INVALID", f"{where}.id")
    seen.add(criterion_id)
    where = criterion_id
    source = sources.get(_field(item, "source_id", str, where))
    if source is None:
        raise CriteriaError("CRITERIA_INVALID", f"{where}.source_id")
    nature = _field(item, "legal_nature", str, where)
    if nature != source["legal_nature"]:
        raise CriteriaError("CRITERIA_INVALID", f"{where}.legal_nature")
    _field(item, "title_ko", str, where)
    if _field(item, "translation_official", bool, where) is not False:
        raise CriteriaError("CRITERIA_INVALID", f"{where}.translation_official")
    for name in TEXT_FIELDS:
        _field(item, name, str, where, nullable=name not in REQUIRED_TEXT_FIELDS)

    # 원문 발췌 구간
    excerpt = _field(item, "excerpt", dict, where)
    excerpt_file = _field(excerpt, "file", str, f"{where}.excerpt")
    if excerpt_file != source["excerpt_file"] or excerpt_file not in parsed_excerpts:
        raise CriteriaError("CRITERIA_INVALID", f"{where}.excerpt.file")
    heading = _field(excerpt, "heading", str, f"{where}.excerpt")
    text_pt = _field(excerpt, "text_pt", str, f"{where}.excerpt")
    found = parsed_excerpts[excerpt_file].get(criterion_id)
    if found is None:
        raise CriteriaError("CRITERIA_EVIDENCE_MISSING", f"{where} excerpt")
    if found != (heading, text_pt):
        raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"{where} excerpt")
    if not _quote_parts_in(item["quote_pt"], text_pt):
        raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"{where} quote_pt")

    # 검토 정리 구간: 칸마다 같은 문장인지
    review_ref = _field(item, "review", dict, where)
    if _field(review_ref, "file", str, f"{where}.review") != REVIEW_FILE:
        raise CriteriaError("CRITERIA_INVALID", f"{where}.review.file")
    found = review.get((REVIEW_HEADING_LEVEL[nature], criterion_id))
    if found is None:
        raise CriteriaError("CRITERIA_EVIDENCE_MISSING", f"{where} review")
    heading, title, fields = found
    if _field(review_ref, "heading", str, f"{where}.review") != heading or item["title_ko"] != title:
        raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"{where} review heading")
    labels = REVIEW_LABELS[nature]
    unknown = set(fields) - set(labels)
    if unknown:
        raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"{where} unknown review field")
    for label, name in labels.items():
        if item[name] != fields.get(label):
            raise CriteriaError("CRITERIA_EVIDENCE_MISMATCH", f"{where}.{name}")


def _quote_parts_in(quote, text_pt):
    """검토 정리의 '원문 발췌'는 큰따옴표로 감싼 문장 1~2개(+ 한국어 보충 설명)다.
    따옴표 안 문장을 생략 표시(...)로 나눈 조각이 모두 원문 발췌 구간에 그대로 있어야 합니다."""
    parts = re.findall(r'"([^"]+)"', quote)
    chunks = [chunk.strip(" ,") for part in parts for chunk in part.split("...") if chunk.strip(" ,.")]
    return bool(chunks) and all(chunk in text_pt for chunk in chunks)
