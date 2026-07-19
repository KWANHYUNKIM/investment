#!/bin/bash
# Cloudflare 임시(Quick) 터널 실행 래퍼 — 도메인/로그인 없이 공개 URL 생성.
# 현재 주소는 로그(ops/logs/quicktunnel.log)의 https://....trycloudflare.com 로 확인.
# 재시작(=cloudflared 재기동)마다 주소가 바뀐다. 고정 URL이 필요하면 setup-tunnel.sh 사용.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
exec cloudflared tunnel --url http://127.0.0.1:3000 --no-autoupdate
