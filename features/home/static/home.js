// 홈 탭 스크립트. 이 탭 패널 내부만 다룹니다. 공통 API 사용법: docs/design_system.md
(function () {
  "use strict";

  const FEATURE_ID = "home";
  const panel = document.querySelector('[data-feature-panel="' + FEATURE_ID + '"]');
  if (!panel) return;

  // 기능 개발 단계에서 구현.
  // - 입력 변경은 공통 shell이 자동 감지합니다.
  // - 결과 생성 후 AppShell.work.setResult(FEATURE_ID, true)
  // - PDF Blob 다운로드는 AppShell.work.downloadBlob(FEATURE_ID, blob, "파일명.pdf")
  // - 탭을 다시 열 때 생성 API를 재호출하지 않습니다(결과 DOM이 그대로 유지됨).

  /* ---------- 바이어 시간 ---------- */
  // 시각은 IANA 시간대 + Intl.DateTimeFormat으로 구합니다. 고정 시차를 쓰지 않습니다.
  // 업무시간 09:00~18:00은 확정되지 않은 가정값입니다(화면에 "가정"으로 표시).
  const SEOUL_TZ = "Asia/Seoul";
  const WORK_START_HOUR = 9;
  const WORK_END_HOUR = 18;
  const HOLIDAY_LOOKAHEAD_DAYS = 14;
  const NEXT_START_SEARCH_DAYS = 31;
  const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
  const STATUS = {
    holiday: { text: "공휴일", tone: "badge-warning" },
    weekend: { text: "주말", tone: "badge-warning" },
    work: { text: "업무시간", tone: "badge-success" },
    off: { text: "업무시간 외", tone: "badge-info" },
  };

  const citySelect = panel.querySelector("#home-city");
  const el = {
    seoul: panel.querySelector("#home-seoul-time"),
    brazil: panel.querySelector("#home-brazil-time"),
    city: panel.querySelector("#home-brazil-city"),
    status: panel.querySelector("#home-status"),
    nextRow: panel.querySelector("#home-next-row"),
    next: panel.querySelector("#home-next-start"),
    nextLocal: panel.querySelector("#home-next-local"),
    holiday: panel.querySelector("#home-holiday"),
    source: panel.querySelector("#home-holiday-source"),
  };

  // 같은 내용이면 DOM을 건드리지 않아 화면낭독기 반복 안내를 줄입니다.
  function setText(node, text) {
    if (node.textContent !== text) node.textContent = text;
  }

  function setClass(node, className) {
    if (node.className !== className) node.className = className;
  }

  /* 날짜 계산. day = {year, month, day}는 시간대와 무관한 달력 날짜입니다. */
  const formatters = new Map();

  function partsIn(instant, timeZone) {
    let fmt = formatters.get(timeZone);
    if (!fmt) {
      fmt = new Intl.DateTimeFormat("en-US", {
        timeZone: timeZone,
        year: "numeric", month: "numeric", day: "numeric",
        hour: "numeric", minute: "numeric", hourCycle: "h23",
      });
      formatters.set(timeZone, fmt);
    }
    const p = {};
    fmt.formatToParts(instant).forEach(function (part) {
      if (part.type !== "literal") p[part.type] = Number(part.value);
    });
    return { year: p.year, month: p.month, day: p.day, hour: p.hour % 24, minute: p.minute };
  }

  function addDays(day, n) {
    const d = new Date(Date.UTC(day.year, day.month - 1, day.day + n));
    return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() };
  }

  function weekday(day) {
    return new Date(Date.UTC(day.year, day.month - 1, day.day)).getUTCDay();
  }

  function isWeekend(day) {
    const w = weekday(day);
    return w === 0 || w === 6;
  }

  function dayKey(day) {
    return day.year + "-" + String(day.month).padStart(2, "0") + "-" + String(day.day).padStart(2, "0");
  }

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  // 10/25(일) 00:10
  function formatDayTime(p) {
    return p.month + "/" + p.day + "(" + WEEKDAYS[weekday(p)] + ") " + pad2(p.hour) + ":" + pad2(p.minute);
  }

  function formatDay(day) {
    return day.month + "/" + day.day + "(" + WEEKDAYS[weekday(day)] + ")";
  }

  // 현지 날짜·시각 → 실제 시점. 오프셋을 고정하지 않고, Intl로 후보 시점의 현지 시각을 확인해
  // 목표 시각과의 차이만큼 보정합니다(시간대 규칙·서머타임 변경 반영).
  function zonedTimeToInstant(day, hour, timeZone) {
    const target = Date.UTC(day.year, day.month - 1, day.day, hour, 0);
    let guess = target;
    for (let i = 0; i < 3; i++) {
      const p = partsIn(new Date(guess), timeZone);
      const diff = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute) - target;
      if (diff === 0) break;
      guess -= diff;
    }
    return new Date(guess);
  }

  /* 공휴일: 연도별로 서버(/api/home/holidays)에서 받아 페이지 메모리에만 둡니다. */
  // 연도 → { loading: true } | { source, fetchedAt, byDate: Map(날짜 → 이름) }
  const holidayYears = new Map();

  function ensureYear(year) {
    if (holidayYears.has(year)) return;
    holidayYears.set(year, { loading: true });
    fetch("/api/home/holidays?year=" + year)
      .then(function (res) { return res.json(); })
      .then(function (body) {
        if (!body.ok) throw new Error(body.error.message);
        const data = body.data;
        return {
          source: data.source,
          fetchedAt: data.fetched_at,
          byDate: new Map(data.holidays.map(function (h) { return [h.date, h.name]; })),
        };
      })
      .catch(function () {
        return { source: "none", fetchedAt: null, byDate: new Map() };
      })
      .then(function (entry) {
        holidayYears.set(year, entry);
        render();
      });
  }

  // 확인하지 못한 연도는 홈을 다시 열 때 재시도합니다.
  function forgetUnavailableYears() {
    holidayYears.forEach(function (entry, year) {
      if (entry.source === "none") holidayYears.delete(year);
    });
  }

  // { name: 공휴일 이름 또는 null, known: 그 연도 공휴일 자료를 확인했는지 }
  function lookupHoliday(day) {
    ensureYear(day.year);
    const entry = holidayYears.get(day.year);
    if (entry.loading || entry.source === "none") return { name: null, known: false };
    return { name: entry.byDate.get(dayKey(day)) || null, known: true };
  }

  function workStatus(day, hour) {
    if (lookupHoliday(day).name) return STATUS.holiday;
    if (isWeekend(day)) return STATUS.weekend;
    if (hour >= WORK_START_HOUR && hour < WORK_END_HOUR) return STATUS.work;
    return STATUS.off;
  }

  // 평일이며 국가 공휴일이 아닌 가장 가까운 날. 오늘 09:00 전이면 오늘부터 찾습니다.
  function nextWorkDay(today, hour) {
    let day = hour < WORK_START_HOUR ? today : addDays(today, 1);
    let allKnown = true;
    for (let i = 0; i < NEXT_START_SEARCH_DAYS; i++, day = addDays(day, 1)) {
      if (isWeekend(day)) continue;
      const holiday = lookupHoliday(day);
      if (!holiday.known) allKnown = false;
      if (!holiday.name) return { day: day, allKnown: allKnown };
    }
    return null;
  }

  // 오늘부터 HOLIDAY_LOOKAHEAD_DAYS일 안의 가장 가까운 국가 공휴일
  function holidayText(today) {
    let allKnown = true;
    for (let i = 0; i <= HOLIDAY_LOOKAHEAD_DAYS; i++) {
      const day = addDays(today, i);
      const holiday = lookupHoliday(day);
      if (!holiday.known) allKnown = false;
      if (!holiday.name) continue;
      if (i === 0) return "오늘 " + formatDay(day) + " " + holiday.name + " — 국가 공휴일";
      const effect = isWeekend(day) ? " (주말)" : " — 회신 지연 가능";
      return formatDay(day) + " " + holiday.name + " · " + (i === 1 ? "내일" : i + "일 후") + effect;
    }
    return allKnown ? HOLIDAY_LOOKAHEAD_DAYS + "일 이내 국가 공휴일 없음" : "공휴일 정보 확인 불가";
  }

  function renderSource(years) {
    const entries = years.map(function (y) { return holidayYears.get(y); });
    if (entries.some(function (e) { return e.loading; })) {
      setClass(el.source, "field-hint");
      setText(el.source, "공휴일 정보 확인 중");
    } else if (entries.some(function (e) { return e.source === "none"; })) {
      setClass(el.source, "notice notice-warning");
      setText(el.source, "공휴일 정보 확인 불가: 공휴일 없이 주말·업무시간만 판단합니다.");
    } else if (entries.some(function (e) { return e.source === "fallback"; })) {
      setClass(el.source, "notice notice-warning");
      setText(el.source, "공휴일 정보: 대체 자료 사용(BrasilAPI 조회 실패)");
    } else {
      const fetched = entries[0].fetchedAt ? " · 조회 " + formatDayTime(partsIn(new Date(entries[0].fetchedAt), SEOUL_TZ)) + " KST" : "";
      setClass(el.source, "field-hint");
      setText(el.source, "공휴일 정보: BrasilAPI 국가 공휴일" + fetched);
    }
  }

  function render() {
    const now = new Date();
    const timeZone = citySelect.value;
    const local = partsIn(now, timeZone);
    const today = { year: local.year, month: local.month, day: local.day };

    setText(el.seoul, formatDayTime(partsIn(now, SEOUL_TZ)));
    setText(el.brazil, formatDayTime(local));
    setText(el.city, citySelect.selectedOptions[0].textContent);

    const status = workStatus(today, local.hour);
    if (holidayYears.get(today.year).loading) {
      setClass(el.status, "badge");
      setText(el.status, "확인 중");
    } else {
      setClass(el.status, "badge " + status.tone);
      setText(el.status, status.text);
    }

    if (status === STATUS.work) {
      el.nextRow.hidden = true;
    } else {
      const next = nextWorkDay(today, local.hour);
      if (next) {
        const start = zonedTimeToInstant(next.day, WORK_START_HOUR, timeZone);
        setText(el.next, formatDayTime(partsIn(start, SEOUL_TZ)) + " KST");
        setText(el.nextLocal, "현지 " + formatDay(next.day) + " " + pad2(WORK_START_HOUR) + ":00" +
          (next.allKnown ? "" : " · 공휴일 미반영"));
      } else {
        setText(el.next, "계산할 수 없음");
        setText(el.nextLocal, "");
      }
      el.nextRow.hidden = false;
    }

    setText(el.holiday, holidayText(today));
    renderSource([today.year, addDays(today, HOLIDAY_LOOKAHEAD_DAYS).year].filter(function (y, i, a) {
      return a.indexOf(y) === i;
    }));
  }

  // 화면에 분 단위까지만 표시하므로 매 분 경계에 한 번 갱신합니다. 홈이 숨겨지면 멈춥니다.
  let timer = null;

  function tick() {
    render();
    clearTimeout(timer);
    timer = setTimeout(tick, 60000 - (Date.now() % 60000) + 50);
  }

  function stop() {
    clearTimeout(timer);
    timer = null;
  }

  citySelect.addEventListener("change", render);

  // 백그라운드 탭에서는 타이머가 지연될 수 있어 다시 보일 때 즉시 갱신합니다.
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && timer !== null) tick();
  });

  AppShell.onShow(FEATURE_ID, function () {
    forgetUnavailableYears();
    tick();
  });
  AppShell.onHide(FEATURE_ID, stop);
  if (AppShell.current() === FEATURE_ID) tick();
})();
