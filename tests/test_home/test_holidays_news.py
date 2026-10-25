"""홈 공휴일·뉴스 수집 모의 테스트. 실제 외부 요청을 보내지 않습니다.

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_home -v

service의 HTTP 함수를 가짜 응답으로 바꿉니다. RSS·KOTRA·BrasilAPI 응답 형태는 2026-10-25 실제 응답과
공식 명세를 따른 가상 값입니다. 인증키는 가짜 문자열입니다.
"""
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from features.home import news_summary, service  # noqa: E402


def rss(*items, lang="pt-BR"):
    body = "".join(
        f"<item><title>{t} - {m}</title><link>{u}</link><pubDate>{d}</pubDate><source url=\"https://x\">{m}</source>"
        f"<description>&lt;a&gt;{t}&lt;/a&gt; {m}</description></item>" for t, u, d, m in items)
    return f'<?xml version="1.0"?><rss><channel><language>{lang}</language>{body}</channel></rss>'.encode()


GOOGLE_RSS = rss(("Indústria têxtil amplia Produção", "https://news.google.com/a1", "Wed, 21 Oct 2026 10:00:00 GMT", "Jornal A"),
                 ("Mesma notícia ABIT", "https://news.google.com/dup", "Tue, 20 Oct 2026 10:00:00 GMT", "Jornal B"),
                 ("Sem data", "https://news.google.com/x", "", "Jornal C"))
ABIT_SITE_RSS = rss(("Mesma notícia ABIT", "https://news.google.com/dup", "Tue, 20 Oct 2026 10:00:00 GMT", "Associação Brasileira da Indústria Têxtil e de Confecção"))
ABIT_PRESS_RSS = rss(("Abit alerta para importações", "https://news.google.com/a2", "Thu, 22 Oct 2026 10:00:00 GMT", "Poder360"))
KOTRA_JSON = json.dumps({"response": {"body": {"itemList": {"item": [
    {"newsTitl": "TEST 브라질 섬유 시장 동향", "kotraNewsUrl": "https://dream.kotra.or.kr/TEST/1", "othbcDt": "2026-10-19", "natn": "브라질", "ovrofInfo": "상파울루무역관"},
    {"newsTitl": "TEST 브라질 자동차", "kotraNewsUrl": "https://dream.kotra.or.kr/TEST/2", "othbcDt": "2026-10-19", "natn": "브라질"},
]}}}}, ensure_ascii=False).encode()


class FakeHttp:
    def __init__(self, fail=()):
        self.fail = set(fail)
        self.calls = []

    def __call__(self, url, accept):
        self.calls.append(url)
        kind = "kotra" if "apis.data.go.kr" in url else "abit_site" if "site%3Aabit" in url else "abit_press" if "%22ABIT%22" in url else "google"
        if kind in self.fail or (kind.startswith("abit") and "abit" in self.fail):
            raise service.NewsFetchError("timeout")
        return {"kotra": KOTRA_JSON, "abit_site": ABIT_SITE_RSS, "abit_press": ABIT_PRESS_RSS, "google": GOOGLE_RSS}[kind]


class NewsTestBase(unittest.TestCase):
    def setUp(self):
        service._news_cache.clear()
        news_summary._cache.clear()
        self.addCleanup(service._news_cache.clear)
        self.addCleanup(news_summary._cache.clear)
        env = mock.patch.dict(os.environ, {service.KOTRA_KEY_ENV: "TEST-KOTRA-KEY"})
        env.start()
        self.addCleanup(env.stop)

    def use(self, fake):
        p = mock.patch.object(service, "_http_get", fake)
        p.start()
        self.addCleanup(p.stop)
        return fake


class NewsTests(NewsTestBase):
    def test_collect_normalize_dedupe_sort(self):
        fake = self.use(FakeHttp())
        data = service.get_news()
        self.assertEqual(len(fake.calls), 4)  # kotra 1 + google 1 + abit 2
        self.assertTrue(all(v["status"] == "ok" for v in data["media"].values()))
        titles = [(i["origin"], i["title"]) for i in data["items"]]
        self.assertEqual(titles, [("abit", "Abit alerta para importações"), ("google", "Indústria têxtil amplia Produção"),
                                  ("abit", "Mesma notícia ABIT"), ("kotra", "TEST 브라질 섬유 시장 동향")])  # 중복은 abit 유지, 최신순
        kotra = data["items"][-1]
        self.assertEqual((kotra["media"], kotra["published_at"], kotra["lang"]), ("KOTRA 해외시장뉴스 · 상파울루무역관", "2026-10-19", "ko"))
        self.assertFalse(any("snippet" in i or "summary_ko" in i for i in data["items"]))
        self.assertEqual(data["summary"], {"pending": 3})  # KOTRA 제외

    def test_cache_and_refresh(self):
        fake = self.use(FakeHttp())
        service.get_news()
        service.get_news()
        self.assertEqual(len(fake.calls), 4)
        service.get_news(refresh="abit")
        self.assertEqual(len(fake.calls), 6)
        for entry in service._news_cache.values():
            entry["expires"] = 0
        service.get_news()
        self.assertEqual(len(fake.calls), 10)

    def test_failure_isolation_and_stale(self):
        self.use(FakeHttp())
        service.get_news()
        self.use(FakeHttp(fail={"google"}))
        data = service.get_news(refresh="google")
        self.assertEqual((data["media"]["google"]["status"], data["media"]["google"]["stale"]), ("error", True))
        self.assertTrue(data["media"]["google"]["error"]["retryable"])
        self.assertTrue(any(i["origin"] == "google" for i in data["items"]))  # 이전 수집분 유지
        self.assertEqual(data["media"]["abit"]["status"], "ok")

    def test_kotra_key_missing(self):
        os.environ.pop(service.KOTRA_KEY_ENV)
        fake = self.use(FakeHttp())
        data = service.get_news()
        self.assertEqual((data["media"]["kotra"]["status"], data["media"]["kotra"]["error"]["code"]), ("not_configured", "key_missing"))
        self.assertFalse(any("apis.data.go.kr" in u for u in fake.calls))

    def test_all_fail(self):
        self.use(FakeHttp(fail={"kotra", "google", "abit"}))
        data = service.get_news()
        self.assertEqual(data["items"], [])
        self.assertTrue(all(v["status"] == "error" for v in data["media"].values()))

    def test_route_refresh_validation(self):
        self.use(FakeHttp())
        client = app.test_client()
        self.assertTrue(client.get("/api/home/news").get_json()["ok"])
        for q in ("?refresh=bad", "?refresh="):
            self.assertEqual(client.get("/api/home/news" + q).status_code, 400)


class HolidayTests(unittest.TestCase):
    def setUp(self):
        service._cache.clear()
        self.addCleanup(service._cache.clear)

    def test_brasilapi_cached(self):
        calls = []

        def fetch(year):
            calls.append(year)
            return [{"date": f"{year}-11-02", "name": "Finados"}]
        with mock.patch.object(service, "_fetch_brasilapi", fetch):
            first = service.get_holidays(2026)
            second = service.get_holidays(2026)
        self.assertEqual((first["source"], first["holidays"]), ("brasilapi", [{"date": "2026-11-02", "name": "Finados"}]))
        self.assertIs(first, second)
        self.assertEqual(calls, [2026])

    def test_failure_fallback_and_none(self):
        def fail(year):
            raise urllib.error.URLError("offline")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(service, "_fetch_brasilapi", fail), \
                mock.patch.object(service, "FALLBACK_DIR", Path(tmp)):
            self.assertEqual(service.get_holidays(2026)["source"], "none")
            Path(tmp, "holidays_br_2026.json").write_text(json.dumps([{"date": "2026-11-02", "name": "TEST_ONLY"}]), encoding="utf-8")
            self.assertEqual(service.get_holidays(2026)["source"], "fallback")
        self.assertNotIn(2026, service._cache)  # 실패는 캐시하지 않음

    def test_route_year_validation(self):
        with mock.patch.object(service, "_fetch_brasilapi", lambda year: [{"date": f"{year}-01-01", "name": "TEST"}]):
            client = app.test_client()
            self.assertTrue(client.get("/api/home/holidays?year=2026").get_json()["ok"])
            for q in ("", "?year=abc", "?year=1800"):
                self.assertEqual(client.get("/api/home/holidays" + q).status_code, 400)


if __name__ == "__main__":
    unittest.main()
