#!/bin/bash
# Cloudflare 고정 터널 실행 래퍼. setup-tunnel.sh 로 만든 'investment' 터널을 띄운다.
# 프론트엔드(:3000) 하나만 공개하면 프록시(next.config.ts)를 통해 백엔드까지 접속된다.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
exec cloudflared tunnel run investment
