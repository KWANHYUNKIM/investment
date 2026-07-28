"""JSON 파일 저장소 — 원자적 쓰기 + 손상 복구를 한 곳에.

이 프로젝트는 DuckDB 에 안 넣는 것들(관심종목·가계부·급여·방문통계·일별 스냅샷…)을
``data/`` 아래 JSON 파일로 둔다. 그 읽고 쓰는 코드가 13개 모듈에 같은 모양으로
복붙되어 있었다.

    tmp = f"{p}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)

이 관용구가 중요한 이유는 **쓰다가 죽어도 이전 파일이 온전히 남는다**는 것이다. 같은
파일에 바로 쓰면 프로세스가 중간에 끊길 때 반쯤 쓰인 JSON 이 남고, 다음 기동에서
사용자 데이터가 통째로 날아간 것처럼 보인다. 열세 곳에 흩어져 있으면 한 곳만
빠뜨려도 그 데이터가 그런 상태가 되므로 여기로 모은다.

읽기도 같은 이유로 모은다 — 파일이 없거나 깨졌을 때 예외를 올리지 않고 기본값으로
되돌아가야 하고, 스키마에 키가 추가됐을 때 예전 파일이 KeyError 를 내지 않아야 한다.
"""
from __future__ import annotations

import copy
import json
import os
import re
from typing import Any

from app.core.config import get_settings

_UNSAFE = re.compile(r"[^A-Za-z0-9_.\-]")


def user_path(prefix: str, user: str | None) -> str:
    """계정별 데이터 파일 경로 — ``data/<prefix>_<user>.json``.

    사용자가 준 이름이 그대로 **파일 이름의 일부가 되므로** 경로에 쓸 수 없는 문자를
    전부 ``_`` 로 바꾼다(``../`` 같은 경로 탈출과 구분자 주입 차단). 네 모듈이
    (watchlist·income·budget·wealthplan) 이 정화기를 각자 복사해 갖고 있었는데, 성격상
    한쪽만 고쳐지면 그 파일만 조용히 위험해지므로 한 곳에 둔다.
    """
    return str(get_settings().data_dir / f"{prefix}_{_UNSAFE.sub('_', user or 'default')}.json")


def read_json(path: str | os.PathLike, default: Any = None) -> Any:
    """JSON 파일을 읽는다. 없거나 깨졌으면 ``default`` 의 **사본**.

    ``default`` 가 dict 이고 읽은 값도 dict 이면 ``default`` 의 키를 빠짐없이 채워
    돌려준다(스키마가 늘어나도 예전 파일이 KeyError 를 내지 않게). 중첩까지 병합하지는
    않는다 — 최상위 키만.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        # 없음 · 권한 없음 · 반쯤 쓰인 JSON — 어느 쪽이든 기본값으로 되돌아간다.
        return copy.deepcopy(default)
    if isinstance(default, dict) and isinstance(data, dict):
        for k, v in default.items():
            data.setdefault(k, copy.deepcopy(v))
    return data


def write_json(path: str | os.PathLike, data: Any, *,
               compact: bool = True, ensure_ascii: bool = False,
               mode: int | None = None) -> None:
    """``path`` 에 원자적으로 쓴다 — 임시 파일에 쓰고 ``os.replace`` 로 갈아끼운다.

    compact       True 면 구분자 공백을 없앤다(파일 크기 — 스냅샷·아카이브용 기본값).
    ensure_ascii  True 면 한글을 ``\\uXXXX`` 로 escape 한다(기본 False: 사람이 읽게).
    mode          주면 쓰기 뒤 ``os.chmod`` (예: 계정 파일 0o600). 실패는 무시한다.
    """
    tmp = f"{os.fspath(path)}.tmp"
    kwargs: dict[str, Any] = {"ensure_ascii": ensure_ascii}
    if compact:
        kwargs["separators"] = (",", ":")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, **kwargs)
    os.replace(tmp, path)
    if mode is not None:
        try:
            os.chmod(path, mode)
        except OSError:
            pass    # 파일시스템이 권한을 지원하지 않는 경우(예: 일부 마운트)
