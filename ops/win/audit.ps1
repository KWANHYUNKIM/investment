<#
.SYNOPSIS
  의존성 취약점 점검 — 파이썬(pip-audit) + 프런트(npm audit).

.DESCRIPTION
  인증을 아무리 잘 짜도 라이브러리로 뚫린다. 실제로 이 저장소에서 처음 돌렸을 때
  36건이 나왔고, 그중 둘이 직접적인 위험이었다 — starlette(웹 계층 그 자체)와
  pypdf(메일로 받은 **신뢰할 수 없는 PDF** 를 파싱하는 곳).

  **한 번 돌린 것으로는 다음 CVE 를 못 잡는다.** 새 취약점은 우리가 코드를 안 고쳐도
  나온다. 그래서 명령 하나로 언제든 돌릴 수 있게 두고, 커밋 훅에서도 부른다.

  종료 코드가 0 이 아니면 취약점이 있다는 뜻이라 CI 에서 바로 쓸 수 있다.

.EXAMPLE
  .\ops\win\audit.ps1              # 파이썬 + 프런트
  .\ops\win\audit.ps1 -Python      # 파이썬만 (훅이 쓰는 경로)
  .\ops\win\audit.ps1 -Fix         # 고칠 수 있는 것을 올린다(파이썬)
#>
[CmdletBinding()]
param(
    [switch]$Python,
    [switch]$Frontend,
    [switch]$Fix
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Py = Join-Path $Root "backend\.venv\Scripts\python.exe"
$failed = 0

if (-not $Python -and -not $Frontend) { $Python = $true; $Frontend = $true }

if ($Python) {
    if (-not (Test-Path $Py)) { throw "가상환경을 찾을 수 없습니다: $Py" }
    Push-Location (Join-Path $Root "backend")
    $env:PYTHONPATH = "src"

    # pip-audit 이 없으면 안내만 하고 통과시킨다 — 도구가 없다고 커밋을 막으면
    # 사람들이 훅을 꺼 버린다.
    & $Py -m pip_audit --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "pip-audit 미설치 — 건너뜁니다. 설치: pip install -r requirements-dev.txt"
    } else {
        Write-Host "== 파이썬 의존성 =="
        if ($Fix) {
            & $Py -m pip_audit --progress-spinner off --fix
        } else {
            & $Py -m pip_audit --progress-spinner off
        }
        if ($LASTEXITCODE -ne 0) { $failed++ } else { Write-Host "  취약점 없음" }
    }
    Pop-Location
}

if ($Frontend) {
    $fe = Join-Path $Root "frontend"
    if (Test-Path (Join-Path $fe "package-lock.json")) {
        Push-Location $fe
        Write-Host "== 프런트 의존성 =="
        # high 이상만 본다. 프런트 트리는 low/moderate 가 많아 전부 보면 잡음에 묻힌다.
        #
        # cmd 로 돌린다. 이 환경의 PowerShell 이 네이티브 인자를 갉아먹어
        # `npm audit` 이 `pm` 으로 전달되는 일이 있었다(Unknown command: "pm").
        & cmd.exe /c "npm audit --audit-level=high" 
        if ($LASTEXITCODE -ne 0) { $failed++ } else { Write-Host "  high 이상 없음" }
        Pop-Location
    } else {
        Write-Warning "package-lock.json 이 없어 프런트 점검을 건너뜁니다."
    }
}

if ($failed -gt 0) {
    Write-Host ""
    Write-Warning "취약점이 있습니다. 고칠 수 있는 것부터: .\ops\win\audit.ps1 -Python -Fix"
    exit 1
}
exit 0
