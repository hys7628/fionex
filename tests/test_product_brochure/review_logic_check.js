// 제품소개서 화면 상태 로직(DOM 없음) 점검. Node 내장 모듈만 사용합니다(패키지 설치 없음).
// 실행: node tests/test_product_brochure/review_logic_check.js
// test_review_logic.py가 Node가 있을 때 이 파일을 실행합니다. 브라우저 동작 확인이 아닙니다.
"use strict";
const assert = require("node:assert/strict");
const path = require("node:path");
const R = require(path.join(__dirname, "..", "..", "features", "product_brochure", "static", "product_brochure.js"));

const MiB = 1024 * 1024;
const XSS = "<img src=x onerror=alert(1)>";
const checks = [];
function check(name, fn) { checks.push([name, fn]); }

function field(key, o) {
  return Object.assign({
    key: key, label: key, value: null, status: "not_found", ai_status: "not_found", evidence: [],
    marked_virtual: false, note: null, server_notes: [], confirmed: false,
  }, o || {});
}
function analysisBody(over) {
  const fields = {
    product_name: field("product_name", { value: "리젠 T2T", status: "found", ai_status: "found",
      evidence: [{ page: 1, quote: XSS, page_in_range: true, check: "not_checked" }] }),
    description: field("description", { value: "AI가 확실히 읽지 못한 설명", status: "unclear", ai_status: "found",
      server_notes: ["유효한 근거(페이지·발췌)가 없어 확인 필요로 바꿨습니다."] }),
    yarn_spec: field("yarn_spec"),
    carbon_reduction: field("carbon_reduction"),
    certification: field("certification", { value: null, status: "not_found", marked_virtual: true }),
    moq: field("moq", { value: "500 kg", status: "found", ai_status: "found", marked_virtual: true,
      evidence: [{ page: 9, quote: "MOQ", page_in_range: false, check: "not_checked" }, { page: 2, quote: "MOQ 500 kg", page_in_range: true, check: "not_checked" }] }),
    sample: field("sample", { value: "1 kg", status: "unclear", ai_status: "found", candidates: ["1 kg", "2 kg"] }),
    lead_time: field("lead_time", { value: "30일", status: "found", ai_status: "found", marked_virtual: true, note: XSS,
      evidence: [{ page: 2, quote: "납기 30일", page_in_range: true, check: "not_checked" }] }),
  };
  const data = {
    extraction_status: "unconfirmed", prompt_version: "brochure_extract_v1",
    source: { size_bytes: 1234, page_count: 3 }, model: "test-model",
    fields: Object.values(fields), multiple_products: true,
    review_notes: [{ source: "server", message: "복수 제품" }, { source: "ai", message: XSS }],
  };
  return { ok: true, data: Object.assign(data, over || {}) };
}
function ok(body) { return { status: 200, json: body }; }

/* 파일 검사 */
check("파일 크기 경계·잘못된 파일", () => {
  assert.equal(R.MAX_FILE_BYTES, 10 * MiB);
  assert.equal(R.validateFile({ name: "a.pdf", size: 10 * MiB }).code, "selected");
  assert.equal(R.validateFile({ name: "a.pdf", size: 10 * MiB + 1 }).code, "too_large");
  assert.equal(R.validateFile({ name: "a.pdf", size: 0 }).code, "empty");
  assert.equal(R.validateFile({ name: "a.docx", size: 5, type: "application/pdf" }).code, "extension");
  assert.equal(R.validateFile(null).code, "none");
});

/* 분석 결과 매핑 */
check("성공 응답 → 8개 항목, 미확인, 가상 보존, 상태 구분", () => {
  const d = R.validateAnalysis(analysisBody());
  assert.ok(d);
  const fs = R.createFieldsFromAnalysis(d);
  assert.deepEqual(fs.map((f) => f.key), R.FIELD_KEYS);
  const get = (k) => fs.find((f) => f.key === k);
  assert.ok(fs.every((f) => f.confirmed === false && f.source === "analysis"));
  assert.equal(get("product_name").provided, true);
  assert.equal(get("product_name").evidence[0].quote, XSS); // 문자열 그대로(HTML로 해석하지 않음, 렌더링은 textContent)
  const desc = get("description");
  assert.equal(desc.status, "unclear");
  assert.equal(desc.value, "AI가 확실히 읽지 못한 설명"); // unclear 값 보존
  assert.equal(desc.provided, false);
  assert.equal(desc.userAdded, false);                  // 사용자 추가로 표시하지 않음
  assert.equal(get("yarn_spec").status, "not_found");
  assert.equal(get("certification").virtual, true);     // 미제공 + 가상
  assert.equal(get("certification").sourceVirtual, true);
  assert.equal(get("moq").virtual, true);
  assert.equal(get("moq").evidence[0].pageInRange, false);
  const sample = get("sample");
  assert.deepEqual(sample.candidates, ["1 kg", "2 kg"]);
  assert.equal(sample.value, "");                       // 후보 중 하나를 확정값으로 채우지 않음
  assert.equal(sample.provided, false);
  assert.equal(get("lead_time").note, XSS);
  assert.equal(R.isDirty(fs), false);
});

check("unclear 값 수정은 사용자 수정, not_found 입력은 사용자 추가, 수정 시 확인 해제", () => {
  const fs = R.createFieldsFromAnalysis(R.validateAnalysis(analysisBody()));
  const desc = fs.find((f) => f.key === "description");
  R.setConfirmed(desc, true);
  R.setValue(desc, "수정한 설명");
  assert.equal(desc.confirmed, false);
  assert.equal(desc.userModified, true);
  assert.equal(desc.userAdded, false);
  const yarn = fs.find((f) => f.key === "yarn_spec");
  R.setValue(yarn, "150D/48F");
  assert.equal(yarn.userAdded, true);
  const moq = fs.find((f) => f.key === "moq");
  assert.equal(R.setVirtual(moq, false), false);       // AI가 가상으로 표시한 값은 해제 불가
  assert.equal(moq.virtual, true);
  assert.equal(R.summarize(fs).unclear, 2);
});

check("잘못된 성공 응답은 거부(부분 반영 없음)", () => {
  const mutate = (fn) => { const b = analysisBody(); fn(b); return R.validateAnalysis(b); };
  assert.equal(mutate((b) => b.data.fields.pop()), null);                                   // 7개
  assert.equal(mutate((b) => { b.data.fields[1] = Object.assign({}, b.data.fields[0]); }), null); // 중복 key
  assert.equal(mutate((b) => { b.data.fields[0].key = "price"; }), null);                   // 알 수 없는 key
  assert.equal(mutate((b) => { b.data.fields[0].status = "verified"; }), null);
  assert.equal(mutate((b) => { b.data.fields[0].confirmed = true; }), null);
  assert.equal(mutate((b) => { b.data.fields[0].evidence[0].page = "1"; }), null);
  assert.equal(mutate((b) => { delete b.data.extraction_status; }), null);
  assert.equal(mutate((b) => { b.data.review_notes = [{ source: "x", message: "m" }]; }), null);
  assert.equal(R.validateAnalysis({ ok: true }), null);
  assert.equal(R.validateAnalysis(null), null);
});

/* 응답 해석 */
check("실패 종류 구분과 안전한 안내", () => {
  assert.equal(R.interpretResponse({ networkError: true }).kind, "network");
  assert.equal(R.interpretResponse({ networkError: true, aborted: true }).kind, "timeout");
  assert.equal(R.interpretResponse({ status: 413, json: undefined }).kind, "too_large");
  const html = R.interpretResponse({ status: 500, json: undefined });
  assert.equal(html.kind, "not_json");
  assert.ok(!/</.test(html.message));
  const safe = R.interpretResponse({ status: 400, json: { ok: false, error: { code: "PDF_ENCRYPTED", message: "암호가 설정된 PDF는 지원하지 않습니다." } } });
  assert.equal(safe.kind, "server_error");
  assert.equal(safe.message, "암호가 설정된 PDF는 지원하지 않습니다.");
  const unsafe = R.interpretResponse({ status: 502, json: { ok: false, error: { code: "provider raw", message: "<b>RAW PROVIDER</b>" } } });
  assert.ok(!unsafe.message.includes("RAW PROVIDER"));
  assert.equal(R.interpretResponse({ status: 200, json: { ok: true, data: {} } }).kind, "invalid_response");
  assert.equal(R.interpretResponse({ status: 500, json: analysisBody() }).kind, "invalid_response");
  assert.equal(R.interpretResponse(ok(analysisBody())).ok, true);
});

/* 요청 실행기 */
function harness(opts) {
  const log = { sends: [], busy: [], success: [], failure: [], confirms: 0 };
  const deps = {
    send: (file) => { log.sends.push(file); return opts.send(file); },
    needsConfirm: () => !!opts.dirty,
    confirm: () => { log.confirms++; return opts.confirm !== false; },
    onBusy: (v) => log.busy.push(v),
    onSuccess: (d) => log.success.push(d),
    onFailure: (o) => log.failure.push(o),
  };
  return { a: R.createAnalyzer(deps), log: log };
}
const PDF = { name: "a.pdf", size: 100 };
function deferred() { let resolve; const p = new Promise((r) => { resolve = r; }); return { p, resolve }; }

check("정상 요청: send 1회, 진행 상태 on→off, 성공 콜백", async () => {
  const h = harness({ send: async () => ok(analysisBody()) });
  assert.equal(await h.a.run(PDF), "success");
  assert.deepEqual(h.log.sends, [PDF]);
  assert.deepEqual(h.log.busy, [true, false]);
  assert.equal(h.log.success.length, 1);
});

check("분석 중 중복 요청 방지", async () => {
  const d = deferred();
  const h = harness({ send: () => d.p });
  const first = h.a.run(PDF);
  assert.equal(h.a.isBusy(), true);
  assert.equal(await h.a.run(PDF), "busy");
  d.resolve(ok(analysisBody()));
  assert.equal(await first, "success");
  assert.equal(h.log.sends.length, 1);
  assert.equal(h.a.isBusy(), false);
});

check("교체 확인 취소 시 요청 0회·상태 변화 없음", async () => {
  const h = harness({ dirty: true, confirm: false, send: async () => ok(analysisBody()) });
  assert.equal(await h.a.run(PDF), "cancelled");
  assert.equal(h.log.confirms, 1);
  assert.equal(h.log.sends.length, 0);
  assert.deepEqual(h.log.busy, []);
});

check("교체 확인 승인 후에도 실패하면 성공 콜백 없음(기존 결과 유지)", async () => {
  const h = harness({ dirty: true, confirm: true, send: async () => ({ status: 502, json: { ok: false, error: { code: "AI_TIMEOUT", message: "시간 초과" } } }) });
  assert.equal(await h.a.run(PDF), "failure");
  assert.equal(h.log.success.length, 0);
  assert.equal(h.log.failure.length, 1);
  assert.deepEqual(h.log.busy, [true, false]);
});

check("잘못된 파일은 요청하지 않음", async () => {
  const h = harness({ send: async () => ok(analysisBody()) });
  assert.equal(await h.a.run({ name: "a.pdf", size: 10 * MiB + 1 }), "invalid");
  assert.equal(await h.a.run(null), "invalid");
  assert.equal(h.log.sends.length, 0);
});

check("send 예외는 네트워크 실패로 처리하고 다시 요청 가능(자동 재시도 없음)", async () => {
  let n = 0;
  const h = harness({ send: async () => { n++; if (n === 1) throw new Error("boom"); return ok(analysisBody()); } });
  assert.equal(await h.a.run(PDF), "failure");
  assert.equal(h.log.failure[0].kind, "network");
  assert.equal(n, 1);
  assert.equal(await h.a.run(PDF), "success");
  assert.equal(n, 2);
});

check("오래된 응답 무시", async () => {
  const d = deferred();
  const h = harness({ send: () => d.p });
  const first = h.a.run(PDF);
  h.a.invalidate();
  d.resolve(ok(analysisBody()));
  assert.equal(await first, "stale");
  assert.equal(h.log.success.length, 0);
  assert.equal(h.log.failure.length, 0);
  assert.deepEqual(h.log.busy, [true, false]);
});

/* 기존 예시 동작 */
check("예시: 8개 항목·가상 고정·수정 시 확인 해제·사용자 추가", () => {
  const fs = R.createFields(R.EXAMPLE_FIELDS);
  assert.equal(fs.length, 8);
  assert.ok(fs.every((f) => f.source === "example" && f.status === null));
  const moq = fs.find((f) => f.key === "moq");
  R.setConfirmed(moq, true);
  R.setValue(moq, "600 kg");
  assert.equal(moq.confirmed, false);
  assert.equal(moq.userModified, true);
  assert.equal(R.setVirtual(moq, false), false);
  const cert = fs.find((f) => f.key === "certification");
  R.setValue(cert, "GRS");
  assert.equal(cert.userAdded, true);
  assert.equal(R.isDirty(fs), true);
});

/* ---------- 카탈로그 생성 연결 ---------- */
function analysisFields() {
  return R.createFieldsFromAnalysis(R.validateAnalysis(analysisBody()));
}
function confirmAll(fs, keys) {
  keys.forEach((k) => R.setConfirmed(fs.find((f) => f.key === k), true));
}
// 확인된 카탈로그 표시명(가상 테스트 값)
const DN = { value: "regen T2T", confirmed: true };
function ctxOf(fs, snap, extra) {
  return Object.assign({ source: "analysis", snapshot: snap, version: 1, currentSignature: R.inputSignature(fs, DN), busy: false }, extra || {});
}
function copyOut(text, keys, virtual, flags) {
  return { text: text, source_keys: keys, virtual: !!virtual, origins: {}, review_flags: flags || [] };
}
function infoOut(key, value, virtual, flags) {
  return { key: key, label: key, value: value, source_keys: [key], virtual: !!virtual, origin: "extracted", review_flags: flags || [] };
}
function generationBody(over) {
  const data = {
    status: "draft_needs_review", language: "pt-BR", prompt_version: "brochure_generate_v2", model: "test-model",
    display_name: { value: "regen T2T", confirmed: true },
    notices: { unofficial: "Material demonstrativo — não é um catálogo oficial.", fictitious: "Condições fictícias para demonstração." },
    pages: {
      cover: { page: 1, product_name: copyOut("regen T2T", ["product_name"]), tagline: copyOut(XSS, ["description"]) },
      intro: { page: 2, paragraphs: [copyOut("Parágrafo.", ["description", "moq"], true, ["new_number"])] },
      details: { page: 3, items: [], empty: true, empty_message: "Informações técnicas a confirmar." },
      supply: { page: 4, items: [infoOut("moq", "500 kg", true)], empty: false, empty_message: null },
    },
    used_keys: ["product_name", "description", "moq"],
    excluded: [{ key: "sample", reason: "unconfirmed" }],
    input_meta: {},
  };
  return { ok: true, data: Object.assign(data, over || {}) };
}

check("origin 변환: 추출 / 사용자 수정 / 사용자 추가(재수정해도 유지)", () => {
  const fs = analysisFields();
  const get = (k) => fs.find((f) => f.key === k);
  assert.equal(R.originOf(get("product_name")), "extracted");
  R.setValue(get("description"), "수정한 설명");
  assert.equal(R.originOf(get("description")), "user_modified");
  R.setValue(get("yarn_spec"), "75D");
  assert.equal(R.originOf(get("yarn_spec")), "user_added");
  R.setValue(get("yarn_spec"), "75D/36F");
  assert.equal(R.originOf(get("yarn_spec")), "user_added"); // 다시 고쳐도 문서 추출로 바뀌지 않음
});

check("적용 스냅샷은 독립 복사본", () => {
  const fs = analysisFields();
  confirmAll(fs, ["product_name", "description"]);
  const snap = R.createSnapshot(fs, "analysis", 1, DN);
  R.setValue(fs[0], "다른 이름");
  assert.equal(snap.fields[0].value, "리젠 T2T");
  assert.ok(snap.fields.every((s, i) => s !== fs[i]));
  assert.deepEqual(Object.keys(snap.fields[0]).sort(), ["confirmed", "key", "origin", "value", "virtual"]);
});

check("생성 가능 조건: 예시·미적용·재적용 필요·필수 미확인·길이 초과·진행 중", () => {
  const ex = R.createFields(R.EXAMPLE_FIELDS);
  confirmAll(ex, ["product_name", "description"]);
  const exSnap = R.createSnapshot(ex, "example", 1, DN);
  assert.equal(R.evaluateGeneration(ctxOf(ex, exSnap, { source: "example" })).reason, "example");
  const fs = analysisFields();
  assert.equal(R.evaluateGeneration(ctxOf(fs, null)).reason, "not_applied");
  let snap = R.createSnapshot(fs, "analysis", 1, DN);
  assert.equal(R.evaluateGeneration(ctxOf(fs, snap)).reason, "required"); // 필수 미확인
  confirmAll(fs, ["product_name", "description"]);
  assert.equal(R.evaluateGeneration(ctxOf(fs, snap)).reason, "reapply"); // 확인 체크 변경 → 다시 적용 필요
  snap = R.createSnapshot(fs, "analysis", 1, DN);
  assert.equal(R.evaluateGeneration(ctxOf(fs, snap, { version: 2 })).reason, "not_applied"); // 새 분석·파일 교체 후
  assert.equal(R.evaluateGeneration(ctxOf(fs, snap, { busy: true })).reason, "busy");
  const ok = R.evaluateGeneration(ctxOf(fs, snap));
  assert.equal(ok.ok, true);
  assert.ok(ok.included.includes("product_name") && ok.included.includes("description"));
  assert.ok(ok.excluded.some((e) => e.key === "moq" && e.reason === "unconfirmed"));
  assert.ok(ok.excluded.some((e) => e.key === "yarn_spec" && e.reason === "empty"));
  R.setValue(fs.find((f) => f.key === "moq"), "x".repeat(201));
  confirmAll(fs, ["moq"]);
  const longSnap = R.createSnapshot(fs, "analysis", 1, DN);
  const tooLong = R.evaluateGeneration(ctxOf(fs, longSnap));
  assert.equal(tooLong.reason, "too_long");
  assert.deepEqual(tooLong.tooLong, ["moq"]);
  assert.equal(R.buildGeneratePayload(longSnap).fields.find((f) => f.key === "moq").value.length, 201); // 자르지 않음
});

check("생성 요청 본문: 8개 key·엄격 형식·추가 필드 없음", () => {
  const fs = analysisFields();
  confirmAll(fs, ["product_name", "description"]);
  const payload = R.buildGeneratePayload(R.createSnapshot(fs, "analysis", 1, DN));
  assert.deepEqual(Object.keys(payload), ["fields", "display_name"]);
  assert.deepEqual(payload.display_name, { value: "regen T2T", confirmed: true });
  assert.deepEqual(payload.fields.map((f) => f.key), R.FIELD_KEYS);
  payload.fields.forEach((f) => {
    assert.deepEqual(Object.keys(f).sort(), ["confirmed", "key", "origin", "value", "virtual"]);
    assert.equal(typeof f.confirmed, "boolean");
    assert.equal(typeof f.virtual, "boolean");
    assert.equal(typeof f.value, "string");
  });
  assert.equal(payload.fields.find((f) => f.key === "moq").virtual, true);
  assert.ok(!JSON.stringify(payload).includes("MOQ 500 kg")); // 근거 발췌 미포함
});

check("생성 응답 검사: 정상 통과, 잘못된 구조는 거부(부분 반영 없음)", () => {
  const d = R.validateGeneration(generationBody());
  assert.ok(d);
  assert.equal(d.pages.cover.tagline.text, XSS); // 문자열 그대로(렌더링은 textContent)
  const bad = (fn) => { const b = generationBody(); fn(b.data); return R.validateGeneration(b); };
  assert.equal(bad((x) => { x.status = "final"; }), null);
  assert.equal(bad((x) => { delete x.pages.supply; }), null);
  assert.equal(bad((x) => { x.pages.supply.items.push(infoOut("sample", "1 kg")); }), null);          // 사용하지 않은 key
  assert.equal(bad((x) => { x.pages.details.items = [infoOut("moq", "500 kg")]; x.pages.details.empty = false; x.pages.details.empty_message = null; }), null); // 다른 쪽 항목
  assert.equal(bad((x) => { x.pages.supply.items.push(infoOut("moq", "500 kg")); }), null);           // 중복
  assert.equal(bad((x) => { x.pages.details.empty = false; }), null);                                 // empty 불일치
  assert.equal(bad((x) => { x.pages.intro.paragraphs = []; }), null);
  assert.equal(bad((x) => { x.pages.intro.paragraphs = [1, 2, 3].map(() => copyOut("p", ["description"])); }), null);
  assert.equal(bad((x) => { x.pages.cover.tagline.source_keys = ["certification"]; }), null);
  assert.equal(bad((x) => { x.pages.cover.product_name.source_keys = ["description"]; }), null);
  assert.equal(bad((x) => { x.pages.supply.items[0].review_flags = "x"; }), null);
  assert.equal(bad((x) => { x.used_keys = ["moq"]; }), null);
  assert.equal(bad((x) => { x.notices = {}; }), null);
});

check("생성 실패 해석: 알려진 코드만 고정 안내, 원문·HTML 미표시, 과금 취소 보장 표현 없음", () => {
  const known = R.interpretGenerateResponse({ status: 502, json: { ok: false, error: { code: "GENERATE_OUTPUT_INVALID", message: "<b>SERVER RAW</b>" } } });
  assert.equal(known.code, "GENERATE_OUTPUT_INVALID");
  assert.ok(!known.message.includes("SERVER RAW"));
  const unknown = R.interpretGenerateResponse({ status: 500, json: { ok: false, error: { code: "X", message: "RAW" } } });
  assert.ok(!unknown.message.includes("RAW"));
  assert.equal(R.interpretGenerateResponse({ status: 500, json: undefined }).kind, "not_json");
  assert.equal(R.interpretGenerateResponse({ status: 413, json: undefined }).kind, "too_large");
  const timeout = R.interpretGenerateResponse({ networkError: true, aborted: true });
  assert.equal(timeout.kind, "timeout");
  assert.ok(timeout.message.includes("취소되었다는 뜻은 아닙니다"));
  assert.equal(R.interpretGenerateResponse({ status: 500, json: generationBody() }).kind, "invalid_response");
  assert.equal(R.interpretGenerateResponse({ status: 200, json: generationBody() }).ok, true);
});

function genHarness(opts) {
  const log = { sends: [], busy: [], success: [], failure: [], confirms: 0 };
  const g = R.createGenerator({
    send: (s) => { log.sends.push(s); return opts.send(s); },
    blocked: () => !!opts.blocked,
    canGenerate: () => opts.can !== false,
    needsConfirm: () => !!opts.hasResult,
    confirm: () => { log.confirms++; return opts.confirm !== false; },
    onBusy: (v) => log.busy.push(v),
    onSuccess: (d) => log.success.push(d),
    onFailure: (o) => log.failure.push(o),
  });
  return { g: g, log: log };
}
const SNAP = { fields: [] };

check("생성 실행기: 정상·조건 미충족·분석 중·재생성 취소는 요청 0회", async () => {
  const ok = genHarness({ send: async () => ({ status: 200, json: generationBody() }) });
  assert.equal(await ok.g.run(SNAP), "success");
  assert.equal(ok.log.sends.length, 1);
  assert.deepEqual(ok.log.busy, [true, false]);
  for (const [opts, expected] of [[{ can: false }, "invalid"], [{ blocked: true }, "blocked"], [{ hasResult: true, confirm: false }, "cancelled"]]) {
    const h = genHarness(Object.assign({ send: async () => ({ status: 200, json: generationBody() }) }, opts));
    assert.equal(await h.g.run(SNAP), expected);
    assert.equal(h.log.sends.length, 0);
    assert.deepEqual(h.log.busy, []);
  }
  assert.equal(await genHarness({ send: async () => ({}) }).g.run(null), "invalid"); // 스냅샷 없음
});

check("생성 실행기: 중복 클릭 방지, 실패 시 성공 콜백 없음, 오래된 응답 무시", async () => {
  const d = deferred();
  const h = genHarness({ send: () => d.p });
  const first = h.g.run(SNAP);
  assert.equal(await h.g.run(SNAP), "busy");
  d.resolve({ status: 502, json: { ok: false, error: { code: "AI_TIMEOUT", message: "x" } } });
  assert.equal(await first, "failure");
  assert.equal(h.log.success.length, 0);
  assert.equal(h.log.sends.length, 1);
  const d2 = deferred();
  const h2 = genHarness({ send: () => d2.p });
  const p = h2.g.run(SNAP);
  h2.g.invalidate();
  d2.resolve({ status: 200, json: generationBody() });
  assert.equal(await p, "stale");
  assert.equal(h2.log.success.length, 0);
});

check("이전 결과 판정과 검토 표시 설명", () => {
  const fs = analysisFields();
  confirmAll(fs, ["product_name", "description"]);
  const snap = R.createSnapshot(fs, "analysis", 1, DN);
  const result = { data: null, signature: snap.signature, version: 1 };
  assert.equal(R.isResultStale(result, ctxOf(fs, snap)), false);
  R.setValue(fs[1], "바뀐 설명");
  assert.equal(R.isResultStale(result, ctxOf(fs, snap)), true);     // 입력 수정
  assert.equal(R.isResultStale(result, { version: 2, currentSignature: snap.signature }), true); // 재분석·파일 교체
  assert.equal(R.isResultStale(null, ctxOf(fs, snap)), false);
  const flags = R.describeReviewFlags(R.validateGeneration(generationBody()));
  assert.deepEqual(flags.map((f) => f.where), ["2쪽 소개 문단 1"]);
  const withItemFlag = generationBody();
  withItemFlag.data.pages.supply.items[0].review_flags = ["number_not_preserved"];
  assert.equal(R.describeReviewFlags(withItemFlag.data)[1].where, "4쪽 MOQ"); // 내부 key 대신 항목 이름
});

/* ---------- 카탈로그 표시명 ---------- */
check("표시명 제안: 혼합 표기에서 명확한 라틴 표기만, 애매하면 비움, 특정 이름 강제 없음", () => {
  const s = R.suggestDisplayName("리젠 T2T (regen T2T)");
  assert.equal(s.value, "regen T2T");
  assert.equal(s.reason, "paren_latin");
  assert.equal(R.suggestDisplayName("EcoYarn® 75D").value, "EcoYarn® 75D");          // 라틴 표기만 → 그대로
  assert.equal(R.suggestDisplayName("Fio Têxtil Ação").value, "Fio Têxtil Ação");     // 악센트 허용
  assert.equal(R.suggestDisplayName("다른 원사 (Alpha Fiber)").value, "Alpha Fiber");  // regen T2T 강제 없음
  for (const ambiguous of ["리젠", "리젠 T2T", "리젠 ABC (regen T2T)", "폴리 원사 (A1) (B2)", "리젠 (재활용)"]) {
    const r = R.suggestDisplayName(ambiguous);
    assert.equal(r.value, "", ambiguous);                                             // 공식 영문명을 만들지 않음
  }
  assert.deepEqual(R.suggestDisplayName("리젠 T2T").candidates, ["T2T"]);
  assert.equal(R.suggestDisplayName("리젠").reason, "none");
  assert.equal(R.suggestDisplayName("폴리 원사 (A1) (B2)").reason, "ambiguous");
});

check("표시명 검사: 빈 값·한글 음절/자모·길이·제어 문자 차단, 악센트·숫자·기호 허용", () => {
  assert.equal(R.validateDisplayName("  ").reason, "empty");
  assert.equal(R.validateDisplayName("리젠").reason, "hangul");
  assert.equal(R.validateDisplayName("regen ㄱ").reason, "hangul");
  assert.equal(R.validateDisplayName("a".repeat(81)).reason, "too_long");
  assert.equal(R.validateDisplayName("a".repeat(80)).ok, true);
  assert.equal(R.validateDisplayName("x\u0007").reason, "control");
  for (const ok of ["regen T2T", "Fio Têxtil Ação 2.0", "EcoYarn® 75D/36F", "Alpha-Beta & Co. (PT)"]) {
    assert.equal(R.validateDisplayName(ok).ok, true, ok);
  }
});

check("표시명은 스냅샷·서명·생성 가능 판정·이전 결과 경고에 포함", () => {
  const fs = analysisFields();
  confirmAll(fs, ["product_name", "description"]);
  const unconfirmed = R.createSnapshot(fs, "analysis", 1, { value: "regen T2T", confirmed: false });
  assert.equal(R.evaluateGeneration(ctxOf(fs, unconfirmed, { currentSignature: R.inputSignature(fs, { value: "regen T2T", confirmed: false }) })).reason, "display_name");
  const hangul = { value: "리젠", confirmed: true };
  assert.equal(R.evaluateGeneration(ctxOf(fs, R.createSnapshot(fs, "analysis", 1, hangul), { currentSignature: R.inputSignature(fs, hangul) })).reason, "display_name");
  const snap = R.createSnapshot(fs, "analysis", 1, DN);
  assert.equal(R.evaluateGeneration(ctxOf(fs, snap)).ok, true);
  const dn = { value: "regen T2T", confirmed: true };
  const snap2 = R.createSnapshot(fs, "analysis", 1, dn);
  dn.value = "changed";                                                       // 원본 객체 변경
  assert.equal(snap2.displayName.value, "regen T2T");                         // 스냅샷 독립
  const changed = R.inputSignature(fs, { value: "regen T2T X", confirmed: false });
  assert.equal(R.evaluateGeneration(ctxOf(fs, snap, { currentSignature: changed })).reason, "reapply"); // 표시명 변경 → 재적용
  const result = { signature: snap.signature, version: 1 };
  assert.equal(R.isResultStale(result, { version: 1, currentSignature: changed }), true);              // 이전 결과 경고
  assert.equal(R.isResultStale(result, ctxOf(fs, snap)), false);
  assert.equal(R.buildGeneratePayload(R.createSnapshot(fs, "analysis", 1, { value: "  regen T2T  ", confirmed: true })).display_name.value, "regen T2T");
});

check("생성 응답 표시명 검사와 한글 잔존 오류 위치 안내", () => {
  const mismatch = generationBody();
  mismatch.data.pages.cover.product_name.text = "리젠 T2T (regen T2T)";
  assert.equal(R.validateGeneration(mismatch), null);                         // 표지 제품명 ≠ 표시명
  const noDn = generationBody();
  delete noDn.data.display_name;
  assert.equal(R.validateGeneration(noDn), null);
  const lang = R.interpretGenerateResponse({ status: 502, json: { ok: false, error: { code: "GENERATE_OUTPUT_LANGUAGE",
    message: "생성된 카탈로그 문구에 한국어가 남아 있어 결과를 표시하지 않았습니다. 위치: 1쪽 소개 문구, 4쪽 샘플 값, <b>원문</b>" } } });
  assert.ok(lang.message.includes("위치: 1쪽 소개 문구, 4쪽 샘플 값"));
  assert.ok(!lang.message.includes("원문"));                                  // 알려진 위치 형식만 표시
  assert.equal(R.describeReviewFlags({ pages: { cover: { tagline: copyOut("t", ["description"]) },
    intro: { paragraphs: [copyOut("p", ["description"], false, ["repeated_text"])] },
    details: { items: [] }, supply: { items: [] } } })[0].text, "표지 소개 문구와 거의 같은 내용이 반복됩니다");
});

/* ---------- 생성 결과 문구 편집 ---------- */
function editableBody() {
  const b = generationBody();
  b.data.pages.details = { page: 3, items: [infoOut("yarn_spec", "75D/36F", true, ["number_not_preserved"])], empty: false, empty_message: null };
  b.data.pages.supply.items[0].fictitious_notice = "Condições fictícias para demonstração.";
  b.data.used_keys = ["product_name", "description", "yarn_spec", "moq"];
  return R.validateGeneration(b);
}

check("편집 칸: 표시명·소개·문단·3/4쪽 값만(라벨·안내·메타데이터 제외), 서버 상한과 동일", () => {
  const d = editableBody();
  const entries = R.editableEntries(d);
  assert.deepEqual(entries.map((e) => e.id), ["display_name", "tagline", "paragraph:0", "detail:yarn_spec", "supply:moq"]);
  assert.deepEqual(entries.map((e) => e.limit), [80, 140, 600, 300, 200]);
  assert.deepEqual(entries.map((e) => e.where), ["1쪽 카탈로그 표시명", "1쪽 소개 문구", "2쪽 소개 문단 1", "3쪽 원사 규격 값", "4쪽 MOQ 값"]);
});

check("편집 적용: 원본·적용본·임시 값 독립, 텍스트만 변경, 메타데이터·고정 안내 보존, 표시명 일관", () => {
  const original = editableBody();
  const current = R.cloneData(original);
  const values = R.editValues(current);
  values.display_name = "  Regen T2T Fio  ";
  values["supply:moq"] = "500 kg por pedido";
  values["paragraph:0"] = "Linha 1\nLinha 2 com acentuação: ação, têxtil.";
  values.tagline = XSS + " editado";                                  // HTML 형태도 문자열로만 보관(원본과 다른 값)
  const r = R.applyEdits(original, current, values);
  assert.equal(r.ok, true);
  assert.notEqual(r.data, current);
  assert.equal(current.pages.supply.items[0].value, "500 kg");        // 적용본 원래 객체 불변
  assert.equal(original.pages.supply.items[0].value, "500 kg");       // AI 원본 불변
  values["supply:moq"] = "x";                                         // 임시 값 변경이 적용본에 영향 없음
  assert.equal(r.data.pages.supply.items[0].value, "500 kg por pedido");
  assert.equal(r.data.display_name.value, "Regen T2T Fio");
  assert.equal(r.data.pages.cover.product_name.text, "Regen T2T Fio");
  assert.equal(r.data.pages.cover.tagline.text, XSS + " editado");
  const item = r.data.pages.supply.items[0];
  assert.deepEqual([item.label, item.source_keys, item.origin, item.virtual, item.fictitious_notice],
    ["moq", ["moq"], "extracted", true, "Condições fictícias para demonstração."]);
  assert.deepEqual(r.data.pages.details.items[0].review_flags, ["number_not_preserved"]); // 원래 검토 표시 유지
  assert.deepEqual(r.data.pages.intro.paragraphs[0].review_flags, ["new_number"]);
  assert.deepEqual(r.data.notices, original.notices);
  assert.deepEqual(r.data.used_keys, original.used_keys);
  assert.deepEqual(r.editedIds, ["display_name", "tagline", "paragraph:0", "supply:moq"]);
  assert.deepEqual(R.describeUserEdits(r.data, r.editedIds).slice(-1), ["4쪽 MOQ 값"]);
});

check("편집 검증: 빈 값·공백·길이 초과·한글·제어 문자는 위치별 오류, 하나라도 틀리면 부분 적용 없음", () => {
  const original = editableBody();
  const current = R.cloneData(original);
  const bad = R.editValues(current);
  bad.tagline = "a".repeat(141);
  bad["paragraph:0"] = "   ";
  bad["detail:yarn_spec"] = "75D 원사";
  bad["supply:moq"] = "500\u0007kg";
  bad.display_name = "리젠";
  const r = R.applyEdits(original, current, bad);
  assert.equal(r.ok, false);
  assert.equal(r.data, undefined);
  assert.deepEqual(r.errors.map((e) => e.where), ["1쪽 카탈로그 표시명", "1쪽 소개 문구", "2쪽 소개 문단 1", "3쪽 원사 규격 값", "4쪽 MOQ 값"]);
  assert.ok(r.errors[1].message.includes("141자"));
  assert.equal(current.pages.cover.tagline.text, original.pages.cover.tagline.text); // 변경 없음
  const one = R.editValues(current);
  one["supply:moq"] = "500 kg";
  one.tagline = "ㅎ";                                                  // 자모만 있어도 거부
  assert.equal(R.applyEdits(original, current, one).ok, false);
  const exact = R.editValues(current);
  exact.tagline = "é".repeat(140);                                      // 경계값·악센트 허용
  assert.equal(R.applyEdits(original, current, exact).ok, true);
});

check("원문 복원·변경 감지: 원본과 같은 값이면 사용자 수정 아님, 임시 값 변경 감지", () => {
  const original = editableBody();
  const current = R.cloneData(original);
  const v = R.editValues(current);
  assert.equal(R.isEditDirty(current, v), false);
  v.tagline = "Outro texto.";
  assert.equal(R.isEditDirty(current, v), true);
  const edited = R.applyEdits(original, current, v).data;
  const back = R.editValues(edited);
  back.tagline = original.pages.cover.tagline.text;                   // 손으로 원래 문구로 되돌림
  assert.deepEqual(R.applyEdits(original, edited, back).editedIds, []);
  assert.deepEqual(R.editedIds(original, R.cloneData(original)), []); // 원문 복원 = 원본 복제
});

check("출력 편집은 입력 변경 경고와 별개: 편집해도 stale 아님, 입력이 바뀌면 stale 유지", () => {
  const fs = analysisFields();
  confirmAll(fs, ["product_name", "description"]);
  const snap = R.createSnapshot(fs, "analysis", 1, DN);
  const result = { signature: snap.signature, version: 1, original: editableBody(), current: editableBody(), editedIds: ["tagline"] };
  assert.equal(R.isResultStale(result, ctxOf(fs, snap)), false);       // 출력만 편집
  R.setValue(fs[1], "입력 변경");
  assert.equal(R.isResultStale(result, ctxOf(fs, snap)), true);        // 입력 변경 경고는 그대로
});

check("재생성 확인: 수정본이 있으면 대체 안내, 취소 시 요청 0회", async () => {
  const sends = [];
  let asked = null;
  const g = R.createGenerator({
    send: (s) => { sends.push(s); return Promise.resolve({ status: 200, json: generationBody() }); },
    blocked: () => false, canGenerate: () => true, needsConfirm: () => true,
    confirmMessage: () => R.REGENERATE_EDITED_MESSAGE,
    confirm: (m) => { asked = m; return false; },
    onBusy: () => {}, onSuccess: () => { throw new Error("호출 금지"); }, onFailure: () => {},
  });
  assert.equal(await g.run({ fields: [] }), "cancelled");
  assert.equal(asked, R.REGENERATE_EDITED_MESSAGE);
  assert.ok(asked.includes("직접 수정한 문구"));
  assert.equal(sends.length, 0);
});

/* ---------- 카탈로그 PDF 다운로드 ---------- */
function pdfOk(over) {
  return Object.assign({ status: 200, contentType: "application/pdf", size: 1000, head: "%PDF-", blob: { fake: true }, revision: 7 }, over || {});
}
function pdfHarness(opts) {
  const log = { sends: [], busy: [], success: [], failure: [], confirms: [] };
  const d = R.createPdfDownloader({
    send: (input) => { log.sends.push(input); return opts.send(input); },
    blocked: () => !!opts.blocked,
    needsConfirm: () => !!opts.stale,
    confirm: (m) => { log.confirms.push(m); return opts.confirm !== false; },
    onBusy: (v) => log.busy.push(v),
    onSuccess: (data) => log.success.push(data),
    onFailure: (o) => log.failure.push(o),
  });
  return { d: d, log: log };
}
function pdfInput(current, revision) {
  return { body: JSON.stringify(R.buildPdfPayload(current)), revision: revision === undefined ? 7 : revision };
}

check("PDF 요청 본문: 적용본의 허용 필드·가상 표시만(AI 원본·라벨·근거·검토 표시·메타데이터 제외)", () => {
  const original = editableBody();
  const values = R.editValues(original);
  values.tagline = "Texto aplicado & <editado>";
  values["supply:moq"] = "800 kg";
  const current = R.applyEdits(original, R.cloneData(original), values).data;
  const payload = R.buildPdfPayload(current);
  assert.deepEqual(Object.keys(payload), ["catalog"]);
  const c = payload.catalog;
  assert.deepEqual(Object.keys(c), ["language", "cover", "intro", "details", "supply"]);
  assert.equal(c.language, "pt-BR");
  assert.deepEqual(c.cover.tagline, { text: "Texto aplicado & <editado>", virtual: false }); // 적용본(원본 아님)
  assert.deepEqual(c.supply.items, [{ key: "moq", value: "800 kg", virtual: true }]);
  assert.deepEqual(c.intro.paragraphs, [{ text: "Parágrafo.", virtual: true }]);
  assert.deepEqual(c.details.items, [{ key: "yarn_spec", value: "75D/36F", virtual: true }]);
  const json = JSON.stringify(payload);
  for (const banned of ["label", "source_keys", "review_flags", "origin", "fictitious_notice", "notices", "model",
                        "display_name", "used_keys", "empty_message", "prompt_version"]) {
    assert.ok(!json.includes('"' + banned + '"'), banned);
  }
  current.pages.cover.tagline.text = "바뀜";                       // 요청 본문은 독립 복사본
  assert.equal(c.cover.tagline.text, "Texto aplicado & <editado>");
  const truthy = R.cloneData(current);
  truthy.pages.supply.items[0].virtual = "yes";                     // 불리언이 아닌 값은 true로 부풀리지 않음
  assert.equal(R.buildPdfPayload(truthy).catalog.supply.items[0].virtual, false);
});

check("PDF 가능 조건: 결과 없음·진행 중·미적용 편집·32 KiB 초과는 거부, 고정 안내", () => {
  const base = { hasResult: true, editDirty: false, busy: false, bodyBytes: 1000 };
  assert.equal(R.evaluatePdfDownload(base).ok, true);
  assert.equal(R.evaluatePdfDownload(Object.assign({}, base, { hasResult: false })).reason, "no_result");
  assert.equal(R.evaluatePdfDownload(Object.assign({}, base, { busy: true })).reason, "busy");
  const pending = R.evaluatePdfDownload(Object.assign({}, base, { editDirty: true }));
  assert.equal(pending.message, "문구를 적용하거나 편집을 취소한 뒤 다운로드하세요.");
  assert.equal(R.evaluatePdfDownload(Object.assign({}, base, { bodyBytes: 32 * 1024 })).ok, true);
  assert.equal(R.evaluatePdfDownload(Object.assign({}, base, { bodyBytes: 32 * 1024 + 1 })).reason, "too_large");
  assert.equal(R.utf8Bytes("ação"), 6);                              // 글자 수가 아닌 UTF-8 바이트
});

check("PDF 응답 해석: 정상만 통과, MIME·빈 파일·서명·HTML·JSON 오류·알 수 없는 코드 구분", () => {
  assert.equal(R.interpretPdfResponse(pdfOk()).ok, true);
  assert.equal(R.interpretPdfResponse(pdfOk({ contentType: "application/pdf; charset=binary" })).ok, true);
  assert.equal(R.interpretPdfResponse(pdfOk({ contentType: "application/octet-stream" })).ok, false);
  assert.equal(R.interpretPdfResponse(pdfOk({ size: 0 })).kind, "invalid_response");
  assert.equal(R.interpretPdfResponse(pdfOk({ head: "<html" })).kind, "invalid_response");
  assert.equal(R.interpretPdfResponse(pdfOk({ status: 201 })).ok, false);
  const html = R.interpretPdfResponse({ status: 502, contentType: "text/html", json: undefined });
  assert.equal(html.kind, "not_json");
  assert.ok(!html.message.includes("<"));
  const htmlOk = R.interpretPdfResponse({ status: 200, contentType: "text/html", json: undefined });
  assert.equal(htmlOk.kind, "invalid_response");
  const codes = { BROCHURE_PDF_INVALID_INPUT: 400, BROCHURE_PDF_BUSY: 429, BROCHURE_PDF_LAYOUT_OVERFLOW: 422,
    BROCHURE_PDF_GLYPH_MISSING: 422, BROCHURE_PDF_ASSET_UNAVAILABLE: 500, BROCHURE_PDF_RENDER_FAILED: 500,
    BROCHURE_PDF_INVALID_JSON: 400 };
  const messages = new Set();
  for (const [code, status] of Object.entries(codes)) {
    const out = R.interpretPdfResponse({ status: status, contentType: "application/json",
      json: { ok: false, error: { code: code, message: "3쪽 " + XSS } } });
    assert.equal(out.code, code);
    assert.equal(out.message, R.PDF_ERROR_MESSAGES[code]);            // 서버 원문 미표시
    assert.ok(!out.message.includes(XSS));
    messages.add(out.message);
  }
  assert.equal(messages.size, Object.keys(codes).length);            // 오류마다 다른 안내
  const big = R.interpretPdfResponse({ status: 413, contentType: "text/html" });
  assert.equal(big.code, "BROCHURE_PDF_REQUEST_TOO_LARGE");
  const unknown = R.interpretPdfResponse({ status: 500, contentType: "application/json", json: { ok: false, error: { code: "X", message: XSS } } });
  assert.equal(unknown.code, null);
  assert.ok(!unknown.message.includes(XSS));
  assert.equal(R.interpretPdfResponse({ networkError: true, aborted: true }).kind, "timeout");
  assert.ok(R.interpretPdfResponse({ networkError: true, aborted: true }).message.includes("멈췄다는 뜻은 아닙니다"));
  assert.equal(R.interpretPdfResponse({ networkError: true }).kind, "network");
});

check("PDF 실행기: 이전 결과 확인 취소·진행 중·크기 초과면 요청 0회", async () => {
  const current = editableBody();
  const cancel = pdfHarness({ stale: true, confirm: false, send: () => Promise.resolve(pdfOk()) });
  assert.equal(await cancel.d.run(pdfInput(current)), "cancelled");
  assert.deepEqual(cancel.log.confirms, [R.PDF_STALE_MESSAGE]);
  assert.equal(R.PDF_STALE_MESSAGE, "이 결과는 현재 입력과 다를 수 있습니다. 현재 미리보기 내용으로 PDF를 다운로드할까요?");
  assert.equal(cancel.log.sends.length, 0);
  const blocked = pdfHarness({ blocked: true, send: () => Promise.resolve(pdfOk()) });
  assert.equal(await blocked.d.run(pdfInput(current)), "blocked");
  assert.equal(blocked.log.sends.length, 0);
  const big = pdfHarness({ send: () => Promise.resolve(pdfOk()) });
  assert.equal(await big.d.run({ body: "x".repeat(32 * 1024 + 1), revision: 1 }), "invalid");
  assert.equal(big.log.sends.length, 0);
  const fresh = pdfHarness({ stale: false, send: () => Promise.resolve(pdfOk()) });
  assert.equal(await fresh.d.run(pdfInput(current)), "success");
  assert.equal(fresh.log.confirms.length, 0);                          // 이전 결과가 아니면 확인 없음
});

check("PDF 실행기: 정상 응답이면 성공 1회(blob·요청 당시 버전), 중복 클릭은 요청 1회", async () => {
  const gate = deferred();
  const h = pdfHarness({ send: (input) => gate.p.then(() => pdfOk({ revision: input.revision })) });
  const first = h.d.run(pdfInput(editableBody(), 3));
  assert.equal(await h.d.run(pdfInput(editableBody(), 3)), "busy");   // 중복 클릭
  gate.resolve();
  assert.equal(await first, "success");
  assert.equal(h.log.sends.length, 1);
  assert.equal(h.log.success.length, 1);
  assert.deepEqual(h.log.success[0], { blob: { fake: true }, revision: 3 });
  assert.deepEqual(h.log.busy, [true, false]);
});

check("PDF 실행기: 잘못된 응답·실패는 다운로드 없음, 실패 후 사용자가 다시 시도 가능(자동 재시도 없음)", async () => {
  const bad = [pdfOk({ head: "PK\u0003\u0004" }), pdfOk({ size: 0 }), pdfOk({ contentType: "text/html", json: undefined }),
    { status: 422, contentType: "application/json", json: { ok: false, error: { code: "BROCHURE_PDF_LAYOUT_OVERFLOW", message: "x" } } }];
  let n = 0;
  const h = pdfHarness({ send: () => Promise.resolve(bad[n++] || pdfOk()) });
  for (let i = 0; i < bad.length; i++) assert.equal(await h.d.run(pdfInput(editableBody())), "failure");
  assert.equal(h.log.success.length, 0);
  assert.equal(h.log.failure.length, bad.length);
  assert.equal(h.log.sends.length, bad.length);                        // 실패마다 요청 1회(재시도 없음)
  assert.equal(await h.d.run(pdfInput(editableBody())), "success");   // 사용자가 다시 누르면 요청
  const thrown = pdfHarness({ send: () => Promise.reject(new Error("net")) });
  assert.equal(await thrown.d.run(pdfInput(editableBody())), "failure");
  assert.equal(thrown.log.failure[0].kind, "network");
  const timeout = pdfHarness({ send: () => Promise.resolve({ networkError: true, aborted: true }) });
  assert.equal(await timeout.d.run(pdfInput(editableBody())), "failure");
  assert.equal(timeout.log.failure[0].kind, "timeout");
  assert.deepEqual(timeout.log.busy, [true, false]);                   // 잠금 해제
});

check("PDF 실행기: 무효화 뒤 도착한 오래된 응답은 무시", async () => {
  const gate = deferred();
  const h = pdfHarness({ send: () => gate.p.then(() => pdfOk()) });
  const pending = h.d.run(pdfInput(editableBody()));
  h.d.invalidate();
  gate.resolve();
  assert.equal(await pending, "stale");
  assert.equal(h.log.success.length + h.log.failure.length, 0);
});

// 사용자 보고(2026-10-26) 회귀: 생성 → 분석·검토 입력 수정(재적용 없음) → PDF 다운로드 시 이전 결과 확인창
// 화면과 같은 판정(isResultStale(generation, 현재 입력 서명))을 PDF 실행기의 needsConfirm에 연결해 흐름 전체를 확인
async function staleFlow(mutate) {
  const fs = analysisFields();
  confirmAll(fs, ["product_name", "description", "moq"]);
  const dn = { value: "regen T2T", confirmed: true };
  const snap = R.createSnapshot(fs, "analysis", 1, dn);
  const body = generationBody().data;
  const generation = { original: R.cloneData(body), current: R.cloneData(body), editedIds: [], signature: snap.signature, version: snap.version };
  mutate({ fs, dn, generation, get: (k) => fs.find((f) => f.key === k) });
  const ctx = () => ({ source: "analysis", snapshot: snap, version: 1, currentSignature: R.inputSignature(fs, dn), busy: false });
  const run = async (accept) => {
    const sends = [];
    const confirms = [];
    const d = R.createPdfDownloader({
      send: (input) => { sends.push(JSON.parse(input.body)); return Promise.resolve(pdfOk()); },
      needsConfirm: () => R.isResultStale(generation, ctx()),
      confirm: (m) => { confirms.push(m); return accept; },
      onBusy: () => {}, onSuccess: () => {}, onFailure: () => {},
    });
    const result = await d.run({ body: JSON.stringify(R.buildPdfPayload(R.cloneData(generation.current))), revision: 1 });
    return { result, sends, confirms };
  };
  return { stale: R.isResultStale(generation, ctx()), cancel: await run(false), accept: await run(true), generation };
}

check("이전 결과 확인(회귀): MOQ 단위만 수정·재적용 없음 → 확인창, 취소 0회·확인 1회(기존 적용본 그대로)", async () => {
  const r = await staleFlow(({ get }) => R.setValue(get("moq"), "500 kgs"));
  assert.equal(r.stale, true);
  assert.equal(r.cancel.result, "cancelled");
  assert.deepEqual(r.cancel.confirms, [R.PDF_STALE_MESSAGE]);
  assert.equal(r.cancel.sends.length, 0);
  assert.equal(r.accept.result, "success");
  assert.equal(r.accept.sends.length, 1);
  assert.equal(r.accept.sends[0].catalog.supply.items[0].value, "500 kg"); // 검토 화면의 수정값을 결과에 몰래 반영하지 않음
});

check("이전 결과 확인(회귀): 제품 설명·표시명·확인 해제·가상 표시 변경도 감지, 결과 문구 편집만은 감지 안 함", async () => {
  const cases = {
    description: ({ get }) => R.setValue(get("description"), "설명 변경(가상)"),
    display_name: ({ dn }) => { dn.value = "regen T2T X"; },
    display_confirm: ({ dn }) => { dn.confirmed = false; },
    unconfirm: ({ get }) => R.setConfirmed(get("moq"), false),
    virtual: ({ get }) => R.setVirtual(get("description"), true),
    revert_value: ({ get }) => { R.setValue(get("moq"), "500 kgs"); R.setValue(get("moq"), "500 kg"); }, // 값은 같아도 확인이 해제됨
  };
  for (const [name, mutate] of Object.entries(cases)) {
    const r = await staleFlow(mutate);
    assert.equal(r.stale, true, name);
    assert.equal(r.cancel.sends.length, 0, name);
    assert.equal(r.accept.sends.length, 1, name);
  }
  const edited = await staleFlow(({ generation }) => {
    const values = R.editValues(generation.current);
    values["supply:moq"] = "800 kg";
    const out = R.applyEdits(generation.original, generation.current, values);
    generation.current = out.data;
    generation.editedIds = out.editedIds;
  });
  assert.equal(edited.stale, false);                                    // 출력 편집만으로 입력 불일치 경고 없음
  assert.deepEqual(edited.accept.confirms, []);
  assert.equal(edited.accept.sends[0].catalog.supply.items[0].value, "800 kg"); // 적용된 수정본 사용
});

check("화면 항목명: 3·4쪽 고정 pt-BR 표시명(AI 라벨 대신, PDF와 같은 값)", () => {
  assert.deepEqual(Object.keys(R.CATALOG_ITEM_LABELS).sort(),
    ["carbon_reduction", "certification", "lead_time", "moq", "sample", "yarn_spec"]);
  assert.equal(R.CATALOG_ITEM_LABELS.moq, "Pedido mínimo (MOQ)");
  assert.equal(R.PDF_FILENAME, "fionex_catalog_pt-BR.pdf");
});

/* ---------- AI 표지 배경 ---------- */
const PNG_HEAD = "\u0089PNG\r\n\u001a\n";
function coverOk(over) {
  return Object.assign({ status: 200, contentType: "image/png", size: 5000, head: PNG_HEAD, decoded: true,
    width: 1024, height: 1536, blob: { fake: "png" }, payload: { display_name: "regen T2T", description: "설명", mood: "minimal" },
    infoSignature: "sig" }, over || {});
}
function coverHarness(opts) {
  const log = { sends: [], busy: [], success: [], failure: [] };
  const g = R.createCoverGenerator({
    send: (input) => { log.sends.push(input); return opts.send(input); },
    blocked: () => !!opts.blocked,
    needsConfirm: () => false, confirm: () => true,
    onBusy: (v) => log.busy.push(v),
    onSuccess: (d) => log.success.push(d),
    onFailure: (o) => log.failure.push(o),
  });
  return { g: g, log: log };
}
function coverInput(mood) {
  const payload = { display_name: "regen T2T", description: "설명", mood: mood || "minimal" };
  return { payload: payload, infoSignature: R.coverInfoSignature(payload.display_name, payload.description) };
}

check("표지 생성 조건: 카탈로그 생성과 같은 판정(예시·미적용·재적용 필요·확인 누락 거부)", () => {
  const fs = analysisFields();
  confirmAll(fs, ["product_name", "description"]);
  const snap = R.createSnapshot(fs, "analysis", 1, DN);
  assert.equal(R.evaluateCover(ctxOf(fs, snap)).ok, true);
  assert.equal(R.evaluateCover(Object.assign(ctxOf(fs, snap), { source: "example" })).reason, "example");
  assert.equal(R.evaluateCover(ctxOf(fs, null)).reason, "not_applied");
  assert.equal(R.evaluateCover(ctxOf(fs, snap, { busy: true })).reason, "busy");
  R.setValue(fs.find((f) => f.key === "description"), "다른 설명");
  assert.equal(R.evaluateCover(ctxOf(fs, snap)).reason, "reapply");          // 적용 후 입력 변경 → 재적용 안내
  const fs2 = analysisFields();
  confirmAll(fs2, ["product_name"]);                                          // 설명 미확인
  assert.equal(R.evaluateCover(ctxOf(fs2, R.createSnapshot(fs2, "analysis", 1, DN))).reason, "required");
  const fs3 = analysisFields();
  confirmAll(fs3, ["product_name", "description"]);
  const noDn = { value: "regen T2T", confirmed: false };
  const s3 = R.createSnapshot(fs3, "analysis", 1, noDn);
  assert.equal(R.evaluateCover(Object.assign(ctxOf(fs3, s3), { currentSignature: R.inputSignature(fs3, noDn) })).reason, "display_name");
});

check("표지 요청 본문: 적용 스냅샷의 표시명·설명과 분위기 3개만(검토 화면 이후 수정값 미반영)", () => {
  const fs = analysisFields();
  confirmAll(fs, ["product_name", "description"]);
  const snap = R.createSnapshot(fs, "analysis", 1, { value: "  regen T2T  ", confirmed: true });
  R.setValue(fs.find((f) => f.key === "description"), "적용 뒤 바꾼 설명");
  const p = R.buildCoverPayload(snap, "premium");
  assert.deepEqual(Object.keys(p).sort(), ["description", "display_name", "mood"]);
  assert.equal(p.display_name, "regen T2T");
  assert.equal(p.description, R.createSnapshot(analysisFields(), "analysis", 1, DN).fields.find((f) => f.key === "description").value.trim());
  assert.equal(p.mood, "premium");
  assert.notEqual(R.coverInfoSignature("a", "b"), R.coverInfoSignature("a", "c"));
});

check("표지 응답 해석: 정상 PNG만 통과, 크기·형식·디코딩·해상도·HTML·JSON 오류 구분(서버 원문 미표시)", () => {
  assert.equal(R.interpretCoverResponse(coverOk()).ok, true);
  const bad = [coverOk({ contentType: "image/jpeg" }), coverOk({ size: 0 }), coverOk({ head: "GIF89a\u0000\u0000" }),
    coverOk({ decoded: false }), coverOk({ width: 1024, height: 1024 }), coverOk({ tooLarge: true }),
    coverOk({ size: 16 * 1024 * 1024 + 1 }), coverOk({ status: 201 })];
  bad.forEach((r, i) => assert.equal(R.interpretCoverResponse(r).ok, false, String(i)));
  assert.ok(R.interpretCoverResponse(coverOk({ size: 16 * 1024 * 1024 + 1 })).message.includes("16 MiB"));
  assert.ok(R.interpretCoverResponse(coverOk({ width: 1536, height: 1024 })).message.includes("1024×1536"));
  assert.equal(R.interpretCoverResponse(coverOk({ size: 16 * 1024 * 1024 })).ok, true);   // 경계값
  const html = R.interpretCoverResponse({ status: 502, contentType: "text/html", json: undefined });
  assert.equal(html.kind, "not_json");
  assert.equal(R.interpretCoverResponse({ status: 200, contentType: "text/html" }).kind, "invalid_response");
  for (const code of ["COVER_IMAGE_INVALID_INPUT", "AI_RATE_LIMITED", "AI_IMAGE_INVALID", "AI_CONFIG_MISSING", "AI_REFUSED"]) {
    const out = R.interpretCoverResponse({ status: 400, contentType: "application/json", json: { ok: false, error: { code, message: XSS } } });
    assert.equal(out.code, code);
    assert.equal(out.message, R.COVER_ERROR_MESSAGES[code]);
    assert.ok(!out.message.includes(XSS));
  }
  const unknown = R.interpretCoverResponse({ status: 500, contentType: "application/json", json: { ok: false, error: { code: "X", message: XSS } } });
  assert.equal(unknown.code, null);
  assert.ok(!unknown.message.includes(XSS));
  assert.equal(R.interpretCoverResponse({ status: 413, contentType: "text/html" }).code, "COVER_IMAGE_REQUEST_TOO_LARGE");
  const to = R.interpretCoverResponse({ networkError: true, aborted: true });
  assert.equal(to.kind, "timeout");
  assert.ok(to.message.includes("과금되지 않았다는 뜻은 아닙니다"));
});

check("표지 실행기: 3필드 외·빈 값·잘못된 분위기 요청 0회, 중복 클릭 1회, 실패 후 재시도 가능, 오래된 응답 무시", async () => {
  const h = coverHarness({ send: () => Promise.resolve(coverOk()) });
  for (const bad of [{ payload: { display_name: "a", description: "b", mood: "dark" } },
                     { payload: { display_name: "a", description: "b", mood: "minimal", extra: 1 } },
                     { payload: { display_name: "", description: "b", mood: "minimal" } }, null]) {
    assert.equal(await h.g.run(bad), "invalid");
  }
  assert.equal(h.log.sends.length, 0);
  const blocked = coverHarness({ blocked: true, send: () => Promise.resolve(coverOk()) });
  assert.equal(await blocked.g.run(coverInput()), "blocked");
  assert.equal(blocked.log.sends.length, 0);
  const gate = deferred();
  const d = coverHarness({ send: (input) => gate.p.then(() => coverOk({ payload: input.payload, infoSignature: input.infoSignature })) });
  const first = d.g.run(coverInput("soft_texture"));
  assert.equal(await d.g.run(coverInput("soft_texture")), "busy");
  gate.resolve();
  assert.equal(await first, "success");
  assert.equal(d.log.sends.length, 1);
  assert.equal(d.log.success[0].payload.mood, "soft_texture");
  assert.deepEqual(d.log.busy, [true, false]);
  let n = 0;
  const f = coverHarness({ send: () => Promise.resolve(n++ ? coverOk() : { networkError: true, aborted: true }) });
  assert.equal(await f.g.run(coverInput()), "failure");                // 시간 초과: 자동 재시도 없음
  assert.equal(f.log.sends.length, 1);
  assert.equal(await f.g.run(coverInput()), "success");                // 사용자가 다시 누르면 요청
  const late = deferred();
  const s = coverHarness({ send: () => late.p.then(() => coverOk()) });
  const pending = s.g.run(coverInput());
  s.g.invalidate();
  late.resolve();
  assert.equal(await pending, "stale");
  assert.equal(s.log.success.length, 0);
});

check("표지 object URL 수명: 후보·적용이 같은 URL이면 유지, 교체·버리기·복원 때 안 쓰는 URL만 해제", () => {
  const a = { url: "blob:a" }, b = { url: "blob:b" };
  assert.deepEqual(R.coverUrlsToRevoke({ candidate: a, applied: null }, { candidate: a, applied: a }), []);  // 적용
  assert.deepEqual(R.coverUrlsToRevoke({ candidate: a, applied: a }, { candidate: null, applied: a }), []); // 적용한 후보 버리기
  assert.deepEqual(R.coverUrlsToRevoke({ candidate: a, applied: a }, { candidate: b, applied: a }), []);    // 새 후보, 적용 유지
  assert.deepEqual(R.coverUrlsToRevoke({ candidate: b, applied: a }, { candidate: null, applied: a }), ["blob:b"]);
  assert.deepEqual(R.coverUrlsToRevoke({ candidate: b, applied: a }, { candidate: b, applied: null }), ["blob:a"]); // 복원
  assert.deepEqual(R.coverUrlsToRevoke({ candidate: a, applied: a }, { candidate: null, applied: null }), ["blob:a"]); // 중복 해제 없음
  assert.deepEqual(R.coverUrlsToRevoke({ candidate: a, applied: null }, { candidate: b, applied: null }), ["blob:a"]);
});

check("PDF 다운로드: 적용한 AI 표지가 있으면 고정 안내로 차단, 후보만 있으면 허용", () => {
  const base = { hasResult: true, editDirty: false, busy: false, bodyBytes: 100 };
  const blocked = R.evaluatePdfDownload(Object.assign({}, base, { coverApplied: true }));
  assert.equal(blocked.reason, "cover_applied");
  assert.equal(blocked.message, "AI 표지 배경의 PDF 반영은 연결 준비 중입니다. 기본 배경으로 복원하면 다운로드할 수 있습니다.");
  assert.equal(R.evaluatePdfDownload(Object.assign({}, base, { coverApplied: false })).ok, true);
});

(async () => {
  let failed = 0;
  for (const [name, fn] of checks) {
    try { await fn(); console.log("ok - " + name); }
    catch (e) { failed++; console.log("FAIL - " + name + "\n  " + (e && e.message)); }
  }
  console.log(checks.length - failed + "/" + checks.length + " checks passed");
  process.exit(failed ? 1 : 0);
})();
