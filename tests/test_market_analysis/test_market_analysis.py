"""시장 분석 1단계(ComexStat 통계) 테스트. 실제 ComexStat 요청을 보내지 않습니다.

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_market_analysis -v

수치는 산식 확인용 가상 값입니다. 실제 통계 대조는 docs/worklogs/han_yunsu/validation.md에 따로 기록합니다.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features.market_analysis import comexstat_client as comex  # noqa: E402
from features.market_analysis import service  # noqa: E402
from features.market_analysis.comexstat_client import ComexStatError  # noqa: E402

LATEST = service.month_index(2026, 9)


def row(ym, country, fob, kg, name="Fios texturizados de poliésteres, crus"):
    y, m = ym.split("-")
    return {"year": int(y), "month": int(m), "country": country, "fob": fob, "kg": kg, "code_name": name}


def req(start="2026-01", end="2026-03", countries=(), code_system="ncm", code="54023310"):
    return service.validate_request(
        {"code_system": code_system, "code": code, "from": start, "to": end, "countries": list(countries)}, LATEST)


_no_snapshot = None


def setUpModule():
    """이 파일은 스냅샷이 없는 상태(조회 실패 = 오류)를 검사합니다. 실제 data/comexstat_snapshot.json 대신 없는 경로를 씁니다.
    스냅샷 대체는 test_snapshot.py에서 따로 검사합니다."""
    global _no_snapshot
    _no_snapshot = mock.patch.object(service, "SNAPSHOT_FILE", Path(__file__).resolve().parent / "_no_snapshot.json")
    _no_snapshot.start()
    service.clear_cache()


def tearDownModule():
    _no_snapshot.stop()
    service.clear_cache()


class ValidateTest(unittest.TestCase):
    def errors(self, **payload):
        base = {"code_system": "ncm", "code": "54023310", "from": "2024-01", "to": "2026-09"}
        base.update(payload)
        with self.assertRaises(service.InputError) as ctx:
            service.validate_request(base, LATEST)
        return ctx.exception.fields

    def test_valid_default(self):
        r = req("2023-10", "2026-09")
        self.assertEqual((r.code, r.end - r.start + 1), ("54023310", 36))

    def test_code_with_dots_and_hs6(self):
        self.assertEqual(req(code="5402.33.10").code, "54023310")
        self.assertEqual(req(code_system="hs6", code="5402.33").code, "540233")

    def test_code_errors(self):
        self.assertIn("8자리", self.errors(code="540233")["code"])
        self.assertIn("숫자", self.errors(code="54O23310")["code"])
        self.assertIn("입력", self.errors(code="")["code"])
        self.assertIn("code_system", self.errors(code_system="cn"))

    def test_period_errors(self):
        self.assertIn("늦습니다", self.errors(**{"from": "2026-05", "to": "2026-01"})["from"])
        self.assertIn("최대 120개월", self.errors(**{"from": "2016-01", "to": "2026-09"})["from"])
        self.assertIn("2026-09", self.errors(to="2026-10")["to"])
        self.assertIn("형식", self.errors(**{"from": "2026-13"})["from"])
        self.assertIn("선택", self.errors(to="")["to"])

    def test_120_months_allowed(self):
        r = req("2016-10", "2026-09")
        self.assertEqual(r.end - r.start + 1, 120)

    def test_countries(self):
        self.assertEqual(req(countries=["160", "190", "160"]).countries, ("160", "190"))
        self.assertIn("countries", self.errors(countries=["XYZ"]))


class ComputeTest(unittest.TestCase):
    def test_weighted_unit_price_not_simple_average(self):
        # 월별 단가 1.0, 10.0 → 단순 평균 5.5이지만 가중 평균은 4100 / 4010
        rows = [row("2026-01", "China", 1000, 1000), row("2026-01", "Índia", 3000, 3000), row("2026-02", "China", 100, 10)]
        r = service.compute(rows, req("2026-01", "2026-02"))
        self.assertAlmostEqual(r["summary"]["unit_price"], 4100 / 4010)

    def test_yoy_and_missing(self):
        rows = [
            row("2025-01", "China", 100, 50), row("2025-02", "China", 0, 0),
            row("2026-01", "China", 150, 60), row("2026-02", "China", 80, 40), row("2026-03", "China", 90, 30),
        ]
        r = service.compute(rows, req("2026-01", "2026-03"))
        s = r["summary"]
        self.assertAlmostEqual(s["yoy"]["fob"]["value"], (320 - 100) / 100 * 100)
        m = {x["month"]: x for x in r["monthly"]}
        self.assertAlmostEqual(m["2026-01"]["yoy"]["fob"]["value"], 50.0)
        self.assertEqual(m["2026-02"]["yoy"]["fob"]["reason"], "전년 동월 값 0")
        self.assertEqual(m["2026-03"]["yoy"]["fob"]["reason"], "전년 동월 기록 없음")
        self.assertIn("1개월은 기록이 없습니다", " ".join(r["notes"]))

    def test_no_record_month_is_not_zero(self):
        rows = [row("2026-01", "China", 100, 50), row("2026-03", "China", 100, 50)]
        r = service.compute(rows, req("2026-01", "2026-03"))
        feb = r["monthly"][1]
        self.assertFalse(feb["has_record"])
        self.assertIsNone(feb["fob"])
        self.assertEqual(feb["unit_price_reason"], "기록 없음")
        self.assertEqual(r["summary"]["months_with_record"], 2)

    def test_zero_or_missing_weight(self):
        r = service.compute([row("2026-01", "China", 100, 0)], req("2026-01", "2026-01"))
        self.assertIsNone(r["summary"]["unit_price"])
        self.assertEqual(r["summary"]["unit_price_reason"], "중량 0")
        r = service.compute([row("2026-01", "China", 100, None)], req("2026-01", "2026-01"))
        self.assertEqual(r["monthly"][0]["unit_price_reason"], "금액 또는 중량 값 없음")

    def test_prior_zero_reason(self):
        rows = [row("2025-01", "China", 0, 0), row("2026-01", "China", 10, 5)]
        s = service.compute(rows, req("2026-01", "2026-01"))["summary"]
        self.assertEqual(s["yoy"]["fob"]["reason"], "전년 동기 값 0")

    def test_outlier_flags_kept(self):
        rows = [row("2026-0%d" % i, "China", p * 100, 100) for i, p in zip(range(1, 6), (1.0, 1.1, 0.9, 2.5, 0.4))]
        r = service.compute(rows, req("2026-01", "2026-05"))
        flags = {m["month"]: m["price_flag"] for m in r["monthly"]}
        self.assertEqual(flags, {"2026-01": None, "2026-02": None, "2026-03": None, "2026-04": "high", "2026-05": "low"})
        self.assertAlmostEqual(r["monthly"][3]["unit_price"], 2.5)  # 값은 삭제하지 않음

    def test_outlier_needs_three(self):
        rows = [row("2026-01", "China", 100, 100), row("2026-02", "China", 900, 100)]
        r = service.compute(rows, req("2026-01", "2026-02"))
        self.assertTrue(all(m["price_flag"] is None for m in r["monthly"]))

    def test_suppliers_rank_share_korea_outside_top10(self):
        names = ["China", "Índia", "Vietnã", "Indonésia", "Tailândia", "Turquia", "Malásia", "Itália",
                 "Espanha", "Egito", "México"]
        rows = [row("2026-01", n, 1000 - i * 10, 100) for i, n in enumerate(names)]
        rows.append(row("2026-01", "Coreia do Sul", 5, 1))
        r = service.compute(rows, req("2026-01", "2026-01", countries=["190", "249"]))
        sup = r["suppliers"]
        total = sum(x["fob"] for x in rows)
        self.assertEqual(len(sup["top"]), 10)
        self.assertEqual(sup["top"][0]["country"]["name_ko"], "중국")
        self.assertAlmostEqual(sup["top"][0]["share"], 1000 / total * 100)
        self.assertEqual(sup["korea"]["rank"], 12)
        self.assertAlmostEqual(sup["korea"]["share"], 5 / total * 100)
        self.assertEqual(sup["selected"][0]["country"]["code"], "190")
        self.assertTrue(sup["selected"][1]["no_record"])  # 미국: 기록 없음

    def test_korea_absent(self):
        r = service.compute([row("2026-01", "China", 10, 5)], req("2026-01", "2026-01"))
        self.assertIsNone(r["suppliers"]["korea"])

    def test_unknown_country_name(self):
        r = service.compute([row("2026-01", "Pais Novo", 10, 5)], req("2026-01", "2026-01"))
        self.assertIsNone(r["suppliers"]["top"][0]["country"]["code"])
        self.assertIn("Pais Novo", " ".join(r["notes"]))

    def test_no_data(self):
        r = service.compute([], req("2026-01", "2026-03"))
        self.assertFalse(r["has_data"])
        self.assertIsNone(r["summary"]["fob"])


class AnalyzeTest(unittest.TestCase):
    def setUp(self):
        service.clear_cache()
        patcher = mock.patch.object(comex, "get_latest_month", return_value=(2026, 9, "2026-10-06"))
        self.latest = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(service.clear_cache)

    def payload(self, **kw):
        p = {"code_system": "ncm", "code": "54023310", "from": "2023-10", "to": "2026-09"}
        p.update(kw)
        return p

    def test_full_years_including_prior_and_cache(self):
        with mock.patch.object(comex, "query_imports", return_value=[row("2026-01", "China", 10, 5)]) as q:
            r1 = service.analyze(self.payload())
            r2 = service.analyze(self.payload(**{"from": "2024-01"}))
        q.assert_called_once_with("ncm", "54023310", 2022, 2026)  # 2023-10의 전년 동기 2022-10 포함
        self.assertEqual(r1["sources"][0]["cache_status"], "fresh")
        self.assertEqual(r2["sources"][0]["cache_status"], "cached")
        self.assertEqual(self.latest.call_count, 1)

    def clock(self, start=1000.0):
        """service._monotonic를 손으로 움직이는 시계로 바꿉니다."""
        now = [start]
        p = mock.patch.object(service, "_monotonic", lambda: now[0])
        p.start()
        self.addCleanup(p.stop)
        return now

    def test_refresh_within_ten_minutes_uses_cache(self):
        now = self.clock()
        with mock.patch.object(comex, "query_imports", return_value=[row("2026-01", "China", 10, 5)]) as q:
            service.analyze(self.payload())
            now[0] += service.REFRESH_MIN_SECONDS - 1
            r = service.analyze(self.payload(refresh=True))
            self.assertEqual((q.call_count, r["sources"][0]["cache_status"]), (1, "cached"))
            now[0] += 2  # 10분이 지나면 다시 불러오기가 실제로 다시 조회
            service.analyze(self.payload(refresh=True))
        self.assertEqual(q.call_count, 2)

    def test_cache_lasts_six_hours(self):
        now = self.clock()
        with mock.patch.object(comex, "query_imports", return_value=[row("2026-01", "China", 10, 5)]) as q:
            service.analyze(self.payload())
            now[0] += service.CACHE_TTL_SECONDS - 1
            service.analyze(self.payload())
            self.assertEqual((q.call_count, self.latest.call_count), (1, 1))
            now[0] += 2
            service.analyze(self.payload())
        self.assertEqual((q.call_count, self.latest.call_count), (2, 2))

    def test_rows_cache_limited(self):
        self.clock()
        with mock.patch.object(comex, "query_imports", return_value=[]), mock.patch.object(comex, "lookup_code", return_value="x"):
            for i in range(service.MAX_ROWS_CACHE + 3):
                service.analyze(self.payload(code="5402%04d" % i))
        self.assertEqual(len(service._rows_cache), service.MAX_ROWS_CACHE)

    def test_stale_on_failure(self):
        now = self.clock()
        with mock.patch.object(comex, "query_imports", return_value=[row("2026-01", "China", 10, 5)]):
            service.analyze(self.payload())
        now[0] += service.REFRESH_MIN_SECONDS + 1
        fail = ComexStatError("MA_SOURCE_RATE_LIMITED", "한도", 429, True)
        with mock.patch.object(comex, "query_imports", side_effect=fail):
            r = service.analyze(self.payload(refresh=True))
            self.assertEqual(r["sources"][0]["cache_status"], "stale")
            service.clear_cache()
            with self.assertRaises(ComexStatError):
                service.analyze(self.payload())

    def test_unknown_code(self):
        with mock.patch.object(comex, "query_imports", return_value=[]), \
                mock.patch.object(comex, "lookup_code", return_value=None):
            with self.assertRaises(service.InputError) as ctx:
                service.analyze(self.payload(code="54029999"))
        self.assertIn("찾지 못했습니다", ctx.exception.fields["code"])

    def test_known_code_without_imports(self):
        with mock.patch.object(comex, "query_imports", return_value=[]), \
                mock.patch.object(comex, "lookup_code", return_value="Nome"):
            r = service.analyze(self.payload())
        self.assertFalse(r["has_data"])
        self.assertEqual(r["query"]["code_name"], "Nome")

    def test_latest_unavailable_skips_upper_bound(self):
        self.latest.side_effect = ComexStatError("MA_SOURCE_UNAVAILABLE", "x", 502, True)
        with mock.patch.object(comex, "query_imports", return_value=[row("2026-01", "China", 10, 5)]):
            # 최신 월 확인 실패로 ComexStat 점검을 기억하므로, 통계는 '다시 불러오기'(refresh)일 때만 다시 시도
            r = service.analyze(self.payload(to="2026-12", refresh=True, **{"from": "2026-01"}))
        self.assertIn("최신 제공 월을 확인하지 못해", r["notes"][0])


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        for name, value in (("_sleep", self.sleeps.append), ("_monotonic", lambda: 1000.0)):
            p = mock.patch.object(comex, name, value)
            p.start()
            self.addCleanup(p.stop)
        comex._last_call[0] = 0.0

    def transport(self, responses):
        calls = []

        def fake(method, url, body, timeout):
            calls.append((method, url, body))
            status, doc = responses.pop(0)
            return status, json.dumps(doc).encode("utf-8")
        return mock.patch.object(comex, "_transport", fake), calls

    def test_query_body_and_parse(self):
        doc = {"data": {"list": [{"year": "2026", "monthNumber": "01", "country": "China", "ncm": "Fios",
                                  "metricFOB": "25001752", "metricKG": "0"}]}}
        patch, calls = self.transport([(200, doc)])
        with patch:
            rows = comex.query_imports("ncm", "54023310", 2022, 2026)
        body = calls[0][2]
        self.assertEqual(body["period"], {"from": "2022-01", "to": "2026-12"})
        self.assertEqual(body["filters"], [{"filter": "ncm", "values": ["54023310"]}])
        self.assertEqual(rows[0], {"year": 2026, "month": 1, "country": "China", "fob": 25001752, "kg": 0, "code_name": "Fios"})

    def test_hs6_filter_name(self):
        patch, calls = self.transport([(200, {"data": {"list": []}})])
        with patch:
            comex.query_imports("hs6", "540233", 2025, 2025)
        self.assertEqual(calls[0][2]["filters"][0]["filter"], "subHeading")

    def test_retry_429_then_success(self):
        patch, calls = self.transport([(429, {}), (200, {"data": {"list": []}})])
        with patch:
            self.assertEqual(comex.query_imports("ncm", "54023310", 2025, 2025), [])
        self.assertEqual(len(calls), 2)
        self.assertIn(15.0, self.sleeps)

    def test_max_two_retries(self):
        patch, calls = self.transport([(429, {}), (503, {}), (429, {})])
        with patch, self.assertRaises(ComexStatError) as ctx:
            comex.query_imports("ncm", "54023310", 2025, 2025)
        self.assertEqual(len(calls), 3)
        self.assertEqual(ctx.exception.code, "MA_SOURCE_RATE_LIMITED")

    def test_latest_month_single_attempt(self):
        """최신 월 확인은 재시도 대기 없이 한 번만(점검 중이면 바로 저장 자료로 대신)."""
        patch, calls = self.transport([(503, {})])
        with patch, self.assertRaises(ComexStatError) as ctx:
            comex.get_latest_month()
        self.assertEqual((len(calls), ctx.exception.code), (1, "MA_SOURCE_UNAVAILABLE"))
        self.assertNotIn(15.0, self.sleeps)

    def test_client_error_not_retried(self):
        patch, calls = self.transport([(400, {})])
        with patch, self.assertRaises(ComexStatError) as ctx:
            comex.get_latest_month()
        self.assertEqual((len(calls), ctx.exception.code, ctx.exception.retryable), (1, "MA_SOURCE_REJECTED", False))

    def test_bad_json(self):
        patch, _ = self.transport([(200, {"nope": 1})])
        with patch, self.assertRaises(ComexStatError) as ctx:
            comex.get_latest_month()
        self.assertEqual(ctx.exception.code, "MA_SOURCE_BAD_RESPONSE")

    def test_lookup_exact_match(self):
        doc = {"data": {"list": [{"coNcm": "54023310", "noNCM": "Fios crus"}]}}
        patch, calls = self.transport([(200, doc), (200, {"data": {"list": []}})])
        with patch:
            self.assertEqual(comex.lookup_code("ncm", "54023310"), "Fios crus")
            self.assertIsNone(comex.lookup_code("ncm", "54029999"))
        self.assertIn("/tables/ncm?search=54023310", calls[0][1])


class RoutesTest(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.client = create_app().test_client()
        service.clear_cache()
        self.addCleanup(service.clear_cache)

    def test_invalid_input_400_with_fields(self):
        with mock.patch.object(comex, "get_latest_month", return_value=(2026, 9, "2026-10-06")):
            res = self.client.post("/api/market-analysis/analyze", json={"code_system": "ncm", "code": "12", "from": "2026-01", "to": "2026-02"})
        body = res.get_json()
        self.assertEqual(res.status_code, 400)
        self.assertFalse(body["ok"])
        self.assertIn("code", body["error"]["fields"])

    def test_source_error_status(self):
        fail = ComexStatError("MA_SOURCE_RATE_LIMITED", "한도", 429, True)
        with mock.patch.object(comex, "get_latest_month", return_value=(2026, 9, "2026-10-06")), \
                mock.patch.object(comex, "query_imports", side_effect=fail):
            res = self.client.post("/api/market-analysis/analyze", json={"code_system": "ncm", "code": "54023310", "from": "2026-01", "to": "2026-02"})
        self.assertEqual(res.status_code, 429)
        self.assertTrue(res.get_json()["error"]["retryable"])

    def test_non_json_body(self):
        res = self.client.post("/api/market-analysis/analyze", data="x")
        self.assertEqual(res.status_code, 400)

    def test_meta_defaults(self):
        with mock.patch.object(comex, "get_latest_month", return_value=(2026, 9, "2026-10-06")):
            data = self.client.get("/api/market-analysis/meta").get_json()["data"]
        self.assertEqual((data["default"]["from"], data["default"]["to"]), ("2023-10", "2026-09"))
        self.assertEqual(data["countries"][0]["name_ko"] is not None, True)

    def test_meta_when_source_down(self):
        fail = ComexStatError("MA_SOURCE_UNAVAILABLE", "연결 실패", 502, True)
        with mock.patch.object(comex, "get_latest_month", side_effect=fail):
            data = self.client.get("/api/market-analysis/meta").get_json()["data"]
        self.assertIsNone(data["latest"])
        self.assertEqual(data["error"]["code"], "MA_SOURCE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
