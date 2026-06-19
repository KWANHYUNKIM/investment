"""글로벌 경쟁지도 — 기술/산업 클러스터 정의.

'기술이 비슷한 애들끼리' 한국·미국·일본·유럽·중화권 종목을 한 묶음으로 본다. 각
클러스터는 (1) 그 군에 속하는 **한국 WICS 업종**들(우리 DB의 한국 종목을 자동 편입)과
(2) **해외 대표 경쟁사**(심볼·국가)를 갖는다. 해외 종목의 시총·영업이익률 등 펀더멘털은
Finnhub에서 받아 붙인다(``finnhub`` 모듈).

해외 심볼 정책: Finnhub 무료티어는 **미국 거래소만** 지원(.T/.DE/.HK/.SZ/.TW/.SW/.PA 등
원거래소 심볼은 전부 NONE 반환). 그래서 비미국 대형주는 **미국 ADR 티커**로 받는다
(예: 도요타=TM, 소니=SONY, 텐센트=TCEHY, 도쿄일렉트론=TOELY, 파나소닉=PCRFF). ADR은
비율 지표(ROIC·마진·성장률 등)가 통화·ADR배율과 무관해 정확하고, 시총·매출은
``metric.marketCapitalization``(보고통화)와 P/S로 환산한다(finnhub.fetch 참조).
ADR이 없는 종목(CATL 300750.SZ, BOE/AUO/JDI, Baosteel)은 원심볼을 두되 정량값은
비고, 정성 프로파일(global_intel)만 표시된다.
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
            ("TOELY", "도쿄일렉트론", "JP"),
        ],
    },
    {
        "key": "battery", "label": "2차전지 · 배터리 소재",
        "desc": "전기차/ESS용 배터리 셀·소재",
        "kr_wics": ["전기제품"],
        "foreign": [
            ("300750.SZ", "CATL", "CN"), ("BYDDY", "BYD", "CN"),
            ("PCRFF", "Panasonic", "JP"), ("ALB", "Albemarle", "US"),
        ],
    },
    {
        "key": "auto", "label": "완성차 · 전기차",
        "desc": "내연/전기 완성차 제조",
        "kr_wics": ["자동차"],
        "foreign": [
            ("TSLA", "Tesla", "US"), ("TM", "Toyota", "JP"), ("HMC", "Honda", "JP"),
            ("VWAGY", "Volkswagen", "DE"), ("MBGYY", "Mercedes-Benz", "DE"),
            ("BMWYY", "BMW", "DE"), ("STLA", "Stellantis", "US"), ("GM", "GM", "US"),
            ("F", "Ford", "US"), ("BYDDY", "BYD", "CN"), ("NSANY", "Nissan", "JP"),
        ],
    },
    {
        "key": "auto_parts", "label": "자동차 부품",
        "desc": "구동·전장·섀시 등 자동차 부품",
        "kr_wics": ["자동차부품"],
        "foreign": [
            ("DNZOY", "Denso", "JP"), ("MGA", "Magna", "US"), ("CTTAY", "Continental", "DE"),
            ("APTV", "Aptiv", "US"), ("MGDDY", "Michelin", "FR"), ("BWA", "BorgWarner", "US"),
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
            ("TCEHY", "Tencent", "CN"), ("BABA", "Alibaba", "CN"),
        ],
    },
    {
        "key": "pharma_bio", "label": "제약 · 바이오",
        "desc": "신약·바이오시밀러·CDMO",
        "kr_wics": ["제약", "생물공학"],
        "foreign": [
            ("LLY", "Eli Lilly", "US"), ("NVO", "Novo Nordisk", "DK"), ("JNJ", "Johnson & Johnson", "US"),
            ("RHHBY", "Roche", "CH"), ("NVS", "Novartis", "CH"), ("PFE", "Pfizer", "US"),
            ("MRK", "Merck", "US"), ("AZN", "AstraZeneca", "UK"), ("ABBV", "AbbVie", "US"),
            ("DSNKY", "Daiichi Sankyo", "JP"), ("SNY", "Sanofi", "FR"),
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
            ("NPSCY", "Nippon Steel", "JP"), ("MT", "ArcelorMittal", "LU"),
            ("NUE", "Nucor", "US"), ("X", "US Steel", "US"), ("600019.SS", "Baosteel", "CN"),
        ],
    },
    {
        "key": "chemical", "label": "화학 · 소재",
        "desc": "기초/정밀 화학",
        "kr_wics": ["화학"],
        "foreign": [
            ("BASFY", "BASF", "DE"), ("DOW", "Dow", "US"), ("LIN", "Linde", "US"),
            ("MTLHY", "Mitsubishi Chemical", "JP"), ("DD", "DuPont", "US"),
        ],
    },
    {
        "key": "shipbuilding", "label": "조선 · 중공업",
        "desc": "선박·해양플랜트·중공업",
        "kr_wics": ["조선"],
        "foreign": [
            ("MHVYF", "Mitsubishi Heavy", "JP"), ("KWHIY", "Kawasaki Heavy", "JP"),
        ],
    },
    {
        "key": "defense", "label": "방산 · 우주항공",
        "desc": "방위산업·항공우주",
        "kr_wics": ["우주항공과국방"],
        "foreign": [
            ("LMT", "Lockheed Martin", "US"), ("RTX", "RTX", "US"), ("NOC", "Northrop Grumman", "US"),
            ("BA", "Boeing", "US"), ("EADSY", "Airbus", "FR"), ("GD", "General Dynamics", "US"),
        ],
    },
    {
        "key": "bank_fin", "label": "은행 · 금융",
        "desc": "은행·종합금융",
        "kr_wics": ["은행", "증권", "카드", "기타금융"],
        "foreign": [
            ("JPM", "JPMorgan", "US"), ("BAC", "Bank of America", "US"), ("WFC", "Wells Fargo", "US"),
            ("MUFG", "Mitsubishi UFJ", "JP"), ("HSBC", "HSBC", "UK"), ("SMFG", "Sumitomo Mitsui", "JP"),
        ],
    },
    {
        "key": "media_game", "label": "엔터 · 미디어 · 게임",
        "desc": "콘텐츠·게임·스트리밍",
        "kr_wics": [],
        "foreign": [
            ("NTDOY", "Nintendo", "JP"), ("SONY", "Sony", "JP"), ("NFLX", "Netflix", "US"),
            ("DIS", "Disney", "US"), ("NTES", "NetEase", "CN"),
        ],
    },
    {
        "key": "consumer", "label": "화장품 · 소비재",
        "desc": "화장품·생활소비재·럭셔리",
        "kr_wics": ["화장품", "가정용품과개인용품"],
        "foreign": [
            ("LRLCY", "L'Oreal", "FR"), ("EL", "Estee Lauder", "US"), ("SSDOY", "Shiseido", "JP"),
            ("LVMUY", "LVMH", "FR"), ("PG", "P&G", "US"), ("NSRGY", "Nestle", "CH"),
        ],
    },
    {
        "key": "ecommerce", "label": "이커머스 · 인터넷 유통",
        "desc": "온라인 커머스",
        "kr_wics": [],
        "foreign": [
            ("AMZN", "Amazon", "US"), ("BABA", "Alibaba", "CN"), ("CPNG", "Coupang", "US"),
            ("PDD", "PDD(Temu)", "CN"), ("MELI", "MercadoLibre", "AR"), ("MPNGY", "Meituan", "CN"),
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
