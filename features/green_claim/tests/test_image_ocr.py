"""홍보 이미지(JPG·JPEG·PNG) AI 글자 판독 검증(모의). 외부 요청·OpenAI 호출 없음. 실행(저장소 루트):

    python -m unittest features.green_claim.tests.test_image_ocr -v

가상 이미지는 이 파일에서 메모리로 만듭니다(Pillow로 그린 도형·단색, 직접 조립한 PNG·JPEG). 실제 홍보물이 아닙니다.
대부분은 image_worker.prepare를 같은 프로세스에서 호출하고, 시간 제한·프로세스 정리는 실제 별도 프로세스로 확인합니다.
공통 generate_structured_from_pdf 자리에 가짜 함수를 넣습니다. 가짜 함수의 성공 결과는 실제 AI 판독 성공이 아닙니다.
"""
import hashlib
import importlib.util
import io
import math
import multiprocessing
import os
import struct
import sys
import unittest
import zlib
from unittest import mock

from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo
from pypdf import PdfReader
from werkzeug.datastructures import FileStorage

from app import create_app
from common import config, errors
from common.pdf_utils import inspect_pdf
from features.green_claim import image_input, image_worker, ocr_service, service

HAS_OPENAI = importlib.util.find_spec("openai") is not None and importlib.util.find_spec("pydantic") is not None
SECRETS = (b"EXIF-SECRET-TEST", b"GPS", b"XMP-SECRET-TEST", b"COMMENT-SECRET-TEST", b"TEXT-SECRET-TEST",
           b"ITXT-SECRET-TEST")


# ---------- 가상 이미지 ----------

def png_chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(body, zlib.crc32(kind)))


def make_png(width=4, height=3, color=2, depth=8, interlace=0, palette=None, trns=None, extra=(), rows=None, idat=None,
             end=True):
    """직접 조립한 PNG(필터 0). rows: 압축 전 데이터, idat: IDAT 본문을 직접 지정."""
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    if rows is None and idat is None:
        rows = (b"\x00" + b"\x00" * math.ceil(width * channels * depth / 8)) * height
    out = image_input.PNG_SIGNATURE + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, color, 0, 0,
                                                                       interlace))
    if palette is not None:
        out += png_chunk(b"PLTE", palette)
    if trns is not None:
        out += png_chunk(b"tRNS", trns)
    for kind, body in extra:
        out += png_chunk(kind, body)
    out += png_chunk(b"IDAT", zlib.compress(rows) if idat is None else idat)
    if end:
        out += png_chunk(b"IEND", b"")
    return out


def jpeg_segment(marker, body):
    return bytes([0xFF, marker]) + struct.pack(">H", len(body) + 2) + body


def make_jpeg(width=16, height=8, components=3):
    """모든 계수가 0인(회색 단색) baseline JPEG. 큰 해상도 경계 시험용(파일이 작음)."""
    head = b"\xff\xd8" + jpeg_segment(0xDB, b"\x00" + bytes([1] * 64))
    comps = b"".join(bytes([i + 1, 0x11, 0]) for i in range(components))
    head += jpeg_segment(0xC0, struct.pack(">BHHB", 8, height, width, components) + comps)
    head += jpeg_segment(0xC4, b"\x00" + bytes([1] + [0] * 15) + b"\x00")
    head += jpeg_segment(0xC4, b"\x10" + bytes([1] + [0] * 15) + b"\x00")
    head += jpeg_segment(0xDA, bytes([components]) + b"".join(bytes([i + 1, 0]) for i in range(components))
                         + b"\x00\x3f\x00")
    bits = 2 * components * math.ceil(width / 8) * math.ceil(height / 8)
    size = math.ceil(bits / 8)
    pad = size * 8 - bits
    scan = b"\x00" * (size - 1) + bytes([(1 << pad) - 1]) if pad else b"\x00" * size
    return head + scan + b"\xff\xd9"


def encode(image, fmt, **params):
    buf = io.BytesIO()
    image.save(buf, fmt, **params)
    return buf.getvalue()


def text_like(mode="RGB", size=(48, 24)):
    """왼쪽 위 검은 사각형 + 흰 배경(방향 확인용)."""
    image = Image.new(mode, size, "white" if mode != "1" else 1)
    ImageDraw.Draw(image).rectangle((0, 0, size[0] // 2 - 1, size[1] // 2 - 1), fill="black" if mode != "1" else 0)
    return image


def exif_with(orientation=None, secret=False):
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    if secret:
        exif[0x010E] = "EXIF-SECRET-TEST"
        gps = exif.get_ifd(0x8825)
        gps[1] = "N"
        gps[2] = (37.0, 33.0, 0.0)
    return exif


def adam7_gray(width, height, values):
    """인터레이스(Adam7) 8비트 회색 PNG. values[y][x] 원본 값."""
    passes = [(0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]
    raw = b""
    for x0, y0, dx, dy in passes:
        xs = range(x0, width, dx)
        for y in range(y0, height, dy):
            if xs:
                raw += b"\x00" + bytes(values[y][x] for x in xs)
    return make_png(width, height, color=0, depth=8, interlace=1, idat=zlib.compress(raw))


LIMITS = {"max_width": 8000, "max_height": 8000, "max_pixels": 20_000_000, "max_sent_bytes": config.PDF_MAX_BYTES}
PNG_RGB = encode(text_like(), "PNG")
JPEG_RGB = encode(text_like(), "JPEG", quality=95)


def prepare(data, expected, **limits):
    return image_worker.prepare(data, dict(LIMITS, expected=expected, **limits))


def sent(result):
    """판독용 사본 PNG를 열어 돌려줌."""
    image = Image.open(io.BytesIO(result["png"]))
    image.load()
    return image


def pixels(image):
    return list(image.get_flattened_data())


def inprocess_worker(data, timeout, target=None, options=None):
    """service.run_worker 대신 같은 프로세스에서 image_worker.prepare 실행(단위 테스트 속도용)."""
    return image_worker.prepare(data, options)


def fast():
    return mock.patch.object(service, "run_worker", side_effect=inprocess_worker)


# ---------- 모의 AI ----------

class FakeSchema:
    """테스트용 스키마 자리표시자(실제 스키마는 ocr_schema.ImageOcrResult, pydantic 필요)."""


class FakeResult:
    def __init__(self, text, uncertain, limitations, pdf_bytes, model="test-model"):
        self.data = type("Data", (), {"text": text, "uncertain": uncertain, "limitations": limitations})()
        self.model = model
        self.usage = None
        self.pdf = inspect_pdf(pdf_bytes)


def fake_ai(text="Texto da imagem\r\nLinha 2 [판독 불가]", uncertain=("linha 2 borrada",), limitations=(), raises=None):
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        if raises:
            raise raises
        return FakeResult(text, list(uncertain), list(limitations), kwargs["pdf_bytes"])

    return generate, calls


def patched(generate):
    return mock.patch.object(ocr_service, "_load_ai", return_value=(generate, FakeSchema))


def pdf_image(pdf):
    page = PdfReader(io.BytesIO(pdf)).pages[0]
    return page, page["/Resources"]["/XObject"]["/Im0"].get_object()


# ---------- 테스트 ----------

class DecodeAndCopyTest(unittest.TestCase):
    def test_supported_sources_decode_and_convert(self):
        palette_image = text_like().convert("P")
        cases = [
            ("JPEG RGB", JPEG_RGB, "jpeg", "RGB"),
            ("JPEG 회색", encode(text_like("L"), "JPEG"), "jpeg", "L"),
            ("JPEG CMYK", encode(text_like().convert("CMYK"), "JPEG"), "jpeg", "RGB"),
            ("PNG RGB", PNG_RGB, "png", "RGB"),
            ("PNG 회색", encode(text_like("L"), "PNG"), "png", "L"),
            ("PNG 1비트", encode(text_like("1"), "PNG"), "png", "L"),
            ("PNG 팔레트", encode(palette_image, "PNG"), "png", "RGB"),
            ("PNG 16비트 RGB", make_png(3, 1, color=2, depth=16,
                                        rows=b"\x00" + struct.pack(">9H", *[128 * 257, 0, 65535] * 3)), "png", "RGB"),
            ("합성 JPEG 8000×2500", make_jpeg(8000, 2500, components=1), "jpeg", "L"),
        ]
        for name, data, kind, color in cases:
            with self.subTest(name):
                r = prepare(data, kind)
                self.assertEqual(r["status"], "ok", r)
                info = r["image"]
                self.assertEqual((info["format"], info["sent_format"], info["sent_color"]), (kind, "png", color))
                self.assertEqual((info["sent_width"], info["sent_height"]), (info["width"], info["height"]))
                self.assertFalse(info["orientation_applied"] or info["transparency_flattened"])
                self.assertEqual(sent(r).size, (info["width"], info["height"]))

    def test_lossless_sources_keep_pixels(self):
        for name, image in (("RGB", text_like()), ("L", text_like("L"))):
            with self.subTest(name):
                self.assertEqual(pixels(sent(prepare(encode(image, "PNG"), "png"))), pixels(image))
        palette = text_like().convert("P")
        self.assertEqual(pixels(sent(prepare(encode(palette, "PNG"), "png"))), pixels(palette.convert("RGB")))
        r = prepare(make_png(3, 1, color=2, depth=16, rows=b"\x00" + struct.pack(">9H", *[128 * 257, 0, 65535] * 3)),
                    "png")
        self.assertEqual(pixels(sent(r)), [(128, 0, 255)] * 3)  # 16비트 → 8비트(상위 바이트)

    def test_cmyk_text_stays_dark(self):
        r = prepare(encode(text_like().convert("CMYK"), "JPEG", quality=95), "jpeg")
        copy = sent(r)
        self.assertLess(sum(copy.getpixel((2, 2))), 60)       # 검은 영역
        self.assertGreater(sum(copy.getpixel((40, 20))), 700)  # 흰 영역

    def test_interlaced_png(self):
        values = [[(x * 16 + y * 3) % 256 for x in range(9)] for y in range(7)]
        r = prepare(adam7_gray(9, 7, values), "png")
        self.assertEqual(r["status"], "ok", r)
        self.assertEqual(pixels(sent(r)), [v for row in values for v in row])

    def test_transparency_flattened_on_white(self):
        rgba = Image.new("RGBA", (2, 1))
        rgba.putpixel((0, 0), (0, 0, 0, 0))
        rgba.putpixel((1, 0), (255, 0, 0, 128))
        r = prepare(encode(rgba, "PNG"), "png")
        self.assertTrue(r["image"]["transparency_flattened"])
        first, second = pixels(sent(r))
        self.assertEqual(first, (255, 255, 255))
        self.assertEqual(second[0], 255)
        self.assertTrue(126 <= second[1] <= 128 and second[1] == second[2])  # 255 × (1 − 128/255) ≈ 127
        palette = b"\x00\x00\x00\xff\xff\xff"
        r = prepare(make_png(2, 1, color=3, depth=8, palette=palette, trns=b"\x00", rows=b"\x00\x00\x01"), "png")
        self.assertEqual((r["image"]["transparency_flattened"], pixels(sent(r))), (True, [(255, 255, 255)] * 2))
        r = prepare(make_png(2, 1, color=4, depth=8, rows=b"\x00\x00\x00\x00\xff"), "png")  # 회색+알파
        self.assertEqual((r["image"]["sent_color"], pixels(sent(r))), ("L", [255, 0]))
        r = prepare(make_png(1, 1, color=4, depth=16, rows=b"\x00" + struct.pack(">HH", 128 * 257, 65535)), "png")
        self.assertEqual(pixels(sent(r)), [(128, 128, 128)])  # 16비트 회색+알파(Pillow가 RGBA로 읽음)

    def test_white_text_on_transparent_background_disappears(self):
        """한계 기록용: 투명 배경 위 흰 글자는 흰 배경 합성 후 구별되지 않음(자동 보정하지 않음)."""
        image = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((5, 5, 30, 12), fill=(255, 255, 255, 255))
        copy = sent(prepare(encode(image, "PNG"), "png"))
        self.assertEqual(set(pixels(copy)), {(255, 255, 255)})

    def test_exif_orientation_applied_once(self):
        # 저장 이미지 48×24, 왼쪽 위 검정. Orientation 6(시계 방향 90도) → 사본 24×48, 검정은 오른쪽 위
        data = encode(text_like(), "JPEG", quality=95, exif=exif_with(6))
        r = prepare(data, "jpeg")
        info = r["image"]
        self.assertEqual((info["exif_orientation"], info["orientation_applied"]), (6, True))
        self.assertEqual((info["width"], info["height"], info["sent_width"], info["sent_height"]), (48, 24, 24, 48))
        copy = sent(r)
        self.assertLess(sum(copy.getpixel((20, 3))), 100)
        self.assertGreater(sum(copy.getpixel((3, 3))), 600)
        self.assertNotIn(0x0112, copy.getexif())  # 사본에 방향 정보가 남지 않아 다시 회전되지 않음
        pdf = image_input.build_pdf(r["png"])
        page, image = pdf_image(pdf)
        self.assertEqual([float(v) for v in page.mediabox], [0, 0, 24, 48])
        self.assertIn("q 24 0 0 48 0 0 cm /Im0 Do Q", page.get_contents().get_data().decode())  # PDF 배치 회전 없음
        # PNG(무손실) 180도: 왼쪽 위 검정 → 오른쪽 아래
        r = prepare(encode(text_like(), "PNG", exif=exif_with(3)), "png")
        copy = sent(r)
        self.assertEqual((copy.getpixel((47, 23)), copy.getpixel((0, 0))), ((0, 0, 0), (255, 255, 255)))
        for value in (0, 9):
            with self.subTest(invalid=value):
                r = prepare(encode(text_like(), "JPEG", exif=exif_with(value or None)), "jpeg")
                self.assertEqual((r["image"]["exif_orientation"], r["image"]["sent_width"]), (1, 48))


class MetadataTest(unittest.TestCase):
    def test_metadata_removed_from_copy_and_pdf(self):
        jpeg = encode(text_like(), "JPEG", exif=exif_with(secret=True), comment=b"COMMENT-SECRET-TEST",
                      xmp=b"<x:xmpmeta>XMP-SECRET-TEST</x:xmpmeta>", dpi=(300, 300))
        info = PngInfo()
        info.add_text("Comment", "TEXT-SECRET-TEST")
        info.add_itxt("Description", "ITXT-SECRET-TEST")
        png = encode(text_like(), "PNG", pnginfo=info, exif=exif_with(secret=True), dpi=(300, 300))
        for name, data, kind in (("JPEG", jpeg, "jpeg"), ("PNG", png, "png")):
            with self.subTest(name):
                self.assertTrue(any(secret in data for secret in SECRETS))  # 원본에는 있음
                before = hashlib.sha256(data).hexdigest()
                r = prepare(data, kind)
                copy_png = r["png"]
                pdf = image_input.build_pdf(copy_png)
                for secret in SECRETS + (b"Exif", b"xmpmeta"):
                    self.assertNotIn(secret, copy_png)
                    self.assertNotIn(secret, pdf)
                self.assertEqual(image_worker._png_chunk_types(copy_png), [b"IHDR", b"IDAT", b"IEND"])
                copy = sent(r)
                self.assertEqual((dict(copy.info), len(copy.getexif())), ({}, 0))
                self.assertEqual(hashlib.sha256(data).hexdigest(), before)  # 원본 bytes 미변경

    def test_pdf_holds_copy_data_and_passes_common_check(self):
        r = prepare(JPEG_RGB, "jpeg")
        pdf = image_input.build_pdf(r["png"])
        self.assertEqual(inspect_pdf(pdf).page_count, 1)
        _, image = pdf_image(pdf)
        self.assertEqual((image["/Width"], image["/Height"], image["/ColorSpace"]), (48, 24, "/DeviceRGB"))
        self.assertEqual(image["/DecodeParms"]["/Predictor"], 15)
        self.assertNotIn(JPEG_RGB[100:140], pdf)  # 원본 압축 데이터를 넣지 않음


class RejectTest(unittest.TestCase):
    def assertCode(self, data, expected, code, **limits):
        r = prepare(data, expected, **limits)
        self.assertEqual(r, {"status": "error", "code": code})

    def test_format_and_extension(self):
        gif = encode(Image.new("RGB", (4, 4)), "GIF")
        webp_like = b"RIFF\x00\x00\x00\x00WEBPVP8 "
        self.assertCode(gif, "png", "IMAGE_INVALID")
        self.assertCode(webp_like, "jpeg", "IMAGE_INVALID")
        self.assertCode("그냥 텍스트".encode(), "jpeg", "IMAGE_INVALID")
        self.assertCode(encode(Image.new("RGB", (4, 4)), "BMP"), "png", "IMAGE_INVALID")  # JPEG·PNG 외 플러그인 미사용
        self.assertCode(PNG_RGB, "jpeg", "IMAGE_FORMAT_MISMATCH")
        self.assertCode(JPEG_RGB, "png", "IMAGE_FORMAT_MISMATCH")

    def test_damaged(self):
        crc = PNG_RGB[:-5] + bytes([PNG_RGB[-5] ^ 1]) + PNG_RGB[-4:]
        noisy = make_png(30, 30, rows=b"".join(b"\x00" + os.urandom(90) for _ in range(30)))
        bad_crc_idat = noisy[:60] + bytes([noisy[60] ^ 0xFF]) + noisy[61:]
        rows = (b"\x00" + b"\x00" * 12) * 20
        cases = {
            "PNG 잘림": (PNG_RGB[:-30], "png"),
            "PNG IEND CRC": (crc, "png"),
            "PNG IDAT CRC(verify)": (bad_crc_idat, "png"),
            "PNG 필터 번호 5": (make_png(4, 20, rows=rows[:13] + b"\x05" + rows[14:]), "png"),
            "JPEG 잘림": (JPEG_RGB[: len(JPEG_RGB) // 2], "jpeg"),
        }
        for name, (data, kind) in cases.items():
            with self.subTest(name):
                self.assertCode(data, kind, "IMAGE_DAMAGED")
        self.assertCode(JPEG_RGB[:20], "jpeg", "IMAGE_INVALID")  # 머리 일부만 남으면 형식 자체를 알아보지 못함

    def test_known_limit_png_short_rows_not_detected(self):
        """한계 기록용(Pillow 13.0.0 확인): 압축 스트림은 정상으로 끝나지만 줄이 1개 모자란 PNG는 verify·load가 통과한다.
        파일 끝이 잘린 경우는 위 test_damaged에서 거부됨. 이 사례를 따로 감지하지 않는다(feature_spec.md 한계)."""
        rows = (b"\x00" + b"\x00" * 12) * 20
        self.assertEqual(prepare(make_png(4, 20, rows=rows[:-13]), "png")["status"], "ok")

    def test_dimension_and_pixel_limits_before_decoding(self):
        broken = b"\x78\x9c\xff\xff"  # 손상 IDAT: 픽셀을 디코딩하면 오류 → 크기 코드가 나오면 디코딩 전 검사
        self.assertCode(make_png(8001, 1, idat=broken), "png", "IMAGE_TOO_LARGE_DIMENSIONS")
        self.assertCode(make_png(1, 8001, idat=broken), "png", "IMAGE_TOO_LARGE_DIMENSIONS")
        self.assertCode(make_png(5001, 4000, idat=broken), "png", "IMAGE_TOO_MANY_PIXELS")
        self.assertCode(make_jpeg(8001, 8, components=1), "jpeg", "IMAGE_TOO_LARGE_DIMENSIONS")
        self.assertCode(make_jpeg(8000, 2501, components=1), "jpeg", "IMAGE_TOO_MANY_PIXELS")
        self.assertEqual(prepare(make_png(8000, 1, color=0, depth=1), "png")["status"], "ok")
        self.assertEqual(prepare(make_png(5000, 4000, color=0, depth=1), "png")["image"]["sent_color"], "L")
        # Pillow 압축 폭탄 경고·오류도 픽셀 수 초과로 처리(상한을 낮춰 확인)
        self.assertCode(make_png(30, 30), "png", "IMAGE_TOO_MANY_PIXELS", max_pixels=100)

    def test_frames_and_modes(self):
        frames = [Image.new("RGB", (8, 8), c) for c in ("red", "blue")]
        self.assertCode(encode(frames[0], "PNG", save_all=True, append_images=frames[1:]), "png", "IMAGE_MULTI_FRAME")
        self.assertCode(encode(frames[0], "MPO", save_all=True, append_images=frames[1:]), "jpeg", "IMAGE_MULTI_FRAME")
        gray16 = make_png(2, 1, color=0, depth=16, rows=b"\x00" + struct.pack(">HH", 0, 65535))
        self.assertCode(gray16, "png", "IMAGE_UNSUPPORTED_MODE")

    def test_converted_size_limit(self):
        self.assertCode(PNG_RGB, "png", "IMAGE_CONVERTED_TOO_LARGE", max_sent_bytes=50)

    def test_dependency_missing(self):
        with mock.patch.dict(sys.modules, {"PIL": None}):
            self.assertCode(PNG_RGB, "png", "IMAGE_DEPENDENCY_MISSING")

    def test_upload_precheck(self):
        for name, data, code in (("a.png", b"", "FILE_EMPTY"), ("a.png", b"x" * 10_000_001, "FILE_TOO_LARGE"),
                                 ("a.gif", b"GIF89a", "FILE_TYPE_UNSUPPORTED"), ("a", b"x", "FILE_TYPE_UNSUPPORTED")):
            with self.subTest(code=code, name=name):
                with self.assertRaises(service.ExtractError) as ctx:
                    image_input.check_upload(name, data)
                self.assertEqual(ctx.exception.code, code)
        self.assertEqual(image_input.check_upload("A.JPEG", b"x"), "jpeg")


class ProcessTest(unittest.TestCase):
    """실제 별도 프로세스(spawn): 성공·시간 초과·예외에서 자식 프로세스가 남지 않는지."""

    def test_success_timeout_and_cleanup(self):
        png, image = ocr_service.prepare_image("promo.png", PNG_RGB)
        self.assertEqual((image["sent_width"], image_worker._png_chunk_types(png)[0]), (48, b"IHDR"))
        self.assertEqual(multiprocessing.active_children(), [])
        with self.assertRaises(service.ExtractError) as ctx:
            ocr_service.prepare_image("promo.png", PNG_RGB, timeout=0.001)
        self.assertEqual(ctx.exception.code, "IMAGE_PREPARE_TIMEOUT")
        self.assertEqual(multiprocessing.active_children(), [])
        with self.assertRaises(service.ExtractError) as ctx:
            ocr_service.prepare_image("promo.png", PNG_RGB[:-30])
        self.assertEqual(ctx.exception.code, "IMAGE_DAMAGED")
        self.assertEqual(multiprocessing.active_children(), [])

    def test_worker_exception_and_crash_codes(self):
        sent_results = []
        in_conn = mock.Mock(recv_bytes=mock.Mock(return_value=PNG_RGB))
        out_conn = mock.Mock(send=sent_results.append)
        with mock.patch.object(image_worker, "prepare", side_effect=RuntimeError("C:\\secret")):
            image_worker.run(in_conn, out_conn, {})
        self.assertEqual(sent_results, [{"status": "error", "code": "IMAGE_CONVERT_FAILED"}])
        in_conn.close.assert_called_once()
        out_conn.close.assert_called_once()
        with mock.patch.object(service, "run_worker", side_effect=service.ExtractError("EXTRACT_FAILED")):
            with self.assertRaises(service.ExtractError) as ctx:
                ocr_service.prepare_image("promo.png", PNG_RGB)
        self.assertEqual(ctx.exception.code, "IMAGE_CONVERT_FAILED")
        with mock.patch.object(service, "run_worker", side_effect=service.ExtractError("EXTRACT_BUSY")):
            with self.assertRaises(service.ExtractError) as ctx:
                ocr_service.prepare_image("promo.png", PNG_RGB)
        self.assertEqual(ctx.exception.code, "EXTRACT_BUSY")


class RunImageOcrTest(unittest.TestCase):
    def test_calls_common_function_once_with_copy_pdf(self):
        generate, calls = fake_ai()
        data = encode(text_like(), "PNG", exif=exif_with(secret=True))
        with fast(), patched(generate) as load:
            r = ocr_service.run_image_ocr("내 홍보물.png", data)
        load.assert_called_once_with("ImageOcrResult")
        self.assertEqual(len(calls), 1)
        kw = calls[0]
        self.assertEqual(set(kw), {"instructions", "pdf_bytes", "schema"})
        self.assertEqual(kw["instructions"], ocr_service.load_instructions(ocr_service.IMAGE_PROMPT_PATH))
        self.assertIs(kw["schema"], FakeSchema)
        self.assertEqual(inspect_pdf(kw["pdf_bytes"]).page_count, 1)
        for secret in ("홍보물".encode(), b"EXIF-SECRET-TEST", b"GPS"):
            self.assertNotIn(secret, kw["pdf_bytes"])
        expected = "Texto da imagem\nLinha 2 [판독 불가]"
        self.assertEqual((r["text"], r["char_count"]), (expected, len(expected)))
        self.assertEqual((r["format"], r["source"], r["prompt_version"]), ("image", "ai_ocr", "image_ocr_v1"))
        self.assertEqual(set(r["image"]), {"format", "width", "height", "color_mode", "exif_orientation",
                                           "orientation_applied", "transparency_flattened", "sent_format",
                                           "sent_width", "sent_height", "sent_color", "sent_bytes"})
        self.assertNotIn("page_count", r)
        self.assertIn(ocr_service.NOTICE_METADATA, r["notices"])
        self.assertNotIn(ocr_service.NOTICE_TRANSPARENCY, r["notices"])
        self.assertEqual(r["limits"]["local_timeout_seconds"], 30.0)

    def test_orientation_and_transparency_notices(self):
        generate, _ = fake_ai()
        with fast(), patched(generate):
            r = ocr_service.run_image_ocr("a.jpg", encode(text_like(), "JPEG", exif=exif_with(8)))
            self.assertIn(ocr_service.NOTICE_ORIENTATION, r["notices"])
            r = ocr_service.run_image_ocr("a.png", encode(Image.new("RGBA", (8, 8), (0, 0, 0, 0)), "PNG"))
            self.assertIn(ocr_service.NOTICE_TRANSPARENCY, r["notices"])
            self.assertTrue(r["image"]["transparency_flattened"])

    def test_no_text_and_char_limit_boundary(self):
        for text, code in ((" \n ", "OCR_NO_TEXT"), ("", "OCR_NO_TEXT"), ("a" * 20_001, "TEXT_TOO_LONG")):
            with self.subTest(code=code, size=len(text)):
                generate, _ = fake_ai(text=text)
                with fast(), patched(generate), self.assertRaises(service.ExtractError) as ctx:
                    ocr_service.run_image_ocr("a.png", PNG_RGB)
                self.assertEqual(ctx.exception.code, code)
        generate, _ = fake_ai(text="a" * 19_999 + "\r\n")
        with fast(), patched(generate):
            self.assertEqual(ocr_service.run_image_ocr("a.png", PNG_RGB)["char_count"], 20_000)

    def test_validation_failures_do_not_call_ai(self):
        load = mock.Mock()
        cases = [
            ("a.png", b"", "FILE_EMPTY"),
            ("a.png", PNG_RGB[:-30], "IMAGE_DAMAGED"),
            ("a.jpg", PNG_RGB, "IMAGE_FORMAT_MISMATCH"),
            ("a.png", b"GIF89a", "IMAGE_INVALID"),
            ("a.png", make_png(8001, 1, idat=b"x"), "IMAGE_TOO_LARGE_DIMENSIONS"),
            ("a.jpg", make_jpeg(8000, 2501, components=1), "IMAGE_TOO_MANY_PIXELS"),
            ("a.png", make_png(2, 1, color=0, depth=16), "IMAGE_UNSUPPORTED_MODE"),
            ("a.gif", b"GIF89a", "FILE_TYPE_UNSUPPORTED"),
            ("a.docx", b"PK\x03\x04", "FILE_TYPE_UNSUPPORTED"),
        ]
        with fast(), mock.patch.object(ocr_service, "_load_ai", load):
            for name, data, code in cases:
                with self.subTest(code=code, name=name):
                    with self.assertRaises(service.ExtractError) as ctx:
                        ocr_service.run_file_ocr(name, data)
                    self.assertEqual(ctx.exception.code, code)
        load.assert_not_called()

    def test_dependency_busy_no_retry(self):
        with fast(), mock.patch.dict(sys.modules, {"common.ai_client": None}):
            with self.assertRaises(service.ExtractError) as ctx:
                ocr_service.run_image_ocr("a.png", PNG_RGB)
        self.assertEqual(ctx.exception.code, "AI_DEPENDENCY_MISSING")
        generate, calls = fake_ai()
        self.assertTrue(ocr_service._ai_slots.acquire(blocking=False))
        try:
            with fast(), patched(generate), self.assertRaises(service.ExtractError) as ctx:
                ocr_service.run_image_ocr("a.png", PNG_RGB)
            self.assertEqual((ctx.exception.code, calls), ("EXTRACT_BUSY", []))
        finally:
            ocr_service._ai_slots.release()
        for err in (errors.AIIncompleteError(), errors.AIOutputInvalidError(), errors.AITimeoutError(),
                    errors.AIRefusalError()):
            with self.subTest(err.code):
                generate, calls = fake_ai(raises=err)
                with fast(), patched(generate), self.assertRaises(errors.AIError):
                    ocr_service.run_image_ocr("a.jpg", JPEG_RGB)
                self.assertEqual(len(calls), 1)

    def test_pdf_check_failures_are_not_reported_as_pdf_errors(self):
        generate, calls = fake_ai()
        cases = ((errors.PdfTooLargeError(), "IMAGE_CONVERTED_TOO_LARGE"), (errors.PdfCorruptError(), "IMAGE_CONVERT_FAILED"))
        for raised, code in cases:
            with self.subTest(code):
                with fast(), patched(generate), mock.patch.object(ocr_service, "inspect_pdf", side_effect=raised):
                    with self.assertRaises(service.ExtractError) as ctx:
                        ocr_service.run_image_ocr("a.png", PNG_RGB)
                self.assertEqual(ctx.exception.code, code)
        self.assertEqual(calls, [])

    def test_logs_without_content(self):
        generate, _ = fake_ai(text="a" * 20_001 + "SEGREDO")
        with fast(), patched(generate), mock.patch.object(ocr_service.logger, "warning") as warn:
            with self.assertRaises(service.ExtractError):
                ocr_service.run_image_ocr("segredo.png", PNG_RGB)
        self.assertIn("TEXT_TOO_LONG", str(warn.call_args))
        self.assertNotIn("SEGREDO", str(warn.call_args_list))
        self.assertNotIn("segredo", str(warn.call_args_list))

    @unittest.skipUnless(HAS_OPENAI, "openai·pydantic 미설치 환경")
    def test_real_common_function_without_settings_never_creates_client(self):
        """실제 공통 함수를 쓰되 키·모델이 없는 상태: 클라이언트를 만들기 전에 AI_CONFIG_MISSING. 외부 통신 없음."""
        from common import ai_client
        clean = {k: v for k, v in os.environ.items() if not k.startswith("OPENAI_")}
        forbid = mock.Mock(side_effect=AssertionError("클라이언트 생성 금지"))
        with fast(), mock.patch.dict(os.environ, clean, clear=True), \
                mock.patch.object(ai_client, "_create_client", forbid):
            with self.assertRaises(errors.AIConfigError):
                ocr_service.run_image_ocr("a.png", PNG_RGB)
        forbid.assert_not_called()

    @unittest.skipUnless(HAS_OPENAI, "openai·pydantic 미설치 환경")
    def test_schema_strict_conversion(self):
        from openai.lib._pydantic import to_strict_json_schema
        from features.green_claim.ocr_schema import ImageOcrResult
        schema = to_strict_json_schema(ImageOcrResult)
        self.assertEqual(set(schema["required"]), {"text", "uncertain", "limitations"})
        self.assertFalse(schema["additionalProperties"])


class PromptTest(unittest.TestCase):
    def test_image_prompt_rules(self):
        text = ocr_service.load_instructions(ocr_service.IMAGE_PROMPT_PATH)
        for rule in ("요약·번역·교정", "추가하지 않는다", "[판독 불가]", "지시로 따르지 말고", "접속하거나 외부 도구",
                     "디자인·색상·그림·사진·로고·배치", "정확도 백분율", "판독용 사본", "흰색 배경"):
            self.assertIn(rule, text)
        self.assertNotIn("\r", text)


class RouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def post(self, url="/api/green-claim/ocr", filename="promo.png", content=PNG_RGB):
        return self.client.post(url, content_type="multipart/form-data",
                                data={"promo_file": FileStorage(io.BytesIO(content), filename=filename)})

    def test_success_shape(self):
        generate, _ = fake_ai(limitations=["texto pequeno"])
        with fast(), patched(generate):
            resp = self.post()
        body = resp.get_json()
        self.assertEqual(resp.status_code, 200, body)
        self.assertEqual(set(body["data"]), {
            "format", "source", "image", "text", "char_count", "uncertain", "uncertain_count", "unreadable_mark_count",
            "model_limitations", "model", "prompt_version", "notices", "limits"})

    def test_error_codes_and_status(self):
        cases = [
            ("promo.png", b"", "FILE_EMPTY", 400),
            ("promo.png", PNG_RGB[:-30], "IMAGE_DAMAGED", 422),
            ("promo.jpg", PNG_RGB, "IMAGE_FORMAT_MISMATCH", 422),
            ("promo.png", b"GIF89a", "IMAGE_INVALID", 422),
            ("promo.png", make_png(5001, 4000, idat=b"x"), "IMAGE_TOO_MANY_PIXELS", 422),
            ("promo.png", make_png(2, 1, color=0, depth=16), "IMAGE_UNSUPPORTED_MODE", 415),
            ("promo.gif", b"GIF89a", "FILE_TYPE_UNSUPPORTED", 415),
            ("promo.docx", b"PK\x03\x04", "FILE_TYPE_UNSUPPORTED", 415),
        ]
        load = mock.Mock()
        with fast(), mock.patch.object(ocr_service, "_load_ai", load):
            for name, data, code, status in cases:
                with self.subTest(code=code, name=name):
                    resp = self.post(filename=name, content=data)
                    body = resp.get_json()
                    self.assertEqual((resp.status_code, body["error"]["code"]), (status, code))
                    self.assertEqual(set(body["error"]), {"code", "message"})
        load.assert_not_called()
        for raised, code, status in [(errors.AIAuthError(), "AI_AUTH_FAILED", 502),
                                     (errors.AIIncompleteError(), "AI_INCOMPLETE", 502),
                                     (RuntimeError("C:\\secret\\path"), "AI_UNKNOWN_ERROR", 500)]:
            with self.subTest(code):
                generate, _ = fake_ai(raises=raised)
                with fast(), patched(generate):
                    resp = self.post()
                body = resp.get_json()
                self.assertEqual((resp.status_code, body["error"]["code"]), (status, code))
                self.assertNotIn("secret", body["error"]["message"])

    def test_general_extract_rejects_images_without_ai(self):
        load = mock.Mock()
        with mock.patch.object(ocr_service, "_load_ai", load):
            self.assertEqual(self.client.get("/").status_code, 200)
            for name, data in (("promo.png", PNG_RGB), ("promo.jpg", JPEG_RGB)):
                resp = self.post(url="/api/green-claim/extract", filename=name, content=data)
                self.assertEqual((resp.status_code, resp.get_json()["error"]["code"]), (415, "FILE_TYPE_UNSUPPORTED"))
        load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
