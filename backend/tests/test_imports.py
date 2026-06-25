"""Import smoke test — 리팩터링으로 import 경로가 깨지지 않았는지 자동 검증.

app.main(앱 전체 와이어링)과 app.data 하위 모든 모듈을 실제로 import 해본다.
모듈 하나라도 import 에 실패하면 테스트가 깨지므로, 패키지 재배치 후 회귀를 잡는다.
"""
from __future__ import annotations

import importlib
import pkgutil

import pytest

import app.data


def _all_data_modules() -> list[str]:
    names: list[str] = []
    for info in pkgutil.walk_packages(app.data.__path__, prefix="app.data."):
        names.append(info.name)
    return names


def test_app_main_imports() -> None:
    """앱 진입점이 import 되면 라우터/스케줄러 와이어링이 정상이라는 뜻."""
    importlib.import_module("app.main")


@pytest.mark.parametrize("module_name", _all_data_modules())
def test_data_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)
