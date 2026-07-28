"""생산유형 태깅(§2.2) + 결합원가 배분(§2.4).

``docs/원가분석_개편계획.md`` §8 결정사항:

* **배분법 기본값 = 상대판매가치법**. 결합원가 × (품목 매출액 ÷ 총매출액).
  공개데이터(사업보고서 품목·부문 매출비중)만으로 계산돼 커버리지가 가장 넓고,
  추가가공비 같은 **가정을 하나도 더 얹지 않는다**(수치를 지어내지 않는다는 원칙).
* **순실현가치법(NRV)은 데이터가 있을 때만 보조 표시**. 품목별 추가가공비·판매비는
  외부공시에 없으므로(⚪), 공개데이터로 실제 계산 가능한 유일한 NRV 변형인
  **부산물 순실현가치 차감법**만 산출한다(부산품이 식별될 때).

상대판매가치법의 성질 하나는 화면에 반드시 같이 적는다: **정의상 품목별
매출총이익률이 모두 같게 나온다**(균등마진 가정). 품목 간 마진 차이를 보려면
품목별 판가·추가가공비가 필요한데 그건 내부데이터(⚪)다. 이 법으로 읽을 수 있는
것은 "어느 품목이 결합원가를 얼마나 짊어지는가"(원가 부담의 절대 규모)다.
"""
from __future__ import annotations

# --- §2.2 생산유형 → 원가모델 아키타입 ------------------------------------
# 계획서 §2.2 표(단일/공정별/조별/등급별/결합) + 수주형(개별)·용역형을 실제 업종에 맞춤.
_TYPE_BY_SECTOR: dict[str, tuple[str, str]] = {
    "음식료·음료": ("조별", "품목(조)별 원가 분리"),
    "화장품": ("조별", "품목(조)별 원가 분리"),
    "제약·바이오": ("조별", "품목(조)별 원가 분리"),
    "의류·패션": ("조별", "품목(조)별 원가 분리"),
    "자동차·부품·타이어": ("조별", "품목(조)별 원가 분리"),
    "화학·정유·에너지": ("결합", "결합원가 배분(연산품)"),
    "2차전지·소재": ("공정별", "공정투입물 스프레드형"),
    "반도체·전자·디스플레이": ("공정별", "공정투입물 스프레드형"),
    "철강·비철·소재": ("등급별", "등급별 배분"),
    "건설·건자재": ("개별", "개별원가(수주·프로젝트)"),
    "조선·방산·기계": ("개별", "개별원가(수주·프로젝트)"),
    "유통·리테일": ("상품매입", "상품매입원가(제조공정 없음)"),
    "운송·물류·렌탈": ("용역", "용역원가(가동률형)"),
    "IT·게임·엔터·미디어·통신": ("용역", "용역원가(가동률형)"),
    "금융": ("용역", "용역원가(가동률형)"),
    "상사·서비스·기타": ("용역", "용역원가(가동률형)"),
}

# 업종 태그만으론 안 잡히는 **명백한 연산품(결합원가) 회사**를 티커로 보정.
# 근거는 "한 공정에서 2종 이상이 동시에 나온다"는 물리적 사실만 쓴다.
_JOINT_TICKERS: dict[str, str] = {
    "010950": "정유 — 원유 상압증류에서 휘발유·등유·경유·나프타·중유가 동시 산출",
    "096770": "정유·석유화학 — 원유 정제 + NCC 분해 연산품",
    "078930": "정유(자회사 GS칼텍스) — 원유 정제 연산품",
    "267250": "정유(자회사 HD현대오일뱅크) — 원유 정제 연산품",
    "011170": "NCC — 나프타 분해에서 에틸렌·프로필렌·부타디엔·BTX 동시 산출",
    "051910": "NCC — 나프타 분해 연산품(+전지·첨단소재 부문)",
    "010130": "비철제련 — 정광에서 아연·연·금·은·황산 동시 회수",
    "136480": "육계 도계 — 한 마리에서 부위별(정육·부산물) 동시 산출",
    "267980": "유가공 — 원유(原乳)에서 시유·발효유·치즈·분유 동시 산출",
    "003920": "유가공 — 원유(原乳)에서 시유·분유·발효유 동시 산출",
    "006040": "수산·식품 — 원어 가공에서 부위·부산물 동시 산출",
}

# 매출비중이 이 값 미만이면 부산품(부산물) 후보로 태깅. 원가회계상 절대기준은
# 없고 "주산품 대비 소액" 이 유일한 잣대라, 임의 임계임을 화면에 명시한다.
BYPRODUCT_PCT = 5.0


def production_type(ticker: str, sector: str) -> dict:
    """업종(+티커 보정) → 생산유형·원가모델 아키타입. §2.2"""
    joint_reason = _JOINT_TICKERS.get(ticker)
    if joint_reason:
        return {
            "type": "결합",
            "archetype": "결합원가 배분(연산품)",
            "is_joint": True,
            "basis": "티커 보정",
            "reason": joint_reason,
        }
    t, arch = _TYPE_BY_SECTOR.get(sector, ("조별", "품목(조)별 원가 분리"))
    return {
        "type": t,
        "archetype": arch,
        "is_joint": t in ("결합", "등급별"),
        "basis": "업종 매핑" if sector in _TYPE_BY_SECTOR else "기본값",
        "reason": None,
    }


def _norm(mix: list[dict]) -> list[dict]:
    """품목 매출비중을 100% 로 정규화(파싱 합계가 100 이 아닐 수 있음)."""
    items = [{"name": x["name"], "pct": float(x["pct"])}
             for x in mix if x.get("name") and (x.get("pct") or 0) > 0]
    tot = sum(x["pct"] for x in items)
    if tot <= 0:
        return []
    for x in items:
        x["pct"] = round(x["pct"] / tot * 100, 2)
    return sorted(items, key=lambda x: x["pct"], reverse=True)


def allocate(ticker: str, sector: str, cogs_eok: float, revenue_eok: float,
             mix: list[dict]) -> dict | None:
    """결합원가(=매출원가 proxy)를 품목별로 배분. §2.4

    기본 = 상대판매가치법. 부산품이 식별되면 순실현가치법(부산물 순액차감)을
    보조로 함께 계산한다. 연산·등급 업종이 아니거나 품목 매출비중이 2개 미만이면
    ``None`` (배분할 근거가 없으면 만들지 않는다).
    """
    ptype = production_type(ticker, sector)
    if not ptype["is_joint"]:
        return None
    items = _norm(mix)
    if len(items) < 2 or not cogs_eok or not revenue_eok:
        return None

    # --- 기본: 상대판매가치법 --------------------------------------------
    products = []
    for x in items:
        sales = revenue_eok * x["pct"] / 100
        alloc = cogs_eok * x["pct"] / 100
        kind = "부산품" if x["pct"] < BYPRODUCT_PCT else "주산품"
        products.append({
            "name": x["name"],
            "kind": kind,
            "sales_pct": x["pct"],
            "sales_eok": round(sales),
            "alloc_cogs_eok": round(alloc),
            "gross_margin_pct": round((sales - alloc) / sales * 100, 1) if sales else None,
        })

    by = [p for p in products if p["kind"] == "부산품"]
    main = [p for p in products if p["kind"] == "주산품"]

    # --- 보조: 순실현가치법(부산물 순액차감) — 부산품이 있을 때만 -------
    if by and main:
        by_nrv = sum(p["sales_eok"] for p in by)          # 부산물 NRV ≈ 매출액(판매비 차감 전)
        joint_after = max(0.0, cogs_eok - by_nrv)
        main_pct = sum(p["sales_pct"] for p in main) or 1.0
        alt_products = []
        for p in main:
            alloc = joint_after * p["sales_pct"] / main_pct
            s = p["sales_eok"]
            alt_products.append({
                "name": p["name"], "kind": "주산품",
                "alloc_cogs_eok": round(alloc),
                "gross_margin_pct": round((s - alloc) / s * 100, 1) if s else None,
                "delta_eok": round(alloc - p["alloc_cogs_eok"]),
            })
        for p in by:
            alt_products.append({
                "name": p["name"], "kind": "부산품",
                "alloc_cogs_eok": 0, "gross_margin_pct": None,
                "delta_eok": -p["alloc_cogs_eok"],
            })
        alt = {
            "method": "순실현가치법(부산물 순액차감)",
            "available": True,
            "byproduct_nrv_eok": round(by_nrv),
            "joint_cost_after_eok": round(joint_after),
            "products": alt_products,
            "note": "부산품 순실현가치를 결합원가에서 먼저 차감하고 주산품에만 배분(순액법). "
                    "부산물 NRV 는 추가가공비·판매비를 못 빼고 매출액으로 근사(🟡).",
        }
    else:
        alt = {
            "method": "순실현가치법",
            "available": False,
            "reason": ("품목별 추가가공비·판매비가 공시되지 않아(⚪) 완전한 NRV 는 계산 불가. "
                       "공개데이터로 가능한 변형(부산물 순액차감)은 부산품(매출비중 "
                       f"{BYPRODUCT_PCT:.0f}% 미만)이 식별될 때만 산출된다."),
            "products": [],
        }

    return {
        "method": "상대판매가치법",
        "method_basis": "결합원가 × (품목 매출액 ÷ 총매출액)",
        "production_type": ptype,
        "source": "DART 사업보고서 품목·부문 매출비중 × DART 매출원가",
        "joint_cost_eok": round(cogs_eok),
        "revenue_eok": round(revenue_eok),
        "byproduct_threshold_pct": BYPRODUCT_PCT,
        "products": products,
        "alt": alt,
        "caveats": [
            "상대판매가치법은 정의상 품목별 매출총이익률이 모두 같게 나온다(균등마진 가정). "
            "품목 간 마진 차이를 보려면 품목별 판가·추가가공비가 필요하고 이는 미공시(⚪)다.",
            "여기서 읽을 것은 '어느 품목이 결합원가를 얼마나 짊어지는가'(원가 부담 규모)다.",
            f"주산품/부산품 구분은 매출비중 {BYPRODUCT_PCT:.0f}% 임계의 임의 기준(원가회계상 절대기준 없음).",
            "매출원가 전액을 결합원가로 본 근사 — 분리점 이후 개별원가는 분리 불가(🟡).",
        ],
    }
