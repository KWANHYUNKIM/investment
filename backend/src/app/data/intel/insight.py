"""Rule-based "왜 샀나/팔았나" inference for the market daily report.

No LLM. For a stock we combine the signals we already have — investor net-buy
direction (개인/외국인/기관), foreign holding-ratio change, price momentum,
valuation (PER/PBR/ROE/배당), distance from the 52-week high — and the themes we
can read out of its news headlines, into a *templated, estimated* reason per
investor type. Output is framed as 추정(estimate), never proven causation.
"""
from __future__ import annotations

# News-headline theme tables: (keywords, human label). First match wins per side.
_POS_THEMES: list[tuple[tuple[str, ...], str]] = [
    (("HBM", "AI", "인공지능", "엔비디아", "온디바이스"), "AI·반도체 수요 기대"),
    (("반도체", "메모리", "D램", "디램", "낸드", "파운드리"), "반도체 업황 개선 기대"),
    (("2차전지", "이차전지", "배터리", "전기차", "양극재", "전고체"), "2차전지 모멘텀"),
    (("수주", "계약", "공급계약", "납품", "수출 호조", "대규모 공급"), "수주·계약 호재"),
    (("호실적", "어닝 서프라이즈", "사상 최대", "최대 매출", "최대 영업이익", "흑자 전환", "실적 개선"), "실적 호조 기대"),
    (("배당", "자사주", "주주환원", "자사주 소각"), "주주환원 기대"),
    (("목표가 상향", "투자의견 상향", "목표주가 상향", "매수 의견"), "증권가 긍정 전망"),
    (("MSCI", "지수 편입", "편입", "패시브"), "지수 편입·패시브 수급"),
    (("신고가", "사상 최고", "52주 신고가", "급등", "강세"), "주가 강세 흐름"),
    (("정책", "지원", "수혜", "규제 완화"), "정책 수혜 기대"),
]
_NEG_THEMES: list[tuple[tuple[str, ...], str]] = [
    (("어닝 쇼크", "실적 쇼크", "적자", "적자 전환", "감익", "실적 부진", "실적 하향", "전망 하향"), "실적 부진 우려"),
    (("리콜", "소송", "제재", "조사", "횡령", "압수수색", "벌금", "과징금"), "악재·리스크 부각"),
    (("목표가 하향", "투자의견 하향", "매도 의견"), "증권가 부정 전망"),
    (("금리", "환율", "관세", "긴축", "경기 둔화", "무역"), "매크로 부담"),
    (("유상증자", "전환사채", "오버행", "블록딜", "물량 부담"), "수급 부담(물량)"),
    (("신저가", "급락", "약세", "패닉"), "주가 약세 흐름"),
]

LABELS = {"individual": "개인", "foreign": "외국인", "organ": "기관"}


def _themes(titles: list[str], table) -> list[str]:
    text = " ".join(titles)
    out: list[str] = []
    for kws, label in table:
        if any(k in text for k in kws) and label not in out:
            out.append(label)
    return out


def _reasons(itype: str, buying: bool, sig: dict, pos: list[str], neg: list[str]) -> list[str]:
    """Estimated reasons for one investor type given its net direction + signals."""
    reasons: list[str] = []
    per = sig.get("per")
    pbr = sig.get("pbr")
    divy = sig.get("div_yield")
    roe = sig.get("roe")
    ret_1m = sig.get("ret_1m")
    pfh = sig.get("pct_from_high")
    fr = sig.get("foreign_ratio")
    frd = sig.get("foreign_ratio_delta")
    chg = sig.get("change_pct")

    # 1) leading news theme aligned with the direction
    themes = pos if buying else neg
    if themes:
        reasons.append(themes[0])

    # 2) structural signals, framed per investor type
    if buying:
        if itype == "foreign":
            if frd is not None and frd > 0.03 and fr is not None:
                reasons.append(f"외국인 보유율 상승(현재 {fr:.1f}%)")
            if per is not None and 0 < per < 12:
                reasons.append(f"밸류에이션 매력(PER {per:.0f}배)")
            if divy is not None and divy >= 3:
                reasons.append(f"배당 매력(배당수익률 {divy:.1f}%)")
        elif itype == "organ":
            if roe is not None and roe >= 12:
                reasons.append(f"높은 수익성(ROE {roe:.0f}%)")
            if pbr is not None and 0 < pbr < 1:
                reasons.append(f"저PBR 저평가(PBR {pbr:.2f}배)")
            if per is not None and 0 < per < 12:
                reasons.append(f"밸류에이션 매력(PER {per:.0f}배)")
        else:  # individual
            if ret_1m is not None and ret_1m > 5:
                reasons.append(f"최근 1개월 +{ret_1m:.0f}% 상승 모멘텀 추종")
            if pfh is not None and pfh > -3:
                reasons.append("52주 신고가 부근 추격 매수")
            if chg is not None and chg < -2:
                reasons.append("당일 하락 저가 매수 시도")
    else:  # selling
        if itype in ("foreign", "organ"):
            if pfh is not None and pfh > -3:
                reasons.append("신고가 부근 차익 실현")
            if per is not None and per > 30:
                reasons.append(f"밸류에이션 부담(PER {per:.0f}배)")
            if itype == "foreign" and frd is not None and frd < -0.03 and fr is not None:
                reasons.append(f"외국인 보유율 하락(현재 {fr:.1f}%)")
        else:  # individual selling
            if ret_1m is not None and ret_1m > 10:
                reasons.append("단기 급등 후 차익 실현")
            if chg is not None and chg > 2:
                reasons.append("당일 강세 구간 매도")

    # 3) fallback so every active side has at least one line
    if not reasons:
        reasons.append("뚜렷한 촉매는 확인되지 않음")
    return reasons[:3]


def build(sig: dict, titles: list[str]) -> list[dict]:
    """Return per-investor-type [{type, action, qty, reasons}] for a stock.

    `sig` carries flow (individual/foreign/organ net-buy + foreign_ratio[_delta])
    and price/valuation factors; `titles` are the stock's recent headlines.
    """
    pos = _themes(titles, _POS_THEMES)
    neg = _themes(titles, _NEG_THEMES)

    out: list[dict] = []
    for key in ("foreign", "individual", "organ"):
        qty = sig.get(key)
        if qty is None:
            out.append({"type": LABELS[key], "key": key, "action": "데이터 없음", "qty": None, "reasons": []})
            continue
        if qty > 0:
            action, buying = "순매수", True
        elif qty < 0:
            action, buying = "순매도", False
        else:
            out.append({"type": LABELS[key], "key": key, "action": "관망", "qty": 0, "reasons": []})
            continue
        out.append(
            {
                "type": LABELS[key],
                "key": key,
                "action": action,
                "qty": int(qty),
                "reasons": _reasons(key, buying, sig, pos, neg),
            }
        )
    return out
