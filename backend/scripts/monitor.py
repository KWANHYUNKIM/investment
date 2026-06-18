"""Standalone scheduler-health dashboard on its OWN port.

The background schedulers (daily-report snapshotter, price scheduler, fundamentals
crawler) all run *inside* the API process — they must, because DuckDB is a single
writer and a second process would deadlock on the file lock. So this is not a
second scheduler; it's a read-only **monitor**: a tiny web page on a different
port that polls the API's status endpoints and shows, at a glance, whether each
job is alive and ticking.

Run it (backend venv):
    python scripts/monitor.py                 # serves http://127.0.0.1:8500
    MONITOR_PORT=9000 API_BASE=http://127.0.0.1:8000 python scripts/monitor.py

It needs nothing but the API running on API_BASE; refresh is automatic.
"""
from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
PORT = int(os.environ.get("MONITOR_PORT", "8500"))


def _get(path: str):
    r = requests.get(f"{API_BASE}{path}", timeout=5)
    r.raise_for_status()
    return r.json()


def _aggregate() -> dict:
    """Poll the API's health + status endpoints into one blob."""
    out: dict = {"api_base": API_BASE, "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        out["health"] = _get("/api/health")
        out["up"] = True
    except Exception as e:
        out["up"] = False
        out["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        return out
    for key, path in (
        ("report", "/api/data/report-scheduler-status"),
        ("price", "/api/data/price-scheduler-status"),
        ("fundamentals", "/api/data/crawler-status"),
        ("industry", "/api/data/industry-scheduler-status"),
    ):
        try:
            out[key] = _get(path)
        except Exception as e:
            out[key] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
    return out


PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>스케줄러 모니터.xlsx - Excel</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{box-sizing:border-box}
body{margin:0;background:#fafafa;color:#1f1f1f;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}
.title{display:flex;align-items:center;gap:8px;background:#217346;color:#fff;padding:8px 16px;font-weight:600;font-size:14px}
.title .x{display:inline-flex;width:20px;height:20px;align-items:center;justify-content:center;background:#fff;color:#217346;border-radius:4px;font-weight:800;font-size:12px}
.wrap{max-width:1100px;margin:0 auto;padding:20px 20px 60px}
h1{font-size:18px;margin:0 0 2px}
.sub{color:#888;font-size:12px;margin-bottom:18px}
.banner{display:flex;align-items:center;gap:12px;border-radius:6px;padding:14px 18px;margin-bottom:20px;font-weight:700;font-size:15px;border:1px solid}
.ok{background:#eef6f0;border-color:#a9d08e;color:#217346}
.bad{background:#fdeeee;border-color:#e2a3a3;color:#c92a2a}
.dot{width:11px;height:11px;border-radius:50%;flex:0 0 auto}
.dot.live{background:#2fa55e;box-shadow:0 0 0 0 #2fa55e66;animation:p 1.6s infinite}
.dot.off{background:#d64545}
@keyframes p{0%{box-shadow:0 0 0 0 #2fa55e66}70%{box-shadow:0 0 0 9px #2fa55e00}100%{box-shadow:0 0 0 0 #2fa55e00}}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.card{background:#fff;border:1px solid #d0d0d0;border-radius:6px;overflow:hidden;box-shadow:0 1px 2px #0000000d}
.card h2{font-size:13px;margin:0;display:flex;align-items:center;gap:8px;background:#f3f2f1;border-bottom:1px solid #d0d0d0;padding:8px 12px}
.card .body{padding:6px 12px 10px}
.pill{font-size:11px;font-weight:700;padding:2px 8px;border-radius:3px;margin-left:auto}
.pill.on{background:#a9d08e;color:#244d1a}
.pill.offp{background:#f3c0c0;color:#8a2020}
.desc{color:#888;font-size:11px;margin:6px 0 8px}
table{width:100%;border-collapse:collapse;font-size:13px}
td{padding:5px 4px;border-bottom:1px solid #eee;vertical-align:top}
td.k{color:#666;width:46%}
td.v{color:#1f1f1f;text-align:right;font-variant-numeric:tabular-nums;word-break:break-all}
.err{color:#c92a2a}
.foot{margin-top:22px;color:#999;font-size:12px;text-align:center}
.beat{display:inline-block;width:7px;height:7px;border-radius:50%;background:#2fa55e;margin-right:6px;animation:p 1.6s infinite}
code{background:#eef0f2;padding:1px 6px;border-radius:4px;color:#1155cc}
</style></head>
<body>
<div class="title"><span class="x">X</span> 스케줄러 모니터.xlsx <span style="opacity:.7;font-size:12px">— Excel</span></div>
<div class="wrap">
<h1>🩺 스케줄러 모니터</h1>
<div class="sub">백엔드 <code id="apibase"></code> 의 백그라운드 작업 상태 · <span class="beat"></span><span id="refresh">자동 갱신 3초</span></div>
<div id="banner" class="banner ok"><span class="dot live"></span><span id="verdict">확인 중…</span></div>
<div id="cards" class="grid"></div>
<div class="foot">마지막 점검: <span id="checked">—</span> · DuckDB 단일 writer 제약상 스케줄러는 API 프로세스 내부에서 돌고, 이 페이지는 다른 포트의 읽기 전용 모니터입니다.</div>
</div>
<script>
const REL=(s)=>{if(!s)return"—";const t=(Date.now()-new Date(s.replace(' ','T')).getTime())/1000;if(isNaN(t))return s;if(t<60)return Math.round(t)+"초 전";if(t<3600)return Math.round(t/60)+"분 전";return Math.round(t/3600)+"시간 전";};
function row(k,v,err){return `<tr><td class="k">${k}</td><td class="v ${err?'err':''}">${v??'—'}</td></tr>`;}
function card(title,desc,st,rows){
  const on=st&&st.running;
  const bad=st&&st.last_error;
  return `<div class="card"><h2>${title}<span class="pill ${on?'on':'offp'}">${on?'RUNNING':'STOPPED'}</span></h2>
    <div class="body"><p class="desc">${desc}</p><table>${rows}</table>
    ${bad?`<table><tr><td class="k">last_error</td><td class="v err">${st.last_error}</td></tr></table>`:''}</div></div>`;
}
async function tick(){
  let d;
  try{ d=await (await fetch('/status',{cache:'no-store'})).json(); }
  catch(e){ document.getElementById('verdict').textContent='모니터 응답 없음'; return; }
  document.getElementById('apibase').textContent=d.api_base||'';
  document.getElementById('checked').textContent=d.checked_at||'—';
  const b=document.getElementById('banner'), v=document.getElementById('verdict');
  if(!d.up){
    b.className='banner bad'; b.querySelector('.dot').className='dot off';
    v.textContent='백엔드 연결 불가 — '+(d.error||'');
    document.getElementById('cards').innerHTML=''; return;
  }
  const rep=d.report||{}, pr=d.price||{}, fu=d.fundamentals||{}, ind=d.industry||{};
  const anyErr = rep.last_error||pr.last_error||ind.last_error;
  const allRun = rep.running&&pr.running&&fu.running&&ind.running;
  if(allRun&&!anyErr){ b.className='banner ok'; b.querySelector('.dot').className='dot live'; v.textContent='정상 작동 중 — 모든 스케줄러가 돌고 있습니다'; }
  else if(anyErr){ b.className='banner bad'; b.querySelector('.dot').className='dot off'; v.textContent='오류 감지 — 아래 카드를 확인하세요'; }
  else{ b.className='banner ok'; b.querySelector('.dot').className='dot live'; v.textContent='일부 스케줄러 비활성 (설정상 꺼졌을 수 있음)'; }

  const cards=[
    card('📋 데일리 리포트 스케줄러','거래일마다 전체 리포트를 JSON으로 저장',rep,
      row('마지막 실행',REL(rep.last_run))+row('점검 횟수',rep.ticks)+row('저장한 스냅샷',rep.snapshots)
      +row('마지막 저장일',rep.last_saved_date)+row('마지막 상태',rep.last_status)
      +row('점검 주기',(rep.interval_sec/60|0)+'분')+row('심층 종목수',rep.deep_n)
      +row('보관된 날짜수',(rep.archived_dates||[]).length)),
    card('📈 가격 스케줄러','전 종목 일봉(OHLCV)을 DuckDB에 적재',pr,
      row('마지막 실행',REL(pr.last_run))+row('점검 횟수',pr.ticks)+row('누적 적재행',pr.rows_written)
      +row('직전 적재행',pr.last_rows)+row('마지막 데이터일',pr.last_date)
      +row('점검 주기',(pr.interval_sec/60|0)+'분')),
    card('🧮 펀더멘털 크롤러','PER/PBR/외인비율 등을 변경 시에만 누적',fu,
      row('마지막 실행',REL(fu.last_run))+row('유니버스',fu.universe)+row('점검한 종목',fu.checked)
      +row('변경 저장행',fu.changed_rows)+row('전체 스윕',fu.sweeps)
      +row('점검 주기',fu.interval_sec+'초')),
    card('🏭 산업 지도 스케줄러','업종 프로파일 + 경쟁군 뉴스 취합을 누적',ind,
      row('마지막 실행',REL(ind.last_run))+row('점검 횟수',ind.ticks)+row('적재 프로파일',ind.profiles)
      +row('저장 스냅샷',ind.snapshots)+row('마지막 스냅샷일',ind.last_snapshot_date)
      +row('분석 종목수/업종',ind.top_k)+row('스냅샷 업종수',ind.snapshot_n)),
  ];
  document.getElementById('cards').innerHTML=cards.join('');
}
tick(); setInterval(tick,3000);
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/status"):
            self._send(json.dumps(_aggregate()).encode("utf-8"), "application/json; charset=utf-8")
        elif self.path in ("/", "/index.html"):
            self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # quiet
        pass


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"scheduler monitor on http://127.0.0.1:{PORT}  (watching {API_BASE})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
