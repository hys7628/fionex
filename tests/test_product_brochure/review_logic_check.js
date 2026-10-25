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

(async () => {
  let failed = 0;
  for (const [name, fn] of checks) {
    try { await fn(); console.log("ok - " + name); }
    catch (e) { failed++; console.log("FAIL - " + name + "\n  " + (e && e.message)); }
  }
  console.log(checks.length - failed + "/" + checks.length + " checks passed");
  process.exit(failed ? 1 : 0);
})();
