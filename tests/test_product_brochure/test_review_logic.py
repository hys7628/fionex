"""제품소개서 화면 상태 로직(review_logic_check.js)을 Node로 실행합니다.

Node가 없으면 건너뜁니다(Node는 프로젝트 의존성이 아님). 브라우저 동작 확인이 아닙니다.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "review_logic_check.js"


class ReviewLogicTests(unittest.TestCase):
    def test_node_logic_checks(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node 없음")
        result = subprocess.run([node, str(SCRIPT)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("checks passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
