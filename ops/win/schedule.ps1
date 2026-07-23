<#
.SYNOPSIS
  자동화 등록 — 부팅 시 백엔드 기동 + 매일 야간 배치. Windows 작업 스케줄러 사용.

.DESCRIPTION
  앱 안에도 스케줄러가 있지만(원가모델 03:30 등), 그건 **백엔드가 떠 있을 때만** 돈다.
  PC 를 껐다 켜거나 서버가 죽으면 아무것도 안 돈다. 그래서 OS 레벨에 두 개를 건다:

    Investment-Backend   로그온 시 백엔드 기동(배치 잠금 대기 포함)
    Investment-Nightly   매일 03:10 야간 배치(원가모델 → 파서검증 → 감사리포트)

  야간 배치는 서버를 잠깐 내렸다가 다시 올린다(DuckDB 단일 쓰기).

.EXAMPLE
  .\ops\win\schedule.ps1 install          # 등록
  .\ops\win\schedule.ps1 status           # 등록 상태·최근 실행 결과
  .\ops\win\schedule.ps1 run -Task nightly # 지금 즉시 한 번 실행
  .\ops\win\schedule.ps1 uninstall
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("install", "uninstall", "status", "run")]
    [string]$Action = "status",

    [ValidateSet("backend", "nightly")]
    [string]$Task = "nightly",

    [string]$NightlyAt = "03:10"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Serve = Join-Path $Root "ops\win\serve.ps1"
$Batch = Join-Path $Root "ops\win\batch.ps1"
$NameBackend = "Investment-Backend"
$NameNightly = "Investment-Nightly"

function New-PsAction([string]$ScriptPath, [string]$Arguments) {
    New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`" $Arguments" `
        -WorkingDirectory $Root
}

switch ($Action) {
    "install" {
        # 1) 로그온 시 백엔드
        Register-ScheduledTask -TaskName $NameBackend -Force `
            -Action (New-PsAction $Serve "start") `
            -Trigger (New-ScheduledTaskTrigger -AtLogOn) `
            -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable `
                -ExecutionTimeLimit (New-TimeSpan -Hours 2)) `
            -Description "로그온 시 투자 백엔드 기동(DuckDB 잠금 대기 포함)" | Out-Null
        Write-Host "등록: $NameBackend (로그온 시)"

        # 2) 매일 야간 배치
        Register-ScheduledTask -TaskName $NameNightly -Force `
            -Action (New-PsAction $Batch "nightly") `
            -Trigger (New-ScheduledTaskTrigger -Daily -At $NightlyAt) `
            -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable `
                -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
                -MultipleInstances IgnoreNew) `
            -Description "야간 배치: 원가모델 → 파서검증 → 감사리포트" | Out-Null
        Write-Host "등록: $NameNightly (매일 $NightlyAt)"
        Write-Host "`n확인: .\ops\win\schedule.ps1 status"
    }
    "uninstall" {
        foreach ($n in @($NameBackend, $NameNightly)) {
            if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) {
                Unregister-ScheduledTask -TaskName $n -Confirm:$false
                Write-Host "해제: $n"
            }
        }
    }
    "run" {
        $n = if ($Task -eq "backend") { $NameBackend } else { $NameNightly }
        if (-not (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue)) {
            throw "$n 이 등록되어 있지 않습니다. 먼저 install 하세요."
        }
        Start-ScheduledTask -TaskName $n
        Write-Host "$n 실행 요청됨 — 진행 상황은 data\logs\ 를 보세요."
    }
    "status" {
        foreach ($n in @($NameBackend, $NameNightly)) {
            $t = Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
            if (-not $t) { Write-Host "$n : 미등록"; continue }
            $i = Get-ScheduledTaskInfo -TaskName $n
            Write-Host ("{0} : {1} · 마지막 {2} (결과 {3}) · 다음 {4}" -f `
                    $n, $t.State, $i.LastRunTime, $i.LastTaskResult, $i.NextRunTime)
        }
        $logs = Join-Path $Root "data\logs"
        if (Test-Path $logs) {
            Write-Host "`n최근 배치 로그:"
            Get-ChildItem $logs -Filter *.log | Sort-Object LastWriteTime -Descending |
                Select-Object -First 5 |
                ForEach-Object { Write-Host ("   {0}  {1:N0} KB  {2}" -f $_.LastWriteTime, ($_.Length / 1KB), $_.Name) }
        }
    }
}
