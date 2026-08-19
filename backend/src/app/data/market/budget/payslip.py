"""급여명세서(엑셀/PDF/CSV)에서 실수령액·지급·공제를 뽑는다.

카드 명세서와 같은 이유로 표 읽기는 ``cards.tables`` 에 맡긴다 — 회사가 주는
명세서도 확장자만 ``.xls`` 인 HTML 인 경우가 있다.
"""
from __future__ import annotations

import io
import re

from .cards import tables

_NET_KW = ["실수령", "실지급", "차인지급", "공제후", "실 지급", "실 수령", "net pay", "net"]
_GROSS_KW = ["지급총액", "지급계", "총지급", "급여계", "지급합계", "지급 합계", "gross", "총액"]
_DEDUCT_KW = ["공제총액", "공제계", "공제합계", "공제 합계", "deduction"]
_PAY_NUM = re.compile(r"\d{1,3}(?:,\d{3})+|\d{5,}")   # 콤마 묶음 또는 5자리 이상
_SAL_MIN, _SAL_MAX = 300_000, 200_000_000            # 급여로 볼 만한 금액 범위


def _nums_in(s: str) -> list[float]:
    out = []
    for m in _PAY_NUM.finditer(s):
        try:
            v = float(m.group(0).replace(",", ""))
            if _SAL_MIN <= v <= _SAL_MAX:
                out.append(v)
        except ValueError:
            pass
    return out


def _lines_from_pdf(data: bytes) -> list[str]:
    try:
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in r.pages)
        return [ln for ln in text.splitlines() if ln.strip()]
    except Exception:
        return []


def parse(filename: str, data: bytes) -> dict:
    """라벨(실수령액/지급총액/공제계) 근처 숫자를 우선 잡고, 못 찾으면 급여 범위의
    가장 큰 숫자를 실수령액 후보로 돌려준다(사용자가 확인 후 저장)."""
    if (filename or "").lower().endswith(".pdf") or data[:5] == b"%PDF-":
        lines = _lines_from_pdf(data)
    else:
        sheet = tables.read(filename or "", data or b"")
        lines = ["\t".join(c for c in row if c) for row in sheet.rows]
        if not lines and sheet.kind == "text":
            lines = tables.decode(data).splitlines()

    def find(keywords: list[str]) -> tuple[float | None, list[dict]]:
        cands: list[dict] = []
        for i, ln in enumerate(lines):
            low = ln.lower()
            if not any(k in low for k in keywords):
                continue
            nums = _nums_in(ln)
            if not nums and i + 1 < len(lines):  # 라벨과 값이 다음 줄에 있을 때
                nums = _nums_in(lines[i + 1])
            if nums:
                cands.append({"label": ln.strip()[:24], "amount": round(max(nums))})
        best = max((c["amount"] for c in cands), default=None)
        return best, cands

    net, net_c = find(_NET_KW)
    gross, _ = find(_GROSS_KW)
    deduct, _ = find(_DEDUCT_KW)

    guessed = False
    if net is None:
        # 라벨을 못 찾음 → 전체에서 급여 범위 최대 숫자를 실수령액 후보로
        all_nums = [n for ln in lines for n in _nums_in(ln)]
        if all_nums:
            net = round(max(all_nums))
            guessed = True

    return {
        "filename": filename,
        "net": net,
        "gross": gross,
        "deduction": deduct,
        "guessed": guessed,
        "candidates": net_c[:6],
        "note": ("실수령액 라벨을 찾지 못해 가장 큰 금액을 추정했습니다. 확인 후 저장하세요."
                 if guessed else "명세서에서 실수령액을 추출했습니다. 확인 후 저장하세요.")
        if net else "금액을 찾지 못했습니다. 직접 입력해 주세요.",
    }
