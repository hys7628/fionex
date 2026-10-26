"""기준 묶음 생성(feature_spec.md "기준 자료 변경 확인과 갱신 관리" — 묶음 생성).

- 입력: 후보 폴더의 저장 자료(원문 발췌 md 2개, review_criteria_ko.md, source_register.md, sources_meta.json). 웹 조회와 분리.
- 텍스트는 md의 해당 칸·구간을 그대로 옮깁니다(새 번역·해석 없음). 기준 ID·순서는 원문 발췌 파일의 구간 순서 그대로.
- 출력: 같은 폴더의 criteria_bundle.json(schema 2). 임시 파일 작성 후 교체하고, 바로 criteria_loader 검증을 적용합니다.
  검증에 실패하면 만든 묶음을 지우고 CRITERIA_BUILD_FAILED(부분 결과를 정상으로 남기지 않음).
- 기본 기준·활성화된 버전 폴더에는 쓰지 않습니다(후보 작업 폴더만). 같은 입력·같은 bundle_version이면 content_hash가 같습니다.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from features.green_claim import criteria_loader as cl

SCHEMA_VERSION = 2
BUNDLE_ID = "green_claim.brazil_claim_criteria"
EVIDENCE_ROLES = {
    "cdc_l8078_excerpt.md": "CDC 포르투갈어 원문 발췌",
    "conar_excerpt.md": "CONAR 포르투갈어 원문 발췌",
    cl.REVIEW_FILE: "한국어 비공식 번역·서비스 검토 지침",
    cl.REGISTER_FILE: "출처·조회 시각·버전 단서·사용권",
    cl.SOURCES_META_FILE: "자료별 메타데이터(법적 성격·역할·판·날짜·사용권 메모)",
}
WORK_DIR_NAME = "criteria_work"
CANDIDATES_DIR_NAME = "candidates"
KST = timezone(timedelta(hours=9))


def candidates_dir(root=cl.DATA_ROOT):
    return Path(root) / WORK_DIR_NAME / CANDIDATES_DIR_NAME


def candidate_directory(name, root=cl.DATA_ROOT):
    """후보 이름 → 후보 폴더(작업 폴더 안만 허용)."""
    if not isinstance(name, str) or not cl.VERSION_ID.match(name) or name.endswith(".partial"):
        raise cl.CriteriaError("CRITERIA_INVALID", "candidate name")
    return candidates_dir(root) / name


def compose_bundle(directory, bundle_version, created_at):
    """저장 자료 → 묶음 dict(schema 2). 원본이 없거나 맞지 않으면 CRITERIA_BUILD_FAILED."""
    try:
        texts = {name: cl._read_text(directory, name) for name in EVIDENCE_ROLES}
        meta = json.loads(texts[cl.SOURCES_META_FILE])
        rows = cl.register_rows(texts[cl.REGISTER_FILE])
        sources = cl.sources_from_meta(meta, rows)
        compared = {item["id"]: item.get("criteria_compared_with_source_id") for item in meta["sources"]}
        review = cl.review_sections(texts[cl.REVIEW_FILE])
        criteria = []
        for source in sources:
            if source["excerpt_file"] is None:
                continue
            supporting = set(source["supporting_excerpt_ids"])
            nature = source["legal_nature"]
            for criterion_id, (heading, text_pt) in cl.excerpt_sections(texts[source["excerpt_file"]]).items():
                if criterion_id in supporting:
                    continue  # 예: CDC-118 시행 조항(검토 기준 항목 없음, 자료의 보조 발췌)
                found = review.get((cl.REVIEW_HEADING_LEVEL[nature], criterion_id))
                if found is None:
                    raise cl.CriteriaError("CRITERIA_BUILD_FAILED", f"{criterion_id} review missing")
                review_heading, title, fields = found
                item = {
                    "id": criterion_id,
                    "source_id": source["id"],
                    "legal_nature": nature,
                    "title_ko": title,
                    "excerpt": {"file": source["excerpt_file"], "heading": heading, "text_pt": text_pt},
                    "review": {"file": cl.REVIEW_FILE, "heading": review_heading},
                    "translation_official": False,
                }
                if compared.get(source["id"]):
                    item["compared_with_source_id"] = compared[source["id"]]
                for name in cl.TEXT_FIELDS:
                    item[name] = None
                for label, name in cl.REVIEW_LABELS[nature].items():
                    item[name] = fields.get(label)
                criteria.append(item)
    except cl.CriteriaError as err:
        if err.code == "CRITERIA_BUILD_FAILED":
            raise
        raise cl.CriteriaError("CRITERIA_BUILD_FAILED", f"{err.code} {err.detail}") from None
    except (ValueError, KeyError, TypeError):
        raise cl.CriteriaError("CRITERIA_BUILD_FAILED", "sources_meta") from None
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": BUNDLE_ID,
        "bundle_version": bundle_version,
        "bundle_version_note": "자체 기준 묶음 버전. 공식 법령·코드의 판·버전이 아님",
        "bundle_created_at": created_at,
        "bundle_created_note": "이 묶음 파일을 저장 자료로 만든 시각. 공식 자료 조회 시각(sources[].retrieved_at)이 아니며 내용 해시에 포함하지 않음",
        "freshness": {"mode": cl.FRESHNESS_STORED_ONLY, "rechecked_at": None,
                      "note": "저장된 기준 사용, 공식 출처 최신성 재확인 미실행. 조회 시각 이후의 개정 여부는 모름"},
        "evidence_files": [{"file": name, "role": role, "sha256": cl.text_sha256(texts[name])}
                           for name, role in EVIDENCE_ROLES.items()],
        "sources": sources,
        "criteria": criteria,
    }
    bundle["content_hash"] = {
        "algorithm": "sha256",
        "value": cl.bundle_hash(bundle),
        "note": "content_hash·bundle_created_at을 뺀 묶음(정렬 키·UTF-8 JSON)의 해시. 어떤 내용을 썼는지 식별·변경 감지용이며 "
                "최신성·법적 효력을 증명하지 않음",
    }
    return bundle


def write_json_atomic(path, data):
    """같은 폴더의 임시 파일에 쓴 뒤 os.replace로 교체(중간 실패 시 부분 파일이 원래 이름으로 남지 않음)."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def build_candidate(name, bundle_version, root=cl.DATA_ROOT, created_at=None):
    """후보 폴더의 저장 자료로 묶음을 만들고 검증합니다. 반환: 로더 결과. 실패하면 묶음을 지우고 CriteriaError."""
    if not isinstance(bundle_version, str) or not cl.VERSION_ID.match(bundle_version):
        raise cl.CriteriaError("CRITERIA_INVALID", "bundle_version")
    directory = candidate_directory(name, root)
    if not directory.is_dir():
        raise cl.CriteriaError("CRITERIA_BUILD_FAILED", "candidate missing")
    created_at = created_at or datetime.now(KST).replace(microsecond=0).isoformat()
    bundle = compose_bundle(directory, bundle_version, created_at)
    target = directory / cl.BUNDLE_FILE
    write_json_atomic(target, bundle)
    try:
        return cl._load_from(directory)
    except cl.CriteriaError as err:
        target.unlink(missing_ok=True)
        raise cl.CriteriaError("CRITERIA_BUILD_FAILED", f"validation {err.code} {err.detail}") from None
