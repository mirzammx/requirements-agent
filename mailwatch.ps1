<#
.SYNOPSIS
  Bid desk mail watcher: moves mail between your Outlook and the Bid desk app. Never sends mail.

.DESCRIPTION
  Every pass:
   1. Each new mail in the Outlook folder "Bid desk" is saved as .msg and handed to the app
      (POST /api/intake). The app decides whether it is a bid (-> triage) or a BidAssist alert
      (-> screen the "Power supply" list only). The mail is then tagged "Bid desk: picked up".
   2. Replies the app has ready (after Mahadevan's Go / No-go / Ask) are created as ReplyAll drafts
      in the original thread, with Mahadevan in CC and the response pack attached on Go, and SAVED
      to your Drafts folder. You check them and press Send yourself.

  Needs: classic Outlook running, and the Bid desk app running (docker compose up -d web).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\mailwatch.ps1            # keep watching, every 2 minutes
  powershell -ExecutionPolicy Bypass -File .\mailwatch.ps1 -Once      # one pass, then exit
#>
param(
    [switch]$Once,
    [int]$IntervalSeconds = 120,
    [string]$FolderName = "Bid desk",
    [string]$AppUrl = "http://localhost:8010"
)

$ErrorActionPreference = "Stop"
$PickedUp = "Bid desk: picked up"
$DataDir = Join-Path $PSScriptRoot "data"
$Temp = Join-Path $env:TEMP "biddesk-mailwatch"
New-Item -ItemType Directory -Force -Path $Temp | Out-Null

function Log($text) { Write-Host ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $text) }

function Get-Outlook {
    try { return [Runtime.InteropServices.Marshal]::GetActiveObject("Outlook.Application") }
    catch { return New-Object -ComObject Outlook.Application }
}

function Get-BidFolder($ns) {
    $inbox = $ns.GetDefaultFolder(6)   # olFolderInbox
    foreach ($f in $inbox.Folders) { if ($f.Name -eq $FolderName) { return $f } }
    foreach ($f in $inbox.Parent.Folders) { if ($f.Name -eq $FolderName) { return $f } }
    Log "Creating Outlook folder '$FolderName' under Inbox. Drag BD's bid mails and BidAssist alerts into it, or add an Outlook rule."
    return $inbox.Folders.Add($FolderName)
}

function Ensure-Category($ns) {
    foreach ($c in $ns.Categories) { if ($c.Name -eq $PickedUp) { return } }
    $ns.Categories.Add($PickedUp) | Out-Null
}

function Invoke-Api([string[]]$CurlArgs) {
    # curl.exe is Windows-signed; reading the reply from a UTF-8 file keeps non-English text intact.
    $out = Join-Path $Temp ("resp-" + [guid]::NewGuid() + ".json")
    $code = & curl.exe -s -o $out -w "%{http_code}" @CurlArgs
    $body = if (Test-Path $out) { Get-Content -Raw -Encoding UTF8 $out } else { "" }
    Remove-Item $out -ErrorAction SilentlyContinue
    return @{ Code = [int]$code; Body = $body }
}

function Send-NewMail($folder) {
    $items = @()
    foreach ($item in $folder.Items) {
        if ($item.Class -eq 43 -and ("" + $item.Categories) -notmatch [regex]::Escape($PickedUp)) { $items += $item }
    }
    foreach ($item in $items) {
        $subject = $item.Subject
        $path = Join-Path $Temp ([guid]::NewGuid().ToString() + ".msg")
        try {
            $item.SaveAs($path, 9)   # olMSGUnicode
            $received = $item.ReceivedTime.ToString("yyyy-MM-dd HH:mm")
            $r = Invoke-Api @("-X", "POST", "-F", "file=@$path", "-F", "entry_id=$($item.EntryID)",
                              "-F", "received=$received", "$AppUrl/api/intake")
            if ($r.Code -ne 200) { Log "Could not hand over '$subject' (HTTP $($r.Code)): $($r.Body)"; continue }
            $result = $r.Body | ConvertFrom-Json
            $item.Categories = (("" + $item.Categories), $PickedUp | Where-Object { $_ }) -join ", "
            $item.Save()
            switch ($result.kind) {
                "bid"       { Log "Bid created from '$subject': triage started ($AppUrl/bids/$($result.bid_id))" }
                "bidassist" { Log "BidAssist alert '$subject': screening started ($AppUrl/shortlists/$($result.shortlist_id)); ignored: $($result.ignored -join ', ')" }
                "ignored"   { Log "BidAssist alert '$subject' ignored: $($result.reason)" }
            }
        } catch {
            Log "Error with '$subject': $($_.Exception.Message)"
        } finally {
            Remove-Item $path -ErrorAction SilentlyContinue
        }
    }
}

function Write-ReplyDrafts($ns) {
    $r = Invoke-Api @("$AppUrl/api/replies")
    if ($r.Code -ne 200) { Log "Could not fetch replies (HTTP $($r.Code)). Is the app running?"; return }
    $due = @($r.Body | ConvertFrom-Json)
    foreach ($d in $due) {
        if (-not $d) { continue }
        try {
            $original = $ns.GetItemFromID($d.entry_id)
            $reply = $original.ReplyAll()
            $reply.CC = (@(("" + $reply.CC), $d.cc) | Where-Object { $_ }) -join "; "
            $html = $d.html.Replace('$', '$$')
            $reply.HTMLBody = [regex]::Replace($reply.HTMLBody, '(<body[^>]*>)', "`$1$html", 1)
            foreach ($a in $d.attachments) {
                $file = Join-Path $DataDir ($a -replace '/', '\')
                if (Test-Path $file) { $reply.Attachments.Add($file) | Out-Null }
                else { Log "Attachment not found: $file" }
            }
            $reply.Save()   # Drafts only. Never Send().
            $ack = Invoke-Api @("-X", "POST", "$AppUrl/api/replies/$($d.bid_id)/drafted")
            Log "Reply drafted ($($d.decision)) for '$($original.Subject)'. Check your Drafts and press Send."
            if ($ack.Code -ne 200) { Log "  (could not mark it drafted in the app: HTTP $($ack.Code))" }
        } catch {
            Log "Could not draft the reply for bid $($d.bid_id): $($_.Exception.Message)"
        }
    }
}

$outlook = Get-Outlook
$ns = $outlook.GetNamespace("MAPI")
$folder = Get-BidFolder $ns
Ensure-Category $ns
Log "Watching Outlook folder '$($folder.FolderPath)' -> $AppUrl. Ctrl+C to stop."

while ($true) {
    try {
        Send-NewMail $folder
        Write-ReplyDrafts $ns
    } catch {
        Log "Pass failed: $($_.Exception.Message)"
    }
    if ($Once) { break }
    Start-Sleep -Seconds $IntervalSeconds
}
