"""실행 데모: 강의의 흐름(스캔 -> 렌더 -> 상태변경 -> 재렌더 -> 이벤트)을 그대로 재현.

실행:
    python -m mvvm.demo
"""
from __future__ import annotations

import random

from .core import Scanner, ViewModel
from .dom import Element


def build_view() -> Element:
    """data-viewmodel 매핑을 가진 View 트리 구성(강의의 HTML 에 해당).

        <section vm="wrapper">
          <h2 vm="title"></h2>
          <section vm="contents"></section>
        </section>
    """
    root = Element("section", {"id": "target", "data-viewmodel": "wrapper"})
    title = Element("h2", {"data-viewmodel": "title"})
    contents = Element("section", {"data-viewmodel": "contents"})
    root.append(title, contents)
    return root


def build_viewmodel() -> ViewModel:
    """View 를 전혀 모르는 순수 데이터 객체."""

    def on_click(el, event, root):
        # 클릭하면 루프를 멈추는 상태 플래그를 켠다.
        root.set("is_stop", True)
        print("  [event] wrapper clicked -> is_stop = True")

    def change_contents(self):
        # ViewModel 의 데이터만 바꾼다. View 는 건드리지 않는다.
        r, g, b = (random.randint(0, 255) for _ in range(3))
        self.wrapper.styles["background"] = f"rgb({r},{g},{b})"
        self.contents.properties["innerHTML"] = format(random.random(), ".8f")

    return ViewModel.get({
        "is_stop": False,
        "change_contents": change_contents,
        "wrapper": {
            "styles": {"width": "50%", "background": "#ffa"},
            "events": {"click": on_click},
        },
        "title": {
            "properties": {"innerHTML": "MVVM in Python"},
        },
        "contents": {
            "properties": {"innerHTML": "(empty)"},
        },
    })


def main() -> None:
    view = build_view()
    viewmodel = build_viewmodel()

    # 1) Scanner 가 data-viewmodel 을 훑어 Binder 를 만든다.
    binder = Scanner().scan(view)

    # 2) 첫 렌더: ViewModel -> View 동기화.
    binder.render(viewmodel)
    print("=== 초기 렌더 ===")
    print(view.render_text())

    # 3) 상태를 바꿔가며 재렌더 (requestAnimationFrame 루프 대용).
    print("\n=== 상태 변경 후 재렌더 (3 프레임) ===")
    for frame in range(3):
        viewmodel.change_contents()   # ViewModel 데이터만 변경
        binder.render(viewmodel)       # 변경분을 View 에 반영
        print(f"\n[frame {frame}]")
        print(view.render_text())

    # 4) 이벤트 발생: View 의 클릭이 ViewModel 상태를 바꾼다.
    print("\n=== 이벤트 디스패치 ===")
    view.dispatch("click")
    print(f"is_stop = {viewmodel.is_stop}")


if __name__ == "__main__":
    main()
