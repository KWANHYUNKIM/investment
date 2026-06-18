"""글로벌 경쟁지도 — 기술/산업 클러스터 정의.

'기술이 비슷한 애들끼리' 한국·미국·일본·유럽·중화권 종목을 한 묶음으로 본다. 각
클러스터는 (1) 그 군에 속하는 **한국 WICS 업종**들(우리 DB의 한국 종목을 자동 편입)과
(2) **해외 대표 경쟁사**(심볼·국가)를 갖는다. 해외 종목의 시총·영업이익률 등 펀더멘털은
Finnhub에서 받아 붙인다(``finnhub`` 모듈).

심볼 접미사(야후/핀허브 공통): 미국=무접미, 도쿄=.T, XETRA(독)=.DE, 파리=.PA,
암스테르담=.AS, 스위스=.SW, 런던=.L, 홍콩=.HK, 상해=.SS, 선전=.SZ, 대만=.TW.
"""
from __future__ import annotations

# (symbol, 표시이름, 국가코드)
CLUSTERS: list[dict] = [
    {
        "key": "semiconductor", "label": "반도체 · 파운드리 · 장비",
        "desc": "메모리/시스템반도체 설계·제조와 전공정 장비",
        "kr_wics": ["반도체와반도체장비"],
        "foreign": [
            ("TSM", "TSMC", "TW"), ("NVDA", "NVIDIA", "US"), ("AVGO", "Broadcom", "US"),
            ("INTC", "Intel", "US"), ("AMD", "AMD", "US"), ("MU", "Micron", "US"),
            ("QCOM", "Qualcomm", "US"), ("TXN", "Texas Instruments", "US"),
            ("ASML", "ASML", "NL"), ("AMAT", "Applied Materials", "US"),
            ("LRCX", "Lam Research", "US"), ("KLAC", "KLA", "US"),
            ("8035.T", "도쿄일렉트론", "JP"), ("2330.TW", "TSMC(대만)", "TW"),
            ("000725.SZ", "BOE", "CN"),
        ],
    },
    {
        "key": "battery", "label": "2차전지 · 배터리 소재",
        "desc": "전기차/ESS용 배터리 셀·소재",
        "kr_wics": ["전기제품"],
        "foreign": [
            ("300750.SZ", "CATL", "CN"), ("1211.HK", "BYD", "CN"),
            ("6752.T", "Panasonic", "JP"), ("051910.KS", "LG화학(참고)", "KR"),
            ("ALB", "Albemarle", "US"),
        ],
    },
    {
        "key": "auto", "label": "완성차 · 전기차",
        "desc": "내연/전기 완성차 제조",
        "kr_wics": ["자동차"],
        "foreign": [
            ("TSLA", "Tesla", "US"), ("7203.T", "Toyota", "JP"), ("7267.T", "Honda", "JP"),
            ("VOW3.DE", "Volkswagen", "DE"), ("MBG.DE", "Mercedes-Benz", "DE"),
            ("BMW.DE", "BMW", "DE"), ("STLA", "Stellantis", "US"), ("GM", "GM", "US"),
            ("F", "Ford", "US"), ("1211.HK", "BYD", "CN"), ("7201.T", "Nissan", "JP"),
        ],
    },
    {
        "key": "auto_parts", "label": "자동차 부품",
        "desc": "구동·전장·섀시 등 자동차 부품",
        "kr_wics": ["자동차부품"],
        "foreign": [
            ("6902.T", "Denso", "JP"), ("MGA", "Magna", "US"), ("CON.DE", "Continental", "DE"),
            ("APTV", "Aptiv", "US"), ("ML.PA", "Michelin", "FR"), ("BWA", "BorgWarner", "US"),
        ],
    },
    {
        "key": "bigtech_sw", "label": "빅테크 · 플랫폼 · 소프트웨어",
        "desc": "인터넷 플랫폼·엔터프라이즈 소프트웨어",
        "kr_wics": ["IT서비스", "양방향미디어와서비스", "소프트웨어"],
        "foreign": [
            ("AAPL", "Apple", "US"), ("MSFT", "Microsoft", "US"), ("GOOGL", "Alphabet", "US"),
            ("AMZN", "Amazon", "US"), ("META", "Meta", "US"), ("ORCL", "Oracle", "US"),
            ("CRM", "Salesforce", "US"), ("SAP", "SAP", "DE"), ("ADBE", "Adobe", "US"),
            ("0700.HK", "Tencent", "CN"), ("BABA", "Alibaba", "CN"), ("9988.HK", "Alibaba(HK)", "CN"),
        ],
    },
    {
        "key": "pharma_bio", "label": "제약 · 바이오",
        "desc": "신약·바이오시밀러·CDMO",
        "kr_wics": ["제약", "생물공학"],
        "foreign": [
            ("LLY", "Eli Lilly", "US"), ("NVO", "Novo Nordisk", "DK"), ("JNJ", "Johnson & Johnson", "US"),
            ("ROG.SW", "Roche", "CH"), ("NVS", "Novartis", "CH"), ("PFE", "Pfizer", "US"),
            ("MRK", "Merck", "US"), ("AZN", "AstraZeneca", "UK"), ("ABBV", "AbbVie", "US"),
            ("4568.T", "Daiichi Sankyo", "JP"), ("SAN.PA", "Sanofi", "FR"),
        ],
    },
    {
        "key": "display", "label": "디스플레이",
        "desc": "OLED/LCD 패널",
        "kr_wics": [],
        "foreign": [
            ("000725.SZ", "BOE", "CN"), ("2409.TW", "AUO", "TW"), ("6740.T", "JDI", "JP"),
        ],
    },
    {
        "key": "steel", "label": "철강 · 금속",
        "desc": "철강·비철금속",
        "kr_wics": ["철강"],
        "foreign": [
            ("5401.T", "Nippon Steel", "JP"), ("MT", "ArcelorMittal", "LU"),
            ("NUE", "Nucor", "US"), ("X", "US Steel", "US"), ("600019.SS", "Baosteel", "CN"),
        ],
    },
    {
        "key": "chemical", "label": "화학 · 소재",
        "desc": "기초/정밀 화학",
        "kr_wics": ["화학"],
        "foreign": [
            ("BAS.DE", "BASF", "DE"), ("DOW", "Dow", "US"), ("LIN", "Linde", "US"),
            ("4188.T", "Mitsubishi Chemical", "JP"), ("DD", "DuPont", "US"),
        ],
    },
    {
        "key": "shipbuilding", "label": "조선 · 중공업",
        "desc": "선박·해양플랜트·중공업",
        "kr_wics": ["조선"],
        "foreign": [
            ("7011.T", "Mitsubishi Heavy", "JP"), ("7012.T", "Kawasaki Heavy", "JP"),
        ],
    },
    {
        "key": "defense", "label": "방산 · 우주항공",
        "desc": "방위산업·항공우주",
        "kr_wics": ["우주항공과국방"],
        "foreign": [
            ("LMT", "Lockheed Martin", "US"), ("RTX", "RTX", "US"), ("NOC", "Northrop Grumman", "US"),
            ("BA", "Boeing", "US"), ("AIR.PA", "Airbus", "FR"), ("GD", "General Dynamics", "US"),
        ],
    },
    {
        "key": "bank_fin", "label": "은행 · 금융",
        "desc": "은행·종합금융",
        "kr_wics": ["은행", "증권", "카드", "기타금융"],
        "foreign": [
            ("JPM", "JPMorgan", "US"), ("BAC", "Bank of America", "US"), ("WFC", "Wells Fargo", "US"),
            ("8306.T", "Mitsubishi UFJ", "JP"), ("HSBC", "HSBC", "UK"), ("8316.T", "Sumitomo Mitsui", "JP"),
        ],
    },
    {
        "key": "media_game", "label": "엔터 · 미디어 · 게임",
        "desc": "콘텐츠·게임·스트리밍",
        "kr_wics": [],
        "foreign": [
            ("7974.T", "Nintendo", "JP"), ("6758.T", "Sony", "JP"), ("NFLX", "Netflix", "US"),
            ("DIS", "Disney", "US"), ("9999.HK", "NetEase", "CN"),
        ],
    },
    {
        "key": "consumer", "label": "화장품 · 소비재",
        "desc": "화장품·생활소비재·럭셔리",
        "kr_wics": ["화장품", "가정용품과개인용품"],
        "foreign": [
            ("OR.PA", "L'Oreal", "FR"), ("EL", "Estee Lauder", "US"), ("4911.T", "Shiseido", "JP"),
            ("MC.PA", "LVMH", "FR"), ("PG", "P&G", "US"), ("NESN.SW", "Nestle", "CH"),
        ],
    },
    {
        "key": "ecommerce", "label": "이커머스 · 인터넷 유통",
        "desc": "온라인 커머스",
        "kr_wics": [],
        "foreign": [
            ("AMZN", "Amazon", "US"), ("BABA", "Alibaba", "CN"), ("CPNG", "Coupang", "US"),
            ("PDD", "PDD(Temu)", "CN"), ("MELI", "MercadoLibre", "AR"), ("3690.HK", "Meituan", "CN"),
        ],
    },
]


def all_foreign_symbols() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for c in CLUSTERS:
        for sym, _nm, _ctry in c["foreign"]:
            if not sym.endswith(".KS") and sym not in seen:  # KR은 자체 DB에서
                seen.add(sym)
                out.append(sym)
    return out


def cluster(key: str) -> dict | None:
    return next((c for c in CLUSTERS if c["key"] == key), None)
