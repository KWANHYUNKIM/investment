"""In-process scheduler that persists the daily report once per trading day.

Mirrors ``price_scheduler``: a daemon thread inside the API process. Each tick it
asks the store for the latest price date and, if that day's report file isn't on
disk yet, builds and saves it. So the archive fills in on its own — one JSON per
trading day — without a manual run.

Cheap by design: the only per-tick cost is a ``MAX(date)`` query plus a file
existence check; the expensive full build runs at most once per day (the first
tick after a new trading day's bars land). Disable with ``REPORT_ARCHIVE=false``;
tune the wake cadence with ``REPORT_ARCHIVE_INTERVAL`` (seconds).
"""
from __future__ import annotations

from app.data.reports import daily_archive
from app.data.infra import store
from app.data.schedulers import runner

_state = {
    "running": False,
    "ticks": 0,
    "snapshots": 0,
    "last_run": None,
    "last_saved_date": None,
    "last_status": None,
    "last_error": None,
}


def _tick() -> None:
    date = store.max_price_date()
    if not date:
        _state["last_status"] = "no-data"
        return
    if daily_archive.exists(date):
        _state["last_status"] = "exists"
        return
    res = daily_archive.snapshot()
    _state["last_status"] = res.get("status")
    if res.get("status") == "saved":
        _state["snapshots"] += 1
        _state["last_saved_date"] = res.get("date")


_sched = runner.Scheduler(
    thread_name="report-scheduler",
    state=_state,
    tick=_tick,
    enabled=lambda s: s.report_archive,
    interval=lambda s: s.report_archive_interval,
    settle=30.0,  # let startup (DB init, first board snapshot) settle
    extra_status=lambda s: {
        "interval_sec": s.report_archive_interval,
        "deep_n": s.report_deep_n,
        "archived_dates": daily_archive.list_dates(),
    },
)

status = _sched.status
start = _sched.start
