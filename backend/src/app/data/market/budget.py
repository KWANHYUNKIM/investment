"""가계부 — 급여·카드내역 관리 + 저축/투자 계획.

로컬 단일 사용자용이라 파일 하나(``data/budget.json``)에 월 수입(급여)과 거래내역
(카드/현금)을 저장한다. 카드사 CSV를 붙여넣으면 날짜·가맹점·금액을 추정 파싱하고
가맹점명으로 지출 카테고리를 자동 분류한다. 월별 지출을 집계하고, 수입−지출 여유로
비상금·저축·투자(주식 포트폴리오 자산 포함) 배분 계획을 제안한다.
"""
from __future__ import annotations

import json
import os
import re
import threading

from app.core.config import get_settings

_lock = threading.Lock()

# 가맹점명 → 카테고리 (부분일치, 위에서부터 우선)
_KEYWORDS: list[tuple[str, list[str]]] = [
    ("카페/간식", [
        "스타벅스", "starbucks", "커피", "coffee", "카페", "cafe", "이디야", "투썸", "twosome", "빽다방", "메가커피", "메가엠지씨",
        "컴포즈", "우지커피", "카페베네", "커피빈", "폴바셋", "탐앤탐스", "할리스", "엔젤리너스", "파스쿠찌", "블루보틀", "매머드",
        "더벤티", "감성커피", "빈스빈스", "테라로사", "프릳츠", "커피나무", "그라찌에",
        "베이커리", "파리바게", "뚜레쥬르", "던킨", "크리스피", "성심당", "공차", "쥬씨", "설빙", "디저트", "도넛", "케이크", "빙수",
        "베스킨", "배스킨", "나뚜루", "아이스크림", "요거트", "요거프레소", "요아정", "명랑핫도그", "핫도그", "붕어빵", "와플",
        "마카롱", "제과", "베이글", "프레첼", "더리터", "커피에반하다", "텐퍼센트", "만랩커피", "하삼동", "커피베이",
    ]),
    ("식비/외식", [
        "식당", "김밥", "김밥천국", "김밥나라", "분식", "국밥", "국수", "국수나무", "고기", "치킨", "교촌", "bbq", "bhc", "굽네",
        "네네", "페리카나", "처갓집", "노랑통닭", "멕시카나", "60계", "푸라닭", "자담", "호식이", "티바", "또래오래", "지코바", "굽는남자",
        "피자", "도미노", "피자헛", "미스터피자", "파파존스", "반올림피자", "피자스쿨", "고피자", "7번가피자",
        "버거", "롯데리아", "맘스터치", "kfc", "버거킹", "노브랜드버거", "써브웨이", "subway", "프랭크버거", "쉐이크쉑", "파이브가이즈", "맥도날드",
        "배달", "배민", "요기요", "쿠팡이츠", "땡겨요",
        "김가네", "죽집", "본죽", "칼국수", "냉면", "육쌈냉면", "떡볶", "엽떡", "신전", "죠스", "국대떡볶", "포차", "주점", "호프",
        "이자카야", "선술집", "포장마차", "한신포차",
        "막창", "곱창", "대창", "감자탕", "삼겹", "갈비", "돼지", "소갈비", "구이", "숯불", "하남돼지집", "새마을식당", "명륜진사",
        "초밥", "스시", "스시로", "갓덴", "횟집", "물회", "돈까스", "돈가스", "뷔페", "우동", "라멘", "라면", "파스타", "짜장",
        "짬뽕", "중국집", "홍콩반점", "마라", "훠궈", "양꼬치",
        "쌀국수", "반쎄오", "백반", "한식", "일식", "중식", "양식", "만두", "왕만두", "족발", "보쌈", "원할머니", "족발야시장",
        "찜닭", "닭갈비", "쭈꾸미", "낙지", "과메기", "올갱이", "꽃마름", "한솥", "본도시락", "도시락", "샐러드", "샤브",
        "부대찌개", "김치찌개", "된장", "설렁탕", "곰탕", "추어탕", "해장국", "순대", "떡갈비", "제육", "덮밥", "비빔밥",
        "타코", "부리또", "멕시칸", "커리", "요리", "주막", "실비", "놀부", "이바돔", "food", "restaurant", "gimbap",
        "본가", "미정국수", "역전우동", "롤링파스타", "인생설렁탕", "성성식당", "리춘시장", "원조쌈밥", "빽보이피자", "돌배기집",
        "두찜", "배떡", "청년다방", "우리할매", "삼첩분식", "두끼", "이삭토스트", "에그드랍", "아딸", "응급실국물떡볶",
        "천냥김밥", "종로김밥", "바르다김선생", "고봉민", "얌샘", "한촌설렁탕", "설농", "유가네", "채선당", "할매", "큰맘",
        "오봉집", "명동교자", "강강술래", "죽이야기", "포메인", "미소야", "코코이찌방",
    ]),
    ("장보기/마트", [
        "이마트", "emart", "홈플러스", "롯데마트", "마트", "마켓컬리", "컬리", "오아시스마켓", "편의점", "gs25", "지에스(gs)", "지에스25",
        "cu", "씨유", "세븐일레븐", "이마트24", "미니스톱", "코스트코", "costco", "농협", "하나로", "축협", "수협", "ssg",
        "슈퍼", "노브랜드", "트레이더스", "킴스클럽", "롯데슈퍼", "gs더프레시", "정육", "청과", "수산", "반찬", "식자재",
    ]),
    ("교통/차량", [
        "택시", "카카오t", "타다", "우버", "버스", "지하철", "교통", "메트로", "도시철도", "주유", "gs칼텍스", "칼텍스", "에스오일",
        "s-oil", "sk에너지", "현대오일", "오일뱅크", "알뜰주유", "하이패스", "코레일", "철도", "ktx", "srt", "수서고속", "고속버스", "시외버스",
        "주차", "파킹", "하이파킹", "나이스파크", "아이파킹", "모두의주차", "렌트", "쏘카", "그린카", "고속도로", "티머니", "교통카드",
        "충전", "휴게소", "톨게이트", "카센터", "타이어", "블루핸즈", "현대차", "기아자동차", "자동차정비",
        "스윙", "킥보드", "씽씽", "지쿠", "롯데렌터카", "sk렌터카", "기아플렉스", "딜카", "케이카", "엔카", "세차", "카닥",
    ]),
    ("여행/숙박", [
        "호텔", "hotel", "리조트", "펜션", "모텔", "게스트하우스", "야놀자", "여기어때", "호텔스", "파르나스", "여행", "투어",
        "숙박", "아고다", "agoda", "부킹닷컴", "booking", "airbnb", "에어비앤비", "대한항공", "아시아나", "제주항공", "에어부산",
        "에어서울", "진에어", "티웨이", "익스피디아", "expedia", "하나투어", "모두투어", "노랑풍선", "인터파크투어", "kkday",
        "클룩", "klook", "콘도", "워터파크",
    ]),
    ("통신", ["skt", "lgu", "u+", "유플러스", "통신", "요금제", "알뜰폰", "sk텔레콤", "케이티", "엘지유플러스", "헬로모바일", "리브엠"]),
    ("주거/공과금", ["관리비", "전기요금", "가스요금", "수도요금", "월세", "임대료", "도시가스", "한국전력", "한전", "상하수도",
                      "아파트관리", "부동산", "중개", "정수기", "렌탈"]),
    ("쇼핑", [
        "쿠팡", "coupang", "11번가", "g마켓", "지마켓", "gmarket", "옥션", "auction", "위메프", "티몬", "ssg닷컴", "신세계몰",
        "롯데온", "네이버쇼핑", "스마트스토어", "오늘의집", "당근마켓", "번개장터", "중고나라",
        "무신사", "musinsa", "지그재그", "에이블리", "브랜디", "29cm", "w컨셉", "자라", "zara", "유니클로", "uniqlo", "h&m",
        "스파오", "탑텐", "에잇세컨즈", "나이키", "아디다스", "뉴발란스", "무인양품", "abc마트", "슈마커", "크록스",
        "올리브영", "다이소", "백화점", "신세계", "롯데백화점", "현대백화점", "갤러리아", "ak플라자", "코엑스", "스타필드",
        "아울렛", "하이마트", "전자랜드", "이케아", "ikea", "토이", "문구", "알리", "aliexpress", "테무", "temu", "쉬인", "shein",
        "가구", "삼성전자", "lg전자", "애플스토어", "롬앤", "이니스프리", "더페이스샵", "에뛰드", "아리따움", "미샤", "토니모리",
        "네이처리퍼블릭", "클리오", "닥터자르트", "설화수", "이랜드", "미쏘", "로엠", "후아유", "폴햄", "지오다노", "리바이스",
        "헤지스", "빈폴", "탑텐", "스파오", "커버낫", "디스이즈네버댓", "마리떼", "패션플러스", "화해", "쿠팡윙", "발란", "머스트잇",
    ]),
    ("문화/여가", [
        "넷플릭스", "netflix", "유튜브", "youtube", "스포티", "spotify", "왓챠", "티빙", "tving", "웨이브", "wavve", "디즈니", "disney",
        "쿠팡플레이", "멜론", "melon", "지니뮤직", "genie", "벅스", "플로", "flo", "영화", "cgv", "메가박스", "롯데시네마", "예술의전당",
        "게임", "스팀", "steam", "닌텐도", "플레이스테이션", "노래", "코인노래", "pc방", "볼링", "당구", "찜질", "사우나", "스크린골프",
        "골프", "헬스", "휘트니스", "피트니스", "필라테스", "요가", "클라이밍", "수영장", "공연", "콘서트", "예매", "인터파크",
        "놀이공원", "에버랜드", "롯데월드", "아쿠아리움", "방탈출",
    ]),
    ("의료/건강", ["병원", "약국", "약사", "의원", "치과", "한의원", "클리닉", "보건소", "메디", "정형외과", "내과", "이비인후과",
                   "피부과", "안과", "산부인과", "소아과", "동물병원", "동물메디컬", "재활", "검진", "의료", "한약", "성형",
                   "안경", "선글라스", "룩옵티컬", "다비치안경", "렌즈", "라식", "아이웨어"]),
    ("금융/보험", ["보험", "이자", "대출", "증권", "카드론", "현금서비스", "수수료", "은행", "캐피탈", "저축은행", "삼성생명",
                   "한화생명", "메리츠", "db손해", "현대해상", "kb손해", "연금", "공제회"]),
    ("교육/자기계발", ["학원", "교육", "서점", "교보문고", "영풍문고", "yes24", "알라딘", "인강", "강의", "클래스101", "패스트캠퍼스",
                       "인프런", "대학교", "대학원", "등록금", "학습지", "구몬", "눈높이", "과외", "독서실", "스터디카페", "어학원", "ebs",
                       "밀리의서재", "윌라", "시원스쿨", "야나두", "해커스", "메가스터디", "이투스", "대성마이맥", "웅진", "재능교육",
                       "교원", "시대인재", "리디북스", "리디셀렉트", "듀오링고", "산타토익"]),
    ("구독/기타결제", ["구독", "멤버십", "애플", "app store", "구글", "google", "apple", "aws", "chatgpt", "openai", "claude", "anthropic",
                       "subscription", "노션", "notion", "어도비", "adobe", "microsoft", "office365", "icloud", "네이버플러스", "쿠팡와우",
                       "github", "figma", "canva", "dropbox", "midjourney", "perplexity"]),
]


CATEGORIES = [
    "식비/외식", "카페/간식", "장보기/마트", "교통/차량", "여행/숙박", "통신",
    "주거/공과금", "쇼핑", "문화/여가", "의료/건강", "금융/보험", "교육/자기계발",
    "구독/기타결제", "기타",
]


def categorize(merchant: str) -> str:
    m = (merchant or "").lower()
    for cat, kws in _KEYWORDS:
        for kw in kws:
            if kw.lower() in m:
                return cat
    return "기타"


def _safe_user(user: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", user or "default")


def _path(user: str) -> str:
    return str(get_settings().data_dir / f"budget_{_safe_user(user)}.json")


def _load(user: str) -> dict:
    p = _path(user)
    if not os.path.exists(p):
        return {"income": {"monthly_net": 0, "extra": 0, "memo": ""}, "transactions": [], "seq": 0, "cat_rules": {}}
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        d.setdefault("income", {"monthly_net": 0, "extra": 0, "memo": ""})
        d.setdefault("transactions", [])
        d.setdefault("seq", max((t.get("id", 0) for t in d["transactions"]), default=0))
        d.setdefault("cat_rules", {})
        return d
    except Exception:
        return {"income": {"monthly_net": 0, "extra": 0, "memo": ""}, "transactions": [], "seq": 0, "cat_rules": {}}


def _save(user: str, d: dict) -> None:
    p = _path(user)
    tmp = f"{p}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)


# --- 수입(급여) ------------------------------------------------------------
def set_income(user: str, monthly_net: float, extra: float = 0, memo: str = "") -> dict:
    with _lock:
        d = _load(user)
        d["income"] = {"monthly_net": float(monthly_net or 0), "extra": float(extra or 0), "memo": memo or ""}
        _save(user, d)
    return d["income"]


# --- 거래내역 파싱/추가 ----------------------------------------------------
_DATE = re.compile(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})")
_MONEY = re.compile(r"-?\d{1,3}(?:,\d{3})+|-?\d+")


def _norm_date(s: str) -> str | None:
    m = _DATE.search(s)
    if not m:
        return None
    y, mo, da = m.group(1), int(m.group(2)), int(m.group(3))
    return f"{y}-{mo:02d}-{da:02d}"


def parse_csv(text: str) -> list[dict]:
    """카드사 CSV/표를 붙여넣으면 날짜·가맹점·금액을 추정 파싱한다.

    구분자(콤마/탭)로 나눈 뒤: 날짜 형태 필드 1개, 금액 형태(콤마 포함 숫자) 1개,
    나머지 가장 긴 텍스트를 가맹점으로 본다. 날짜가 없는 줄(헤더/합계)은 건너뛴다.
    """
    rows: list[dict] = []
    int_re = re.compile(r"-?\d+")
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        date = _norm_date(line)
        if not date:
            continue  # 헤더/합계/설명 줄(날짜 없음)
        # 천 단위 콤마(숫자와 숫자 사이 콤마)를 먼저 제거해야 필드 콤마와 구분된다.
        norm = re.sub(r"(?<=\d),(?=\d)", "", line)
        fields = [f.strip() for f in re.split(r"[\t,]", norm) if f.strip()]

        # 금액 후보: 날짜 조각이 아닌 순수 정수 필드 → 절댓값 최대(보통 결제금액)
        amounts = []
        for f in fields:
            if _DATE.search(f):
                continue
            fx = f.replace(" ", "")
            if int_re.fullmatch(fx):
                try:
                    amounts.append(float(fx))
                except ValueError:
                    pass
        if not amounts:
            continue
        amount = max(amounts, key=abs)

        # 가맹점: 날짜도 아니고 순수 숫자도 아닌 필드 중 가장 긴 것
        cand = [f for f in fields
                if not _DATE.search(f) and not int_re.fullmatch(f.replace(" ", ""))]
        merchant = max(cand, key=len) if cand else "미상"
        rows.append({"date": date, "merchant": merchant, "amount": amount,
                     "category": categorize(merchant)})
    return rows


# --- 급여명세서(엑셀/PDF) 파싱 --------------------------------------------
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


def _lines_from_excel(data: bytes) -> list[str]:
    import io
    import pandas as pd
    lines: list[str] = []
    try:
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
    except Exception:
        return lines
    for df in sheets.values():
        for row in df.itertuples(index=False):
            cells = [str(c) for c in row if c is not None and str(c) != "nan"]
            if cells:
                lines.append("\t".join(cells))
    return lines


def _lines_from_pdf(data: bytes) -> list[str]:
    import io
    try:
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in r.pages)
        return [ln for ln in text.splitlines() if ln.strip()]
    except Exception:
        return []


def parse_payslip(filename: str, data: bytes) -> dict:
    """급여명세서(.xlsx/.xls/.pdf/.csv)에서 실수령액·지급·공제를 추출한다.

    라벨(실수령액/지급총액/공제계) 근처 숫자를 우선 잡고, 못 찾으면 급여 범위의
    가장 큰 숫자를 실수령액 후보로 돌려준다(사용자가 확인 후 저장).
    """
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        lines = _lines_from_excel(data)
    elif name.endswith(".pdf"):
        lines = _lines_from_pdf(data)
    else:
        try:
            lines = data.decode("utf-8", errors="ignore").splitlines()
        except Exception:
            lines = []

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
                label = ln.strip()[:24]
                cands.append({"label": label, "amount": round(max(nums))})
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


# --- 카드사 파일(엑셀/CSV) 헤더 인식 파싱 ---------------------------------
_H_DATE = ["거래일", "이용일", "승인일", "매출일", "사용일", "일자", "날짜", "결제일"]
_H_MERCH = ["가맹점", "상호", "이용내역", "적요", "내용", "이용하신곳", "가맹점명"]
_H_AMT_STRONG = ["이용금액", "승인금액", "결제금액", "매출금액", "사용금액", "국내이용금액", "이용하신금액", "청구금액"]
_H_AMT_WEAK = ["금액", "합계"]
_H_AMT_BAD = ["번호", "한도", "잔액", "포인트", "누계", "수수료", "할부", "해외", "세금", "봉사료", "면세", "적립"]
_H_CANCEL = ["취소", "환불", "상태"]


def _clean_amt(s) -> float | None:
    try:
        v = float(str(s).replace(",", "").replace(" ", "").replace("원", ""))
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def _excel_rows(data: bytes) -> list[list]:
    import io
    import pandas as pd
    rows: list[list] = []
    try:
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
    except Exception:
        return rows
    for df in sheets.values():
        for row in df.itertuples(index=False):
            rows.append([None if (c is None or str(c) == "nan") else c for c in row])
    return rows


def parse_rows(rows: list[list]) -> list[dict] | None:
    """헤더 행을 찾아 날짜·가맹점·금액 컬럼을 매핑해 파싱(카드사 엑셀/표).

    헤더를 못 찾으면 None(호출부가 기존 휴리스틱으로 폴백).
    """
    def has(cell: str, cands, bad=None) -> bool:
        return any(k in cell for k in cands) and (not bad or not any(b in cell for b in bad))

    hidx, dcol, mcol, acol, ccol = -1, -1, -1, -1, -1
    for i, row in enumerate(rows[:15]):
        cells = ["" if c is None else str(c) for c in row]
        d = next((j for j, c in enumerate(cells) if has(c, _H_DATE)), -1)
        a = next((j for j, c in enumerate(cells) if has(c, _H_AMT_STRONG, _H_AMT_BAD)), -1)
        if a == -1:
            a = next((j for j, c in enumerate(cells) if has(c, _H_AMT_WEAK, _H_AMT_BAD)), -1)
        if d != -1 and a != -1:
            hidx, dcol, acol = i, d, a
            mcol = next((j for j, c in enumerate(cells) if has(c, _H_MERCH)), -1)
            ccol = next((j for j, c in enumerate(cells) if has(c, _H_CANCEL)), -1)
            break
    if hidx == -1:
        return None

    out: list[dict] = []
    for row in rows[hidx + 1:]:
        cells = ["" if c is None else str(c) for c in row]
        if dcol >= len(cells) or acol >= len(cells):
            continue
        date = _norm_date(cells[dcol])
        amt = _clean_amt(cells[acol])
        if not date or amt is None:
            continue
        merchant = cells[mcol].strip() if (0 <= mcol < len(cells) and cells[mcol].strip()) else "미상"
        if 0 <= ccol < len(cells) and any(k in cells[ccol] for k in ["취소", "환불"]):
            amt = -abs(amt)
        out.append({"date": date, "merchant": merchant, "amount": amt, "category": categorize(merchant)})
    return out


def import_file(user: str, filename: str, data: bytes) -> dict:
    """카드사 엑셀/CSV 파일 업로드 → 거래내역 등록(헤더 인식, 실패 시 휴리스틱)."""
    name = (filename or "").lower()
    text = ""
    if name.endswith((".xlsx", ".xls")):
        rows = _excel_rows(data)
    else:
        try:
            text = data.decode("utf-8")
        except Exception:
            text = data.decode("euc-kr", errors="ignore")
        rows = [re.split(r"[\t,]", ln) for ln in text.splitlines()]

    parsed = parse_rows(rows)
    if parsed is None:  # 헤더 못 찾음 → 기존 텍스트 휴리스틱
        if not text:
            text = "\n".join("\t".join("" if c is None else str(c) for c in r) for r in rows)
        parsed = parse_csv(text)
    if parsed:
        add_transactions(user, parsed)
    return {"parsed": len(parsed), "sample": parsed[:8]}


def add_transactions(user: str, items: list[dict]) -> dict:
    with _lock:
        d = _load(user)
        seq = d.get("seq", 0)
        rules = d.get("cat_rules", {})
        for it in items or []:
            date = _norm_date(str(it.get("date", ""))) or str(it.get("date", ""))[:10]
            try:
                amount = float(str(it.get("amount", 0)).replace(",", ""))
            except (TypeError, ValueError):
                continue
            merchant = str(it.get("merchant", "")).strip() or "미상"
            # 사용자 지정 규칙(가맹점→분류) 우선, 없으면 자동 분류
            cat = rules.get(merchant) or it.get("category") or categorize(merchant)
            seq += 1
            d["transactions"].append({"id": seq, "date": date, "merchant": merchant,
                                      "amount": amount, "category": cat})
        d["seq"] = seq
        _save(user, d)
    return {"added": len(items or [])}


def import_csv(user: str, text: str) -> dict:
    parsed = parse_csv(text)
    if parsed:
        add_transactions(user, parsed)
    return {"parsed": len(parsed), "sample": parsed[:5]}


def delete_transaction(user: str, tx_id: int) -> dict:
    with _lock:
        d = _load(user)
        d["transactions"] = [t for t in d["transactions"] if t.get("id") != tx_id]
        _save(user, d)
    return {"ok": True}


def set_category(user: str, tx_id: int, category: str, apply_all: bool = True) -> dict:
    """거래의 분류를 바꾼다. apply_all이면 같은 가맹점 규칙으로 저장+기존 전부 재분류."""
    category = (category or "").strip() or "기타"
    with _lock:
        d = _load(user)
        target = next((t for t in d["transactions"] if t.get("id") == tx_id), None)
        if not target:
            return {"ok": False}
        target["category"] = category
        if apply_all:
            merchant = target.get("merchant")
            d.setdefault("cat_rules", {})[merchant] = category
            for t in d["transactions"]:
                if t.get("merchant") == merchant:
                    t["category"] = category
        _save(user, d)
    return {"ok": True, "category": category, "applied_all": apply_all}


def clear_month(user: str, month: str) -> dict:
    with _lock:
        d = _load(user)
        before = len(d["transactions"])
        d["transactions"] = [t for t in d["transactions"] if not str(t.get("date", "")).startswith(month)]
        _save(user, d)
    return {"removed": before - len(d["transactions"])}


# --- 집계 ------------------------------------------------------------------
def _months(txs: list[dict]) -> list[str]:
    return sorted({str(t.get("date", ""))[:7] for t in txs if t.get("date")}, reverse=True)


def summary(user: str, month: str | None = None) -> dict:
    d = _load(user)
    txs = d["transactions"]
    months = _months(txs)
    if not month:
        month = months[0] if months else ""

    mtx = [t for t in txs if str(t.get("date", "")).startswith(month)]
    spent = sum(t["amount"] for t in mtx if t["amount"] > 0)
    refund = sum(-t["amount"] for t in mtx if t["amount"] < 0)
    net_spent = spent - refund

    by_cat: dict[str, float] = {}
    for t in mtx:
        if t["amount"] > 0:
            by_cat[t["category"]] = by_cat.get(t["category"], 0.0) + t["amount"]
    cats = sorted(({"category": k, "amount": round(v),
                    "pct": round(v / spent * 100, 1) if spent else 0} for k, v in by_cat.items()),
                  key=lambda x: -x["amount"])

    inc = d["income"]
    income_total = (inc.get("monthly_net") or 0) + (inc.get("extra") or 0)
    savings_possible = income_total - net_spent

    return {
        "month": month,
        "months": months,
        "income": inc,
        "income_total": round(income_total),
        "spent": round(net_spent),
        "refund": round(refund),
        "savings_possible": round(savings_possible),
        "savings_rate": round(savings_possible / income_total * 100, 1) if income_total else None,
        "by_category": cats,
        "categories": CATEGORIES,
        "count": len(mtx),
        "transactions": sorted(mtx, key=lambda t: str(t.get("date", "")), reverse=True),
    }


def plan(user: str, emergency_months: int = 3, invest_ratio: float = 0.5) -> dict:
    """저축/투자 계획: 최근 월평균 지출과 수입 여유로 비상금·저축·투자를 배분한다.

    주식 포트폴리오 평가액을 '이미 투자 중인 자산'으로 포함한다.
    invest_ratio: 매월 여유자금 중 투자에 배분할 비율(나머지는 안전저축).
    """
    d = _load(user)
    txs = d["transactions"]
    months = _months(txs)

    # 최근 최대 3개월 평균 지출
    recent = months[:3]
    per_month = []
    for m in recent:
        s = sum(t["amount"] for t in txs if str(t.get("date", "")).startswith(m) and t["amount"] > 0)
        per_month.append(s)
    avg_spend = round(sum(per_month) / len(per_month)) if per_month else 0

    inc = d["income"]
    income_total = (inc.get("monthly_net") or 0) + (inc.get("extra") or 0)
    surplus = round(income_total - avg_spend)

    # 주식 포트폴리오 평가액 (있으면 포함)
    stock_value = 0
    try:
        from app.data.market import watchlist
        stock_value = watchlist.diagnose(user).get("summary", {}).get("total_value", 0) or 0
    except Exception:
        stock_value = 0

    emergency_target = avg_spend * emergency_months
    monthly_invest = round(max(0, surplus) * invest_ratio)
    monthly_save = round(max(0, surplus) - monthly_invest)

    steps = []
    if income_total <= 0:
        steps.append("먼저 월 급여(실수령액)를 입력하면 저축·투자 계획을 계산합니다.")
    elif surplus <= 0:
        steps.append(f"현재 월 지출(평균 {avg_spend:,}원)이 수입({income_total:,}원)과 비슷하거나 많습니다. "
                     "지출 카테고리 상위부터 줄여 여유자금을 먼저 확보하세요.")
    else:
        steps.append(f"매월 여유자금은 약 {surplus:,}원입니다(수입 {income_total:,} − 평균지출 {avg_spend:,}).")
        steps.append(f"1순위 비상금: 생활비 {emergency_months}개월치({emergency_target:,}원)를 예적금으로 먼저 확보하세요.")
        steps.append(f"이후 매월 여유자금을 저축 {monthly_save:,}원 / 투자(주식 등) {monthly_invest:,}원으로 배분하는 것을 제안합니다.")
        if stock_value:
            steps.append(f"이미 주식 포트폴리오 {round(stock_value):,}원을 투자 자산으로 보유 중입니다(투자 배분의 일부).")

    return {
        "income_total": round(income_total),
        "avg_spend": avg_spend,
        "surplus": surplus,
        "savings_rate": round(surplus / income_total * 100, 1) if income_total else None,
        "emergency_months": emergency_months,
        "emergency_target": round(emergency_target),
        "invest_ratio": invest_ratio,
        "monthly_save": monthly_save,
        "monthly_invest": monthly_invest,
        "stock_value": round(stock_value),
        "allocation": [
            {"name": "안전저축(예적금)", "monthly": monthly_save},
            {"name": "투자(주식 등)", "monthly": monthly_invest},
        ],
        "steps": steps,
        "note": "월평균 지출·수입 기반 참고 계획입니다. 비상금 개월수·투자비중은 조절할 수 있습니다.",
    }


def state(user: str) -> dict:
    d = _load(user)
    return {"income": d["income"], "months": _months(d["transactions"]), "count": len(d["transactions"])}
