<#
.SYNOPSIS
  Starts the whole Bid desk: waits for Docker, starts the app, then runs the mail watcher.
  Run by the Startup shortcut at Windows login (see install-autostart.ps1). Log: data\logs\biddesk.log

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\start-biddesk.ps1
#>
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$logDir = Join-Path $PSScriptRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "biddesk.log"
function Log($text) { Add-Content -Path $log -Encoding UTF8 -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $text) }

Log "Starting. Waiting for Docker Desktop..."
$deadline = (Get-Date).AddMinutes(15)
while ($true) {
    & docker info *> $null
    if ($LASTEXITCODE -eq 0) { break }
    if ((Get-Date) -gt $deadline) { Log "Docker did not start in 15 minutes. Start Docker Desktop, then run start-biddesk.ps1 again."; exit 1 }
    Start-Sleep -Seconds 10
}

$up = & docker compose up -d web 2>&1 | Out-String
Log "App: $($up.Trim())"

Log "Starting the mail watcher."
& (Join-Path $PSScriptRoot "mailwatch.ps1") *>> $log
Log "Mail watcher stopped."
