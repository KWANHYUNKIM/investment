"""카드별 결제 주기 — 거래일에서 '그 돈이 언제 빠지는지'를 계산한다.

카드사가 청구월을 안 알려주는 파일(롯데 결제예정금액·하나 이용내역)이 많고, 알려줘도
카드마다 결제일이 달라 같은 날 긁은 돈이 서로 다른 달에 빠진다. 그래서 카드마다
이용기간과 결제일을 등록해 두고 거래일에서 청구월을 계산한다.

설정 네 가지 — **자동으로 추론하지 않는다.**

    cycle_start_day  이용기간 시작일 (1~31, 0=말일)
    cycle_end_day    이용기간 종료일 (1~31, 0=말일)
    pay_day          결제일 (1~31, 0=말일)
    pay_offset       종료월 기준 몇 달 뒤에 결제하나 (0=당월, 1=익월, 2=다다음달)

처음엔 '결제일이 종료일보다 뒤면 당월' 로 추론하려 했는데, 실제 카드가 그렇지 않다.
7/18~8/18 이용분을 **9월**에 받는 카드가 있고(종료 18일 · 결제 1일 · 익월), 같은
종료일에 8/25 에 받는 카드도 있다(당월). 추론하면 한 달씩 어긋난 채로 조용히
쌓이므로 사용자가 직접 고르게 한다.

시작일이 종료일 이상이면 이용기간은 **전월 시작 ~ 당월 종료** 로 걸친다. 주기끼리
하루도 겹치지 않게 다음 주기 시작 전날까지로 자르므로, 시작·종료를 같은 날로 넣으면
종료가 하루 당겨진다(사람이 '18일부터 18일까지' 라고 말하는 걸 그대로 받은 결과).

    시작 18 · 종료 18  →  7/18 ~ 8/17   (겹침 제거로 하루 당겨짐)
    시작 12 · 종료 11  →  7/12 ~ 8/11
    시작  1 · 종료 말일 →  8/1  ~ 8/31   (한 달 안)

**할부는 거래일로 계산하면 안 된다.** 5/17 에 12개월 할부로 긁은 건의 3회차는
5월 거래지만 8월에 빠진다. 1회차 청구월을 거래일로 구한 뒤 ``회차 - 1`` 개월을 더한다.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

MONTH_END = 0       # 날짜 항목에 0 을 넣으면 '말일'

DEFAULT = {"cycle_start_day": 1, "cycle_end_day": MONTH_END, "pay_day": 14, "pay_offset": 1}


def _day_in(year: int, month: int, day: int) -> int:
    """그 달에 없는 날짜(2월 31일)와 '말일'(0)을 실제 날로 바꾼다."""
    last = calendar.monthrange(year, month)[1]
    return last if (not day or day > last) else day


def _shift(year: int, month: int, n: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + n
    return total // 12, total % 12 + 1


def _at(year: int, month: int, day: int) -> date:
    return date(year, month, _day_in(year, month, day))


def normalize(cfg: dict | None) -> dict:
    """저장된 설정을 안전한 범위로 다듬는다(없으면 기본값)."""
    c = {**DEFAULT, **(cfg or {})}
    out = {}
    for k in ("cycle_start_day", "cycle_end_day", "pay_day"):
        try:
            v = int(c.get(k) or 0)
        except (TypeError, ValueError):
            v = DEFAULT[k]
        out[k] = v if 0 <= v <= 31 else DEFAULT[k]
    try:
        off = int(c.get("pay_offset", 1))
    except (TypeError, ValueError):
        off = 1
    out["pay_offset"] = off if 0 <= off <= 3 else 1
    return out


def _spans_two_months(cfg: dict) -> bool:
    """시작일이 종료일 이상이면 전월에서 시작해 당월에 끝난다."""
    start, end = cfg["cycle_start_day"], cfg["cycle_end_day"]
    return (start or 32) >= (end or 32)


def _cycle_start(year: int, month: int, cfg: dict) -> date:
    """그 달에 끝나는 주기의 시작일."""
    sy, sm = _shift(year, month, -1) if _spans_two_months(cfg) else (year, month)
    return _at(sy, sm, cfg["cycle_start_day"])


def cycle_ending(year: int, month: int, cfg: dict) -> tuple[date, date]:
    """그 달에 끝나는 이용기간 (시작일, 종료일) — 주기끼리 겹치지 않게 자른다.

    사람은 '7월 18일부터 8월 18일까지' 라고 말하지만 시작·종료를 둘 다 포함으로
    두면 18일이 앞 주기의 마지막이자 뒤 주기의 첫날이 되어 거래 하나가 두 달에
    걸린다. 다음 주기가 시작하기 전날까지로 잘라 실제 경계를 만들고, 화면에는
    이렇게 **잘린 실제 기간**을 보여준다(7/18 ~ 8/17).
    """
    start = _cycle_start(year, month, cfg)
    ny, nm = _shift(year, month, 1)
    end = min(_at(year, month, cfg["cycle_end_day"]),
              _cycle_start(ny, nm, cfg) - timedelta(days=1))
    return start, end


def cycle_of(d: date, cfg: dict) -> tuple[date, date]:
    """거래일이 속한 이용기간."""
    for ahead in (1, 0, -1):
        y, m = _shift(d.year, d.month, ahead)
        start, end = cycle_ending(y, m, cfg)
        if start <= d <= end:
            return start, end
    # 주기가 연속이라 여기 오지 않지만, 방어적으로 당월 주기를 준다.
    return cycle_ending(d.year, d.month, cfg)


def pay_date_of(cycle_end: date, cfg: dict) -> date:
    y, m = _shift(cycle_end.year, cycle_end.month, cfg["pay_offset"])
    return _at(y, m, cfg["pay_day"])


def billing_month_of(tx_date: str, cfg: dict, seq: int = 0) -> str:
    """거래일 → 청구월(``YYYY-MM``). ``seq`` 는 할부 회차(1부터, 0이면 일시불)."""
    cfg = normalize(cfg)
    try:
        y, m, d = (int(x) for x in str(tx_date)[:10].split("-"))
        day = date(y, m, d)
    except (ValueError, TypeError):
        return ""
    _, end = cycle_of(day, cfg)
    pay = pay_date_of(end, cfg)
    if seq and seq > 1:
        py, pm = _shift(pay.year, pay.month, seq - 1)
        return f"{py}-{pm:02d}"
    return f"{pay.year}-{pay.month:02d}"


def window_for(billing_month: str, cfg: dict) -> dict:
    """청구월 → 그 달에 빠지는 돈의 이용기간. 설정이 맞는지 눈으로 확인시켜 주는 용도.

    ``{"start": "2026-07-18", "end": "2026-08-18", "pay": "2026-09-01"}``
    """
    cfg = normalize(cfg)
    try:
        y, m = (int(x) for x in str(billing_month).split("-")[:2])
    except (ValueError, IndexError):
        return {}
    ey, em = _shift(y, m, -cfg["pay_offset"])
    start, end = cycle_ending(ey, em, cfg)
    pay = pay_date_of(end, cfg)
    return {"start": start.isoformat(), "end": end.isoformat(), "pay": pay.isoformat()}


def describe(cfg: dict) -> str:
    """설정을 한 줄로 — '전월 18일 시작 · 익월 1일 결제'.

    종료일은 여기 넣지 않는다. 겹침을 없애느라 실제 종료가 하루 당겨질 수 있어
    글로 쓰면 어긋난다 — 실제 기간은 ``window_for`` 가 날짜로 보여준다.
    """
    cfg = normalize(cfg)
    day = (lambda v: "말일" if not v else f"{v}일")
    when = {0: "당월", 1: "익월", 2: "다다음달", 3: "3개월 뒤"}[cfg["pay_offset"]]
    start_when = "전월" if _spans_two_months(cfg) else "당월"
    return (f"{start_when} {day(cfg['cycle_start_day'])} 시작 · "
            f"{when} {day(cfg['pay_day'])} 결제")
