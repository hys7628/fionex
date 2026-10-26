"""홈 브라질 섬유 전시회 테스트. 외부 요청이 없습니다.

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_home -v

가상 행사는 임시 폴더의 JSON으로 만들고, 실제 자료(features/home/data/br_textile_fairs.json)는 형식만 검사합니다.
"""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from features.home import fairs  # noqa: E402

TODAY = date(2026, 10, 25)


def fair(name, start, end, verified=True, **extra):
    item = {"name": name, "start": start, "end": end, "city": "TEST City", "venue": "TEST Venue", "focus": "TEST",
            "url": "https://example.com/" + name, "source": "TEST 출처", "verified": verified, "checked_at": "2026-10-25",
            "country": "브라질", "region": "brazil"}
    item.update(extra)
    return item


class FairsTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "fairs.json"

    def write(self, items, checked_at="2026-10-25", raw=None):
        self.path.write_text(raw if raw is not None else json.dumps({"checked_at": checked_at, "fairs": items}), encoding="utf-8")

    def upcoming(self, limit=5, today=TODAY):
        return fairs.get_upcoming(limit, today=today, path=self.path)


class ListTests(FairsTestBase):
    def test_filter_sort_dday(self):
        self.write([
            fair("future", "2027-04-27", "2027-04-30"),
            fair("ended", "2026-10-01", "2026-10-24"),
            fair("ongoing", "2026-10-24", "2026-10-26", verified=False),
            fair("today", "2026-10-25", "2026-10-27"),
            fair("ends_today", "2026-10-20", "2026-10-25"),
        ])
        data = self.upcoming()
        self.assertEqual([f["name"] for f in data["fairs"]], ["ends_today", "ongoing", "today", "future"])  # 시작일 순, 종료 제외
        by = {f["name"]: f for f in data["fairs"]}
        self.assertEqual((by["future"]["d_day"], by["future"]["status"]), ("D-184", "upcoming"))
        self.assertEqual((by["today"]["d_day"], by["today"]["status"]), ("D-DAY", "today"))
        self.assertEqual((by["ongoing"]["d_day"], by["ongoing"]["status"]), ("진행 중", "ongoing"))
        self.assertEqual(by["ends_today"]["d_day"], "진행 중")
        self.assertIs(by["ongoing"]["verified"], False)
        self.assertEqual((data["total_upcoming"], data["invalid_count"], data["data_checked_at"]), (4, 0, "2026-10-25"))

    def test_limit(self):
        self.write([fair(f"f{i}", f"2027-01-{i + 10:02d}", f"2027-01-{i + 10:02d}") for i in range(8)])
        self.assertEqual(len(self.upcoming(limit=3)["fairs"]), 3)
        self.assertEqual(self.upcoming(limit=3)["total_upcoming"], 8)

    def test_none_upcoming(self):
        self.write([fair("ended", "2026-01-01", "2026-01-02")])
        data = self.upcoming()
        self.assertEqual((data["fairs"], data["total_upcoming"]), ([], 0))

    def test_invalid_items_excluded_not_filled(self):
        no_url = fair("no_url", "2027-01-01", "2027-01-02")
        del no_url["url"]
        self.write([
            fair("ok", "2027-01-01", "2027-01-02"),
            no_url,
            fair("bad_url", "2027-01-01", "2027-01-02", url="javascript:alert(1)"),
            fair("no_source", "2027-01-01", "2027-01-02", source=""),
            fair("bad_date", "2027-13-01", "2027-01-02"),
            fair("end_before_start", "2027-01-05", "2027-01-02"),
            fair("verified_str", "2027-01-01", "2027-01-02", verified="true"),
            {k: v for k, v in fair("no_name", "2027-01-01", "2027-01-02").items() if k != "name"},
            "not a dict",
        ])
        data = self.upcoming()
        self.assertEqual([f["name"] for f in data["fairs"]], ["ok"])
        self.assertEqual(data["invalid_count"], 8)

    def test_optional_fields_stay_unknown(self):
        self.write([fair("partial", "2027-01-01", "2027-01-02", venue=None, focus="  ", city=None)])
        f = self.upcoming()["fairs"][0]
        self.assertEqual((f["city"], f["venue"], f["focus"], f["note"]), (None, None, None, None))

    def test_file_errors(self):
        with self.assertRaises(fairs.FairsDataError):
            fairs.get_upcoming(today=TODAY, path=Path(self.tmp.name) / "missing.json")
        for raw in ("{broken", "[]", json.dumps({"fairs": "x"}), json.dumps({"checked_at": "2026-10-25"})):
            self.write(None, raw=raw)
            with self.assertRaises(fairs.FairsDataError):
                self.upcoming()


def latam(name, start, end, country="페루"):
    return fair(name, start, end, verified=False, country=country, region="latin_america")


class RegionTests(FairsTestBase):
    """A 브라질 · B 중남미 · C 전체 · D 브라질 최소 2건 · E 브라질 1건뿐 · G country/region 누락."""

    def setUp(self):
        super().setUp()
        self.write([latam("L1", "2026-11-01", "2026-11-02"), latam("L2", "2026-11-10", "2026-11-11", "콜롬비아"),
                    latam("L3", "2026-12-01", "2026-12-02"), fair("B1", "2027-01-10", "2027-01-11"),
                    fair("B2", "2027-02-10", "2027-02-11"), fair("B3", "2027-03-10", "2027-03-11")])

    def test_region_fields_and_filters(self):
        listed = self.upcoming(limit=20)["fairs"]
        self.assertEqual([(f["name"], f["country"], f["region"]) for f in listed][:2],
                         [("L1", "페루", "latin_america"), ("L2", "콜롬비아", "latin_america")])
        self.assertEqual([f["name"] for f in listed if f["region"] == "brazil"], ["B1", "B2", "B3"])  # A
        self.assertEqual([f["name"] for f in listed if f["region"] == "latin_america"], ["L1", "L2", "L3"])  # B
        self.assertEqual(len(listed), 6)  # C 양쪽 모두

    def test_all_view_keeps_two_brazil(self):
        names = [f["name"] for f in fairs.get_upcoming(3, today=TODAY, path=self.path, min_brazil=fairs.MIN_BRAZIL_IN_ALL)["fairs"]]
        self.assertEqual(names, ["L1", "B1", "B2"])  # D 브라질 2건 + 나머지 날짜순, 결과는 날짜순
        self.assertEqual([f["name"] for f in self.upcoming(limit=3)["fairs"]], ["L1", "L2", "L3"])  # 정책 없으면 날짜순

    def test_only_one_brazil_no_fake(self):
        self.write([latam("L1", "2026-11-01", "2026-11-02"), latam("L2", "2026-11-10", "2026-11-11"),
                    latam("L3", "2026-12-01", "2026-12-02"), fair("B1", "2027-01-10", "2027-01-11")])
        names = [f["name"] for f in fairs.get_upcoming(3, today=TODAY, path=self.path, min_brazil=2)["fairs"]]
        self.assertEqual(names, ["L1", "L2", "B1"])  # E 있는 1건만, 가짜 없음

    def test_missing_country_or_region_excluded(self):
        bad = [fair("NoCountry", "2026-11-01", "2026-11-02", country=""), fair("NoRegion", "2026-11-01", "2026-11-02", region=None),
               fair("BadRegion", "2026-11-01", "2026-11-02", region="europe"), fair("OK", "2026-11-01", "2026-11-02")]
        self.write(bad)
        data = self.upcoming()
        self.assertEqual(([f["name"] for f in data["fairs"]], data["invalid_count"]), (["OK"], 3))  # G


class RealDataTests(unittest.TestCase):
    def test_repository_data_is_valid(self):
        listed, checked_at, invalid = fairs.load_fairs(fairs.DATA_FILE)
        self.assertEqual(invalid, 0)
        self.assertEqual(checked_at, "2026-10-25")
        self.assertGreaterEqual(len(listed), 3)
        for f in listed:
            self.assertTrue(f["url"].startswith("https://"))
        names = {f["name"]: f for f in listed}
        self.assertIs(names["Inspiramais"]["verified"], False)  # 공식 사이트 연도 표기 불일치
        self.assertIsNotNone(names["Inspiramais"]["note"])
        # 중남미 추가 3건: 목록 사이트 기준이라 확인 필요, 날짜 미확정 행사(F)는 자료에 없음
        for name, country in (("Expotextil Perú 2026", "페루"), ("Colombiatex de las Américas 2027", "콜롬비아"), ("Createx 2027", "콜롬비아")):
            self.assertEqual((names[name]["country"], names[name]["region"], names[name]["verified"]), (country, "latin_america", False))
        self.assertFalse([n for n in names if "Colombiamoda" in n or "Intermoda" in n])
        for f in listed:
            self.assertIn(f["region"], fairs.REGIONS)
            self.assertEqual(f["region"] == "brazil", f["country"] == "브라질")
        tecno = names["Tecnotêxtil Brasil 2027"]  # 공식 사이트 "de 27 a 30 de abril de 2027"(2026-10-25 재확인)
        self.assertEqual((str(tecno["start"]), str(tecno["end"]), tecno["verified"]), ("2027-04-27", "2027-04-30", True))

    def test_feature_spec_table_matches_data(self):
        spec = (ROOT / "features" / "home" / "feature_spec.md").read_text(encoding="utf-8")
        for f in fairs.load_fairs(fairs.DATA_FILE)[0]:
            self.assertIn(f"| {f['name']} | {f['start']} ~ {f['end']} |", spec)


class RouteTests(FairsTestBase):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(fairs, "DATA_FILE", self.path)
        p.start()
        self.addCleanup(p.stop)
        self.client = app.test_client()

    def test_route_ok_and_limit(self):
        self.write([fair(f"f{i}", f"2099-01-{i + 1:02d}", f"2099-01-{i + 1:02d}") for i in range(25)])
        body = self.client.get("/api/home/fairs").get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(len(body["data"]["fairs"]), 5)
        self.assertEqual(len(self.client.get("/api/home/fairs?limit=2").get_json()["data"]["fairs"]), 2)
        self.assertEqual(len(self.client.get("/api/home/fairs?limit=500").get_json()["data"]["fairs"]), fairs.MAX_LIMIT)
        for q in ("?limit=0", "?limit=-1", "?limit=abc", "?limit="):
            res = self.client.get("/api/home/fairs" + q)
            self.assertEqual(res.status_code, 400, q)
            self.assertEqual(res.get_json()["error"]["code"], "invalid_limit")

    def test_route_file_error(self):
        self.write(None, raw="{broken")
        res = self.client.get("/api/home/fairs")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.get_json(), {"ok": False, "error": {"code": "fairs_unavailable", "message": "전시회 일정 자료를 확인할 수 없습니다."}})


if __name__ == "__main__":
    unittest.main()
