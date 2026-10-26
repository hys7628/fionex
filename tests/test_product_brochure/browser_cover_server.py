"""수동 브라우저 회귀 서버: AI만 모의, PDF는 실제 API. 새 패키지/유료 호출 없음.

python tests/test_product_brochure/browser_cover_server.py
브라우저 http://127.0.0.1:5017/#product_brochure
가상 자료만 사용. 실행마다 samples/browser_cover_<timestamp> 새 폴더(기존 파일 덮어쓰기 없음).
"""
import io
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app import create_app
from flask import Response, jsonify, request
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "samples" / ("browser_cover_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
OUT.mkdir(parents=True, exist_ok=False)
# 기존 Node 로직 테스트의 가상 fixture만 재사용(테스트 실행기는 실행하지 않음).
fixture_script = """
const fs=require('fs'), vm=require('vm'), path=require('path');
const file=path.resolve('tests/test_product_brochure/review_logic_check.js');
const ctx={require:require('module').createRequire(file),__dirname:path.dirname(file),console,TextEncoder,Blob,FormData};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(file,'utf8').split('(async () => {')[0] + `
const a=analysisBody(); const g=editableBody();
g.pages.cover.tagline.text='Fibra demonstrativa para teste de capa.';
g.pages.intro.paragraphs[0].text='Material ficticio para verificar o catalogo.';
console.log(JSON.stringify({analysis:a,generation:{ok:true,data:g}}));`,ctx);
"""
fixtures = json.loads(subprocess.check_output(["node", "-e", fixture_script], cwd=ROOT))
images = []
for base, stripe in [((245, 215, 215), (190, 35, 35)), ((210, 225, 250), (35, 65, 190))]:
    im = Image.new("RGB", (1024, 1536), base)
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 900, 1023, 1535), fill=stripe)
    draw.rectangle((800, 0, 1023, 1535), fill=stripe)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    images.append(buf.getvalue())

app = create_app()
counts = {"analyze": 0, "generate": 0, "cover": 0, "pdf": 0}

@app.before_request
def mock_ai():
    if request.path == "/api/product-brochure/analyze":
        counts["analyze"] += 1
        return jsonify(fixtures["analysis"])
    if request.path == "/api/product-brochure/generate":
        counts["generate"] += 1
        return jsonify(fixtures["generation"])
    if request.path == "/api/product-brochure/cover-image":
        i = counts["cover"] % 2
        counts["cover"] += 1
        return Response(images[i], mimetype="image/png")

@app.after_request
def capture(response):
    if request.path == "/" and response.status_code == 200:
        html = response.get_data(as_text=True)
        response.set_data(html.replace("</body>", '<script src="/qa.js"></script></body>'))
    if request.path == "/api/product-brochure/pdf":
        counts["pdf"] += 1
        if response.status_code == 200:
            with (OUT / f"api_{counts['pdf']:02d}.pdf").open("xb") as f:
                f.write(response.get_data())
    return response

@app.get("/qa.js")
def qa_script():
    return Response((HERE / "browser_cover_check.js").read_text(encoding="utf-8"), mimetype="text/javascript")

@app.post("/qa/report")
def report():
    body = request.get_json()
    body["server_counts"] = dict(counts)
    with (OUT / ("report_" + datetime.now().strftime("%H%M%S_%f") + ".json")).open("x", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
    print(json.dumps(body, ensure_ascii=True), flush=True)
    return jsonify(ok=True)

@app.get("/qa/status")
def status():
    return jsonify(counts=counts, samples=str(OUT))

def forbid(*args, **kwargs):
    raise AssertionError("QA server forbids actual AI calls")

if __name__ == "__main__":
    print("QA_SAMPLES=" + str(OUT), flush=True)
    with patch("common.ai_client._create_client", forbid):
        app.run(host="127.0.0.1", port=5017, debug=False, use_reloader=False)
