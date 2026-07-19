#!/bin/bash
# launchd 서비스 3개 내리고 제거 (자동시작 해제).
set -euo pipefail
LA="$HOME/Library/LaunchAgents"
for svc in backend frontend tunnel; do
  launchctl bootout "gui/$(id -u)/com.investment.$svc" 2>/dev/null || true
  rm -f "$LA/com.investment.$svc.plist"
  echo "🗑  제거: com.investment.$svc"
done
echo "완료. (수동 실행은 ops/run-*.sh 로 여전히 가능)"
