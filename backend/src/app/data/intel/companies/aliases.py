"""회사명 별칭 — 표시 이름이 여러 가지인 곳을 대표 키로 흡수한다."""
from __future__ import annotations

ALIASES: dict[str, str] = {
    "alphabet": "Alphabet", "google": "Alphabet", "alphabet inc": "Alphabet",
    "nvidia corp": "NVIDIA", "nvidia corporation": "NVIDIA",
    "advanced micro devices": "AMD",
    "taiwan semiconductor": "TSMC", "tsmc(대만)": "TSMC",
    "micron technology": "Micron",
    "tesla inc": "Tesla", "tesla, inc": "Tesla",
    "apple inc": "Apple", "microsoft corp": "Microsoft", "microsoft corporation": "Microsoft",
    "meta platforms": "Meta",
    "alibaba(hk)": "Alibaba", "alibaba group": "Alibaba",
    "도쿄일렉트론": "Tokyo Electron", "tokyo electron": "Tokyo Electron",
    "에코프로비엠": "에코프로비엠",
}
