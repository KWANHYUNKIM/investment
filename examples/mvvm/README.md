# mvvm — Code Spitz MVVM 패턴의 Python 포팅

[Code Spitz MVVM 강의](https://junilhwang.github.io/TIL/CodeSpitz/Object-Oriented-Javascript/02-MVVM/)의
바닐라 JS 미니 프레임워크(Scanner / Binder / BinderItem / ViewModel)를 파이썬으로 1:1 옮긴 것.

핵심: **View 조작 권한을 Binder 에게 위임(IoC)** 하고, 개발자는 `ViewModel`(순수 데이터)만
바꾼 뒤 `binder.render(viewmodel)` 만 호출한다.

## 실행

프로젝트 루트에서:

```bash
python -m examples.mvvm.demo
```

Windows 콘솔에서 한글이 깨지면 출력 인코딩 문제일 뿐 동작은 정상:

```powershell
$env:PYTHONUTF8 = "1"; python -m examples.mvvm.demo
```

## 구성요소 (각 클래스 책임 1개 — SRP)

| 클래스 | 역할 | JS 원본 대응 |
|--------|------|--------------|
| `ViewModel` | View 를 모르는 순수 데이터(styles/attributes/properties/events + 상태/메서드) | `ViewModel` |
| `Element` (dom.py) | View. DOM 유사 트리(style/properties/events/children) | `HTMLElement` |
| `Scanner` | View 트리를 훑어 `data-viewmodel` 매핑 수집 → `Binder` 생성 | `Scanner` |
| `BinderItem` | `(element, viewmodel 이름)` 불변 매핑 | `BinderItem` |
| `Binder` | ViewModel 값을 Element 에 일괄 적용(동기화) | `Binder` |

## 데이터 흐름

```
ViewModel(데이터만 변경)
        │  binder.render(vm)
        ▼
Binder ── 각 BinderItem 순회 ──▶ Element.style / .properties / .attributes / .events
        ▲
Scanner ── data-viewmodel 스캔으로 BinderItem 생성
```

## 사용 예

```python
from examples.mvvm import Element, Scanner, ViewModel

# 1) View: data-viewmodel 로 바인딩 지점 표시
root = Element("section", {"data-viewmodel": "wrapper"})
root.append(Element("h2", {"data-viewmodel": "title"}))

# 2) ViewModel: 순수 데이터 (중첩 dict 는 자동으로 중첩 ViewModel 로 승격)
vm = ViewModel.get({
    "wrapper": {"styles": {"width": "50%"}},
    "title": {"properties": {"innerHTML": "Hello"}},
})

# 3) 스캔 → 렌더
binder = Scanner().scan(root)
binder.render(vm)

# 4) 데이터만 바꾸고 다시 렌더하면 View 가 동기화됨
vm.title.properties["innerHTML"] = "Changed"
binder.render(vm)
```

## 실제 GUI 로 확장

`dom.Element` 는 View 어댑터일 뿐이다. Tkinter/PySide 로 갈 때는
`Element` 자리에 위젯 트리를 두고, `Binder.render` 에서
`el.style[k]=v` / `el.properties[k]=v` / `el.events[k]=h` 대신
해당 위젯의 `configure(...)` / `setText(...)` / `clicked.connect(...)` 를
호출하도록 어댑터만 바꾸면 `ViewModel`·`Scanner`·`Binder` 는 그대로 재사용된다.
```
