"""바이어 목록(리젠 T2T 잠재 바이어) 자료 읽기. 화면(⑥)과 PDF가 같은 결과를 씁니다.

- ① 잠재 바이어: data/buyer_textile_companies.json (buyer_data_builder.py가 국세청 CNPJ 공개 자료로 생성)
- ② 재생·T2T 관심 근거: data/buyer_t2t_evidence.json (업체 공식 웹·보도자료 링크와 확인일, 사람 검토 후 추가)
수입 실적은 공개 자료로 확인할 수 없습니다(MDIC FAQ, Decreto 11.544/2023 제13조).

우선순위 등급(2026-10-26, 점수 대신 공개 규칙. 코드 판단·비용 없음, 수입 실적 기반 아님):
- 업종 관련도: 높음 = 합성섬유 방적·직조, 편직, 날염·가연(텍스처링) / 중간 = 표백·염색·연사, 재봉실 / 낮음 = 면·천연섬유 직조
- 연락 가능: 높음 = 대표 전화 + 회사 도메인 / 중간 = 둘 중 하나 / 없음
- A = 관련도 높음 + 연락 가능 높음, B = 관련도 중간 또는 관련도 높음이지만 연락 가능이 높음이 아님, C = 관련도 낮음
- 재생·T2T 공개 근거가 있으면 한 단계 올림(C→B, B→A)
정렬: 등급 → 근거 있음 → 관련도 → 연락 가능 → 원래 순서(주·회사명).
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
COMPANIES_FILE = DATA_DIR / "buyer_textile_companies.json"
EVIDENCE_FILE = DATA_DIR / "buyer_t2t_evidence.json"
IMPORT_NOTE = "수입 여부는 공식 자료로 확인 불가: 브라질 정부는 수입 업체 목록을 공개하지 않습니다(MDIC FAQ, Decreto 11.544/2023 제13조)."
CONTACT_NOTE = ("전화는 국세청에 등록된 법인 대표 번호입니다(최신·정확성 미확인). 이메일은 표시하지 않고, "
                "회사명과 겹치는 회사 도메인만 표시합니다(개인 메일·회계사무소 주소 제외).")
GRADE_NOTE = "수입 실적 기반 아님 · 업종과 공개 근거 기준"

# 업종 코드(CNAE) → (한국어 짧은 이름, 관련도). 화면 CNAE_SHORT와 같은 이름입니다.
CNAE_INFO = {
    "1313800": ("합성섬유 방적", "high"),
    "1323500": ("합성섬유 직물", "high"),
    "1330800": ("니트 원단(편직)", "high"),
    "1340501": ("날염·가공사(텍스처링)", "high"),  # 가연(texturização)을 포함하는 코드
    "1340502": ("표백·염색·연사", "mid"),
    "1314600": ("재봉·자수실", "mid"),
    "1321900": ("면 직물", "low"),
    "1322700": ("기타 천연섬유 직물", "low"),
}
LEVEL_LABELS = {"high": "높음", "mid": "중간", "low": "낮음", "none": "없음"}
CONTACT_LABELS = {"high": "대표 전화·회사 도메인", "mid": "전화 또는 도메인 하나", "none": "연락처 없음"}
GRADE_RULES = [
    "업종 관련도 — 높음: 합성섬유 방적·직조, 편직, 날염·가연(텍스처링) / 중간: 표백·염색·연사, 재봉실 / 낮음: 면·천연섬유 직조",
    "연락 가능 — 높음: 대표 전화 + 회사 도메인 / 중간: 둘 중 하나 / 없음",
    "A: 업종 관련도 높음 + 연락 가능 높음 · B: 업종 관련도 중간, 또는 높음이지만 연락처가 부족 · C: 업종 관련도 낮음",
    "재생·T2T 공개 근거(업체 공식 웹·보도자료, 사람 검토)가 있으면 한 단계 올림",
]
_ORDER = {"high": 0, "mid": 1, "low": 2, "none": 2}
_cache = {}


def contact_level(company):
    has_phone, has_domain = bool(company.get("phones")), bool(company.get("domain"))
    return "high" if has_phone and has_domain else "mid" if has_phone or has_domain else "none"


def grade(company, has_evidence=False):
    """{"grade", "relevance", "contact", "raised", "reason"}. 공개 규칙만 쓰며 수입 실적은 쓰지 않습니다."""
    label, relevance = CNAE_INFO.get(company.get("cnae"), (company.get("cnae_desc") or company.get("cnae") or "업종 미상", "low"))
    contact = contact_level(company)
    base = "C" if relevance == "low" else "A" if relevance == "high" and contact == "high" else "B"
    final = {"C": "B", "B": "A", "A": "A"}[base] if has_evidence else base
    reason = "업종 관련도 %s(%s) · 연락 %s" % (LEVEL_LABELS[relevance], label, CONTACT_LABELS[contact])
    if has_evidence:
        reason += " · 재생·T2T 공개 근거" + (" → 한 단계 올림" if final != base else "(이미 A)")
    return {"grade": final, "relevance": relevance, "contact": contact, "raised": final != base, "reason": reason}


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
    """{"ready", "companies"(등급순, 각 행에 grade·grade_reason 등), "counts", "source", "notes", "grade_note", "grade_rules"}."""
    base = _read(COMPANIES_FILE)
    evidence = _read(EVIDENCE_FILE) or {"companies": []}
    if base is None:
        return {"ready": False, "companies": [], "counts": None, "source": None, "filters": None,
                "evidence_reviewed_at": evidence.get("reviewed_at"), "notes": [IMPORT_NOTE],
                "grade_note": GRADE_NOTE, "grade_rules": GRADE_RULES}
    by_cnpj = {}
    for e in evidence.get("companies", []):
        by_cnpj.setdefault(e["cnpj"][:8], []).extend(e.get("evidence", []))
    rows = []
    for c in base["companies"]:
        ev = by_cnpj.get(c["cnpj"][:8], [])
        g = grade(c, bool(ev))
        rows.append(dict(c, evidence=ev, grade=g["grade"], grade_reason=g["reason"], relevance=g["relevance"],
                         contact_level=g["contact"], cnae_label=CNAE_INFO.get(c["cnae"], (c.get("cnae_desc"),))[0]))
    # 안정 정렬: 등급 → 근거 있음 → 관련도 → 연락 가능, 같으면 원래 순서(주·회사명)
    rows.sort(key=lambda r: (r["grade"], not r["evidence"], _ORDER[r["relevance"]], _ORDER[r["contact_level"]]))
    grades = {k: sum(1 for r in rows if r["grade"] == k) for k in ("A", "B", "C")}
    return {
        "ready": True,
        "companies": rows,
        "counts": dict(base["counts"], with_evidence=sum(1 for r in rows if r["evidence"]), grades=grades),
        "source": dict(base["source"], generated_at=base.get("generated_at")),
        "filters": base.get("filters"),
        "evidence_reviewed_at": evidence.get("reviewed_at"),
        "notes": [IMPORT_NOTE, CONTACT_NOTE],
        "grade_note": GRADE_NOTE,
        "grade_rules": GRADE_RULES,
    }


def find(cnpj):
    """등급이 붙은 업체 1곳(load() 기준) 또는 None. 화면이 보낸 회사 정보는 믿지 않고 기준 자료에서 다시 찾습니다."""
    data = load()
    for row in data["companies"]:
        if row["cnpj"] == cnpj:
            return row, data
    return None, data
