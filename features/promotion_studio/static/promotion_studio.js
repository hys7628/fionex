// 홍보 스튜디오 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
// 현재 구현: 콘티 입력 검증(서버 service.validate_input과 같은 규칙), 텍스트 콘티 생성 요청과 결과 표시.
(function () {
  "use strict";

  const FEATURE_ID = "promotion_studio";
  const panel = document.querySelector('[data-feature-panel="' + FEATURE_ID + '"]');
  if (!panel) return;
  const form = panel.querySelector("[data-ps-form]");
  if (!form) return;

  const LIMITS = JSON.parse(form.dataset.psLimits);
  const DOC_EXT = JSON.parse(form.dataset.psDocExt);
  const IMAGE_EXT = JSON.parse(form.dataset.psImageExt);
  const MB = 1024 * 1024;

  const LABELS = {
    audience: "대상",
    description: "제품 설명",
    purposes: "홍보 목적",
    purpose_other: "홍보 목적 기타",
    cta: "CTA",
    tone: "홍보 톤",
    tone_other: "홍보 톤 기타",
    duration: "영상 길이",
    scene_count: "장면 수",
    aspect_ratio: "화면 비율",
    image_style: "이미지 스타일",
    image_style_other: "이미지 스타일 기타",
    max_wait_seconds: "최대 대기 시간",
    documents: "보조 문서",
    photos: "제품 사진",
    logo: "로고",
    logo_scope: "로고 적용 범위",
  };
  // 아직 손대지 않은 필수 항목은 오류 대신 요약에만 표시합니다.
  const touched = new Set();
  // 파일별 서명 검사 결과(이미지 확장자와 내용 일치 여부). 파일 객체 → true/false
  const signatureOk = new WeakMap();

  function el(name) { return form.elements.namedItem(name); }
  function text(name) { const f = el(name); return f && !f.disabled ? f.value.trim() : ""; }
  function checked(name) {
    return Array.from(form.querySelectorAll('input[name="' + name + '"]:checked:not(:disabled)')).map(function (i) { return i.value; });
  }
  function ext(filename) { const i = filename.lastIndexOf("."); return i < 0 ? "" : filename.slice(i).toLowerCase(); }
  function files(name) { return Array.from(el(name).files || []); }
  function sizeText(bytes) { return bytes >= MB ? (bytes / MB).toFixed(1) + "MB" : Math.max(1, Math.round(bytes / 1024)) + "KB"; }

  // ---------- 서명 검사(파일 앞 12바이트) ----------
  function readHead(file) {
    return file.slice(0, 12).arrayBuffer().then(function (buf) { return new Uint8Array(buf); });
  }
  function imageSignatureOk(extension, b) {
    if (extension === ".png") return b.length >= 8 && b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47 && b[4] === 0x0d && b[5] === 0x0a && b[6] === 0x1a && b[7] === 0x0a;
    if (extension === ".jpg" || extension === ".jpeg") return b.length >= 3 && b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff;
    if (extension === ".webp") {
      const s = String.fromCharCode.apply(null, Array.from(b));
      return s.slice(0, 4) === "RIFF" && s.slice(8, 12) === "WEBP";
    }
    return false;
  }
  function checkSignatures(list) {
    return Promise.all(list.map(function (file) {
      const e = ext(file.name);
      if (IMAGE_EXT.indexOf(e) < 0 || file.size === 0 || signatureOk.has(file)) return null;
      return readHead(file).then(function (b) { signatureOk.set(file, imageSignatureOk(e, b)); })
        .catch(function () { signatureOk.set(file, false); });
    }));
  }

  // ---------- 검증 ----------
  function checkFiles(errors, name, allowed, maxFiles, maxFileBytes, image) {
    const list = files(name);
    if (list.length > maxFiles) errors.push([name, LABELS[name] + "은(는) 최대 " + maxFiles + "개까지 올릴 수 있습니다."]);
    let total = 0;
    list.forEach(function (file) {
      total += file.size;
      const e = ext(file.name);
      if (allowed.indexOf(e) < 0) errors.push([name, file.name + ": 지원하지 않는 형식입니다."]);
      else if (file.size === 0) errors.push([name, file.name + ": 빈 파일입니다."]);
      else if (file.size > maxFileBytes) errors.push([name, file.name + ": 파일당 " + maxFileBytes / MB + "MB 이하만 올릴 수 있습니다."]);
      else if (image && signatureOk.get(file) === false) errors.push([name, file.name + ": 확장자와 파일 내용이 맞지 않습니다."]);
    });
    return total;
  }

  function otherText(errors, name) {
    const v = text(name);
    if (!v) errors.push([name, LABELS[name] + " 내용을 입력하세요."]);
    else if (v.length > LIMITS.other_max_chars) errors.push([name, LABELS[name] + "은(는) " + LIMITS.other_max_chars + "자 이하로 입력하세요."]);
  }

  function validate() {
    const errors = [];
    if (!checked("audience").length) errors.push(["audience", "대상을(를) 선택하세요."]);

    const description = text("description");
    if (!description) errors.push(["description", "제품 설명을 입력하세요."]);
    else if (description.length > LIMITS.description_max_chars) errors.push(["description", "제품 설명은 " + LIMITS.description_max_chars.toLocaleString() + "자 이하로 입력하세요."]);

    const purposes = checked("purposes");
    if (!purposes.length) errors.push(["purposes", "홍보 목적을 1개 이상 선택하세요."]);
    else if (purposes.length > LIMITS.purpose_max) errors.push(["purposes", "홍보 목적은 최대 " + LIMITS.purpose_max + "개까지 선택할 수 있습니다."]);
    if (purposes.indexOf("other") >= 0) otherText(errors, "purpose_other");

    if (text("cta").length > LIMITS.cta_max_chars) errors.push(["cta", "CTA는 " + LIMITS.cta_max_chars + "자 이하로 입력하세요."]);

    const tone = checked("tone");
    if (!tone.length) errors.push(["tone", "홍보 톤을(를) 선택하세요."]);
    else if (tone[0] === "other") otherText(errors, "tone_other");

    if (!checked("duration").length) errors.push(["duration", "영상 길이를 선택하세요."]);
    const scenes = Number(el("scene_count").value);
    if (!Number.isInteger(scenes) || scenes < LIMITS.scene_min || scenes > LIMITS.scene_max) {
      errors.push(["scene_count", "장면 수는 " + LIMITS.scene_min + "~" + LIMITS.scene_max + "개 중에서 선택하세요."]);
    }
    if (!checked("aspect_ratio").length) errors.push(["aspect_ratio", "화면 비율을(를) 선택하세요."]);
    const style = checked("image_style");
    if (!style.length) errors.push(["image_style", "이미지 스타일을(를) 선택하세요."]);
    else if (style[0] === "other") otherText(errors, "image_style_other");

    const waitRaw = text("max_wait_seconds");
    const wait = Number(waitRaw);
    if (!/^\d+$/.test(waitRaw) || wait < LIMITS.wait_min_seconds || wait > LIMITS.wait_max_seconds) {
      errors.push(["max_wait_seconds", "최대 대기 시간은 " + LIMITS.wait_min_seconds + "~" + LIMITS.wait_max_seconds + "초 사이의 정수로 입력하세요."]);
    }

    const docTotal = checkFiles(errors, "documents", DOC_EXT, LIMITS.doc_max_files, LIMITS.doc_max_file_bytes, false);
    if (docTotal > LIMITS.doc_max_total_bytes) errors.push(["documents", "보조 문서 합계는 " + LIMITS.doc_max_total_bytes / MB + "MB 이하여야 합니다."]);
    const photoTotal = checkFiles(errors, "photos", IMAGE_EXT, LIMITS.photo_max_files, LIMITS.image_max_file_bytes, true);
    const logoTotal = checkFiles(errors, "logo", IMAGE_EXT, LIMITS.logo_max_files, LIMITS.image_max_file_bytes, true);
    if (photoTotal + logoTotal > LIMITS.image_max_total_bytes) errors.push(["photos", "제품 사진과 로고 합계는 " + LIMITS.image_max_total_bytes / MB + "MB 이하여야 합니다."]);
    if (files("logo").length && !checked("logo_scope").length) errors.push(["logo_scope", "로고 적용 범위을(를) 선택하세요."]);
    return errors;
  }

  // ---------- 화면 반영 ----------
  function render() {
    const errors = validate();
    const byField = {};
    errors.forEach(function (e) { (byField[e[0]] = byField[e[0]] || []).push(e[1]); });

    panel.querySelectorAll("[data-ps-error]").forEach(function (box) {
      const name = box.dataset.psError;
      const messages = touched.has(name) ? byField[name] || [] : [];
      box.textContent = messages.join(" ");
      box.hidden = !messages.length;
      const control = form.querySelector("#" + FEATURE_ID + "-" + name);
      const group = control ? [control] : Array.from(form.querySelectorAll('input[name="' + name + '"]'));
      group.forEach(function (c) {
        if (messages.length) c.setAttribute("aria-invalid", "true");
        else c.removeAttribute("aria-invalid");
      });
    });

    const summary = panel.querySelector("[data-ps-summary]");
    const summaryText = panel.querySelector("[data-ps-summary-text]");
    const names = Object.keys(byField);
    if (!names.length) {
      summary.className = "notice notice-success";
      summaryText.textContent = "콘티 생성에 필요한 입력이 준비되었습니다.";
    } else {
      summary.className = "notice notice-info";
      summaryText.textContent = "확인할 항목 " + names.length + "개: " + names.map(function (n) { return LABELS[n]; }).join(", ");
    }
  }

  function syncOther(choiceName, otherName) {
    const box = panel.querySelector('[data-ps-other="' + otherName + '"]');
    const on = checked(choiceName).indexOf("other") >= 0;
    box.hidden = !on;
    el(otherName).disabled = !on; // 비활성 입력은 제출·작성 중 감지에서 빠집니다.
  }

  function syncLogoScope() {
    const box = panel.querySelector("[data-ps-logo-scope]");
    const on = files("logo").length > 0;
    box.hidden = !on;
    box.querySelectorAll("input").forEach(function (i) { i.disabled = !on; });
  }

  function syncCounter(name) {
    const counter = panel.querySelector('[data-ps-counter="' + name + '"]');
    if (counter) counter.textContent = el(name).value.length.toLocaleString();
  }

  function syncFileList(name) {
    const list = panel.querySelector('[data-ps-file-list="' + name + '"]');
    const selected = files(name);
    // 목록을 다시 그리면 버튼이 교체되므로, 초점이 있던 × 버튼 위치를 기억해 복원합니다.
    const focused = list.contains(document.activeElement) ? document.activeElement.dataset.psRemoveIndex : null;
    list.replaceChildren.apply(list, selected.map(function (file, index) {
      const li = document.createElement("li");
      li.className = "ps-file-item";
      const label = document.createElement("span");
      label.textContent = file.name + " (" + sizeText(file.size) + ")";
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "btn btn-ghost ps-file-remove";
      remove.textContent = "×";
      remove.dataset.psRemoveFile = name;
      remove.dataset.psRemoveIndex = String(index);
      remove.setAttribute("aria-label", file.name + " 첨부 해제");
      remove.title = "첨부 해제(컴퓨터의 원본 파일은 삭제되지 않습니다)";
      li.append(label, remove);
      return li;
    }));
    list.hidden = !selected.length;
    if (focused !== null) {
      const again = list.querySelector('[data-ps-remove-index="' + focused + '"]');
      (again || el(name)).focus();
    }
  }

  // 선택한 파일 하나만 첨부에서 뺍니다. 파일 입력은 목록 일부 삭제를 지원하지 않아 나머지 파일로 목록을 다시 만듭니다.
  // 브라우저는 선택 목록만 바꾸며 컴퓨터의 원본 파일에는 접근하지 않습니다.
  function removeFile(name, index) {
    const input = el(name);
    const keep = new DataTransfer();
    files(name).forEach(function (file, i) { if (i !== index) keep.items.add(file); });
    input.files = keep.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));  // 검증·목록·작성 중 감지·PDF 안내를 기존 경로로 갱신
    const next = panel.querySelector('[data-ps-remove-file="' + name + '"][data-ps-remove-index="' + Math.min(index, keep.files.length - 1) + '"]');
    (next || input).focus();
  }

  panel.addEventListener("click", function (event) {
    const button = event.target.closest("[data-ps-remove-file]");
    if (!button) return;
    removeFile(button.dataset.psRemoveFile, Number(button.dataset.psRemoveIndex));
  });

  function syncAll() {
    syncOther("purposes", "purpose_other");
    syncOther("tone", "tone_other");
    syncOther("image_style", "image_style_other");
    syncLogoScope();
    ["description", "cta"].forEach(syncCounter);
    ["documents", "photos", "logo"].forEach(syncFileList);
    AppShell.work.recheckInputs(FEATURE_ID); // 코드로 바꾼 disabled 상태를 작성 중 감지에 반영
    render();
  }

  form.addEventListener("input", function (event) {
    if (event.target.dataset.psCount) syncCounter(event.target.dataset.psCount);
    render();
    syncStale();
  });
  form.addEventListener("change", function (event) {
    const name = event.target.name;
    if (name) touched.add(name);
    if (event.target.dataset.psFile) {
      checkSignatures(files(name)).then(syncAll);
    }
    syncAll();
    syncStale();
    syncPdf();
    syncImageGen();  // 제품 사진이 바뀌면 장면 이미지 생성 가능 여부를 갱신합니다.
  });
  form.addEventListener("focusout", function (event) {
    if (event.target.name && event.target.type !== "file") {
      touched.add(event.target.name);
      render();
    }
  });
  form.addEventListener("reset", function () {
    touched.clear();
    setTimeout(function () { syncAll(); syncStale(); }, 0);
  });

  // ---------- 콘티 생성 ----------
  const API_URL = "/api/promotion-studio/storyboard";
  const submitBtn = form.querySelector("[data-ps-submit]");
  const cancelBtn = form.querySelector("[data-ps-cancel]");
  const resultCard = panel.querySelector("[data-ps-result-card]");
  const busyBox = panel.querySelector("[data-ps-busy]");
  const errorBox = panel.querySelector("[data-ps-error-box]");
  const errorText = panel.querySelector("[data-ps-error-text]");
  const staleBox = panel.querySelector("[data-ps-stale]");
  const emptyBox = panel.querySelector("[data-ps-empty]");
  const resultBox = panel.querySelector("[data-ps-result]");
  const errorTitle = panel.querySelector("[data-ps-error-title]");
  const pdfBtn = panel.querySelector("[data-ps-pdf]");
  const pdfEdition = panel.querySelector("[data-ps-pdf-edition]");
  const pdfHint = panel.querySelector("[data-ps-pdf-hint]");

  let lastResult = null;       // PDF 요청에 다시 보내는 현재 결과(페이지 메모리에만 보관)
  let pdfBusy = false;
  let sceneImages = {};        // 장면 번호 → {blob, url, cost}. 페이지 메모리에만 보관
  let imageBusy = false;
  let imageController = null;
  let controller = null;       // 진행 중 요청. 동시에 하나만 보냅니다.
  let requestSeq = 0;          // 취소·시간 초과 뒤 늦게 온 응답을 버리기 위한 번호
  let resultSignature = null;  // 현재 결과를 만든 입력 조건

  // 입력 조건 비교용 문자열. 파일은 이름·크기만 비교합니다(내용을 읽지 않음).
  function formSignature() {
    return JSON.stringify(Array.from(new FormData(form).entries()).map(function (pair) {
      const v = pair[1];
      return [pair[0], typeof v === "string" ? v : v.name + ":" + v.size];
    }));
  }

  function syncStale() {
    staleBox.hidden = resultSignature === null || resultSignature === formSignature();
  }

  function setBusy(on) {
    submitBtn.disabled = on;
    cancelBtn.hidden = !on;
    busyBox.hidden = !on;
    if (on) resultCard.setAttribute("aria-busy", "true");
    else resultCard.removeAttribute("aria-busy");
    syncPdf();
    syncImageGen();
  }

  function showError(message, title) {
    errorTitle.textContent = title || "콘티를 만들지 못했습니다";
    errorText.textContent = message;
    errorBox.hidden = false;
  }

  // PDF는 시간 합계가 맞는 결과가 있을 때만 만들 수 있습니다(feature_spec.md 7장).
  function syncPdf() {
    const ready = lastResult !== null && lastResult.timing.ok;
    pdfBtn.disabled = !ready || pdfBusy || controller !== null || imageBusy;
    pdfEdition.disabled = !ready;
    pdfBtn.textContent = pdfBusy ? "PDF 만드는 중…" : "PDF 다운로드";
    if (lastResult === null) pdfHint.textContent = "콘티를 생성하면 PDF로 내려받을 수 있습니다.";
    else if (!ready) pdfHint.textContent = "장면 시간 합계가 영상 길이와 달라 PDF를 만들 수 없습니다. 콘티를 다시 생성하세요.";
    else {
      const made = Object.keys(sceneImages).length;
      pdfHint.textContent = "PDF는 표지·장면별 페이지·확인 필요 사항으로 구성되며, 올린 로고는 표지에 넣습니다. " +
        (files("photos").length ? (made ? "생성한 장면 이미지 " + made + "장을 넣고, " : "") +
          "이미지가 없는 장면은 PDF 다운로드 때 AI 생성 또는 첨부 사진 중 고른 방법으로 채웁니다." :
          (made ? "생성한 장면 이미지 " + made + "장을 해당 장면 페이지에 넣습니다." :
            "제품 사진을 첨부하면 장면 이미지 칸을 채울 수 있습니다. 지금은 이미지 칸이 비어 있는 텍스트 PDF입니다."));
    }
  }

  function fileNameOf(res) {
    const m = /filename="?([^";]+)"?/.exec(res.headers.get("Content-Disposition") || "");
    return m ? m[1] : "promotion_storyboard.pdf";
  }

  // usePhotos: AI 이미지가 없는 장면 칸에 첨부 제품 사진을 넣습니다(사진이 있을 때).
  async function downloadPdf(usePhotos) {
    if (!lastResult || pdfBusy) return;
    pdfBusy = true;
    errorBox.hidden = true;
    pdfChoice.hidden = true;
    syncPdf();
    const body = new FormData();
    body.append("storyboard", JSON.stringify(lastResult));
    body.append("edition", pdfEdition.value);
    const logo = files("logo")[0];
    if (logo) body.append("logo", logo);
    Object.keys(sceneImages).forEach(function (n) {
      body.append("scene_images", sceneImages[n].blob, "scene_image_" + n + ".png");
    });
    if (usePhotos === true && files("photos").length) {
      body.append("use_photos", "1");
      files("photos").forEach(function (f) { body.append("photos", f); });
    }
    try {
      const res = await fetch("/api/promotion-studio/pdf", { method: "POST", body: body });
      if (res.ok && (res.headers.get("Content-Type") || "").indexOf("application/pdf") === 0) {
        AppShell.work.downloadBlob(FEATURE_ID, await res.blob(), fileNameOf(res));
      } else {
        let data = null;
        try { data = await res.json(); } catch (e) { data = null; }
        showError(data && data.error ? data.error.message : "PDF를 만들지 못했습니다. 잠시 후 다시 시도하세요.", "PDF를 만들지 못했습니다");
      }
    } catch (err) {
      showError("서버에 연결하지 못했습니다. 앱 서버가 실행 중인지 확인한 뒤 다시 시도하세요.", "PDF를 만들지 못했습니다");
    } finally {
      pdfBusy = false;
      syncPdf();
    }
  }
  // PDF 버튼: 제품 사진이 있고 AI 이미지가 없는 장면이 있으면 이미지 칸 채우는 방법을 먼저 묻습니다.
  const pdfChoice = panel.querySelector("[data-ps-pdf-choice]");
  const pdfChoiceText = panel.querySelector("[data-ps-pdf-choice-text]");
  pdfBtn.addEventListener("click", function () {
    const missing = missingScenes();
    const photos = files("photos").length;
    if (!photos || !missing.length) {
      downloadPdf(photos > 0);
      return;
    }
    const estimate = IMAGE_INFO.estimated_usd === null ? "예상 비용 미실측" :
      "약 $" + (IMAGE_INFO.estimated_usd * missing.length).toFixed(3) + " 추정(참조 사진 1장·low 실측 기준, 실제 청구와 다를 수 있음)";
    pdfChoiceText.textContent = "이미지가 없는 장면 " + missing.length + "개(장면 " + missing.join(", ") + ")가 있습니다. " +
      "AI 생성: 첨부 사진 " + photos + "장을 참고해 장면별 이미지를 만든 뒤 PDF를 받습니다(장당 약 20초, " + estimate +
      "). 실패한 장면에는 첨부 사진을 넣습니다. 첨부 사진: 요금 없이 올린 사진을 장면 순서대로 넣습니다.";
    pdfChoice.hidden = false;
    panel.querySelector("[data-ps-pdf-choice-ai]").focus();
  });
  panel.querySelector("[data-ps-pdf-choice-ai]").addEventListener("click", async function () {
    pdfChoice.hidden = true;
    if (await generateImages(missingScenes())) downloadPdf(true);
  });
  panel.querySelector("[data-ps-pdf-choice-photo]").addEventListener("click", function () { downloadPdf(true); });
  panel.querySelector("[data-ps-pdf-choice-cancel]").addEventListener("click", function () {
    pdfChoice.hidden = true;
    pdfBtn.focus();
  });

  // ---------- 장면 이미지 생성(첨부 제품 사진 참고) ----------
  const imageGen = panel.querySelector("[data-ps-image-gen]");
  const IMAGE_INFO = JSON.parse(imageGen.dataset.psImageInfo);
  const imageStart = panel.querySelector("[data-ps-image-start]");
  const imageStop = panel.querySelector("[data-ps-image-stop]");
  const imageHint = panel.querySelector("[data-ps-image-hint]");
  const imageStatus = panel.querySelector("[data-ps-image-status]");
  const imageConfirm = panel.querySelector("[data-ps-image-confirm]");
  const imageConfirmText = panel.querySelector("[data-ps-image-confirm-text]");

  function missingScenes() {
    return lastResult ? lastResult.scenes.map(function (s) { return s.number; }).filter(function (n) { return !sceneImages[n]; }) : [];
  }

  function clearSceneImages() {
    Object.keys(sceneImages).forEach(function (n) { URL.revokeObjectURL(sceneImages[n].url); });
    sceneImages = {};
    imageStatus.textContent = "";
    imageConfirm.hidden = true;
  }

  function syncImageGen() {
    imageGen.hidden = lastResult === null;
    if (lastResult === null) return;
    const photos = files("photos").length;
    const missing = missingScenes().length;
    imageStart.disabled = imageBusy || controller !== null || pdfBusy || !photos || !missing;
    imageStart.textContent = Object.keys(sceneImages).length && missing ? "남은 장면 이미지 생성" : "장면 이미지 생성";
    imageStop.hidden = !imageBusy;
    if (!photos) imageHint.textContent = "장면 이미지는 첨부한 제품 사진을 반드시 참고해 만듭니다. 콘티 조건에서 제품 사진을 1장 이상 첨부하세요.";
    else if (!missing) imageHint.textContent = "모든 장면 이미지가 준비되었습니다. 다시 만들려면 콘티를 다시 생성하세요.";
    else imageHint.textContent = "첨부한 제품 사진 " + photos + "장을 매 장면 참고해 이미지를 만듭니다. 생성 전에 장수와 예상 비용을 확인합니다.";
  }

  function costText(usd) { return usd === null || usd === undefined ? "미확인" : "$" + usd.toFixed(3); }

  imageStart.addEventListener("click", function () {
    const missing = missingScenes();
    const size = IMAGE_INFO.sizes[lastResult.conditions.aspect_ratio];
    const estimate = IMAGE_INFO.estimated_usd === null ? "장당 예상 비용은 아직 실측 전입니다(생성 후 장면별 사용 토큰 기준 추정액을 표시)." :
      "장당 약 $" + IMAGE_INFO.estimated_usd.toFixed(3) + ", 합계 약 $" + (IMAGE_INFO.estimated_usd * missing.length).toFixed(3) + "(참조 사진 1장·low 품질 실측 1회 기준 추정, 사진이 많을수록 입력 비용이 늘어남).";
    imageConfirmText.textContent = "장면 " + missing.length + "개의 이미지를 만듭니다(장면 " + missing.join(", ") + "). 첨부 사진 " +
      files("photos").length + "장을 매 장면 참고하며 품질 " + IMAGE_INFO.quality + ", 크기 " + size + "입니다. " + estimate +
      " 실제 청구액과 다를 수 있고, 중지해도 이미 보낸 요청은 과금될 수 있습니다.";
    imageConfirm.hidden = false;
    panel.querySelector("[data-ps-image-confirm-yes]").focus();
  });
  panel.querySelector("[data-ps-image-confirm-no]").addEventListener("click", function () {
    imageConfirm.hidden = true;
    imageStart.focus();
  });
  panel.querySelector("[data-ps-image-confirm-yes]").addEventListener("click", function () {
    imageConfirm.hidden = true;
    generateImages(missingScenes());
  });
  imageStop.addEventListener("click", function () { if (imageController) imageController.abort(); });

  function b64ToBlob(b64, type) {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Blob([bytes], { type: type });
  }

  function showSceneImage(number, data) {
    const area = resultBox.querySelector('[data-ps-scene-image="' + number + '"]');
    if (!area) return;
    if (data.error) {
      const msg = node("p", "field-error", "이미지 생성 실패: " + data.error + " '남은 장면 이미지 생성'으로 다시 시도할 수 있습니다.");
      area.replaceChildren(msg);
      return;
    }
    const img = node("img", "ps-scene-img");
    img.src = data.url;
    img.style.aspectRatio = lastResult.conditions.aspect_ratio.replace(":", " / ");
    img.alt = "장면 " + number + " AI 생성 이미지(첨부 제품 사진 참고)";
    area.replaceChildren(img, node("p", "field-hint",
      "AI 생성 이미지 · 첨부 사진 " + data.references + "장 참고 · 실제 제품 외형과 다를 수 있어 검토가 필요합니다. 추정 비용 " + costText(data.cost)));
  }

  async function generateImages(numbers) {
    imageBusy = true;
    imageController = new AbortController();
    errorBox.hidden = true;
    syncImageGen();
    syncPdf();
    submitBtn.disabled = true;
    let done = 0;
    let failed = 0;
    let total = 0;
    const conditions = lastResult.conditions;
    const style = conditions.image_style_code ? conditions : { image_style_code: "photo", image_style: "실사형" };
    let stopped = false;
    try {
      for (const number of numbers) {
        imageStatus.textContent = "장면 " + number + " 이미지 생성 중… (" + (done + failed + 1) + "/" + numbers.length + ")";
        const scene = lastResult.scenes[number - 1];
        const body = new FormData();
        body.append("scene", JSON.stringify({
          visual_pt: scene.visual_pt, camera_pt: scene.camera_pt, aspect_ratio: conditions.aspect_ratio,
          image_style_code: style.image_style_code, image_style: style.image_style,
        }));
        files("photos").forEach(function (f) { body.append("photos", f); });
        let res;
        try {
          res = await fetch("/api/promotion-studio/scene-image", { method: "POST", body: body, signal: imageController.signal });
        } catch (err) {
          if (imageController.signal.aborted) break;
          showSceneImage(number, { error: "서버에 연결하지 못했습니다." });
          failed++;
          continue;
        }
        let data = null;
        try { data = await res.json(); } catch (e) { data = null; }
        if (data && data.ok) {
          const blob = b64ToBlob(data.data.image_base64, data.data.mime_type);
          sceneImages[number] = { blob: blob, url: URL.createObjectURL(blob), cost: data.data.estimated_cost_usd };
          showSceneImage(number, { url: sceneImages[number].url, references: data.data.reference_count, cost: data.data.estimated_cost_usd });
          if (typeof data.data.estimated_cost_usd === "number") total += data.data.estimated_cost_usd;
          done++;
        } else {
          showSceneImage(number, { error: data && data.error ? data.error.message : "알 수 없는 오류입니다." });
          failed++;
          // 설정·인증·사진 누락처럼 모든 장면에 같은 오류가 날 경우는 멈춥니다.
          if (data && data.error && /CONFIG|AUTH|PERMISSION|PHOTO|MODEL_UNAVAILABLE/.test(data.error.code)) break;
        }
      }
    } finally {
      stopped = imageController.signal.aborted;
      imageStatus.textContent = (stopped ? "중지했습니다. " : "") + "생성 " + done + "장, 실패 " + failed + "장. " +
        "사용 토큰 기준 추정 합계 $" + total.toFixed(3) + "(실제 청구와 다를 수 있음)." +
        (stopped ? " 중지 직전 보낸 요청은 과금될 수 있습니다." : "");
      imageBusy = false;
      imageController = null;
      submitBtn.disabled = false;
      syncImageGen();
      syncPdf();
    }
    return !stopped;  // 사용자가 중지하면 false
  }

  // 모델 출력은 textContent로만 넣습니다(HTML로 해석하지 않음).
  function node(tag, className, value) {
    const n = document.createElement(tag);
    if (className) n.className = className;
    if (value !== undefined) n.textContent = value;
    return n;
  }

  function clock(sec) { return Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0"); }

  const SCENE_ROWS = [
    ["화면 설명", "visual"],
    ["카메라 구도·움직임", "camera"],
    ["자막", "subtitle"],
    ["내레이션", "narration"],
  ];

  function sceneCard(scene) {
    const article = node("article", "ps-scene");
    const head = node("div", "ps-scene-head");
    head.append(
      node("h3", "ps-scene-title", "장면 " + scene.number),
      node("span", "badge badge-info",
        clock(scene.start_seconds) + "–" + clock(scene.end_seconds) + " · " + scene.duration_seconds + "초")
    );
    const table = node("table", "table ps-scene-table");
    table.append(node("caption", "visually-hidden", "장면 " + scene.number + " 구성"));
    const headRow = node("tr");
    ["항목", "포르투갈어", "한국어 검토본"].forEach(function (t) {
      const th = node("th", "", t);
      th.scope = "col";
      headRow.append(th);
    });
    const thead = node("thead");
    thead.append(headRow);
    const tbody = node("tbody");
    SCENE_ROWS.forEach(function (row) {
      const tr = node("tr");
      const th = node("th", "", row[0]);
      th.scope = "row";
      tr.append(th, node("td", "", scene[row[1] + "_pt"] || "없음"), node("td", "", scene[row[1] + "_ko"] || "없음"));
      tbody.append(tr);
    });
    table.append(thead, tbody);
    const wrap = node("div", "table-wrap");
    wrap.append(table);
    const imageArea = node("div", "ps-scene-image");
    imageArea.dataset.psSceneImage = String(scene.number);
    imageArea.append(node("p", "field-hint", "이미지: 아직 생성하지 않았습니다. 제품 사진을 첨부한 뒤 '장면 이미지 생성'을 누르세요."));
    article.append(head, imageArea, wrap);
    return article;
  }

  function renderResult(data) {
    const parts = [];

    const header = node("div", "ps-result-head");
    header.append(node("p", "ps-result-title", data.title_pt), node("p", "field-hint", "한국어 검토본: " + data.title_ko));
    const meta = node("div", "ps-choices");
    const c = data.conditions;
    [c.audience, c.duration + "초", "장면 " + c.scene_count + "개", c.aspect_ratio].forEach(function (t) {
      meta.append(node("span", "badge badge-info", t));
    });
    header.append(meta);
    parts.push(header);

    if (!data.timing.ok) {
      const warn = node("div", "notice notice-warning");
      warn.append(node("p", "notice-title", "장면 시간 합계 확인 필요"),
        node("p", "", "장면 길이 합계가 " + data.timing.total_seconds + "초로, 선택한 영상 길이 " +
          data.timing.expected_seconds + "초와 다릅니다. 다시 생성하세요."));
      parts.push(warn);
    }
    data.notices.forEach(function (msg) {
      const info = node("div", "notice notice-info");
      info.append(node("p", "", msg));
      parts.push(info);
    });

    data.scenes.forEach(function (scene) { parts.push(sceneCard(scene)); });

    const review = node("div", "notice notice-warning");
    review.append(node("p", "notice-title", "확인 필요 사항"));
    if (data.review_notes.length) {
      const ul = node("ul", "ps-review-list");
      data.review_notes.forEach(function (t) { ul.append(node("li", "", t)); });
      review.append(ul);
    } else {
      review.append(node("p", "", "AI가 표시한 항목은 없습니다. 수치·인증·친환경 주장은 근거 자료로 직접 확인하세요."));
    }
    parts.push(review);
    parts.push(node("p", "field-hint",
      "AI 생성 결과이며 사실 확인의 근거가 아닙니다. 번역 의미와 제품 정보는 담당자가 검토하세요. (" +
      data.model + " · " + data.prompt_version + ")"));

    resultBox.replaceChildren.apply(resultBox, parts);
    resultBox.hidden = false;
    emptyBox.hidden = true;
  }

  function focusFirstError() {
    const box = Array.from(panel.querySelectorAll("[data-ps-error]")).find(function (b) { return !b.hidden; });
    if (!box) return;
    const name = box.dataset.psError;
    const control = form.querySelector("#" + FEATURE_ID + "-" + name) ||
      form.querySelector('[name="' + name + '"]:not(:disabled)');
    if (control) control.focus();
  }

  async function generate() {
    const seq = ++requestSeq;
    const waitSeconds = Number(text("max_wait_seconds"));
    const signature = formSignature();
    let abortReason = null;
    controller = new AbortController();
    const timer = setTimeout(function () { abortReason = "timeout"; controller.abort(); }, waitSeconds * 1000);
    cancelBtn.onclick = function () { abortReason = "cancel"; controller.abort(); };

    errorBox.hidden = true;
    setBusy(true);
    try {
      const res = await fetch(API_URL, { method: "POST", body: new FormData(form), signal: controller.signal });
      let body = null;
      try { body = await res.json(); } catch (e) { body = null; }
      if (seq !== requestSeq) return;
      if (!body || typeof body.ok !== "boolean") {
        showError("서버 응답을 확인하지 못했습니다. 잠시 후 다시 시도하세요.");
      } else if (!body.ok) {
        const fields = body.error.fields || [];
        fields.forEach(function (f) { touched.add(f.field); });
        if (fields.length) render();
        showError([body.error.message].concat(fields.map(function (f) { return f.message; })).join(" "));
      } else {
        clearSceneImages();
        renderResult(body.data);
        lastResult = body.data;
        syncImageGen();
        resultSignature = signature;
        syncStale();
        AppShell.work.setResult(FEATURE_ID, true);
      }
    } catch (err) {
      if (seq !== requestSeq) return;
      if (abortReason === "timeout") {
        showError("최대 대기 시간(" + waitSeconds + "초)을 넘겨 기다리기를 멈췄습니다. 다시 시도하세요. " +
          "이미 보낸 요청은 서버에서 완료되거나 과금될 수 있습니다.");
      } else if (abortReason === "cancel") {
        showError("생성을 취소했습니다. 입력과 기존 결과는 그대로입니다. 이미 보낸 요청은 서버에서 완료되거나 과금될 수 있습니다.");
      } else {
        showError("서버에 연결하지 못했습니다. 앱 서버가 실행 중인지 확인한 뒤 다시 시도하세요.");
      }
    } finally {
      clearTimeout(timer);
      if (seq === requestSeq) {
        controller = null;
        setBusy(false);
      }
    }
  }

  form.addEventListener("submit", function () {
    // 기본 제출(페이지 이동)은 공통 shell이 막습니다.
    if (controller) return;
    Object.keys(LABELS).forEach(function (name) { touched.add(name); });
    render();
    if (validate().length) {
      focusFirstError();
      return;
    }
    generate();
  });

  syncAll();
})();
