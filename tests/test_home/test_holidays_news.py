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
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from features.home import news_summary, service  # noqa: E402


def rss(*items, lang="pt-BR"):
    """items: (제목, 링크, 날짜, 매체[, 매체 주소]). 매체 주소 기본값은 https://jornal.com.br."""
    body = "".join(
        f"<item><title>{t} - {m}</title><link>{u}</link><pubDate>{d}</pubDate>"
        f"<source url=\"{(rest or ['https://jornal.com.br'])[0]}\">{m}</source>"
        f"<description>&lt;a&gt;{t}&lt;/a&gt; {m}</description></item>" for t, u, d, m, *rest in items)
    return f'<?xml version="1.0"?><rss><channel><language>{lang}</language>{body}</channel></rss>'.encode()


GOOGLE_RSS = rss(("Indústria têxtil amplia Produção", "https://news.google.com/a1", "Wed, 21 Oct 2026 10:00:00 GMT", "Jornal A"),
                 ("Mesma notícia ABIT sobre fios", "https://news.google.com/dup", "Tue, 20 Oct 2026 10:00:00 GMT", "Jornal B"),
                 ("Sem data", "https://news.google.com/x", "", "Jornal C"))
ABIT_SITE_RSS = rss(("Mesma notícia ABIT sobre fios", "https://news.google.com/dup", "Tue, 20 Oct 2026 10:00:00 GMT",
                      "Associação Brasileira da Indústria Têxtil e de Confecção", "https://www.abit.org.br"))
ABIT_PRESS_RSS = rss(("Abit alerta para importações de vestuário", "https://news.google.com/a2", "Thu, 22 Oct 2026 10:00:00 GMT", "Poder360"))
KOTRA_JSON = json.dumps({"response": {"body": {"itemList": {"item": [
    {"newsTitl": "TEST 브라질 섬유 시장 동향", "kotraNewsUrl": "https://dream.kotra.or.kr/TEST/1", "othbcDt": "2026-10-19", "natn": "브라질", "ovrofInfo": "상파울루무역관"},
    {"newsTitl": "TEST 브라질 자동차", "kotraNewsUrl": "https://dream.kotra.or.kr/TEST/2", "othbcDt": "2026-10-19", "natn": "브라질"},
]}}}}, ensure_ascii=False).encode()


class FakeHttp:
    def __init__(self, fail=(), **bodies):
        self.fail = set(fail)
        self.calls = []
        self.bodies = {"kotra": KOTRA_JSON, "abit_site": ABIT_SITE_RSS, "abit_press": ABIT_PRESS_RSS, "google": GOOGLE_RSS, **bodies}

    def __call__(self, url, accept):
        self.calls.append(url)
        kind = "kotra" if "apis.data.go.kr" in url else "abit_site" if "site%3Aabit" in url else "abit_press" if "%22ABIT%22" in url else "google"
        if kind in self.fail or (kind.startswith("abit") and "abit" in self.fail):
            raise service.NewsFetchError("timeout")
        return self.bodies[kind]


class NewsTestBase(unittest.TestCase):
    def setUp(self):
        service._news_cache.clear()
        news_summary._cache.clear()
        self.addCleanup(service._news_cache.clear)
        self.addCleanup(news_summary._cache.clear)
        env = mock.patch.dict(os.environ, {service.KOTRA_KEY_ENV: "TEST-KOTRA-KEY"})
        env.start()
        self.addCleanup(env.stop)

    def clock(self):
        now = [1000.0]
        p = mock.patch.object(service, "monotonic", lambda: now[0])
        p.start()
        self.addCleanup(p.stop)
        return now

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
        self.assertEqual(titles, [("abit", "Abit alerta para importações de vestuário"), ("google", "Indústria têxtil amplia Produção"),
                                  ("abit", "Mesma notícia ABIT sobre fios"), ("kotra", "TEST 브라질 섬유 시장 동향")])  # 중복은 abit 유지, 최신순
        kotra = data["items"][-1]
        self.assertEqual((kotra["media"], kotra["published_at"], kotra["lang"]), ("KOTRA 해외시장뉴스 · 상파울루무역관", "2026-10-19", "ko"))
        self.assertFalse(any("snippet" in i or "summary_ko" in i for i in data["items"]))
        self.assertEqual(data["summary"], {"pending": 3})  # KOTRA 제외

    def test_cache_and_refresh(self):
        now = self.clock()
        fake = self.use(FakeHttp())
        service.get_news()
        service.get_news()
        self.assertEqual(len(fake.calls), 4)
        service.get_news(refresh="abit")  # 성공 수집 1분 안: 다시 가져오지 않음
        self.assertEqual(len(fake.calls), 4)
        now[0] += service.NEWS_REFRESH_MIN_SECONDS
        service.get_news(refresh="abit")
        self.assertEqual(len(fake.calls), 6)
        now[0] += service.NEWS_CACHE_SECONDS - service.NEWS_REFRESH_MIN_SECONDS - 1
        service.get_news()  # 6시간 안: 캐시
        self.assertEqual(len(fake.calls), 6)
        for entry in service._news_cache.values():
            entry["expires"] = 0
        service.get_news()
        self.assertEqual(len(fake.calls), 10)

    def test_failure_isolation_and_stale(self):
        now = self.clock()
        self.use(FakeHttp())
        service.get_news()
        now[0] += service.NEWS_REFRESH_MIN_SECONDS
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


def kotra_json(*items):
    return json.dumps({"response": {"body": {"itemList": {"item": list(items)}}}}, ensure_ascii=False).encode()


def item(title, origin="google", published_at="2026-10-20T10:00:00-03:00", domain="jornal.com.br"):
    return {"title": title, "url": "https://news.google.com/" + title, "origin": origin, "published_at": published_at,
            "media_domain": domain}


class RelevanceTests(unittest.TestCase):
    def test_keyword_filter(self):
        for title in ("Indústria têxtil brasileira amplia uso de poliéster reciclado",
                      "Novos fios reciclados chegam ao setor de confecção",
                      "Setor TEXTIL sem acento também passa",  # 악센트·대소문자 무시
                      "Exportações da indústria da moda crescem"):  # 'moda'는 구문으로만
            self.assertTrue(service.is_relevant_news(item(title)), title)
        for title in ("Como a IA está transformando empregos no Brasil", "Conheça uma bela vila italiana",
                      "Semana de moda movimenta São Paulo", "Fiocruz anuncia vacina"):  # 'moda' 단독, 단어 일부(fio)
            self.assertFalse(service.is_relevant_news(item(title)), title)

    def test_media_domain_rules(self):
        title = "Indústria têxtil amplia produção"
        self.assertFalse(service.is_relevant_news(item(title, domain="welectric.pt")))  # .pt 매체
        self.assertFalse(service.is_relevant_news(item(title, domain="www.jornal.pt")))
        self.assertFalse(service.is_relevant_news(item(title, domain="portugaltextil.com")))  # EXCLUDED_MEDIA_DOMAINS
        self.assertTrue(service.is_relevant_news(item("Reforma tributária e exportações", domain="abit.org.br")))  # 공식 도메인
        self.assertTrue(service.is_relevant_news(item(title, domain="ptnews.com.br")))  # .pt로 끝나지 않음

    def test_source_domain_from_rss_not_google_link(self):
        body = rss(("Indústria têxtil portuguesa", "https://news.google.com/p1", "Wed, 21 Oct 2026 10:00:00 GMT",
                    "Portugal Têxtil", "https://www.portugaltextil.com"),
                   ("Indústria têxtil cresce", "https://news.google.com/p2", "Wed, 21 Oct 2026 09:00:00 GMT", "Jornal A"))
        items = service.parse_google_rss(body, "google")
        self.assertEqual([i["media_domain"] for i in items], ["portugaltextil.com", "jornal.com.br"])
        self.assertEqual([service.is_relevant_news(i) for i in items], [False, True])

    def test_counts_in_media(self):
        NewsTestBase.setUp(self)
        NewsTestBase.use(self, FakeHttp())
        media = service.get_news()["media"]
        self.assertEqual({m: (v["collected"], v["after_filter"], v["count"]) for m, v in media.items()},
                         {"kotra": (2, 1, 1), "google": (2, 2, 2), "abit": (2, 2, 2)})


class TopicTagTests(NewsTestBase):
    """뉴스 주제 태그(코드 기반, 제목만). 필수 사례 4개 + 최대 2개·순서·API tags."""

    def test_required_cases(self):
        cases = [
            ("Brasil regulamenta acesso a cotas de exportação para a Noruega", ["규제·무역"]),
            ("Abrapa destaca inovação e sustentabilidade como caminhos para o futuro do algodão", ["원사", "리사이클·ESG"]),
            ("Setor enfrenta o desafio de crescer em 2027", ["기타"]),  # desafio 안의 fio는 원사가 아님
            ("Veja as novidades da semana", ["기타"]),
        ]
        for title, expected in cases:
            self.assertEqual(service.news_topics(title), expected, title)

    def test_normalize_word_boundary_max_two_and_order(self):
        self.assertEqual(service.news_topics("FIOS de POLIÉSTER"), ["원사"])  # 대소문자·악센트 무시
        self.assertEqual(service.news_topics("Desafios e desafio"), ["기타"])
        self.assertEqual(service.news_topics("Novo fio"), ["원사"])
        # 원사·원단·규제·ESG·패션 모두 맞아도 표 순서 앞쪽 2개
        tags = service.news_topics("Fios e tecidos reciclados: exportação e moda")
        self.assertEqual(tags, ["원사", "원단"])
        self.assertEqual(service.news_topics("Exportações de moda sustentável"), ["규제·무역", "리사이클·ESG"])
        self.assertEqual(service.news_topics("한국 원사 수출 동향"), ["원사", "규제·무역"])  # KOTRA 한국어 제목
        self.assertEqual(service.news_topics("TEST 브라질 섬유 시장 동향"), ["기타"])

    def test_constants_cover_order(self):
        self.assertEqual(service.NEWS_TOPIC_ORDER, ("원사", "원단", "규제·무역", "리사이클·ESG", "패션·리테일"))
        self.assertEqual(set(service.NEWS_TOPIC_KEYWORDS), set(service.NEWS_TOPIC_ORDER))

    def test_api_items_have_tags(self):
        self.use(FakeHttp())
        body = app.test_client().get("/api/home/news").get_json()
        items = body["data"]["items"]
        self.assertTrue(items)
        for item in items:
            self.assertTrue(1 <= len(item["tags"]) <= 2, item)
        self.assertEqual({i["title"]: i["tags"] for i in items}["Abit alerta para importações de vestuário"], ["규제·무역", "패션·리테일"])

    def test_relevance_filter_unchanged_by_tags(self):
        # 관련성 필터는 별도 상수: 태그 키워드(예: cotas)만 있는 제목은 여전히 걸러짐
        self.assertFalse(service.is_relevant_news(item("Brasil regulamenta acesso a cotas de exportação para a Noruega")))


class KotraExposureTests(NewsTestBase):
    """A 응답 0건 · B 필터 후 0건 · C 최소 노출 · D 강제 포함 없음 · E 중복 없음."""

    def kotra_media(self, body):
        self.use(FakeHttp(kotra=body))
        with self.assertLogs(service.logger, "INFO") as logs:
            media = service.get_news()["media"]["kotra"]
        return media, [line for line in logs.output if "뉴스 kotra" in line]

    def test_a_response_zero(self):
        media, logs = self.kotra_media(kotra_json())
        self.assertEqual((media["status"], media["collected"], media["after_filter"], media["count"]), ("ok", 0, 0, 0))
        self.assertIn("collected=0 filtered=0", logs[0])

    def test_b_filter_zero(self):
        media, logs = self.kotra_media(kotra_json(
            {"newsTitl": "TEST 브라질 자동차", "kotraNewsUrl": "https://dream.kotra.or.kr/TEST/2", "othbcDt": "2026-10-19", "natn": "브라질"}))
        self.assertEqual((media["collected"], media["after_filter"], media["count"]), (1, 0, 0))
        self.assertIn("collected=1 filtered=0", logs[0])

    def test_c_minimum_includes_older_kotra(self):
        news = [item(f"têxtil {n}", published_at=f"2026-10-2{n}T10:00:00-03:00") for n in range(9, -1, -1)]
        news.append(item("KOTRA 섬유", origin="kotra", published_at="2026-10-01"))
        top, counts = service.select_top_news(news, 8, {"kotra": 1})
        self.assertEqual(len(top), 8)
        self.assertEqual(top[-1]["origin"], "kotra")  # 선정 후에도 최신순
        self.assertEqual(counts, {"google": 7, "kotra": 1})
        self.assertEqual(service.select_top_news(news, 8)[1], {"google": 8})  # 최소 노출 없으면 C(선정 0건)

    def test_d_no_kotra_no_fake(self):
        news = [item(f"têxtil {n}") for n in range(3)]
        top, counts = service.select_top_news(news, 8, {"kotra": 1})
        self.assertEqual((top, counts), (news, {"google": 3}))

    def test_e_no_duplicate_when_already_selected(self):
        news = [item("KOTRA 섬유", origin="kotra", published_at="2026-10-25")] + [item(f"têxtil {n}") for n in range(9)]
        top, counts = service.select_top_news(news, 8, {"kotra": 1})
        self.assertEqual(len(top), 8)
        self.assertEqual(len({id(i) for i in top}), 8)
        self.assertEqual(counts, {"kotra": 1, "google": 7})


class NewsSearchTests(NewsTestBase):
    """업계 소식 상세의 Google News 추가 검색(/api/home/news/search). 외부 요청 없음(가짜 응답)."""

    SEARCH_RSS = rss(
        ("Fios de poliéster reciclado ganham espaço", "https://news.google.com/s1", "Wed, 21 Oct 2026 10:00:00 GMT", "Jornal A"),
        ("Tecidos técnicos para exportação", "https://news.google.com/s2", "Tue, 20 Oct 2026 10:00:00 GMT", "Jornal B"),
        ("Malharia amplia produção no Sul", "https://news.google.com/s3", "Mon, 19 Oct 2026 10:00:00 GMT", "Jornal C"),
        ("Indústria têxtil portuguesa cresce", "https://news.google.com/s4", "Mon, 19 Oct 2026 09:00:00 GMT", "Jornal PT", "https://www.jornal.pt"),
        ("Como a IA está mudando empregos", "https://news.google.com/s5", "Sun, 18 Oct 2026 10:00:00 GMT", "Jornal D"),
        ("Fios de poliéster reciclado ganham espaço", "https://news.google.com/s1", "Wed, 21 Oct 2026 10:00:00 GMT", "Jornal A"),  # 중복
    )

    def fake(self, body=None, fail=False):
        calls = []

        def get(url, accept):
            calls.append(url)
            if fail:
                raise service.NewsFetchError("timeout")
            return body if body is not None else self.SEARCH_RSS
        self.use(get)
        return calls

    def test_relevance_pt_unrelated_duplicate_and_tags(self):
        calls = self.fake()
        data = service.search_news("  poliéster   reciclado ")
        # A 6건(중복 1) → 관련 3건, B .pt 제외, C 무관 제외, D 중복 1건
        self.assertEqual([i["title"] for i in data["items"]],
                         ["Fios de poliéster reciclado ganham espaço", "Tecidos técnicos para exportação", "Malharia amplia produção no Sul"])
        self.assertEqual((data["count"], data["collected"], data["after_filter"], data["source"], data["query"]),
                         (3, 5, 3, "google_news_rss", "poliéster reciclado"))
        for item in data["items"]:  # E 태그 1~2개, 기존 항목 구조
            self.assertTrue(1 <= len(item["tags"]) <= 2)
            self.assertEqual(item["origin"], "google")
        self.assertEqual(data["items"][0]["tags"], ["원사", "리사이클·ESG"])
        # 검색어 구성: 따옴표 묶음 + 섬유 낱말 + 기간, 기존 지역·언어 설정
        url = urllib.parse.unquote(calls[0])
        self.assertIn('"poliéster reciclado" (têxtil OR tecido OR fio OR confecção OR vestuário) when:90d', url)
        self.assertIn("hl=pt-BR&gl=BR&ceid=BR:pt-419", url)

    def test_limit_constant(self):
        many = rss(*[(f"Tecido número {n}", f"https://news.google.com/m{n}", "Wed, 21 Oct 2026 10:00:00 GMT", "Jornal") for n in range(30)])
        self.fake(many)
        self.assertEqual(service.search_news("tecido")["count"], service.NEWS_SEARCH_LIMIT)

    def test_no_new_ai_call_but_reuses_cached_summary(self):
        self.fake()
        target = service.parse_google_rss(self.SEARCH_RSS, "google")[0]
        news_summary._cache[(target["id"], target["title"])] = {"summary": "재활용 폴리에스터 원사 확대", "expires": 10 ** 12}
        with mock.patch.object(news_summary, "_request", side_effect=AssertionError("OpenAI 호출 금지")):
            data = service.search_news("poliéster")
        self.assertEqual(data["items"][0].get("summary_ko"), "재활용 폴리에스터 원사 확대")
        self.assertNotIn("summary_ko", data["items"][1])

    def test_route_ok_invalid_and_failure_keeps_news(self):
        client = app.test_client()
        self.use(FakeHttp())
        client.get("/api/home/news")
        before = client.get("/api/home/news").get_json()["data"]["items"]
        calls = self.fake()
        body = client.get("/api/home/news/search?q=" + urllib.parse.quote("poliéster")).get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(len(calls), 1)
        # G 빈 검색어·공백·1글자·너무 김 → 400, 외부 요청 없음
        for q in ("", "   ", "a", "x" * 81):
            res = client.get("/api/home/news/search?q=" + urllib.parse.quote(q))
            self.assertEqual((res.status_code, res.get_json()["error"]["code"]), (400, "invalid_query"), q)
        self.assertEqual(client.get("/api/home/news/search").status_code, 400)
        self.assertEqual(len(calls), 1)
        # F RSS 실패 → 502 고정 문장, 기존 수집 뉴스는 그대로
        self.fake(fail=True)
        res = client.get("/api/home/news/search?q=tecido")
        self.assertEqual((res.status_code, res.get_json()["error"]),
                         (502, {"code": "search_failed", "message": "Google News 검색 결과를 가져오지 못했습니다."}))
        self.assertEqual(client.get("/api/home/news").get_json()["data"]["items"], before)


class HolidayTests(unittest.TestCase):
    def setUp(self):
        service._cache.clear()
        service._holiday_failures.clear()
        self.addCleanup(service._cache.clear)
        self.addCleanup(service._holiday_failures.clear)

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
            service._holiday_failures.clear()  # 실패 결과 10분 캐시가 지난 상황
            self.assertEqual(service.get_holidays(2026)["source"], "fallback")
        self.assertNotIn(2026, service._cache)  # 실패는 성공 캐시에 넣지 않음

    def test_failure_cached_ten_minutes(self):
        now = [1000.0]
        calls = []

        def fail(year):
            calls.append(year)
            raise urllib.error.URLError("offline")
        with mock.patch.object(service, "_fetch_brasilapi", fail), mock.patch.object(service, "monotonic", lambda: now[0]):
            service.get_holidays(2031)
            now[0] += service.HOLIDAY_FAILURE_CACHE_SECONDS - 1
            service.get_holidays(2031)
            self.assertEqual(calls, [2031])  # 10분 안: API를 다시 부르지 않음
            now[0] += 2
            service.get_holidays(2031)
        self.assertEqual(calls, [2031, 2031])

    def test_route_year_validation(self):
        with mock.patch.object(service, "_fetch_brasilapi", lambda year: [{"date": f"{year}-01-01", "name": "TEST"}]):
            client = app.test_client()
            self.assertTrue(client.get("/api/home/holidays?year=2026").get_json()["ok"])
            for q in ("", "?year=abc", "?year=1800"):
                self.assertEqual(client.get("/api/home/holidays" + q).status_code, 400)


if __name__ == "__main__":
    unittest.main()
