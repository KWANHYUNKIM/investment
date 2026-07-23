<#
.SYNOPSIS
  야간 배치·검증·리포트를 한 명령으로. 서버와 DuckDB 잠금을 알아서 조율한다.

.DESCRIPTION
  DuckDB 는 단일 쓰기라 **DB 를 쓰는 배치는 서버를 잠깐 내려야** 한다. 손으로 하면
  까먹기 쉬운 부분이라 스크립트가 stop → 배치 → start 를 묶어서 처리한다.

  작업 목록
    costmodel  전 종목 원가모델 배치(감사점수·인건비·재료비 실측 포함). **DB 필요** → 서버 정지
    delisting  관리종목·상폐 스크리너 캐시.                              **DB 필요** → 서버 정지
    blog       오늘의 증시 보고서 블로그 글 발행(data/blog_posts).        **DB 필요** → 서버 정지
    verify     공시 파서 스모크 테스트(품질 깨지면 종료코드 1).           DB 불필요 → 서버 유지
    report     전 종목 재무제표 감사 리포트(업종 보정).                   DB 불필요 → 서버 유지
    nightly    costmodel → verify → report 순서로 전부

.EXAMPLE
  .\ops\win\batch.ps1 verify
  .\ops\win\batch.ps1 costmodel
  .\ops\win\batch.ps1 nightly
  .\ops\win\batch.ps1 report -Top 40
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("costmodel", "delisting", "verify", "report", "blog", "nightly")]
    [string]$Task = "report",

    [int]$Top = 20,
    [string]$Date = "",          # blog: 대상 날짜(YYYY-MM-DD), 비우면 오늘
    [double]$Sleep = 0.1,        # 원가모델 배치의 종목 간 대기(DART rate limit)
    [switch]$KeepServer          # DB 배치라도 서버를 내리지 않는다(실패할 수 있음)
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$Serve = Join-Path $PSScriptRoot "serve.ps1"
$LogDir = Join-Path $Root "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Invoke-Py {
    param([string[]]$PyArgs, [string]$Label)
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $log = Join-Path $LogDir "$Label-$stamp.log"
    Write-Host "▶ $Label 시작 — 로그 $log"
    $env:PYTHONPATH = $Backend
    $env:PYTHONUNBUFFERED = "1"
    Push-Location $Backend
    try {
        # Out-Host 로 흘려보내야 함수 반환값(종료코드)에 로그가 섞이지 않는다.
        & $Python @PyArgs 2>&1 | Tee-Object -FilePath $log | Out-Host
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    Write-Host "◀ $Label 종료 (exit $code)"
    return $code
}

function Invoke-DbTask {
    param([string[]]$PyArgs, [string]$Label)
    $wasUp = $false
    if (-not $KeepServer) {
        $up = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*uvicorn*app.main:app*" }
        if ($up) {
            $wasUp = $true
            Write-Host "DB 작업이라 백엔드를 잠시 내립니다…"
            & $Serve stop | Out-Host
        }
    }
    try {
        return (Invoke-Py -PyArgs $PyArgs -Label $Label | Select-Object -Last 1)
    } finally {
        if ($wasUp) {
            Write-Host "백엔드를 다시 올립니다…"
            & $Serve start | Out-Host
        }
    }
}

$fail = 0
switch ($Task) {
    "costmodel" {
        # 전 종목 analyze() → data\company_costmodels.json (감사점수·인건비·재료비 포함)
        $code = "from app.data.fundamentals import company_costmodel as c; import json; " +
                "print(json.dumps(c.build_batch(sleep_sec=$Sleep), ensure_ascii=False))"
        $fail = Invoke-DbTask -PyArgs @("-c", $code) -Label "costmodel"
    }
    "delisting" {
        $fail = Invoke-DbTask -PyArgs @("-m", "scripts.build_delisting") -Label "delisting"
    }
    "verify" {
        $fail = Invoke-Py -PyArgs @("-m", "scripts.verify_parsers",
            "--json", (Join-Path $Root "data\verify_parsers.json")) -Label "verify"
        if ($fail -ne 0) { Write-Warning "파서 품질 경고 발생 — 로그를 확인하세요." }
    }
    "report" {
        $fail = Invoke-Py -PyArgs @("-m", "scripts.audit_report", "--top", "$Top",
            "--json", (Join-Path $Root "data\audit_report.json")) -Label "report"
    }
    "blog" {
        # 시세·수급을 DuckDB 에서 읽어 오늘자 증시 보고서를 만든다 → 서버 정지 필요
        $a = @("-m", "scripts.build_blog")
        if ($Date) { $a += @("--date", $Date) }
        $fail = Invoke-DbTask -PyArgs $a -Label "blog"
    }
    "nightly" {
        $c1 = Invoke-DbTask -PyArgs @("-c",
            "from app.data.fundamentals import company_costmodel as c; import json; " +
            "print(json.dumps(c.build_batch(sleep_sec=$Sleep), ensure_ascii=False))") -Label "costmodel"
        $c2 = Invoke-Py -PyArgs @("-m", "scripts.verify_parsers",
            "--json", (Join-Path $Root "data\verify_parsers.json")) -Label "verify"
        $c3 = Invoke-Py -PyArgs @("-m", "scripts.audit_report", "--top", "$Top",
            "--json", (Join-Path $Root "data\audit_report.json")) -Label "report"
        $fail = [Math]::Max([Math]::Max($c1, $c2), $c3)
        Write-Host "`n야간 배치 요약: costmodel=$c1 verify=$c2 report=$c3"
    }
}
exit $fail
