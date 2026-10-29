# Tests for the pure functions in mailwatch.ps1 (no Outlook, no app needed).
# Run:  powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\test_mailwatch.ps1
$ErrorActionPreference = "Stop"
$script = Join-Path (Split-Path $PSScriptRoot -Parent) "mailwatch.ps1"
$ast = [System.Management.Automation.Language.Parser]::ParseFile($script, [ref]$null, [ref]$null)
foreach ($fn in $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)) {
    Invoke-Expression $fn.Extent.Text
}

$failures = 0
function Check([string]$name, [bool]$ok) {
    if ($ok) { Write-Host "PASS $name" } else { Write-Host "FAIL $name"; $script:failures++ }
}

# I-1: a JSON array of several replies must become several items (Windows PowerShell 5.1 wraps it otherwise)
$two = ConvertTo-DueList '[{"bid_id":"a","entry_id":"E1"},{"bid_id":"b","entry_id":"E2"}]'
Check "two replies -> two items" ($two.Count -eq 2 -and $two[0].bid_id -eq "a" -and $two[1].entry_id -eq "E2")
$one = ConvertTo-DueList '[{"bid_id":"a","entry_id":"E1"}]'
Check "one reply -> one item" ($one.Count -eq 1 -and $one[0].bid_id -eq "a")
$none = ConvertTo-DueList '[]'
Check "no replies -> zero items" ($none.Count -eq 0)

# I-2: our text must be inserted whether or not the reply body has a <body> tag
$withBody = Add-ReplyHtml '<html><head></head><body lang="EN"><p>original</p></body></html>' '<p>OUR $1 TEXT</p>'
Check "inserted after <body>" ($withBody -match '<body lang="EN"><p>OUR \$1 TEXT</p><p>original</p>')
$noBody = Add-ReplyHtml 'plain original text' '<p>OUR TEXT</p>'
Check "prepended when there is no <body>" ($noBody.StartsWith('<p>OUR TEXT</p>') -and $noBody.Contains('plain original text'))

if ($failures) { Write-Host "$failures failed"; exit 1 } else { Write-Host "all passed" }
