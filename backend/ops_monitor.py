"""독립 실행 Ops 모니터 대시보드 (별도 포트).

메인 백엔드(:8000)의 /api/ops/stats 를 폴링해 백그라운드 스케줄러/크롤러 상태와
DB 저장 현황(테이블별 행 수·용량)을 자동 새로고침 화면으로 보여준다.

DB 는 메인 백엔드가 단독 writer 로 잠그므로 이 모니터는 직접 DB 를 읽지 않고
백엔드 엔드포인트를 서버사이드로 프록시한다(브라우저는 이 포트만 → CORS 무관).

실행:
    cd backend && ./.venv/bin/python ops_monitor.py
    # → http://127.0.0.1:8899   (백엔드가 :8000 에 떠 있어야 함)

환경변수: OPS_PORT(기본 8899), OPS_BACKEND(기본 http://127.0.0.1:8000)
"""
from __future__ import annotations

import http.server
import json
import os
import socketserver
import urllib.request

PORT = int(os.environ.get("OPS_PORT", "8899"))
BACKEND = os.environ.get("OPS_BACKEND", "http://127.0.0.1:8000").rstrip("/")

HTML = """<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ops 모니터 · 크롤러/저장 현황</title>
<style>
  :root { --green:#217346; --bg:#f4f6f5; --card:#fff; --line:#e2e6e4; --mut:#8a938d; --ink:#222; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
    font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Apple SD Gothic Neo",sans-serif; }
  header { position:sticky; top:0; background:var(--green); color:#fff; padding:10px 16px;
    display:flex; align-items:center; gap:12px; flex-wrap:wrap; z-index:5; }
  header h1 { font-size:15px; margin:0; font-weight:700; }
  header .meta { font-size:12px; color:#cfe7d8; }
  header .right { margin-left:auto; display:flex; align-items:center; gap:12px; font-size:12px; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; }
  main { padding:16px; max-width:1200px; margin:0 auto; }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-bottom:18px; }
  .kpi { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 12px; }
  .kpi .n { font-size:20px; font-weight:700; color:var(--green); }
  .kpi .l { font-size:11px; color:var(--mut); margin-top:2px; }
  h2 { font-size:13px; color:var(--green); margin:18px 0 8px; border-left:3px solid var(--green); padding-left:8px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:10px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:11px 12px; }
  .card .top { display:flex; align-items:center; gap:7px; margin-bottom:7px; }
  .card .title { font-weight:700; font-size:13px; }
  .card .sub { font-size:11px; color:var(--mut); }
  .badge { font-size:10px; font-weight:700; padding:1px 7px; border-radius:10px; }
  .run { background:#e4f5ea; color:var(--green); }
  .idle { background:#eee; color:#888; }
  .chips { display:flex; flex-wrap:wrap; gap:5px; }
  .chip { font-size:11px; background:#f2f4f3; border:1px solid #e8ece9; border-radius:5px; padding:1px 6px; }
  .chip b { color:#333; }
  .chip.err { background:#fdecea; border-color:#f5c6c0; color:#c0392b; }
  .twrap { background:var(--card); border:1px solid var(--line); border-radius:8px; overflow:hidden; }
  .trow { display:flex; align-items:center; gap:10px; padding:6px 12px; border-top:1px solid #f0f2f1; }
  .trow:first-child { border-top:none; }
  .trow .tn { width:170px; flex-shrink:0; font-family:ui-monospace,Menlo,monospace; font-size:12px; }
  .trow .bar { flex:1; height:14px; background:#f1f3f2; border-radius:4px; overflow:hidden; }
  .trow .bar > div { height:14px; background:var(--green); border-radius:4px; }
  .trow .rn { width:110px; text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }
  .muted { color:var(--mut); }
  #err { display:none; background:#fdecea; color:#c0392b; padding:8px 12px; border-radius:6px; margin-bottom:12px; }
</style></head>
<body>
<header>
  <h1>🛰 Ops 모니터</h1>
  <span class="meta">백그라운드 크롤러 · DB 저장 현황</span>
  <div class="right">
    <label><input type="checkbox" id="auto" checked> 자동새로고침 5s</label>
    <span id="upd">—</span>
  </div>
</header>
<main>
  <div id="err"></div>
  <div class="kpis" id="kpis"></div>
  <h2>백그라운드 스케줄러 / 크롤러</h2>
  <div class="grid" id="scheds"></div>
  <h2>DB 테이블 저장량 (행 수)</h2>
  <div class="twrap" id="tables"></div>
</main>
<script>
const NUM = n => n==null ? "—" : n.toLocaleString("ko-KR");
const BYTES = b => { if(b==null) return "—"; const u=["B","KB","MB","GB"]; let i=0; while(b>=1024&&i<u.length-1){b/=1024;i++;} return b.toFixed(i?1:0)+u[i]; };
const AGO = t => { if(!t) return ""; const s=Date.now()/1000-t; if(s<60) return Math.max(1,s|0)+"초 전"; if(s<3600) return (s/60|0)+"분 전"; if(s<86400) return (s/3600|0)+"시간 전"; return (s/86400|0)+"일 전"; };
// status dict → 보기 좋은 칩들. running/error 는 특별 처리, 나머지는 key:value.
const PRIORITY = ["rows_written","records","changed_rows","snapshots","checked","profiles","financials","dart_financials","foreign_fin","universe","last_date","last_run","last_saved_date","interval_sec"];
const LABELS = {rows_written:"기록행",records:"기록",changed_rows:"변경행",snapshots:"스냅샷",checked:"점검",profiles:"프로파일",financials:"재무",dart_financials:"DART재무",foreign_fin:"해외",universe:"유니버스",last_date:"최신일",last_run:"최근실행",last_saved_date:"저장일",interval_sec:"주기(초)",ticks:"틱",sweeps:"스윕",theme_refreshes:"테마갱신"};
function chips(st){
  const out=[]; const seen=new Set();
  const err = st.error||st.last_error;
  const push=(k,v)=>{ if(seen.has(k)||v==null||v==="") return; seen.add(k);
    let disp = k==="last_run"||k==="last_saved_date" ? AGO(typeof v==="number"?v:Date.parse(v)/1000)||v : (typeof v==="number"?NUM(v):v);
    out.push(`<span class="chip"><b>${LABELS[k]||k}</b> ${disp}</span>`); };
  for(const k of PRIORITY) if(k in st) push(k, st[k]);
  for(const k in st){ if(["running","error","last_error"].includes(k)) continue; push(k, st[k]); }
  if(err) out.push(`<span class="chip err">⚠ ${err}</span>`);
  return out.join("");
}
async function tick(){
  let d;
  try { d = await (await fetch("/stats",{cache:"no-store"})).json(); }
  catch(e){ document.getElementById("err").style.display="block"; document.getElementById("err").textContent="백엔드 연결 실패 (:8000 실행 중인지 확인)"; return; }
  if(d.error){ document.getElementById("err").style.display="block"; document.getElementById("err").textContent="백엔드 오류: "+d.error; return; }
  document.getElementById("err").style.display="none";
  document.getElementById("upd").textContent = "업데이트 "+AGO(d.ts);

  const totalRows = d.tables.reduce((a,t)=>a+(t.rows||0),0);
  const runN = d.schedulers.filter(s=>s.status&&s.status.running).length;
  document.getElementById("kpis").innerHTML = [
    ["DB 용량", BYTES(d.db.size_bytes)],
    ["WAL(미반영)", BYTES(d.db.wal_bytes)],
    ["총 저장 행", NUM(totalRows)],
    ["테이블 수", NUM(d.tables.length)],
    ["실행중 스케줄러", runN+" / "+d.schedulers.length],
    ["주가 최신일", d.db.max_price_date||"—"],
  ].map(([l,n])=>`<div class="kpi"><div class="n">${n}</div><div class="l">${l}</div></div>`).join("");

  document.getElementById("scheds").innerHTML = d.schedulers.map(s=>{
    const run = s.status && s.status.running;
    const tRows = (s.tables||[]).map(tn=>{const t=d.tables.find(x=>x.table===tn); return t?`${tn} ${NUM(t.rows)}`:tn;});
    return `<div class="card">
      <div class="top">
        <span class="badge ${run?'run':'idle'}"><span class="dot" style="background:${run?'#217346':'#bbb'}"></span>${run?'실행중':'대기'}</span>
        <span class="title">${s.label}</span>
      </div>
      <div class="sub" style="margin-bottom:6px">${s.name}${tRows.length?' · '+tRows.join(' / '):''}</div>
      <div class="chips">${chips(s.status||{})}</div>
    </div>`;
  }).join("");

  const max = Math.max(1, ...d.tables.map(t=>t.rows||0));
  document.getElementById("tables").innerHTML = d.tables.map(t=>`
    <div class="trow">
      <span class="tn">${t.table}</span>
      <span class="bar"><div style="width:${((t.rows||0)/max*100).toFixed(1)}%"></div></span>
      <span class="rn">${NUM(t.rows)}</span>
    </div>`).join("");
}
let timer;
function schedule(){ clearInterval(timer); if(document.getElementById("auto").checked) timer=setInterval(tick,5000); }
document.getElementById("auto").addEventListener("change",schedule);
tick(); schedule();
</script>
</body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/stats"):
            try:
                req = urllib.request.Request(f"{BACKEND}/api/ops/stats")
                with urllib.request.urlopen(req, timeout=15) as r:
                    self._send(200, r.read(), "application/json; charset=utf-8")
            except Exception as e:
                self._send(502, json.dumps({"error": str(e)}).encode(), "application/json")
        else:
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")

    def log_message(self, *args) -> None:  # 조용히
        pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("127.0.0.1", PORT), Handler) as httpd:
        print(f"🛰 Ops 모니터: http://127.0.0.1:{PORT}  (백엔드 {BACKEND})")
        httpd.serve_forever()
