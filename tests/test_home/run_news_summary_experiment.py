"""뉴스 요약 프롬프트 A/B 실험(실제 OpenAI 호출, 과금). 자동 테스트가 아니며 담당자가 직접 실행합니다.

실행(프로젝트 루트, Conda jasonenv, 셸에 OPENAI_API_KEY·OPENAI_MODEL 설정):
    python tests/test_home/run_news_summary_experiment.py --live
    python tests/test_home/run_news_summary_experiment.py --live --real 20   # 현재 Google·ABIT 실제 제목도 포함

- 버전마다 가상 사례(+선택: 실제 제목)를 한 번의 요청으로 보냅니다. 기본 2회 요청(v1·v2 각 1회).
- 결과는 docs/worklogs/hong_eunju/experiments/news_summary_<시각>.json 에 저장합니다(키·환경변수 값은 저장하지 않음).
- temperature 등은 공통 클라이언트가 보내지 않습니다(공급자 기본값).
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import config  # noqa: E402
from common.ai_client import generate_structured  # noqa: E402
from common.errors import AIError  # noqa: E402
from features.home import news_summary, service  # noqa: E402

OUT_DIR = ROOT / "docs" / "worklogs" / "hong_eunju" / "experiments"
VERSIONS = ("news_summary_v1.md", "news_summary_v2.md")

# 가상 제목(실제 기사 아님). v2 few-shot 예시와 다른 문장을 씁니다. expect: summary / empty
CASES = [
    {"id": "A1", "kind": "정상", "expect": "summary", "title": "Malharias de Santa Catarina investem em teares mais eficientes"},
    {"id": "A2", "kind": "정상", "expect": "summary", "title": "Associação têxtil lança programa de capacitação para costureiras"},
    {"id": "B1", "kind": "숫자 함정(연도만)", "expect": "summary", "title": "Confecções brasileiras apostam em recuperação das vendas em 2027"},
    {"id": "B2", "kind": "숫자 함정(숫자 없음)", "expect": "summary", "title": "Exportações de tecidos devem crescer no próximo ano"},
    {"id": "C1", "kind": "정보 부족", "expect": "empty", "title": "Veja as novidades da semana"},
    {"id": "C2", "kind": "정보 부족", "expect": "empty", "title": "Clique e saiba mais"},
    {"id": "C3", "kind": "정보 부족", "expect": "empty", "title": "Confira o que mudou hoje"},
    {"id": "D1", "kind": "여러 숫자", "expect": "summary", "title": "Importações de tecidos da Ásia caem 8% no terceiro trimestre de 2026"},
    {"id": "D2", "kind": "여러 숫자", "expect": "summary", "title": "Feira em São Paulo reúne 300 expositores de 15 países entre 3 e 5 de novembro"},
    {"id": "D3", "kind": "여러 숫자(소수·금액)", "expect": "summary", "title": "Preço do fio de poliéster sobe 2,5% e chega a R$ 14,80 por quilo"},
]


def real_cases(limit):
    items = []
    for fetch in (service._fetch_google, service._fetch_abit):
        items.extend(i for i in fetch() if news_summary.is_target(i))
    items = service.dedupe_news(items)[:limit]
    return [{"id": i["id"], "kind": "실제 제목(" + i["origin"] + ")", "expect": "review", "title": i["title"]} for i in items]


def run_version(name, cases):
    requested = [{"id": c["id"], "title": c["title"]} for c in cases]
    record = {"prompt": "features/home/prompts/" + name, "requested_count": len(requested)}
    started = time.perf_counter()
    try:
        result = generate_structured(
            instructions=news_summary.load_prompt(name),
            input_text=json.dumps(requested, ensure_ascii=False),
            schema=news_summary._schema(),
        )
    except AIError as err:
        record.update({"ok": False, "error_code": err.code, "seconds": round(time.perf_counter() - started, 2)})
        return record

    raw = [item.model_dump() for item in result.data.items]
    final, reasons = news_summary.validate_summaries(requested, raw)
    by_id = {}
    for entry in raw:
        by_id.setdefault(entry["id"], entry["summary_ko"])
    rows = []
    for case in cases:
        text = by_id.get(case["id"])
        rows.append({
            "id": case["id"], "kind": case["kind"], "expect": case["expect"], "title": case["title"],
            "raw_summary_ko": text,
            "raw_chars": len(text) if isinstance(text, str) else None,
            "unverified_numbers": news_summary.unverified_numbers(text, case["title"]) if isinstance(text, str) else None,
            "final_summary_ko": final[case["id"]],
        })
    expected_ids = {c["id"] for c in cases}
    record.update({
        "ok": True,
        "model": result.model,
        "usage": result.usage.__dict__ if result.usage else None,
        "seconds": round(time.perf_counter() - started, 2),
        "metrics": {
            "unknown_ids": sum(1 for e in raw if e["id"] not in expected_ids),
            "missing_ids": len(expected_ids - {e["id"] for e in raw}),
            "duplicate_ids": len(raw) - len({e["id"] for e in raw}),
            "raw_with_unverified_numbers": sum(1 for r in rows if r["unverified_numbers"]),
            "raw_over_60_chars": sum(1 for r in rows if (r["raw_chars"] or 0) > news_summary.TARGET_CHARS),
            "expected_empty_total": sum(1 for c in cases if c["expect"] == "empty"),
            "expected_empty_returned_empty": sum(1 for r in rows if r["expect"] == "empty" and not (r["raw_summary_ko"] or "").strip()),
            "expected_summary_returned_empty": sum(1 for r in rows if r["expect"] == "summary" and not (r["raw_summary_ko"] or "").strip()),
            "final_accepted": sum(1 for r in rows if r["final_summary_ko"]),
            "validation_reasons": dict(reasons),
        },
        "rows": rows,
    })
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="실제 OpenAI 호출에 동의(과금)")
    parser.add_argument("--real", type=int, default=0, help="현재 Google·ABIT 실제 제목 N건 포함")
    args = parser.parse_args()
    if not args.live:
        parser.error("실제 OpenAI 호출(과금)입니다. --live 를 붙여 실행하세요.")
    if not config.get_openai_api_key() or not config.get_text_model():
        parser.error("OPENAI_API_KEY와 OPENAI_MODEL 환경변수가 필요합니다(값은 출력하지 않습니다).")

    cases = CASES + (real_cases(args.real) if args.real > 0 else [])
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    report = {
        "experiment": "news_summary_ab_" + now.strftime("%Y_%m_%d_%H%M"),
        "type": "service_prompt_experiment",
        "worker": "홍은주", "feature": "home",
        "run_at": now.isoformat(timespec="seconds"),
        "requested_model_env": config.ENV_OPENAI_MODEL,
        "settings": {"temperature": "미전송(공급자 기본값)", "store": config.TEXT_STORE,
                     "max_output_tokens": config.TEXT_MAX_OUTPUT_TOKENS, "timeout_seconds": config.TEXT_TIMEOUT_SECONDS},
        "input_note": "A~D는 가상 제목. 실제 제목은 Google News RSS 공개 제목(본문 없음).",
        "runs": [run_version(name, cases) for name in VERSIONS],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / ("news_summary_" + now.strftime("%Y_%m_%d_%H%M%S") + ".json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for run in report["runs"]:
        print(run["prompt"], "ok" if run["ok"] else "error " + run.get("error_code", ""),
              json.dumps(run.get("metrics", {}), ensure_ascii=False))
    print("saved:", out)


if __name__ == "__main__":
    main()
