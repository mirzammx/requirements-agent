<#
.SYNOPSIS
  Makes the Bid desk start by itself when you log in to Windows (app + mail watcher, hidden window).

.DESCRIPTION
  Puts a "Bid desk" shortcut in your Startup folder that runs start-biddesk.ps1. No admin rights needed.
  Docker Desktop must also start at login: Docker Desktop > Settings > General > "Start Docker Desktop when you sign in".
  To stop the auto-start: run this script with -Remove (or delete the shortcut from shell:startup).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install-autostart.ps1
  powershell -ExecutionPolicy Bypass -File .\install-autostart.ps1 -Remove
#>
param([switch]$Remove)

$link = Join-Path ([Environment]::GetFolderPath("Startup")) "Bid desk.lnk"
if ($Remove) {
    Remove-Item $link -ErrorAction SilentlyContinue
    Write-Host "Removed. The Bid desk will no longer start at login."
    return
}
$shell = New-Object -ComObject WScript.Shell
$s = $shell.CreateShortcut($link)
$s.TargetPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$s.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot 'start-biddesk.ps1')`""
$s.WorkingDirectory = $PSScriptRoot
$s.WindowStyle = 7
$s.Description = "Start the Bid desk app and mail watcher"
$s.Save()
Write-Host "Done. The Bid desk starts by itself at your next login. Log: $(Join-Path $PSScriptRoot 'data\logs\biddesk.log')"
