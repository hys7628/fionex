"""카탈로그 PDF 렌더러 검증용 고정 데이터. 실제 제품·사용자 자료가 아닌 명확한 가상 예시입니다(수치·조건 모두 가상).
구조는 화면 generation.current의 pages에서 문구·key·virtual만 뽑은 형태(pdf_catalog.parse_catalog)와 같습니다."""
import copy


def base():
    """기본: 3·4쪽 항목 모두, 가상 표시는 4쪽 조건 일부만."""
    return {
        "language": "pt-BR",
        "cover": {
            "product_name": {"text": "Fibra Exemplo D1", "virtual": False},
            "tagline": {"text": "Fio de poliéster de demonstração para avaliar o layout do catálogo.", "virtual": False},
        },
        "intro": {"paragraphs": [
            {"text": "A Fibra Exemplo D1 é um produto fictício usado apenas para testar a geração do catálogo em PDF. "
                     "Nenhuma informação desta página descreve um produto real.", "virtual": False},
        ]},
        "details": {"items": [
            {"key": "yarn_spec", "value": "75D/36F (valor de exemplo)", "virtual": False},
            {"key": "certification", "value": "Nenhuma certificação informada neste exemplo.", "virtual": False},
            {"key": "carbon_reduction", "value": "Dado de exemplo sem medição real.", "virtual": True},
        ]},
        "supply": {"items": [
            {"key": "moq", "value": "500 kg", "virtual": True},
            {"key": "sample", "value": "1 kg", "virtual": True},
            {"key": "lead_time", "value": "30 dias", "virtual": True},
        ]},
    }


def edited():
    """편집된 표시명·문구(화면에서 사용자가 적용한 편집본이라고 가정). 악센트와 &, <, > 포함."""
    d = base()
    d["cover"]["product_name"]["text"] = "Fio Ação & Têxtil <Demo>"
    d["cover"]["tagline"]["text"] = "Texto editado: ação, coração, têxtil, órgão & <marcação> não interpretada."
    d["intro"]["paragraphs"] = [
        {"text": "Parágrafo editado 1 — inclui acentuação (ã, õ, ç, é, ê, á, í, ó, ú, à) e símbolos & < > \" '.", "virtual": False},
        {"text": "Parágrafo editado 2 com informações fictícias.\nSegunda linha após quebra manual.", "virtual": True},
    ]
    d["supply"]["items"][0]["value"] = "800 kg por pedido (editado)"
    return d


def empty_info():
    """3·4쪽 정보 없음(서버 빈 상태 안내)."""
    d = base()
    d["details"]["items"] = []
    d["supply"]["items"] = []
    return d


def virtual_all():
    """모든 칸 가상(가상 안내 위치 확인)."""
    d = copy.deepcopy(base())
    d["cover"]["product_name"]["virtual"] = True
    d["cover"]["tagline"]["virtual"] = True
    for p in d["intro"]["paragraphs"]:
        p["virtual"] = True
    for i in d["details"]["items"] + d["supply"]["items"]:
        i["virtual"] = True
    return d


def long_max():
    """상한 근처 긴 문구(넘침 없이 들어가야 하는 경우): 문단 2개 합계 > 400자 → 이미지 축소·본문 크기."""
    d = base()
    sentence = "Texto longo de demonstração para verificar quebras de linha e altura do bloco. "
    d["cover"]["tagline"]["text"] = (sentence * 2)[:140].strip()
    d["intro"]["paragraphs"] = [{"text": (sentence * 8)[:520].strip(), "virtual": False},
                                {"text": (sentence * 8)[:520].strip(), "virtual": True}]
    d["details"]["items"] = [{"key": k, "value": (sentence * 4)[:200].strip(), "virtual": True}
                             for k in ("yarn_spec", "certification", "carbon_reduction")]
    d["supply"]["items"] = [{"key": k, "value": (sentence * 3)[:200].strip(), "virtual": True}
                            for k in ("moq", "sample", "lead_time")]
    return d


def max_paragraphs():
    """상한 경계: 문단 2개 모두 600자 + 가상 안내(2쪽 축소 배치 안에 들어가야 함)."""
    d = base()
    d["intro"]["paragraphs"] = [{"text": ("Palavra " * 80)[:600].strip(), "virtual": True},
                                {"text": ("Palavra " * 80)[:600].strip(), "virtual": True}]
    return d


def overflow_details():
    """배치 초과: 3쪽 상세 3개 모두 300자 + 가상 안내(각 값은 상한 이내지만 3쪽 영역을 넘음)."""
    d = base()
    d["details"]["items"] = [{"key": k, "value": ("Informação técnica fictícia " * 12)[:300].strip(), "virtual": True}
                             for k in ("yarn_spec", "certification", "carbon_reduction")]
    return d


def overflow_title():
    """배치 초과: 표지 표시명에 칸보다 긴 한 단어."""
    d = base()
    d["cover"]["product_name"]["text"] = "Superpoliésterregeneradoexemplo"
    return d
