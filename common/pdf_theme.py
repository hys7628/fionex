"""공통 PDF 디자인(2026-10-27). 홈 일일 브리핑·시장 분석·그린 클레임·홍보 콘티 PDF가 같은 머리·꼬리·제목·표 모양을 씁니다.

- 글꼴: 대시보드와 같은 Pretendard(common/config.py PDF_FONT_FILES). 제품소개서 PDF는 이 모듈을 쓰지 않습니다.
- 쪽 머리: 왼쪽 위 영문 머리말(예: MARKET REPORT) + 오른쪽 FIONEX 로고 + 그 아래 블루→아쿠아 선.
- 쪽 꼬리: 왼쪽 'FIONEX | WEAVE A BRIGHTER TOMORROW', 오른쪽 '날짜 | n / 전체'.
- 색은 화면 tokens.css 값(네이비 글자·블루·아쿠아·민트)을 씁니다. 색만으로 뜻을 전하지 않습니다(글자와 함께).
- 로고는 static/assets/fionex_logo.png를 메모리에서 줄여 한 번만 읽습니다(파일을 쓰지 않음).
"""
import io
from functools import lru_cache
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Flowable, Paragraph, Table, TableStyle

from common.config import PDF_FONT_FILES, PDF_FONT_NAMES

FONT, FONT_BOLD = PDF_FONT_NAMES["regular"], PDF_FONT_NAMES["bold"]
# 머리·꼬리 전용 이름(같은 Pretendard 파일). 쪽을 모았다가 저장할 때 그리므로 본문 글꼴 묶음에 새 글자를 더하지 않게 따로 씁니다
# (본문과 같은 이름이면 저장 시점에 늘어난 글자 묶음이 그 쪽 자원에 빠져 텍스트 추출이 깨질 수 있음).
CHROME, CHROME_BOLD = "FionexChrome", "FionexChrome-Bold"
LOGO_PATH = Path(__file__).resolve().parents[1] / "static" / "assets" / "fionex_logo.png"

NAVY = colors.HexColor("#13233f")
MUTED = colors.HexColor("#54637a")
LINE = colors.HexColor("#e2e8f0")
LINE_STRONG = colors.HexColor("#c3cedc")
SOFT = colors.HexColor("#f6f8fb")
PRIMARY = colors.HexColor("#1d6ad4")
PRIMARY_SOFT = colors.HexColor("#eaf2fd")
AQUA = colors.HexColor("#22b8cf")
MINT = colors.HexColor("#23b39b")
MINT_SOFT = colors.HexColor("#e6f6f2")
MINT_TEXT = colors.HexColor("#0a7262")
DANGER = colors.HexColor("#b42318")
WARNING = colors.HexColor("#8f4b00")
WARNING_SOFT = colors.HexColor("#fdf2df")

HEADER_TOP = 12 * mm      # 쪽 위에서 머리말 기준선까지
CONTENT_TOP = 26 * mm     # 본문 시작(머리 아래) — 문서 topMargin으로 씁니다
CONTENT_BOTTOM = 20 * mm  # 꼬리 위 — 문서 bottomMargin으로 씁니다
TAGLINE = "WEAVE A BRIGHTER TOMORROW"

_registered = set()


def _register(names):
    if names not in _registered:
        pdfmetrics.registerFont(TTFont(names[0], str(PDF_FONT_FILES["regular"])))
        pdfmetrics.registerFont(TTFont(names[1], str(PDF_FONT_FILES["bold"])))
        _registered.add(names)


def register_fonts():
    """Pretendard 두 굵기를 공통 이름(본문용)으로 한 번만 등록합니다."""
    _register((FONT, FONT_BOLD))


@lru_cache(maxsize=1)
def _logo_png():
    """로고를 폭 600px로 줄인 PNG bytes(투명 유지). 파일이 없으면 None(로고 없이 글자만)."""
    if not LOGO_PATH.is_file():
        return None
    from PIL import Image

    with Image.open(LOGO_PATH) as img:
        img = img.convert("RGBA")
        h = round(img.height * 600 / img.width)
        out = io.BytesIO()
        img.resize((600, h), Image.LANCZOS).save(out, format="PNG", optimize=True)
    return out.getvalue()


def logo_reader():
    data = _logo_png()
    return ImageReader(io.BytesIO(data)) if data else None


def draw_header(canvas, page_w, kicker, margin, font=FONT, font_bold=FONT_BOLD, page_h=None):
    """머리: 왼쪽 영문 머리말, 오른쪽 로고(높이 9mm), 그 아래 블루→아쿠아 선(로고 앞까지)."""
    page_h = page_h or canvas._pagesize[1]
    y = page_h - HEADER_TOP
    canvas.saveState()
    canvas.setFont(font, 8.5)
    canvas.setFillColor(NAVY)
    canvas.drawString(margin, y, kicker.upper())
    logo = logo_reader()
    logo_h = 9 * mm
    logo_w = logo_h * 3
    if logo:
        canvas.drawImage(logo, page_w - margin - logo_w, y - 3.2 * mm, logo_w, logo_h, mask="auto")
    else:
        canvas.setFont(font_bold, 12)
        canvas.setFillColor(PRIMARY)
        canvas.drawRightString(page_w - margin, y, "FIONEX")
    canvas.restoreState()
    # 블루→아쿠아 그라데이션 선: 얇은 사각형으로 자른 영역에 그라데이션을 칠합니다.
    line_end = page_w - margin - logo_w - 4 * mm
    line_y = y - 3.6 * mm
    canvas.saveState()
    path = canvas.beginPath()
    path.rect(margin, line_y - 0.7, line_end - margin, 1.4)
    canvas.clipPath(path, stroke=0, fill=0)
    canvas.linearGradient(margin, line_y, line_end, line_y, (PRIMARY, AQUA), extend=False)
    canvas.restoreState()


def draw_footer(canvas, page_w, margin, date_text, page_text, font=FONT, font_bold=FONT_BOLD, note=None):
    """꼬리: 왼쪽 'FIONEX | WEAVE A BRIGHTER TOMORROW'(+ 선택 안내), 오른쪽 '날짜 | 쪽'."""
    y = 10 * mm
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(margin, y + 5 * mm, page_w - margin, y + 5 * mm)
    canvas.setFont(font_bold, 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(margin, y, "FIONEX")
    brand_w = pdfmetrics.stringWidth("FIONEX", font_bold, 8)
    canvas.setFont(font, 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(margin + brand_w + 3 * mm, y, "|  " + TAGLINE + (("   ·   " + note) if note else ""))
    canvas.setFont(font_bold, 8)
    canvas.setFillColor(NAVY)
    canvas.drawRightString(page_w - margin, y, page_text)
    num_w = pdfmetrics.stringWidth(page_text, font_bold, 8)
    canvas.setFont(font, 7)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(page_w - margin - num_w - 2.5 * mm, y, date_text + "  |")
    canvas.restoreState()


def numbered_canvas(kicker, date_text, margin, note=None, font=CHROME, font_bold=CHROME_BOLD):
    """쪽마다 머리·꼬리를 미뤄 두었다가 저장할 때 'n / 전체'와 함께 그리는 Canvas 클래스(머리·꼬리 전용 글꼴 이름)."""
    if (font, font_bold) == (CHROME, CHROME_BOLD):
        _register((CHROME, CHROME_BOLD))

    class ThemedCanvas(Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved)
            for state in self._saved:
                self.__dict__.update(state)
                w = self._pagesize[0]
                draw_header(self, w, kicker, margin, font, font_bold)
                draw_footer(self, w, margin, date_text, f"{self._pageNumber} / {total}", font, font_bold, note)
                super().showPage()
            super().save()

    return ThemedCanvas


# ---------- 본문 조각 ----------
def styles(font=FONT, font_bold=FONT_BOLD):
    base = ParagraphStyle("t_body", fontName=font, fontSize=9.2, leading=13.8, textColor=NAVY, wordWrap="CJK")
    return {
        "title": ParagraphStyle("t_title", parent=base, fontName=font_bold, fontSize=24, leading=30, spaceAfter=4),
        "lead": ParagraphStyle("t_lead", parent=base, fontSize=10.5, leading=16, textColor=colors.HexColor("#33415a"), spaceAfter=8),
        "body": base,
        "small": ParagraphStyle("t_small", parent=base, fontSize=7.8, leading=11.2, textColor=MUTED),
        "cell": ParagraphStyle("t_cell", parent=base, fontSize=8.4, leading=12),
        "cell_head": ParagraphStyle("t_cell_head", parent=base, fontName=font_bold, fontSize=8.2, leading=11.5, textColor=NAVY),
        "label": ParagraphStyle("t_label", parent=base, fontName=font_bold, fontSize=8.4, leading=12, textColor=MUTED),
    }


class SectionTitle(Flowable):
    """블루 세로 막대 + 굵은 제목 + (선택) 연한 '| 꼬리표'. 다음 내용과 같은 쪽에 붙습니다."""

    def __init__(self, text, tag=None, size=12.5, font=FONT, font_bold=FONT_BOLD, space_before=12, space_after=6):
        super().__init__()
        self.text, self.tag, self.size = text, tag, size
        self.font, self.font_bold = font, font_bold
        self.spaceBefore, self.spaceAfter = space_before, space_after
        self.keepWithNext = 1
        self._para = Paragraph(self._markup(), ParagraphStyle("st", fontName=font_bold, fontSize=size, leading=size * 1.35,
                                                              textColor=NAVY, wordWrap="CJK"))

    def _markup(self):
        from xml.sax.saxutils import escape
        tag = ('  <font name="%s" size="%.1f" color="#7b8aa1">|  %s</font>' % (self.font, self.size * 0.7, escape(self.tag))
               if self.tag else "")
        return escape(self.text) + tag

    def wrap(self, aw, ah):
        self._w, self._h = self._para.wrap(aw - 9, ah)
        return aw, self._h

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(PRIMARY)
        c.rect(0, 1, 3, self._h - 2, stroke=0, fill=1)
        c.restoreState()
        self._para.drawOn(c, 9, 0)


def data_table(rows, widths, head_rows=1, num_cols=(), zebra=True, highlight=(), valign="TOP"):
    """민트 머리 + 가로 구분선만 있는 표. rows는 이미 만든 단락(또는 문자열 아님)이어야 합니다."""
    t = Table(rows, colWidths=widths, repeatRows=head_rows)
    st = [
        ("VALIGN", (0, 0), (-1, -1), valign),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, MINT),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if head_rows:
        st += [("BACKGROUND", (0, 0), (-1, head_rows - 1), MINT_SOFT), ("LINEBELOW", (0, head_rows - 1), (-1, head_rows - 1), 0.6, MINT)]
    if zebra:
        for r in range(head_rows + 1, len(rows), 2):
            st.append(("BACKGROUND", (0, r), (-1, r), SOFT))
    for r in highlight:
        st.append(("BACKGROUND", (0, r), (-1, r), PRIMARY_SOFT))
    t.setStyle(TableStyle(st))
    return t


def kv_table(rows, label_w, total_w):
    """항목·내용 두 칸 표(왼쪽 칸 민트 바탕). rows: [(label 단락, value 단락)]."""
    t = Table(rows, colWidths=(label_w, total_w - label_w))
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), MINT_SOFT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, MINT),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def stat_cards(items, total_w, font=FONT, font_bold=FONT_BOLD, value_size=20):
    """큰 숫자 카드 줄. items: [(라벨, 값, 색, 보조 문장 또는 None)]. 카드 사이 세로선(시안의 검수 결과 요약 모양)."""
    from xml.sax.saxutils import escape
    n = len(items)
    label_st = ParagraphStyle("sc_l", fontName=font_bold, fontSize=9, leading=12, textColor=NAVY, alignment=1, wordWrap="CJK")
    sub_st = ParagraphStyle("sc_s", fontName=font, fontSize=7.4, leading=10, textColor=MUTED, alignment=1, wordWrap="CJK")
    cells = []
    for label, value, color, sub in items:
        val_st = ParagraphStyle("sc_v", fontName=font_bold, fontSize=value_size, leading=value_size * 1.2,
                                textColor=color or NAVY, alignment=1)
        cell = [Paragraph(escape(label), label_st), Paragraph(escape(value), val_st)]
        if sub:
            cell.append(Paragraph(escape(sub), sub_st))
        cells.append(cell)
    t = Table([cells], colWidths=[total_w / n] * n)
    st = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
          ("LINEBELOW", (0, 0), (-1, -1), 0.6, LINE)]
    for i in range(1, n):
        st.append(("LINEBEFORE", (i, 0), (i, 0), 0.6, LINE))
    t.setStyle(TableStyle(st))
    return t


def note_box(paragraph, total_w, tone="info"):
    """옅은 바탕 + 왼쪽 강조선 안내 상자."""
    bg, bar = {"info": (PRIMARY_SOFT, PRIMARY), "warning": (WARNING_SOFT, WARNING), "mint": (MINT_SOFT, MINT)}[tone]
    t = Table([[paragraph]], colWidths=[total_w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 2.4, bar),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t
