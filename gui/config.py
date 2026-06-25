"""GUI 설정값. 환경변수로 덮어쓸 수 있다."""
from __future__ import annotations

import os

# 백엔드 FastAPI 주소. 예: INVEST_API_URL=http://127.0.0.1:8000
API_BASE_URL = os.environ.get("INVEST_API_URL", "http://127.0.0.1:8000")

# 네트워크 타임아웃(초)
REQUEST_TIMEOUT = float(os.environ.get("INVEST_API_TIMEOUT", "20"))
