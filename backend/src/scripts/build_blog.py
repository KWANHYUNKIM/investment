"""증시 보고서 블로그 글 생성 — 서버 없이도 돌아가는 발행 스크립트.

앱 안 스케줄러(평일 16:20)와 같은 일을 하지만, 이건 **서버가 꺼져 있어도** 돌릴 수 있다.
그래서 OS 스케줄러(작업 스케줄러)에 걸어두면 PC 만 켜져 있으면 글이 쌓인다.

산출물: ``data/blog_posts/<날짜>_market-wrap.json`` (제목·마크다운·HTML·태그)
        ``data/blog_posts/<날짜>_market-wrap.md``   (그대로 복사해 올릴 원고)

사용:
    python -m scripts.build_blog                  # 오늘자 발행(이미 있으면 갱신)
    python -m scripts.build_blog --date 2026-07-22
    python -m scripts.build_blog --print          # 본문을 화면에 출력
    python -m scripts.build_blog --list           # 저장된 글 목록
"""
from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser(description="증시 보고서 블로그 글 생성")
    ap.add_argument("--date", default="", help="대상 날짜(YYYY-MM-DD). 기본 오늘")
    ap.add_argument("--print", dest="show", action="store_true", help="본문 출력")
    ap.add_argument("--list", dest="listing", action="store_true", help="저장된 글 목록")
    ap.add_argument("--no-force", action="store_true", help="이미 있으면 재사용(재생성 안 함)")
    args = ap.parse_args()

    from app.data.admin import blog, blog_archive

    if args.listing:
        rows = blog_archive.listing()
        print(f"저장 위치: {blog_archive.dir_path()}  ({len(rows)}편)")
        for r in rows:
            print("  %-12s %-12s %-52s %5d자 · %d섹션" % (
                r["date"], r["kind"], (r["title"] or "")[:52], r["chars"], r["sections"]))
        return 0

    t0 = time.time()
    post = blog.publish_market_wrap(args.date or None, force=not args.no_force)
    md = post.get("markdown") or ""
    print(f"발행 {'재사용' if post.get('reused') else '완료'}: {post.get('title')}")
    print(f"  날짜 {post.get('date')} · {len(md):,}자 · 섹션 {md.count(chr(10) + '## ')}개 "
          f"· {time.time() - t0:.1f}s")
    print(f"  {post.get('markdown_path') or post.get('path')}")
    if not md.strip():
        print("본문이 비었습니다 — 시세·뉴스 데이터가 아직 없을 수 있습니다.", file=sys.stderr)
        return 1
    if args.show:
        print("\n" + "=" * 70)
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
