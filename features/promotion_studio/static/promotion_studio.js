// 홍보 스튜디오 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
// 현재 구현: 콘티 입력 검증(서버 service.validate_input과 같은 규칙). 콘티 생성은 다음 단계에서 연결합니다.
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
      summaryText.textContent = "콘티 생성에 필요한 입력이 준비되었습니다. 콘티 생성 기능은 준비 중입니다.";
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
    list.replaceChildren.apply(list, selected.map(function (file) {
      const li = document.createElement("li");
      li.textContent = file.name + " (" + sizeText(file.size) + ")";
      return li;
    }));
    list.hidden = !selected.length;
  }

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
  });
  form.addEventListener("change", function (event) {
    const name = event.target.name;
    if (name) touched.add(name);
    if (event.target.dataset.psFile) {
      checkSignatures(files(name)).then(syncAll);
    }
    syncAll();
  });
  form.addEventListener("focusout", function (event) {
    if (event.target.name && event.target.type !== "file") {
      touched.add(event.target.name);
      render();
    }
  });
  form.addEventListener("reset", function () {
    touched.clear();
    setTimeout(syncAll, 0);
  });

  syncAll();
})();
