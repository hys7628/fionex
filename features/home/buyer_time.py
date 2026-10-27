"""바이어 시간 서버 계산(일일 브리핑 PDF용). 화면 계산(static/home.js)과 같은 규칙입니다.

- 도시 코드는 화면 기준 도시 선택값(IANA 시간대)을 그대로 씁니다. 시간은 zoneinfo로 변환하며 고정 시차를 쓰지 않습니다.
- 상태: 브라질 국가 공휴일 → 주말 → 현지 09:00~18:00(가정값) 업무시간 → 업무시간 외.
- 다음 업무 시작: 평일·국가 공휴일이 아닌 가장 가까운 날의 현지 09:00(오늘 09:00 전이면 오늘부터), 최대 31일 탐색.
- 공휴일은 service.get_holidays(연도) 결과(서버 캐시)를 씁니다. 확인할 수 없으면 공휴일 없이 판단하고 그렇다고 표시합니다.
- 다음 공휴일: 기준 도시 현지 날짜 이후(오늘 포함) 가장 가까운 국가 공휴일. 올해 남은 공휴일이 없을 때만 다음 해 목록을 봅니다.
  그 연도 자료를 확인하지 못하면 추측하지 않고 None(화면·PDF "다음 공휴일 확인 불가").
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")
CITIES = {
    "America/Sao_Paulo": "상파울루",
    "America/Fortaleza": "포르탈레자",
    "America/Manaus": "마나우스",
    "America/Rio_Branco": "히우브랑쿠",
}
DEFAULT_CITY = "America/Sao_Paulo"
WORK_START_HOUR = 9
WORK_END_HOUR = 18
NEXT_START_SEARCH_DAYS = 31
HOLIDAY_LOOKAHEAD_DAYS = 7
WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")  # date.weekday() 순서


def buyer_time(city, now, holidays_for_year):
    """now: 시간대가 있는 datetime. holidays_for_year(연도) → {"source", "holidays": [{date, name}]}

    반환 {"city", "city_name", "seoul", "local", "status", "next_start", "holidays", "next_holiday", "holiday_info"}
    """
    tz = ZoneInfo(city)
    local = now.astimezone(tz)
    today = local.date()
    lookup = _HolidayLookup(holidays_for_year)

    holiday_today = lookup.name(today)
    if holiday_today:
        status = "공휴일"
    elif today.weekday() >= 5:
        status = "주말"
    elif WORK_START_HOUR <= local.hour < WORK_END_HOUR:
        status = "업무시간"
    else:
        status = "업무시간 외"

    next_start = None
    if status != "업무시간":
        next_start = _next_work_start(today, local.hour, tz, lookup)

    upcoming = []
    for offset in range(HOLIDAY_LOOKAHEAD_DAYS + 1):
        day = today + timedelta(days=offset)
        name = lookup.name(day)
        if name:
            upcoming.append({"date": day, "name": name, "weekend": day.weekday() >= 5, "days": offset})

    return {
        "city": city,
        "city_name": CITIES[city],
        "seoul": now.astimezone(SEOUL),
        "local": local,
        "status": status,
        "next_start": next_start,
        "holidays": upcoming,
        "next_holiday": next_holiday(today, lookup),
        "holiday_info": lookup.summary(),
    }


def next_holiday(today, lookup):
    """today 이후(오늘 포함) 가장 가까운 공휴일 {"date", "name", "days"}. 올해 남은 것이 없으면 다음 해 첫 공휴일.

    필요한 연도의 자료를 확인하지 못하면 None. 다음 해 목록은 올해에 남은 공휴일이 없을 때만 가져옵니다.
    """
    for year in (today.year, today.year + 1):
        dates = lookup.dates(year)
        if dates is None:
            return None
        upcoming = [d for d in dates if d >= today]
        if upcoming:
            day = upcoming[0]
            return {"date": day, "name": lookup.name(day), "days": (day - today).days}
    return None


def next_holiday_text(holiday):
    """11/2(월) Finados · D-8 / 오늘이면 D-DAY. 공휴일 이름은 BrasilAPI 원문 그대로입니다."""
    if holiday is None:
        return "다음 공휴일 확인 불가"
    d_day = "D-DAY" if holiday["days"] == 0 else f"D-{holiday['days']}"
    return f"{format_day(holiday['date'])} {holiday['name']} · {d_day}"


def _next_work_start(today, hour, tz, lookup):
    day = today if hour < WORK_START_HOUR else today + timedelta(days=1)
    all_known = True
    for _ in range(NEXT_START_SEARCH_DAYS):
        if day.weekday() < 5:
            if not lookup.known(day):
                all_known = False
            if not lookup.name(day):
                start = datetime.combine(day, time(WORK_START_HOUR), tzinfo=tz)
                return {"local": start, "seoul": start.astimezone(SEOUL), "holidays_known": all_known}
        day += timedelta(days=1)
    return None


class _HolidayLookup:
    """연도별 공휴일을 한 번만 가져와 날짜로 찾습니다."""

    def __init__(self, holidays_for_year):
        self._fetch = holidays_for_year
        self._years = {}

    def _year(self, year):
        if year not in self._years:
            data = self._fetch(year)
            known = data.get("source") in ("brasilapi", "fallback")
            self._years[year] = {
                "source": data.get("source"),
                "fetched_at": data.get("fetched_at"),
                "known": known,
                "by_date": {h["date"]: h["name"] for h in data.get("holidays", [])} if known else {},
            }
        return self._years[year]

    def known(self, day):
        return self._year(day.year)["known"]

    def name(self, day):
        return self._year(day.year)["by_date"].get(day.isoformat())

    def dates(self, year):
        """그 해 공휴일 날짜(오름차순). 자료를 확인하지 못한 해는 None."""
        entry = self._year(year)
        if not entry["known"]:
            return None
        return sorted(date.fromisoformat(value) for value in entry["by_date"])

    def summary(self):
        return {year: {"source": v["source"], "fetched_at": v["fetched_at"]} for year, v in sorted(self._years.items())}


def format_day_time(dt):
    """10/25(일) 00:10 — 화면(home.js formatDayTime)과 같은 형식"""
    return f"{dt.month}/{dt.day}({WEEKDAYS[dt.weekday()]}) {dt:%H:%M}"


def format_day(day):
    return f"{day.month}/{day.day}({WEEKDAYS[day.weekday()]})"
