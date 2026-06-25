"""GUI 진입점 — 계층을 조립해 앱을 띄운다.

실행:
    python -m gui.main
환경변수:
    INVEST_API_URL   백엔드 주소(기본 http://127.0.0.1:8000)
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from gui.controllers import ScreeningController
from gui.services import ScreeningApiClient
from gui.views import ScreeningView


def main() -> int:
    app = QApplication(sys.argv)

    # 계층 조립: service → model/view ← controller
    client = ScreeningApiClient()
    view = ScreeningView()
    controller = ScreeningController(view, client)  # noqa: F841 - 신호 연결 유지용

    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
