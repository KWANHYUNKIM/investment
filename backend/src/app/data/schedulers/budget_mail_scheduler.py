"""카드사 이용대금명세서 메일 자동 수집 — 30분마다 받은편지함 확인.

명세서는 **월 1회**밖에 안 오므로 자주 볼 이유가 없다. 30분 주기는 '언제 왔는지
신경 쓰지 않아도 그날 안에 들어와 있다' 정도를 노린 값이다. IMAP 은 readonly 로
열기 때문에 이 스케줄러가 도는 것만으로 메일이 읽음 처리되지는 않는다.

자격증명이 없으면 아예 돌지 않는다(``configured()``). 켜 두고 .env 만 비워 두면
30분마다 조용히 건너뛰므로, 스케줄러 상태에 그 사유를 남긴다.

BUDGET_MAIL=false 로 끈다.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.data.schedulers import runner

_state = {
    "running": False,
    "ticks": 0,
    "scans": 0,
    "imported": 0,       # 자동 등록된 명세서 수(건수 아님)
    "pending": 0,        # 확인 대기 중인 명세서 수
    "last_run": None,
    "last_result": None,
    "skipped_reason": None,
    "last_error": None,
}


def _tick() -> None:
    from app.data.market.budget import mailbox

    if not mailbox.configured():
        _state["skipped_reason"] = "IMAP 미설정 (backend/.env)"
        return
    _state["skipped_reason"] = None

    res = mailbox.scan()
    _state["scans"] += 1
    _state["imported"] += res.get("imported", 0)
    _state["pending"] = len(mailbox.load(get_settings().budget_mail_user)["pending"])
    _state["last_result"] = {k: res.get(k) for k in
                             ("examined", "imported", "added", "pending", "locked", "note")}


def _extra_status(s) -> dict:
    return {
        "enabled": s.budget_mail,
        "interval_min": round(s.budget_mail_check_interval / 60),
        "account": s.imap_user,
        "target_user": s.budget_mail_user,
        "autoimport": s.budget_mail_autoimport,
    }


_sched = runner.Scheduler(
    thread_name="budget-mail-scheduler",
    state=_state,
    tick=_tick,
    enabled=lambda s: s.budget_mail,
    interval=lambda s: s.budget_mail_check_interval,
    settle=90.0,        # startup 이 자리잡은 뒤 (IMAP 접속이 느릴 수 있다)
    extra_status=_extra_status,
)

status = _sched.status
start = _sched.start
