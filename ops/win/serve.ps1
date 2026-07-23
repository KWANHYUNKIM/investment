<#
.SYNOPSIS
  백엔드(uvicorn) 기동·중지·상태 확인. DuckDB 쓰기잠금까지 알아서 처리한다.

.DESCRIPTION
  이 프로젝트의 DuckDB 는 **단일 쓰기(single-writer)** 라, 배치가 돌고 있으면 서버가
  뜨지 못하고 startup 에서 IOException 으로 죽는다. 반대로 서버가 떠 있으면 배치가
  DB 를 못 연다. 손으로 하면 매번 걸리는 부분이라 스크립트가 대신 처리한다:

    · start   : 배치가 끝날 때까지 기다렸다가 기동
    · 기동방식 : Start-Process 로 **콘솔 세션과 분리**해 띄운다. 터미널을 닫아도 살아 있고,
                반대로 터미널 타임아웃에 같이 죽지도 않는다.
    · 로그    : data\uvicorn.log / uvicorn.err.log

.EXAMPLE
  .\ops\win\serve.ps1 start
  .\ops\win\serve.ps1 restart
  .\ops\win\serve.ps1 status
  .\ops\win\serve.ps1 logs -Tail 40
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status", "logs")]
    [string]$Action = "status",

    [ValidateSet("backend", "frontend", "all")]
    [string]$App = "all",           # 무엇을 다룰지. status 는 항상 둘 다 보여준다

    [int]$Port = 8000,
    [int]$WebPort = 3000,
    [int]$Tail = 20,
    [int]$WaitMinutes = 90          # 배치 종료를 기다리는 최대 시간
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$LogOut = Join-Path $Root "data\uvicorn.log"
$LogErr = Join-Path $Root "data\uvicorn.err.log"

function Get-ServerProcs {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*uvicorn*app.main:app*" }
}

function Get-BatchProcs {
    # DuckDB 쓰기잠금을 쥘 수 있는 배치들(원가모델·상폐·수집)
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -like "*build_batch*" -or
            $_.CommandLine -like "*refresh_all*" -or
            $_.CommandLine -like "*scripts.ingest*" -or
            $_.CommandLine -like "*scripts.build_*"
        }
}

function Get-WebProcs {
    Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*next*" -or $_.CommandLine -like "*npm*run*dev*" }
}

function Test-Web {
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$WebPort/" -TimeoutSec 5 -UseBasicParsing
        return $r.StatusCode -eq 200
    } catch { return $false }
}

function Stop-Web {
    $ps = @(Get-WebProcs)
    if (-not $ps) { Write-Host "프론트: 실행 중 아님"; return }
    foreach ($p in $ps) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "프론트 중지 (pid $($p.ProcessId))"
    }
    Start-Sleep -Seconds 2
}

function Start-Web {
    if (Get-WebProcs) { Write-Host "프론트: 이미 실행 중"; return }
    $fe = Join-Path $Root "frontend"
    if (-not (Test-Path (Join-Path $fe "node_modules"))) {
        Write-Warning "node_modules 없음 — frontend 에서 npm install 을 먼저 하세요."
        return
    }
    # npm 은 배치 파일이라 cmd 를 거쳐야 하고, 여기서도 세션과 분리해 띄운다.
    $p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" `
        -WorkingDirectory $fe `
        -RedirectStandardOutput (Join-Path $Root "data\next.log") `
        -RedirectStandardError (Join-Path $Root "data\next.err.log") `
        -WindowStyle Hidden -PassThru
    Write-Host "프론트 기동 (pid $($p.Id)) — 세션과 분리됨"
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        if (Test-Web) { Write-Host "준비 완료: http://127.0.0.1:$WebPort"; return }
    }
    Write-Warning "60초 내 응답 없음 — data\next.err.log 를 확인하세요."
}

function Test-Api {
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$Port/openapi.json" -TimeoutSec 5 -UseBasicParsing
        return $r.StatusCode -eq 200
    } catch {
        # 401 은 인증 미들웨어가 살아 있다는 뜻이므로 '떠 있음'으로 본다
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode.value__ -in 401, 403) { return $true }
        return $false
    }
}

function Stop-Server {
    $ps = Get-ServerProcs
    if (-not $ps) { Write-Host "백엔드: 실행 중 아님"; return }
    foreach ($p in $ps) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "백엔드 중지 (pid $($p.ProcessId))"
    }
    Start-Sleep -Seconds 2
}

function Start-Server {
    if (Get-ServerProcs) { Write-Host "이미 실행 중"; return }
    if (-not (Test-Path $Python)) { throw "가상환경 파이썬 없음: $Python" }

    $busy = Get-BatchProcs
    if ($busy) {
        Write-Host "배치가 DuckDB 를 쓰는 중 — 끝날 때까지 대기 (최대 $WaitMinutes 분)"
        foreach ($b in $busy) { Write-Host ("   pid {0}: {1}" -f $b.ProcessId, $b.CommandLine.Substring(0, [Math]::Min(90, $b.CommandLine.Length))) }
        $deadline = (Get-Date).AddMinutes($WaitMinutes)
        while ((Get-Date) -lt $deadline -and (Get-BatchProcs)) { Start-Sleep -Seconds 15 }
        if (Get-BatchProcs) { throw "배치가 $WaitMinutes 분 내에 끝나지 않음 — 나중에 다시 시도하세요." }
        Write-Host "배치 종료 확인"
    }

    $env:PYTHONPATH = $Backend
    $env:PYTHONUNBUFFERED = "1"
    $p = Start-Process -FilePath $Python `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port" `
        -WorkingDirectory $Backend `
        -RedirectStandardOutput $LogOut -RedirectStandardError $LogErr `
        -WindowStyle Hidden -PassThru
    Write-Host "백엔드 기동 (pid $($p.Id)) — 세션과 분리됨"

    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 2
        if (Test-Api) { Write-Host "준비 완료: http://127.0.0.1:$Port"; return }
        if (-not (Get-ServerProcs)) {
            Write-Warning "기동 실패 — 마지막 오류:"
            if (Test-Path $LogErr) { Get-Content $LogErr -Tail 12 }
            throw "백엔드가 뜨지 못했습니다."
        }
    }
    Write-Warning "40초 내 응답 없음 — 로그를 확인하세요: .\ops\win\serve.ps1 logs"
}

$doBack = $App -in @("backend", "all")
$doWeb = $App -in @("frontend", "all")

switch ($Action) {
    "start" { if ($doBack) { Start-Server }; if ($doWeb) { Start-Web } }
    "stop" { if ($doBack) { Stop-Server }; if ($doWeb) { Stop-Web } }
    "restart" {
        if ($doBack) { Stop-Server }
        if ($doWeb) { Stop-Web }
        if ($doBack) { Start-Server }
        if ($doWeb) { Start-Web }
    }
    "logs" {
        if (Test-Path $LogOut) { Write-Host "--- uvicorn.log ---"; Get-Content $LogOut -Tail $Tail }
        if (Test-Path $LogErr) { Write-Host "--- uvicorn.err.log ---"; Get-Content $LogErr -Tail $Tail }
    }
    "status" {
        $ps = @(Get-ServerProcs)
        $ws = @(Get-WebProcs)
        $bs = @(Get-BatchProcs)
        Write-Host ("백엔드 : {0}" -f $(if ($ps) { "실행 중 (pid " + ($ps.ProcessId -join ", ") + ")" } else { "중지" }))
        Write-Host ("API    : {0}" -f $(if (Test-Api) { "응답함 (:$Port)" } else { "응답 없음" }))
        Write-Host ("프론트  : {0}" -f $(if (Test-Web) { "응답함 (:$WebPort)" } elseif ($ws) { "기동 중" } else { "중지" }))
        Write-Host ("배치    : {0}" -f $(if ($bs) { "$($bs.Count)개 실행 중 — DB 잠금" } else { "없음" }))
        $f = Join-Path $Root "data\company_costmodels.json"
        if (Test-Path $f) {
            $fi = Get-Item $f
            Write-Host ("원가배치 : {0} ({1:N0} KB)" -f $fi.LastWriteTime, ($fi.Length / 1KB))
        }
    }
}
