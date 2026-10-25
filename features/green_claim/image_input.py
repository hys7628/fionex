"""홍보 이미지(JPG·JPEG·PNG) 업로드 사전 검사와 판독용 1페이지 PDF 만들기(feature_spec.md "홍보 이미지 AI 글자 판독").

공통 AI 연결에는 이미지 입력 함수가 없어(docs/decisions.md), image_worker가 만든 판독용 PNG 사본을 1페이지 PDF에 담아
공통 PDF 판독(generate_structured_from_pdf)을 재사용합니다. 메모리 bytes만 다루며 디스크에 쓰지 않습니다.

- 실제 형식·디코딩 검사, EXIF 방향·투명 합성·색 변환, 메타데이터 제거는 image_worker(Pillow, 별도 프로세스)가 합니다.
- 이 모듈은 요청 프로세스에서 크기·확장자만 먼저 확인하고, 사본 PNG의 IDAT 데이터를 PDF 이미지(FlateDecode + PNG 예측기)로
  넣습니다. 사본은 이미 방향을 반영했으므로 PDF 배치는 회전하지 않습니다(1픽셀 = 1pt, 확대·축소 없음).
"""
import struct

from features.green_claim.service import ExtractError, _check_size

# 이번 단계 초기 처리 제한(공급자 수락·판독 품질·비용·메모리 상한 보장 아님). feature_spec.md와 같은 값.
MAX_WIDTH = 8_000
MAX_HEIGHT = 8_000
MAX_PIXELS = 20_000_000

EXTENSIONS = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png"}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_COLOR_SPACES = {"L": ("/DeviceGray", 1), "RGB": ("/DeviceRGB", 3)}


def _extension(filename):
    name = (filename or "").lower()
    dot = name.rfind(".")
    return name[dot:] if dot >= 0 else ""


def is_image_name(filename):
    return _extension(filename) in EXTENSIONS


def check_upload(filename, data):
    """요청 프로세스의 사전 검사. 빈 파일·크기·확장자. 확장자로 기대하는 실제 형식("jpeg"/"png")을 돌려줍니다."""
    _check_size(data)
    expected = EXTENSIONS.get(_extension(filename))
    if expected is None:
        raise ExtractError("FILE_TYPE_UNSUPPORTED")
    return expected


def _png_parts(png):
    """image_worker가 만든 PNG(IHDR·IDAT·IEND, 8비트, 인터레이스 없음)에서 (가로, 세로, 색 형식, IDAT 데이터)."""
    if not png.startswith(PNG_SIGNATURE):
        raise ExtractError("IMAGE_CONVERT_FAILED")
    pos = len(PNG_SIGNATURE)
    header = None
    idat = []
    while pos + 12 <= len(png):
        length, kind = struct.unpack(">I4s", png[pos:pos + 8])
        body = png[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        pos += 12 + length
    if header is None or not idat:
        raise ExtractError("IMAGE_CONVERT_FAILED")
    width, height, depth, color, _, _, interlace = header
    mode = {0: "L", 2: "RGB"}.get(color)
    if mode is None or depth != 8 or interlace:
        raise ExtractError("IMAGE_CONVERT_FAILED")
    return width, height, mode, b"".join(idat)


def build_pdf(png):
    """판독용 PNG 사본 1장을 담은 1페이지 PDF bytes. 사본의 압축 데이터를 그대로 쓰며 다시 인코딩하지 않습니다."""
    width, height, mode, stream = _png_parts(png)
    color_space, channels = _COLOR_SPACES[mode]
    image_dict = (f"/Width {width} /Height {height} /ColorSpace {color_space} /BitsPerComponent 8 "
                  f"/Filter /FlateDecode /DecodeParms << /Predictor 15 /Colors {channels} "
                  f"/BitsPerComponent 8 /Columns {width} >>")
    content = f"q {width} 0 0 {height} 0 0 cm /Im0 Do Q".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
         f"/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>").encode("ascii"),
        (f"<< /Type /XObject /Subtype /Image {image_dict} /Length {len(stream)} >>\nstream\n"
         ).encode("ascii") + stream + b"\nendstream",
        f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    return bytes(out)
