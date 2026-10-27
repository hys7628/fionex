"""홈 환율 모의 테스트. 실제 외부 API 요청을 보내지 않습니다.

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_home -v

fx._http_get_json을 가짜 응답으로 바꿉니다. 응답 형식은 공식 명세(수출입은행 개발명세, BCB PTAX OData 메타데이터)와
2026-10-25 실제 PTAX 응답 형태를 따른 가상 값입니다. 인증키는 가짜 문자열입니다.
"""
import io
import logging
import os
import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from features.home import fx  # noqa: E402

FAKE_KEY = "TEST-EXIM-KEY-0000"
SUNDAY = date(2026, 10, 25)


def exim_item(rate, unit="USD", result=1):
    return {"result": result, "cur_unit": unit, "ttb": "0", "tts": "0", "deal_bas_r": rate, "bkpr": "0",
            "yy_efee_r": "0", "ten_dd_efee_r": "0", "kftc_bkpr": "0", "kftc_deal_bas_r": rate, "cur_nm": "TEST"}


def ptax_rows(*pairs):
    return {"value": [{"cotacaoCompra": float(v) - 0.0006, "cotacaoVenda": v, "dataHoraCotacao": d + " 13:05:00.000"}
                      for d, v in pairs]}


class FakeHttp:
    """URL로 수출입은행/PTAX를 구분해 응답합니다. exim: {YYYYMMDD: 응답}, 없는 날짜는 [](비영업일)."""

    def __init__(self, exim=None, ptax=None, exim_error=None, ptax_error=None):
        self.exim, self.ptax = exim or {}, ptax
        self.exim_error, self.ptax_error = exim_error, ptax_error
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if url.startswith(fx.EXIM_URL):
            if self.exim_error:
                raise fx.FxError(self.exim_error)
            stamp = url.split("searchdate=")[1][:8]
            return self.exim.get(stamp, [])
        if self.ptax_error:
            raise fx.FxError(self.ptax_error)
        return self.ptax

    def count(self, prefix):
        return sum(1 for u in self.calls if u.startswith(prefix))


class FxTestBase(unittest.TestCase):
    def setUp(self):
        fx._cache.clear()
        fx._exim_days.clear()
        self.addCleanup(fx._cache.clear)
        self.addCleanup(fx._exim_days.clear)
        env = mock.patch.dict(os.environ, {fx.EXIM_KEY_ENV: FAKE_KEY})
        env.start()
        self.addCleanup(env.stop)
        today = mock.patch.object(fx, "_today", lambda tz: SUNDAY)
        today.start()
        self.addCleanup(today.stop)

    def use(self, fake):
        p = mock.patch.object(fx, "_http_get_json", fake)
        p.start()
        self.addCleanup(p.stop)
        return fake


NORMAL_EXIM = {"20261023": [exim_item("1,405.2"), exim_item("1.9", "AED")], "20261022": [exim_item("1,400.9")]}
NORMAL_PTAX = ptax_rows(("2026-10-21", 5.0277), ("2026-10-22", 5.0383), ("2026-10-23", 5.0377))


class ParseTests(unittest.TestCase):
    def test_parse_exim(self):
        self.assertEqual(fx.parse_exim([exim_item("291.7", "AED"), exim_item("1,405.2")]), Decimal("1405.2"))
        self.assertIsNone(fx.parse_exim([]))  # 비영업일·고시 전
        self.assertIsNone(fx.parse_exim([exim_item(None)]))  # null 값
        self.assertIsNone(fx.parse_exim([exim_item("1.9", "AED")]))  # USD 없음
        for result, code in ((3, "access_denied"), (4, "rate_limited"), (2, "invalid_response"), (9, "invalid_response")):
            with self.assertRaises(fx.FxError) as ctx:
                fx.parse_exim([exim_item(None, None, result)])
            self.assertEqual(ctx.exception.code, code)
        for bad in ({"result": 1}, ["x"]):
            with self.assertRaises(fx.FxError):
                fx.parse_exim(bad)

    def test_parse_ptax(self):
        rows = fx.parse_ptax({"value": [
            {"cotacaoCompra": 5.0, "cotacaoVenda": 5.0383, "dataHoraCotacao": "2026-10-22 13:12:09.300403"},
            {"cotacaoCompra": 5.0, "cotacaoVenda": 5.0377, "dataHoraCotacao": "2026-10-23 13:07:14.754567"},
            {"cotacaoCompra": 5.0, "cotacaoVenda": 5.0300, "dataHoraCotacao": "2026-10-23 10:00:00.000"},
            {"cotacaoCompra": 5.0, "cotacaoVenda": None, "dataHoraCotacao": "2026-10-21 13:00:00"},
            {"cotacaoCompra": 5.0, "cotacaoVenda": 5.1, "dataHoraCotacao": "bad"},
        ]})
        self.assertEqual(rows, [(date(2026, 10, 22), Decimal("5.0383")), (date(2026, 10, 23), Decimal("5.0377"))])
        for bad in ({}, {"value": "x"}, []):
            with self.assertRaises(fx.FxError):
                fx.parse_ptax(bad)

    def test_math(self):
        self.assertEqual(fx.change_pct(Decimal("1405.2"), Decimal("1400.9")), 0.31)
        self.assertEqual(fx.change_pct(Decimal("5.0377"), Decimal("5.0383")), -0.01)
        derived = fx.derive_brl_krw({"status": "ok", "rate": 1400.0, "date": "2026-10-23"},
                                    {"status": "ok", "rate": 5.0, "date": "2026-10-23"})
        self.assertEqual(derived["rate"], 280.0)
        self.assertIsNone(fx.derive_brl_krw({"status": "error"}, {"status": "ok", "rate": 5.0}))
        self.assertIsNone(fx.derive_brl_krw({"status": "ok", "rate": 1400.0}, {"status": "not_configured"}))


class FxTests(FxTestBase):
    def test_weekend_uses_latest_published_and_previous(self):
        fake = self.use(FakeHttp(exim=NORMAL_EXIM, ptax=NORMAL_PTAX))
        data = fx.get_fx()
        krw, brl = data["usd_krw"], data["usd_brl"]
        self.assertEqual((krw["status"], krw["rate"], krw["date"]), ("ok", 1405.2, "2026-10-23"))  # 일→토→금
        self.assertEqual(krw["previous"], {"rate": 1400.9, "date": "2026-10-22"})
        self.assertEqual(krw["change_pct"], 0.31)
        self.assertEqual((brl["rate"], brl["date"], brl["previous"]["date"], brl["change_pct"]), (5.0377, "2026-10-23", "2026-10-22", -0.01))
        self.assertEqual(data["brl_krw"]["rate"], float((Decimal("1405.2") / Decimal("5.0377")).quantize(Decimal("0.0001"))))
        self.assertEqual((data["brl_krw"]["usd_krw_date"], data["brl_krw"]["usd_brl_date"]), ("2026-10-23", "2026-10-23"))
        self.assertEqual(fake.count(fx.EXIM_URL), 4)  # 25·24·23 + 직전 22
        self.assertEqual(fake.count("https://olinda"), 1)  # 기간 1회
        ptax_url = [u for u in fake.calls if u.startswith("https://olinda")][0]
        self.assertIn("@dataInicial='10-11-2026'", ptax_url)
        self.assertIn("@dataFinalCotacao='10-25-2026'", ptax_url)

    def test_cache(self):
        fake = self.use(FakeHttp(exim=NORMAL_EXIM, ptax=NORMAL_PTAX))
        fx.get_fx()
        fx.get_fx()
        self.assertEqual(len(fake.calls), 5)  # 두 번째는 캐시
        for entry in fx._cache.values():
            entry["expires"] = 0
        fx.get_fx()
        # 만료 후 수출입은행은 오늘(보관 안 함)만 다시 묻고 지난 날짜는 날짜별 보관분 사용
        self.assertEqual(fake.count(fx.EXIM_URL), 5)
        self.assertEqual(fake.count("https://olinda"), 2)

    def clock(self):
        now = [1000.0]
        p = mock.patch.object(fx, "monotonic", lambda: now[0])
        p.start()
        self.addCleanup(p.stop)
        return now

    def test_refresh_one_source(self):
        now = self.clock()
        fake = self.use(FakeHttp(exim=NORMAL_EXIM, ptax=NORMAL_PTAX))
        fx.get_fx()
        before = list(fake.calls)
        now[0] += fx.REFRESH_MIN_SECONDS
        fx.get_fx(refresh="usd_brl")
        new = fake.calls[len(before):]
        self.assertEqual(len(new), 1)
        self.assertTrue(new[0].startswith("https://olinda"))

    def test_refresh_within_a_minute_uses_cache(self):
        now = self.clock()
        fake = self.use(FakeHttp(exim=NORMAL_EXIM, ptax=NORMAL_PTAX))
        fx.get_fx()
        before = len(fake.calls)
        now[0] += fx.REFRESH_MIN_SECONDS - 1
        fx.get_fx(refresh="usd_brl")
        self.assertEqual(len(fake.calls), before)  # 1분 안 연타: 다시 조회하지 않음

    def test_cache_three_hours(self):
        now = self.clock()
        fake = self.use(FakeHttp(exim=NORMAL_EXIM, ptax=NORMAL_PTAX))
        fx.get_fx()
        before = len(fake.calls)
        now[0] += fx.CACHE_SECONDS - 1
        fx.get_fx()
        self.assertEqual(len(fake.calls), before)
        now[0] += 2
        fx.get_fx()
        self.assertGreater(len(fake.calls), before)

    def test_no_rate_within_7_days(self):
        self.use(FakeHttp(exim={"20261017": [exim_item("1,390.0")]}, ptax=ptax_rows(("2026-10-17", 5.1))))
        data = fx.get_fx()
        for name in ("usd_krw", "usd_brl"):
            self.assertEqual(data[name]["status"], "error")
            self.assertEqual(data[name]["error"]["code"], "no_recent_rate")
            self.assertIsNone(data[name]["rate"])
        self.assertIsNone(data["brl_krw"])

    def test_no_previous_means_no_change(self):
        self.use(FakeHttp(exim={"20261023": [exim_item("1,405.2")]}, ptax=ptax_rows(("2026-10-23", 5.0377))))
        data = fx.get_fx()
        for name in ("usd_krw", "usd_brl"):
            self.assertEqual(data[name]["status"], "ok")
            self.assertIsNone(data[name]["previous"])
            self.assertIsNone(data[name]["change_pct"])

    def test_exim_fails_ptax_ok(self):
        self.use(FakeHttp(exim_error="timeout", ptax=NORMAL_PTAX))
        data = fx.get_fx()
        self.assertEqual((data["usd_krw"]["status"], data["usd_krw"]["error"]["code"]), ("error", "timeout"))
        self.assertTrue(data["usd_krw"]["error"]["retryable"])
        self.assertIsNone(data["usd_krw"]["rate"])
        self.assertEqual(data["usd_brl"]["status"], "ok")
        self.assertIsNone(data["brl_krw"])

    def test_ptax_fails_exim_ok(self):
        self.use(FakeHttp(exim=NORMAL_EXIM, ptax_error="fetch_failed"))
        data = fx.get_fx()
        self.assertEqual(data["usd_krw"]["status"], "ok")
        self.assertEqual(data["usd_brl"]["status"], "error")
        self.assertIsNone(data["brl_krw"])

    def test_both_fail_and_failure_ttl(self):
        fake = self.use(FakeHttp(exim_error="fetch_failed", ptax_error="fetch_failed"))
        data = fx.get_fx()
        self.assertTrue(all(data[n]["status"] == "error" for n in ("usd_krw", "usd_brl")))
        self.assertIsNone(data["brl_krw"])
        fx.get_fx()
        self.assertEqual(len(fake.calls), 2)  # 실패도 잠시 캐시
        for entry in fx._cache.values():
            self.assertLessEqual(entry["expires"] - fx.monotonic(), fx.FAILURE_CACHE_SECONDS + 1)

    def test_unexpected_exception_isolated(self):
        def boom(url):
            if url.startswith(fx.EXIM_URL):
                raise RuntimeError("unexpected")
            return NORMAL_PTAX
        self.use(boom)
        data = fx.get_fx()
        self.assertEqual(data["usd_krw"]["error"]["code"], "fetch_failed")
        self.assertEqual(data["usd_brl"]["status"], "ok")

    def test_key_missing(self):
        os.environ.pop(fx.EXIM_KEY_ENV)
        fake = self.use(FakeHttp(exim=NORMAL_EXIM, ptax=NORMAL_PTAX))
        data = fx.get_fx()
        self.assertEqual((data["usd_krw"]["status"], data["usd_krw"]["error"]["code"]), ("not_configured", "key_missing"))
        self.assertFalse(data["usd_krw"]["error"]["retryable"])
        self.assertEqual(fake.count(fx.EXIM_URL), 0)
        self.assertEqual(data["usd_brl"]["status"], "ok")

    def test_auth_error_not_logged_with_key(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logging.getLogger().addHandler(handler)
        self.addCleanup(logging.getLogger().removeHandler, handler)
        self.use(FakeHttp(exim={"20261025": [exim_item(None, None, 3)]}, ptax=NORMAL_PTAX))
        data = fx.get_fx()
        self.assertEqual(data["usd_krw"]["error"]["code"], "access_denied")
        self.assertFalse(data["usd_krw"]["error"]["retryable"])
        self.assertNotIn(FAKE_KEY, stream.getvalue())
        self.assertNotIn(FAKE_KEY, str(data))


class RouteTests(FxTestBase):
    def test_route(self):
        self.use(FakeHttp(exim=NORMAL_EXIM, ptax=NORMAL_PTAX))
        client = app.test_client()
        body = client.get("/api/home/fx").get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(set(body["data"]), {"usd_krw", "usd_brl", "brl_krw"})
        for q in ("?refresh=bad", "?refresh=", "?refresh=USD_KRW"):
            res = client.get("/api/home/fx" + q)
            self.assertEqual(res.status_code, 400)
            self.assertEqual(res.get_json()["error"]["code"], "invalid_refresh")


if __name__ == "__main__":
    unittest.main()
