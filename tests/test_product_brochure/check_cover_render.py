"""가상 표지로 실제 Flask PDF API/PDFium 렌더링 확인. 설치된 pypdfium2 필요.
새 실행 폴더만 생성하며 기존 샘플을 변경하지 않습니다. UI/브라우저 검증은 아닙니다.
"""
import hashlib
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app import create_app
from PIL import Image, ImageDraw
import pypdfium2 as pdfium
import pdf_fixtures

out = Path(__file__).parent / "samples" / ("cover_render_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
out.mkdir(parents=True, exist_ok=False)
images = {}
for name, bg, stripe in [("a", (245, 215, 215), (190, 35, 35)), ("b", (210, 225, 250), (35, 65, 190))]:
    im = Image.new("RGB", (1024, 1536), bg)
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 900, 1023, 1535), fill=stripe)
    draw.rectangle((800, 0, 1023, 1535), fill=stripe)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    images[name] = buf.getvalue()
    (out / (name + ".png")).write_bytes(buf.getvalue())

catalog = {"catalog": pdf_fixtures.base()}
rendered = {}
client = create_app().test_client()
with patch("common.ai_client._create_client", side_effect=AssertionError("AI forbidden")):
    for name in ("default", "a", "b", "restored"):
        if name in images:
            response = client.post("/api/product-brochure/pdf", data={"catalog": json.dumps(catalog), "cover_image": (io.BytesIO(images[name]), "cover.png")})
        else:
            response = client.post("/api/product-brochure/pdf", json=catalog)
        assert response.status_code == 200
        data = response.get_data()
        (out / (name + ".pdf")).write_bytes(data)
        response.close()
        rendered[name] = []
        with pdfium.PdfDocument(data) as doc:
            assert len(doc) == 4
            for i in range(4):
                page = doc[i]
                bitmap = page.render(scale=4/3)  # 96 dpi: 화면 CSS px에 대응
                im = bitmap.to_pil().convert("RGB")
                im.save(out / f"{name}_page_{i+1}.png")
                rendered[name].append(im)
                bitmap.close()
                page.close()

for name in ("a", "b", "restored"):
    for i in range(1, 4):
        assert rendered[name][i].tobytes() == rendered["default"][i].tobytes(), (name, i)
assert rendered["restored"][0].tobytes() == rendered["default"][0].tobytes()
assert rendered["a"][0].tobytes() != rendered["b"][0].tobytes()
# CSS object-fit:cover의 794×940, object-position 50% 70%에서 수평 띠는 y≈520px.
# 글자가 없는 오른쪽 위치에서 JPEG 허용 오차 내 같은 경계인지 확인.
for name, color in [("a", (190, 35, 35)), ("b", (35, 65, 190))]:
    im = rendered[name][0]
    y = next(y for y in range(400, 700) if max(abs(a-b) for a,b in zip(im.getpixel((550,y)), color)) < 10)
    expected = (900 * (794 / 1024)) + (940 - 1536 * (794 / 1024)) * 0.7
    assert abs(y - expected) < 3, (name, y, expected)
sheet = Image.new("RGB", (794 * 2, 1123 * 2), "white")
for i, im in enumerate(rendered["a"]):
    sheet.paste(im, ((i % 2) * 794, (i // 2) * 1123))
sheet.save(out / "a_contact_sheet.png")
print(json.dumps({"samples": str(out), "result": "4 PDFs rendered; pages 2-4 pixel-identical; restored page 1 pixel-identical; cover crop boundary within 3px"}))
