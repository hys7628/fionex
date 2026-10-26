"""홍보 이미지 검사·판독용 사본 만들기. service.run_worker가 별도 프로세스(multiprocessing spawn)에서 run()을 실행합니다.

- 시간 제한·프로세스 종료는 service.py가 담당합니다. 이 모듈은 Flask를 import하지 않습니다.
- Pillow로 실제 형식을 판별하고 verify() 후 다시 열어 load()로 픽셀까지 디코딩합니다. 잘린 파일 허용 설정은 켜지 않습니다.
- 크기·픽셀 수는 픽셀 디코딩 전에 헤더 값으로 확인합니다.
- 판독용 사본: EXIF 방향을 한 번 반영하고, 투명 영역은 흰 배경에 합성하고, 8비트 회색(L) 또는 RGB로 바꾼 뒤
  디코딩한 픽셀만으로 새 이미지를 만들어 메타데이터 없는 PNG로 저장합니다. 자르기·축소·보정은 하지 않습니다.
- 업로드 이미지·사본을 디스크·로그에 남기지 않습니다.
"""
import io
import struct
import warnings

GRAY_MODES = ("1", "L", "LA", "La")
# 변환을 가상 이미지로 확인한 Pillow 색 형식. 16비트 회색(I;16 등)은 L 변환 시 값이 잘려 제외(feature_spec.md).
SUPPORTED_MODES = ("1", "L", "LA", "La", "P", "PA", "RGB", "RGBA", "RGBa", "CMYK", "YCbCr")
ALPHA_MODES = ("LA", "La", "PA", "RGBA", "RGBa")
ALLOWED_PNG_CHUNKS = (b"IHDR", b"IDAT", b"IEND")
WHITE = 255


def _png_chunk_types(png):
    pos, kinds = 8, []
    while pos + 8 <= len(png):
        length, kind = struct.unpack(">I4s", png[pos:pos + 8])
        kinds.append(kind)
        pos += 12 + length
    return kinds


def _open(Image, data):
    return Image.open(io.BytesIO(data), formats=["JPEG", "PNG"])


def prepare(data, limits):
    """이미지 bytes → 판독용 PNG 사본.

    성공: {"status": "ok", "png": bytes, "image": {...}}   실패: {"status": "error", "code": str}
    """
    try:
        from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError
    except ImportError:
        return {"status": "error", "code": "IMAGE_DEPENDENCY_MISSING"}

    ImageFile.LOAD_TRUNCATED_IMAGES = False
    Image.MAX_IMAGE_PIXELS = limits["max_pixels"]
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            return _prepare(Image, ImageOps, UnidentifiedImageError, data, limits)
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            return {"status": "error", "code": "IMAGE_TOO_MANY_PIXELS"}


def _error(code):
    return {"status": "error", "code": code}


def _prepare(Image, ImageOps, UnidentifiedImageError, data, limits):
    try:
        probe = _open(Image, data)
    except UnidentifiedImageError:
        return _error("IMAGE_INVALID")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise
    except Exception:
        return _error("IMAGE_DAMAGED")
    with probe:
        kind = {"JPEG": "jpeg", "MPO": "jpeg", "PNG": "png"}.get(probe.format)
        if kind != limits["expected"]:
            return _error("IMAGE_FORMAT_MISMATCH")
        width, height = probe.size  # 헤더 값. 아직 픽셀을 디코딩하지 않음
        if width <= 0 or height <= 0:
            return _error("IMAGE_DAMAGED")
        if width > limits["max_width"] or height > limits["max_height"]:
            return _error("IMAGE_TOO_LARGE_DIMENSIONS")
        if width * height > limits["max_pixels"]:
            return _error("IMAGE_TOO_MANY_PIXELS")
        if probe.format == "MPO" or getattr(probe, "n_frames", 1) > 1 or getattr(probe, "is_animated", False):
            return _error("IMAGE_MULTI_FRAME")
        mode = probe.mode
        if mode not in SUPPORTED_MODES:
            return _error("IMAGE_UNSUPPORTED_MODE")
        try:
            probe.verify()  # 구조·CRC 확인(PNG CRC 오류는 load()만으로는 통과할 수 있음)
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise
        except Exception:
            return _error("IMAGE_DAMAGED")

    # verify() 뒤에는 같은 객체를 쓸 수 없어 다시 열고 실제 픽셀을 디코딩합니다.
    try:
        image = _open(Image, data)
        image.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise
    except Exception:
        return _error("IMAGE_DAMAGED")
    with image:
        if image.size != (width, height) or image.mode != mode:
            return _error("IMAGE_DAMAGED")
        orientation = _orientation(image)
        has_alpha = mode in ALPHA_MODES or "transparency" in image.info
        copy = _reading_copy(Image, ImageOps, image, mode, has_alpha, orientation)
    try:
        out = io.BytesIO()
        copy.save(out, "PNG")  # 새 이미지라 info가 비어 있어 메타데이터 청크를 쓰지 않음
        png = out.getvalue()
        sent_width, sent_height = copy.size
        sent_color = copy.mode
    finally:
        copy.close()
    if any(kind not in ALLOWED_PNG_CHUNKS for kind in _png_chunk_types(png)):
        return _error("IMAGE_CONVERT_FAILED")
    if len(png) > limits["max_sent_bytes"]:
        return _error("IMAGE_CONVERTED_TOO_LARGE")
    return {
        "status": "ok",
        "png": png,
        "image": {
            "format": kind,
            "width": width,
            "height": height,
            "color_mode": mode,
            "exif_orientation": orientation,
            "orientation_applied": orientation != 1,
            "transparency_flattened": has_alpha,
            "sent_format": "png",
            "sent_width": sent_width,
            "sent_height": sent_height,
            "sent_color": sent_color,
            "sent_bytes": len(png),
        },
    }


def _orientation(image):
    """EXIF Orientation(1~8). 없거나 읽지 못하면 1(반영하지 않음)."""
    try:
        value = image.getexif().get(0x0112, 1)
    except Exception:
        return 1
    return value if isinstance(value, int) and 1 <= value <= 8 else 1


def _reading_copy(Image, ImageOps, image, mode, has_alpha, orientation):
    """방향 반영 → 투명 합성(흰 배경) → L/RGB 변환 → 픽셀만으로 새 이미지. 원본 image 객체는 바꾸지 않습니다."""
    target = "L" if mode in GRAY_MODES else "RGB"
    work = image
    if orientation != 1:
        work = ImageOps.exif_transpose(image)
    if has_alpha:
        rgba = work.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (WHITE, WHITE, WHITE, 255))
        flat = Image.alpha_composite(base, rgba)
        rgba.close()
        base.close()
        converted = flat.convert(target)
        flat.close()
    else:
        converted = work.convert(target)
    if work is not image:
        work.close()
    clean = Image.frombytes(converted.mode, converted.size, converted.tobytes())
    converted.close()
    return clean


def run(in_conn, out_conn, limits):
    """프로세스 진입점. in_conn으로 이미지 bytes를 받고 out_conn으로 결과 dict를 보냅니다."""
    try:
        result = prepare(in_conn.recv_bytes(), limits)
    except Exception:
        result = {"status": "error", "code": "IMAGE_CONVERT_FAILED"}
    try:
        out_conn.send(result)
    except OSError:
        pass  # 시간 초과로 부모가 연결을 닫은 경우. 부모가 이 프로세스를 종료합니다.
    finally:
        in_conn.close()
        out_conn.close()
