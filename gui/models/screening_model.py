"""스크리닝 결과를 담는 Qt 테이블 모델.

이 프로젝트의 스크리닝 응답은 컬럼이 동적(펀더멘털 종류 + name/sector/score 등)이라,
모델은 특정 컬럼에 의존하지 않고 레코드(dict 리스트)에서 컬럼을 추론한다.

Qt Model/View 의 핵심: View(QTableView)는 데이터를 직접 모르고, 오직 이 모델에
rowCount/columnCount/data/headerData 를 물어본다. 데이터가 바뀌면 모델이 신호를
보내 View 가 자동 갱신된다 — 이것이 Qt 식 데이터 바인딩이다.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

# 자주 나오는 컬럼은 보기 좋은 한글 헤더로 매핑(없으면 원본 키 사용).
COLUMN_LABELS: dict[str, str] = {
    "market": "시장",
    "ticker": "종목코드",
    "name": "종목명",
    "sector": "섹터",
    "score": "점수",
    "per": "PER",
    "pbr": "PBR",
    "pcr": "PCR",
    "psr": "PSR",
    "roe": "ROE",
    "eps": "EPS",
    "bps": "BPS",
    "div_yield": "배당수익률",
    "market_cap": "시가총액",
}

# 이 순서대로 앞쪽에 배치(나머지는 알파벳 순으로 뒤에).
PREFERRED_ORDER = ["market", "ticker", "name", "sector", "score"]

# 숫자 컬럼 표시 소수 자리수
DECIMALS = 2

# 정렬 시 원본 숫자값을 쓰기 위한 커스텀 역할
SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class ScreeningTableModel(QAbstractTableModel):
    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._records: list[dict[str, Any]] = []
        self._columns: list[str] = []
        if records:
            self.set_records(records)

    # --- 데이터 교체 ------------------------------------------------------
    def set_records(self, records: list[dict[str, Any]]) -> None:
        """새 결과로 모델을 통째로 교체하고 View 에 리셋을 알린다."""
        self.beginResetModel()
        self._records = list(records)
        self._columns = self._infer_columns(self._records)
        self.endResetModel()

    @staticmethod
    def _infer_columns(records: list[dict[str, Any]]) -> list[str]:
        keys: list[str] = []
        seen: set[str] = set()
        for row in records:
            for k in row:
                if k not in seen:
                    seen.add(k)
                    keys.append(k)
        preferred = [c for c in PREFERRED_ORDER if c in seen]
        rest = sorted(k for k in keys if k not in PREFERRED_ORDER)
        return preferred + rest

    # --- QAbstractTableModel 필수 구현 ------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        value = self._records[index.row()].get(self._columns[index.column()])

        if role == Qt.ItemDataRole.DisplayRole:
            return self._format(value)
        if role == SORT_ROLE:
            # 정렬용: 숫자는 숫자로, 나머지는 문자열로.
            return value if isinstance(value, (int, float)) else self._format(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and isinstance(value, (int, float)):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            key = self._columns[section]
            return COLUMN_LABELS.get(key, key)
        return section + 1  # 행 번호

    # --- 표시 포맷 --------------------------------------------------------
    @staticmethod
    def _format(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:,.{DECIMALS}f}"
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)
