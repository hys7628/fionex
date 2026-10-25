"""홍보 스튜디오 콘티 PDF 생성(fpdf2). 입력 검증은 service.parse_pdf_request가 먼저 합니다.

구성(feature_spec.md 7장): 표지 → 장면당 1쪽 → 마지막 확인 필요 사항 페이지.
판형: A4 가로(명세 미정 사항을 2026-10-25 임시로 정함). 글꼴: fonts/README.md.
PDF는 메모리에서 만들고 디스크에 저장하지 않습니다.
"""
import io
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont
from fpdf import FPDF
from PIL import Image
from fpdf.enums import MethodReturnValue, XPos, YPos

_FONT_DIR = Path(__file__).resolve().parent / "fonts"
_FONT = "noto_sans_kr"

EDITIONS = ("bilingual", "pt")
# Windows Python에는 시간대 DB가 없을 수 있어 고정 오프셋을 씁니다(한국은 서머타임 없음).
_KST = timezone(timedelta(hours=9))

# 판형·여백(mm)
_MARGIN = 15
_FRAME_W = 105       # 장면 이미지 영역 최대 폭
_FRAME_MAX_H = 140   # 세로 비율(9:16)에서 높이 상한
_GAP = 10
_HEADER_H = 14
_FOOTER_H = 12
# 장면 문구가 한 쪽에 들어가지 않으면 이 순서로 글자 크기를 줄입니다. 최소 크기에서도 넘치면 다음 쪽으로 이어집니다.
_TEXT_SIZES = (11, 10, 9, 8, 7)

# 색(RGB). 화면 tokens.css의 글자·보조 글자·선 계열을 참고했습니다.
_TEXT = (23, 32, 51)
_MUTED = (84, 96, 120)
_LINE = (214, 222, 235)
_PRIMARY = (37, 99, 235)

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
        "title": "Título", "page": "{n}/{total}",
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
        "title": "Título · 제목", "page": "{n}/{total}",
    },
}


class LogoImageError(ValueError):
    """로고 이미지를 PDF에 넣지 못함(손상·지원하지 않는 내용)."""


class SceneImageError(ValueError):
    """장면 이미지를 PDF에 넣지 못함."""


_REPLACEMENT = "□"
_KEEP = "\n\r\t"


@lru_cache(maxsize=1)
def _supported_codepoints():
    """두 굵기 글꼴에 모두 있는 문자. 없는 문자는 PDF에서 빈칸이 되므로 미리 바꿉니다."""
    sets = []
    for name in ("NotoSansKR-Regular.ttf", "NotoSansKR-Bold.ttf"):
        with TTFont(str(_FONT_DIR / name), lazy=True) as font:
            sets.append(frozenset(font.getBestCmap()))
    return frozenset.intersection(*sets)


def _replace_unsupported(board, edition, lab):
    """(바꾼 콘티, 바꾼 위치 문구 목록). 원본 board는 바꾸지 않습니다."""
    ok = _supported_codepoints()
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
    return out


def _clock(sec):
    return f"{sec // 60}:{sec % 60:02d}"


def _ratio(aspect):
    w, h = (int(v) for v in aspect.split(":"))
    return w, h


class _Doc(FPDF):
    def __init__(self, labels):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.labels = labels
        self.set_margins(_MARGIN, _MARGIN, _MARGIN)
        self.set_auto_page_break(True, margin=_MARGIN + _FOOTER_H - 4)
        self.add_font(_FONT, "", str(_FONT_DIR / "NotoSansKR-Regular.ttf"))
        self.add_font(_FONT, "B", str(_FONT_DIR / "NotoSansKR-Bold.ttf"))
        self.alias_nb_pages()

    def footer(self):
        self.set_y(-_MARGIN)
        self.set_font(_FONT, "", 8)
        self.set_text_color(*_MUTED)
        self.cell(0, 5, self.labels["page"].format(n=self.page_no(), total="{nb}"), align="R")

    def text_block(self, w, text, size, style="", color=_TEXT, dry=False):
        """폭 w에 줄바꿈해 쓰고 높이(mm)를 돌려줍니다. dry=True면 쓰지 않고 높이만 계산합니다."""
        self.set_font(_FONT, style, size)
        self.set_text_color(*color)
        line_h = size * 0.5
        if dry:
            return self.multi_cell(w, line_h, text, align="L", dry_run=True, output=MethodReturnValue.HEIGHT)
        x = self.get_x()
        before = self.get_y()
        self.multi_cell(w, line_h, text, align="L", new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_x(x)
        return self.get_y() - before


def _cover(doc, board, edition, logo_bytes):
    lab = doc.labels
    c = board.conditions
    doc.add_page()
    y = _MARGIN + 10
    if logo_bytes:
        # 원본 비율을 유지해 최대 60×30mm 안에 넣습니다. 서명만 맞고 내용이 깨진 파일은 여기서 실패합니다.
        try:
            doc.image(io.BytesIO(logo_bytes), x=_MARGIN, y=y, w=60, h=30, keep_aspect_ratio=True)
        except Exception:
            raise LogoImageError() from None
        y += 40
    doc.set_xy(_MARGIN, y)
    width = doc.w - 2 * _MARGIN
    doc.text_block(width, lab["cover_kicker"], 12, color=_PRIMARY)
    doc.ln(3)
    doc.text_block(width, board.title_pt, 26, "B")
    if edition == "bilingual":
        doc.ln(1)
        doc.text_block(width, board.title_ko, 16, color=_MUTED)
    doc.ln(10)

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
        doc.set_x(_MARGIN)
        top = doc.get_y()
        doc.text_block(label_w, label, 11, "B", _MUTED)
        doc.set_xy(_MARGIN + label_w, top)
        h = doc.text_block(width - label_w, value, 11)
        doc.set_y(max(doc.get_y(), top + h) + 3)

    doc.set_y(doc.h - _MARGIN - _FOOTER_H - 10)
    doc.set_x(_MARGIN)
    doc.text_block(width, lab["draft"], 9, color=_MUTED)


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
        total += doc.text_block(w, label, size - 1, "B", dry=True) + 1
        for text, _ in lines:
            total += doc.text_block(w, text, size, dry=True) + 1
        total += 3
    return total


def _scene_page(doc, number, scene, start, aspect, edition, image_bytes=None, caption_key="ai_image"):
    lab = doc.labels
    doc.add_page()
    end = start + scene.duration_seconds

    doc.set_xy(_MARGIN, _MARGIN)
    doc.set_font(_FONT, "B", 15)
    doc.set_text_color(*_TEXT)
    title = lab["scene"].format(n=number)
    doc.cell(doc.get_string_width(title) + 6, 8, title)
    doc.set_font(_FONT, "", 11)
    doc.set_text_color(*_PRIMARY)
    doc.cell(0, 8, f"{_clock(start)}–{_clock(end)}  ({scene.duration_seconds}s)")
    doc.set_draw_color(*_LINE)
    doc.line(_MARGIN, _MARGIN + _HEADER_H - 3, doc.w - _MARGIN, _MARGIN + _HEADER_H - 3)

    # 이미지 영역(아직 생성 이미지 없음). 콘티 한 편의 화면 비율로 그립니다.
    rw, rh = _ratio(aspect)
    frame_w = _FRAME_W
    frame_h = frame_w * rh / rw
    if frame_h > _FRAME_MAX_H:
        frame_h = _FRAME_MAX_H
        frame_w = frame_h * rw / rh
    top = _MARGIN + _HEADER_H
    doc.set_draw_color(*_LINE)
    doc.set_fill_color(244, 247, 252)
    doc.rect(_MARGIN, top, frame_w, frame_h, style="DF")
    if image_bytes:
        try:
            doc.image(_fit_scene_image(image_bytes, rw, rh), x=_MARGIN, y=top, w=frame_w, h=frame_h)
        except Exception:
            raise SceneImageError() from None
        doc.set_xy(_MARGIN, top + frame_h + 1)
        doc.set_font(_FONT, "", 7)
        doc.set_text_color(*_MUTED)
        doc.cell(frame_w, 4, lab[caption_key])
    else:
        doc.set_xy(_MARGIN, top + frame_h / 2 - 3)
        doc.set_font(_FONT, "", 9)
        doc.set_text_color(*_MUTED)
        doc.cell(frame_w, 6, f"{lab['no_image']}  ·  {aspect}", align="C")

    x = _MARGIN + _FRAME_W + _GAP
    w = doc.w - _MARGIN - x
    available = doc.h - top - _MARGIN - _FOOTER_H
    blocks = _scene_texts(scene, edition, lab)
    size = next((s for s in _TEXT_SIZES if _blocks_height(doc, blocks, w, s) <= available), _TEXT_SIZES[-1])

    doc.set_xy(x, top)
    for label, lines in blocks:
        doc.set_x(x)
        doc.text_block(w, label, size - 1, "B", _PRIMARY)
        doc.ln(1)
        for text, color in lines:
            doc.set_x(x)
            doc.text_block(w, text, size, color=color)
            doc.ln(1)
        doc.ln(3)
    return end


def _review_page(doc, board, replaced):
    lab = doc.labels
    doc.add_page()
    width = doc.w - 2 * _MARGIN
    doc.set_xy(_MARGIN, _MARGIN)
    doc.text_block(width, lab["review"], 15, "B")
    doc.ln(4)
    if replaced:
        doc.set_x(_MARGIN)
        doc.text_block(width, "• " + lab["replaced"].format(where=", ".join(replaced)), 11, color=(180, 83, 9))
        doc.ln(2)
    if board.review_notes:
        for note in board.review_notes:
            doc.set_x(_MARGIN)
            doc.text_block(width, "• " + note, 11)
            doc.ln(2)
    else:
        doc.set_x(_MARGIN)
        doc.text_block(width, lab["no_review"], 11)
    doc.ln(4)
    doc.set_x(_MARGIN)
    doc.text_block(width, lab["review_hint"], 9, color=_MUTED)


def build_pdf(board, edition, logo_bytes=None, scene_images=None, photos=None):
    """검증된 콘티(service.PdfStoryboard) → PDF bytes.

    scene_images: {장면 번호: AI 생성 PNG bytes}(선택). photos: 제품 사진 bytes 목록(선택) —
    AI 이미지가 없는 장면에 순서대로 돌려 넣고 "첨부 사진(AI 생성 아님)"으로 표시합니다.
    """
    doc = _Doc(_LABELS[edition])
    board, replaced = _replace_unsupported(board, edition, doc.labels)
    doc.set_title(board.title_pt)
    doc.set_creator("fionex promotion_studio")
    _cover(doc, board, edition, logo_bytes)
    start = 0
    # 번호·시작 시간은 받은 값 대신 장면 순서와 길이로 다시 계산합니다.
    for number, scene in enumerate(board.scenes, start=1):
        image, caption = (scene_images or {}).get(number), "ai_image"
        if image is None and photos:
            image, caption = photos[(number - 1) % len(photos)], "photo_image"
        start = _scene_page(doc, number, scene, start, board.conditions.aspect_ratio, edition, image, caption)
    _review_page(doc, board, replaced)
    return bytes(doc.output())
