"""ComexStat 점검·장애 대비용 시연 스냅샷 만들기(앱과 별도로 수동 실행).

MDIC가 공개하는 Comex Stat 기본 데이터 CSV(연도별 수입 IMP_{연도}.csv)를 받아 한 줄씩 읽고
CO_NCM이 540233(폴리에스터 텍스처사)으로 시작하는 행만 남겨 data/comexstat_snapshot.json에 저장합니다.

    python -m features.market_analysis.build_snapshot            # 기본 2022~2026
    python -m features.market_analysis.build_snapshot --years 2023-2026

- 원본 CSV는 임시 폴더에 받아 한 줄씩 읽고(파일 전체를 메모리에 올리지 않음) 끝나면 성공·실패와 관계없이 지웁니다.
  원본은 저장소에 넣지 않습니다.
- 행 형식은 comexstat_client.query_imports 반환과 같습니다({year, month, country, fob, kg, code_name}) + 8자리 ncm.
  같은 연·월·NCM·국가는 합산합니다(원본은 주·세관·운송 수단별로 나뉨).
- 국가명은 data/countries.json(code → name_pt, 3자리 0 채움)으로 바꿉니다. 품목 이름은 MDIC 코드표(NCM.csv, NCM_SH.csv)에서
  대상 코드만 가져옵니다(표시용).
- 저장은 임시 파일에 쓴 뒤 바꿔치기합니다(중간에 멈춰도 기존 스냅샷이 깨지지 않음).
"""
import argparse
import csv
import io
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SNAPSHOT_FILE = DATA_DIR / "comexstat_snapshot.json"
COUNTRIES_FILE = DATA_DIR / "countries.json"
IMP_URL = "https://balanca.mdic.gov.br/balanca/bd/comexstat-bd/ncm/IMP_{year}.csv"
NCM_TABLE_URL = "https://balanca.mdic.gov.br/balanca/bd/tabelas/NCM.csv"
SH6_TABLE_URL = "https://balanca.mdic.gov.br/balanca/bd/tabelas/NCM_SH.csv"
NCM_PREFIX = "540233"
DEFAULT_YEARS = (2022, 2026)
SOURCE_NAME = "MDIC 공개 원본 자료(Comex Stat 기본 데이터 CSV)"
KST = timezone(timedelta(hours=9))
USER_AGENT = "fionex/0.1 (internal dashboard snapshot)"
TIMEOUT_SECONDS = 120
# 원본 CSV는 UTF-8 BOM 또는 Latin-1. 숫자·코드 열만 읽으므로 Latin-1로 읽어도 값이 바뀌지 않습니다.
CSV_ENCODING = "latin-1"


DOWNLOAD_RETRIES = 8


def download(url, dest, retries=DOWNLOAD_RETRIES):
    """url을 dest 파일로 조금씩 받아 씁니다(메모리에 통째로 올리지 않음).
    MDIC 서버가 큰 파일 전송 중 연결을 끊는 경우가 있어, 받은 곳부터 이어 받기(Range)로 다시 시도합니다."""
    Path(dest).write_bytes(b"")
    for attempt in range(retries + 1):
        have = Path(dest).stat().st_size
        headers = {"User-Agent": USER_AGENT}
        if have:
            headers["Range"] = "bytes=%d-" % have
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT_SECONDS) as res:
                if have and res.status != 206:  # 이어 받기를 지원하지 않으면 처음부터
                    Path(dest).write_bytes(b"")
                with open(dest, "ab") as out:
                    shutil.copyfileobj(res, out, length=1 << 20)
            return
        except (ConnectionError, TimeoutError, OSError) as err:
            if attempt == retries:
                raise
            print("  연결이 끊겨 이어 받기 재시도(%d/%d): %s" % (attempt + 1, retries, type(err).__name__), flush=True)
            time.sleep(min(30, 3 * (attempt + 1)))


def _reader(path, encoding=CSV_ENCODING):
    handle = open(path, "r", encoding=encoding, newline="")
    reader = csv.DictReader(handle, delimiter=";")
    # UTF-8 BOM(Latin-1로 읽으면 'ï»¿')이 첫 열 이름에 붙어 있으면 떼어 냅니다.
    # BOM 뒤 첫 열은 따옴표가 풀리지 않아 '"CO_ANO"'로 읽히므로 따옴표도 떼어 냅니다.
    reader.fieldnames = [f.replace("ï»¿", "").strip().strip('"') for f in reader.fieldnames or []]
    return handle, reader


def load_country_names(path=COUNTRIES_FILE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(c["code"]).zfill(3): c["name_pt"] for c in data["countries"]}


def filter_csv(path, countries, prefix=NCM_PREFIX):
    """IMP CSV 한 개 → {(year, month, ncm, country): [fob, kg]}, 이름 없는 국가 코드 집합. 한 줄씩 읽습니다."""
    sums, unknown = {}, set()
    handle, reader = _reader(path)
    try:
        for r in reader:
            ncm = (r.get("CO_NCM") or "").strip().strip('"')
            if not ncm.startswith(prefix):
                continue
            code = (r.get("CO_PAIS") or "").strip().zfill(3)
            country = countries.get(code)
            if country is None:
                unknown.add(code)
                country = code
            key = (int(r["CO_ANO"]), int(r["CO_MES"]), ncm, country)
            acc = sums.setdefault(key, [0, 0])
            acc[0] += int(r["VL_FOB"] or 0)
            acc[1] += int(r["KG_LIQUIDO"] or 0)
    finally:
        handle.close()
    return sums, unknown


def load_code_names(ncm_path, sh6_path, prefix=NCM_PREFIX):
    """대상 코드의 포르투갈어 이름만: {"ncm": {8자리: 이름}, "hs6": {6자리: 이름}}."""
    names = {"ncm": {}, "hs6": {}}
    for path, code_col, name_col, kind in ((ncm_path, "CO_NCM", "NO_NCM_POR", "ncm"), (sh6_path, "CO_SH6", "NO_SH6_POR", "hs6")):
        if path is None:
            continue
        handle, reader = _reader(path)
        try:
            for r in reader:
                code = (r.get(code_col) or "").strip()
                if code.startswith(prefix):
                    names[kind][code] = (r.get(name_col) or "").strip() or None
        finally:
            handle.close()
    return names


def build(years, fetch=download, countries_path=COUNTRIES_FILE, now=None):
    """스냅샷 dict를 만듭니다. fetch(url, dest)로 받은 원본은 함수가 끝나면 지웁니다."""
    countries = load_country_names(countries_path)
    tmp = Path(tempfile.mkdtemp(prefix="comexstat_raw_"))
    sums, unknown, files = {}, set(), []
    try:
        for year in years:
            url = IMP_URL.format(year=year)
            dest = tmp / ("IMP_%d.csv" % year)
            print("받는 중:", url, flush=True)
            fetch(url, dest)
            part, miss = filter_csv(dest, countries)
            dest.unlink()  # 연도마다 바로 지워 임시 공간을 아낌
            for key, (fob, kg) in part.items():
                acc = sums.setdefault(key, [0, 0])
                acc[0] += fob
                acc[1] += kg
            unknown |= miss
            files.append({"year": year, "url": url, "rows": len(part)})
            print("  %d년: 대상 행 %d개" % (year, len(part)), flush=True)
        names = {"ncm": {}, "hs6": {}}
        try:
            fetch(NCM_TABLE_URL, tmp / "NCM.csv")
            fetch(SH6_TABLE_URL, tmp / "NCM_SH.csv")
            names = load_code_names(tmp / "NCM.csv", tmp / "NCM_SH.csv")
        except Exception as err:  # 이름은 표시용이라 실패해도 스냅샷은 만듭니다
            print("코드 이름표를 받지 못함(이름 없이 저장):", type(err).__name__, flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    rows = [{"ncm": ncm, "year": y, "month": m, "country": country, "fob": fob, "kg": kg,
             "code_name": names["ncm"].get(ncm)}
            for (y, m, ncm, country), (fob, kg) in sorted(sums.items())]
    latest = max(((r["year"], r["month"]) for r in rows), default=None)
    retrieved = (now or datetime.now(KST)).isoformat(timespec="seconds")
    return {
        "source": {
            "name": SOURCE_NAME,
            "files": files,
            "code_tables": [NCM_TABLE_URL, SH6_TABLE_URL],
            "retrieved_at": retrieved,
            "latest_month": "%04d-%02d" % latest if latest else None,
            "ncm_prefix": NCM_PREFIX,
            "years": list(years),
            "unknown_country_codes": sorted(unknown),
            "note": "같은 연·월·NCM·국가 행을 합산(FOB USD, 순중량 kg). 수동 생성 시연용 자료이며 실시간 조회가 아님.",
        },
        "code_names": names,
        "rows": rows,
    }


def save(snapshot, path=SNAPSHOT_FILE):
    """임시 파일에 쓴 뒤 바꿔치기(원자적 저장)."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(snapshot, out, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _parse_years(text):
    a, _, b = text.partition("-")
    first, last = int(a), int(b or a)
    if first > last:
        raise argparse.ArgumentTypeError("연도 범위가 거꾸로입니다")
    return list(range(first, last + 1))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--years", type=_parse_years, default=list(range(DEFAULT_YEARS[0], DEFAULT_YEARS[1] + 1)),
                        help="예: 2022-2026 (기본)")
    args = parser.parse_args(argv)
    snapshot = build(args.years)
    save(snapshot)
    src = snapshot["source"]
    print("저장:", SNAPSHOT_FILE, "· 행", len(snapshot["rows"]), "· 최신 월", src["latest_month"],
          "· 이름 없는 국가 코드", src["unknown_country_codes"] or "없음")


if __name__ == "__main__":
    sys.exit(main())
