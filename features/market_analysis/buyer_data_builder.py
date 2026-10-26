"""바이어 목록 ①(원사·원단 제조 기업) 기준 자료 생성기. 앱 실행과 무관한 수동 도구입니다.

브라질 연방국세청(Receita Federal) CNPJ 공개 자료(월별 폴더의 zip, 세미콜론 CSV, latin-1)를 읽어
대상 업종·활성·법인·규모 조건에 맞는 기업만 남긴 작은 JSON을 만듭니다. 원본 zip은 저장소에 넣지 않습니다.

사용(프로젝트 루트, jasonenv):
    python -m features.market_analysis.buyer_data_builder <원본 폴더> <자료 기준월 YYYY-MM>

원본 폴더에 필요한 파일: Estabelecimentos0~9.zip, Empresas0~9.zip, Cnaes.zip, Municipios.zip, Naturezas.zip
공식 저장소: https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9 (월별 폴더)

조건(2026-10-26 담당자 결정, feature_spec.md '바이어 목록' 절)
- 사업장 주 업종(CNAE 주)이 TARGET_CNAES 중 하나, 영업 상태 활성(02)
- 법인만: 법인 형태 '개인사업자(2135)' 제외. MEI는 규모 코드가 '소기업(01)'이라 아래 규모 조건에서 빠집니다(Simples 파일 불필요)
- 기업 규모 코드 '그 외(05)'만(소기업 01·소규모 03·미상 00 제외)
- 기업 1곳당 1행: 조건에 맞는 사업장 중 본사(matriz)를 우선 대표로, 없으면 가장 먼저 읽힌 지점
수입 실적은 공개 자료에 없으므로 담지 않습니다. 연락처는 국세청 등록 값 그대로입니다(최신·정확성 미확인).
"""
import csv
import io
import json
import re
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
OUT_FILE = Path(__file__).resolve().parent / "data" / "buyer_textile_companies.json"
SOURCE_URL = "https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9"

# DTY를 직접 쓰는 원사·원단 제조 업종(국세청 Cnaes 표의 공식 명칭으로 대조, 2026-10-26)
TARGET_CNAES = ("1313800", "1314600", "1321900", "1322700", "1323500", "1330800", "1340501", "1340502")
INDIVIDUAL_NATUREZA = "2135"  # Empresário (Individual)
PORTE_DEMAIS = "05"
ACTIVE = "02"
PORTE_TEXT = {"00": "미상", "01": "소기업", "03": "소규모", "05": "그 외(중·대형)"}

# Estabelecimentos 열 순서(국세청 공개 자료 항목 설명서)
E_BASICO, E_ORDEM, E_DV, E_MATRIZ, E_FANTASIA, E_SITUACAO = 0, 1, 2, 3, 4, 5
E_INICIO, E_CNAE, E_UF, E_MUN = 10, 11, 19, 20
E_DDD1, E_TEL1, E_DDD2, E_TEL2, E_EMAIL = 21, 22, 23, 24, 27
# Empresas: 0 기본 CNPJ, 1 회사명, 2 법인 형태, 5 규모
# 속도: 원본은 수천만 줄이라 대상 업종 코드가 든 줄만 정규식으로 먼저 고른 뒤 그 줄만 CSV로 해석합니다.
_CNAE_FIELD = re.compile(rb';"(?:' + b"|".join(c.encode() for c in TARGET_CNAES) + rb')";')
_BLOCK = 64 * 1024 * 1024


def _csv_rows(path):
    """zip 안 CSV를 한 줄씩 읽습니다(전체를 메모리에 올리지 않음)."""
    with zipfile.ZipFile(path) as z:
        for member in z.namelist():
            with z.open(member) as f:
                yield from csv.reader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";", quotechar='"')


def _blocks(path):
    """zip 안 CSV를 큰 덩어리(줄 단위로 끝나게)로 읽습니다."""
    with zipfile.ZipFile(path) as z:
        for member in z.namelist():
            with z.open(member) as f:
                rest = b""
                while True:
                    data = f.read(_BLOCK)
                    if not data:
                        if rest:
                            yield rest
                        break
                    data = rest + data
                    cut = data.rfind(b"\n") + 1
                    rest = data[cut:]
                    yield data[:cut]


def _parse(line_bytes):
    return next(csv.reader([line_bytes.decode("latin-1").rstrip("\r")], delimiter=";", quotechar='"'))


def _table(folder, name):
    return {r[0]: r[1] for r in _csv_rows(Path(folder) / f"{name}.zip") if len(r) >= 2}


def _phone(ddd, number):
    ddd, number = (ddd or "").strip(), (number or "").strip()
    return "(%s) %s" % (ddd, number) if ddd and number else (number or None)


def _clean(text):
    return " ".join(str(text or "").split()) or None


def _establishments_in(path):
    found = {}
    for block in _blocks(path):
        last_start = -1
        for m in _CNAE_FIELD.finditer(block):
            start = block.rfind(b"\n", 0, m.start()) + 1
            if start == last_start:
                continue  # 같은 줄에서 두 번 찾은 경우
            last_start = start
            end = block.find(b"\n", m.end())
            r = _parse(block[start:end if end != -1 else len(block)])
            if len(r) <= E_EMAIL or r[E_CNAE] not in TARGET_CNAES or r[E_SITUACAO].zfill(2) != ACTIVE:
                continue
            found.setdefault(r[E_BASICO], []).append({
                "cnpj": r[E_BASICO] + r[E_ORDEM] + r[E_DV], "matriz": r[E_MATRIZ] == "1",
                "nome_fantasia": _clean(r[E_FANTASIA]), "cnae": r[E_CNAE], "uf": _clean(r[E_UF]), "municipio_code": r[E_MUN],
                "inicio": r[E_INICIO] or None,
                "phones": [p for p in (_phone(r[E_DDD1], r[E_TEL1]), _phone(r[E_DDD2], r[E_TEL2])) if p],
                "email": (_clean(r[E_EMAIL]) or "").lower() or None,
            })
    return found


def _companies_in(args):
    path, basicos = args
    keys = {b'"' + b.encode() + b'"' for b in basicos}
    out = {}
    for block in _blocks(path):
        for line in block.split(b"\n"):
            if line[:10] in keys:
                r = _parse(line)
                if len(r) >= 6:
                    out[r[0]] = {"razao_social": _clean(r[1]), "natureza": r[2], "porte": r[5].zfill(2)}
    return out


def collect_establishments(folder, files=range(10), workers=1):
    """조건 업종·활성 사업장. {기본 CNPJ: [사업장 dict, ...]}. workers>1이면 파일별 병렬 처리."""
    paths = [Path(folder) / f"Estabelecimentos{i}.zip" for i in files]
    parts = list(ProcessPoolExecutor(workers).map(_establishments_in, paths)) if workers > 1 else map(_establishments_in, paths)
    found = {}
    for part in parts:
        for k, v in part.items():
            found.setdefault(k, []).extend(v)
    return found


def collect_companies(folder, basicos, files=range(10), workers=1):
    jobs = [(Path(folder) / f"Empresas{i}.zip", basicos) for i in files]
    parts = list(ProcessPoolExecutor(workers).map(_companies_in, jobs)) if workers > 1 else map(_companies_in, jobs)
    out = {}
    for part in parts:
        out.update(part)
    return out


def build(folder, reference_month, files=range(10), workers=1):
    cnaes = _table(folder, "Cnaes")
    municipios = _table(folder, "Municipios")
    naturezas = _table(folder, "Naturezas")
    est = collect_establishments(folder, files, workers)
    companies = collect_companies(folder, set(est), files, workers)
    counts = {"establishments_matched": sum(len(v) for v in est.values()), "companies_matched": len(est)}
    rows = []
    excluded = {"no_company_row": 0, "individual": 0, "porte": 0}
    for basico, sites in est.items():
        c = companies.get(basico)
        if c is None:
            excluded["no_company_row"] += 1
            continue
        if c["natureza"] == INDIVIDUAL_NATUREZA:
            excluded["individual"] += 1
            continue
        if c["porte"] != PORTE_DEMAIS:
            excluded["porte"] += 1
            continue
        rep = next((s for s in sites if s["matriz"]), sites[0])
        rows.append({
            "cnpj": rep["cnpj"], "razao_social": c["razao_social"], "nome_fantasia": rep["nome_fantasia"],
            "cnae": rep["cnae"], "cnae_desc": cnaes.get(rep["cnae"]), "uf": rep["uf"],
            "municipio": _clean(municipios.get(rep["municipio_code"])), "phones": rep["phones"], "email": rep["email"],
            "porte": PORTE_TEXT.get(c["porte"], c["porte"]), "natureza": _clean(naturezas.get(c["natureza"])),
            "matriz": rep["matriz"], "sites_matched": len(sites), "inicio_atividade": rep["inicio"],
        })
    rows.sort(key=lambda r: (r["uf"] or "", r["razao_social"] or ""))
    return {
        "source": {"name": "Receita Federal do Brasil — Dados abertos do CNPJ", "url": SOURCE_URL,
                   "reference_month": reference_month, "note": "수입 실적은 공개 자료에 없음. 연락처는 국세청 등록 값(최신·정확성 미확인)."},
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "filters": {"cnaes": [{"code": c, "desc": cnaes.get(c)} for c in TARGET_CNAES], "situacao": "ATIVA(02)",
                    "excluded_natureza": "%s %s" % (INDIVIDUAL_NATUREZA, naturezas.get(INDIVIDUAL_NATUREZA)),
                    "mei": "규모 '소기업(01)'이라 규모 조건으로 제외",
                    "porte": PORTE_TEXT[PORTE_DEMAIS]},
        "counts": {**counts, "excluded": excluded, "companies": len(rows)},
        "companies": rows,
    }


def main(argv):
    if len(argv) != 3:
        sys.exit("사용: python -m features.market_analysis.buyer_data_builder <원본 폴더> <YYYY-MM>")
    data = build(argv[1], argv[2], workers=10)
    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("saved", OUT_FILE, data["counts"])


if __name__ == "__main__":
    main(sys.argv)
