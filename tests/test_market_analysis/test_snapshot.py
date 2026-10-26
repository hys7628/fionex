"""MDIC 공개 원본 CSV 스냅샷 테스트. 작은 가짜 CSV·임시 폴더만 씁니다(외부 요청 없음)."""
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pypdf import PdfReader  # noqa: E402

from features.market_analysis import build_snapshot as bs  # noqa: E402
from features.market_analysis import comexstat_client as comex  # noqa: E402
from features.market_analysis import pdf_report, service  # noqa: E402
from features.market_analysis.comexstat_client import ComexStatError  # noqa: E402

HEADER = '"CO_ANO";"CO_MES";"CO_NCM";"CO_UNID";"CO_PAIS";"SG_UF_NCM";"CO_VIA";"CO_URF";"QT_ESTAT";"KG_LIQUIDO";"VL_FOB";"VL_FRETE";"VL_SEGURO"'


def csv_line(year, month, ncm, country, kg, fob, uf="SP"):
    return '"%d";"%02d";"%s";"10";"%s";"%s";"01";"0817800";%d;%d;%d;0;0' % (year, month, ncm, country, uf, kg, kg, fob)


FAKE_CSV = {
    2025: "﻿" + "\n".join([HEADER,
                                csv_line(2025, 3, "54023310", "160", 1000, 2000),
                                csv_line(2025, 3, "54023310", "160", 500, 900, uf="SC"),  # 같은 연·월·NCM·국가 → 합산
                                csv_line(2025, 3, "54023320", "160", 100, 300),
                                csv_line(2025, 4, "54023310", "023", 50, 80),           # 3자리 0 채움 국가코드
                                csv_line(2025, 4, "82023900", "160", 9999, 9999),       # 다른 코드는 버림
                                csv_line(2025, 5, "54023310", "777", 10, 20)]) + "\n",  # 이름 없는 국가 코드
    2026: "\n".join([HEADER, csv_line(2026, 2, "54023310", "160", 700, 1400),
                     csv_line(2026, 2, "54023320", "160", 30, 60)]) + "\n",
}
NCM_TABLE = ('"CO_NCM";"CO_UNID";"CO_SH6";"NO_NCM_POR"\n"54023310";"10";"540233";"Fios texturizados de poliésteres, crus"\n'
             '"54023320";"10";"540233";"Fios texturizados de poliésteres, tintos"\n"49011000";"10";"490110";"Livros"\n')
SH6_TABLE = '"CO_SH6";"NO_SH6_POR"\n"540233";"Fios texturizados de poliésteres"\n"490110";"Livros"\n'


def fake_fetch(downloaded):
    def fetch(url, dest):
        downloaded.append(Path(dest))
        if url.endswith("NCM_SH.csv"):
            Path(dest).write_text(SH6_TABLE, encoding="latin-1")
        elif url.endswith("NCM.csv"):
            Path(dest).write_text(NCM_TABLE, encoding="latin-1")
        else:
            year = int(url.rsplit("_", 1)[1][:4])
            Path(dest).write_text(FAKE_CSV[year], encoding="utf-8")
    return fetch


def build_fake():
    downloaded = []
    snap = bs.build([2025, 2026], fetch=fake_fetch(downloaded), now=datetime(2026, 10, 27, 9, 0, tzinfo=bs.KST))
    return snap, downloaded


class BuildSnapshotTest(unittest.TestCase):
    def test_filter_convert_and_cleanup(self):
        snap, downloaded = build_fake()
        rows = {(r["year"], r["month"], r["ncm"], r["country"]): r for r in snap["rows"]}
        china = [c["name_pt"] for c in json.loads(bs.COUNTRIES_FILE.read_text(encoding="utf-8"))["countries"] if c["code"] == "160"][0]
        r = rows[(2025, 3, "54023310", china)]
        self.assertEqual((r["fob"], r["kg"]), (2900, 1500))  # 두 행 합산
        self.assertEqual(r["code_name"], "Fios texturizados de poliésteres, crus")
        self.assertEqual(set(r), {"ncm", "year", "month", "country", "fob", "kg", "code_name"})
        self.assertFalse(any(k[2] == "82023900" for k in rows))  # 다른 코드 제외
        self.assertTrue(any(k[3] != "023" and k[1] == 4 for k in rows))  # 023 → 국가명 변환
        self.assertIn("777", snap["source"]["unknown_country_codes"])
        self.assertEqual(snap["source"]["latest_month"], "2026-02")
        self.assertEqual(snap["code_names"]["hs6"], {"540233": "Fios texturizados de poliésteres"})
        self.assertEqual(snap["source"]["retrieved_at"], "2026-10-27T09:00:00+09:00")
        self.assertTrue(downloaded and not any(p.exists() for p in downloaded))  # 원본 CSV는 지움
        self.assertFalse(downloaded[0].parent.exists())

    def test_cleanup_on_failure_and_atomic_save(self):
        downloaded = []
        base = fake_fetch(downloaded)

        def broken(url, dest):
            base(url, dest)
            if "2026" in url:
                raise ConnectionError("끊김")
        with self.assertRaises(ConnectionError):
            bs.build([2025, 2026], fetch=broken)
        self.assertFalse(any(p.exists() for p in downloaded))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "snap.json"
            bs.save({"rows": [], "source": {}}, target)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["rows"], [])
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["snap.json"])  # 임시 파일 남지 않음


class SnapshotFallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        snap, _ = build_fake()
        self.path = Path(self.tmp.name) / "comexstat_snapshot.json"
        bs.save(snap, self.path)
        p = mock.patch.object(service, "SNAPSHOT_FILE", self.path)
        p.start()
        self.addCleanup(p.stop)
        service.clear_cache()
        self.addCleanup(service.clear_cache)
        fail = ComexStatError("MA_SOURCE_UNAVAILABLE", "점검 중", 502, True)
        for name in ("get_latest_month", "query_imports", "lookup_code"):
            q = mock.patch.object(comex, name, side_effect=fail)
            q.start()
            self.addCleanup(q.stop)

    def payload(self, **kw):
        p = {"code_system": "ncm", "code": "54023310", "from": "2026-01", "to": "2026-02"}
        p.update(kw)
        return p

    def test_ncm_falls_back_to_snapshot(self):
        r = service.analyze(self.payload())
        src = r["sources"][0]
        self.assertEqual(src["cache_status"], "snapshot")
        self.assertEqual(src["fetched_at"], "2026-10-27T09:00:00+09:00")
        self.assertEqual(src["latest_month"], "2026-02")  # 최신 월도 스냅샷 값
        self.assertTrue(src["latest_stale"])
        self.assertEqual(r["summary"]["fob"], 1400)
        self.assertEqual(r["query"]["code_name"], "Fios texturizados de poliésteres, crus")
        self.assertIn("MDIC 공개 원본 자료(기준: 2026-10-27)", r["notes"][0])

    def test_hs6_sums_ncm_rows(self):
        r = service.analyze(self.payload(code_system="hs6", code="540233"))
        self.assertEqual(r["sources"][0]["cache_status"], "snapshot")
        self.assertEqual(r["summary"]["fob"], 1400 + 60)  # 2026-02의 54023310 + 54023320
        self.assertEqual(r["query"]["code_name"], "Fios texturizados de poliésteres")

    def test_out_of_range_keeps_error(self):
        with self.assertRaises(ComexStatError):
            service.analyze(self.payload(code="54024400"))  # 스냅샷 대상(540233) 밖 코드
        with self.assertRaises(ComexStatError):
            service.analyze(self.payload(**{"from": "2023-01", "to": "2023-02"}))  # 스냅샷 연도 밖

    def test_meta_latest_from_snapshot(self):
        m = service.meta()
        self.assertEqual((m["latest"]["month"], m["latest"]["stale"], m["latest"]["snapshot"]), ("2026-02", True, True))

    def test_memory_cache_first_then_snapshot(self):
        service.clear_cache()
        with mock.patch.object(comex, "query_imports", return_value=[{"year": 2026, "month": 1, "country": "China",
                                                                       "fob": 1, "kg": 1, "code_name": None}]), \
                mock.patch.object(comex, "get_latest_month", return_value=(2026, 2, "2026-03-05")):
            service.analyze(self.payload())
        with mock.patch.object(service, "_monotonic", lambda: 10 ** 9):  # 캐시가 오래됨 → 조회 실패 시 stale 우선
            r = service.analyze(self.payload())
        self.assertEqual(r["sources"][0]["cache_status"], "stale")

    def test_broken_snapshot_ignored(self):
        self.path.write_text("{깨짐", encoding="utf-8")
        service.clear_cache()
        with self.assertRaises(ComexStatError):
            service.analyze(self.payload())

    def test_pdf_shows_snapshot_label(self):
        r = service.analyze(self.payload())
        pdf = pdf_report.build_pdf({"stats": r, "ai": None})
        text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn("MDIC 공개 원본 자료(기준: 2026-10-27) 사용", text)


if __name__ == "__main__":
    unittest.main()
