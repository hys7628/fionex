"""개발 검증용: 고정 가상 데이터(pdf_fixtures)로 카탈로그 PDF를 만들어 지정한 폴더에 저장합니다.
서비스 사용자 결과 저장이 아니며, 저장소 밖 폴더를 지정해 Git 추적 대상에 섞이지 않게 합니다.

    python tests/test_product_brochure/make_pdf_samples.py <출력 폴더>
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pdf_fixtures  # noqa: E402
from features.product_brochure import pdf_catalog  # noqa: E402

CASES = ("base", "edited", "empty_info", "virtual_all", "long_max", "max_paragraphs", "wide_words", "overflow_details", "overflow_title")


def main(out_dir):
    out = Path(out_dir).resolve()
    if out == ROOT or ROOT in out.parents:
        sys.exit("저장소 밖 폴더를 지정하세요(개발 산출물을 Git 작업 트리에 두지 않음).")
    out.mkdir(parents=True, exist_ok=True)
    for name in CASES:
        start = time.perf_counter()
        try:
            pdf = pdf_catalog.build_pdf(getattr(pdf_fixtures, name)())
        except pdf_catalog.AIError as exc:  # 넘침 등 기대한 실패도 결과로 출력
            print(f"{name}: 실패 {exc.code} {exc.message} ({time.perf_counter() - start:.2f}s)")
            continue
        path = out / f"catalog_{name}.pdf"
        try:
            with open(path, "xb") as f:  # 기존 파일은 덮어쓰지 않음(새 폴더를 지정)
                f.write(pdf)
        except FileExistsError:
            print(f"{name}: 같은 이름 파일이 있어 저장하지 않음 → {path}")
            continue
        print(f"{name}: {len(pdf)} bytes ({time.perf_counter() - start:.2f}s) → {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
