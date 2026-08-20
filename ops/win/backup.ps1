<#
.SYNOPSIS
  PostgreSQL 백업 — 뜨고, 검증하고, 오래된 것을 지운다.

.DESCRIPTION
  백업은 **복원이 되는지 확인해야** 백업이다. 뜨기만 하고 열어보지 않은 덤프는
  필요한 날에 깨져 있는 경우가 흔하다. 그래서 이 스크립트는 세 가지를 한다.

    1. pg_dump 로 뜬다 (custom 포맷 — 부분 복원과 병렬 복원이 된다)
    2. pg_restore --list 로 **열어서 목록을 뽑는다**. 여기서 깨진 덤프가 걸린다
    3. 보관 기간이 지난 것을 지운다

  덤프에는 가계부 거래·계정 해시가 들어 있다. 지금은 로컬 디스크에 그대로 두지만,
  외부로 옮길 때는 반드시 암호화해야 한다(README 참고).

.EXAMPLE
  .\ops\win\backup.ps1
  .\ops\win\backup.ps1 -Keep 30
  .\ops\win\backup.ps1 -Verify        # 최근 백업을 열어 목록만 확인
#>
[CmdletBinding()]
param(
    [int]$Keep = 14,                    # 보관 일수
    [switch]$Verify,                    # 새로 뜨지 않고 최근 것만 검증
    [string]$Container = "investment-db",
    [string]$Database = "investment",
    [string]$User = "investment"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Dir = Join-Path $Root "data\backups"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null

function Latest {
    Get-ChildItem $Dir -Filter "investment_*.dump" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Test-Dump([string]$Path) {
    # pg_restore --list 는 덤프의 목차를 읽는다. 깨진 파일이면 여기서 실패한다.
    $name = Split-Path $Path -Leaf
    & docker cp $Path "${Container}:/tmp/$name" | Out-Null
    $list = & docker exec $Container pg_restore --list "/tmp/$name" 2>&1
    & docker exec $Container rm -f "/tmp/$name" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "덤프를 열 수 없습니다: $name" }
    $tables = ($list | Select-String "TABLE DATA").Count
    return $tables
}

if (-not (& docker ps --filter "name=$Container" --format "{{.Names}}")) {
    throw "$Container 가 실행 중이 아닙니다. docker compose -f ops/postgres/docker-compose.yml up -d"
}

if ($Verify) {
    $f = Latest
    if (-not $f) { throw "백업이 없습니다." }
    $n = Test-Dump $f.FullName
    Write-Host "검증 통과: $($f.Name) — 데이터 있는 표 $n 개"
    return
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = Join-Path $Dir "investment_$stamp.dump"

# custom 포맷(-Fc): 압축되고, 표 단위 복원이 되고, pg_restore 로 목차를 읽을 수 있다.
& docker exec $Container pg_dump -U $User -d $Database -Fc --no-owner --no-privileges -f "/tmp/dump.bin"
if ($LASTEXITCODE -ne 0) { throw "pg_dump 실패" }
& docker cp "${Container}:/tmp/dump.bin" $out | Out-Null
& docker exec $Container rm -f /tmp/dump.bin | Out-Null

$size = [math]::Round((Get-Item $out).Length / 1MB, 2)
$tables = Test-Dump $out
Write-Host "백업 완료: $(Split-Path $out -Leaf)  ($size MB, 표 $tables 개) — 열어서 확인함"

# 보관 기간이 지난 것 정리. 최소 3개는 남긴다 — 기간만으로 지우면 오래 안 돌린 뒤
# 한 번 돌렸을 때 옛 백업이 통째로 사라진다.
$all = Get-ChildItem $Dir -Filter "investment_*.dump" | Sort-Object LastWriteTime -Descending
$old = $all | Select-Object -Skip 3 | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$Keep) }
foreach ($f in $old) {
    Remove-Item $f.FullName -Force
    Write-Host "  오래된 백업 삭제: $($f.Name)"
}
Write-Host "보관 중: $((Get-ChildItem $Dir -Filter 'investment_*.dump').Count) 개"
