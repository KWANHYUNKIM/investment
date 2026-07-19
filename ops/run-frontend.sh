#!/bin/bash
# 프론트엔드(Next.js) 실행 래퍼. 프로덕션 빌드 후 start (항상 켜두는 용도로 dev 보다 안정적).
# 코드를 바꾸면 이 스크립트가 재시작될 때 자동으로 다시 빌드한다.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /Users/kwanhyun/investment/frontend
npm run build
exec npm run start -- --port 3000
