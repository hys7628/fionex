/* 브라우저 DOM 회귀. browser_cover_server.py에서만 주입, 제품 코드에서 로드하지 않음.
   AI는 서버 가상 fixture, PDF는 실제 API. 사용자의 자료/실제 AI 호출 없음. */
(async function () {
  "use strict";
  const panel = document.querySelector('[data-feature-panel="product_brochure"]');
  const q = (s) => panel.querySelector(s);
  const checks = [], requests = [], downloads = [], revokes = [], dialogs = [];
  const fetchReal = window.fetch.bind(window);
  const nativeConfirm = window.confirm;
  let accept = true, mode = "normal", release = null;
  const delay = (n) => new Promise((r) => setTimeout(r, n));
  async function wait(fn) {
    for (let i = 0; i < 400; i++) { if (fn()) return; await delay(50); }
    throw new Error("Timed out waiting for browser state");
  }
  function check(ok, name) { if (!ok) throw new Error(name); checks.push(name); }
  function click(s) { const e = q(s); if (!e || e.disabled) throw new Error("Unavailable: " + s); e.click(); }
  function input(s, value) { const e = q(s); e.value = value; e.dispatchEvent(new Event("input", { bubbles: true })); }
  window.confirm = (message) => { dialogs.push(message); return accept; };
  const revoke = URL.revokeObjectURL.bind(URL);
  URL.revokeObjectURL = (url) => { revokes.push(url); revoke(url); };
  const download = AppShell.work.downloadBlob;
  AppShell.work.downloadBlob = (id, blob, name) => {
    downloads.push({ size: blob.size, name });
    download(id, blob, name); // 실제 브라우저 다운로드 경로 유지
  };
  window.fetch = async (url, init) => {
    if (url !== "/api/product-brochure/pdf") return fetchReal(url, init);
    const row = { multipart: init.body instanceof FormData, headers: init.headers };
    if (row.multipart) {
      row.keys = [...init.body.keys()];
      row.name = init.body.get("cover_image").name;
      row.image = [...new Uint8Array(await init.body.get("cover_image").arrayBuffer())];
      row.catalog = JSON.parse(init.body.get("catalog"));
    } else row.catalog = JSON.parse(await init.body.text());
    requests.push(row);
    if (mode === "delay") await new Promise((r) => { release = r; });
    if (mode === "error") return new Response(JSON.stringify({ ok: false, error: { code: "BROCHURE_PDF_COVER_INVALID", message: "UNTRUSTED" } }), { status: 400, headers: { "Content-Type": "application/json" } });
    return fetchReal(url, init);
  };
  const coverSrc = () => q('[data-result-dialog] .catalog-cover-figure img').src;
  const heading = () => q('[data-cover-candidate-heading]').textContent;
  const bytes = async (url) => [...new Uint8Array(await (await fetchReal(url)).arrayBuffer())];
  async function pdf() {
    const n = requests.length, d = downloads.length;
    click('[data-pdf-download]');
    await wait(() => requests.length === n + 1 && !q('[data-pdf-download]').disabled);
    check(downloads.length === d + 1, "PDF downloaded " + (d + 1));
    check(AppShell.work.get("product_brochure").hasDraft, "Leave protection after download " + (d + 1));
  }
  async function generateCover() {
    const prev = q('[data-cover-candidate-img]').src;
    click('[data-cover-generate]');
    await wait(() => q('[data-cover-candidate-img]').src !== prev && !q('[data-cover-generate]').disabled);
    return q('[data-cover-candidate-img]').src;
  }
  try {
    AppShell.show("product_brochure");
    const dt = new DataTransfer();
    dt.items.add(new File(["%PDF-1.4 MOCK"], "synthetic.pdf", { type: "application/pdf" }));
    q('input[type=file]').files = dt.files;
    q('input[type=file]').dispatchEvent(new Event("change", { bubbles: true }));
    click('[data-analyze]');
    await wait(() => q('#product_brochure-confirm-description'));
    for (const key of ["product_name", "description", "moq"]) click('#product_brochure-confirm-' + key);
    input('#product_brochure-display-name', "regen T2T");
    click('#product_brochure-display-name-confirm');
    click('[data-apply]');
    click('[data-generate]');
    await wait(() => !q('[data-result-open]').disabled);
    const original = coverSrc();
    const otherImages = () => [...q('[data-result-dialog]').querySelectorAll('img')].slice(1).map((x) => x.src).join('|');
    const unchanged = otherImages();
    await pdf();
    check(!requests[0].multipart, "Default JSON regression");
    const a = await generateCover();
    check(heading() === "생성 후보" && coverSrc() === original, "Candidate is unapplied");
    click('[data-cover-apply]');
    check(heading() === "현재 표지에 적용된 이미지" && coverSrc() === a, "Apply A and heading");
    check(!q('[data-pdf-status]').textContent.includes("다운로드 요청됨"), "Apply invalidates previous download");
    const aBytes = await bytes(a);
    const b = await generateCover();
    check(heading() === "생성 후보" && coverSrc() === a, "New B leaves A applied");
    await pdf();
    check(JSON.stringify(requests[1].image) === JSON.stringify(aBytes), "Applied A sent, not candidate B");
    check(requests[1].name === "cover.png" && requests[1].keys.join() === "catalog,cover_image", "Multipart field and filename contract");
    check(!Object.keys(requests[1].headers).some((k) => k.toLowerCase() === "content-type"), "Browser chooses multipart boundary");
    click('[data-cover-apply]');
    check(coverSrc() === b && revokes.includes(a), "Replace A with B releases unused A");
    await pdf();
    check(JSON.stringify(requests[2].image) === JSON.stringify(await bytes(b)), "Replacement B sent");
    check(otherImages() === unchanged, "Pages 2-4 preview unchanged");

    mode = "error";
    const n = requests.length, d = downloads.length;
    click('[data-pdf-download]');
    await wait(() => requests.length === n + 1 && !q('[data-pdf-download]').disabled);
    check(downloads.length === d && !q('[data-pdf-error]').hidden, "Error does not download");
    check(!q('[data-pdf-error]').textContent.includes("UNTRUSTED") && coverSrc() === b && q('[data-cover-candidate-img]').src === b, "Failure preserves images and hides raw error");
    await delay(150);
    check(requests.length === n + 1, "No automatic retry");

    mode = "delay";
    click('[data-pdf-download]');
    await wait(() => release);
    check(['[data-cover-apply]', '[data-cover-restore]', '[data-cover-generate]', '[data-cover-discard]', '[data-result-open]', '[data-generate]', '[data-apply]'].every((s) => q(s).disabled), "PDF locks image and result changes");
    const pendingCount = requests.length;
    q('[data-pdf-download]').disabled = false;
    q('[data-pdf-download]').click();
    check(requests.length === pendingCount, "Forced duplicate click blocked");
    release(); release = null;
    await wait(() => downloads.length === d + 1);
    mode = "normal";

    input('#product_brochure-field-description', "Changed synthetic description");
    const beforeCancel = requests.length, beforeDialogs = dialogs.length;
    accept = false;
    click('[data-pdf-download]');
    await delay(100);
    check(requests.length === beforeCancel && dialogs.length === beforeDialogs + 1, "Input plus image stale uses one dialog; cancel zero requests");
    accept = true;
    await pdf();
    check(dialogs.length === beforeDialogs + 2, "Accept stale uses one dialog");

    click('[data-cover-restore]');
    check(coverSrc() === original && heading() === "생성 후보" && !revokes.includes(b), "Restore retains candidate and correct heading");
    await pdf();
    check(!requests[requests.length - 1].multipart, "Restore returns to JSON");
    click('[data-cover-discard]');
    check(q('[data-cover-candidate]').hidden && !q('[data-cover-candidate-img]').hasAttribute('src') && revokes.includes(b), "Discard releases last URL and clears hidden src");
    check(AppShell.work.get("product_brochure").hasDraft, "Leave protection retained at end");
    click('[data-result-open]');
    await fetchReal('/qa/report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ok: true, checks, requestCount: requests.length, downloads, dialogs, revoked: revokes.length }) });
    document.title = "PASS " + checks.length + " - fionex cover QA";
  } catch (error) {
    document.title = "FAIL - fionex cover QA";
    await fetchReal('/qa/report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ok: false, checks, error: String(error), stack: error.stack }) });
  } finally {
    window.fetch = fetchReal;
    window.confirm = nativeConfirm;
    AppShell.work.downloadBlob = download;
  }
})();
