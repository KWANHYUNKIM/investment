"""core.jsonstore 동작 고정 테스트.

13개 모듈의 사용자 데이터(관심종목·가계부·급여·계정·일별 스냅샷…)가 이 두 함수를 지난다.
그래서 여기서 지키려는 건 **데이터가 날아가지 않는다**는 성질이다.

  · 쓰다 죽어도 이전 파일이 온전히 남는다(원자적 교체)
  · 파일이 없거나 반쯤 쓰였어도 예외 대신 기본값으로 되돌아간다
  · 스키마에 키가 추가돼도 예전 파일이 KeyError 를 내지 않는다
  · 기본값을 돌려줄 때 **사본**이라 호출부가 고쳐도 다음 호출이 오염되지 않는다
"""
from __future__ import annotations

import json

import pytest

from app.core.jsonstore import read_json, write_json


def test_roundtrip(tmp_path) -> None:
    p = tmp_path / "a.json"
    write_json(p, {"k": "값", "n": 1})
    assert read_json(p) == {"k": "값", "n": 1}


def test_missing_file_returns_default(tmp_path) -> None:
    assert read_json(tmp_path / "none.json", {"a": 1}) == {"a": 1}
    assert read_json(tmp_path / "none.json", []) == []
    assert read_json(tmp_path / "none.json") is None


def test_corrupt_file_returns_default(tmp_path) -> None:
    """반쯤 쓰인 JSON — 예외 대신 기본값. (예전 코드가 except Exception 으로 했던 것)"""
    p = tmp_path / "half.json"
    p.write_text('{"a": 1, "b":', encoding="utf-8")
    assert read_json(p, {"a": 0}) == {"a": 0}


def test_default_keys_are_filled(tmp_path) -> None:
    """스키마가 늘었을 때 예전 파일이 KeyError 를 내지 않아야 한다."""
    p = tmp_path / "old.json"
    write_json(p, {"watch": ["005930"]})
    got = read_json(p, {"watch": [], "holdings": []})
    assert got == {"watch": ["005930"], "holdings": []}


def test_existing_values_win_over_defaults(tmp_path) -> None:
    p = tmp_path / "a.json"
    write_json(p, {"n": 7})
    assert read_json(p, {"n": 0})["n"] == 7


def test_default_is_copied_not_shared(tmp_path) -> None:
    """기본값을 그대로 돌려주면 호출부의 변경이 다음 호출에 새어 나간다."""
    default = {"rows": []}
    a = read_json(tmp_path / "none.json", default)
    a["rows"].append("x")
    b = read_json(tmp_path / "none.json", default)
    assert b == {"rows": []}
    assert default == {"rows": []}


def test_non_dict_default_is_not_merged(tmp_path) -> None:
    p = tmp_path / "list.json"
    write_json(p, [1, 2, 3])
    assert read_json(p, []) == [1, 2, 3]


def test_write_leaves_no_tmp_file(tmp_path) -> None:
    p = tmp_path / "a.json"
    write_json(p, {"a": 1})
    assert [f.name for f in tmp_path.iterdir()] == ["a.json"]


def test_write_replaces_previous_content(tmp_path) -> None:
    p = tmp_path / "a.json"
    write_json(p, {"a": 1, "long": "x" * 100})
    write_json(p, {"a": 2})
    assert read_json(p) == {"a": 2}          # 이전 내용 잔재가 섞이지 않는다


def test_compact_and_ensure_ascii_options(tmp_path) -> None:
    p = tmp_path / "a.json"
    write_json(p, {"k": "값"})
    assert p.read_text(encoding="utf-8") == '{"k":"값"}'          # compact 기본
    write_json(p, {"k": "값"}, compact=False)
    assert p.read_text(encoding="utf-8") == '{"k": "값"}'
    write_json(p, {"k": "값"}, compact=False, ensure_ascii=True)
    assert json.loads(p.read_text(encoding="utf-8")) == {"k": "값"}
    assert "\\u" in p.read_text(encoding="utf-8")


@pytest.mark.parametrize("payload", [{}, [], 0, "", None, {"nested": {"a": [1, {"b": 2}]}}])
def test_various_payloads_survive(tmp_path, payload) -> None:
    p = tmp_path / "a.json"
    write_json(p, payload)
    assert read_json(p, "SENTINEL") == payload
