"""MVVM 코어: 타입체크 + ViewModel + Scanner/BinderItem/Binder.

강의의 vanilla JS 구현을 1:1 로 옮긴 것. 각 클래스의 책임은 단 하나씩이다(SRP).
    - ViewModel : 순수 데이터(스타일/속성/프로퍼티/이벤트 + 임의 상태/메서드)만 보관
    - Scanner   : View 트리를 훑어 data-viewmodel 매핑을 찾아 Binder 를 만든다
    - BinderItem: (element, viewmodel 이름) 한 쌍의 불변 매핑
    - Binder    : ViewModel 의 값을 실제 Element 에 일괄 적용(렌더)한다

핵심은 IoC: View 에 대한 모든 조작 권한을 Binder 에게 위임하고,
개발자는 ViewModel 만 바꾼 뒤 binder.render(viewmodel) 만 호출한다.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from .dom import Element

# ViewModel 의 예약 버킷 키. 그 외 키는 모두 일반 상태/중첩 ViewModel/메서드로 본다.
_BUCKETS = ("styles", "attributes", "properties", "events")


def require_type(target: Any, expected: type | tuple[type, ...]) -> Any:
    """런타임 타입 검증. 강의의 type() 헬퍼에 해당하며 실패 시 즉시 예외."""
    if not isinstance(target, expected):
        raise TypeError(f"invalid type: expected {expected}, got {type(target).__name__}")
    return target


class ViewModel:
    """View 를 대신하는 순수 데이터 구조체.

    View(Element)의 존재를 전혀 모른다. styles/attributes/properties/events 버킷과,
    그 외 임의의 상태(예: is_stop)·중첩 ViewModel·메서드를 함께 보관한다.
    """

    # 외부에서 ViewModel() 직접 생성을 막기 위한 토큰(강의의 #private Symbol).
    _TOKEN = object()

    def __init__(self, token: object, data: dict[str, Any]) -> None:
        if token is not ViewModel._TOKEN:
            raise TypeError("Use ViewModel.get(...) instead of ViewModel(...)")

        self.styles: dict[str, Any] = {}
        self.attributes: dict[str, Any] = {}
        self.properties: dict[str, Any] = {}
        self.events: dict[str, Callable] = {}
        # 버킷 외의 임의 키(상태/중첩 VM/메서드)를 담는다.
        self._extra: dict[str, Any] = {}

        for key, value in data.items():
            if key in _BUCKETS:
                require_type(value, dict)
                setattr(self, key, dict(value))
            else:
                self._extra[key] = value

    @classmethod
    def get(cls, data: dict[str, Any]) -> "ViewModel":
        """ViewModel 팩토리. 중첩 dict 도 재귀적으로 ViewModel 로 승격한다."""
        require_type(data, dict)
        # 버킷이 아닌 dict 값은 '중첩 ViewModel' 로 간주해 자동 변환한다.
        normalized: dict[str, Any] = {}
        for key, value in data.items():
            if key not in _BUCKETS and isinstance(value, dict):
                normalized[key] = cls.get(value)
            else:
                normalized[key] = value
        return cls(cls._TOKEN, normalized)

    # 일반 상태/중첩 VM/메서드 접근을 속성처럼 노출한다.
    def __getattr__(self, name: str) -> Any:
        # __init__ 에서 _extra 가 만들어지기 전 호출되는 경우를 방어한다.
        extra = self.__dict__.get("_extra", {})
        if name in extra:
            value = extra[name]
            # 메서드라면 self 를 바인딩해 돌려준다.
            if callable(value) and not isinstance(value, ViewModel):
                return lambda *a, **k: value(self, *a, **k)
            return value
        raise AttributeError(name)

    def set(self, name: str, value: Any) -> None:
        """일반 상태 값을 갱신한다(예: vm.set('is_stop', True))."""
        self._extra[name] = value


class BinderItem:
    """(element, viewmodel 이름) 한 쌍의 불변 매핑."""

    __slots__ = ("el", "viewmodel")

    def __init__(self, el: Element, viewmodel: str) -> None:
        self.el = el
        self.viewmodel = viewmodel

    def __setattr__(self, key: str, value: Any) -> None:
        # 한 번 정해지면 동결(강의의 Object.freeze).
        if key in self.__slots__ and key in getattr(self, "__dict__", {}):
            raise AttributeError("BinderItem is frozen")
        object.__setattr__(self, key, value)


class Binder:
    """ViewModel 의 값을 실제 Element 에 일괄 적용하는 동기화 엔진."""

    def __init__(self) -> None:
        self._items: list[BinderItem] = []

    def add(self, item: BinderItem) -> None:
        require_type(item, BinderItem)
        self._items.append(item)

    def render(self, viewmodel: ViewModel) -> None:
        """등록된 모든 매핑을 순회하며 View 를 ViewModel 상태로 동기화한다."""
        require_type(viewmodel, ViewModel)
        for item in self._items:
            vm = getattr(viewmodel, item.viewmodel)  # 중첩 ViewModel 조회
            require_type(vm, ViewModel)
            el = item.el

            for k, v in vm.styles.items():
                el.style[k] = v
            for k, v in vm.attributes.items():
                el.attributes[k] = v
            for k, v in vm.properties.items():
                el.properties[k] = v
            for k, v in vm.events.items():
                # 핸들러에 (element, payload, 루트 viewmodel) 컨텍스트를 넘긴다.
                el.events[k] = self._wrap(el, v, viewmodel)

    @staticmethod
    def _wrap(el: Element, handler: Callable, root: ViewModel) -> Callable:
        def bound(payload: Any = None) -> Any:
            return handler(el, payload, root)
        return bound


class Scanner:
    """View 트리를 훑어 data-viewmodel 매핑을 찾아 Binder 를 만든다."""

    ATTR = "data-viewmodel"

    def scan(self, root: Element) -> Binder:
        require_type(root, Element)
        binder = Binder()
        # 강의의 스택 기반 순회 대신 트리 제너레이터로 동일한 결과를 낸다.
        for el in root.iter():
            name = el.get_attribute(self.ATTR)
            if name:
                binder.add(BinderItem(el, name))
        return binder
