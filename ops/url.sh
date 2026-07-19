#!/bin/bash
# 현재 임시 터널의 공개 URL 출력. (재부팅/터널 재기동 시 주소가 바뀌므로 이걸로 확인)
url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /Users/kwanhyun/investment/ops/logs/quicktunnel.log | tail -1)
if [[ -n "$url" ]]; then
  echo "$url"
else
  echo "아직 URL 없음 — 터널 준비 중이거나 서비스 미실행. 확인: launchctl list | grep com.investment"
fi
