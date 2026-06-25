"""스크리닝 화면 위젯 — UI 구성과 입력 신호만 담당.

View 는 '무엇을 보여줄지'만 알고 '어떻게 가져올지'는 모른다. 사용자가 조회를
누르면 search_requested 시그널만 쏘고, 데이터를 채우는 일은 Controller 의 몫이다.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

# 콤보 표시값 -> API market 파라미터
MARKETS = [("전체", None), ("한국 (KR)", "KR"), ("미국 (US)", "US")]


class ScreeningView(QWidget):
    # 조회 요청: {"market": str|None, "top_n": int}
    search_requested = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("종목 스크리닝 — Qt Model/View")
        self.resize(900, 600)

        # --- 상단 컨트롤 바 ----------------------------------------------
        self.market_combo = QComboBox()
        for label, _ in MARKETS:
            self.market_combo.addItem(label)

        self.topn_spin = QSpinBox()
        self.topn_spin.setRange(1, 500)
        self.topn_spin.setValue(30)

        self.search_btn = QPushButton("조회")
        self.search_btn.clicked.connect(self._emit_search)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("시장"))
        controls.addWidget(self.market_combo)
        controls.addSpacing(12)
        controls.addWidget(QLabel("상위"))
        controls.addWidget(self.topn_spin)
        controls.addSpacing(12)
        controls.addWidget(self.search_btn)
        controls.addStretch(1)

        # --- 테이블 ------------------------------------------------------
        self.table = QTableView()
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)

        # --- 상태 표시줄 -------------------------------------------------
        self.status = QLabel("준비됨 — '조회'를 눌러 백엔드에서 데이터를 불러오세요.")

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.table)
        layout.addWidget(self.status)

    # --- 외부(Controller)에서 쓰는 헬퍼 ---------------------------------
    def set_busy(self, busy: bool) -> None:
        self.search_btn.setEnabled(not busy)
        self.search_btn.setText("불러오는 중…" if busy else "조회")

    def set_status(self, text: str) -> None:
        self.status.setText(text)

    # --- 내부 ------------------------------------------------------------
    def _emit_search(self) -> None:
        market = MARKETS[self.market_combo.currentIndex()][1]
        self.search_requested.emit({"market": market, "top_n": self.topn_spin.value()})
