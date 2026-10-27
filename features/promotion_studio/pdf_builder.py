"""홍보 스튜디오 콘티 PDF 생성(reportlab). 입력 검증은 service.parse_pdf_request가 먼저 합니다.

구성(feature_spec.md 7장): 표지 → 장면당 1쪽 → 마지막 확인 필요 사항 페이지.
판형: A4 가로(명세 미정 사항을 2026-10-25 임시로 정함).
글꼴: 대시보드와 같은 공통 Pretendard(common/config.py PDF_FONT_FILES, 2026-10-27 Noto Sans KR에서 통일).
디자인: 기존 배치(표지 → 장면 → 확인 필요 사항)는 그대로 두고 공통 PDF 디자인(common/pdf_theme.py)의
머리('PROMOTION REPORT'·로고·블루→아쿠아 선)·브랜드 꼬리·색, 표지 그라데이션 패널만 더했습니다.
PDF 도구는 팀의 다른 기능과 같은 reportlab 5.1.0을 씁니다(2026-10-26 fpdf2에서 전환).
PDF는 메모리에서 만들고 디스크에 저장하지 않습니다.
"""
import io
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from common import pdf_theme as theme

_FONT = theme.FONT
_FONT_BOLD = theme.FONT_BOLD

EDITIONS = ("bilingual", "pt")
# Windows Python에는 시간대 DB가 없을 수 있어 고정 오프셋을 씁니다(한국은 서머타임 없음).
_KST = timezone(timedelta(hours=9))

# 판형·여백(mm)
_PAGE_W, _PAGE_H = (v / mm for v in landscape(A4))
_MARGIN = 15
_TOP = 26            # 머리(영문 머리말·로고·선) 아래 본문 시작
_FRAME_W = 105       # 장면 이미지 영역 최대 폭
_FRAME_MAX_H = 140   # 세로 비율(9:16)에서 높이 상한
_GAP = 10
_HEADER_H = 14
_FOOTER_H = 12
# 장면 문구가 한 쪽에 들어가지 않으면 이 순서로 글자 크기를 줄입니다. 최소 크기에서도 넘치면 다음 쪽으로 이어집니다.
_TEXT_SIZES = (11, 10, 9, 8, 7)
_LINE_RATIO = 1.45   # 줄 간격 = 글자 크기(pt) × 비율

# 색(RGB). 화면 tokens.css·공통 PDF 디자인과 같은 네이비·블루·아쿠아·민트 계열
_TEXT = (19, 35, 63)
_MUTED = (84, 99, 122)
_LINE = (226, 232, 240)
_PRIMARY = (29, 106, 212)
_AQUA = (34, 184, 207)
_MINT = (35, 179, 155)
_WARN = (143, 75, 0)
_FRAME_FILL = (246, 248, 251)

_AUDIENCE_PT = {"buyer": "Compradores (B2B)", "consumer": "Consumidores"}
_PURPOSE_PT = {
    "product_intro": "Apresentação do produto",
    "brand_awareness": "Reconhecimento de marca",
    "eco_value": "Valor ambiental",
    "buyer_inquiry": "Contato de compradores",
    "consumer_purchase": "Incentivo à compra",
    "partnership": "Proposta de parceria",
}

_FIELDS = ("visual", "camera", "subtitle", "narration")
_LABELS = {
    "pt": {
        "cover_kicker": "Roteiro de vídeo promocional",
        "audience": "Público-alvo", "purposes": "Objetivos", "duration": "Duração",
        "seconds": "{n} segundos", "scenes": "{n} cenas", "created": "Gerado em",
        "draft": "Rascunho gerado por IA. Revise produto, afirmações e tradução antes do uso.",
        "scene": "Cena {n}", "no_image": "Imagem não gerada",
        "ai_image": "Imagem gerada por IA com base na foto do produto. Revise a aparência do produto.",
        "photo_image": "Foto do produto enviada (não gerada por IA), recortada no formato da cena.",
        "visual": "Descrição visual", "camera": "Câmera", "subtitle": "Legenda", "narration": "Narração",
        "empty": "—", "review": "Pontos a verificar", "no_review": "Nenhum ponto indicado pela IA.",
        "review_hint": "Números, certificações e afirmações ambientais devem ser confirmados com documentos.",
        "replaced": "Caracteres que a fonte do PDF não suporta foram substituídos por □: {where}",
        "title": "Título", "page": "{n} / {total}",
    },
    "bilingual": {
        "cover_kicker": "Roteiro de vídeo promocional · 홍보 영상 콘티",
        "audience": "Público-alvo · 대상", "purposes": "Objetivos · 홍보 목적", "duration": "Duração · 영상 길이",
        "seconds": "{n} segundos · {n}초", "scenes": "{n} cenas · 장면 {n}개", "created": "Gerado em · 생성일",
        "draft": "AI 생성 초안입니다. 제품 정보·주장·번역을 담당자가 검토한 뒤 사용하세요.",
        "scene": "Cena {n} · 장면 {n}", "no_image": "Imagem não gerada · 이미지 미생성",
        "ai_image": "제품 사진을 참고한 AI 생성 이미지 · 실제 제품 외형과 다를 수 있어 검토 필요",
        "photo_image": "첨부한 제품 사진(AI 생성 아님) · 장면 비율에 맞게 가운데를 잘라 배치",
        "visual": "Descrição visual · 화면 설명", "camera": "Câmera · 카메라 구도·움직임",
        "subtitle": "Legenda · 자막", "narration": "Narração · 내레이션",
        "empty": "— (없음)", "review": "Pontos a verificar · 확인 필요 사항",
        "no_review": "AI가 표시한 항목은 없습니다.",
        "review_hint": "수치·인증·친환경 주장은 근거 자료로 직접 확인하세요.",
        "replaced": "PDF 글꼴로 표시할 수 없는 문자를 □로 바꿨습니다(다른 언어 문자 혼입 가능성): {where}",
        "title": "Título · 제목", "page": "{n} / {total}",
    },
}


class LogoImageError(ValueError):
    """로고 이미지를 PDF에 넣지 못함(손상·지원하지 않는 내용)."""


class SceneImageError(ValueError):
    """장면 이미지를 PDF에 넣지 못함."""


@lru_cache(maxsize=1)
def _register_fonts():
    """공통 Pretendard를 등록하고 두 굵기에 모두 있는 문자 집합을 돌려줍니다."""
    theme.register_fonts()
    regular = pdfmetrics.getFont(_FONT)
    bold = pdfmetrics.getFont(_FONT_BOLD)
    return frozenset(regular.face.charToGlyph) & frozenset(bold.face.charToGlyph)


_REPLACEMENT = "□"
_KEEP = "\n\r\t"


def _replace_unsupported(board, edition, lab):
    """(바꾼 콘티, 바꾼 위치 문구 목록). 글꼴에 없는 문자는 PDF에서 빈칸이 되므로 □로 바꿉니다. 원본 board는 그대로."""
    ok = _register_fonts()
    where = []

    def clean(text, location):
        if all(ord(ch) in ok or ch in _KEEP for ch in text):
            return text
        where.append(location)
        return "".join(ch if ord(ch) in ok or ch in _KEEP else _REPLACEMENT for ch in text)

    langs = ("pt", "ko") if edition == "bilingual" else ("pt",)
    update = {"title_pt": clean(board.title_pt, lab["title"] + " PT")}
    if edition == "bilingual":
        update["title_ko"] = clean(board.title_ko, lab["title"] + " KO")
    scenes = []
    for number, scene in enumerate(board.scenes, start=1):
        fields = {}
        for field in _FIELDS:
            for lang in langs:
                key = f"{field}_{lang}"
                fields[key] = clean(getattr(scene, key), f"{lab['scene'].format(n=number)} {lab[field]} {lang.upper()}")
        scenes.append(scene.model_copy(update=fields))
    update["scenes"] = scenes
    update["review_notes"] = [clean(note, lab["review"]) for note in board.review_notes]
    c = board.conditions
    update["conditions"] = c.model_copy(update={
        "audience": clean(c.audience, lab["audience"]),
        "purposes": [clean(p, lab["purposes"]) for p in c.purposes],
        "purpose_other": clean(c.purpose_other, lab["purposes"]),
    })
    return board.model_copy(update=update), list(dict.fromkeys(where))


_SCENE_JPEG_QUALITY = 85


def _fit_scene_image(data, rw, rh):
    """생성 이미지를 콘티 화면 비율(rw:rh)로 가운데 기준 잘라 JPEG로 줄입니다.

    공통 생성 크기(1536x1024 등)는 16:9·4:5와 비율이 달라, 장면 비율을 맞추려고 위아래(또는 좌우)를 자릅니다.
    PNG를 그대로 넣으면 장당 약 3MB라 PDF가 커지므로 JPEG로 바꿉니다.
    """
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        w, h = img.size
        target = rw / rh
        if w / h > target:
            new_w = round(h * target)
            box = ((w - new_w) // 2, 0, (w - new_w) // 2 + new_w, h)
        else:
            new_h = round(w / target)
            box = (0, (h - new_h) // 2, w, (h - new_h) // 2 + new_h)
        out = io.BytesIO()
        img.crop(box).save(out, format="JPEG", quality=_SCENE_JPEG_QUALITY)
    out.seek(0)
    return ImageReader(out)


def _clock(sec):
    return f"{sec // 60}:{sec % 60:02d}"


def _ratio(aspect):
    w, h = (int(v) for v in aspect.split(":"))
    return w, h


def _wrap(text, font, size, width_mm):
    """폭(mm)에 맞춰 줄을 나눕니다. 공백 단위로 나누고, 한 단어가 폭보다 길면 글자 단위로 자릅니다."""
    width = width_mm * mm
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            candidate = word if not line else line + " " + word
            if pdfmetrics.stringWidth(candidate, font, size) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
            line = ""
            for ch in word:
                if pdfmetrics.stringWidth(line + ch, font, size) > width and line:
                    lines.append(line)
                    line = ""
                line += ch
        lines.append(line)
    return lines


def _line_h(size):
    """글자 크기(pt)의 줄 높이(mm)."""
    return size * _LINE_RATIO / mm


class _Doc:
    """reportlab 캔버스를 위쪽 기준 mm 좌표로 다룹니다. 쪽 번호 "n/전체"는 저장할 때 씁니다."""

    def __init__(self, labels, buffer):
        self.labels = labels
        self.c = canvas.Canvas(buffer, pagesize=landscape(A4), pageCompression=1)
        self.pages = []      # 각 쪽의 캔버스 상태(쪽 번호를 마지막에 그리기 위해 보관)
        self.started = False
        self.y = _TOP        # 현재 위치(위쪽에서부터 mm)

    def add_page(self):
        if self.started:
            self.pages.append(dict(self.c.__dict__))
            self.c._startPage()
        self.started = True
        self.y = _TOP

    def finish(self):
        """쪽마다 공통 머리·꼬리(머리·꼬리 전용 글꼴 이름)를 그리고 'n / 전체'를 씁니다."""
        self.pages.append(dict(self.c.__dict__))
        total = len(self.pages)
        theme.numbered_canvas("PROMOTION REPORT", "", _MARGIN * mm)  # 머리·꼬리 전용 글꼴 등록
        today = datetime.now(_KST).strftime("%Y.%m.%d")
        for number, state in enumerate(self.pages, start=1):
            self.c.__dict__.update(state)
            theme.draw_header(self.c, _PAGE_W * mm, "PROMOTION REPORT", _MARGIN * mm, theme.CHROME, theme.CHROME_BOLD)
            theme.draw_footer(self.c, _PAGE_W * mm, _MARGIN * mm, today,
                              self.labels["page"].format(n=number, total=total), theme.CHROME, theme.CHROME_BOLD)
            canvas.Canvas.showPage(self.c)
        self.c.save()

    # ---- 그리기 도우미(좌표는 위쪽 기준 mm) ----
    def color(self, rgb, stroke=False):
        r, g, b = (v / 255 for v in rgb)
        (self.c.setStrokeColorRGB if stroke else self.c.setFillColorRGB)(r, g, b)

    def text(self, x, y_top, s, size, bold=False, color=_TEXT, align="left"):
        self.c.setFont(_FONT_BOLD if bold else _FONT, size)
        self.color(color)
        baseline = (_PAGE_H - y_top) * mm - size * 0.85
        if align == "center":
            self.c.drawCentredString(x * mm, baseline, s)
        else:
            self.c.drawString(x * mm, baseline, s)

    def block_height(self, width, s, size, bold=False):
        return len(_wrap(s, _FONT_BOLD if bold else _FONT, size, width)) * _line_h(size)

    def block(self, x, width, s, size, bold=False, color=_TEXT):
        """현재 위치부터 줄바꿈해 쓰고 높이를 돌려줍니다. 쪽 아래에 닿으면 새 쪽으로 이어 씁니다."""
        font = _FONT_BOLD if bold else _FONT
        start = self.y
        for line in _wrap(s, font, size, width):
            if self.y + _line_h(size) > _PAGE_H - _MARGIN - _FOOTER_H + 4:
                self.add_page()
            self.text(x, self.y, line, size, bold, color)
            self.y += _line_h(size)
        return self.y - start

    def rect(self, x, y_top, w, h, fill=_FRAME_FILL, stroke=_LINE):
        self.color(fill)
        self.color(stroke, stroke=True)
        self.c.rect(x * mm, (_PAGE_H - y_top - h) * mm, w * mm, h * mm, stroke=1, fill=1)

    def line(self, x1, y1, x2, y2, rgb=_LINE):
        self.color(rgb, stroke=True)
        self.c.line(x1 * mm, (_PAGE_H - y1) * mm, x2 * mm, (_PAGE_H - y2) * mm)

    def image(self, reader, x, y_top, w, h, keep_ratio=False):
        self.c.drawImage(reader, x * mm, (_PAGE_H - y_top - h) * mm, w * mm, h * mm,
                         preserveAspectRatio=keep_ratio, anchor="nw", mask="auto")


def _cover(doc, board, edition, logo_bytes):
    lab = doc.labels
    c = board.conditions
    doc.add_page()
    _cover_panel(doc)
    doc.y = _TOP + 6
    if logo_bytes:
        # 원본 비율을 유지해 최대 60×30mm 안에 넣습니다. 서명만 맞고 내용이 깨진 파일은 여기서 실패합니다.
        try:
            with Image.open(io.BytesIO(logo_bytes)) as img:
                img.load()
                logo = ImageReader(img.copy())
            doc.image(logo, _MARGIN, doc.y, 60, 30, keep_ratio=True)
        except Exception:
            raise LogoImageError() from None
        doc.y += 40
    width = _COVER_TEXT_W
    doc.block(_MARGIN, width, lab["cover_kicker"], 12, color=_PRIMARY)
    doc.y += 3
    doc.block(_MARGIN, width, board.title_pt, 26, bold=True)
    if edition == "bilingual":
        doc.y += 1
        doc.block(_MARGIN, width, board.title_ko, 16, color=_MUTED)
    doc.y += 10

    if edition == "pt":
        audience = _AUDIENCE_PT[c.audience_code]
        purposes = [c.purpose_other if p == "other" else _PURPOSE_PT[p] for p in c.purpose_codes]
    else:
        audience = f"{_AUDIENCE_PT[c.audience_code]} · {c.audience}"
        purposes = [c.purpose_other if p == "other" else f"{_PURPOSE_PT[p]} · {label}"
                    for p, label in zip(c.purpose_codes, c.purposes)]
    created = datetime.now(_KST).strftime("%Y-%m-%d")
    rows = [
        (lab["audience"], audience),
        (lab["purposes"], " / ".join(purposes)),
        (lab["duration"], lab["seconds"].format(n=c.duration) + "  ·  " + lab["scenes"].format(n=c.scene_count)),
        (lab["created"], created),
    ]
    label_w = 70
    for label, value in rows:
        top = doc.y
        h1 = doc.block(_MARGIN, label_w, label, 11, bold=True, color=_MUTED)
        doc.y = top
        h2 = doc.block(_MARGIN + label_w, width - label_w, value, 11)
        doc.y = top + max(h1, h2) + 3

    doc.y = _PAGE_H - _MARGIN - _FOOTER_H - 10
    doc.block(_MARGIN, width, lab["draft"], 9, color=_MUTED)


_COVER_TEXT_W = 185  # 표지 왼쪽 글 폭(mm). 오른쪽은 장식 패널


def _cover_panel(doc):
    """표지 오른쪽 장식 패널: 블루→아쿠아→민트 그라데이션 + 옅은 물결선(원사 느낌). 제품 사진이 아닌 장식입니다."""
    x = _MARGIN + _COVER_TEXT_W + 10
    w = _PAGE_W - _MARGIN - x
    top, h = _TOP, _PAGE_H - _TOP - _MARGIN - _FOOTER_H - 2
    c = doc.c
    x0, y0 = x * mm, (_PAGE_H - top - h) * mm
    c.saveState()
    path = c.beginPath()
    path.roundRect(x0, y0, w * mm, h * mm, 4 * mm)
    c.clipPath(path, stroke=0, fill=0)
    rgb = lambda t: tuple(v / 255 for v in t)
    from reportlab.lib.colors import Color
    c.linearGradient(x0, y0 + h * mm, x0 + w * mm, y0, (Color(*rgb(_PRIMARY)), Color(*rgb(_AQUA)), Color(*rgb(_MINT))),
                     (0, 0.55, 1), extend=True)
    c.setStrokeColorRGB(1, 1, 1, alpha=0.28)
    c.setLineWidth(0.8)
    import math
    for k in range(14):  # 원사 다발처럼 겹치는 물결선
        base = y0 + h * mm * (0.12 + k * 0.06)
        p = c.beginPath()
        p.moveTo(x0, base)
        steps = 40
        for i in range(1, steps + 1):
            t = i / steps
            p.lineTo(x0 + w * mm * t, base + math.sin(t * math.pi * 2 + k * 0.45) * 6 * mm * (0.6 + 0.4 * math.cos(k)))
        c.drawPath(p, stroke=1, fill=0)
    c.restoreState()
    doc.text(x + 10, top + 14, "FIONEX", 12, bold=True, color=(255, 255, 255))
    doc.text(x + 10, top + 22, theme.TAGLINE, 8, color=(235, 245, 255))


def _scene_texts(scene, edition, lab):
    """[(라벨, [(문장, 색)])] — 병기본은 포르투갈어 아래 한국어 검토본을 둡니다."""
    blocks = []
    for field in _FIELDS:
        pt = getattr(scene, field + "_pt") or lab["empty"]
        lines = [(pt, _TEXT)]
        if edition == "bilingual":
            lines.append((getattr(scene, field + "_ko") or lab["empty"], _MUTED))
        blocks.append((lab[field], lines))
    return blocks


def _blocks_height(doc, blocks, w, size):
    total = 0
    for label, lines in blocks:
        total += doc.block_height(w, label, size - 1, bold=True) + 1
        for text, _ in lines:
            total += doc.block_height(w, text, size) + 1
        total += 3
    return total


def _scene_page(doc, number, scene, start, aspect, edition, image_bytes=None, caption_key="ai_image"):
    lab = doc.labels
    doc.add_page()
    end = start + scene.duration_seconds

    title = lab["scene"].format(n=number)
    doc.rect(_MARGIN, _TOP - 6, 1.2, 7, fill=_PRIMARY, stroke=_PRIMARY)  # 구역 제목 막대(공통 디자인)
    doc.text(_MARGIN + 4, _TOP - 6, title, 15, bold=True)
    title_w = pdfmetrics.stringWidth(title, _FONT_BOLD, 15) / mm
    doc.text(_MARGIN + 4 + title_w + 6, _TOP - 4.8, f"{_clock(start)}–{_clock(end)}  ({scene.duration_seconds}s)", 11,
             color=_PRIMARY)

    # 이미지 영역. 콘티 한 편의 화면 비율로 그립니다.
    rw, rh = _ratio(aspect)
    frame_w = _FRAME_W
    frame_h = frame_w * rh / rw
    if frame_h > _FRAME_MAX_H:
        frame_h = _FRAME_MAX_H
        frame_w = frame_h * rw / rh
    top = _TOP + _HEADER_H - 8
    doc.rect(_MARGIN, top, frame_w, frame_h)
    if image_bytes:
        try:
            doc.image(_fit_scene_image(image_bytes, rw, rh), _MARGIN, top, frame_w, frame_h)
        except Exception:
            raise SceneImageError() from None
        doc.y = top + frame_h + 1.5
        doc.block(_MARGIN, frame_w, lab[caption_key], 7, color=_MUTED)
    else:
        doc.text(_MARGIN + frame_w / 2, top + frame_h / 2 - 2, f"{lab['no_image']}  ·  {aspect}", 9,
                 color=_MUTED, align="center")

    x = _MARGIN + _FRAME_W + _GAP
    w = _PAGE_W - _MARGIN - x
    available = _PAGE_H - top - _MARGIN - _FOOTER_H
    blocks = _scene_texts(scene, edition, lab)
    size = next((s for s in _TEXT_SIZES if _blocks_height(doc, blocks, w, s) <= available), _TEXT_SIZES[-1])

    doc.y = top
    for label, lines in blocks:
        doc.rect(x, doc.y + 0.6, 0.9, _line_h(size - 1) - 1.2, fill=_MINT, stroke=_MINT)
        doc.block(x + 2.5, w - 2.5, label, size - 1, bold=True, color=_PRIMARY)
        doc.y += 1
        for text, color in lines:
            doc.block(x, w, text, size, color=color)
            doc.y += 1
        doc.y += 3
    return end


def _review_page(doc, board, replaced):
    lab = doc.labels
    doc.add_page()
    width = _PAGE_W - 2 * _MARGIN
    doc.rect(_MARGIN, doc.y + 0.5, 1.2, 6, fill=_PRIMARY, stroke=_PRIMARY)
    doc.block(_MARGIN + 4, width - 4, lab["review"], 15, bold=True)
    doc.y += 4
    if replaced:
        doc.block(_MARGIN, width, "• " + lab["replaced"].format(where=", ".join(replaced)), 11, color=_WARN)
        doc.y += 2
    if board.review_notes:
        for note in board.review_notes:
            doc.block(_MARGIN, width, "• " + note, 11)
            doc.y += 2
    else:
        doc.block(_MARGIN, width, lab["no_review"], 11)
    doc.y += 4
    doc.block(_MARGIN, width, lab["review_hint"], 9, color=_MUTED)


def build_pdf(board, edition, logo_bytes=None, scene_images=None, photos=None):
    """검증된 콘티(service.PdfStoryboard) → PDF bytes.

    scene_images: {장면 번호: AI 생성 PNG bytes}(선택). photos: 제품 사진 bytes 목록(선택) —
    AI 이미지가 없는 장면에 순서대로 돌려 넣고 "첨부 사진(AI 생성 아님)"으로 표시합니다.
    """
    labels = _LABELS[edition]
    board, replaced = _replace_unsupported(board, edition, labels)
    buffer = io.BytesIO()
    doc = _Doc(labels, buffer)
    doc.c.setTitle(board.title_pt)
    doc.c.setCreator("fionex promotion_studio")
    _cover(doc, board, edition, logo_bytes)
    start = 0
    # 번호·시작 시간은 받은 값 대신 장면 순서와 길이로 다시 계산합니다.
    for number, scene in enumerate(board.scenes, start=1):
        image, caption = (scene_images or {}).get(number), "ai_image"
        if image is None and photos:
            image, caption = photos[(number - 1) % len(photos)], "photo_image"
        start = _scene_page(doc, number, scene, start, board.conditions.aspect_ratio, edition, image, caption)
    _review_page(doc, board, replaced)
    doc.finish()
    return buffer.getvalue()
