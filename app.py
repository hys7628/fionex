"""Flask 앱 진입점. 공통 화면(사이드바 + 5개 탭 패널)을 한 페이지로 제공합니다."""
from flask import Flask, render_template

from common.config import SERVICE_NAME
from features.home import routes as home_routes
from features.market_analysis import routes as market_analysis_routes
from features.product_brochure import routes as product_brochure_routes
from features.green_claim import routes as green_claim_routes
from features.promotion_studio import routes as promotion_studio_routes

# 사이드바 순서. 각 모듈은 bp(Blueprint)와 FEATURE(메뉴·제목·설명)를 제공합니다.
FEATURE_MODULES = [
    home_routes,
    market_analysis_routes,
    product_brochure_routes,
    green_claim_routes,
    promotion_studio_routes,
]


def create_app():
    app = Flask(__name__)
    features = []
    for module in FEATURE_MODULES:
        app.register_blueprint(module.bp)
        features.append(module.FEATURE)

    @app.route("/")
    def index():
        return render_template("base.html", service_name=SERVICE_NAME, features=features)

    return app


app = create_app()

if __name__ == "__main__":
    # 로컬 개발 기본 포트 5003. README의 flask 실행 명령과 같은 포트를 사용합니다.
    app.run(host="127.0.0.1", port=5003, debug=True)
