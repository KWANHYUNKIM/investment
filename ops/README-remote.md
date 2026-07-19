# 회사에서 접속하기 (Cloudflare 고정 터널)

로컬(집 Mac)은 이미 다 세팅됨:
- 백엔드 FastAPI `:8000` + 크롤링 스케줄러 전부 동작
- 프론트엔드 Next.js `:3000` — `/api/*` 를 백엔드로 프록시(공개 URL 하나로 끝)
- 로그인 인증으로 데이터 보호됨

아래는 **한 번만** 하면 되는 '외부 노출' 설정. ①②는 사용자가 직접(브라우저·도메인),
③④는 준비된 스크립트로 끝.

---

## ① Cloudflare 에 내 도메인 등록 (없으면 1회)
- 이미 Cloudflare 를 쓰는 도메인이 있으면 건너뜀.
- 없으면: 도메인 하나(예: `.com` 아무거나)를 사서 Cloudflare 대시보드 → **Add a site** →
  네임서버를 Cloudflare 로 변경. (무료 플랜으로 충분)
- 도메인 사기 싫으면 → 맨 아래 **"도메인 없이 임시로"** 참고.

## ② cloudflared 로그인 (1회, 브라우저)
```bash
cloudflared tunnel login
```
브라우저가 열리면 위 도메인을 선택 → `~/.cloudflared/cert.pem` 생성됨.

## ③ 터널 생성·연결 (스크립트)
`investment` 를 원하는 서브도메인으로 바꿔서:
```bash
ops/setup-tunnel.sh investment.내도메인.com
```
→ 터널 생성 + `config.yml`(`:3000` 으로 프록시) + DNS(CNAME) 자동 등록.

## ④ 항상 켜두기 (재부팅해도 자동 시작)
```bash
ops/install-services.sh
```
백엔드·프론트엔드·터널을 launchd 서비스로 등록(죽으면 자동 재시작, 로그인 시 자동 시작).

**끝. 회사에서:** `https://investment.내도메인.com` → 로그인 → 대시보드 🎉

---

## 항상 응답하게 (Mac 잠들면 서버도 멈춤)
전원 연결 상태에서 잠들지 않게:
```bash
sudo pmset -c sleep 0 disksleep 0
```
노트북 덮개 닫고도 쓰려면 위 설정 + 외부전원(클램셸).

## 관리 명령
```bash
launchctl list | grep com.investment          # 상태
tail -f ops/logs/{backend,frontend,tunnel}.log # 로그
ops/uninstall-services.sh                       # 자동시작 해제
```

## 크롤링 추가 데이터 키 (선택)
부동산 실거래가·국내 거시(ECOS)·해외 펀더멘털(Finnhub)·DART·AI 예측을 켜려면
무료 키 발급 후 `backend/.env` 에 입력:
```bash
cp backend/.env.example backend/.env   # 편집해서 키 채우기 → 백엔드 재시작
```
키가 없어도 한국/미국 시세·급등락·개장예측·데일리리포트·미래테마는 자동 동작함.

---

## 도메인 없이 임시로 (Quick Tunnel)
도메인/로그인 없이 즉시 공개 URL(단, 재시작마다 주소 바뀜):
```bash
cloudflared tunnel --url http://127.0.0.1:3000
```
출력되는 `https://xxxx.trycloudflare.com` 로 회사에서 접속. 고정 주소가 필요하면 위 ①~④.
