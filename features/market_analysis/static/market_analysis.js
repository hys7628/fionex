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
  const resultTitle = panel.querySelector("#market_analysis-result-title");
  const formTitle = panel.querySelector("#market_analysis-input-title");
  const resultView = panel.querySelector('[data-ma-view="result"]');
  const stepBar = panel.querySelector(".ma-step-bar");
  const toResultBtn = panel.querySelector("[data-ma-to-result]");
  const querySummary = panel.querySelector("[data-ma-query-summary]");
  const statusLive = panel.querySelector("[data-ma-status]");
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
  const pdfMessage = panel.querySelector("[data-ma-pdf-message]");

  let meta = null;
  let busy = false;
  let lastResult = null;  // 통계(analyze 응답)
  let lastAi = null;      // AI 분석(ai 응답)
  let aiBusy = false;
  let pdfBusy = false;    // PDF 요청 중(조회·AI 분석이 끝나도 PDF 버튼을 다시 켜지 않게 함)
  // 다운로드 요청 안내는 잠깐만 보여 줍니다(Home 일일 브리핑과 같은 4초). 오류 안내는 다음 시도 때까지 둡니다.
  const PDF_SUCCESS_MS = 4000;
  let pdfMessageTimer = null;
  // fetch 거부(TypeError)·응답 해석 실패 같은 브라우저 오류 원문은 화면에 쓰지 않습니다.
  const CONNECTION_ERROR = "서버에 연결하지 못했거나 응답을 읽지 못했습니다.";
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

  // 화면낭독기용 짧은 상태 문장. 같은 문장을 다시 알릴 수 있도록 비운 뒤 다음 차례에 넣습니다.
  function announce(text) {
    statusLive.textContent = "";
    if (text) setTimeout(function () { statusLive.textContent = text; }, 50);
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
    updateBriefButtons();  // AI 설정 여부가 늦게 확인되면 바이어 'AI 브리핑' 버튼 상태를 맞춤
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

  // button: 누른 버튼(분석 실행 또는 다시 불러오기). 그 버튼만 '작업 중' 문구로 바꿉니다.
  function setBusy(value, button) {
    busy = value;
    submitBtn.disabled = value;
    refreshBtn.disabled = value;
    if (value) AppShell.ui.setButtonBusy(button, button === refreshBtn ? "불러오는 중..." : "분석 중...");
    else { AppShell.ui.setButtonBusy(submitBtn, null); AppShell.ui.setButtonBusy(refreshBtn, null); }
    resultBox.setAttribute("aria-busy", value ? "true" : "false");
    updatePdfButton();
  }

  // 시장 통계 화면 전환: "form"(① 조회 조건) / "result"(② 분석 결과). focusEl이 있으면 그 제목에 초점, 화면은 그 화면 맨 위부터.
  function showView(name, focusEl) {
    form.hidden = name !== "form";
    resultView.hidden = name !== "result";
    toResultBtn.hidden = !lastResult;
    if (!focusEl) return;
    AppShell.ui.focusResult(focusEl, { scroll: false });
    (name === "result" ? stepBar : form).scrollIntoView({ block: "start", behavior: "auto" });
  }

  function summaryText(payload) {
    const n = payload.countries.length;
    return (payload.code_system === "hs6" ? "HS " : "NCM ") + payload.code + " · " + payload.from + " ~ " + payload.to + " · " +
      (n ? "공급국 " + n + "곳 비교" : "전체 국가");
  }

  async function run(refresh) {
    if (busy) return;
    clearErrors();
    const payload = collect(refresh);
    const localErrors = clientValidate(payload);
    if (Object.keys(localErrors).length) { showView("form"); showFieldErrors(localErrors); return; }

    querySummary.textContent = summaryText(payload);
    showView("result", resultTitle);  // 결과 화면으로 넘어가서 불러오는 중 표시
    setBusy(true, refresh ? refreshBtn : submitBtn);
    let failed = false;
    announce("ComexStat 자료를 불러오는 중입니다.");
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
          announce("");
          showView("form");
          showFieldErrors(body.error.fields);
          return;
        }
        throw body.error;
      }
      lastResult = body.data;
      lastAi = null;
      showPdfMessage(null);  // 이전 결과에 대한 PDF 안내를 새 결과에 남기지 않음
      renderResult(body.data);
      refreshBtn.hidden = false;
      AppShell.work.setResult(FEATURE_ID, true);
      updatePdfButton();
      refreshAiPanel();
      // 결과 화면으로 넘어갈 때 이미 결과 제목에 초점을 두었습니다. 그사이 사용자가 결과 화면 안 다른 곳으로 옮겼으면 그대로 둡니다(결과 전체는 낭독하지 않음).
      const moved = AppShell.ui.focusResult(resultTitle, { scroll: false, from: [resultView] });
      announce("분석 결과가 준비되었습니다." + (moved ? " 결과 제목으로 이동했습니다." : ""));
    } catch (err) {
      announce("");
      resultBox.innerHTML = previous;
      // 서버 오류 객체({code, message})의 고정 문장만 쓰고, 브라우저·스크립트 오류(Error) 원문은 쓰지 않습니다.
      const serverMessage = err && !(err instanceof Error) && err.message;
      // 실패하면 조회 조건 화면으로 돌아가 오류 안내(role=alert)를 보여 줍니다(보이는 상태에서 넣어야 읽힘). 이전 결과가 있으면 '분석 결과 보기'로 볼 수 있습니다.
      showView("form");
      showFormError("자료 조회 실패", serverMessage || CONNECTION_ERROR + " 입력은 그대로이며 다시 실행할 수 있습니다.");
      failed = true;
    } finally {
      setBusy(false);
    }
    // 다시 시도하기 쉽게 '분석 실행'에 초점(오류 안내 바로 아래). 결과 화면의 '다시 불러오기'에서 실패해도 같음.
    if (failed) {
      submitBtn.focus({ preventScroll: true });
      formError.scrollIntoView({ block: "nearest", behavior: "auto" });
      submitBtn.scrollIntoView({ block: "nearest", behavior: "auto" });
    }
  }

  form.addEventListener("submit", function () { run(false); }); // 기본 제출은 공통 shell이 막음
  refreshBtn.addEventListener("click", function () { run(true); });
  panel.querySelector("[data-ma-to-form]").addEventListener("click", function () { showView("form", formTitle); });
  toResultBtn.addEventListener("click", function () { showView("result", resultTitle); });

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

  // 결과 ①~⑤는 하위 탭으로 하나씩 봅니다(아래 '← 이전 / 다음 →'으로도 넘김). 닫는 쪽은 "</section>".
  // shown이면 탭 없이 바로 보임(조회 결과가 없어 ⑤ 근거 자료만 있을 때).
  const RESULT_TABS = [["s1", "① 핵심 수치"], ["s2", "② 시장 추세"], ["s3", "③ 공급국"], ["s4", "④ AI 분석"], ["s5", "⑤ 근거 자료"]];
  let selectResultTab = null;

  function paneOpen(id, title, shown) {
    return '<section class="ma-section ma-rpane"' + (shown ? "" : ' role="tabpanel" id="market_analysis-rpane-' + id +
      '" aria-labelledby="market_analysis-rtab-' + id + '" hidden') + ' data-ma-rpane="' + id + '"><h3 class="ma-h3" id="market_analysis-' + id + '">' +
      esc(title) + "</h3>";
  }

  function resultTabsHtml() {
    return '<div class="ma-subtabs ma-result-tabs" role="tablist" aria-label="분석 결과 항목">' + RESULT_TABS.map(function (t) {
      return '<button type="button" class="ma-subtab" role="tab" id="market_analysis-rtab-' + t[0] + '" aria-controls="market_analysis-rpane-' + t[0] +
        '" aria-selected="false" tabindex="-1" data-ma-rtab="' + t[0] + '">' + esc(t[1]) + "</button>";
    }).join("") + "</div>";
  }

  function pagerHtml() {
    return '<div class="ma-pager" data-ma-pager><button type="button" class="btn btn-secondary" data-ma-rstep="-1"></button>' +
      '<span class="ma-pager-pos" data-ma-pager-pos></span><button type="button" class="btn btn-secondary" data-ma-rstep="1"></button></div>';
  }

  // 결과를 새로 그린 뒤 탭을 연결하고 ① 핵심 수치부터 보여 줍니다.
  function setupResultTabs() {
    const list = Array.from(resultBox.querySelectorAll("[data-ma-rtab]"));
    if (!list.length) { selectResultTab = null; return; }
    selectResultTab = bindTabs(list, function (t) { return resultBox.querySelector('[data-ma-rpane="' + t.dataset.maRtab + '"]'); }, updatePager);
    selectResultTab(list[0], false);
  }

  function updatePager(tab) {
    if (tab.dataset.maRtab === "s2") drawChart();  // ② 탭이 보일 때 실제 칸 폭으로 다시 그림
    const list = Array.from(resultBox.querySelectorAll("[data-ma-rtab]"));
    const i = list.indexOf(tab);
    // 좁은 화면에서 탭 줄이 가로로 넘치면 선택한 탭이 보이게 탭 줄만 옮깁니다(페이지 세로 스크롤은 그대로).
    const bar = tab.parentElement;
    if (tab.offsetLeft < bar.scrollLeft) bar.scrollLeft = tab.offsetLeft;
    else if (tab.offsetLeft + tab.offsetWidth > bar.scrollLeft + bar.clientWidth) bar.scrollLeft = tab.offsetLeft + tab.offsetWidth - bar.clientWidth;
    resultBox.querySelector("[data-ma-pager-pos]").textContent = (i + 1) + " / " + list.length;
    resultBox.querySelectorAll("[data-ma-rstep]").forEach(function (b) {
      const next = list[i + Number(b.dataset.maRstep)];
      b.disabled = !next;
      b.textContent = Number(b.dataset.maRstep) < 0 ? "← 이전" + (next ? ": " + next.textContent : "") : "다음" + (next ? ": " + next.textContent : "") + " →";
    });
  }

  // '← 이전 / 다음 →': 누른 버튼에 초점을 두고(끝이라 비활성이 되면 반대쪽 버튼), 새 항목 머리가 화면 밖이면 탭 줄로 올립니다.
  function stepResult(button) {
    const list = Array.from(resultBox.querySelectorAll("[data-ma-rtab]"));
    const cur = list.findIndex(function (t) { return t.getAttribute("aria-selected") === "true"; });
    const next = list[cur + Number(button.dataset.maRstep)];
    if (!next) return;
    selectResultTab(next, false);
    if (button.disabled) resultBox.querySelector('[data-ma-rstep="' + (-Number(button.dataset.maRstep)) + '"]').focus();
    const bar = resultBox.querySelector(".ma-result-tabs");
    if (bar.getBoundingClientRect().top < 0) bar.scrollIntoView({ block: "start", behavior: "auto" });
    announce(next.textContent + " 항목을 표시합니다.");
  }

  function renderResult(d) {
    const q = d.query, s = d.summary, src = d.sources[0];
    const caption = "출처: ComexStat · 브라질 수입 · " + q.code_system_label + " " + q.code + " · " + q.from + "~" + q.to;
    let html = "";

    html += '<div class="ma-query">' + badge("neutral", "브라질 수입") + " " +
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
      html += sourcesHtml(d, true);
      resultBox.innerHTML = html;
      setupResultTabs();
      return;
    }

    html += resultTabsHtml();
    // ① 핵심 수치
    html += paneOpen("s1", "① 핵심 수치");
    html += '<div class="ma-tiles">' +
      tile("수입액 (FOB)", usd(s.fob), s.yoy.fob) +
      tile("수입량 (순중량)", tons(s.kg), s.yoy.kg) +
      tile("평균 수입단가 (FOB, USD/kg)", s.unit_price == null ? NA + " (" + s.unit_price_reason + ")" : price(s.unit_price), s.yoy.unit_price) +
      "</div>";
    html += '<p class="field-hint">전년 동기: ' + esc(s.prior_period.from + " ~ " + s.prior_period.to) + ". 증감률 = (현재 − 전년 동기) ÷ 전년 동기 × 100. 평균 수입단가 = FOB 합계 ÷ 순중량 합계.</p></section>";

    // ② 시장 추세
    html += paneOpen("s2", "② 시장 추세 (월별)");
    html += '<div class="ma-metric-switch" role="radiogroup" aria-label="그래프 지표" data-work-ignore>' +
      Object.keys(METRICS).map(function (k) {
        return '<label class="choice"><input type="radio" name="market_analysis-metric" value="' + k + '"' + (k === chartMetric ? " checked" : "") + "> " + esc(METRICS[k].label) + "</label>";
      }).join("") + "</div>";
    html += '<figure class="ma-chart" data-ma-chart></figure>';
    html += "<details class=\"ma-details\"><summary>월별 상세 표 보기</summary>" + monthlyTable(d, caption) + "</details></section>";

    // ③ 공급국
    html += paneOpen("s3", "③ 공급국 비교");
    html += '<p class="field-hint">수입액 기준 순위. 비중의 분모는 같은 품목·기간의 브라질 전체 수입액입니다. 공급국은 ComexStat 기준 원산지 국가이며 판매 회사의 국가가 아닙니다(MDIC 통계 이용 매뉴얼). 기간 내 공급국 ' + d.suppliers.count + "개국.</p>";
    html += koreaHtml(d.suppliers);
    html += supplierTable(d.suppliers.top, caption + " · 상위 " + d.suppliers.top.length + "개국");
    if (d.suppliers.selected.length) {
      html += '<h4 class="ma-h4">선택한 공급국</h4>' + supplierTable(d.suppliers.selected, caption + " · 선택한 공급국 (비중은 전체 시장 기준)");
    }
    html += "</section>";

    // ④ AI 분석(사용자가 직접 실행하는 유료 호출)
    html += paneOpen("s4", "④ AI 분석") + '<div data-ma-ai>' + aiIdleHtml() + "</div></section>";

    html += sourcesHtml(d) + pagerHtml();
    resultBox.innerHTML = html;
    setupResultTabs();
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
    // 실행 버튼이 이 블록과 함께 다시 그려져 초점이 사라지므로, 감싸는 '④ AI 분석' 탭 패널에 초점을 둡니다.
    const region = box.closest("[data-ma-rpane]") || box;
    box.innerHTML = '<div class="empty-state"><span class="spinner" aria-hidden="true"></span><p class="empty-state-title">AI 분석 중입니다</p>' +
      "<p>초안 작성 후 5차례 검토를 차례로 진행합니다(1분 안팎). 이 탭을 새로고침하지 마세요.</p></div>";
    AppShell.ui.focusResult(region, { scroll: false, from: [region] });
    announce("AI 분석을 시작했습니다. 1분 안팎 걸립니다.");
    let done = "";
    try {
      const res = await fetch("/api/market-analysis/ai", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bundle_id: lastResult.bundle_id }),
      });
      let body = null;
      try { body = await res.json(); } catch (e) { body = null; }
      if (!body || typeof body.ok !== "boolean") throw new Error("unreadable");
      if (!body.ok) throw body.error;
      lastAi = body.data;
      box.innerHTML = aiHtml(body.data);
      done = "AI 분석 결과가 준비되었습니다.";
    } catch (err) {
      // 서버 오류 객체의 고정 문장만 쓰고, 브라우저 오류 원문(Failed to fetch 등)은 쓰지 않습니다.
      const message = err && !(err instanceof Error) && err.message
        ? err.message
        : CONNECTION_ERROR + " 이미 보낸 요청의 처리·요금이 취소되었는지는 보장할 수 없습니다.";
      box.innerHTML = (previous || "") + '<div class="notice notice-danger" role="alert"><p class="notice-title">AI 분석을 실행하지 못했습니다</p><p>' +
        esc(message) + "</p></div>" + (previous ? "" : aiIdleHtml());
    } finally {
      aiBusy = false;
      box.setAttribute("aria-busy", "false");
      refreshAiPanel();
      updatePdfButton();
    }
    // 결과·오류 시작점(④ 영역)에 초점을 두고 짧게 알립니다. 오류 문장은 notice의 role=alert가 읽습니다.
    AppShell.ui.focusResult(region, { scroll: "nearest", from: [region] });
    announce(done);
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
    const ready = !!lastResult && !busy && !aiBusy && !pdfBusy;
    pdfBtn.disabled = !ready;
    pdfHint.textContent = !lastResult ? "분석 결과가 생기면 화면 내용 그대로 A4 PDF로 받을 수 있습니다."
      : pdfBusy ? "현재 화면 내용으로 PDF를 만들고 있습니다."
      : aiBusy ? "AI 분석이 끝나면 PDF를 받을 수 있습니다."
      : "현재 화면의 통계" + (lastAi ? "·AI 분석" : "") + "로 PDF를 만듭니다. 다시 조회하거나 분석하지 않습니다.";
  }

  // type: "success" | "danger" | null(지움). 성공은 PDF_SUCCESS_MS 뒤 사라지고 오류는 다음 시도까지 남습니다.
  function showPdfMessage(type, title, text) {
    clearTimeout(pdfMessageTimer);
    pdfMessage.replaceChildren();
    if (!type) return;
    const box = document.createElement("div");
    box.className = "notice notice-" + type;
    box.setAttribute("role", type === "danger" ? "alert" : "status");
    box.innerHTML = '<p class="notice-title">' + esc(title) + "</p>" + (text ? "<p>" + esc(text) + "</p>" : "");
    pdfMessage.append(box);
    if (type === "success") pdfMessageTimer = setTimeout(function () { box.remove(); }, PDF_SUCCESS_MS);
  }

  pdfBtn.addEventListener("click", async function () {
    if (pdfBusy || pdfBtn.disabled || !lastResult) return;  // 중복 요청 방지
    pdfBusy = true;
    AppShell.ui.setButtonBusy(pdfBtn, "PDF 준비 중...");
    showPdfMessage(null);
    updatePdfButton();
    const target = lastResult;
    try {
      const res = await fetch("/api/market-analysis/pdf", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stats: target, ai: lastAi }),
      });
      if (!res.ok || (res.headers.get("Content-Type") || "").indexOf("application/pdf") !== 0) {
        let msg = "서버에서 PDF를 받지 못했습니다.";
        try { msg = (await res.json()).error.message || msg; } catch (e) { /* JSON 아님: 기본 문장 */ }
        throw { message: msg };
      }
      const blob = await res.blob();
      const q = target.query;
      AppShell.work.downloadBlob(FEATURE_ID, blob, "market_analysis_" + q.code + "_" + q.from + "_" + q.to + ".pdf");
      // 머리글의 '다운로드 요청됨 · 저장 여부는 브라우저에서 확인' 표시를 띄우지 않습니다(2026-10-26 담당자 지시).
      // clear는 downloadBlob이 해제한 것과 같은 경고 상태에 다운로드 요청 표시만 추가로 끕니다(공통 코드 변경 없음).
      AppShell.work.clear(FEATURE_ID);
      showPdfMessage("success", "PDF 다운로드를 요청했습니다", "저장 여부는 브라우저의 다운로드 목록에서 확인해 주세요.");
    } catch (err) {
      const message = err && !(err instanceof Error) && err.message ? err.message : CONNECTION_ERROR;
      showPdfMessage("danger", "PDF를 만들지 못했습니다", message + " 결과는 화면에 그대로 있으며 다시 시도할 수 있습니다.");
    } finally {
      pdfBusy = false;
      AppShell.ui.setButtonBusy(pdfBtn, null);
      updatePdfButton();
    }
  });

  resultBox.addEventListener("click", function (event) {
    if (event.target.closest("[data-ma-ai-run]")) runAi();
    const step = event.target.closest("[data-ma-rstep]");
    if (step && !step.disabled) stepResult(step);
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

  function sourcesHtml(d, shown) {
    const src = d.sources[0];
    const cache = { fresh: "이번 조회에서 받음", cached: "오늘 받은 자료 재사용", stale: "이전 자료 사용(최신 조회 실패)" }[src.cache_status];
    let html = paneOpen("s5", "⑤ 근거 자료", shown) + '<ul class="ma-sources">';
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

  // 그래프 요약(화면 표시만): 기록 있는 달의 최고·최저·월평균과 마지막 달. 값은 받은 월별 자료에서 그대로 계산합니다.
  function chartStats(months, values, metric) {
    const rows = months.map(function (m, i) { return { month: m.month, v: values[i] }; }).filter(function (r) { return r.v != null; });
    if (!rows.length) return "";
    const hi = rows.reduce(function (a, b) { return b.v > a.v ? b : a; });
    const lo = rows.reduce(function (a, b) { return b.v < a.v ? b : a; });
    const avg = rows.reduce(function (a, b) { return a + b.v; }, 0) / rows.length;
    const last = rows[rows.length - 1];
    const item = function (label, value, sub) {
      return '<div class="ma-chart-stat"><span class="ma-chart-stat-label">' + esc(label) + '</span><span class="ma-chart-stat-value">' +
        esc(value) + '</span><span class="ma-chart-stat-sub">' + esc(sub) + "</span></div>";
    };
    return '<div class="ma-chart-stats">' +
      item("최근 달", metric.text(last.v), last.month) +
      item("최고", metric.text(hi.v), hi.month) +
      item("최저", metric.text(lo.v), lo.month) +
      item("월평균", metric.text(avg), "기록 있는 " + rows.length + "개월") + "</div>";
  }

  function drawChart() {
    const fig = resultBox.querySelector("[data-ma-chart]");
    if (!fig || !lastResult) return;
    const metric = METRICS[chartMetric];
    const months = lastResult.monthly;
    // 실제 칸 폭으로 그려 글자·막대가 화면 크기와 관계없이 같은 크기로 보이게 합니다(높이 고정).
    const W = fig.clientWidth > 0 ? Math.max(320, Math.round(fig.clientWidth - 42)) : 720;  // 숨겨진 탭이면 기본 폭, 보일 때 다시 그림
    const H = W < 520 ? 240 : 300, L = W < 520 ? 52 : 64, R = 16, T = 20, B = 44;
    const values = months.map(function (m) { return m.has_record ? metric.value(m) : null; });
    const present = values.filter(function (v) { return v != null; });
    const isLine = chartMetric === "unit_price";
    // 막대(수입액·수입량)는 0부터, 단가 선은 값 범위에 맞춘 눈금(작은 변화도 보이게)
    let min = 0, max = niceMax(Math.max.apply(null, present.concat([0])));
    if (isLine && present.length) {
      const hiV = Math.max.apply(null, present), loV = Math.min.apply(null, present);
      const tick = niceMax(Math.max(hiV - loV, hiV * 0.1) / 4);
      min = Math.max(0, Math.floor(loV / tick) * tick - tick);
      max = Math.ceil(hiV / tick) * tick + tick;
    }
    const avg = present.length ? present.reduce(function (a, b) { return a + b; }, 0) / present.length : null;
    const step = (W - L - R) / months.length;
    const y = function (v) { return T + (H - T - B) * (1 - (v - min) / (max - min)); };
    let svg = '<svg viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" class="ma-svg" role="img" aria-labelledby="market_analysis-chart-title">';
    svg += '<title id="market_analysis-chart-title">' + esc(metric.label + " 월별 추이 (" + metric.unit + ")") + "</title>";
    svg += '<defs><linearGradient id="market_analysis-bar-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="ma-fill-top"/><stop offset="1" class="ma-fill-bottom"/></linearGradient>' +
      '<linearGradient id="market_analysis-area-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="ma-area-top"/><stop offset="1" class="ma-area-bottom"/></linearGradient></defs>';
    // 해마다 번갈아 옅은 띠(연도 구분)와 1월 위치 연도 표시
    let bandStart = 0;
    months.forEach(function (m, i) {
      const next = months[i + 1];
      if (!next || next.month.slice(0, 4) !== m.month.slice(0, 4)) {
        const year = Number(m.month.slice(0, 4));
        if (year % 2 === 0) svg += '<rect class="ma-year-band" x="' + (L + step * bandStart) + '" y="' + T + '" width="' + step * (i + 1 - bandStart) + '" height="' + (H - T - B) + '"/>';
        if (step * (i + 1 - bandStart) >= 38) svg += '<text class="ma-axis ma-axis-year" x="' + (L + step * bandStart + 4) + '" y="' + (T + 12) + '">' + year + "</text>";  // 띠가 좁으면 연도 생략
        bandStart = i + 1;
      }
    });
    for (let i = 0; i <= 4; i++) {
      const v = min + (max - min) * i / 4, yy = y(v);
      svg += '<line class="ma-grid" x1="' + L + '" x2="' + (W - R) + '" y1="' + yy + '" y2="' + yy + '"/>';
      svg += '<text class="ma-axis" x="' + (L - 8) + '" y="' + (yy + 4) + '" text-anchor="end">' + esc(axisText(v, chartMetric)) + "</text>";
    }
    // x축: 칸 폭에 맞춰 몇 달마다 'YY.MM' 표시
    const labelEvery = Math.max(1, Math.ceil(months.length / Math.max(4, Math.floor((W - L - R) / 64))));
    let path = "", area = "", firstX = null, lastX = null;
    let penDown = false; // 값이 없는 달에서 선을 끊습니다.
    months.forEach(function (m, i) {
      const cx = L + step * i + step / 2;
      const v = values[i];
      if (i % labelEvery === 0) svg += '<text class="ma-axis" x="' + cx + '" y="' + (H - B + 20) + '" text-anchor="middle">' + m.month.slice(2).replace("-", ".") + "</text>";
      if (v == null) { penDown = false; return; }
      if (isLine) {
        path += (penDown ? "L" : "M") + cx.toFixed(1) + "," + y(v).toFixed(1);
        if (firstX === null) firstX = cx;
        lastX = cx;
        area += (area ? "L" : "M") + cx.toFixed(1) + "," + y(v).toFixed(1);
        penDown = true;
      } else {
        const bw = Math.max(2, Math.min(28, step * 0.72)), top = y(v), h = (H - B) - top;
        const r = Math.min(3, bw / 2, h);
        const x0 = cx - bw / 2, x1 = cx + bw / 2, base = H - B;
        // 위쪽 모서리만 둥글게(기준선 쪽은 각지게). 마지막 달은 진하게
        svg += '<path class="ma-bar' + (i === months.length - 1 ? " ma-bar-last" : "") + '" data-i="' + i + '" d="M' + x0 + "," + base + "V" + (top + r) + "Q" + x0 + "," + top + " " + (x0 + r) + "," + top +
          "H" + (x1 - r) + "Q" + x1 + "," + top + " " + x1 + "," + (top + r) + "V" + base + 'Z"/>';
      }
    });
    if (isLine && area) svg += '<path class="ma-area" d="' + area + "L" + lastX.toFixed(1) + "," + (H - B) + "L" + firstX.toFixed(1) + "," + (H - B) + 'Z"/>';
    if (isLine) {
      if (path) svg += '<path class="ma-line" d="' + path + '"/>';
      months.forEach(function (m, i) {
        if (values[i] == null) return;
        const cx = L + step * i + step / 2;
        svg += '<circle class="ma-dot' + (m.price_flag ? " ma-dot-flag" : "") + '" cx="' + cx + '" cy="' + y(values[i]) + '" r="' + (m.price_flag ? 5 : 3) + '"/>';
      });
    }
    // 월평균 점선
    if (avg != null) {
      const ya = y(avg);
      svg += '<line class="ma-avg" x1="' + L + '" x2="' + (W - R) + '" y1="' + ya + '" y2="' + ya + '"/>' +
        '<text class="ma-axis ma-avg-label" x="' + (L + 6) + '" y="' + (ya - 6) + '">월평균 ' + esc(axisText(avg, chartMetric)) + "</text>";
    }
    svg += '<line class="ma-baseline" x1="' + L + '" x2="' + (W - R) + '" y1="' + (H - B) + '" y2="' + (H - B) + '"/>';
    svg += '<line class="ma-cursor" x1="0" x2="0" y1="' + T + '" y2="' + (H - B) + '" hidden/>';
    months.forEach(function (m, i) {
      svg += '<rect class="ma-hit" data-i="' + i + '" x="' + (L + step * i) + '" y="' + T + '" width="' + step + '" height="' + (H - T - B) + '"/>';
    });
    svg += "</svg>";
    fig.innerHTML = '<figcaption class="ma-chart-title">' + esc(metric.label + " 월별 추이 (" + metric.unit + ")") + "</figcaption>" +
      chartStats(months, values, metric) + '<div class="ma-chart-plot">' + svg + "</div>" +
      '<div class="ma-tooltip" role="status" hidden></div>' +
      (isLine ? '<p class="field-hint">큰 점은 \'확인 필요\' 단가입니다(중앙값의 ½ 미만 또는 2배 초과). 끊긴 구간은 기록이 없거나 계산 불가인 달입니다.</p>' : '<p class="field-hint">막대가 없는 달은 수입 기록이 없는 달입니다. 진한 막대는 마지막 달, 점선은 월평균입니다.</p>');
    bindTooltip(fig, months, metric);
  }

  // 화면 폭이 바뀌면 칸 폭에 맞춰 다시 그립니다(자료 요청 없음).
  let chartResizeTimer = null;
  window.addEventListener("resize", function () {
    clearTimeout(chartResizeTimer);
    chartResizeTimer = setTimeout(function () {
      const fig = resultBox.querySelector("[data-ma-chart]");
      if (fig && fig.offsetParent) drawChart();
    }, 150);
  });

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
      const cursor = svg.querySelector(".ma-cursor");
      const cx = Number(hit.getAttribute("x")) + Number(hit.getAttribute("width")) / 2;
      cursor.setAttribute("x1", cx);
      cursor.setAttribute("x2", cx);
      cursor.removeAttribute("hidden");
      svg.querySelectorAll(".ma-bar-hover").forEach(function (b) { b.classList.remove("ma-bar-hover"); });
      const bar = svg.querySelector('.ma-bar[data-i="' + hit.dataset.i + '"]');
      if (bar) bar.classList.add("ma-bar-hover");
      const box = fig.getBoundingClientRect();
      const x = Math.min(event.clientX - box.left + 12, box.width - tip.offsetWidth - 4);
      tip.style.left = Math.max(4, x) + "px";
      tip.style.top = (event.clientY - box.top + 12) + "px";
    });
    svg.addEventListener("pointerleave", function () {
      tip.hidden = true;
      svg.querySelector(".ma-cursor").setAttribute("hidden", "");
      svg.querySelectorAll(".ma-bar-hover").forEach(function (b) { b.classList.remove("ma-bar-hover"); });
    });
  }

  /* ---------- ⑥ 바이어 목록 (기준 자료 파일, 첫 5곳만 펼쳐 표시) ---------- */
  const buyersBox = panel.querySelector("[data-ma-buyers]");
  const BUYERS_SHOWN = 5;

  // 대상 업종(CNAE) 짧은 한글 이름. 국세청 공식 명칭(포르투갈어)은 마우스를 올리면 보입니다.
  const CNAE_SHORT = {
    "1313800": "합성섬유 방적", "1314600": "재봉·자수실", "1321900": "면 직물", "1322700": "기타 천연섬유 직물",
    "1323500": "합성섬유 직물", "1330800": "니트 원단", "1340501": "날염·가공사(텍스처링)", "1340502": "표백·염색·연사",
  };

  function buyerRow(c, i) {
    const name = '<span class="ma-buyer-name">' + esc(c.razao_social) + "</span>" +
      (c.nome_fantasia && c.nome_fantasia !== c.razao_social ? '<br><span class="field-hint">' + esc(c.nome_fantasia) + "</span>" : "") +
      '<br><span class="field-hint">CNPJ ' + esc(c.cnpj) + "</span>";
    const ev = c.evidence.length ? c.evidence.map(function (e) {
      return linkHtml(e.url, e.title) + '<br><span class="field-hint">확인 ' + esc(e.checked_at) + "</span>";
    }).join("<br>") : '<span class="field-hint">없음</span>';
    const contact = c.phones.map(esc).concat(c.domain ? ['<span class="field-hint">' + esc(c.domain) + "</span>"] : []).join("<br>") ||
      '<span class="field-hint">등록 없음</span>';
    // 등급: 공개 규칙(코드) 결과와 근거 한 줄. 색은 보조이며 글자 A/B/C로 구분합니다.
    const grade = '<span class="ma-grade ma-grade-' + esc(c.grade) + '">' + esc(c.grade) + '</span><span class="visually-hidden">등급</span>' +
      '<br><span class="field-hint">' + esc(c.grade_reason) + "</span>";
    const hidden = '<span class="visually-hidden"> · ' + esc(c.razao_social) + "</span>";
    const brief = '<span class="ma-row-actions"><button type="button" class="btn btn-secondary ma-brief-btn" data-ma-inline="' + esc(c.cnpj) + '" aria-expanded="false">' +
      '<span data-ma-label>상세 보기</span>' + hidden + "</button>" +
      '<button type="button" class="btn btn-primary ma-brief-btn" data-ma-brief-open="' + esc(c.cnpj) + '" aria-haspopup="dialog" aria-describedby="market_analysis-briefing-row-hint">AI 브리핑' +
      hidden + "</button></span>";
    return "<tr><td class=\"num\">" + (i + 1) + "</td><td>" + name + '</td><td class="ma-grade-cell">' + grade + "</td><td>" + esc(c.uf || "") +
      '<br><span class="field-hint">' + esc(c.municipio || "") + "</span></td>" +
      '<td title="' + esc(c.cnae + " " + (c.cnae_desc || "")) + '">' + esc(CNAE_SHORT[c.cnae] || c.cnae_desc || c.cnae) + "</td><td>" +
      contact + "</td><td>" + ev + "</td><td>" + brief + "</td></tr>";
  }

  function buyerTable(rows, offset, caption) {
    return '<div class="table-wrap"><table class="table ma-buyer-table"><caption>' + esc(caption) + "</caption><thead><tr>" +
      '<th scope="col" class="num">#</th><th scope="col">회사명</th><th scope="col">등급 · 근거</th><th scope="col">지역</th><th scope="col">업종</th>' +
      '<th scope="col">전화 · 회사 도메인</th><th scope="col">재생·T2T 근거</th><th scope="col">상세 · AI 브리핑</th></tr></thead><tbody>' +
      rows.map(function (c, i) { return buyerRow(c, offset + i); }).join("") + "</tbody></table></div>";
  }

  // ⓘ 아이콘(장식). 그린 클레임 도움말 아이콘과 같은 모양
  const INFO_ICON = '<svg class="ma-info-icon" viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" focusable="false">' +
    '<circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="1.6"/>' +
    '<path d="M10 9.2v4.8" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>' +
    '<circle cx="10" cy="6.3" r="1.15" fill="currentColor"/></svg>';

  function renderBuyers(d) {
    // 안내 문구·선정 조건·출처는 '참고 사항'으로 접어 둡니다(2026-10-26 담당자 지시).
    let notes = d.notes.map(function (n) { return '<div class="notice notice-info"><p>' + esc(n) + "</p></div>"; }).join("");
    if (!d.ready) {
      buyersBox.innerHTML = '<details class="ma-details"><summary>참고 사항</summary>' + notes + "</details>" +
        '<div class="empty-state"><p class="empty-state-title">기준 자료가 아직 없습니다</p>' +
        "<p>buyer_data_builder로 국세청 공개 자료에서 목록을 만든 뒤 표시됩니다.</p></div>";
      return;
    }
    const list = d.companies;
    notes += '<p class="field-hint">' + esc("선정 조건: 주 업종이 원사·원단 제조 8개 업종, 영업 중, 법인(개인사업자 제외), 규모 '" + d.filters.porte +
      "', 외국 법인·파산·회생 절차 회사 제외") + "</p>";
    notes += '<p class="field-hint">출처: ' + esc(d.source.name) + " · " + linkHtml(d.source.url) + " · " +
      esc("자료 기준월 " + d.source.reference_month + " · 생성 " + kstTime(d.source.generated_at)) + "</p>";
    const g = d.counts.grades || {};
        // 개수 요약·등급 기준·규칙·참고 사항은 ⓘ 접힘 상자 하나에(2026-10-27). 등급별 개수는 아래 거르기 칩에도 보입니다.
    let html = '<details class="ma-info"><summary>' + INFO_ICON + "<span>등급 기준·참고 사항</span>" +
      '<span class="ma-info-brief">' + esc(fmtInt.format(list.length)) + "곳 · 재생·T2T 근거 " + esc(fmtInt.format(d.counts.with_evidence)) + "곳</span></summary>" +
      '<div class="ma-buyer-summary"><p><strong>' + esc(fmtInt.format(list.length)) + "곳</strong> · " +
      ["A", "B", "C"].map(function (k) { return '<span class="ma-grade ma-grade-' + k + '">' + k + "</span> " + esc(fmtInt.format(g[k] || 0)) + "곳"; }).join(" · ") +
      " · 재생·T2T 근거 " + esc(d.counts.with_evidence + "곳" + (d.counts.with_evidence ? "" : " (검토된 근거 없음)")) + "</p>" +
      '<p class="ma-grade-note">우선순위 등급: ' + esc(d.grade_note) + "</p>" +
      '<p class="ma-info-sub">등급 규칙</p><ul class="ma-grade-rules">' +
      d.grade_rules.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("") + "</ul>" +
      '<p class="ma-info-sub">참고 사항</p>' + notes + "</div></details>";
    // 검색·등급 거르기: 받은 목록에서만 거릅니다(추가 요청 없음). 보기 설정이라 작성 중 감지에서 제외(data-work-ignore).
    html += '<div class="ma-buyer-tools" role="search" aria-label="바이어 검색" data-work-ignore>' +
      '<div class="field ma-buyer-search"><label class="field-label" for="market_analysis-buyer-query">업체 검색</label>' +
      '<input class="input" id="market_analysis-buyer-query" type="search" autocomplete="off" maxlength="80" data-ma-buyer-query' +
      ' placeholder="회사명·상호·CNPJ·도시·주(SP)·업종" aria-describedby="market_analysis-buyer-count"></div>' +
      '<div class="ma-grade-filter" role="group" aria-label="등급으로 거르기">' +
      [["all", "전체"], ["A", "A"], ["B", "B"], ["C", "C"]].map(function (f) {
        return '<button type="button" class="ma-filter-chip" data-ma-grade-filter="' + f[0] + '" aria-pressed="' + (f[0] === "all") + '">' +
          (f[0] === "all" ? "전체" : '<span class="ma-grade ma-grade-' + f[0] + '">' + f[0] + "</span>") +
          '<span class="ma-filter-count">' + fmtInt.format(f[0] === "all" ? list.length : (g[f[0]] || 0)) + "</span>" +
          (f[0] === "all" ? "" : '<span class="visually-hidden">등급</span>') + "</button>";
      }).join("") + "</div></div>" +
      '<p class="ma-buyer-count" id="market_analysis-buyer-count" role="status" data-ma-buyer-count></p>' +
      '<p class="field-hint" id="market_analysis-briefing-row-hint">' + esc("'상세 보기'는 행 아래에 업체 정보를 펼칩니다. 'AI 브리핑'은 업체 상세와 브리핑을 창으로 열며, 받은 적 없는 업체는 바로 OpenAI를 1회 호출합니다(유료, 같은 업체는 다시 호출하지 않음).") + "</p>" +
      "<div data-ma-buyer-results></div>";
    buyersBox.innerHTML = html;
    buyerView.list = list.map(function (c) {
      return { c: c, hay: plainText([c.razao_social, c.nome_fantasia, c.cnpj, c.municipio, c.uf, c.cnae, c.cnae_label, c.cnae_desc, c.domain].join(" ")) };
    });
    renderBuyerResults();
  }

  /* ---------- 바이어 검색 ---------- */
  const buyerView = { list: [], rows: [], query: "", grade: "all" };
  const BUYERS_SHOWN_FILTERED = 20;
  let buyerSearchTimer = null;

  // 대소문자·포르투갈어 악센트(ã·ç 등)·CNPJ 기호(./-)를 무시하고 비교합니다.
  function plainText(value) {
    return String(value || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[./-]/g, "");
  }

  function renderBuyerResults() {
    const box = buyersBox.querySelector("[data-ma-buyer-results]");
    const countEl = buyersBox.querySelector("[data-ma-buyer-count]");
    if (!box) return;
    const words = plainText(buyerView.query).split(/\s+/).filter(Boolean);
    const filtered = !words.length && buyerView.grade === "all";
    const rows = buyerView.list.filter(function (x) {
      return (buyerView.grade === "all" || x.c.grade === buyerView.grade) && words.every(function (w) { return x.hay.indexOf(w) !== -1; });
    }).map(function (x) { return x.c; });
    buyerView.rows = rows;
    const total = buyerView.list.length;
    countEl.textContent = filtered ? "전체 " + fmtInt.format(total) + "곳 · 우선순위 등급순"
      : "검색 결과 " + fmtInt.format(rows.length) + "곳 / 전체 " + fmtInt.format(total) + "곳";
    if (!rows.length) {
      box.innerHTML = '<div class="empty-state"><p class="empty-state-title">조건에 맞는 업체가 없습니다</p>' +
        "<p>검색어를 줄이거나 등급을 '전체'로 바꿔 보세요. 회사명·상호·CNPJ·도시·주·업종으로 찾을 수 있습니다.</p></div>";
      updateBriefButtons();
      return;
    }
    const shown = filtered ? BUYERS_SHOWN : BUYERS_SHOWN_FILTERED;
    let html = buyerTable(rows.slice(0, shown), 0, (filtered ? "우선순위 등급순 · 첫 " : "검색 결과 · 첫 ") + Math.min(shown, rows.length) + "곳");
    if (rows.length > shown) {
      html += '<details class="ma-details"><summary>나머지 ' + fmtInt.format(rows.length - shown) + "곳 보기</summary>" +
        buyerTable(rows.slice(shown), shown, filtered ? "나머지 업체" : "나머지 검색 결과") + "</details>";
    }
    box.innerHTML = html;
    updateBriefButtons();
  }

  buyersBox.addEventListener("input", function (event) {
    if (!event.target.matches("[data-ma-buyer-query]")) return;
    clearTimeout(buyerSearchTimer);
    buyerSearchTimer = setTimeout(function () {
      buyerView.query = event.target.value.trim();
      renderBuyerResults();
    }, 150);
  });

  // 새로고침을 안내하지 않습니다(다른 탭의 작성 중 입력·결과가 사라짐). 같은 자리에서 다시 시도합니다.
  let buyersBusy = false;
  let buyersData = null;

  async function loadBuyers() {
    if (buyersBusy) return;
    buyersBusy = true;
    const retry = buyersBox.querySelector("[data-ma-buyers-retry]");
    if (retry) { retry.disabled = true; AppShell.ui.setButtonBusy(retry, "불러오는 중..."); }
    buyersBox.setAttribute("aria-busy", "true");
    let ok = false;
    try {
      const res = await fetch("/api/market-analysis/buyers");
      const body = await res.json();
      if (!body.ok) throw new Error();
      buyersData = body.data;
      if (dialog.open) dialog.close();
      renderBuyers(body.data);
      ok = true;
    } catch (e) {
      buyersBox.innerHTML = '<div class="notice notice-danger" role="alert"><p class="notice-title">바이어 목록을 불러오지 못했습니다</p>' +
        '<p>잠시 후 다시 시도해 주세요. 다른 화면의 입력과 결과는 그대로 있습니다.</p>' +
        '<button type="button" class="btn btn-secondary" data-ma-buyers-retry>바이어 목록 다시 불러오기</button></div>';
    } finally {
      buyersBusy = false;
      buyersBox.setAttribute("aria-busy", "false");
    }
    // 처음 자동 로딩은 초점을 옮기지 않습니다. 사용자가 재시도한 경우만 버튼이 사라진 자리를 이어 줍니다:
    // 성공 → 목록 제목, 다시 실패 → 새 재시도 버튼.
    if (retry) {
      AppShell.ui.focusResult(ok ? panel.querySelector("#market_analysis-buyers-title") : buyersBox.querySelector("[data-ma-buyers-retry]"),
        { scroll: false, from: [buyersBox] });
    }
  }

  buyersBox.addEventListener("click", function (event) {
    if (event.target.closest("[data-ma-buyers-retry]")) loadBuyers();
    const chip = event.target.closest("[data-ma-grade-filter]");
    if (chip) {
      buyerView.grade = chip.dataset.maGradeFilter;
      buyersBox.querySelectorAll("[data-ma-grade-filter]").forEach(function (b) { b.setAttribute("aria-pressed", String(b === chip)); });
      renderBuyerResults();
    }
    const inline = event.target.closest("[data-ma-inline]");
    if (inline) toggleInline(inline);
    const open = event.target.closest("[data-ma-brief-open]");
    if (open) openDialog(open.dataset.maBriefOpen);
  });

  /* ---------- 바이어별 AI 브리핑(유료 1회 호출) ---------- */
  const briefBox = panel.querySelector("[data-ma-briefing]");
  const briefTitle = panel.querySelector("#market_analysis-briefing-title");
  const briefStatus = panel.querySelector("[data-ma-briefing-status]");
  let briefBusy = false;

  function briefAnnounce(text) {
    briefStatus.textContent = "";
    if (text) setTimeout(function () { briefStatus.textContent = text; }, 50);
  }

  // 'AI 브리핑 받기'는 상세 화면 하나뿐입니다. 다른 업체 브리핑이 진행 중이면 잠가 동시에 여러 번 유료 호출하지 않게 합니다.
  const briefRunBtn = panel.querySelector("[data-ma-brief-run]");
  const briefRunHint = panel.querySelector("[data-ma-brief-run-hint]");
  const briefCache = {};      // 업체(CNPJ)별 마지막 브리핑(화면 메모리, 저장 안 함)
  let briefRunning = null;    // 진행 중인 업체 CNPJ

  function updateBriefButtons() {
    if (!briefRunBtn) return;
    if (!briefRunBtn.hasAttribute("aria-busy")) briefRunBtn.textContent = detailCnpj && briefCache[detailCnpj] ? "AI 브리핑 다시 받기" : "AI 브리핑 받기";
    briefRunBtn.disabled = briefBusy || !aiReady() || !detailCnpj;
    briefRunHint.textContent = !aiReady() ? "서버에 AI 설정(OpenAI 키·텍스트 모델)이 없어 지금은 받을 수 없습니다."
      : briefBusy && briefRunning !== detailCnpj ? "다른 업체의 브리핑을 만드는 중입니다. 끝난 뒤 받을 수 있습니다."
      : detailCnpj && briefCache[detailCnpj] ? "이미 받은 브리핑입니다. 같은 조회 조건이면 다시 받아도 추가 호출이 없습니다."
      : lastResult ? "시장 통계 조회 결과(" + lastResult.query.code + " · " + lastResult.query.from + "~" + lastResult.query.to + ")가 시장 맥락으로 들어갑니다."
      : "시장 통계를 먼저 조회하면 시장 맥락이 함께 들어갑니다(지금은 업체 정보만).";
  }

  function srcChips(sources) {
    return sources.map(function (s) {
      return '<a class="ma-src" href="' + esc(safeUrl(s.url) || "#") + '" target="_blank" rel="noopener noreferrer" title="' +
        esc(s.name + " · " + s.date) + '">' + esc(s.id) + '<span class="visually-hidden"> 출처: ' + esc(s.name) + " (새 탭)</span></a>";
    }).join(" ");
  }

  // 브리핑 화면(업체 상세 안): 시장 맥락 한 줄 → 넓은 화면 2열(왼쪽 회사 개요·시장 맥락 / 오른쪽 접근 포인트·예상 질문) →
  // 확인 안내 → 근거 부족·코드 검사로 뺀 문장·출처·사용량. 출처 칩은 문장 끝 작은 ID 링크입니다.
  function briefList(items, used, empty) {
    if (!items.length) return '<p class="field-hint">' + esc(empty) + "</p>";
    return '<ul class="ma-brief-list">' + items.map(function (p) {
      p.sources.forEach(function (x) { used[x.id] = x; });
      return "<li>" + esc(p.text) + " " + srcChips(p.sources) + "</li>";
    }).join("") + "</ul>";
  }

  function briefBlock(title, body) {
    return '<section class="ma-brief-block"><h3 class="ma-brief-block-title">' + esc(title) + "</h3>" + body + "</section>";
  }

  function briefingHtml(b) {
    const used = {};
    const market = b.market.included
      ? b.market.query.code_system_label + " " + b.market.query.code + " · " + b.market.query.from + "~" + b.market.query.to
      : "미포함";
    // 업체 정보는 상세 화면 위 업체 카드에 있으므로 여기서는 시장 맥락만 보여 줍니다(PDF에는 업체 표 포함).
    let html = '<p class="ma-brief-market"><span class="ma-brief-market-label">시장 맥락</span> ' + esc(market) +
      (b.market.included ? "" : ' <span class="field-hint">· ' + esc(b.market.note) + "</span>") + "</p>";
    const questions = b.questions.length ? '<div class="ma-qa-list">' + b.questions.map(function (q) {
      q.sources.forEach(function (x) { used[x.id] = x; });
      return '<div class="ma-qa"><p class="ma-qa-q"><span class="ma-qa-mark" aria-hidden="true">Q</span><span class="visually-hidden">질문: </span>' + esc(q.question) + "</p>" +
        '<p class="ma-qa-a"><span class="ma-qa-mark ma-qa-mark-a" aria-hidden="true">A</span><span class="visually-hidden">준비할 답: </span>' +
        esc(q.answer_direction) + " " + srcChips(q.sources) + "</p></div>";
    }).join("") + "</div>" : '<p class="field-hint">근거가 있는 질문이 없어 쓰지 않았습니다.</p>';
    html += '<div class="ma-brief-grid"><div class="ma-brief-col">' +
      briefBlock("회사 개요", briefList(b.sections.overview || [], used, "근거가 있는 내용이 없어 쓰지 않았습니다.")) +
      briefBlock("시장 맥락", briefList(b.sections.market_context || [], used,
        b.market.included ? "근거가 있는 내용이 없어 쓰지 않았습니다." : "시장 통계를 조회하지 않아 비어 있습니다.")) +
      '</div><div class="ma-brief-col">' +
      briefBlock("접근 포인트", briefList(b.sections.approach_points || [], used, "근거가 있는 내용이 없어 쓰지 않았습니다.")) +
      briefBlock("예상 질문", questions) + "</div></div>";
    html += '<div class="notice notice-info"><p class="notice-title">확인 안내</p><ul class="ma-brief-notes">' +
      b.notes.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") + "</ul></div>";
    if (b.gaps.length) html += '<p class="field-hint">근거 부족으로 쓰지 않은 내용: ' + esc(b.gaps.join("; ")) + "</p>";
    if (b.removed.length) {
      html += '<details class="ma-details"><summary>코드 검사로 뺀 문장 ' + b.removed.length + "개 보기</summary><ul class=\"ma-brief-list\">" +
        b.removed.map(function (r) { return "<li>" + esc(r.section + " · " + r.text) + '<br><span class="field-hint">' + esc(r.reason) + "</span></li>"; }).join("") +
        "</ul></details>";
    }
    const ids = Object.keys(used).sort();
    if (ids.length) {
      html += '<div class="ma-brief-sources"><p class="ma-brief-sources-title">출처</p><ul>' + ids.map(function (id) {
        const x = used[id];
        return '<li><span class="ma-src">' + esc(id) + "</span> " + linkHtml(x.url, x.name) + ' <span class="field-hint">' + esc(x.date) + "</span></li>";
      }).join("") + "</ul></div>";
    }
    const u = b.usage || {};
    html += '<p class="field-hint">' + esc((b.reused ? "이미 만든 브리핑을 다시 표시했습니다(추가 호출 없음) · " : "") +
      "모델 " + (u.model || "-") + " · 호출 " + (u.calls || 0) + "회 · 입력 " + (u.input_tokens || 0) + " / 출력 " + (u.output_tokens || 0) +
      " 토큰 · 소요 " + (u.seconds || 0) + "초" + (u.estimated_cost_usd != null ? " · 추정 비용 USD " + u.estimated_cost_usd : "") +
      " · 프롬프트 " + b.prompt_version + " · 생성 " + kstTime(b.generated_at)) + "</p>";
    return html;
  }

  /* ----- 브리핑 PDF: 서버가 보관한 브리핑(briefing_id)으로 만듭니다(AI 재호출 없음) ----- */
  const briefPdfBtn = panel.querySelector("[data-ma-brief-pdf]");
  const briefPdfHint = panel.querySelector("[data-ma-brief-pdf-hint]");
  const briefPdfMessage = panel.querySelector("[data-ma-brief-pdf-message]");
  let currentBriefing = null;
  let briefPdfBusy = false;
  let briefPdfTimer = null;

  function updateBriefPdf() {
    briefPdfBtn.disabled = !currentBriefing || briefBusy || briefPdfBusy;
    briefPdfHint.textContent = !currentBriefing ? "브리핑을 받으면 PDF로 내려받을 수 있습니다."
      : briefPdfBusy ? "브리핑 PDF를 만들고 있습니다."
      : briefBusy ? "새 브리핑이 끝나면 내려받을 수 있습니다."
      : "지금 보이는 '" + currentBriefing.company.razao_social + "' 브리핑을 PDF로 내려받습니다(다시 호출하지 않음).";
  }

  function showBriefPdfMessage(type, title, text) {
    clearTimeout(briefPdfTimer);
    briefPdfMessage.replaceChildren();
    if (!type) return;
    const box = document.createElement("div");
    box.className = "notice notice-" + type;
    box.setAttribute("role", type === "danger" ? "alert" : "status");
    box.innerHTML = '<p class="notice-title">' + esc(title) + "</p>" + (text ? "<p>" + esc(text) + "</p>" : "");
    briefPdfMessage.append(box);
    if (type === "success") briefPdfTimer = setTimeout(function () { box.remove(); }, PDF_SUCCESS_MS);
  }

  briefPdfBtn.addEventListener("click", async function () {
    if (briefPdfBusy || briefPdfBtn.disabled || !currentBriefing) return;
    briefPdfBusy = true;
    AppShell.ui.setButtonBusy(briefPdfBtn, "PDF 준비 중...");
    showBriefPdfMessage(null);
    updateBriefPdf();
    const target = currentBriefing;
    try {
      const res = await fetch("/api/market-analysis/buyer-briefing/pdf", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ briefing_id: target.briefing_id }),
      });
      if (!res.ok || (res.headers.get("Content-Type") || "").indexOf("application/pdf") !== 0) {
        let msg = "서버에서 PDF를 받지 못했습니다.";
        try { msg = (await res.json()).error.message || msg; } catch (e) { /* JSON 아님 */ }
        throw { message: msg };
      }
      const blob = await res.blob();
      const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "");
      AppShell.work.downloadBlob(FEATURE_ID, blob, match ? match[1] : "buyer_briefing_" + target.company.cnpj + ".pdf");
      AppShell.work.clear(FEATURE_ID);  // 시장 통계 PDF와 같이 머리글 '다운로드 요청됨' 표시를 띄우지 않음
      showBriefPdfMessage("success", "브리핑 PDF 다운로드를 요청했습니다", "저장 여부는 브라우저의 다운로드 목록에서 확인해 주세요.");
    } catch (err) {
      const message = err && !(err instanceof Error) && err.message ? err.message : CONNECTION_ERROR;
      showBriefPdfMessage("danger", "브리핑 PDF를 만들지 못했습니다", message + " 브리핑은 화면에 그대로 있으며 다시 시도할 수 있습니다.");
    } finally {
      briefPdfBusy = false;
      AppShell.ui.setButtonBusy(briefPdfBtn, null);
      updateBriefPdf();
    }
  });

  function briefEmptyHtml() {
    return '<div class="empty-state"><p class="empty-state-title">아직 이 업체의 브리핑이 없습니다</p>' +
      "<p>'AI 브리핑 받기'를 누르면 출처 있는 자료로 1쪽 브리핑을 만듭니다(OpenAI 1회, 유료).</p></div>";
  }

  // 지금 보고 있는 업체의 브리핑 영역을 그립니다(보관본이 있으면 다시 호출하지 않고 표시).
  function showBriefingFor(cnpj) {
    currentBriefing = briefCache[cnpj] || null;
    showBriefPdfMessage(null);
    if (briefRunning === cnpj) {
      briefBox.setAttribute("aria-busy", "true");
      briefBox.innerHTML = '<div class="empty-state"><span class="spinner" aria-hidden="true"></span><p class="empty-state-title">AI 브리핑을 만드는 중입니다</p><p>보통 10~30초 걸립니다.</p></div>';
    } else {
      briefBox.setAttribute("aria-busy", "false");
      briefBox.innerHTML = currentBriefing ? briefingHtml(currentBriefing) : briefEmptyHtml();
    }
    updateBriefButtons();
    updateBriefPdf();
  }

  async function runBriefing(cnpj, button) {
    if (briefBusy || !cnpj) return;
    if (!aiReady()) {
      briefBox.innerHTML = '<div class="notice notice-warning" role="status"><p class="notice-title">AI 브리핑 설정 필요</p><p>' +
        "서버에 AI 설정(OpenAI 키·텍스트 모델)이 없어 지금은 실행할 수 없습니다. 업체 정보와 등급은 그대로 볼 수 있습니다.</p></div>";
      AppShell.ui.focusResult(briefTitle, { scroll: "start", from: [dialog] });
      return;
    }
    const company = (findCompany(cnpj) || {}).razao_social || cnpj;
    briefBusy = true;
    briefRunning = cnpj;
    AppShell.ui.setButtonBusy(button, "브리핑 중...");
    showBriefingFor(cnpj);
    updateBriefBadge();
    briefAnnounce(company + " AI 브리핑을 만드는 중입니다.");
    let done = "";
    let errorHtml = "";
    try {
      const res = await fetch("/api/market-analysis/buyer-briefing", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cnpj: cnpj, bundle_id: lastResult ? lastResult.bundle_id : null }),
      });
      let body = null;
      try { body = await res.json(); } catch (e) { body = null; }
      if (!body || typeof body.ok !== "boolean") throw new Error("unreadable");
      if (!body.ok) throw body.error;
      briefCache[cnpj] = body.data;
      done = company + " AI 브리핑이 준비되었습니다. PDF로 내려받을 수 있습니다.";
    } catch (err) {
      const server = err && !(err instanceof Error) ? err : null;
      const config = server && server.needs_restart;
      const message = server && server.message ? server.message
        : CONNECTION_ERROR + " 이미 보낸 요청의 처리·요금이 취소되었는지는 보장할 수 없습니다.";
      errorHtml = '<div class="notice ' + (config ? "notice-warning" : "notice-danger") + '" role="' + (config ? "status" : "alert") + '">' +
        '<p class="notice-title">' + (config ? "AI 브리핑을 시작하지 않았습니다" : "AI 브리핑을 만들지 못했습니다") + "</p><p>" + esc(message) +
        (config ? "" : " 'AI 브리핑 받기'를 다시 눌러 시도할 수 있습니다.") + "</p>" + (server ? diagHtml(server.diagnostic) : "") + "</div>";
      done = company + " AI 브리핑을 만들지 못했습니다.";
    } finally {
      briefBusy = false;
      briefRunning = null;
      AppShell.ui.setButtonBusy(button, null);
    }
    if (detailCnpj !== cnpj) {  // 그사이 다른 업체로 옮겼으면 결과는 보관만 하고 지금 화면은 그대로 둡니다.
      updateBriefButtons();
      updateBriefBadge();
      briefAnnounce(done);
      return;
    }
    showBriefingFor(cnpj);
    if (errorHtml) briefBox.innerHTML = errorHtml + (briefCache[cnpj] ? briefingHtml(briefCache[cnpj]) : "");
    // 업체 상세 탭을 보고 있으면 초점을 빼앗지 않고 탭 옆에 '새 결과'만 표시합니다(완료 문장은 읽어 줌).
    if (briefPaneShown()) AppShell.ui.focusResult(briefTitle, { scroll: "start", from: [dialog] });
    else briefFresh[cnpj] = true;
    updateBriefBadge();
    briefAnnounce(done);
  }

  if (briefRunBtn) briefRunBtn.addEventListener("click", function () { runBriefing(detailCnpj, briefRunBtn); });

  /* ---------- 업체 상세: 목록 행 아래 가벼운 펼치기 + AI 브리핑 글래스 창 ---------- */
  const dialog = panel.querySelector("[data-ma-dialog]");
  const dialogHead = panel.querySelector("[data-ma-dialog-head]");
  const detailBox = panel.querySelector("[data-ma-detail]");
  let detailCnpj = null;   // 창에 띄운 업체
  let dialogTabs = [];     // 창 안 하위 탭(아래 '하위 탭'에서 연결)
  let selectDialogTab = null;
  const briefBadge = panel.querySelector("[data-ma-brief-badge]");
  const briefFresh = {};   // 업체 상세 탭을 보는 사이 끝난 브리핑(AI 브리핑 탭을 열면 지움)

  function briefPaneShown() { return !panel.querySelector('[data-ma-dpane="brief"]').hidden; }

  // AI 브리핑 탭 옆 작은 표시: 지금 창 업체의 브리핑이 생성 중이거나, 상세를 보는 사이 끝났을 때
  function updateBriefBadge() {
    const text = detailCnpj && briefRunning === detailCnpj ? "생성 중" : (detailCnpj && briefFresh[detailCnpj] ? "새 결과" : "");
    briefBadge.textContent = text ? " · " + text : "";
    briefBadge.hidden = !text;
  }

  function findCompany(cnpj) {
    const hit = buyerView.list.find(function (x) { return x.c.cnpj === cnpj; });
    return hit ? hit.c : null;
  }

  function startedText(c) {
    const v = c.inicio_atividade || "";
    if (!/^\d{8}$/.test(v)) return "미상";
    const now = new Date();
    let years = now.getFullYear() - Number(v.slice(0, 4));
    if (now.getMonth() + 1 < Number(v.slice(4, 6)) || (now.getMonth() + 1 === Number(v.slice(4, 6)) && now.getDate() < Number(v.slice(6)))) years -= 1;
    return v.slice(0, 4) + "-" + v.slice(4, 6) + "-" + v.slice(6) + " · 업력 " + years + "년";
  }

  // 업체 정보 칸(펼치기·창 공용). 국세청 공개 자료와 등급만 쓰며 외부 요청 없음.
  function detailGrid(c) {
    const item = function (label, value, wide) { return '<div' + (wide ? ' class="ma-detail-wide"' : "") + "><dt>" + esc(label) + "</dt><dd>" + value + "</dd></div>"; };
    const evidence = c.evidence.length ? "<ul>" + c.evidence.map(function (e) {
      return "<li>" + linkHtml(e.url, e.title) + ' <span class="field-hint">확인 ' + esc(e.checked_at) + "</span></li>";
    }).join("") + "</ul>" : '<span class="field-hint">없음(검토된 공개 근거 없음)</span>';
    return '<dl class="ma-detail-grid">' +
      item("등급 근거", esc(c.grade_reason), true) +
      item("지역", esc((c.municipio || "미상") + ", " + (c.uf || ""))) +
      item("업종", esc(c.cnae_label || c.cnae) + '<br><span class="field-hint">' + esc(c.cnae + " · " + (c.cnae_desc || "")) + "</span>") +
      item("규모(국세청 코드)", esc(c.porte || "미상")) +
      item("개업일", esc(startedText(c))) +
      item("사업장", esc((c.matriz ? "본점" : "지점 자료(본점 아님)") + " · 대상 업종 사업장 " + (c.sites_matched || 1) + "곳")) +
      item("법인 형태", esc(c.natureza || "미상")) +
      item("대표 전화", c.phones.length ? c.phones.map(esc).join("<br>") : '<span class="field-hint">등록 없음</span>') +
      item("회사 도메인", c.domain ? linkHtml("https://" + c.domain, c.domain) : '<span class="field-hint">없음</span>') +
      item("재생·T2T 근거", evidence, true) + "</dl>";
  }

  // '상세 보기': 행 바로 아래에 펼치기/접기(목록 화면 그대로, 여러 업체 동시에 펼칠 수 있음)
  function toggleInline(btn) {
    const tr = btn.closest("tr");
    const next = tr.nextElementSibling;
    const label = btn.querySelector("[data-ma-label]");
    if (next && next.classList.contains("ma-inline-row")) {
      next.remove();
      btn.setAttribute("aria-expanded", "false");
      label.textContent = "상세 보기";
      return;
    }
    const c = findCompany(btn.dataset.maInline);
    if (!c) return;
    const id = "market_analysis-inline-" + c.cnpj;
    tr.insertAdjacentHTML("afterend", '<tr class="ma-inline-row" id="' + id + '"><td colspan="' + tr.children.length + '"><div class="ma-inline-detail">' +
      detailGrid(c) + "</div></td></tr>");
    btn.setAttribute("aria-expanded", "true");
    btn.setAttribute("aria-controls", id);
    label.textContent = "상세 접기";
  }

  // 'AI 브리핑': 글래스 창에 업체 상세 + 브리핑. 받은 적 없는 업체면 바로 받습니다(1회 유료), 받은 업체는 다시 호출하지 않음.
  function openDialog(cnpj) {
    const c = findCompany(cnpj);
    if (!c) return;
    detailCnpj = cnpj;
    dialogHead.innerHTML = '<div class="ma-brief-title-row"><span class="ma-grade ma-grade-' + esc(c.grade) + '" title="우선순위 등급">' + esc(c.grade) +
      '</span><span class="visually-hidden">등급</span><h2 class="card-title ma-detail-title" id="market_analysis-dialog-title" tabindex="-1">' + esc(c.razao_social) + "</h2></div>" +
      '<p class="ma-brief-sub">' + esc([c.nome_fantasia && c.nome_fantasia !== c.razao_social ? c.nome_fantasia : "", "CNPJ " + c.cnpj, (c.cnae_label || c.cnae),
        (c.municipio || "") + ", " + (c.uf || "")].filter(Boolean).join(" · ")) + "</p>";
    const notes = (buyersData && buyersData.notes ? buyersData.notes : []).map(function (n) { return '<p class="field-hint">' + esc(n) + "</p>"; }).join("");
    detailBox.innerHTML = '<h3 class="visually-hidden">업체 상세</h3>' + detailGrid(c) + notes;
    showBriefingFor(cnpj);
    selectDialogTab(dialogTabs.find(function (t) { return t.dataset.maDtab === "brief"; }), false);
    if (!dialog.open) dialog.showModal();
    AppShell.ui.focusResult(panel.querySelector("#market_analysis-dialog-title"), { scroll: false });
    if (!briefCache[cnpj] && !briefBusy) runBriefing(cnpj, briefRunBtn);
  }

  panel.querySelector("[data-ma-dialog-close]").addEventListener("click", function () { dialog.close(); });
  // 창 바깥(흐린 배경)을 누르면 닫습니다.
  dialog.addEventListener("click", function (event) { if (event.target === dialog) dialog.close(); });
  // 닫히면(Esc 포함) 브라우저가 창을 연 버튼으로 초점을 돌려줍니다. 진행 중 브리핑은 계속되고 결과는 업체별로 보관됩니다.
  dialog.addEventListener("close", function () {
    detailCnpj = null;
    updateBriefButtons();
    updateBriefBadge();
  });

  /* ---------- 하위 탭(시장 통계 / 바이어 목록, 창 안 업체 상세 / AI 브리핑) ---------- */
  // 탭 묶음 하나를 연결하고 선택 함수를 돌려줍니다. paneOf(tab) = 그 탭의 패널, onSelect(tab) = 선택 뒤 할 일(없어도 됨)
  function bindTabs(list, paneOf, onSelect) {
    function select(tab, focus) {
      list.forEach(function (t) {
        const on = t === tab;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.tabIndex = on ? 0 : -1;
        paneOf(t).hidden = !on;
      });
      if (focus) tab.focus();
      if (onSelect) onSelect(tab);
    }
    list.forEach(function (t, i) {
      t.addEventListener("click", function () { select(t, false); });
      t.addEventListener("keydown", function (event) {
        const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
        if (event.key === "Home" || event.key === "End") {
          event.preventDefault();
          select(list[event.key === "Home" ? 0 : list.length - 1], true);
        } else if (step) {
          event.preventDefault();
          select(list[(i + step + list.length) % list.length], true);
        }
      });
    });
    return select;
  }

  const tabs = Array.from(panel.querySelectorAll("[data-ma-tab]"));
  bindTabs(tabs, function (t) { return panel.querySelector('[data-ma-pane="' + t.dataset.maTab + '"]'); });

  dialogTabs = Array.from(panel.querySelectorAll("[data-ma-dtab]"));
  selectDialogTab = bindTabs(dialogTabs, function (t) { return panel.querySelector('[data-ma-dpane="' + t.dataset.maDtab + '"]'); }, function (t) {
    if (t.dataset.maDtab === "brief" && detailCnpj) delete briefFresh[detailCnpj];
    dialog.querySelector(".ma-dialog-body").scrollTop = 0;
    updateBriefBadge();
  });

  loadMeta();
  loadBuyers();
})();
