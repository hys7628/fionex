// 제품소개서 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
// 범위: 한국어 PDF 선택 → 분석 요청(POST /api/product-brochure/analyze) → 결과 확인·수정. 개발용 예시도 유지합니다.
(function () {
  "use strict";

  /* ---------- 상태 로직(DOM 없음) ---------- */
  // 항목 상태는 서로 독립된 값으로 둡니다. 미제공과 가상은 동시에 성립할 수 있습니다.
  //   provided: 자료가 값을 제공했는지(예시: 값 있음, AI 분석: found이면서 값 있음). 사용자가 바꿀 수 없습니다.
  //   status: AI 분석 항목만 found/unclear/not_found(예시는 null).
  //   virtual: 시연용 가상 정보인지. 자료가 가상으로 표시한 값은 해제할 수 없습니다.
  //   confirmed: 사용자가 검토했다고 표시했는지. 사실 검증·원문 대조·인증 완료가 아닙니다.
  //   userAdded: 자료 값이 없던 항목에 사용자가 입력함. userModified: 자료 값을 사용자가 바꿈.
  const Review = (function () {
    const ANALYZE_URL = "/api/product-brochure/analyze";
    const MAX_FILE_BYTES = 10 * 1024 * 1024; // 서버 공통 설정 PDF_MAX_BYTES와 같은 값
    const STATUSES = ["found", "unclear", "not_found"];

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
    const FIELD_KEYS = EXAMPLE_FIELDS.map(function (d) { return d.key; });

    function baseField(def) {
      return {
        key: def.key, group: def.group, label: def.label, multiline: !!def.multiline,
        status: null, aiStatus: null, evidence: [], note: null, serverNotes: [], candidates: null,
        confirmed: false, userAdded: false, userModified: false,
      };
    }

    function createFields(defs) {
      return defs.map(function (d) {
        const f = baseField(d);
        f.source = "example";
        f.sourceValue = d.value;
        f.sourceVirtual = !!d.virtual;
        f.provided = !!d.provided;
        f.value = d.value;
        f.virtual = !!d.virtual;
        return f;
      });
    }

    function isStr(v) { return typeof v === "string"; }
    function isStrOrNull(v) { return v === null || typeof v === "string"; }
    function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }
    function isCount(v) { return typeof v === "number" && Number.isInteger(v) && v >= 0; }

    function validField(f) {
      if (!isObj(f) || FIELD_KEYS.indexOf(f.key) < 0 || STATUSES.indexOf(f.status) < 0) return false;
      if (!isStrOrNull(f.value) || !isStrOrNull(f.note) || typeof f.marked_virtual !== "boolean") return false;
      if (f.confirmed !== false) return false;
      if (!Array.isArray(f.server_notes) || !f.server_notes.every(isStr)) return false;
      if (f.candidates !== undefined && (!Array.isArray(f.candidates) || !f.candidates.every(isStrOrNull))) return false;
      if (!Array.isArray(f.evidence)) return false;
      return f.evidence.every(function (e) {
        return isObj(e) && (e.page === null || Number.isInteger(e.page)) && isStrOrNull(e.quote) &&
          typeof e.page_in_range === "boolean" && isStr(e.check);
      });
    }

    // 성공 응답 본문 전체를 먼저 검사합니다. 하나라도 어긋나면 결과를 쓰지 않습니다(부분 덮어쓰기 없음).
    function validateAnalysis(body) {
      if (!isObj(body) || body.ok !== true || !isObj(body.data)) return null;
      const d = body.data;
      if (d.extraction_status !== "unconfirmed" || !isStr(d.model) || typeof d.multiple_products !== "boolean") return null;
      if (!isObj(d.source) || !isCount(d.source.size_bytes) || !isCount(d.source.page_count)) return null;
      if (!Array.isArray(d.review_notes) || !d.review_notes.every(function (n) {
        return isObj(n) && (n.source === "server" || n.source === "ai") && isStr(n.message);
      })) return null;
      if (!Array.isArray(d.fields) || d.fields.length !== FIELD_KEYS.length || !d.fields.every(validField)) return null;
      const keys = d.fields.map(function (f) { return f.key; });
      const unique = keys.filter(function (k, i) { return keys.indexOf(k) === i; });
      if (unique.length !== FIELD_KEYS.length) return null; // 중복 key
      return d;
    }

    // 검사를 통과한 분석 data → 화면 항목. 확인은 항상 해제 상태로 시작합니다.
    function createFieldsFromAnalysis(data) {
      return EXAMPLE_FIELDS.map(function (def) {
        const r = data.fields.filter(function (x) { return x.key === def.key; })[0];
        const f = baseField(def);
        const hasCandidates = Array.isArray(r.candidates) && r.candidates.length > 1;
        // 후보가 여럿이면 하나를 확정값처럼 채우지 않습니다.
        const value = hasCandidates ? "" : (r.value || "");
        f.source = "analysis";
        f.status = r.status;
        f.aiStatus = r.ai_status === undefined ? null : r.ai_status;
        f.sourceValue = value;
        f.value = value;
        f.provided = r.status === "found" && value.trim() !== "";
        f.sourceVirtual = r.marked_virtual;
        f.virtual = r.marked_virtual;
        f.evidence = r.evidence.map(function (e) {
          return { page: e.page, quote: e.quote, pageInRange: e.page_in_range };
        });
        f.note = r.note;
        f.serverNotes = r.server_notes.slice();
        f.candidates = hasCandidates ? r.candidates.slice() : null;
        return f;
      });
    }

    function setValue(field, value) {
      const text = String(value);
      if (text === field.value) return false;
      field.value = text;
      field.confirmed = false; // 값을 바꾸면 확인을 해제합니다.
      const hadSourceValue = field.sourceValue !== "";
      // unclear처럼 자료 값이 있던 항목의 수정은 "사용자 추가"가 아니라 "사용자 수정"입니다.
      field.userAdded = !hadSourceValue && text.trim() !== "";
      field.userModified = hadSourceValue && text !== field.sourceValue;
      return true;
    }

    function setConfirmed(field, value) {
      field.confirmed = !!value;
    }

    function setVirtual(field, value) {
      if (field.sourceVirtual) return false; // 자료가 가상으로 표시한 값은 실제 정보로 바꿀 수 없습니다.
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
        unclear: fields.filter(function (f) { return f.status === "unclear"; }).length,
      };
    }

    // 브라우저가 알려준 MIME은 쓰지 않습니다. 화면 1차 확인(선택·확장자·빈 파일·크기)만 합니다.
    function validateFile(file) {
      if (!file) return { ok: false, code: "none", message: "PDF 파일을 선택하지 않았습니다." };
      if (!/\.pdf$/i.test(file.name || "")) {
        return { ok: false, code: "extension", message: "PDF가 아닌 확장자입니다. 확장자가 .pdf인 파일을 선택하세요." };
      }
      if (file.size === 0) return { ok: false, code: "empty", message: "빈 파일입니다(0 bytes). 내용이 있는 PDF를 선택하세요." };
      if (file.size > MAX_FILE_BYTES) {
        return { ok: false, code: "too_large", message: "파일이 10 MiB를 넘습니다. 10 MiB 이하의 PDF를 선택하세요." };
      }
      return {
        ok: true, code: "selected",
        message: "파일을 선택했습니다. 실제 PDF 형식·손상·암호화·페이지 수는 분석 요청 시 서버에서 확인합니다.",
      };
    }

    function formatSize(bytes) {
      if (bytes < 1024) return bytes + " bytes";
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB (" + bytes.toLocaleString("ko-KR") + " bytes)";
      return (bytes / (1024 * 1024)).toFixed(1) + " MB (" + bytes.toLocaleString("ko-KR") + " bytes)";
    }

    // 서버 JSON 오류의 message는 공통 오류 계약의 고정 문장입니다. 형식이 맞을 때만 보여 줍니다.
    const SAFE_CODE = /^(PDF|AI|UPLOAD)_[A-Z_]{2,40}$/;

    // res: { networkError, aborted } 또는 { status, json }(JSON이 아니면 json undefined)
    function interpretResponse(res) {
      if (!res || res.networkError) {
        return { ok: false, kind: res && res.aborted ? "timeout" : "network",
          message: res && res.aborted
            ? "서버 응답이 오래 걸려 요청을 중단했습니다. 잠시 후 다시 시도하세요."
            : "서버에 연결하지 못했습니다. 네트워크 상태를 확인한 뒤 다시 시도하세요." };
      }
      if (res.status === 413) {
        return { ok: false, kind: "too_large", message: "파일 또는 요청 크기가 허용 범위(PDF 10 MiB)를 넘습니다." };
      }
      const body = res.json;
      if (body === undefined) {
        return { ok: false, kind: "not_json",
          message: "서버 응답을 해석하지 못했습니다(HTTP " + res.status + "). 잠시 후 다시 시도하세요." };
      }
      if (isObj(body) && body.ok === false) {
        const err = isObj(body.error) ? body.error : {};
        const safe = isStr(err.code) && SAFE_CODE.test(err.code) && isStr(err.message) && err.message.length <= 200;
        return { ok: false, kind: "server_error", code: safe ? err.code : null,
          message: safe ? err.message : "분석 요청을 처리하지 못했습니다(HTTP " + res.status + "). 다시 시도하세요." };
      }
      const data = res.status >= 200 && res.status < 300 ? validateAnalysis(body) : null;
      if (!data) {
        return { ok: false, kind: "invalid_response", message: "분석 응답 형식이 올바르지 않아 결과를 표시하지 않았습니다. 다시 시도하세요." };
      }
      return { ok: true, data: data };
    }

    // 분석 요청 실행기. 중복 요청을 막고, 요청 번호로 오래된 응답을 무시합니다. 자동 재시도는 없습니다.
    //   deps.send(file) → Promise<res>, deps.needsConfirm() → bool, deps.confirm(msg) → bool,
    //   deps.onBusy(bool), deps.onSuccess(data), deps.onFailure(result)
    const REPLACE_MESSAGE = "PDF 분석 결과로 현재 확인·수정한 내용을 교체합니다. 분석에 성공한 뒤에만 교체됩니다. 계속할까요?";

    function createAnalyzer(deps) {
      let seq = 0;
      let busy = false;

      async function run(file) {
        if (busy) return "busy";
        if (!validateFile(file).ok) return "invalid";
        if (deps.needsConfirm() && !deps.confirm(REPLACE_MESSAGE)) return "cancelled";
        const id = ++seq;
        busy = true;
        deps.onBusy(true);
        try {
          let res;
          try {
            res = await deps.send(file);
          } catch (e) {
            res = { networkError: true };
          }
          if (id !== seq) return "stale";
          const out = interpretResponse(res);
          if (out.ok) deps.onSuccess(out.data);
          else deps.onFailure(out);
          return out.ok ? "success" : "failure";
        } finally {
          if (id === seq) {
            busy = false;
            deps.onBusy(false);
          }
        }
      }

      // 진행 중 요청의 응답을 무시하도록 만듭니다(현재 화면에서는 사용하지 않는 방어 경로).
      function invalidate() {
        seq++;
        if (busy) {
          busy = false;
          deps.onBusy(false);
        }
      }

      return { run: run, invalidate: invalidate, isBusy: function () { return busy; } };
    }

    return {
      ANALYZE_URL: ANALYZE_URL, MAX_FILE_BYTES: MAX_FILE_BYTES, REPLACE_MESSAGE: REPLACE_MESSAGE,
      GROUPS: GROUPS, EXAMPLE_FIELDS: EXAMPLE_FIELDS, FIELD_KEYS: FIELD_KEYS,
      createFields: createFields, createFieldsFromAnalysis: createFieldsFromAnalysis, validateAnalysis: validateAnalysis,
      setValue: setValue, setConfirmed: setConfirmed, setVirtual: setVirtual,
      isDirty: isDirty, summarize: summarize, validateFile: validateFile, formatSize: formatSize,
      interpretResponse: interpretResponse, createAnalyzer: createAnalyzer,
    };
  })();

  // 개발용 로직 점검(Node)에서 불러올 때는 DOM 연결을 건너뜁니다.
  if (typeof module === "object" && module.exports) {
    module.exports = Review;
    return;
  }

  /* ---------- 화면 연결 ---------- */
  const FEATURE_ID = "product_brochure";
  const REQUEST_TIMEOUT_MS = 180000; // 서버 PDF 호출 timeout(120초)보다 길게
  const panel = document.querySelector('[data-feature-panel="' + FEATURE_ID + '"]');
  if (!panel) return;

  const form = panel.querySelector("form");
  const fileInput = panel.querySelector("#product_brochure-file");
  const fileStatus = panel.querySelector("[data-file-status]");
  const fileInfo = panel.querySelector("[data-file-info]");
  const fileName = panel.querySelector("[data-file-name]");
  const fileSize = panel.querySelector("[data-file-size]");
  const analyzeBtn = panel.querySelector("[data-analyze]");
  const analyzeStatus = panel.querySelector("[data-analyze-status]");
  const analyzeError = panel.querySelector("[data-analyze-error]");
  const loadExampleBtn = panel.querySelector("[data-load-example]");
  const reviewCard = panel.querySelector("[data-review-card]");
  const reviewEmpty = panel.querySelector("[data-review-empty]");
  const review = panel.querySelector("[data-review]");
  const exampleNotice = panel.querySelector("[data-source-example]");
  const analysisNotice = panel.querySelector("[data-source-analysis]");
  const analysisMeta = panel.querySelector("[data-analysis-meta]");
  const reviewNotes = panel.querySelector("[data-review-notes]");
  const groupsRoot = panel.querySelector("[data-review-groups]");
  const applyBtn = panel.querySelector("[data-apply]");
  const applyStatus = panel.querySelector("[data-apply-status]");

  let fields = null;          // 현재 검토 중인 항목(브라우저 메모리)
  let fieldsSource = null;    // "example" | "analysis"
  let applied = null;         // "확인 내용 적용" 시점의 요약
  let lastFile = null;        // 파일 교체 취소 시 되돌릴 이전 선택
  let busy = false;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text; // AI·사용자 문자열은 항상 텍스트로만 넣습니다.
    return node;
  }

  /* 작업 상태: 진행 중 요청과 분석 결과(재요청 비용)는 보호, 예시는 수정했을 때만 보호 */
  function syncWork() {
    const protect = busy || (!!fields && (fieldsSource === "analysis" || Review.isDirty(fields)));
    AppShell.work.setDraft(FEATURE_ID, protect);
  }

  /* 파일 선택 */
  function currentFile() {
    return fileInput.files[0] || null;
  }

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
    syncControls();
  }

  function restoreFile(file) {
    const dt = new DataTransfer();
    if (file) dt.items.add(file);
    fileInput.files = dt.files;
  }

  fileInput.addEventListener("change", function () {
    const file = currentFile();
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
    hideError();
    renderFile(file);
  });

  /* 조작 가능 상태 */
  function syncControls() {
    const valid = Review.validateFile(currentFile()).ok;
    analyzeBtn.disabled = busy || !valid;
    fileInput.disabled = busy;
    loadExampleBtn.disabled = busy;
    applyBtn.disabled = busy;
    groupsRoot.querySelectorAll("fieldset").forEach(function (fs) { fs.disabled = busy; });
    reviewCard.setAttribute("aria-busy", busy ? "true" : "false");
    analyzeStatus.replaceChildren();
    if (busy) {
      analyzeStatus.append(el("span", "spinner"), document.createTextNode(" PDF를 분석하고 있습니다. 최대 몇 분 걸릴 수 있습니다."));
    } else {
      analyzeStatus.textContent = valid
        ? "분석을 요청하면 PDF가 서버로 전송되어 OpenAI API로 분석됩니다."
        : "10 MiB 이하의 PDF를 선택하면 분석할 수 있습니다.";
    }
  }

  function showError(out) {
    analyzeError.replaceChildren(
      el("p", "notice-title", "PDF 분석에 실패했습니다"),
      el("p", "", out.message),
      el("p", "", "선택한 파일과 기존 검토 내용은 그대로 남아 있습니다. 다시 시도할 수 있습니다."));
    analyzeError.hidden = false;
  }

  function hideError() {
    analyzeError.hidden = true;
    analyzeError.replaceChildren();
  }

  /* 검토 영역 */
  function badge(text, tone) {
    return el("span", "badge" + (tone ? " badge-" + tone : ""), text);
  }

  const STATUS_BADGE = {
    found: ["문서에서 추출", "info"],
    unclear: ["확인 필요", "warning"],
    not_found: ["문서에서 찾지 못함", ""],
  };

  function renderBadges(field, root) {
    root.replaceChildren();
    if (field.status) {
      const s = STATUS_BADGE[field.status];
      root.append(badge(s[0], s[1]));
    } else {
      root.append(field.provided ? badge("제공됨", "info") : badge("미제공", "warning"));
    }
    if (field.virtual) root.append(badge("가상 정보", "warning"));
    if (field.userAdded) root.append(badge("사용자 추가 정보", "info"));
    if (field.userModified) root.append(badge("사용자 수정", "info"));
    root.append(field.confirmed ? badge("사용자 확인", "success") : badge("미확인"));
  }

  // 항목별로 다른 안내만 표시합니다. 공통 설명은 검토 영역 상단에 있습니다.
  function hintText(field) {
    if (field.userAdded) return "사용자 입력 값입니다. 문서 근거가 아닙니다.";
    if (field.candidates) return "AI가 서로 다른 값을 반환했습니다. 아래 후보를 확인하고 값을 직접 입력하세요.";
    if (field.status === "not_found") return "문서에서 찾지 못한 항목입니다. 입력하면 사용자 추가 정보로 구분됩니다.";
    if (field.status === "unclear") return "AI가 확실히 읽지 못했거나 근거가 부족합니다. 근거와 원문을 확인하세요.";
    if (!field.status && !field.provided) return "미제공 항목입니다. 입력하면 사용자 추가 정보로 구분됩니다.";
    return "";
  }

  function renderDetails(field) {
    const box = el("div", "product_brochure-details");
    if (field.candidates) {
      const list = el("ul", "product_brochure-list");
      field.candidates.forEach(function (c) { list.append(el("li", "", c === null ? "(값 없음)" : c)); });
      box.append(el("p", "product_brochure-detail-title", "후보 값(확정 아님)"), list);
    }
    if (field.evidence.length) {
      const list = el("ul", "product_brochure-list");
      field.evidence.forEach(function (e) {
        const item = el("li");
        item.append(el("span", "product_brochure-page", e.page === null ? "페이지 없음" : "p." + e.page));
        if (!e.pageInRange) item.append(document.createTextNode(" "), badge("범위 밖 페이지", "danger"));
        item.append(document.createTextNode(" "), el("q", "", e.quote === null ? "(발췌 없음)" : e.quote));
        list.append(item);
      });
      box.append(el("p", "product_brochure-detail-title", "AI 제시 근거"), list);
    }
    if (field.note) box.append(el("p", "field-hint", "AI 설명: " + field.note));
    field.serverNotes.forEach(function (n) { box.append(el("p", "field-hint", "서버 검토: " + n)); });
    return box.childNodes.length ? box : null;
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
    input.placeholder = field.provided ? "" : (field.status === "not_found" ? "문서에서 찾지 못함" : "미제공");
    const badges = el("div", "product_brochure-badges");
    badges.setAttribute("aria-live", "polite");
    const hint = el("p", "field-hint");
    hint.id = id + "-hint";

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
      const text = hintText(field);
      hint.textContent = text;
      hint.hidden = !text;
      if (text) input.setAttribute("aria-describedby", hint.id);
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
    wrap.append(label, badges, input, hint);
    const details = renderDetails(field);
    if (details) wrap.append(details);
    wrap.append(choices);
    return wrap;
  }

  function renderSourceNotice(meta) {
    exampleNotice.hidden = fieldsSource !== "example";
    analysisNotice.hidden = fieldsSource !== "analysis";
    reviewNotes.replaceChildren();
    reviewNotes.hidden = true;
    if (fieldsSource !== "analysis" || !meta) return;
    analysisMeta.textContent = "PDF " + meta.source.page_count + "쪽 · " + Review.formatSize(meta.source.size_bytes) +
      " · 응답 모델 " + meta.model;
    const notes = meta.review_notes.slice();
    if (notes.length || meta.multiple_products) {
      const list = el("ul", "product_brochure-list");
      if (meta.multiple_products) list.append(el("li", "", "복수 제품이 있을 수 있습니다. 각 값이 대상 제품의 정보인지 확인하세요."));
      notes.forEach(function (n) { list.append(el("li", "", (n.source === "ai" ? "AI: " : "서버: ") + n.message)); });
      reviewNotes.append(el("p", "notice-title", "검토 필요 사항"), list);
      reviewNotes.hidden = false;
    }
  }

  function renderReview(meta) {
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
    renderSourceNotice(meta);
    reviewEmpty.hidden = true;
    review.hidden = false;
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

  function resetApplied() {
    applied = null;
    applyStatus.hidden = true;
    applyStatus.replaceChildren();
  }

  function clearReview() {
    fields = null;
    fieldsSource = null;
    resetApplied();
    groupsRoot.replaceChildren();
    review.hidden = true;
    reviewEmpty.hidden = false;
    syncWork();
  }

  function showFields(newFields, source, meta) {
    // 검사를 마친 결과로 한 번에 교체합니다.
    fields = newFields;
    fieldsSource = source;
    resetApplied();
    renderReview(meta);
    syncControls();
    syncWork();
  }

  loadExampleBtn.addEventListener("click", function () {
    if (busy) return;
    if (fields && Review.isDirty(fields) &&
        !window.confirm("개발용 예시를 다시 불러오면 현재 확인·수정한 내용이 사라집니다. 계속할까요?")) {
      return;
    }
    // 선택한 PDF는 읽지 않습니다. 고정 예시로만 화면을 채웁니다.
    hideError();
    showFields(Review.createFields(Review.EXAMPLE_FIELDS), "example", null);
  });

  /* 분석 요청 */
  async function send(file) {
    const body = new FormData();
    body.append("source_file", file, "document.pdf"); // 원본 파일명 대신 고정 이름. Content-Type은 브라우저가 정함
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, REQUEST_TIMEOUT_MS);
    try {
      const res = await fetch(Review.ANALYZE_URL, {
        method: "POST", body: body, signal: controller.signal, headers: { Accept: "application/json" },
      });
      let json;
      if ((res.headers.get("content-type") || "").indexOf("application/json") >= 0) {
        try { json = await res.json(); } catch (e) { json = undefined; }
      }
      return { status: res.status, json: json }; // JSON이 아닌 본문(HTML 등)은 읽거나 표시하지 않음
    } catch (e) {
      return { networkError: true, aborted: !!e && e.name === "AbortError" };
    } finally {
      clearTimeout(timer);
    }
  }

  const analyzer = Review.createAnalyzer({
    send: send,
    needsConfirm: function () { return !!fields && Review.isDirty(fields); },
    confirm: function (msg) { return window.confirm(msg); },
    onBusy: function (value) {
      busy = value;
      if (value) hideError();
      syncControls();
      if (!value) AppShell.work.recheckInputs(FEATURE_ID); // 비활성 중 건너뛴 파일 입력 감지를 다시 반영
      syncWork();
    },
    onSuccess: function (data) {
      hideError();
      showFields(Review.createFieldsFromAnalysis(data), "analysis", data);
    },
    onFailure: function (out) {
      showError(out); // 기존 파일·검토 내용·작업 상태는 그대로 둡니다
    },
  });

  form.addEventListener("submit", function () {
    // 기본 제출은 공통 shell이 막습니다. 분석은 사용자가 버튼을 누를 때만 요청합니다(교체 확인 취소 시 요청 없음).
    analyzer.run(currentFile());
  });

  applyBtn.addEventListener("click", function () {
    if (!fields || busy) return;
    // 브라우저 메모리의 검토 상태만 갱신합니다. 서버 전송·저장·카탈로그 생성은 하지 않습니다.
    applied = Review.summarize(fields);
    const title = fieldsSource === "analysis"
      ? "AI 추출 결과의 검토 상태를 이 화면에 반영했습니다"
      : "개발용 예시의 검토 상태를 이 화면에 반영했습니다";
    const scope = fieldsSource === "analysis"
      ? "원문 대조나 사실 검증을 한 것이 아니며 저장·전송하지 않았습니다. "
      : "실제 PDF 분석 결과가 아니며 저장·전송하지 않았습니다. ";
    applyStatus.className = "notice notice-info";
    applyStatus.replaceChildren(
      el("p", "notice-title", title),
      el("p", "", scope + "확인 " + applied.confirmed + "/" + applied.total +
        " · 확인 필요 " + applied.unclear + " · 미제공 " + applied.notProvided + " · 사용자 추가 " + applied.userAdded +
        " · 사용자 수정 " + applied.userModified + " · 가상 정보 " + applied.virtual + "."));
    applyStatus.hidden = false;
  });

  syncControls();
})();
