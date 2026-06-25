"""Code Spitz 스타일 MVVM 프레임워크의 Python 포팅.

바닐라 JS 강의(Scanner / Binder / BinderItem / ViewModel)를 그대로 옮긴 것으로,
View(Element 트리)의 제어를 Binder 에게 위임(IoC)하고, 개발자는 ViewModel 이라는
순수 데이터 객체만 다루도록 만든 미니 프레임워크다.
"""
from __future__ import annotations

from .dom import Element
from .core import ViewModel, BinderItem, Binder, Scanner, require_type

__all__ = [
    "Element",
    "ViewModel",
    "BinderItem",
    "Binder",
    "Scanner",
    "require_type",
]
