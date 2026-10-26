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

(async () => {
  let failed = 0;
  for (const [name, fn] of checks) {
    try { await fn(); console.log("ok - " + name); }
    catch (e) { failed++; console.log("FAIL - " + name + "\n  " + (e && e.message)); }
  }
  console.log(checks.length - failed + "/" + checks.length + " checks passed");
  process.exit(failed ? 1 : 0);
})();
