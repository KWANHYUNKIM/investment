"""Numeric coercion helpers shared across domains."""
from __future__ import annotations

import math
import re


def json_float(v) -> float | None:
    """JSON-safe float: ``None`` for missing/NaN/non-numeric values.

    Promoted from the per-module ``_f``/``_num`` helpers so every domain shapes
    numbers identically (NaN → null) instead of re-implementing the guard.

    주의: 값이 ``0`` 이거나 ``inf`` 면 그대로 돌려준다. "0도 없는 값으로 본다" 같은
    도메인 규칙은 여기 넣지 말고 호출부에서 처리한다(예: ``loaders/krx.py`` 는 시세 0을
    '거래정지'로 보아 자체 헬퍼를 유지한다).
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


# 회계 표기 숫자: 천단위 콤마, 괄호가 음수, 소수점 허용.
_ACCOUNTING = re.compile(r"-?\d[\d,]*\.?\d*")


def parse_accounting_number(s: str | None) -> float | None:
    """공시 표(表) 셀의 회계 표기 숫자를 float 으로. 못 읽으면 ``None``.

        '29,436,673'   →  29436673.0
        '(29,436,673)' → -29436673.0     괄호 = 음수 (회계 관행)
        '-1,234.56'    → -1234.56
        '1,234 원'     →  1234.0         단위·주석이 붙어도 숫자만 집어낸다
        '-' · '—' · '' →  None           숫자가 없으면 None

    DART 사업보고서 파서 두 곳(``report_notes``·``report_business``)이 각자 구현하고
    있었다. 그중 하나는 부호를 두 번 뒤집어(``-123`` → ``+123``) 앞에 마이너스가 붙은
    셀을 잘못 읽었고, 다른 하나만 소수점을 지원했다. 여기로 합치면서 소수점을 지원하는
    쪽 정규식을 쓰고 부호는 한 번만 적용한다.
    """
    t = (s or "").strip()
    if not t or not re.search(r"\d", t):
        return None
    m = _ACCOUNTING.search(t)
    if not m:
        return None
    try:
        v = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    # 괄호로 감싼 음수. 정규식이 이미 선행 마이너스를 먹었으므로 여기서 또 뒤집지 않는다.
    if t.startswith("(") and t.endswith(")"):
        return -abs(v)
    return v
