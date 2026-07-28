"""백그라운드 스케줄러 공용 러너.

이 폴더의 스케줄러 10종은 하는 일은 전부 다르지만 **껍데기는 같았다**: 데몬 스레드
하나를 띄우고, 기동 직후 잠깐 쉬고, 무한 루프에서 틱을 돌리고, 예외를 삼켜 루프를
살려두고, ticks/last_run/last_error 를 기록하고, 설정에서 주기를 읽어 잔다. 그 35줄이
모듈마다 복붙되어 있었다(합계 ~350줄). 여기로 모은다.

각 스케줄러 모듈에 남는 것은 **고유한 것뿐**이다.

    _state = {"running": False, "ticks": 0, "records": 0, "last_run": None, "last_error": None}

    def _tick() -> None:
        ...                                  # 이 스케줄러가 실제로 하는 일

    _sched = runner.Scheduler(
        thread_name="movers-scheduler",
        state=_state,                        # 러너가 이 dict 를 그대로 갱신한다
        tick=_tick,
        enabled=lambda s: s.movers,          # 설정 스위치
        interval=lambda s: s.movers_interval,
        settle=60.0,                         # 기동 후 대기(startup 이 자리잡을 시간)
        extra_status=lambda s: {"interval_sec": s.movers_interval},
    )
    status = _sched.status
    start = _sched.start

``state`` 를 모듈이 선언한 dict 그대로 받는 이유: 기존 ``_tick`` 본문이 ``_state[...]``
를 직접 건드리므로 같은 객체를 공유해야 틱 코드를 한 글자도 안 바꿔도 된다. 상태 키의
순서·이름이 그대로라 ops 모니터에 나가는 JSON 도 이전과 동일하다.

``status``/``start`` 를 모듈 수준 이름으로 다시 내보내는 것도 계약이다 — ``api/ops.py``
는 스케줄러 **모듈**을 리스트로 들고 ``mod.status()`` 를, ``main.py`` 는 ``mod.start()``
를 호출한다.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from app.core.config import Settings, get_settings

# 상태 dict 에 반드시 있어야 하는 키 — 러너가 갱신을 책임진다.
_REQUIRED = ("running", "ticks", "last_run", "last_error")


class Scheduler:
    """데몬 스레드 하나 + 틱 루프. 스케줄러마다 인스턴스 하나."""

    def __init__(
        self,
        *,
        thread_name: str,
        state: dict,
        tick: Callable[[], None],
        enabled: Callable[[Settings], bool],
        interval: Callable[[Settings], float],
        settle: float = 0.0,
        extra_status: Callable[[Settings], dict] | None = None,
        before_loop: Callable[[], None] | None = None,
    ) -> None:
        missing = [k for k in _REQUIRED if k not in state]
        if missing:
            raise ValueError(f"{thread_name}: 상태 키 누락 {missing}")
        self._thread_name = thread_name
        self.state = state
        self._tick = tick
        self._enabled = enabled
        self._interval = interval
        self._settle = float(settle)
        self._extra_status = extra_status
        self._before_loop = before_loop

    # ── 공개면 (ops.py / main.py 가 모듈을 통해 호출) ────────────────────────
    def status(self) -> dict:
        """상태 dict + 설정에서 파생된 값들. ops 모니터가 이 모양을 그대로 렌더한다."""
        s = get_settings()
        extra = self._extra_status(s) if self._extra_status else {}
        return {**self.state, **extra}

    def start(self) -> None:
        """설정에서 켜져 있으면 스레드를 한 번만 띄운다."""
        if self.state["running"]:
            return
        if not self._enabled(get_settings()):
            return
        self.state["running"] = True
        threading.Thread(target=self._loop, daemon=True, name=self._thread_name).start()

    # ── 내부 ────────────────────────────────────────────────────────────────
    def _loop(self) -> None:
        if self._settle:
            time.sleep(self._settle)
        if self._before_loop is not None:
            # 재시작 시 중복 실행 방지용 시딩 등. 실패 처리는 훅 자신의 책임(기존 코드와 동일).
            self._before_loop()
        while True:
            # 틱 시작 시점에 비운다 — 틱이 스스로 사유를 써 넣는 경우(예: 실거래 API 키
            # 미설정)를 뒤에서 덮어쓰지 않기 위해서다. 성공하면 자연히 None 으로 남는다.
            self.state["last_error"] = None
            try:
                self._tick()
                self.state["ticks"] += 1
                self.state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:  # noqa: BLE001 - 상류가 흔들려도 루프는 살려둔다
                self.state["last_error"] = f"{type(e).__name__}: {str(e)[:120]}"
            time.sleep(self._interval(get_settings()))
