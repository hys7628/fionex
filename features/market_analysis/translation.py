"""기사 제목 한국어 번역(포르투갈어·스페인어). common.ai_client.generate_structured를 재사용합니다.

- 번역 대상: language가 포르투갈어·스페인어인 기사 제목. 한국어(KOTRA)·영어 제목은 번역하지 않습니다.
- 뉴스 수집 1회당 OpenAI 1회 호출(서로 다른 제목 최대 MAX_TITLES개). 같은 날(KST) 같은 제목은 서버 메모리에서 재사용합니다.
  디스크·DB에 쓰지 않으며 서버를 다시 시작하면 사라집니다(공개 기사 제목만 다룸).
- 실패하거나 설정이 없어도 기사 표시는 막지 않습니다. 원문 제목만 보이고 상태에 사유를 남깁니다.
- 모델 출력은 id 대조·빈 값·길이 검사를 통과한 것만 씁니다. 화면·PDF에는 'AI 번역'으로 표시합니다.
"""
import json
import threading
import time
from pathlib import Path

from pydantic import BaseModel

from common import ai_client, config
from common.errors import AIError

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT = "news_title_translate_v1.md"
LANGUAGES = {"portuguese", "spanish", "pt", "es"}
MAX_TITLES = 80
MAX_OUTPUT_TOKENS = 4096

_cache = {}  # (KST 날짜, 원문 제목) → 한국어 제목
_lock = threading.Lock()


class TitleKo(BaseModel):
    id: str
    title_ko: str


class Translations(BaseModel):
    items: list[TitleKo]


def needs_translation(item):
    return str(item.get("language") or "").strip().lower() in LANGUAGES


def clear_cache():
    with _lock:
        _cache.clear()


def _prompt():
    return (PROMPT_DIR / PROMPT).read_text(encoding="utf-8")


def translate_titles(items, day, generate=None, clock=time.monotonic):
    """items(공개 dict 목록)에 제자리에서 title_ko를 붙이고 상태 dict를 돌려줍니다.

    상태: status none(대상 없음)|ok|partial|skipped(설정 없음)|failed, count(번역이 붙은 기사 수), calls(호출 수).
    generate: 테스트용 교체(기본 common.ai_client.generate_structured).
    """
    targets = [it for it in items if needs_translation(it) and it.get("title")]
    if not targets:
        return {"status": "none", "count": 0, "calls": 0, "prompt": PROMPT}
    by_title = {}
    for it in targets:
        by_title.setdefault(it["title"], []).append(it)
    with _lock:
        known = {t: _cache[(day, t)] for t in by_title if (day, t) in _cache}
    for title, ko in known.items():
        for it in by_title[title]:
            it["title_ko"] = ko
    pending = [t for t in by_title if t not in known]
    base = {"prompt": PROMPT, "reused": len(known)}
    if not pending:
        return {**base, "status": "ok", "count": len(targets), "calls": 0}

    if generate is None:
        if not config.get_openai_api_key() or not config.get_text_model():
            return {**base, "status": "skipped", "count": _counted(targets), "calls": 0,
                    "reason": "AI 설정(OpenAI 키·모델)이 없어 제목을 번역하지 않았습니다."}
        generate = ai_client.generate_structured

    batch = pending[:MAX_TITLES]
    ids = {"T%d" % i: title for i, title in enumerate(batch, 1)}
    payload = {"items": [{"id": k, "title": title} for k, title in ids.items()]}
    started = clock()
    try:
        res = generate(instructions=_prompt(), input_text=json.dumps(payload, ensure_ascii=False),
                       schema=Translations, max_output_tokens=MAX_OUTPUT_TOKENS)
    except AIError as err:
        return {**base, "status": "failed", "count": _counted(targets), "calls": 1, "code": err.code,
                "reason": "제목 번역에 실패해 원문 제목만 표시합니다(%s)." % err.message}
    done = set()
    for tr in res.data.items:
        title = ids.get(tr.id)
        ko = " ".join(str(tr.title_ko or "").split())
        # 입력에 없는 id, 빈 값, 원문보다 지나치게 긴 출력(설명 덧붙임 의심)은 쓰지 않습니다.
        if title is None or title in done or not ko or len(ko) > max(80, 3 * len(title)):
            continue
        done.add(title)
        with _lock:
            _cache[(day, title)] = ko
        for it in by_title[title]:
            it["title_ko"] = ko
    usage = res.usage
    return {**base, "status": "ok" if len(done) == len(pending) else "partial", "count": _counted(targets), "calls": 1,
            "missing": len(pending) - len(done), "model": res.model, "seconds": round(clock() - started, 1),
            "input_tokens": usage.input_tokens if usage else None, "output_tokens": usage.output_tokens if usage else None}


def _counted(targets):
    return sum(1 for it in targets if it.get("title_ko"))
