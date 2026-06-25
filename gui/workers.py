"""백그라운드 작업 헬퍼 — API 호출로 UI 가 멈추지 않게 한다.

Qt 의 메인 스레드에서 네트워크를 직접 호출하면 화면이 얼어붙는다. QThreadPool 에
QRunnable 을 던지고, 결과/에러는 시그널로 메인 스레드에 안전하게 돌려준다.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    result = Signal(object)   # 성공 시 반환값
    error = Signal(str)       # 실패 시 에러 메시지
    finished = Signal()       # 성공/실패 무관하게 마지막에


class Worker(QRunnable):
    """임의의 함수를 스레드풀에서 실행하는 일회용 작업."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            value = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001 - 모든 실패를 UI 로 전달
            self.signals.error.emit(str(exc))
        else:
            self.signals.result.emit(value)
        finally:
            self.signals.finished.emit()
