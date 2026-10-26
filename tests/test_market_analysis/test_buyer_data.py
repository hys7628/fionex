"""바이어 목록 기준 자료 생성기(buyer_data_builder) 모의 테스트. 국세청 공개 자료 형식을 흉내 낸 작은 zip을 씁니다.

실행(프로젝트 루트, Conda jasonenv):
    python -m unittest discover -s tests/test_market_analysis -v
"""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features.market_analysis import buyer_data_builder as bdb  # noqa: E402


def est(basico, ordem, matriz, cnae, situacao="02", uf="SP", mun="7107", email="contato@empresa.com.br"):
    row = [""] * 30
    row[0], row[1], row[2], row[3] = basico, ordem, "11", "1" if matriz else "2"
    row[4], row[5], row[10], row[11] = "FANTASIA", situacao, "19900101", cnae
    row[19], row[20], row[21], row[22], row[27] = uf, mun, "11", "33334444", email
    return row


def write_zip(folder, name, rows):
    text = "\n".join(";".join('"%s"' % v for v in r) for r in rows)
    with zipfile.ZipFile(Path(folder) / f"{name}.zip", "w") as z:
        z.writestr(name.upper() + "CSV", text.encode("latin-1"))


class BuyerDataBuilderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = self.tmp.name
        write_zip(d, "Cnaes", [["1323500", "Tecelagem de fios de fibras artificiais e sintéticas"], ["1311100", "Preparação e fiação de fibras de algodão"]])
        write_zip(d, "Municipios", [["7107", "SAO PAULO"], ["8105", "BLUMENAU"]])
        write_zip(d, "Naturezas", [["2062", "Sociedade Empresária Limitada"], ["2135", "Empresário (Individual)"]])
        write_zip(d, "Estabelecimentos0", [
            est("11111111", "0002", False, "1323500", uf="SC", mun="8105", email="FILIAL@A.COM"),  # 지점 먼저
            est("11111111", "0001", True, "1323500"),                 # 본사 → 대표
            est("22222222", "0001", True, "1311100"),                 # 대상 업종 아님
            est("33333333", "0001", True, "1323500", situacao="08"),  # 폐업
            est("44444444", "0001", True, "1323500"),                 # 개인사업자
            est("55555555", "0001", True, "1323500"),                 # MEI(규모 소기업)
            est("66666666", "0001", True, "1323500"),                 # 소규모
        ])
        write_zip(d, "Empresas0", [
            ["11111111", "TEXTIL A LTDA", "2062", "49", "1000000,00", "05", ""],
            ["44444444", "FULANO DE TAL", "2135", "50", "1000,00", "05", ""],
            ["55555555", "MEI TEXTIL", "2062", "49", "1000,00", "01", ""],
            ["66666666", "PEQUENA TEXTIL", "2062", "49", "1000,00", "03", ""],
        ])

    def test_filters_and_representative(self):
        data = bdb.build(self.tmp.name, "2026-10", files=[0])
        rows = data["companies"]
        self.assertEqual([r["razao_social"] for r in rows], ["TEXTIL A LTDA"])
        r = rows[0]
        self.assertEqual((r["cnpj"], r["matriz"], r["sites_matched"]), ("11111111000111", True, 2))  # 본사 우선, 지점 수 기록
        self.assertEqual((r["uf"], r["municipio"], r["cnae_desc"], r["porte"]), ("SP", "SAO PAULO", "Tecelagem de fios de fibras artificiais e sintéticas", "그 외(중·대형)"))
        self.assertEqual((r["phones"], r["email"], r["natureza"]), (["(11) 33334444"], "contato@empresa.com.br", "Sociedade Empresária Limitada"))
        self.assertEqual(data["counts"]["excluded"], {"no_company_row": 0, "individual": 1, "porte": 2})
        self.assertEqual(data["counts"]["companies_matched"], 4)  # 업종·활성 조건까지 통과한 기업(폐업·비대상 업종 제외)
        self.assertEqual(data["source"]["reference_month"], "2026-10")
        self.assertIn("수입 실적은 공개 자료에 없음", data["source"]["note"])

    def test_parallel_same_result_and_secondary_cnae_not_matched(self):
        d = self.tmp.name
        # 부 업종(CNAE 부)에만 대상 코드가 있는 사업장은 넣지 않음
        row = est("77777777", "0001", True, "4781400")
        row[12] = "1323500"
        write_zip(d, "Estabelecimentos1", [row])
        write_zip(d, "Empresas1", [["77777777", "LOJA LTDA", "2062", "49", "1,00", "05", ""]])
        one = bdb.build(d, "2026-10", files=[0, 1])
        two = bdb.build(d, "2026-10", files=[0, 1], workers=2)
        self.assertEqual([r["razao_social"] for r in one["companies"]], ["TEXTIL A LTDA"])
        self.assertEqual(one["companies"], two["companies"])

    def test_target_cnaes_exclude_fiber_makers_and_natural_spinning(self):
        for code in ("2040100", "1311100", "1312000"):
            self.assertNotIn(code, bdb.TARGET_CNAES)
        self.assertIn("1340501", bdb.TARGET_CNAES)  # 가공사(texturização)


class BuyersLoadTest(unittest.TestCase):
    """buyers.load: ② 근거 업체 먼저, 자료 파일이 없으면 ready False. PDF에 전체 목록 포함."""

    def setUp(self):
        from features.market_analysis import buyers
        self.buyers = buyers
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.orig = (buyers.COMPANIES_FILE, buyers.EVIDENCE_FILE)
        self.addCleanup(lambda: setattr(buyers, "COMPANIES_FILE", self.orig[0]) or setattr(buyers, "EVIDENCE_FILE", self.orig[1]))
        buyers.COMPANIES_FILE, buyers.EVIDENCE_FILE = d / "c.json", d / "e.json"

    def write(self, path, data):
        import json
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def company(self, cnpj, name):
        return {"cnpj": cnpj, "razao_social": name, "nome_fantasia": None, "cnae": "1323500", "cnae_desc": "Tecelagem",
                "uf": "SP", "municipio": "SAO PAULO", "phones": ["(11) 33334444"], "email": "a@b.com", "porte": "그 외(중·대형)",
                "natureza": "LTDA", "matriz": True, "sites_matched": 1, "inicio_atividade": "19900101"}

    def test_missing_file_not_ready(self):
        d = self.buyers.load()
        self.assertFalse(d["ready"])
        self.assertIn("수입 여부는 공식 자료로 확인 불가", d["notes"][0])

    def test_evidence_first_and_pdf_full_list(self):
        rows = [self.company("%08d000199" % (i + 1),"EMPRESA %02d" % i) for i in range(8)]
        self.write(self.buyers.COMPANIES_FILE, {"source": {"name": "RFB", "url": "https://example.gov.br", "reference_month": "2026-10"},
                                                "generated_at": "2026-10-26T12:00:00+09:00", "filters": {"porte": "그 외(중·대형)"},
                                                "counts": {"companies": 8}, "companies": rows})
        self.write(self.buyers.EVIDENCE_FILE, {"reviewed_at": "2026-10-26", "companies": [
            {"cnpj": rows[6]["cnpj"], "evidence": [{"title": "Fio reciclado", "url": "https://empresa.com.br/news", "checked_at": "2026-10-26"}]}]})
        d = self.buyers.load()
        self.assertTrue(d["ready"])
        self.assertEqual(d["companies"][0]["razao_social"], "EMPRESA 06")
        self.assertEqual([c["razao_social"] for c in d["companies"][1:3]], ["EMPRESA 00", "EMPRESA 01"])
        self.assertEqual(d["counts"]["with_evidence"], 1)

        from pypdf import PdfReader
        import io
        from features.market_analysis import pdf_report
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from test_phase2 import make_stats  # 기존 PDF 테스트의 모의 통계

        pdf = pdf_report.build_pdf({"stats": make_stats(), "ai": None})
        text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn("⑥ 바이어 목록", text)
        self.assertIn("EMPRESA 07", text)  # 화면 토글 너머(6번째 이후)도 PDF에는 포함


if __name__ == "__main__":
    unittest.main()
