#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# 백엔드 · 프론트엔드 · 터널을 launchd 서비스로 등록 → 로그인/재부팅 시 자동 시작,
# 죽으면 자동 재시작(KeepAlive). 회사에서 언제든 접속 가능하게 '항상 켜둠'.
#
# 선행: ops/setup-tunnel.sh <주소> 를 먼저 끝내야 터널 서비스가 정상 동작.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
OPS="/Users/kwanhyun/investment/ops"
LA="$HOME/Library/LaunchAgents"

mkdir -p "$OPS/logs" "$LA"
chmod +x "$OPS"/run-*.sh

# 수동으로 띄워둔 백엔드/프론트엔드가 있으면 포트를 비워 충돌 방지
lsof -ti:8000 | xargs kill 2>/dev/null || true
lsof -ti:3000 | xargs kill 2>/dev/null || true

for svc in backend frontend tunnel; do
  plist="com.investment.$svc.plist"
  cp "$OPS/$plist" "$LA/$plist"
  # 이미 로드돼 있으면 내렸다 다시 올림
  launchctl bootout "gui/$(id -u)/com.investment.$svc" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$LA/$plist"
  launchctl enable "gui/$(id -u)/com.investment.$svc"
  echo "✅ 등록: com.investment.$svc"
done

echo ""
echo "상태 확인:  launchctl list | grep com.investment"
echo "로그:       tail -f $OPS/logs/{backend,frontend,tunnel}.log"
echo ""
echo "⚠️  Mac 이 잠자면 서버도 멈춥니다. 항상 응답하게 하려면 (전원 연결 시):"
echo "     sudo pmset -c sleep 0 disksleep 0"
echo "   노트북 덮개 닫아도 켜두려면 clamshell 사용(외부전원+옵션) 또는 위 pmset."
