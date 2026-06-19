"""미래 성장테마 — '지금 시대가 무엇을 구축하고 있나' + 거기 속한 종목의 미래가치.

빨간(오른) 종목뿐 아니라 **지금 빠진(파란) 종목**이라도 미래 메가트렌드에 속하면
미래가치 후보로 본다. 동작:
  1. 메가트렌드 테마(AI 데이터센터·전력 인프라·원전/SMR·로봇·냉각·전력반도체·
     비만치료제·방산우주·자율주행·ESS·AI SW)를 큐레이션,
  2. 테마마다 실시간 뉴스(Google News RSS, 국내+해외)를 취합해 '무엇이 구축/투자
     되고 있나'(동향·방향·대표 헤드라인)를 읽고,
  3. 우리 DB의 한국 종목(업종/제품/이름)을 테마에 매핑해 시세·수익률을 붙이되,
     **최근 하락(파란) 종목을 '미래가치 후보'로 강조**한다.

뉴스는 키 없는 RSS, 매핑은 company_profile(제품/업종) + screen_table_prices(시세).
"""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.core.config import get_settings
from app.data import macro, news, store

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 1800.0  # 30분

# 메가트렌드 테마.
#   queries: (query, hl, gl, ceid) — 국내(ko)+해외(en) 뉴스
#   match  : 한국 종목 매핑 키워드(제품/업종/이름에 부분일치). 구체적으로 — 오탐 방지.
THEMES: list[dict] = [
    {
        "key": "ai_datacenter", "label": "AI 데이터센터", "icon": "🖥️",
        "desc": "AI 학습·추론용 데이터센터 대규모 증설 — 서버·HBM·고속 네트워크·전력/냉각까지 수요 폭증.",
        "queries": [
            ("AI 데이터센터 투자 증설", "ko", "KR", "KR:ko"),
            ("데이터센터 서버 수요", "ko", "KR", "KR:ko"),
            ("AI data center buildout capex", "en-US", "US", "US:en"),
            ("hyperscaler data center investment", "en-US", "US", "US:en"),
        ],
        "match": ["데이터센터", "IDC", "서버", "HBM", "AI 반도체", "가속기", "기판", "FC-BGA"],
    },
    {
        "key": "power_infra", "label": "전력 인프라·전력기기", "icon": "⚡",
        "desc": "데이터센터·전동화로 전력 수요 급증 → 변압기·전선·송배전·중전기 수출 슈퍼사이클.",
        "queries": [
            ("전력기기 변압기 수출", "ko", "KR", "KR:ko"),
            ("전력 인프라 데이터센터 전력난", "ko", "KR", "KR:ko"),
            ("electricity grid transformer demand AI", "en-US", "US", "US:en"),
            ("power grid infrastructure investment", "en-US", "US", "US:en"),
        ],
        "match": ["변압기", "전력기기", "전선", "송배전", "중전기", "전력설비", "케이블", "전력반도체", "차단기", "배전"],
    },
    {
        "key": "nuclear_smr", "label": "원자력·SMR", "icon": "☢️",
        "desc": "AI 전력 수요·탄소중립으로 원전 재부상 — 소형모듈원전(SMR)·원전 수출.",
        "queries": [
            ("SMR 소형모듈원전", "ko", "KR", "KR:ko"),
            ("원전 수출 원자력", "ko", "KR", "KR:ko"),
            ("small modular reactor nuclear SMR", "en-US", "US", "US:en"),
            ("nuclear power data center", "en-US", "US", "US:en"),
        ],
        "match": ["원자력", "원전", "SMR", "원자로", "방사선", "핵연료"],
    },
    {
        "key": "robot", "label": "휴머노이드·로봇", "icon": "🤖",
        "desc": "휴머노이드·협동로봇·자동화 — 감속기·액추에이터·로봇부품 국산화.",
        "queries": [
            ("휴머노이드 로봇", "ko", "KR", "KR:ko"),
            ("로봇 자동화 협동로봇", "ko", "KR", "KR:ko"),
            ("humanoid robot Tesla Optimus", "en-US", "US", "US:en"),
            ("robotics automation investment", "en-US", "US", "US:en"),
        ],
        "match": ["로봇", "액추에이터", "감속기", "협동로봇", "구동장치", "모터"],
    },
    {
        "key": "cooling", "label": "데이터센터 냉각·액침냉각", "icon": "❄️",
        "desc": "고발열 AI 서버 → 액침냉각·수냉·항온항습 등 냉각 인프라가 신성장.",
        "queries": [
            ("데이터센터 냉각 액침냉각", "ko", "KR", "KR:ko"),
            ("data center liquid cooling immersion", "en-US", "US", "US:en"),
        ],
        "match": ["냉각", "쿨링", "액침", "항온항습", "열관리"],
    },
    {
        "key": "power_semi", "label": "전력반도체 (SiC·GaN)", "icon": "🔌",
        "desc": "전기차·전력 인프라용 고효율 전력반도체(SiC/GaN) 수요 확대.",
        "queries": [
            ("전력반도체 SiC 실리콘카바이드", "ko", "KR", "KR:ko"),
            ("silicon carbide power semiconductor SiC", "en-US", "US", "US:en"),
        ],
        "match": ["전력반도체", "SiC", "실리콘카바이드", "GaN", "전력소자"],
    },
    {
        "key": "bio_obesity", "label": "비만치료제·바이오", "icon": "💊",
        "desc": "GLP-1 비만치료제 열풍·바이오시밀러·CDMO — 한국 바이오의 미래 축.",
        "queries": [
            ("비만치료제 GLP-1 신약", "ko", "KR", "KR:ko"),
            ("바이오 CDMO 바이오시밀러", "ko", "KR", "KR:ko"),
            ("GLP-1 obesity drug weight loss", "en-US", "US", "US:en"),
        ],
        "match": ["비만", "GLP", "펩타이드", "바이오시밀러", "신약", "CDMO", "항체", "세포치료"],
    },
    {
        "key": "space_defense", "label": "방산·우주", "icon": "🚀",
        "desc": "K-방산 수출 급증·우주 발사체/위성 — 지정학 긴장 속 구조적 성장.",
        "queries": [
            ("방산 수출 K방산", "ko", "KR", "KR:ko"),
            ("우주 발사체 위성", "ko", "KR", "KR:ko"),
            ("defense export weapons spending", "en-US", "US", "US:en"),
        ],
        "match": ["방산", "미사일", "위성", "발사체", "우주", "유도무기", "항공", "탄약", "함정"],
    },
    {
        "key": "autonomous", "label": "자율주행·전장", "icon": "🚗",
        "desc": "자율주행·SDV로 차량 전장(전자장치) 콘텐츠 급증 — 라이다·차량반도체·ADAS.",
        "queries": [
            ("자율주행 전장 SDV", "ko", "KR", "KR:ko"),
            ("autonomous driving ADAS lidar", "en-US", "US", "US:en"),
        ],
        "match": ["자율주행", "전장", "ADAS", "라이다", "차량용 반도체", "차량용반도체", "센서"],
    },
    {
        "key": "grid_ess", "label": "전력저장·ESS", "icon": "🔋",
        "desc": "신재생·전력망 안정용 에너지저장장치(ESS) 수요 — 배터리의 새 축.",
        "queries": [
            ("ESS 에너지저장장치", "ko", "KR", "KR:ko"),
            ("energy storage ESS grid battery", "en-US", "US", "US:en"),
        ],
        "match": ["ESS", "에너지저장", "전력저장", "이차전지", "배터리"],
    },
    {
        "key": "ai_software", "label": "AI 소프트웨어·클라우드", "icon": "🧠",
        "desc": "생성형 AI·클라우드·온디바이스 AI 소프트웨어 — AI를 '쓰는' 쪽의 성장.",
        "queries": [
            ("AI 소프트웨어 클라우드 생성형", "ko", "KR", "KR:ko"),
            ("generative AI software cloud", "en-US", "US", "US:en"),
        ],
        "match": ["소프트웨어", "클라우드", "생성형", "AI 솔루션", "플랫폼", "보안", "SaaS"],
    },
]


def _is_article(a: dict) -> bool:
    return bool(
        (a.get("title") or "").strip()
        and (a.get("source") or "").strip()
        and (a.get("link") or "").startswith("http")
    )


def _theme_news(theme: dict) -> dict:
    """테마별 뉴스 동향 — 무엇이 구축/투자되고 있나 (count·lean·헤드라인·digest)."""
    pool: list[dict] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=6) as ex:
        def fetch(q):
            try:
                return news._fetch(q[0], q[1], q[2], q[3], 10)
            except Exception:
                return []
        for arts in ex.map(fetch, theme["queries"]):
            for a in arts:
                if not _is_article(a):
                    continue
                t = a.get("title", "").strip()
                if t in seen:
                    continue
                seen.add(t)
                pool.append(a)
    pool.sort(key=lambda a: a.get("ts") or 0, reverse=True)
    pos = sum(1 for a in pool if macro._lean(a["title"]) == "긍정")
    neg = sum(1 for a in pool if macro._lean(a["title"]) == "부정")
    lean = "긍정" if pos > neg else "부정" if neg > pos else "중립"
    digest: list[str] = []
    seen_d: set[str] = set()
    for a in pool[:6]:
        for line in a.get("cluster", []):
            k = line.strip()
            if k and k not in seen_d:
                seen_d.add(k)
                digest.append(line)
            if len(digest) >= 5:
                break
        if len(digest) >= 5:
            break
    return {
        "count": len(pool),
        "pos": pos, "neg": neg, "lean": lean,
        "headlines": [
            {"title": a["title"], "link": a["link"], "source": a["source"]}
            for a in pool[:8]
        ],
        "digest": digest,
    }


def _txt(*vals) -> str:
    out = []
    for v in vals:
        if v is None:
            continue
        if isinstance(v, float) and v != v:  # NaN
            continue
        out.append(str(v))
    return " ".join(out).lower()


def _members(theme: dict, profiles, price_map: dict) -> list[dict]:
    """테마 매핑 종목 — 시세/수익률 + '하락(파란) 미래가치 후보' 플래그."""
    kws = [k.lower() for k in theme["match"]]
    rows: list[dict] = []
    for p in profiles:
        hay = _txt(p.get("name"), p.get("products"), p.get("wics_sector"), p.get("industry"))
        if not any(k in hay for k in kws):
            continue
        tk = p.get("ticker")
        q = price_map.get(tk) or {}
        ret_3m = q.get("ret_3m")
        ret_1m = q.get("ret_1m")
        pfh = q.get("pct_from_high")
        # 최근 하락(파란) = 미래가치 후보: 3개월 수익률 음수 OR 고점 대비 -25% 이하.
        beaten = (ret_3m is not None and ret_3m < 0) or (pfh is not None and pfh <= -25)
        rows.append({
            "ticker": tk,
            "name": p.get("name"),
            "products": p.get("products"),
            "wics_sector": p.get("wics_sector"),
            "market_cap": q.get("market_cap") or p.get("market_cap"),
            "close": q.get("close"),
            "change_pct": q.get("change_pct"),
            "ret_1m": ret_1m,
            "ret_3m": ret_3m,
            "ret_12m": q.get("ret_12m"),
            "pct_from_high": pfh,
            "per": q.get("per"),
            "pbr": q.get("pbr"),
            "beaten": beaten,
        })
    # 시총 큰 순. 시총 없으면 뒤로.
    rows.sort(key=lambda r: (r["market_cap"] or 0), reverse=True)
    return rows[:30]


def _assemble() -> list[dict]:
    try:
        profiles = store.company_profiles().to_dict("records")
    except Exception:
        profiles = []
    try:
        price_map = {r["ticker"]: r for r in store.screen_table_prices()}
    except Exception:
        price_map = {}

    out: list[dict] = []
    for theme in THEMES:
        news_data = _theme_news(theme)
        members = _members(theme, profiles, price_map)
        beaten = [m for m in members if m["beaten"]]
        # 모멘텀 점수: 뉴스량 + 방향 가중(긍정 우위면 가점).
        score = news_data["count"] + (news_data["pos"] - news_data["neg"]) * 2
        out.append({
            "key": theme["key"], "label": theme["label"], "icon": theme["icon"],
            "desc": theme["desc"],
            "news": news_data,
            "momentum_score": score,
            "member_count": len(members),
            "beaten_count": len(beaten),
            "members": members,
        })
    out.sort(key=lambda t: t["momentum_score"], reverse=True)
    return out


def themes(force: bool = False) -> list[dict]:
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]
    data = _assemble()
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data


def index() -> list[dict]:
    """좌측 목록용 — 멤버/헤드라인 제외한 요약."""
    out = []
    for t in themes():
        out.append({
            "key": t["key"], "label": t["label"], "icon": t["icon"], "desc": t["desc"],
            "momentum_score": t["momentum_score"],
            "member_count": t["member_count"], "beaten_count": t["beaten_count"],
            "news_count": t["news"]["count"], "lean": t["news"]["lean"],
        })
    return out


def get(key: str) -> dict | None:
    return next((t for t in themes() if t["key"] == key), None)


# --------------------------------------------------------------------------- #
# 일별 스냅샷 누적 (하루 1개 JSON) — 미래 성장테마가 어떻게 흘러왔는지 쌓인다.
# --------------------------------------------------------------------------- #
_snap_lock = threading.Lock()


def _path(date: str) -> str:
    return str(get_settings().future_themes_dir / f"{date}.json")


def list_dates() -> list[str]:
    d = get_settings().future_themes_dir
    if not d.exists():
        return []
    return sorted((p.stem for p in d.glob("*.json")), reverse=True)


def load(date: str) -> dict | None:
    p = _path(date)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def snapshot(force: bool = False) -> dict:
    """오늘(최신 거래일) 미래 성장테마를 빌드해 JSON으로 저장(이미 있으면 skip)."""
    with _snap_lock:
        date = store.max_price_date()
        if not date:
            return {"status": "no_data"}
        p = _path(date)
        if os.path.exists(p) and not force:
            return {"status": "exists", "date": date, "path": p}
        data = {
            "date": date,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "themes": themes(force=True),
        }
        tmp = f"{p}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, p)
        return {"status": "saved", "date": date, "path": p, "themes": len(data["themes"])}
