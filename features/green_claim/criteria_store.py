"""기준 상태·후보·교체 관리(feature_spec.md "기준 자료 변경 확인과 갱신 관리" — 교체·복구·동시 실행).

- 잠금: data/criteria_state/criteria.lock 배타 생성. 최대 LOCK_WAIT_SECONDS 대기 후 CRITERIA_BUSY.
  잠금 시각이 LOCK_STALE_SECONDS보다 오래되면 남은 잠금으로 보고 지운 뒤 1회 다시 시도합니다.
  같은 컴퓨터·같은 폴더의 프로세스 사이만 대상이며, 네트워크 드라이브·여러 서버 간 동시성은 보장하지 않습니다.
- 활성화: 검토 기록·후보 검증 → criteria_versions/<ID>.partial 복사 → 복사본 재검증 → 폴더 이름 변경 →
  active.json 포인터를 임시 파일 작성 후 os.replace(포인터 교체만 원자적). 중간 실패 시 포인터는 그대로라 기존 기준 유지.
- 버전 폴더는 만든 뒤 바꾸지 않습니다. 사용자 파일·문구·AI 응답·개인정보는 저장하지 않습니다.
"""
import json
import os
import shutil
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from features.green_claim import criteria_build as cb
from features.green_claim import criteria_loader as cl

LOCK_FILE = "criteria.lock"
CHECK_STATE_FILE = "check_state.json"
REVIEW_FILE = "review.json"
LOCK_WAIT_SECONDS = 5.0
LOCK_POLL_SECONDS = 0.2
LOCK_STALE_SECONDS = 600.0
# comparison_units.json: 조항 단위 비교 범위(criteria_check). 원문 발췌를 고치면 검토자가 확보본 기준으로 다시 판정해야 함
CANDIDATE_FILES = ("cdc_l8078_excerpt.md", "conar_excerpt.md", cl.REVIEW_FILE, cl.REGISTER_FILE, cl.SOURCES_META_FILE,
                   "comparison_units.json")
REVIEW_REQUIRED_TRUE = ("translation_reviewed", "guidance_reviewed")


def now_iso():
    return datetime.now(cb.KST).replace(microsecond=0).isoformat()


def state_dir(root=cl.DATA_ROOT):
    path = Path(root) / cl.STATE_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------- 잠금 ----------

@contextmanager
def criteria_lock(root=cl.DATA_ROOT, wait=LOCK_WAIT_SECONDS, stale=LOCK_STALE_SECONDS):
    """확인·교체 작업 잠금. 얻지 못하면 CRITERIA_BUSY. 성공·실패 모두 잠금 파일을 지웁니다."""
    path = state_dir(root) / LOCK_FILE
    deadline = time.monotonic() + wait
    broke_stale = False
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if not broke_stale and _lock_age(path) > stale:
                broke_stale = True
                try:
                    path.unlink()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise cl.CriteriaError("CRITERIA_BUSY") from None
            time.sleep(LOCK_POLL_SECONDS)
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "created": time.time()}).encode("ascii"))
    finally:
        os.close(fd)
    try:
        yield
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def _lock_age(path):
    try:
        created = json.loads(path.read_text(encoding="ascii"))["created"]
        return time.time() - float(created)
    except (OSError, ValueError, KeyError, TypeError):
        try:
            return time.time() - path.stat().st_mtime  # 내용이 없거나 깨진 잠금은 파일 시각으로 판단
        except OSError:
            return 0.0


def force_unlock(root=cl.DATA_ROOT):
    """개발용: 남은 잠금 파일 삭제(다른 작업이 실제로 진행 중이 아님을 사람이 확인한 뒤 사용)."""
    path = Path(root) / cl.STATE_DIR_NAME / LOCK_FILE
    if path.exists():
        path.unlink()
        return True
    return False


# ---------- 확인 상태 ----------

def read_check_state(root=cl.DATA_ROOT):
    """마지막 확인 상태. 없거나 손상되면 빈 상태(손상은 warnings에 표시)."""
    path = Path(root) / cl.STATE_DIR_NAME / CHECK_STATE_FILE
    empty = {"schema_version": 1, "sources": {}, "unresolved_changes": [], "warnings": []}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return empty
    except (OSError, ValueError):
        empty["warnings"].append("확인 상태 파일을 읽지 못해 이전 확인 기록 없이 진행합니다.")
        return empty
    if not isinstance(state, dict) or not isinstance(state.get("sources"), dict):
        empty["warnings"].append("확인 상태 파일 형식이 맞지 않아 이전 확인 기록 없이 진행합니다.")
        return empty
    state.setdefault("unresolved_changes", [])
    state["warnings"] = []
    return state


def write_check_state(root, state):
    data = {key: value for key, value in state.items() if key != "warnings"}
    cb.write_json_atomic(state_dir(root) / CHECK_STATE_FILE, data)


# ---------- 후보 ----------

def prepare_candidate(name, root=cl.DATA_ROOT):
    """개발용: 현재 활성 기준의 저장 자료(md·sources_meta)를 새 후보 폴더로 복사합니다. 묶음·검토 기록은 복사하지 않습니다."""
    target = cb.candidate_directory(name, root)
    if target.exists():
        raise cl.CriteriaError("CRITERIA_INVALID", "candidate exists")
    pointer = cl.read_pointer(root)
    source = cl.version_directory(root, cl.BASE_VERSION if pointer is None else pointer["active"])
    target.mkdir(parents=True)
    for name_ in CANDIDATE_FILES:
        if not (source / name_).is_file():
            shutil.rmtree(target, ignore_errors=True)
            raise cl.CriteriaError("CRITERIA_EVIDENCE_MISSING", name_)
        shutil.copy2(source / name_, target / name_)
    return target


def read_review(directory):
    """후보의 검토 기록(review.json). 사람이 작성한 개발용 파일이며 사용자 요청 필드가 아닙니다.
    필수: reviewed_by·reviewed_at·scope(비어 있지 않은 문자열), translation_reviewed·guidance_reviewed가 true,
    criteria_updated_on(이 기준 자료가 실제로 갱신된 날짜 YYYY-MM-DD, 화면·PDF의 "기준 자료 업데이트 날짜")."""
    try:
        review = json.loads((Path(directory) / REVIEW_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise cl.CriteriaError("CRITERIA_REVIEW_MISSING") from None
    if not isinstance(review, dict):
        raise cl.CriteriaError("CRITERIA_REVIEW_MISSING")
    for name in ("reviewed_by", "reviewed_at", "scope"):
        if not isinstance(review.get(name), str) or not review[name].strip():
            raise cl.CriteriaError("CRITERIA_REVIEW_MISSING", name)
    for name in REVIEW_REQUIRED_TRUE:
        if review.get(name) is not True:
            raise cl.CriteriaError("CRITERIA_REVIEW_MISSING", name)
    updated = review.get("criteria_updated_on")
    if not isinstance(updated, str) or not cl._DATE.match(updated) or not cl._valid_date(updated):
        raise cl.CriteriaError("CRITERIA_REVIEW_MISSING", "criteria_updated_on")
    rechecked = review.get("sources_rechecked", [])
    if not isinstance(rechecked, list) or not all(isinstance(value, str) for value in rechecked):
        raise cl.CriteriaError("CRITERIA_REVIEW_MISSING", "sources_rechecked")
    return review


def validate_candidate(name, root=cl.DATA_ROOT):
    """개발용: 후보 묶음 로더 검증 + 검토 기록 상태. 검토 기록이 없어도 검증 결과는 돌려줍니다(활성화는 거부)."""
    directory = cb.candidate_directory(name, root)
    loaded = cl._load_from(directory)
    try:
        review = read_review(directory)
        review_status = {"ok": True, "reviewed_by": review["reviewed_by"], "reviewed_at": review["reviewed_at"]}
    except cl.CriteriaError as err:
        review_status = {"ok": False, "reason": err.detail or "review.json 없음"}
    return {"bundle": loaded["bundle"], "counts": loaded["counts"], "review": review_status}


# ---------- 활성화·되돌리기 ----------

def _versions_dir(root):
    return Path(root) / cl.VERSIONS_DIR_NAME


def _cleanup_partials(root):
    versions = _versions_dir(root)
    if versions.is_dir():
        for path in versions.glob("*.partial"):
            shutil.rmtree(path, ignore_errors=True)


def _write_pointer(root, active, previous, extra):
    pointer = {"active": active, "previous": previous, "activated_at": now_iso(), **extra}
    cb.write_json_atomic(state_dir(root) / cl.POINTER_FILE, pointer)
    return pointer


def activate_candidate(name, root=cl.DATA_ROOT):
    """개발용: 검토 기록이 있고 검증을 통과한 후보만 새 버전으로 활성화합니다. 실패 시 기존 활성 기준 유지."""
    directory = cb.candidate_directory(name, root)
    with criteria_lock(root):
        review = read_review(directory)
        loaded = cl._load_from(directory)
        if loaded["bundle"]["schema_version"] < 2:
            raise cl.CriteriaError("CRITERIA_INVALID", "candidate must be schema 2")
        content_hash = loaded["bundle"]["content_hash"]["value"]
        version_id = f"{loaded['bundle']['bundle_version']}-{content_hash[:12]}"
        if not cl.VERSION_ID.match(version_id):
            raise cl.CriteriaError("CRITERIA_INVALID", "version id")
        pointer = cl.read_pointer(root)
        current = cl.BASE_VERSION if pointer is None else pointer["active"]
        if current == version_id:
            raise cl.CriteriaError("CRITERIA_ACTIVATION_FAILED", "already active")
        target = cl.version_directory(root, version_id)
        _cleanup_partials(root)
        try:
            if target.exists():
                if cl._load_from(target)["bundle"]["content_hash"]["value"] != content_hash:
                    raise cl.CriteriaError("CRITERIA_ACTIVATION_FAILED", "version exists with other content")
            else:
                partial = target.with_name(target.name + ".partial")
                partial.mkdir(parents=True)
                for file_name in CANDIDATE_FILES + (cl.BUNDLE_FILE, REVIEW_FILE):
                    shutil.copy2(directory / file_name, partial / file_name)
                cl._load_from(partial)
                os.rename(partial, target)
            new_pointer = _write_pointer(root, version_id, current, {
                "content_hash": content_hash,
                "review": {key: review[key] for key in ("reviewed_by", "reviewed_at", "scope", "criteria_updated_on")},
            })
        except cl.CriteriaError:
            _cleanup_partials(root)
            raise
        except OSError:
            _cleanup_partials(root)
            raise cl.CriteriaError("CRITERIA_ACTIVATION_FAILED", "file operation") from None
        # 검토에서 다시 확인했다고 적은 출처의 미반영 변경 경고는 해소
        rechecked = set(review.get("sources_rechecked", []))
        if rechecked:
            state = read_check_state(root)
            state["unresolved_changes"] = [item for item in state["unresolved_changes"]
                                           if item.get("source_id") not in rechecked]
            write_check_state(root, state)
        return new_pointer


def rollback(root=cl.DATA_ROOT):
    """개발용: 포인터의 previous 버전을 검증한 뒤 그 버전으로 되돌립니다(base 포함)."""
    with criteria_lock(root):
        pointer = cl.read_pointer(root)
        if pointer is None or not isinstance(pointer.get("previous"), str):
            raise cl.CriteriaError("CRITERIA_POINTER_INVALID", "no previous")
        previous = pointer["previous"]
        directory = cl.version_directory(root, previous)
        cl._load_from(directory)
        try:
            return _write_pointer(root, previous, pointer["active"], {"rolled_back": True})
        except OSError:
            raise cl.CriteriaError("CRITERIA_ACTIVATION_FAILED", "pointer write") from None
