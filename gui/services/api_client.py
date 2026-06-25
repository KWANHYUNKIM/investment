"""백엔드 FastAPI 호출 클라이언트.

GUI 의 다른 계층은 HTTP/JSON 세부사항을 몰라도 되도록, 이 모듈이 요청 조립과
에러 변환을 모두 흡수한다. 실패는 모두 ApiError 로 통일해 위로 올린다.
"""
from __future__ import annotations

from typing import Any

import requests

from gui.config import API_BASE_URL, REQUEST_TIMEOUT


class ApiError(Exception):
    """백엔드 호출 실패를 표현하는 단일 예외 타입."""


class ScreeningApiClient:
    """/api/screen 엔드포인트 래퍼."""

    def __init__(self, base_url: str = API_BASE_URL, timeout: float = REQUEST_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def screen(
        self,
        market: str | None = None,
        top_n: int = 30,
        filters: list[dict[str, Any]] | None = None,
        factors: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """스크리닝 결과 레코드 리스트를 돌려준다(실패 시 ApiError)."""
        payload = {
            "market": market,
            "top_n": top_n,
            "filters": filters or [],
            "factors": factors or [],
        }
        url = f"{self.base_url}/api/screen"
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except requests.ConnectionError as exc:
            raise ApiError(
                f"백엔드에 연결할 수 없습니다 ({url}).\n"
                f"FastAPI 서버가 떠 있는지 확인하세요."
            ) from exc
        except requests.Timeout as exc:
            raise ApiError(f"요청 시간이 초과되었습니다 ({self.timeout}s).") from exc

        if resp.status_code == 404:
            # store 에 펀더멘털이 없을 때 백엔드가 주는 안내.
            raise ApiError(
                "스크리닝할 데이터가 없습니다. 먼저 ingest 스크립트로 펀더멘털을 적재하세요.\n"
                f"(서버 응답: {self._detail(resp)})"
            )
        if not resp.ok:
            raise ApiError(f"백엔드 오류 {resp.status_code}: {self._detail(resp)}")

        data = resp.json()
        return data.get("results", [])

    @staticmethod
    def _detail(resp: requests.Response) -> str:
        try:
            return str(resp.json().get("detail", resp.text))
        except ValueError:
            return resp.text[:200]
