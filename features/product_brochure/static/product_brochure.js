// 제품소개서 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
// 현재 범위: 한국어 PDF 선택 + 분석 결과 확인·수정 화면. 서버 요청(fetch)은 하지 않습니다.
(function () {
  "use strict";

  /* ---------- 상태 로직(DOM 없음) ---------- */
  // 항목 상태는 서로 독립된 값으로 둡니다. 미제공과 가상은 동시에 성립할 수 있습니다.
  //   provided: 자료(현재는 개발용 예시)가 값을 제공했는지. 사용자가 바꿀 수 없습니다.
  //   virtual: 시연용 가상 정보인지. 자료가 가상으로 제공한 값은 해제할 수 없습니다.
  //   confirmed: 사용자가 검토했다고 표시했는지. 사실 검증·인증 완료가 아닙니다.
  //   userAdded: 미제공 항목에 사용자가 값을 입력함. userModified: 제공된 값을 사용자가 바꿈.
  const Review = (function () {
    const GROUPS = [
      { key: "basic", label: "기본 정보" },
      { key: "spec", label: "기술 사양" },
      { key: "certification", label: "인증 정보" },
      { key: "supply", label: "공급 조건" },
    ];

    // 개발용 예시. 업로드한 PDF의 분석 결과가 아니며 근거 위치·원문 발췌가 없습니다.
    const EXAMPLE_FIELDS = [
      { key: "product_name", group: "basic", label: "제품명", value: "리젠 T2T", provided: true, virtual: false },
      { key: "description", group: "basic", label: "제품 설명", value: "폐의류를 재활용하는 폴리에스터 섬유", provided: true, virtual: false, multiline: true },
      { key: "yarn_spec", group: "spec", label: "원사 규격", value: "", provided: false, virtual: false },
      { key: "carbon_reduction", group: "spec", label: "탄소 저감률", value: "", provided: false, virtual: false },
      { key: "certification", group: "certification", label: "인증", value: "", provided: false, virtual: false },
      { key: "moq", group: "supply", label: "MOQ", value: "500 kg", provided: true, virtual: true },
      { key: "sample", group: "supply", label: "샘플", value: "1 kg", provided: true, virtual: true },
      { key: "lead_time", group: "supply", label: "납기", value: "30일", provided: true, virtual: true },
    ];

    function createFields(defs) {
      return defs.map(function (d) {
        return {
          key: d.key, group: d.group, label: d.label, multiline: !!d.multiline,
          source: "example",
          sourceValue: d.value, sourceVirtual: !!d.virtual, provided: !!d.provided,
          value: d.value, virtual: !!d.virtual, confirmed: false,
          userAdded: false, userModified: false,
        };
      });
    }

    function setValue(field, value) {
      const text = String(value);
      if (text === field.value) return false;
      field.value = text;
      field.confirmed = false; // 값을 바꾸면 확인을 해제합니다.
      field.userAdded = !field.provided && text.trim() !== "";
      field.userModified = field.provided && text !== field.sourceValue;
      return true;
    }

    function setConfirmed(field, value) {
      field.confirmed = !!value;
    }

    function setVirtual(field, value) {
      if (field.sourceVirtual) return false; // 자료가 가상으로 제공한 값은 실제 정보로 바꿀 수 없습니다.
      field.virtual = !!value;
      return true;
    }

    function isDirty(fields) {
      return fields.some(function (f) {
        return f.value !== f.sourceValue || f.confirmed || f.virtual !== f.sourceVirtual;
      });
    }

    function summarize(fields) {
      return {
        total: fields.length,
        confirmed: fields.filter(function (f) { return f.confirmed; }).length,
        notProvided: fields.filter(function (f) { return !f.provided && !f.userAdded; }).length,
        userAdded: fields.filter(function (f) { return f.userAdded; }).length,
        userModified: fields.filter(function (f) { return f.userModified; }).length,
        virtual: fields.filter(function (f) { return f.virtual; }).length,
      };
    }

    // 브라우저가 알려준 MIME은 쓰지 않습니다. 화면 1차 확인(선택·빈 파일·확장자)만 합니다.
    function validateFile(file) {
      if (!file) return { ok: false, code: "none", message: "PDF 파일을 선택하지 않았습니다." };
      if (!/\.pdf$/i.test(file.name || "")) {
        return { ok: false, code: "extension", message: "PDF가 아닌 확장자입니다. 확장자가 .pdf인 파일을 선택하세요." };
      }
      if (file.size === 0) return { ok: false, code: "empty", message: "빈 파일입니다(0 bytes). 내용이 있는 PDF를 선택하세요." };
      return {
        ok: true, code: "selected",
        message: "파일을 선택했습니다. 확장자만 확인했으며 실제 PDF 여부·손상·암호화는 아직 확인하지 않았습니다.",
      };
    }

    function formatSize(bytes) {
      if (bytes < 1024) return bytes + " bytes";
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB (" + bytes.toLocaleString("ko-KR") + " bytes)";
      return (bytes / (1024 * 1024)).toFixed(1) + " MB (" + bytes.toLocaleString("ko-KR") + " bytes)";
    }

    return {
      GROUPS: GROUPS, EXAMPLE_FIELDS: EXAMPLE_FIELDS, createFields: createFields,
      setValue: setValue, setConfirmed: setConfirmed, setVirtual: setVirtual,
      isDirty: isDirty, summarize: summarize, validateFile: validateFile, formatSize: formatSize,
    };
  })();

  // 개발용 로직 점검(Node)에서 불러올 때는 DOM 연결을 건너뜁니다.
  if (typeof module === "object" && module.exports) {
    module.exports = Review;
    return;
  }

  /* ---------- 화면 연결 ---------- */
  const FEATURE_ID = "product_brochure";
  const panel = document.querySelector('[data-feature-panel="' + FEATURE_ID + '"]');
  if (!panel) return;

  const fileInput = panel.querySelector("#product_brochure-file");
  const fileStatus = panel.querySelector("[data-file-status]");
  const fileInfo = panel.querySelector("[data-file-info]");
  const fileName = panel.querySelector("[data-file-name]");
  const fileSize = panel.querySelector("[data-file-size]");
  const loadExampleBtn = panel.querySelector("[data-load-example]");
  const reviewEmpty = panel.querySelector("[data-review-empty]");
  const review = panel.querySelector("[data-review]");
  const groupsRoot = panel.querySelector("[data-review-groups]");
  const applyBtn = panel.querySelector("[data-apply]");
  const applyStatus = panel.querySelector("[data-apply-status]");

  let fields = null;          // 현재 검토 중인 항목(브라우저 메모리)
  let applied = null;         // "확인 내용 적용" 시점의 요약
  let lastFile = null;        // 파일 교체 취소 시 되돌릴 이전 선택

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text; // 사용자 값은 항상 텍스트로만 넣습니다.
    return node;
  }

  /* 파일 선택 */
  function renderFile(file) {
    const result = Review.validateFile(file);
    fileStatus.textContent = result.message;
    fileStatus.className = result.ok || result.code === "none" ? "field-hint" : "field-error";
    if (result.ok || result.code === "none") fileInput.removeAttribute("aria-invalid");
    else fileInput.setAttribute("aria-invalid", "true");
    if (file) {
      fileName.textContent = file.name;
      fileSize.textContent = Review.formatSize(file.size);
      fileInfo.hidden = false;
    } else {
      fileInfo.hidden = true;
    }
  }

  function restoreFile(file) {
    const dt = new DataTransfer();
    if (file) dt.items.add(file);
    fileInput.files = dt.files;
  }

  fileInput.addEventListener("change", function () {
    const file = fileInput.files[0] || null;
    // 새 파일을 고르면 기존 검토 내용을 새 PDF의 결과로 보지 않고 정리합니다.
    if (file && file !== lastFile && fields) {
      if (Review.isDirty(fields) &&
          !window.confirm("새 PDF를 선택하면 현재 확인·수정한 내용이 초기화됩니다. 계속할까요?")) {
        restoreFile(lastFile); // 공통 shell의 입력 감지는 이 뒤에 실행되어 되돌린 상태를 반영합니다.
        return;
      }
      clearReview();
    }
    lastFile = file;
    renderFile(file);
  });

  /* 검토 영역 */
  function badge(text, tone) {
    return el("span", "badge" + (tone ? " badge-" + tone : ""), text);
  }

  function renderBadges(field, root) {
    root.replaceChildren();
    root.append(field.provided ? badge("제공됨", "info") : badge("미제공", "warning"));
    if (field.virtual) root.append(badge("가상 정보", "warning"));
    if (field.userAdded) root.append(badge("사용자 추가 정보", "info"));
    if (field.userModified) root.append(badge("사용자 수정", "info"));
    root.append(field.confirmed ? badge("사용자 확인", "success") : badge("미확인"));
  }

  // 항목별로 다른 안내만 표시합니다. 모든 항목에 같은 설명은 검토 영역 상단 "검토 방법"에 있습니다.
  function evidenceText(field) {
    if (field.userAdded) return "사용자 입력 값입니다. 문서 근거가 아닙니다.";
    if (!field.provided) return "미제공 항목입니다. 입력하면 사용자 추가 정보로 구분됩니다.";
    return "";
  }

  function renderField(field) {
    const id = FEATURE_ID + "-field-" + field.key;
    const wrap = el("div", "field product_brochure-item" + (field.multiline ? " product_brochure-item-wide" : ""));
    const label = el("label", "field-label", field.label);
    label.htmlFor = id;
    const input = field.multiline ? el("textarea", "textarea") : el("input", "input");
    if (!field.multiline) input.type = "text";
    input.id = id;
    input.value = field.value;
    input.placeholder = field.provided ? "" : "미제공";
    const badges = el("div", "product_brochure-badges");
    badges.setAttribute("aria-live", "polite");
    const evidence = el("p", "field-hint");
    evidence.id = id + "-evidence";

    const choices = el("div", "product_brochure-choices");
    const confirmBox = el("input");
    confirmBox.type = "checkbox";
    confirmBox.id = FEATURE_ID + "-confirm-" + field.key;
    const confirmLabel = el("label", "choice");
    confirmLabel.append(confirmBox, document.createTextNode("사용자 확인"));
    const virtualBox = el("input");
    virtualBox.type = "checkbox";
    virtualBox.id = FEATURE_ID + "-virtual-" + field.key;
    virtualBox.disabled = field.sourceVirtual;
    const virtualLabel = el("label", "choice");
    virtualLabel.append(virtualBox, document.createTextNode("가상 정보"));
    choices.append(confirmLabel, virtualLabel);

    function sync() {
      confirmBox.checked = field.confirmed;
      virtualBox.checked = field.virtual;
      const hint = evidenceText(field);
      evidence.textContent = hint;
      evidence.hidden = !hint;
      if (hint) input.setAttribute("aria-describedby", evidence.id);
      else input.removeAttribute("aria-describedby");
      renderBadges(field, badges);
    }

    input.addEventListener("input", function () {
      if (Review.setValue(field, input.value)) changed();
      sync();
    });
    confirmBox.addEventListener("change", function () {
      Review.setConfirmed(field, confirmBox.checked);
      changed();
      sync();
    });
    virtualBox.addEventListener("change", function () {
      Review.setVirtual(field, virtualBox.checked);
      changed();
      sync();
    });

    sync();
    wrap.append(label, badges, input, evidence, choices);
    return wrap;
  }

  function renderReview() {
    groupsRoot.replaceChildren();
    Review.GROUPS.forEach(function (g) {
      const groupFields = fields.filter(function (f) { return f.group === g.key; });
      if (!groupFields.length) return;
      const fieldset = el("fieldset", "fieldset product_brochure-group");
      fieldset.append(el("legend", "field-label", g.label));
      // 공통 .grid: 검토 카드의 실제 폭이 충분할 때만 2열, 좁으면 1열
      const items = el("div", "grid product_brochure-items");
      groupFields.forEach(function (f) { items.append(renderField(f)); });
      fieldset.append(items);
      groupsRoot.append(fieldset);
    });
    reviewEmpty.hidden = true;
    review.hidden = false;
  }

  function syncWork() {
    // 예시를 불러오기만 한 상태는 보호할 작업이 아닙니다. 사용자가 바꾼 것이 있을 때만 작성 중으로 알립니다.
    AppShell.work.setDraft(FEATURE_ID, !!fields && Review.isDirty(fields));
  }

  function changed() {
    if (applied) {
      applyStatus.className = "notice notice-warning";
      applyStatus.replaceChildren(
        el("p", "notice-title", "적용 이후 수정된 내용이 있습니다"),
        el("p", "", "다시 \"확인 내용 적용\"을 누르면 현재 검토 상태가 반영됩니다."));
    }
    syncWork();
  }

  function clearReview() {
    fields = null;
    applied = null;
    groupsRoot.replaceChildren();
    applyStatus.hidden = true;
    applyStatus.replaceChildren();
    review.hidden = true;
    reviewEmpty.hidden = false;
    syncWork();
  }

  loadExampleBtn.addEventListener("click", function () {
    if (fields && Review.isDirty(fields) &&
        !window.confirm("개발용 예시를 다시 불러오면 현재 확인·수정한 내용이 사라집니다. 계속할까요?")) {
      return;
    }
    // 선택한 PDF는 읽지 않습니다. 고정 예시로만 화면을 채웁니다.
    fields = Review.createFields(Review.EXAMPLE_FIELDS);
    applied = null;
    applyStatus.hidden = true;
    applyStatus.replaceChildren();
    renderReview();
    syncWork();
  });

  applyBtn.addEventListener("click", function () {
    if (!fields) return;
    // 브라우저 메모리의 검토 상태만 갱신합니다. 서버 전송·저장·카탈로그 생성은 하지 않습니다.
    applied = Review.summarize(fields);
    applyStatus.className = "notice notice-info";
    applyStatus.replaceChildren(
      el("p", "notice-title", "개발용 예시의 검토 상태를 이 화면에 반영했습니다"),
      el("p", "", "실제 PDF 분석 결과가 아니며 저장·전송하지 않았습니다. 확인 " + applied.confirmed + "/" + applied.total +
        " · 미제공 " + applied.notProvided + " · 사용자 추가 " + applied.userAdded +
        " · 사용자 수정 " + applied.userModified + " · 가상 정보 " + applied.virtual + "."));
    applyStatus.hidden = false;
  });
})();
