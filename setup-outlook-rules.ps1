<#
.SYNOPSIS
  Adds two Outlook rules that file bid mail into the "Bid desk" folder, so nobody has to drag mails.

.DESCRIPTION
  Rule "Bid desk - BD bids":       mail from BD (Imran, Muyeed, Arif) with an attachment and a tender word
                                   in the subject (RFQ, tender, bid, enquiry, ...). Replies ("RE:") are left alone.
  Rule "Bid desk - BidAssist":     mail whose sender address contains "bidassist".
  Both move the mail into Inbox\Bid desk. Running the script again replaces the two rules (it never touches
  other rules). The rules only apply to new mail; old mail stays where it is.

  To remove them: Outlook > File > Manage Rules & Alerts, delete the two "Bid desk - ..." rules.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\setup-outlook-rules.ps1
#>
param(
    [string]$FolderName = "Bid desk",
    [string[]]$BdSenders = @("imran.khan@rugrel.com", "muyeed.shariff@rugrel.com", "md.arif@rugrel.com"),
    [string[]]$TenderWords = @("RFQ", "RFP", "tender", "bid", "enquiry", "inquiry", "quotation", "EOI", "GEM/"),
    [string]$BidAssistSender = "bidassist"
)

$ErrorActionPreference = "Stop"
$BdRule = "Bid desk - BD bids"
$AlertRule = "Bid desk - BidAssist"

try { $outlook = [Runtime.InteropServices.Marshal]::GetActiveObject("Outlook.Application") }
catch { $outlook = New-Object -ComObject Outlook.Application }
$ns = $outlook.GetNamespace("MAPI")
$inbox = $ns.GetDefaultFolder(6)   # olFolderInbox
$folder = $null
foreach ($f in $inbox.Folders) { if ($f.Name -eq $FolderName) { $folder = $f } }
if (-not $folder) { $folder = $inbox.Folders.Add($FolderName) }

function Set-MoveTo($rule) {
    # A plain "$action.Folder = $folder" is silently dropped by PowerShell's COM binder.
    $action = $rule.Actions.MoveToFolder
    [void][System.__ComObject].InvokeMember("Folder", [System.Reflection.BindingFlags]::SetProperty, $null, $action, @($folder))
    $action.Enabled = $true
}

$rules = $ns.DefaultStore.GetRules()
for ($i = $rules.Count; $i -ge 1; $i--) {
    if ($rules.Item($i).Name -in @($BdRule, $AlertRule)) { $rules.Remove($i) }
}

# 0 = olRuleReceive
$bd = $rules.Create($BdRule, 0)
$bd.Conditions.SenderAddress.Address = [string[]]$BdSenders
$bd.Conditions.SenderAddress.Enabled = $true
$bd.Conditions.HasAttachment.Enabled = $true
$bd.Conditions.Subject.Text = [string[]]$TenderWords
$bd.Conditions.Subject.Enabled = $true
$bd.Exceptions.Subject.Text = [string[]]@("RE:")
$bd.Exceptions.Subject.Enabled = $true
Set-MoveTo $bd

$alert = $rules.Create($AlertRule, 0)
$alert.Conditions.SenderAddress.Address = [string[]]@($BidAssistSender)
$alert.Conditions.SenderAddress.Enabled = $true
Set-MoveTo $alert

$rules.Save($false)
Write-Host "Done. New mail from BD (with an RFQ attached) and from BidAssist now goes to '$($folder.FolderPath)'."
Write-Host "Check or remove them any time: Outlook > File > Manage Rules & Alerts."
