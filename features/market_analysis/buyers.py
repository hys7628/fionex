"""바이어 목록(리젠 T2T 잠재 바이어) 자료 읽기. 화면(⑥)과 PDF가 같은 결과를 씁니다.

- ① 잠재 바이어: data/buyer_textile_companies.json (buyer_data_builder.py가 국세청 CNPJ 공개 자료로 생성)
- ② 재생·T2T 관심 근거: data/buyer_t2t_evidence.json (업체 공식 웹·보도자료 링크와 확인일, 사람 검토 후 추가)
② 근거가 있는 업체를 앞에 둡니다. 수입 실적은 공개 자료로 확인할 수 없습니다(MDIC FAQ, Decreto 11.544/2023 제13조).
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
COMPANIES_FILE = DATA_DIR / "buyer_textile_companies.json"
EVIDENCE_FILE = DATA_DIR / "buyer_t2t_evidence.json"
IMPORT_NOTE = "수입 여부는 공식 자료로 확인 불가: 브라질 정부는 수입 업체 목록을 공개하지 않습니다(MDIC FAQ, Decreto 11.544/2023 제13조)."
CONTACT_NOTE = ("전화는 국세청에 등록된 법인 대표 번호입니다(최신·정확성 미확인). 이메일은 표시하지 않고, "
                "회사명과 겹치는 회사 도메인만 표시합니다(개인 메일·회계사무소 주소 제외).")
_cache = {}


def _read(path):
    """파일이 바뀌었을 때만 다시 읽습니다. 파일이 없으면 None."""
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return None
    hit = _cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    data = json.loads(path.read_text(encoding="utf-8"))
    _cache[path] = (mtime, data)
    return data


def load():
    """{"ready", "companies"(② 근거 업체 먼저), "counts", "source", "evidence_source", "notes"}."""
    base = _read(COMPANIES_FILE)
    evidence = _read(EVIDENCE_FILE) or {"companies": []}
    if base is None:
        return {"ready": False, "companies": [], "counts": None, "source": None, "filters": None,
                "evidence_reviewed_at": evidence.get("reviewed_at"), "notes": [IMPORT_NOTE]}
    by_cnpj = {}
    for e in evidence.get("companies", []):
        by_cnpj.setdefault(e["cnpj"][:8], []).extend(e.get("evidence", []))
    rows = []
    for c in base["companies"]:
        ev = by_cnpj.get(c["cnpj"][:8], [])
        rows.append(dict(c, evidence=ev))
    rows.sort(key=lambda r: not r["evidence"])  # 안정 정렬: 근거 업체 먼저, 그 안에서는 원래 순서(주·회사명)
    return {
        "ready": True,
        "companies": rows,
        "counts": dict(base["counts"], with_evidence=sum(1 for r in rows if r["evidence"])),
        "source": dict(base["source"], generated_at=base.get("generated_at")),
        "filters": base.get("filters"),
        "evidence_reviewed_at": evidence.get("reviewed_at"),
        "notes": [IMPORT_NOTE, CONTACT_NOTE],
    }
