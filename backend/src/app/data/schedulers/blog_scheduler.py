"""증시 보고서 블로그 글 자동 발행 — 평일 장 마감 후 하루 1편.

원가모델 배치(``costmodel_scheduler``)와 같은 "하루 한 번 정해진 시각" 방식이다.
차이는 **평일에만** 돈다는 것 — 주말·공휴일엔 새 시세가 없어 같은 글이 또 나온다.
(공휴일은 달력을 따로 두지 않고, 리포트의 시세 기준일이 오늘이 아니면 건너뛴다.)

기본 16:20. 한국 장 마감(15:30) + 마감 시세·투자자 수급이 반영될 여유를 둔 시각이다.
서버가 그 시각에 꺼져 있었다면 켜진 뒤 첫 점검에서 그날 몫을 따라잡는다.
BLOG_AUTOPUBLISH=false 로 끈다.
"""
from __future__ import annotations

import time

from app.core.config import get_settings
from app.data.schedulers import runner

_state = {
    "running": False,
    "ticks": 0,
    "posts": 0,
    "last_run": None,
    "last_post_date": None,
    "last_title": None,
    "skipped_reason": None,
    "last_error": None,
}


def _due(now: time.struct_time) -> tuple[bool, str | None]:
    s = get_settings()
    today = time.strftime("%Y-%m-%d", now)
    if now.tm_wday >= 5:
        return False, "주말"
    if _state["last_post_date"] == today:
        return False, "오늘 발행 완료"
    if (now.tm_hour, now.tm_min) < (s.blog_publish_hour, s.blog_publish_minute):
        return False, "발행 시각 이전"
    return True, None


def _tick() -> None:
    now = time.localtime()
    ok, why = _due(now)
    _state["skipped_reason"] = why
    if not ok:
        return
    from app.data.admin import blog
    today = time.strftime("%Y-%m-%d", now)
    post = blog.publish_market_wrap(force=True)
    _state["posts"] += 1
    _state["last_post_date"] = today
    _state["last_title"] = post.get("title")


def _seed_last_post() -> None:
    from app.data.admin import blog_archive
    latest = blog_archive.latest("market-wrap")
    if latest and latest.get("date"):
        _state["last_post_date"] = latest["date"]      # 재시작 시 중복 발행 방지


def _extra_status(s) -> dict:
    from app.data.admin import blog_archive   # 지연 import — 순환 참조 회피
    latest = blog_archive.latest("market-wrap") or {}
    return {
        "schedule": "%02d:%02d 평일" % (s.blog_publish_hour, s.blog_publish_minute),
        "enabled": s.blog_autopublish,
        "latest_post": {"date": latest.get("date"), "title": latest.get("title"),
                        "saved_at": latest.get("saved_at")} if latest else None,
    }


_sched = runner.Scheduler(
    thread_name="blog-scheduler",
    state=_state,
    tick=_tick,
    enabled=lambda s: s.blog_autopublish,
    interval=lambda s: s.blog_publish_check_interval,
    settle=120.0,  # startup 이 자리잡은 뒤 시작
    before_loop=_seed_last_post,
    extra_status=_extra_status,
)

status = _sched.status
start = _sched.start
