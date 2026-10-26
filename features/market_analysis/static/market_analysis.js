// 시장 분석 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
// 결과는 페이지 메모리(DOM)에만 둡니다. 브라우저 저장소에 쓰지 않습니다.
(function () {
  "use strict";

  const FEATURE_ID = "market_analysis";
  const panel = document.querySelector('[data-feature-panel="' + FEATURE_ID + '"]');
  if (!panel) return;

  const form = panel.querySelector("[data-ma-form]");
  const submitBtn = panel.querySelector("[data-ma-submit]");
  const refreshBtn = panel.querySelector("[data-ma-refresh]");
  const formError = panel.querySelector("[data-ma-form-error]");
  const resultBox = panel.querySelector("[data-ma-result]");
  const periodHint = panel.querySelector("[data-ma-period-hint]");
  const countryList = panel.querySelector("[data-ma-country-list]");
  const countryCount = panel.querySelector("[data-ma-country-count]");
  const countrySearch = panel.querySelector("#market_analysis-country-search");
  const inputs = {
    code_system: form.elements.code_system,
    code: form.elements.code,
    from: form.elements.from,
    to: form.elements.to,
  };

  const pdfBtn = panel.querySelector("[data-ma-pdf]");
  const pdfHint = panel.querySelector("[data-ma-pdf-hint]");

  let meta = null;
  let busy = false;
  let lastResult = null;  // 통계(analyze 응답)
  let lastAi = null;      // AI 분석(ai 응답)
  let aiBusy = false;
  let chartMetric = "fob";

  /* ---------- 숫자 표시 (계산은 서버 원본 값, 여기서는 반올림 표시만) ---------- */
  const fmtInt = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
  const fmt1 = new Intl.NumberFormat("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const fmt2 = new Intl.NumberFormat("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const NA = "계산 불가";

  function usd(v) { return v == null ? "기록 없음" : "USD " + fmtInt.format(v); }
  function tons(kg) { return kg == null ? "기록 없음" : fmt1.format(kg / 1000) + " t"; }
  function price(v) { return v == null ? NA : fmt2.format(v) + " USD/kg"; }
  function pct(v) { return v == null ? NA : fmt1.format(v) + "%"; }
  function signedPct(v) { return (v > 0 ? "+" : "") + fmt1.format(v) + "%"; }
  function yoyText(y) { return y.value == null ? NA + " (" + y.reason + ")" : signedPct(y.value); }
  // 표 안에서는 단위를 열 제목에 두고 숫자만 표시합니다.
  function nUsd(v) { return v == null ? "—" : fmtInt.format(v); }
  function nTons(kg) { return kg == null ? "—" : fmt1.format(kg / 1000); }
  function nPrice(v, reason) { return v == null ? NA + (reason ? " (" + reason + ")" : "") : fmt2.format(v); }

  const METRICS = {
    fob: { label: "수입액", unit: "USD", value: function (m) { return m.fob; }, text: usd },
    kg: { label: "수입량", unit: "t", value: function (m) { return m.kg == null ? null : m.kg / 1000; }, text: function (v) { return v == null ? "기록 없음" : fmt1.format(v) + " t"; } },
    unit_price: { label: "평균 수입단가(FOB)", unit: "USD/kg", value: function (m) { return m.unit_price; }, text: function (v) { return price(v); } },
  };

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // 링크로 쓸 수 있는 http(s) 절대 주소만 통과시킵니다(javascript: 등 차단).
  function safeUrl(value) {
    if (typeof value !== "string" || !value || /[\s<>"'\u0000-\u001f]/.test(value)) return null;
    try {
      const u = new URL(value);
      return (u.protocol === "http:" || u.protocol === "https:") && u.host ? value : null;
    } catch (e) {
      return null;
    }
  }

  function linkHtml(url, label) {
    const safe = safeUrl(url);
    if (!safe) return '<span class="field-hint">원문 주소 형식 오류(링크 미표시)</span>';
    return '<a href="' + esc(safe) + '" target="_blank" rel="noopener noreferrer">' + esc(label || safe) + "</a>";
  }

  function countryName(c) {
    if (!c) return "";
    if (c.name_ko && c.name_pt) return c.name_ko + " (" + c.name_pt + ")";
    return c.name_ko || c.name_pt || "";
  }

  function kstTime(iso) {
    if (!iso) return "확인 안 됨";
    return iso.replace("T", " ").replace("+09:00", " KST");
  }

  /* ---------- 입력 오류 ---------- */
  function clearErrors() {
    panel.querySelectorAll("[data-error-for]").forEach(function (p) { p.hidden = true; p.textContent = ""; });
    Object.values(inputs).forEach(function (el) { el.removeAttribute("aria-invalid"); });
    formError.hidden = true;
    formError.textContent = "";
  }

  function showFieldErrors(fields) {
    let first = null;
    Object.keys(fields).forEach(function (name) {
      const p = panel.querySelector('[data-error-for="' + name + '"]');
      if (p) { p.textContent = fields[name]; p.hidden = false; }
      const el = inputs[name];
      if (el) { el.setAttribute("aria-invalid", "true"); if (!first) first = el; }
    });
    if (first) first.focus();
  }

  function showFormError(title, message) {
    formError.innerHTML = '<p class="notice-title">' + esc(title) + "</p><p>" + esc(message) + "</p>";
    formError.hidden = false;
  }

  // 서버와 같은 기준의 빠른 확인. 최종 검증은 서버가 합니다.
  function clientValidate(payload) {
    const fields = {};
    const len = payload.code_system === "hs6" ? 6 : 8;
    if (!payload.code) fields.code = "품목코드를 입력해 주세요.";
    else if (!/^\d+$/.test(payload.code)) fields.code = "품목코드는 숫자로 입력해 주세요. 점(.)은 넣어도 됩니다.";
    else if (payload.code.length !== len) fields.code = (len === 8 ? "NCM 8자리" : "HS 6자리") + " 코드는 숫자 " + len + "자리입니다. 입력한 코드는 " + payload.code.length + "자리입니다.";
    if (!payload.from) fields.from = "시작 월을 선택해 주세요.";
    if (!payload.to) fields.to = "종료 월을 선택해 주세요.";
    if (payload.from && payload.to && !fields.from && !fields.to) {
      const span = monthIndex(payload.to) - monthIndex(payload.from) + 1;
      if (span < 1) fields.from = "시작 월이 종료 월보다 늦습니다. 기간을 다시 선택해 주세요.";
      else if (meta && span > meta.max_months) fields.from = "조회 기간은 최대 " + meta.max_months + "개월입니다. 지금은 " + span + "개월입니다. 기간을 줄여 주세요.";
      else if (meta && meta.latest && payload.to > meta.latest.month) fields.to = "통계는 " + meta.latest.month + "까지 제공됩니다. 종료 월을 " + meta.latest.month + " 이전으로 선택해 주세요.";
    }
    return fields;
  }

  function monthIndex(value) {
    const parts = value.split("-");
    return Number(parts[0]) * 12 + Number(parts[1]) - 1;
  }

  /* ---------- 초기값 ---------- */
  function setDefault(el, value) {
    el.defaultValue = value;
    el.value = value;
  }

  function renderCountries(countries, koreaCode) {
    const items = countries.map(function (c) {
      const id = "market_analysis-country-" + c.code;
      const strong = c.code === koreaCode ? " ma-country-korea" : "";
      return '<label class="choice ma-country' + strong + '" for="' + id + '" data-search="' +
        esc(((c.name_ko || "") + " " + c.name_pt + " " + c.code).toLowerCase()) + '">' +
        '<input type="checkbox" id="' + id + '" name="countries" value="' + esc(c.code) + '">' +
        "<span>" + esc(countryName(c)) + "</span></label>";
    });
    countryList.innerHTML = items.join("");
  }

  function updateCountryCount() {
    const checked = countryList.querySelectorAll('input[name="countries"]:checked');
    countryCount.textContent = checked.length ? "선택한 공급국 " + checked.length + "개" : "선택한 공급국 없음";
  }

  countryList.addEventListener("change", updateCountryCount);
  countrySearch.addEventListener("input", function () {
    const q = countrySearch.value.trim().toLowerCase();
    countryList.querySelectorAll(".ma-country").forEach(function (label) {
      label.hidden = q !== "" && label.dataset.search.indexOf(q) === -1;
    });
  });

  async function loadMeta() {
    try {
      const res = await fetch("/api/market-analysis/meta");
      const body = await res.json();
      if (!body.ok) throw new Error("meta");
      meta = body.data;
    } catch (err) {
      periodHint.textContent = "초기값을 불러오지 못했습니다. 품목코드와 기간을 직접 입력해 주세요.";
      return;
    }
    if (!inputs.code.value) setDefault(inputs.code, meta.default.code);
    renderCountries(meta.countries, meta.korea_code);
    inputs.from.min = meta.first_month;
    inputs.to.min = meta.first_month;
    if (meta.latest) {
      inputs.from.max = meta.latest.month;
      inputs.to.max = meta.latest.month;
      if (!inputs.from.value) setDefault(inputs.from, meta.default.from);
      if (!inputs.to.value) setDefault(inputs.to, meta.default.to);
      periodHint.textContent = "최신 제공 월 " + meta.latest.month + " (ComexStat 갱신일 " + meta.latest.updated +
        "). 기본값은 최신 월까지 최근 " + meta.default.months + "개월이며 최대 " + meta.max_months + "개월까지 조회할 수 있습니다." +
        (meta.latest.stale ? " 오늘 최신 월을 다시 확인하지 못해 이전에 확인한 값을 사용했습니다." : "");
    } else {
      periodHint.textContent = "최신 제공 월을 확인하지 못했습니다(" + (meta.error ? meta.error.message : "") +
        "). 기간을 직접 선택해 주세요. 최대 " + meta.max_months + "개월입니다.";
    }
    AppShell.work.recheckInputs(FEATURE_ID);
  }

  /* ---------- 조회 ---------- */
  function collect(refresh) {
    return {
      code_system: inputs.code_system.value,
      code: inputs.code.value.replace(/[\s.\-]/g, ""),
      from: inputs.from.value,
      to: inputs.to.value,
      countries: Array.from(countryList.querySelectorAll('input[name="countries"]:checked')).map(function (el) { return el.value; }),
      refresh: !!refresh,
    };
  }

  function setBusy(value) {
    busy = value;
    submitBtn.disabled = value;
    refreshBtn.disabled = value;
    resultBox.setAttribute("aria-busy", value ? "true" : "false");
    updatePdfButton();
  }

  async function run(refresh) {
    if (busy) return;
    clearErrors();
    const payload = collect(refresh);
    const localErrors = clientValidate(payload);
    if (Object.keys(localErrors).length) { showFieldErrors(localErrors); return; }

    setBusy(true);
    const previous = resultBox.innerHTML;
    resultBox.innerHTML = '<div class="empty-state"><span class="spinner" aria-hidden="true"></span>' +
      '<p class="empty-state-title">ComexStat에서 자료를 불러오는 중입니다</p><p>호출 한도 때문에 수십 초 걸릴 수 있습니다.</p></div>';
    try {
      const res = await fetch("/api/market-analysis/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      let body = null;
      try { body = await res.json(); } catch (e) { body = null; }
      if (!body) throw { message: "서버 응답을 읽지 못했습니다. 다시 시도해 주세요.", retryable: true };
      if (!body.ok) {
        if (body.error.fields) {
          resultBox.innerHTML = previous;
          showFieldErrors(body.error.fields);
          return;
        }
        throw body.error;
      }
      lastResult = body.data;
      lastAi = null;
      renderResult(body.data);
      refreshBtn.hidden = false;
      AppShell.work.setResult(FEATURE_ID, true);
      updatePdfButton();
      refreshAiPanel();
    } catch (err) {
      resultBox.innerHTML = previous;
      showFormError("자료 조회 실패", (err && err.message) || "네트워크 오류로 조회하지 못했습니다. 다시 시도해 주세요.");
      refreshBtn.hidden = false;
    } finally {
      setBusy(false);
    }
  }

  form.addEventListener("submit", function () { run(false); }); // 기본 제출은 공통 shell이 막음
  refreshBtn.addEventListener("click", function () { run(true); });

  /* ---------- 결과 ---------- */
  function badge(tone, text) { return '<span class="badge badge-' + tone + '">' + esc(text) + "</span>"; }
  function flagBadge(flag) {
    if (flag === "high") return " " + badge("warning", "확인 필요 · 중앙값의 2배 초과");
    if (flag === "low") return " " + badge("warning", "확인 필요 · 중앙값의 ½ 미만");
    return "";
  }

  function tile(label, value, yoy, extra) {
    return '<div class="ma-tile"><p class="ma-tile-label">' + esc(label) + '</p><p class="ma-tile-value">' + esc(value) + "</p>" +
      '<p class="ma-tile-sub">전년 동기 대비 ' + esc(yoyText(yoy)) + "</p>" + (extra || "") + "</div>";
  }

  function renderResult(d) {
    const q = d.query, s = d.summary, src = d.sources[0];
    const caption = "출처: ComexStat · 브라질 수입 · " + q.code_system_label + " " + q.code + " · " + q.from + "~" + q.to;
    let html = "";

    html += '<div class="ma-query">' + badge("info", "브라질 수입") + " " +
      "<span>" + esc(q.code_system_label + " " + q.code + (q.code_name ? " · " + q.code_name : "")) + "</span>" +
      "<span>" + esc(q.from + " ~ " + q.to + " (" + q.months + "개월)") + "</span>" +
      "<span>" + esc(q.countries.length ? "비교 공급국: " + q.countries.map(countryName).join(", ") : "공급국: 전체 국가") + "</span></div>";
    html += '<p class="field-hint">무역 통계는 해당 코드의 전체 시장입니다. 일반 원사·재생 원사·리젠 T2T를 구분하지 않으므로 T2T 수요나 시장 규모로 해석하지 마세요. 평균 수입단가는 FOB 기준이며 견적·판매가격·도착가격이 아닙니다.</p>';

    // 통계 참고 사항(코드표 기준·재수입 제외·수치 재집계 등)은 접어 둡니다. T2T 해석 주의와 '이전 자료 사용' 경고는 항상 표시.
    if (d.notes.length) {
      html += '<details class="ma-details ma-period-notes"><summary>통계 참고 사항 ' + d.notes.length + "건 보기</summary>" +
        d.notes.map(function (n) { return '<div class="notice notice-info"><p>' + esc(n) + "</p></div>"; }).join("") + "</details>";
    }
    if (src.cache_status === "stale") {
      html += '<div class="notice notice-warning" role="status"><p class="notice-title">이전 자료 사용</p><p>ComexStat 조회에 실패해 ' +
        esc(kstTime(src.fetched_at)) + "에 받은 자료로 표시했습니다. 최신 자료가 아닐 수 있습니다.</p></div>";
    }

    if (!d.has_data) {
      html += '<div class="empty-state"><p class="empty-state-title">조회 결과 없음</p><p>이 조건에는 ComexStat 수입 기록이 없습니다. 자료 조회 실패가 아니며, 수입액이 0으로 확인된 것도 아닙니다.</p></div>';
      html += sourcesHtml(d);
      resultBox.innerHTML = html;
      return;
    }

    // ① 핵심 수치
    html += '<section class="ma-section" aria-labelledby="market_analysis-s1"><h3 class="ma-h3" id="market_analysis-s1">① 핵심 수치</h3>';
    html += '<div class="ma-tiles">' +
      tile("수입액 (FOB)", usd(s.fob), s.yoy.fob) +
      tile("수입량 (순중량)", tons(s.kg), s.yoy.kg) +
      tile("평균 수입단가 (FOB, USD/kg)", s.unit_price == null ? NA + " (" + s.unit_price_reason + ")" : price(s.unit_price), s.yoy.unit_price) +
      "</div>";
    html += '<p class="field-hint">전년 동기: ' + esc(s.prior_period.from + " ~ " + s.prior_period.to) + ". 증감률 = (현재 − 전년 동기) ÷ 전년 동기 × 100. 평균 수입단가 = FOB 합계 ÷ 순중량 합계.</p></section>";

    // ② 시장 추세
    html += '<section class="ma-section" aria-labelledby="market_analysis-s2"><h3 class="ma-h3" id="market_analysis-s2">② 시장 추세 (월별)</h3>';
    html += '<div class="ma-metric-switch" role="radiogroup" aria-label="그래프 지표" data-work-ignore>' +
      Object.keys(METRICS).map(function (k) {
        return '<label class="choice"><input type="radio" name="market_analysis-metric" value="' + k + '"' + (k === chartMetric ? " checked" : "") + "> " + esc(METRICS[k].label) + "</label>";
      }).join("") + "</div>";
    html += '<figure class="ma-chart" data-ma-chart></figure>';
    html += "<details class=\"ma-details\"><summary>월별 상세 표 보기</summary>" + monthlyTable(d, caption) + "</details></section>";

    // ③ 공급국
    html += '<section class="ma-section" aria-labelledby="market_analysis-s3"><h3 class="ma-h3" id="market_analysis-s3">③ 공급국 비교</h3>';
    html += '<p class="field-hint">수입액 기준 순위. 비중의 분모는 같은 품목·기간의 브라질 전체 수입액입니다. 공급국은 ComexStat 기준 원산지 국가이며 판매 회사의 국가가 아닙니다(MDIC 통계 이용 매뉴얼). 기간 내 공급국 ' + d.suppliers.count + "개국.</p>";
    html += koreaHtml(d.suppliers);
    html += supplierTable(d.suppliers.top, caption + " · 상위 " + d.suppliers.top.length + "개국");
    if (d.suppliers.selected.length) {
      html += '<h4 class="ma-h4">선택한 공급국</h4>' + supplierTable(d.suppliers.selected, caption + " · 선택한 공급국 (비중은 전체 시장 기준)");
    }
    html += "</section>";

    // ④ AI 분석(사용자가 직접 실행하는 유료 호출)
    html += '<section class="ma-section" aria-labelledby="market_analysis-s4"><h3 class="ma-h3" id="market_analysis-s4">④ AI 분석</h3>' +
      '<div data-ma-ai>' + aiIdleHtml() + "</div></section>";

    html += sourcesHtml(d);
    resultBox.innerHTML = html;
    drawChart();
  }

  /* ---------- AI 분석 ---------- */
  const DIAG_ENV_TEXT = { OPENAI_API_KEY: "키 미설정", OPENAI_MODEL: "모델 미설정" };

  function aiReady() { return !(meta && meta.ai && !meta.ai.ready); }

  // 개발자 진단: 분류·환경변수 이름·HTTP 상태만(비밀값 없음). 사용자 안내 문장과 분리해 접어 둡니다.
  function diagHtml(d) {
    if (!d) return "";
    const parts = ["분류: " + d.label + " (" + d.kind + ")"];
    if (d.env_missing && d.env_missing.length) parts.push("비어 있는 환경변수: " + d.env_missing.join(", "));
    if (d.status_code) parts.push("HTTP 상태 " + d.status_code);
    if (d.detail) parts.push(d.detail);
    return '<details class="ma-details"><summary>개발자 진단 보기</summary><p class="field-hint">' + esc(parts.join(" · ")) + "</p></details>";
  }

  function aiIdleHtml() {
    let html = "";
    if (!aiReady()) {
      const missing = meta.ai.missing || [];
      html += '<div class="notice notice-warning" role="status"><p class="notice-title">AI 분석 설정 필요</p><p>' +
        "서버에 AI 분석 설정(OpenAI 키·텍스트 모델)이 없어 지금은 실행할 수 없습니다. 통계와 근거 자료는 그대로 볼 수 있습니다. 관리자가 설정한 뒤 서버를 다시 시작하고 이 페이지를 새로 열어야 합니다.</p>" +
        diagHtml({ kind: "config", label: missing.map(function (m) { return DIAG_ENV_TEXT[m] || m; }).join("·") || "설정 누락", env_missing: missing,
          detail: ".env 파일은 앱이 직접 읽지 않습니다(python-dotenv 미설치 시). 서버를 시작하는 셸의 환경변수로 넣어야 합니다." }) + "</div>";
    }
    // 소요 시간은 2026-10-26 실제 실행 3회(44~56초) 기준. 회차별 검토 항목은 실행 후 '5차례 검토 기록'에 나옵니다.
    return html + '<p class="field-hint">통계(ComexStat)를 근거로 분석합니다. OpenAI를 최대 6번 호출하는 유료 기능(초안 1회 + 5차례 검토)이며 1분 안팎 걸립니다. ' +
      "같은 조회 결과로는 한 번만 실행됩니다.</p>" +
      '<button type="button" class="btn btn-primary" data-ma-ai-run disabled>AI 분석 실행</button>';
  }

  function refreshAiPanel() {
    const run = resultBox.querySelector("[data-ma-ai-run]");
    if (run) run.disabled = aiBusy || !lastResult || !aiReady();
  }

  async function runAi() {
    const box = resultBox.querySelector("[data-ma-ai]");
    if (!box || aiBusy || !lastResult) return;
    aiBusy = true;
    box.setAttribute("aria-busy", "true");
    const previous = lastAi ? aiHtml(lastAi) : null;
    box.innerHTML = '<div class="empty-state"><span class="spinner" aria-hidden="true"></span><p class="empty-state-title">AI 분석 중입니다</p>' +
      "<p>초안 작성 후 5차례 검토를 차례로 진행합니다(1분 안팎). 이 탭을 새로고침하지 마세요.</p></div>";
    try {
      const res = await fetch("/api/market-analysis/ai", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bundle_id: lastResult.bundle_id }),
      });
      const body = await res.json();
      if (!body.ok) throw body.error;
      lastAi = body.data;
      box.innerHTML = aiHtml(body.data);
    } catch (err) {
      box.innerHTML = (previous || "") + '<div class="notice notice-danger" role="alert"><p class="notice-title">AI 분석을 실행하지 못했습니다</p><p>' +
        esc((err && err.message) || "네트워크 오류입니다.") + "</p></div>" + (previous ? "" : aiIdleHtml());
    } finally {
      aiBusy = false;
      box.setAttribute("aria-busy", "false");
      refreshAiPanel();
      updatePdfButton();
    }
  }

  const STATUS_TONE = { "사실": "success", "추정": "info", "미확인": "warning" };

  function aiHtml(a) {
    let html = "";
    if (!a.has_draft) {
      const e = a.error || {};
      if (e.needs_restart) {
        // 설정 누락: 다시 눌러도 같은 결과이므로 재실행 버튼을 두지 않습니다(호출 0회).
        return '<div class="notice notice-warning" role="status"><p class="notice-title">AI 분석을 시작하지 않았습니다</p><p>' +
          esc(e.message || "AI 분석 설정이 없습니다.") + "</p>" + diagHtml(e.diagnostic) + "</div>" + usageHtml(a);
      }
      return '<div class="notice notice-danger" role="alert"><p class="notice-title">AI 분석을 시작하지 못했습니다</p><p>' +
        esc(e.message || "알 수 없는 오류입니다.") + " 분석 결과는 만들어지지 않았습니다. 통계와 근거 자료는 그대로 볼 수 있습니다.</p>" + diagHtml(e.diagnostic) +
        '<button type="button" class="btn btn-secondary" data-ma-ai-run>다시 실행</button></div>' + usageHtml(a);
    }
    if (!a.complete) {
      const e = a.error || {};
      html += '<div class="notice notice-warning" role="status"><p class="notice-title">검토 미완료 (' + a.rounds.length + "/" + a.rounds_total + "회 완료)</p><p>" +
        esc((e.failed_at ? e.failed_at + "에서 멈춤. " : "") + (e.message || "")) + " 아래 표는 마지막으로 끝난 단계의 결과이며 완료된 분석이 아닙니다.</p>" +
        diagHtml(e.diagnostic) + '<button type="button" class="btn btn-secondary" data-ma-ai-run>이어서 실행</button></div>';
    } else {
      html += '<p class="field-hint">' + badge("success", "초안 + 5차례 검토 완료") + (a.reused ? " 이미 끝난 분석 결과를 다시 표시했습니다(추가 호출 없음)." : "") + "</p>";
    }
    // 출처로 확인된 사실 행만 표시합니다(추정·미확인 행은 서버가 빼고, 이전 결과에 대비해 여기서도 거름).
    const factRows = a.rows.filter(function (r) { return r.status === "사실"; });
    if (factRows.length) {
      html += '<div class="table-wrap"><table class="table"><caption>AI 분석 · 출처로 확인된 사실만 표시 · 수치는 코드 계산값과 근거 기사에 있는 값만 허용</caption><thead><tr>' +
        '<th scope="col">구분</th><th scope="col">핵심 내용</th><th scope="col">영업·마케팅 시사점</th><th scope="col">사실/추정/미확인</th><th scope="col">출처·기준일</th></tr></thead><tbody>';
      factRows.forEach(function (r) {
        const srcs = r.sources.length ? r.sources.map(function (s) {
          return linkHtml(s.url, s.id + " " + s.name) + ' <span class="field-hint">' + esc(s.date) + "</span>";
        }).join("<br>") : "출처 없음";
        html += '<tr><th scope="row">' + esc(r.section) + "</th><td>" + esc(r.content) + "</td><td>" + esc(r.implication) + "</td><td>" +
          badge(STATUS_TONE[r.status] || "info", r.status) +
          (r.flags.length ? '<p class="field-hint">확인 필요: ' + esc(r.flags.join("; ")) + "</p>" : "") + "</td><td>" + srcs + "</td></tr>";
      });
      html += "</tbody></table></div>";
    } else {
      html += '<div class="empty-state"><p class="empty-state-title">표에 남은 행이 없습니다</p><p>근거가 부족해 작성하지 않았습니다.</p></div>';
    }
    if (a.gaps.length) html += '<p class="field-hint">근거 부족으로 작성하지 않은 내용: ' + esc(a.gaps.join("; ")) + "</p>";
    if (a.remaining_findings.length) html += '<div class="notice notice-warning"><p class="notice-title">자동 검사에서 남은 문제</p><p>' + esc(a.remaining_findings.join("; ")) + "</p></div>";
    html += '<details class="ma-details"><summary>5차례 검토 기록 보기</summary><div class="table-wrap"><table class="table"><thead><tr>' +
      '<th scope="col">회차</th><th scope="col">확인한 항목</th><th scope="col">수정 사항</th><th scope="col">근거</th><th scope="col">미해결</th><th scope="col">코드 검사(전→후)</th><th scope="col">완료</th></tr></thead><tbody>';
    for (let i = 0; i < a.rounds_total; i++) {
      const r = a.rounds[i];
      if (!r) { html += "<tr><th scope=\"row\">" + (i + 1) + '회차</th><td colspan="6">미실행</td></tr>'; continue; }
      html += '<tr><th scope="row">' + esc(r.number + ". " + r.title) + "</th><td>" + esc(r.checked.join("; ") || "-") + "</td><td>" +
        esc(r.changes.join("; ") || "수정 없음") + "</td><td>" + esc(r.evidence.join("; ") || "-") + "</td><td>" + esc(r.unresolved.join("; ") || "-") +
        "</td><td>" + esc(r.code_findings_before.length + "건 → " + r.code_findings_after.length + "건") + "</td><td>" +
        badge(r.status === "done" ? "success" : "warning", r.status === "done" ? "완료" : "미완료") + "</td></tr>";
    }
    html += "</tbody></table></div>";
    const removed = a.removed_rows || [];
    if (removed.length) {
      html += '<p class="field-hint">출처로 확인되지 않아 표에서 뺀 항목 ' + removed.length + "건: " +
        esc(removed.map(function (r) { return r.section + " · " + r.content; }).join("; ")) + "</p>";
    }
    html += "</details>";
    return html + usageHtml(a);
  }

  function usageHtml(a) {
    const u = a.usage || {};
    return '<p class="field-hint">' + esc("모델 " + (u.model || "-") + " · 호출 " + (u.calls || 0) + "회 · 입력 " + (u.input_tokens || 0) + " / 출력 " +
      (u.output_tokens || 0) + " 토큰 · 소요 " + (u.seconds || 0) + "초" + (u.estimated_cost_usd != null ? " · 추정 비용 USD " + u.estimated_cost_usd + " (" + u.cost_basis + ")" : "") +
      " · 프롬프트 " + a.prompt_versions.draft + " / " + a.prompt_versions.review) + "</p>";
  }

  /* ---------- PDF ---------- */
  function updatePdfButton() {
    const ready = !!lastResult && !busy && !aiBusy;
    pdfBtn.disabled = !ready;
    pdfHint.textContent = !lastResult ? "분석 결과가 생기면 화면 내용 그대로 A4 PDF로 받을 수 있습니다."
      : aiBusy ? "AI 분석이 끝나면 PDF를 받을 수 있습니다."
      : "현재 화면의 통계" + (lastAi ? "·AI 분석" : "") + "로 PDF를 만듭니다. 다시 조회하거나 분석하지 않습니다.";
  }

  pdfBtn.addEventListener("click", async function () {
    if (pdfBtn.disabled || !lastResult) return;
    pdfBtn.disabled = true;
    pdfHint.textContent = "PDF를 만드는 중입니다.";
    try {
      const res = await fetch("/api/market-analysis/pdf", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stats: lastResult, ai: lastAi }),
      });
      if (!res.ok) {
        let msg = "PDF를 만들지 못했습니다.";
        try { msg = (await res.json()).error.message; } catch (e) { /* 기본 문장 */ }
        throw new Error(msg);
      }
      const q = lastResult.query;
      AppShell.work.downloadBlob(FEATURE_ID, await res.blob(), "market_analysis_" + q.code + "_" + q.from + "_" + q.to + ".pdf");
      // 머리글의 '다운로드 요청됨 · 저장 여부는 브라우저에서 확인' 표시를 띄우지 않습니다(2026-10-26 담당자 지시).
      // clear는 downloadBlob이 해제한 것과 같은 경고 상태에 다운로드 요청 표시만 추가로 끕니다(공통 코드 변경 없음).
      AppShell.work.clear(FEATURE_ID);
      updatePdfButton();
      pdfHint.textContent = "PDF 다운로드를 요청했습니다.";
    } catch (err) {
      updatePdfButton();
      pdfHint.textContent = err.message;
    }
  });

  resultBox.addEventListener("click", function (event) {
    if (event.target.closest("[data-ma-ai-run]")) runAi();
  });

  function koreaHtml(sup) {
    const k = sup.korea;
    if (!k) {
      return '<div class="notice notice-info"><p class="notice-title">한국 현황</p><p>조회 기간에 한국(Coreia do Sul)의 수입 기록이 없습니다.</p></div>';
    }
    return '<div class="notice notice-info"><p class="notice-title">한국 현황</p><p>' + esc(k.rank + "위 / " + sup.count + "개국 · 비중 " + pct(k.share) +
      " · 수입액 " + usd(k.fob) + " · 수입량 " + tons(k.kg) + " · 평균 수입단가 " + price(k.unit_price) + " · 기록 있는 달 " + k.months_with_record + "개월") + "</p></div>";
  }

  function supplierTable(list, caption) {
    const rows = list.map(function (c) {
      if (c.no_record) {
        return '<tr><td class="num">—</td><th scope="row">' + esc(countryName(c.country)) + '</th><td colspan="6">조회 기간 수입 기록 없음</td></tr>';
      }
      const korea = c.country.code === "190" ? " ma-row-korea" : "";
      return '<tr class="' + korea + '"><td class="num">' + c.rank + '</td><th scope="row">' + esc(countryName(c.country)) + "</th>" +
        '<td class="num">' + esc(nUsd(c.fob)) + '</td><td class="num">' + esc(pct(c.share)) + "</td>" +
        '<td class="num">' + esc(nTons(c.kg)) + '</td><td class="num">' + esc(nPrice(c.unit_price, c.unit_price_reason)) + "</td>" +  // 공급국 단가에는 '확인 필요'를 붙이지 않음(2026-10-26 원자료 대조 후 담당자 지시)
        '<td class="num">' + esc(yoyText(c.yoy.fob)) + '</td><td class="num">' + c.months_with_record + "</td></tr>";
    });
    return '<div class="table-wrap"><table class="table"><caption>' + esc(caption) + "</caption><thead><tr>" +
      '<th scope="col" class="num">순위</th><th scope="col">공급국</th><th scope="col" class="num">수입액 (USD)</th><th scope="col" class="num">비중</th>' +
      '<th scope="col" class="num">수입량 (t)</th><th scope="col" class="num">평균 수입단가 (USD/kg)</th><th scope="col" class="num">수입액 전년 대비</th><th scope="col" class="num">기록 월 수</th>' +
      "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>";
  }

  function monthlyTable(d, caption) {
    const rows = d.monthly.map(function (m) {
      if (!m.has_record) {
        return '<tr><th scope="row">' + m.month + '</th><td colspan="6">기록 없음</td></tr>';
      }
      return '<tr><th scope="row">' + m.month + '</th><td class="num">' + esc(nUsd(m.fob)) + '</td><td class="num">' + esc(yoyText(m.yoy.fob)) + "</td>" +
        '<td class="num">' + esc(nTons(m.kg)) + '</td><td class="num">' + esc(yoyText(m.yoy.kg)) + "</td>" +
        '<td class="num">' + esc(nPrice(m.unit_price, m.unit_price_reason)) + flagBadge(m.price_flag) +
        '</td><td class="num">' + esc(yoyText(m.yoy.unit_price)) + "</td></tr>";
    });
    return '<div class="table-wrap"><table class="table"><caption>' + esc(caption) + " · 단가 확인 필요 기준: " + esc(d.outlier.rule) + "</caption><thead><tr>" +
      '<th scope="col">월</th><th scope="col" class="num">수입액 (USD)</th><th scope="col" class="num">전년 동월 대비</th><th scope="col" class="num">수입량 (t)</th>' +
      '<th scope="col" class="num">전년 동월 대비</th><th scope="col" class="num">평균 수입단가 (USD/kg)</th><th scope="col" class="num">전년 동월 대비</th>' +
      "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>";
  }

  function sourcesHtml(d) {
    const src = d.sources[0];
    const cache = { fresh: "이번 조회에서 받음", cached: "오늘 받은 자료 재사용", stale: "이전 자료 사용(최신 조회 실패)" }[src.cache_status];
    let html = '<section class="ma-section" aria-labelledby="market_analysis-s5"><h3 class="ma-h3" id="market_analysis-s5">⑤ 근거 자료</h3><ul class="ma-sources">';
    html += "<li><strong>" + esc(src.name) + "</strong> · " + linkHtml(src.url) + "<br>" +
      esc("지표: " + src.metrics + " · 자료 갱신일 " + (src.data_updated || "확인 안 됨") + " · 최신 제공 월 " + (src.latest_month || "확인 안 됨") +
        " · 자료 받은 시각 " + kstTime(src.fetched_at) + " · " + cache) + "</li>";
    return html + "</ul></section>";
  }

  /* ---------- 그래프 (SVG, 단일 계열 → 범례 없이 제목으로 지표 표시) ---------- */
  resultBox.addEventListener("change", function (event) {
    if (event.target.name === "market_analysis-metric") {
      chartMetric = event.target.value;
      drawChart();
    }
  });

  function niceMax(v) {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    const n = v / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
  }

  function axisText(v, metric) {
    if (metric === "fob") {
      if (v >= 1e6) return fmt1.format(v / 1e6) + "M";
      if (v >= 1e3) return fmt1.format(v / 1e3) + "K";
      return fmtInt.format(v);
    }
    if (metric === "kg") return fmtInt.format(v);
    return fmt2.format(v);
  }

  function drawChart() {
    const fig = resultBox.querySelector("[data-ma-chart]");
    if (!fig || !lastResult) return;
    const metric = METRICS[chartMetric];
    const months = lastResult.monthly;
    const W = 720, H = 280, L = 64, R = 16, T = 16, B = 40;
    const values = months.map(function (m) { return m.has_record ? metric.value(m) : null; });
    const max = niceMax(Math.max.apply(null, values.filter(function (v) { return v != null; }).concat([0])));
    const step = (W - L - R) / months.length;
    const y = function (v) { return T + (H - T - B) * (1 - v / max); };
    let svg = '<svg viewBox="0 0 ' + W + " " + H + '" class="ma-svg" role="img" aria-labelledby="market_analysis-chart-title">';
    svg += '<title id="market_analysis-chart-title">' + esc(metric.label + " 월별 추이 (" + metric.unit + ")") + "</title>";
    for (let i = 0; i <= 4; i++) {
      const v = max * i / 4, yy = y(v);
      svg += '<line class="ma-grid" x1="' + L + '" x2="' + (W - R) + '" y1="' + yy + '" y2="' + yy + '"/>';
      svg += '<text class="ma-axis" x="' + (L - 8) + '" y="' + (yy + 4) + '" text-anchor="end">' + esc(axisText(v, chartMetric)) + "</text>";
    }
    const labelEvery = Math.max(1, Math.ceil(months.length / 8));
    const isLine = chartMetric === "unit_price";
    let path = "";
    let penDown = false; // 값이 없는 달에서 선을 끊습니다.
    months.forEach(function (m, i) {
      const cx = L + step * i + step / 2;
      const v = values[i];
      if (i % labelEvery === 0) svg += '<text class="ma-axis" x="' + cx + '" y="' + (H - B + 18) + '" text-anchor="middle">' + m.month + "</text>";
      if (v == null) { penDown = false; return; }
      if (isLine) {
        path += (penDown ? "L" : "M") + cx.toFixed(1) + "," + y(v).toFixed(1);
        penDown = true;
      } else {
        const bw = Math.max(2, step - 2), top = y(v), h = (H - B) - top;
        const r = Math.min(4, bw / 2, h);
        const x0 = cx - bw / 2, x1 = cx + bw / 2, base = H - B;
        // 위쪽 모서리만 둥글게(기준선 쪽은 각지게)
        svg += '<path class="ma-bar" d="M' + x0 + "," + base + "V" + (top + r) + "Q" + x0 + "," + top + " " + (x0 + r) + "," + top +
          "H" + (x1 - r) + "Q" + x1 + "," + top + " " + x1 + "," + (top + r) + "V" + base + 'Z"/>';
      }
    });
    if (isLine) {
      if (path) svg += '<path class="ma-line" d="' + path + '"/>';
      months.forEach(function (m, i) {
        if (values[i] == null) return;
        const cx = L + step * i + step / 2;
        svg += '<circle class="ma-dot' + (m.price_flag ? " ma-dot-flag" : "") + '" cx="' + cx + '" cy="' + y(values[i]) + '" r="' + (m.price_flag ? 5 : 3) + '"/>';
      });
    }
    svg += '<line class="ma-baseline" x1="' + L + '" x2="' + (W - R) + '" y1="' + (H - B) + '" y2="' + (H - B) + '"/>';
    months.forEach(function (m, i) {
      svg += '<rect class="ma-hit" data-i="' + i + '" x="' + (L + step * i) + '" y="' + T + '" width="' + step + '" height="' + (H - T - B) + '"/>';
    });
    svg += "</svg>";
    fig.innerHTML = '<figcaption class="ma-chart-title">' + esc(metric.label + " 월별 추이 (" + metric.unit + ")") + "</figcaption>" + svg +
      '<div class="ma-tooltip" role="status" hidden></div>' +
      (isLine ? '<p class="field-hint">큰 점은 \'확인 필요\' 단가입니다(중앙값의 ½ 미만 또는 2배 초과). 끊긴 구간은 기록이 없거나 계산 불가인 달입니다.</p>' : '<p class="field-hint">막대가 없는 달은 수입 기록이 없는 달입니다.</p>');
    bindTooltip(fig, months, metric);
  }

  function bindTooltip(fig, months, metric) {
    const tip = fig.querySelector(".ma-tooltip");
    const svg = fig.querySelector("svg");
    svg.addEventListener("pointermove", function (event) {
      const hit = event.target.closest(".ma-hit");
      if (!hit) { tip.hidden = true; return; }
      const m = months[Number(hit.dataset.i)];
      let text;
      if (!m.has_record) text = "기록 없음";
      else {
        const v = metric.value(m);
        const reason = chartMetric === "unit_price" && v == null ? " (" + m.unit_price_reason + ")" : "";
        text = metric.text(v) + reason + " · 전년 동월 대비 " + yoyText(m.yoy[chartMetric]) + (m.price_flag && chartMetric === "unit_price" ? " · 확인 필요" : "");
      }
      tip.innerHTML = "<strong>" + esc(m.month) + "</strong><br>" + esc(text);
      tip.hidden = false;
      const box = fig.getBoundingClientRect();
      const x = Math.min(event.clientX - box.left + 12, box.width - tip.offsetWidth - 4);
      tip.style.left = Math.max(4, x) + "px";
      tip.style.top = (event.clientY - box.top + 12) + "px";
    });
    svg.addEventListener("pointerleave", function () { tip.hidden = true; });
  }

  /* ---------- ⑥ 바이어 목록 (기준 자료 파일, 첫 5곳만 펼쳐 표시) ---------- */
  const buyersBox = panel.querySelector("[data-ma-buyers]");
  const BUYERS_SHOWN = 5;

  function buyerRow(c, i) {
    const name = esc(c.razao_social) + (c.nome_fantasia ? '<br><span class="field-hint">' + esc(c.nome_fantasia) + "</span>" : "");
    const ev = c.evidence.length ? c.evidence.map(function (e) {
      return linkHtml(e.url, e.title) + '<br><span class="field-hint">확인 ' + esc(e.checked_at) + "</span>";
    }).join("<br>") : "—";
    const contact = c.phones.map(esc).concat(c.domain ? ["도메인 " + esc(c.domain)] : []).join("<br>") || "등록 없음";
    return "<tr><td>" + (i + 1) + "</td><td>" + name + "<br><span class=\"field-hint\">CNPJ " + esc(c.cnpj) + "</span></td><td>" +
      esc((c.uf || "") + " · " + (c.municipio || "")) + "</td><td>" + esc(c.cnae + " " + (c.cnae_desc || "")) + "</td><td>" +
      contact + "</td><td>" + ev + "</td></tr>";
  }

  function buyerTable(rows, offset, caption) {
    return '<div class="table-wrap"><table class="table"><caption>' + esc(caption) + "</caption><thead><tr>" +
      '<th scope="col">#</th><th scope="col">회사명</th><th scope="col">지역(주·시)</th><th scope="col">업종(CNAE)</th>' +
      '<th scope="col">법인 대표 전화 · 회사 도메인</th><th scope="col">재생·T2T 근거</th></tr></thead><tbody>' +
      rows.map(function (c, i) { return buyerRow(c, offset + i); }).join("") + "</tbody></table></div>";
  }

  function renderBuyers(d) {
    let html = d.notes.map(function (n) { return '<div class="notice notice-info"><p>' + esc(n) + "</p></div>"; }).join("");
    if (!d.ready) {
      buyersBox.innerHTML = html + '<div class="empty-state"><p class="empty-state-title">기준 자료가 아직 없습니다</p>' +
        "<p>buyer_data_builder로 국세청 공개 자료에서 목록을 만든 뒤 표시됩니다.</p></div>";
      return;
    }
    const list = d.companies;
    html += '<p class="field-hint">' + esc("전체 " + list.length + "곳 · 재생·T2T 근거 " + d.counts.with_evidence + "곳" +
      (d.counts.with_evidence ? "" : "(검토된 근거 없음)") + " · 조건: 주 업종 대상 CNAE, 활성, 법인, 규모 '" + d.filters.porte + "'") + "</p>";
    html += buyerTable(list.slice(0, BUYERS_SHOWN), 0, "바이어 목록 · 첫 " + Math.min(BUYERS_SHOWN, list.length) + "곳");
    if (list.length > BUYERS_SHOWN) {
      html += '<details class="ma-details"><summary>나머지 ' + (list.length - BUYERS_SHOWN) + "곳 보기</summary>" +
        buyerTable(list.slice(BUYERS_SHOWN), BUYERS_SHOWN, "바이어 목록 · 나머지") + "</details>";
    }
    html += '<p class="field-hint">출처: ' + esc(d.source.name) + " · " + linkHtml(d.source.url) + " · " +
      esc("자료 기준월 " + d.source.reference_month + " · 생성 " + kstTime(d.source.generated_at)) + "</p>";
    buyersBox.innerHTML = html;
  }

  async function loadBuyers() {
    try {
      const res = await fetch("/api/market-analysis/buyers");
      const body = await res.json();
      if (!body.ok) throw new Error();
      renderBuyers(body.data);
    } catch (e) {
      buyersBox.innerHTML = '<div class="notice notice-danger" role="alert"><p>바이어 목록을 불러오지 못했습니다. 새로고침해 주세요.</p></div>';
    }
  }

  loadMeta();
  loadBuyers();
})();
