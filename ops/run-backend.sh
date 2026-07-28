#!/bin/bash
# 백엔드(FastAPI + 크롤링 스케줄러) 실행 래퍼. launchd 와 수동 실행 모두 사용.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /Users/kwanhyun/investment/backend
# src 레이아웃 — app 패키지는 src/ 아래. CWD 는 backend 로 유지해야 한다
# (설정의 data_dir="../data" 와 .env 가 CWD 기준 상대경로).
export PYTHONPATH="$PWD/src"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
