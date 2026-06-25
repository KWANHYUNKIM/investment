"""스크리닝 컨트롤러 — View ↔ API ↔ 모델 오케스트레이션.

View 의 조회 요청을 받아 백그라운드로 API 를 호출하고, 결과를 모델에 반영하거나
에러를 상태줄에 표시한다. View 와 Service 어느 쪽도 서로를 직접 모른다.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QSortFilterProxyModel, Qt, QThreadPool

from gui.models.screening_model import SORT_ROLE, ScreeningTableModel
from gui.services import ApiError, ScreeningApiClient
from gui.views import ScreeningView
from gui.workers import Worker


class ScreeningController(QObject):
    def __init__(self, view: ScreeningView, client: ScreeningApiClient) -> None:
        super().__init__()
        self.view = view
        self.client = client
        self.pool = QThreadPool.globalInstance()

        # 모델 + 정렬용 프록시(헤더 클릭 시 숫자 기준 정렬).
        self.model = ScreeningTableModel()
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.view.table.setModel(self.proxy)

        # View 의 요청을 처리.
        self.view.search_requested.connect(self.on_search)

    def on_search(self, params: dict[str, Any]) -> None:
        self.view.set_busy(True)
        self.view.set_status("백엔드 호출 중…")

        worker = Worker(
            self.client.screen,
            market=params["market"],
            top_n=params["top_n"],
        )
        worker.signals.result.connect(self._on_result)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(lambda: self.view.set_busy(False))
        self.pool.start(worker)

    def _on_result(self, records: list[dict[str, Any]]) -> None:
        self.model.set_records(records)
        self.view.table.resizeColumnsToContents()
        if records:
            self.view.set_status(f"{len(records)}개 종목 로드됨. 헤더를 클릭하면 정렬됩니다.")
        else:
            self.view.set_status("조건에 맞는 결과가 없습니다.")

    def _on_error(self, message: str) -> None:
        self.model.set_records([])
        self.view.set_status(f"오류: {message}")
