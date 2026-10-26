"""제품소개서 카탈로그 PDF 렌더러(A4 세로 4페이지, ReportLab 5.1.0). 화면 연결·다운로드 라우트는 아직 없습니다.

입력은 화면의 현재 적용된 편집본(generation.current)에서 뽑은 구조화 데이터뿐입니다(parse_catalog 참고).
HTML·URL·파일 경로·글꼴·색·안내 문구는 받지 않고, 쪽 제목·항목명·비공식/가상/AI 이미지 안내·빈 상태 문구는 서버 상수를 씁니다.
서버는 생성 결과를 저장하지 않으므로 요청의 virtual 표시가 원래 생성 결과와 같은지 인증하지 못합니다(형식만 검사해 보존).

- 배치 상수는 화면 템플릿(catalog_preview.html·product_brochure.css)의 CSS px 값을 그대로 적고, 그릴 때 PX(pt/px)로 바꿉니다.
  ReportLab은 브라우저와 다른 렌더러라 줄바꿈·글자 폭·자간이 화면과 완전히 같지 않습니다.
- 문구 높이·너비는 실제 글꼴로 측정하고, 정해진 영역을 넘으면 쪽 번호와 함께 실패합니다(자르기·숨기기·글자 축소 없음).
- 사용자 문자열은 XML 이스케이프 후 Paragraph에 넣습니다(마크업 해석 방지). 줄바꿈만 <br/>로 바꿉니다.
- 자산(이미지 2개·글꼴 2개)은 고정 경로만 읽고, 없거나 손상되면 실패합니다. 앱 시작 시가 아니라 렌더링할 때 확인합니다.
- PDF는 BytesIO에서 bytes로 만들고 디스크·로그에 남기지 않습니다. OpenAI·외부 네트워크를 쓰지 않습니다.
"""
import io
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Literal
from xml.sax.saxutils import escape

from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, ValidationError

from common.errors import AIError, AIInputError
from features.product_brochure.generation import (
    DETAIL_KEYS, EMPTY_DETAILS, EMPTY_SUPPLY, HANGUL, MAX_DETAIL_VALUE_CHARS, MAX_DISPLAY_NAME_CHARS,
    MAX_INTRO_PARAGRAPHS, MAX_PARAGRAPH_CHARS, MAX_SUPPLY_VALUE_CHARS, MAX_TAGLINE_CHARS,
    NOTICE_FICTITIOUS, NOTICE_FICTITIOUS_CONTENT, NOTICE_UNOFFICIAL, SUPPLY_KEYS,
)

# ---------- 고정 자산(경로는 여기 한곳에서 관리. 공통 글꼴 위치가 정해지면 FONT_DIR만 바꿉니다) ----------
_BASE = Path(__file__).resolve().parent
FONT_DIR = _BASE / "fonts"
FONT_FILES = {"regular": FONT_DIR / "NotoSansKR-Regular.ttf", "bold": FONT_DIR / "NotoSansKR-Bold.ttf"}
# 다른 기능이 같은 ReportLab 전역 등록부에 "NotoSansKR"을 등록하므로 이름을 따로 씁니다.
FONT_NAMES = {"regular": "PBCatalogSans", "bold": "PBCatalogSans-Bold"}
IMAGE_DIR = _BASE / "static" / "images"
IMAGE_FILES = {"cover": IMAGE_DIR / "catalog_cover_concept.png", "material": IMAGE_DIR / "catalog_material_concept.png"}
IMAGE_SIZES = {"cover": (1024, 1536), "material": (1448, 1086)}  # 크롭 위치가 이 크기 기준
JPEG_QUALITY = 88

PAGE_COUNT = 4
PDF_TITLE = "Catálogo de demonstração — fionex"

# ---------- 서버 고정 문구(템플릿과 같은 pt-BR, 번역 검수 전) ----------
AI_IMAGE_NOTICE = "Imagem conceitual gerada por IA — não representa o produto real."
KICKER_COVER = "fionex · catálogo de demonstração"
KICKERS = {2: "01 · Apresentação", 3: "02 · Detalhes", 4: "03 · Comercial"}
HEADINGS = {2: "Sobre o material", 3: "Detalhes do produto", 4: "Amostras e condições comerciais"}
DETAIL_CAPTION = AI_IMAGE_NOTICE + " Recorte ampliado da imagem da página 2."
CLOSING_TITLE = "Próximos passos"
CLOSING_BODY = "Entre em contato para consultar a disponibilidade de amostras e as condições comerciais."
# 항목명은 AI 생성 라벨 대신 서버 상수(pt-BR, 번역 검수 전). 화면 미리보기는 아직 AI 라벨을 표시함(명세 §25)
ITEM_LABELS = {
    "yarn_spec": "Especificação do fio",
    "certification": "Certificações",
    "carbon_reduction": "Redução de carbono",
    "moq": "Pedido mínimo (MOQ)",
    "sample": "Amostra",
    "lead_time": "Prazo de entrega",
}

# ---------- 색(product_brochure.css의 --catalog-* 값) ----------
COLORS = {
    "paper": "#f7f5ef", "paper_deep": "#efebe2", "ink": "#1c2622", "muted": "#56625b", "line": "#d9dcd3",
    "green": "#1f4a39", "green_deep": "#143326", "green_mid": "#3d6b57",
}

# ---------- 배치(CSS px, 96dpi 기준 794x1123). PX = PDF pt / CSS px ----------
PAGE_W, PAGE_H = 794, 1123
PX = 595.2756 / PAGE_W           # A4 폭 595.28pt
PAD = 64                          # --catalog-pad (space-12 + space-4)
CONTENT_BOTTOM = PAGE_H - 80      # --catalog-footer-h 위까지 본문
CONTENT_W = PAGE_W - 2 * PAD
GAP = 32                          # .catalog-page gap (space-8)
FOOTER_BOTTOM = 32                # .catalog-footer bottom
FOOTER_PAD_TOP = 12
FONT_PX = {"sm": 14, "md": 16, "lg": 18, "xl": 22, "title": 28 * 2.6, "heading": 28 * 1.4, "term": 28 * 1.3}

COVER_FIGURE_H = 940
COVER_TEXT_W = 440
COVER_TEXT_BOTTOM = COVER_FIGURE_H - PAD   # 표지 문구는 이미지 위 밝은 영역 안(띠 위)까지
COVER_BAND_PAD = 20
INTRO_FIGURE_W = 680
INTRO_FIGURE_H, INTRO_FIGURE_H_LONG = 420, 300
INTRO_LONG_CHARS = 400            # 문단 합계가 넘으면 이미지 높이를 줄이고 본문 크기(화면 renderResult와 같은 기준)
DETAIL_FIGURE_W, DETAIL_FIGURE_H = 340, 960
DETAIL_TEXT_X = DETAIL_FIGURE_W + 48
DETAIL_TEXT_W = PAGE_W - PAD - DETAIL_TEXT_X
TERM_GAP, TERM_PAD_X, TERM_PAD_Y = 20, 20, 24
TERM_BIG_MAX_CHARS = 24           # 짧은 값은 큰 숫자 위계(화면 infoItem과 같은 기준)
CLOSING_MIN_H = 200               # 4쪽 마무리 이미지 최소 높이(이보다 작아지면 넘침으로 처리)
CROPS = {"cover": (0.5, 0.7), "intro": (0.4, 0.45), "detail": (0.8, 0.55), "closing": (0.85, 0.88)}  # object-position

_CONTROL_ALL = re.compile("[\u0000-\u001f\u007f]")
_CONTROL_TEXT = re.compile("[\u0000-\u0009\u000b-\u001f\u007f]")  # 여러 줄 문구는 줄바꿈만 허용(편집 검사와 같음)


# ---------- 오류(공통 오류 계약: code·message·http_status) ----------
class CatalogPdfInputError(AIInputError):
    code = "BROCHURE_PDF_INVALID_INPUT"
    message = "PDF로 만들 카탈로그 문구 형식이 올바르지 않습니다."


class CatalogPdfGlyphError(AIInputError):
    code = "BROCHURE_PDF_GLYPH_MISSING"
    message = "PDF 글꼴로 표시할 수 없는 문자가 있습니다."
    http_status = 422


class CatalogPdfOverflowError(AIInputError):
    code = "BROCHURE_PDF_LAYOUT_OVERFLOW"
    message = "문구가 PDF 페이지의 정해진 영역을 넘습니다. 문구를 줄여 주세요."
    http_status = 422

    def __init__(self, page, area):
        super().__init__(message=f"{page}쪽 {area}이(가) PDF 페이지의 정해진 영역을 넘습니다. 문구를 줄여 주세요.")
        self.page = page
        self.area = area


class CatalogPdfAssetError(AIError):
    code = "BROCHURE_PDF_ASSET_UNAVAILABLE"
    message = "PDF에 필요한 이미지·글꼴을 불러오지 못했습니다."
    http_status = 500
    retryable = False


class CatalogPdfRenderError(AIError):
    code = "BROCHURE_PDF_RENDER_FAILED"
    message = "카탈로그 PDF를 만들지 못했습니다."
    http_status = 500
    retryable = False


# ---------- 입력 스키마(generation.current의 pages 구조에서 문구·key·virtual만) ----------
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TextIn(_Strict):
    text: StrictStr
    virtual: StrictBool


class ItemIn(_Strict):
    key: StrictStr
    value: StrictStr
    virtual: StrictBool


class CoverIn(_Strict):
    product_name: TextIn
    tagline: TextIn


class IntroIn(_Strict):
    paragraphs: List[TextIn]


class ItemsIn(_Strict):
    items: List[ItemIn]


class CatalogIn(_Strict):
    language: Literal["pt-BR"]
    cover: CoverIn
    intro: IntroIn
    details: ItemsIn
    supply: ItemsIn


def _clean(value, limit, where, multiline=True):
    text = value.strip()
    if not text:
        raise CatalogPdfInputError(message=f"{where}이(가) 비어 있습니다.")
    if len(text) > limit:
        raise CatalogPdfInputError(message=f"{where}이(가) {limit}자를 넘습니다.")
    if HANGUL.search(text):
        raise CatalogPdfInputError(message=f"{where}에 한글이 있습니다. 카탈로그 문구는 pt-BR로 입력하세요.")
    if (_CONTROL_TEXT if multiline else _CONTROL_ALL).search(text):
        raise CatalogPdfInputError(message=f"{where}에 쓸 수 없는 문자가 있습니다.")
    return text


def _items(items, allowed, limit, page):
    seen = [i.key for i in items]
    if any(k not in allowed for k in seen):
        raise CatalogPdfInputError(message=f"{page}쪽에 허용되지 않은 항목이 있습니다.")
    if len(set(seen)) != len(seen):
        raise CatalogPdfInputError(message=f"{page}쪽에 같은 항목이 여러 번 있습니다.")
    order = {k: n for n, k in enumerate(allowed)}
    return [{"key": i.key, "label": ITEM_LABELS[i.key], "value": _clean(i.value, limit, f"{page}쪽 {ITEM_LABELS[i.key]} 값"),
             "virtual": i.virtual} for i in sorted(items, key=lambda i: order[i.key])]


def parse_catalog(payload):
    """구조화 데이터 → 렌더링용 dict. 생성·편집과 같은 상한(표시명 80·소개 140·문단 600·상세 300·공급 200),
    빈 값·한글·제어 문자 검사, 쪽별 허용 key·중복 검사. 값은 앞뒤 공백만 정리하고 고치거나 채우지 않습니다."""
    if not isinstance(payload, dict):
        raise CatalogPdfInputError()
    try:
        data = CatalogIn.model_validate(payload)
    except ValidationError:
        raise CatalogPdfInputError() from None  # 오류 위치에 사용자 문자열을 넣지 않음
    paragraphs = data.intro.paragraphs
    if not 1 <= len(paragraphs) <= MAX_INTRO_PARAGRAPHS:
        raise CatalogPdfInputError(message=f"2쪽 소개 문단은 1~{MAX_INTRO_PARAGRAPHS}개여야 합니다.")
    return {
        "product_name": {"text": _clean(data.cover.product_name.text, MAX_DISPLAY_NAME_CHARS, "1쪽 카탈로그 표시명",
                                        multiline=False), "virtual": data.cover.product_name.virtual},
        "tagline": {"text": _clean(data.cover.tagline.text, MAX_TAGLINE_CHARS, "1쪽 소개 문구"),
                    "virtual": data.cover.tagline.virtual},
        "paragraphs": [{"text": _clean(p.text, MAX_PARAGRAPH_CHARS, f"2쪽 소개 문단 {n}"), "virtual": p.virtual}
                       for n, p in enumerate(paragraphs, start=1)],
        "details": _items(data.details.items, DETAIL_KEYS, MAX_DETAIL_VALUE_CHARS, 3),
        "supply": _items(data.supply.items, SUPPLY_KEYS, MAX_SUPPLY_VALUE_CHARS, 4),
    }


# ---------- 자산 ----------
_registered = {}


def _register_fonts():
    """글꼴을 처음 렌더링할 때 등록합니다(앱 시작에 영향 없음). 실패하면 등록하지 않고 자산 오류."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for role, path in FONT_FILES.items():
        if _registered.get(role) == path:
            continue
        try:
            font = TTFont(FONT_NAMES[role], str(path))
        except Exception:
            raise CatalogPdfAssetError() from None
        pdfmetrics.registerFont(font)
        _registered[role] = path
    return {role: set(pdfmetrics.getFont(name).face.charToGlyph) for role, name in FONT_NAMES.items()}


@lru_cache(maxsize=4)
def _decoded_image(path, mtime, size):
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    with Image.open(path) as probe:
        probe.verify()                      # 손상 검사(verify 뒤에는 다시 열어야 함)
    with Image.open(path) as im:
        im.load()
        image = im.convert("RGB")
    # PNG 원본을 그대로 넣으면 PDF가 약 8.9 MB라 메모리에서 JPEG로 바꿔 넣습니다(해상도 유지, 손실 압축).
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    buf.seek(0)
    return ImageReader(buf), image.size


def _load_images():
    images = {}
    for role, path in IMAGE_FILES.items():
        try:
            stat = path.stat()
            reader, size = _decoded_image(str(path), stat.st_mtime_ns, stat.st_size)
        except Exception:
            raise CatalogPdfAssetError() from None
        if size != IMAGE_SIZES[role]:
            raise CatalogPdfAssetError()     # 다른 이미지로 바뀌면 크롭 위치가 맞지 않음
        images[role] = (reader, size)
    return images


# ---------- 그리기 도구 ----------
def _hex(c):
    from reportlab.lib import colors
    return colors.HexColor(COLORS[c])


def _style(name, size, *, bold=False, color="ink", line=1.6, split=True):
    from reportlab.lib.styles import ParagraphStyle
    return ParagraphStyle(name, fontName=FONT_NAMES["bold" if bold else "regular"], fontSize=FONT_PX[size] * PX,
                          leading=FONT_PX[size] * line * PX, textColor=_hex(color), splitLongWords=1 if split else 0)


def _styles():
    return {
        "kicker": _style("kicker", "sm", color="green_mid"),
        "title": _style("title", "title", bold=True, color="green_deep", line=1.02, split=False),
        "heading": _style("heading", "heading", bold=True, color="green_deep", line=1.15, split=False),
        "lead": _style("lead", "xl", line=1.45),
        "lead_lg": _style("lead_lg", "lg", line=1.45),
        "lead_md": _style("lead_md", "md"),
        "body": _style("body", "lg"),
        "value": _style("value", "md"),
        "caption": _style("caption", "sm", color="muted"),
        "fictitious": _style("fictitious", "sm", color="muted"),
        "label": _style("label", "sm", color="muted"),
        "term": _style("term", "term", bold=True, color="green_deep", line=1.1, split=False),
        "term_long": _style("term_long", "lg", color="green_deep", line=1.45),
        "status": _style("status", "xl", bold=True, color="green_deep"),
        "closing_title": _style("closing_title", "xl", bold=True, color="green_deep"),
    }


class _Page:
    """CSS px 좌표(위가 0)로 받아 PDF pt 좌표로 그립니다."""

    def __init__(self, canvas, number, styles):
        self.c, self.number, self.st = canvas, number, styles

    def para(self, text, style, width, area):
        from reportlab.platypus import Paragraph
        p = Paragraph(escape(text).replace("\n", "<br/>"), self.st[style])
        if not self.st[style].splitLongWords and p.minWidth() > width * PX + 0.01:
            raise CatalogPdfOverflowError(self.number, area)   # 줄 안에 들어가지 않는 긴 단어
        p.wrap(width * PX, 10 ** 6)
        p.px_height = p.height / PX
        return p

    def draw(self, p, x, top):
        p.drawOn(self.c, x * PX, (PAGE_H - top) * PX - p.height)
        return top + p.px_height

    def rect(self, x, top, w, h, color):
        self.c.setFillColor(_hex(color))
        self.c.rect(x * PX, (PAGE_H - top - h) * PX, w * PX, h * PX, stroke=0, fill=1)

    def hline(self, x, top, w, thickness, color):
        self.rect(x, top, w, thickness, color)

    def image(self, image, crop, x, top, w, h):
        """object-fit: cover + object-position(크롭)을 잘라내기 경로로 재현합니다."""
        reader, (iw, ih) = image
        scale = max(w / iw, h / ih)
        dw, dh = iw * scale, ih * scale
        ox, oy = CROPS[crop]
        dx, dy = x + (w - dw) * ox, top + (h - dh) * oy
        self.rect(x, top, w, h, "paper_deep")
        self.c.saveState()
        path = self.c.beginPath()
        path.rect(x * PX, (PAGE_H - top - h) * PX, w * PX, h * PX)
        self.c.clipPath(path, stroke=0, fill=0)
        self.c.drawImage(reader, dx * PX, (PAGE_H - dy - dh) * PX, dw * PX, dh * PX)
        self.c.restoreState()

    def kicker(self, text, x, top):
        """대문자·자간 0.14em 한 줄(고정 문구)."""
        size = FONT_PX["sm"] * PX
        t = self.c.beginText()
        t.setFont(FONT_NAMES["regular"], size)
        t.setCharSpace(size * 0.14)
        t.setFillColor(_hex("green_mid"))
        line_h = FONT_PX["sm"] * 1.6
        t.setTextOrigin(x * PX, (PAGE_H - top - line_h + (line_h - FONT_PX["sm"]) / 2 + FONT_PX["sm"] * 0.2) * PX)
        t.textLine(text.upper())
        self.c.drawText(t)
        return top + line_h

    def header(self, top=PAD, x=PAD, width=CONTENT_W):
        bottom = self.kicker(KICKERS[self.number], x, top)
        return self.draw(self.para(HEADINGS[self.number], "heading", width, "제목"), x, bottom + 8)

    def copy(self, item, style, x, top, width, area, measure_only=False):
        """생성 문구 + 가상 안내(서버 상수). measure_only면 높이만 돌려줍니다."""
        blocks = [(self.para(item["text"], style, width, area), 0)]
        if item["virtual"]:
            blocks.append((self.para(NOTICE_FICTITIOUS_CONTENT, "fictitious", width, area), 8 + 8))
        height = sum(p.px_height + gap for p, gap in blocks)
        if not measure_only:
            for p, gap in blocks:
                top = self.draw(p, x, top + gap)
        return height

    def footer(self):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        size = FONT_PX["sm"] * PX
        no = f"{self.number} / {PAGE_COUNT}"
        if (stringWidth(NOTICE_UNOFFICIAL, FONT_NAMES["regular"], size) + stringWidth(no, FONT_NAMES["regular"], size)
                > (CONTENT_W - 16) * PX):
            raise CatalogPdfOverflowError(self.number, "하단 안내")
        line_h = FONT_PX["sm"] * 1.6
        top = PAGE_H - FOOTER_BOTTOM - line_h - FOOTER_PAD_TOP
        self.rect(PAD, top, CONTENT_W, line_h + FOOTER_PAD_TOP, "paper")
        self.hline(PAD, top, CONTENT_W, 1, "line")
        base = (FOOTER_BOTTOM + (line_h - FONT_PX["sm"]) / 2 + FONT_PX["sm"] * 0.2) * PX
        self.c.setFont(FONT_NAMES["regular"], size)
        self.c.setFillColor(_hex("muted"))
        self.c.drawString(PAD * PX, base, NOTICE_UNOFFICIAL)
        self.c.drawRightString((PAD + CONTENT_W) * PX, base, no)
        return top

    @staticmethod
    def fits(bottom, limit, number, area):
        if bottom > limit + 0.01:
            raise CatalogPdfOverflowError(number, area)


# ---------- 페이지 ----------
def _page_cover(pg, data, images):
    pg.image(images["cover"], "cover", 0, 0, PAGE_W, COVER_FIGURE_H)
    top = pg.kicker(KICKER_COVER, PAD, PAD)
    title = pg.para(data["product_name"]["text"], "title", COVER_TEXT_W, "카탈로그 표시명")
    height = 16 + 12 + title.px_height + 16 + pg.copy(data["tagline"], "lead", 0, 0, COVER_TEXT_W, "소개 문구", True)
    if data["product_name"]["virtual"]:
        name_notice = pg.para(NOTICE_FICTITIOUS_CONTENT, "fictitious", COVER_TEXT_W, "카탈로그 표시명")
        height += 8 + name_notice.px_height
    pg.fits(top + height, COVER_TEXT_BOTTOM, 1, "표지 문구")
    top = pg.draw(title, PAD, top + 16 + 12)
    if data["product_name"]["virtual"]:
        top = pg.draw(name_notice, PAD, top + 8)
    pg.copy(data["tagline"], "lead", PAD, top + 16, COVER_TEXT_W, "소개 문구")
    pg.draw(pg.para(AI_IMAGE_NOTICE, "caption", CONTENT_W, "AI 이미지 안내"), PAD, COVER_FIGURE_H + COVER_BAND_PAD)
    pg.fits(COVER_FIGURE_H + COVER_BAND_PAD + FONT_PX["sm"] * 1.6, pg.footer(), 1, "AI 이미지 안내")


def _page_intro(pg, data, images):
    long = sum(len(p["text"]) for p in data["paragraphs"]) > INTRO_LONG_CHARS
    top = pg.header()
    fig_h = INTRO_FIGURE_H_LONG if long else INTRO_FIGURE_H
    fig_top = top + GAP
    caption_top = fig_top + fig_h + 12
    caption = pg.para(AI_IMAGE_NOTICE, "caption", CONTENT_W, "AI 이미지 안내")
    text_top = caption_top + caption.px_height + GAP
    style = "lead_md" if long else "lead_lg"
    heights = [pg.copy(p, style, 0, 0, CONTENT_W, f"소개 문단 {n}", True) for n, p in enumerate(data["paragraphs"], 1)]
    bottom = text_top + 2 + 24 + sum(heights) + 16 * (len(heights) - 1)
    pg.fits(bottom, CONTENT_BOTTOM, 2, "소개 문단")
    pg.image(images["material"], "intro", 0, fig_top, INTRO_FIGURE_W, fig_h)
    pg.draw(caption, PAD, caption_top)
    pg.hline(PAD, text_top, CONTENT_W, 2, "green")
    y = text_top + 2 + 24
    for n, (p, h) in enumerate(zip(data["paragraphs"], heights), 1):
        pg.copy(p, style, PAD, y, CONTENT_W, f"소개 문단 {n}")
        y += h + 16
    pg.footer()


def _status_box(pg, message, x, width, *, top=None, bottom=None):
    p = pg.para(message, "status", width - 24 * 2 - 3, "빈 상태 안내")
    h = 24 + p.px_height + 24
    top = bottom - h if top is None else top
    pg.rect(x, top, width, h, "paper_deep")
    pg.rect(x, top, 3, h, "green")
    pg.draw(p, x + 3 + 24, top + 24)
    return top, top + h


def _page_details(pg, data, images):
    pg.image(images["material"], "detail", 0, 0, DETAIL_FIGURE_W, DETAIL_FIGURE_H)
    caption = pg.para(DETAIL_CAPTION, "caption", 300, "AI 이미지 안내")
    footer_top = pg.footer()
    pg.fits(DETAIL_FIGURE_H + 16 + caption.px_height, footer_top, 3, "AI 이미지 안내")
    pg.draw(caption, 24, DETAIL_FIGURE_H + 16)
    top = pg.header(x=DETAIL_TEXT_X, width=DETAIL_TEXT_W)
    if not data["details"]:
        box_top, _ = _status_box(pg, EMPTY_DETAILS, DETAIL_TEXT_X, DETAIL_TEXT_W, bottom=CONTENT_BOTTOM)
        pg.fits(top + GAP, box_top, 3, "빈 상태 안내")
        return
    rows = []
    for item in data["details"]:
        label = pg.para(item["label"], "label", DETAIL_TEXT_W, "상세 항목명")
        rows.append((label, item, pg.copy({"text": item["value"], "virtual": False}, "value", 0, 0, DETAIL_TEXT_W,
                                          f"{item['label']} 값", True)))
    y = top + GAP
    total = y
    for label, item, value_h in rows:
        total += 1 + 16 + label.px_height + 4 + value_h + (8 + _notice_h(pg, NOTICE_FICTITIOUS, DETAIL_TEXT_W)
                                                           if item["virtual"] else 0) + 16
    pg.fits(total, CONTENT_BOTTOM, 3, "상세 정보")
    for label, item, value_h in rows:
        pg.hline(DETAIL_TEXT_X, y, DETAIL_TEXT_W, 1, "line")
        y = pg.draw(label, DETAIL_TEXT_X, y + 1 + 16)
        pg.copy({"text": item["value"], "virtual": False}, "value", DETAIL_TEXT_X, y + 4, DETAIL_TEXT_W, item["label"])
        y += 4 + value_h
        if item["virtual"]:
            y = pg.draw(pg.para(NOTICE_FICTITIOUS, "fictitious", DETAIL_TEXT_W, item["label"]), DETAIL_TEXT_X, y + 8)
        y += 16


def _notice_h(pg, text, width):
    return pg.para(text, "fictitious", width, "가상 안내").px_height


def _page_supply(pg, data, images):
    top = pg.header()
    y = top + GAP
    items = data["supply"]
    if items:
        col_w = (CONTENT_W - TERM_GAP * 2) / 3
        inner = col_w - TERM_PAD_X * 2
        cards = []
        for item in items:
            label = pg.para(item["label"], "label", inner, f"{item['label']} 항목명")
            value = None
            if len(item["value"]) <= TERM_BIG_MAX_CHARS:
                try:
                    value = pg.para(item["value"], "term", inner, item["label"])
                except CatalogPdfOverflowError:
                    value = None   # 큰 숫자 위계에서 한 단어가 칸을 넘으면 긴 값 글자 크기로(자르지 않음)
            if value is None:
                value = pg.para(item["value"], "term_long", inner, item["label"])
            notice = pg.para(NOTICE_FICTITIOUS, "fictitious", inner, item["label"]) if item["virtual"] else None
            cards.append((label, value, notice))
        card_h = max(TERM_PAD_Y + l.px_height + 8 + v.px_height + ((8 + 8 + n.px_height) if n else 0) + TERM_PAD_Y
                     for l, v, n in cards)
        for n, (label, value, notice) in enumerate(cards):
            x = PAD + n * (col_w + TERM_GAP)
            pg.rect(x, y, col_w, card_h, "paper_deep")
            pg.rect(x, y, col_w, 3, "green")
            cy = pg.draw(label, x + TERM_PAD_X, y + TERM_PAD_Y)
            pg.draw(value, x + TERM_PAD_X, cy + 8)
            if notice:  # 카드 아래쪽에 붙임(margin-top: auto)
                pg.draw(notice, x + TERM_PAD_X, y + card_h - TERM_PAD_Y - notice.px_height)
        y += card_h
    else:
        _, y = _status_box(pg, EMPTY_SUPPLY, PAD, CONTENT_W, top=y)

    closing_top = y + GAP
    closing_h = CONTENT_BOTTOM - closing_top
    fig_w = (CONTENT_W - GAP) * 6 / 11
    text_x, text_w = PAD + fig_w + GAP, (CONTENT_W - GAP) * 5 / 11
    parts = [pg.para(CLOSING_TITLE, "closing_title", text_w, "마무리 문구"),
             pg.para(CLOSING_BODY, "body", text_w, "마무리 문구"),
             pg.para(AI_IMAGE_NOTICE, "caption", text_w, "AI 이미지 안내")]
    text_h = sum(p.px_height for p in parts) + 16 * (len(parts) - 1)
    if closing_h < max(CLOSING_MIN_H, text_h):
        raise CatalogPdfOverflowError(4, "공급 조건")
    pg.image(images["cover"], "closing", PAD, closing_top, fig_w, closing_h)
    ty = CONTENT_BOTTOM - text_h
    for p in parts:
        ty = pg.draw(p, text_x, ty) + 16
    pg.footer()


def _check_glyphs(data, glyphs):
    texts = [data["product_name"]["text"], data["tagline"]["text"]] + [p["text"] for p in data["paragraphs"]]
    texts += [i["value"] for i in data["details"] + data["supply"]]
    fixed = [AI_IMAGE_NOTICE, KICKER_COVER.upper(), DETAIL_CAPTION, CLOSING_TITLE, CLOSING_BODY, NOTICE_UNOFFICIAL,
             NOTICE_FICTITIOUS, NOTICE_FICTITIOUS_CONTENT, EMPTY_DETAILS, EMPTY_SUPPLY]
    fixed += [k.upper() for k in KICKERS.values()] + list(HEADINGS.values()) + list(ITEM_LABELS.values())
    for text in texts + fixed:   # 굵게 쓰는 문구도 있어 두 글꼴 모두 확인
        for ch in set(text) - {"\n"}:
            if ord(ch) not in glyphs["regular"] or ord(ch) not in glyphs["bold"]:
                raise CatalogPdfGlyphError()


def build_pdf(payload):
    """구조화 데이터 → A4 세로 4페이지 PDF bytes. 검증·자산·넘침·페이지 수 중 하나라도 실패하면 예외(부분 PDF 없음)."""
    data = parse_catalog(payload)
    glyphs = _register_fonts()
    images = _load_images()
    _check_glyphs(data, glyphs)

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    buf = io.BytesIO()
    # 기본 Helvetica 대신 내장한 글꼴을 초기 글꼴로(포함되지 않는 표준 글꼴 참조 방지)
    c = rl_canvas.Canvas(buf, pagesize=A4, pageCompression=1, initialFontName=FONT_NAMES["regular"])
    c.setTitle(PDF_TITLE)
    c.setAuthor("fionex")
    c.setSubject(NOTICE_UNOFFICIAL)
    c.setCreator("fionex")
    styles = _styles()
    for number, draw in enumerate((_page_cover, _page_intro, _page_details, _page_supply), start=1):
        c.setFillColor(_hex("paper"))
        c.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
        draw(_Page(c, number, styles), data, images)
        c.showPage()
    c.save()
    pdf = buf.getvalue()
    _check_page_count(pdf)
    return pdf


def _check_page_count(pdf):
    """출력 검사: pypdf로 다시 읽어 정확히 4페이지·A4 세로인지 확인합니다.
    업로드 입력 검사(common/pdf_utils.inspect_pdf)의 크기·페이지 상한은 용도가 달라 쓰지 않습니다."""
    from pypdf import PdfReader
    try:
        pages = PdfReader(io.BytesIO(pdf)).pages
        sizes = [(float(p.mediabox.width), float(p.mediabox.height)) for p in pages]
    except Exception:
        raise CatalogPdfRenderError() from None
    if len(sizes) != PAGE_COUNT or any(abs(w - 595.2756) > 0.5 or abs(h - 841.8898) > 0.5 for w, h in sizes):
        raise CatalogPdfRenderError()
