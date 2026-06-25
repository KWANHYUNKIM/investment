"""View 역할을 하는 가벼운 DOM 유사 Element 트리.

강의의 HTMLElement 를 대신한다. 특정 GUI 프레임워크에 묶이지 않도록 순수 파이썬으로
구현했고, 나중에 이 Element 어댑터만 Tkinter/PySide 위젯으로 바꾸면 동일한
Scanner/Binder 가 그대로 동작한다.

DOM 과의 대응:
    el.style[k] = v        -> self.style[k]        (스타일)
    el[k] = v (innerHTML)  -> self.properties[k]   (프로퍼티)
    el.setAttribute(k, v)  -> self.attributes[k]   (속성)
    el.onclick = handler   -> self.events[k]        (이벤트)
"""
from __future__ import annotations

from typing import Any, Callable, Iterator, Optional


class Element:
    """DOM 노드 한 개. 자식 트리를 가지며 style/properties/attributes/events 를 보관한다."""

    def __init__(self, tag: str, attributes: Optional[dict[str, str]] = None) -> None:
        self.tag = tag
        # data-viewmodel 같은 정적 속성. Scanner 가 여기서 매핑 키를 읽는다.
        self.attributes: dict[str, str] = dict(attributes or {})
        self.style: dict[str, Any] = {}
        self.properties: dict[str, Any] = {}      # innerHTML, value 등
        self.events: dict[str, Callable] = {}     # 'click' -> handler
        self.children: list["Element"] = []
        self.parent: Optional["Element"] = None

    # --- 트리 조작 --------------------------------------------------------
    def append(self, *children: "Element") -> "Element":
        for child in children:
            child.parent = self
            self.children.append(child)
        return self

    @property
    def first_element_child(self) -> Optional["Element"]:
        return self.children[0] if self.children else None

    @property
    def next_element_sibling(self) -> Optional["Element"]:
        if self.parent is None:
            return None
        siblings = self.parent.children
        idx = siblings.index(self)
        return siblings[idx + 1] if idx + 1 < len(siblings) else None

    def iter(self) -> Iterator["Element"]:
        """자기 자신부터 깊이우선으로 모든 후손을 순회한다."""
        yield self
        for child in self.children:
            yield from child.iter()

    # --- DOM 유사 API -----------------------------------------------------
    def get_attribute(self, name: str) -> Optional[str]:
        return self.attributes.get(name)

    def dispatch(self, event: str, payload: Any = None) -> None:
        """등록된 이벤트 핸들러를 호출한다(브라우저의 이벤트 발생에 해당)."""
        handler = self.events.get(event)
        if handler is not None:
            handler(payload)

    # --- 디버깅 출력 ------------------------------------------------------
    def render_text(self, depth: int = 0) -> str:
        """현재 트리 상태를 들여쓰기된 문자열로 덤프(콘솔 확인용)."""
        pad = "  " * depth
        vm = self.attributes.get("data-viewmodel")
        head = f"{pad}<{self.tag}"
        if vm:
            head += f' vm="{vm}"'
        if self.style:
            head += f" style={self.style}"
        if self.properties:
            head += f" props={self.properties}"
        if self.events:
            head += f" events={list(self.events)}"
        head += ">"
        lines = [head]
        for child in self.children:
            lines.append(child.render_text(depth + 1))
        return "\n".join(lines)

    def __repr__(self) -> str:  # pragma: no cover - 편의용
        vm = self.attributes.get("data-viewmodel")
        return f"<Element {self.tag}{f' vm={vm!r}' if vm else ''}>"
