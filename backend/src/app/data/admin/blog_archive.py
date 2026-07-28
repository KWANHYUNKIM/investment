"""생성한 블로그 글을 날짜별로 보관한다.

``blog.generate()`` 는 지금까지 글을 만들어 **돌려주기만** 했다. 그래서 관리자가 그 자리에서
복사하지 않으면 사라졌고, 자동 생성도 의미가 없었다(어디에도 안 남으니까).

여기서는 하루 한 편을 파일로 남긴다.

    data/blog_posts/2026-07-23_market-wrap.json   ← 제목·마크다운·HTML·태그·메타
    data/blog_posts/2026-07-23_market-wrap.md     ← 그대로 복사해 붙일 원고

JSON 하나로 충분하지만 ``.md`` 를 같이 두는 건, 블로그에 올릴 때 파일만 열어 복사하면
되게 하기 위해서다(에디터·모바일에서도 바로 열린다).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from app.core.config import get_settings

_SAFE = re.compile(r"[^0-9a-zA-Z가-힣._-]+")


def dir_path() -> Path:
    d = Path(get_settings().data_dir) / "blog_posts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stem(date: str, kind: str) -> str:
    return f"{date}_{_SAFE.sub('-', kind).strip('-') or 'post'}"


def save(post: dict, kind: str = "market-wrap", date: str | None = None) -> dict:
    """글 1편 저장. 같은 날·같은 종류면 덮어쓴다(재생성 = 갱신)."""
    date = date or post.get("date") or time.strftime("%Y-%m-%d")
    stem = _stem(date, kind)
    d = dir_path()
    rec = {**post, "kind": kind, "date": date,
           "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (d / f"{stem}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / f"{stem}.md").write_text(
        f"# {post.get('title', '')}\n\n{post.get('markdown', '')}", encoding="utf-8")
    rec["path"] = str(d / f"{stem}.json")
    rec["markdown_path"] = str(d / f"{stem}.md")
    return rec


def load(date: str, kind: str = "market-wrap") -> dict | None:
    p = dir_path() / f"{_stem(date, kind)}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def exists(date: str, kind: str = "market-wrap") -> bool:
    return (dir_path() / f"{_stem(date, kind)}.json").exists()


def listing(limit: int = 60) -> list[dict]:
    """최신순 목록(본문 제외 — 목록 화면이 무거워지지 않게)."""
    out: list[dict] = []
    for p in sorted(dir_path().glob("*.json"), reverse=True)[:limit]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        md = d.get("markdown") or ""
        out.append({
            "date": d.get("date"), "kind": d.get("kind"), "title": d.get("title"),
            "tags": d.get("tags") or [], "saved_at": d.get("saved_at"),
            "chars": len(md), "sections": md.count("\n## "),
            "file": p.name,
        })
    return out


def latest(kind: str = "market-wrap") -> dict | None:
    for p in sorted(dir_path().glob(f"*_{kind}.json"), reverse=True):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None
