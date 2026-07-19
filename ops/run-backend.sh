#!/bin/bash
# 백엔드(FastAPI + 크롤링 스케줄러) 실행 래퍼. launchd 와 수동 실행 모두 사용.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /Users/kwanhyun/investment/backend
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
