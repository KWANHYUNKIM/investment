#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Cloudflare 고정 터널 셋업 (1회 실행).
#
# 선행 조건 (사용자가 직접):
#   1) Cloudflare 계정에 '내 도메인'이 등록돼 있어야 함 (무료 플랜 OK).
#   2) cloudflared tunnel login  ← 브라우저가 열리고 도메인 인증 (cert.pem 생성)
#
# 사용법:
#   ops/setup-tunnel.sh investment.example.com
#     └ 인자 = 회사에서 칠 '고정 주소'. 본인 도메인의 서브도메인이면 됨.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

HOSTNAME="${1:-}"
TUNNEL="investment"
CFG_DIR="$HOME/.cloudflared"

if [[ -z "$HOSTNAME" ]]; then
  echo "❌ 사용법: ops/setup-tunnel.sh <고정주소>  예) ops/setup-tunnel.sh investment.mydomain.com"
  exit 1
fi

if [[ ! -f "$CFG_DIR/cert.pem" ]]; then
  echo "❌ 먼저 로그인해야 합니다:  cloudflared tunnel login"
  echo "   (브라우저에서 본인 도메인을 선택하면 $CFG_DIR/cert.pem 이 생성됩니다)"
  exit 1
fi

# 터널이 없으면 생성 (있으면 재사용)
if ! cloudflared tunnel list 2>/dev/null | grep -qw "$TUNNEL"; then
  echo "▶ 터널 생성: $TUNNEL"
  cloudflared tunnel create "$TUNNEL"
else
  echo "▶ 기존 터널 재사용: $TUNNEL"
fi

# 터널 UUID + 자격증명 파일 경로
UUID="$(cloudflared tunnel list 2>/dev/null | awk -v t="$TUNNEL" '$2==t{print $1}')"
CRED="$CFG_DIR/$UUID.json"
echo "▶ UUID=$UUID"
echo "▶ 자격증명=$CRED"

# config.yml 작성 — 공개 호스트명 → 로컬 프론트엔드(:3000)
cat > "$CFG_DIR/config.yml" <<YAML
tunnel: $UUID
credentials-file: $CRED

ingress:
  - hostname: $HOSTNAME
    service: http://127.0.0.1:3000
  - service: http_status:404
YAML
echo "▶ config.yml 작성 완료 → $HOSTNAME → http://127.0.0.1:3000"

# DNS 라우팅 (본인 도메인에 서브도메인 CNAME 추가)
echo "▶ DNS 라우팅: $HOSTNAME"
cloudflared tunnel route dns "$TUNNEL" "$HOSTNAME"

echo ""
echo "✅ 터널 셋업 완료. 이제 항상 켜두려면:"
echo "     ops/install-services.sh"
echo "   또는 지금 한 번만 띄우려면:"
echo "     cloudflared tunnel run $TUNNEL"
echo ""
echo "   회사에서 접속 주소:  https://$HOSTNAME"
