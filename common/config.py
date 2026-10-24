"""공통 설정. 공통 화면 실행에는 API 키가 필요하지 않습니다."""
import os

# 서비스(대시보드)명. 2026-10-24 확정(docs/decisions.md).
SERVICE_NAME = "fionex"

# 기능 개발 단계에서 사용. 값이 없어도 공통 화면은 실행됩니다.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "")
