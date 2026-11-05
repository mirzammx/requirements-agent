<#
.SYNOPSIS
  Puts the Bid desk on Azure App Service (Linux B1), behind company Microsoft sign-in.

.DESCRIPTION
  Creates (or updates, when run again) in resource group rugrel-biddesk:
    - a container registry, with the app image built here by Docker and uploaded
      (.dockerignore keeps samples/, data/ and .env out of it)
    - a storage account with an Azure Files share mounted at /app/data (tenders, summaries, documents)
    - an App Service plan (Linux B1) and the web app, always on, HTTPS only
    - company sign-in (Entra ID). Only the mail watcher's three /api/ paths skip sign-in;
      they need the secret key instead.
  Then points this PC's mail watcher at the Azure address (BIDDESK_URL, BIDDESK_API_KEY for your Windows user).

  Run "az login" first. Running it again rebuilds the image and restarts the app (use it to deploy updates).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\deploy-azure.ps1
#>
param(
    [string]$Location = "centralindia",
    [string]$ResourceGroup = "rugrel-biddesk"
)

# The Az helper throws on any failed az call; "Continue" keeps expected "not found" lookups (2>$null) harmless in PowerShell 5.1.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
function Az {
    $out = & az.cmd @args
    if ($LASTEXITCODE -ne 0) { throw "az $($args[0..2] -join ' ') ... failed (see the message above)" }
    return $out
}
function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }

$sub = Az account show --query id -o tsv
$tenant = Az account show --query tenantId -o tsv
Write-Host "Subscription: $(Az account show --query name -o tsv) ($sub)"
$suffix = ($sub -replace '-', '').Substring(0, 6)           # same names every run for this subscription
$acr = "rugrelbid$suffix"; $storage = "rugrelbid$suffix"; $share = "biddesk-data"
$plan = "rugrel-biddesk-plan"; $app = "rugrel-biddesk-$suffix"; $hostName = "$app.azurewebsites.net"
$image = "$acr.azurecr.io/biddesk:latest"

$envFile = @{}
if (Test-Path .env) { Get-Content .env | Where-Object { $_ -match '^\s*([A-Z_]+)\s*=\s*(.+)$' } | ForEach-Object { $envFile[$Matches[1]] = $Matches[2].Trim() } }
if (-not ($envFile.GEMINI_API_KEY -or $envFile.ANTHROPIC_API_KEY)) { throw "Put GEMINI_API_KEY=... (or ANTHROPIC_API_KEY=...) in .env first." }

Step "Resource providers"
foreach ($p in "Microsoft.Web", "Microsoft.ContainerRegistry", "Microsoft.Storage") { Az provider register --namespace $p --wait | Out-Null }

Step "Resource group $ResourceGroup ($Location)"
Az group create -n $ResourceGroup -l $Location -o none

Step "Container registry $acr; build the image here with Docker and upload it"
# Admin login on: the web app pulls with it (this subscription's policy blocks granting AcrPull to the app).
Az acr create -g $ResourceGroup -n $acr --sku Basic --admin-enabled true -o none
Az acr update -n $acr --admin-enabled true -o none
# Built locally (az acr build's upload step fails in this Azure CLI); .dockerignore keeps samples/, data/, .env out.
& docker build -t $image -t "$acr.azurecr.io/biddesk:$(git rev-parse --short HEAD)" .
if ($LASTEXITCODE -ne 0) { throw "docker build failed. Is Docker Desktop running?" }
$token = Az acr login -n $acr --expose-token --query accessToken -o tsv
# Passed as an argument: PowerShell 5.1 appends CRLF when piping to --password-stdin, which breaks the token.
$password = ("" + $token).Trim()
& docker login "$acr.azurecr.io" -u 00000000-0000-0000-0000-000000000000 -p $password 2>&1 | Where-Object { $_ -notmatch 'WARNING' }
if ($LASTEXITCODE -ne 0) { throw "docker login to $acr failed" }
& docker push --all-tags "$acr.azurecr.io/biddesk"
if ($LASTEXITCODE -ne 0) { throw "docker push failed" }


# Everything else is one ARM template (infra/azuredeploy.json): this PC's Smart App Control blocks the
# Azure CLI's "webapp" and "storage" commands, but "deployment", "rest" and "ad" work.
$site = "https://management.azure.com/subscriptions/$sub/resourceGroups/$ResourceGroup/providers/Microsoft.Web/sites/$app"
$current = & az.cmd rest --method post --url "$site/config/appsettings/list?api-version=2023-12-01" --query properties -o json 2>$null | Out-String
$current = if ($LASTEXITCODE -eq 0 -and $current.Trim()) { $current | ConvertFrom-Json } else { $null }

Step "Company sign-in (Entra ID app registration)"
# Stop here rather than ever putting the app online without sign-in.
$appId = Az ad app list --display-name "Bid desk ($app)" --query "[0].appId" -o tsv
if (-not $appId) {
    $appId = Az ad app create --display-name "Bid desk ($app)" --sign-in-audience AzureADMyOrg `
        --web-redirect-uris "https://$hostName/.auth/login/aad/callback" --enable-id-token-issuance true --query appId -o tsv
    Az ad sp create --id $appId -o none
}
$secret = if ($current -and $current.MICROSOFT_PROVIDER_AUTHENTICATION_SECRET) { $current.MICROSOFT_PROVIDER_AUTHENTICATION_SECRET }
          else { Az ad app credential reset --id $appId --display-name "app-service" --years 2 --append --query password -o tsv }
$apiKey = if ($current -and $current.BIDDESK_API_KEY) { $current.BIDDESK_API_KEY }
          else { -join ((48..57) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ }) }

Step "Storage, App Service plan (Linux B1), web app $app, data mount, settings and sign-in"
$params = @{ location = $Location; appName = $app; planName = $plan; registryName = $acr; storageName = $storage
             shareName = $share; image = $image; tenantId = $tenant; authClientId = $appId; authClientSecret = $secret
             apiKey = $apiKey; geminiApiKey = "$($envFile.GEMINI_API_KEY)"; anthropicApiKey = "$($envFile.ANTHROPIC_API_KEY)" }
$paramFile = Join-Path $env:TEMP ("biddesk-params-" + [guid]::NewGuid() + ".json")
$wrapped = @{ '$schema' = "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#"
              contentVersion = "1.0.0.0"; parameters = @{} }
foreach ($k in $params.Keys) { $wrapped.parameters[$k] = @{ value = $params[$k] } }
[IO.File]::WriteAllText($paramFile, ($wrapped | ConvertTo-Json -Depth 5))
try {
    Az deployment group create -g $ResourceGroup -n "biddesk-$(Get-Date -Format yyyyMMdd-HHmmss)" `
        --template-file infra\azuredeploy.json --parameters "@$paramFile" -o none
} finally { Remove-Item $paramFile }   # holds secrets

Step "Restart (pulls the new image)"
Start-Sleep -Seconds 20   # give the new AcrPull permission a moment to take effect
Az rest --method post --url "$site/restart?api-version=2023-12-01" -o none

Step "Point this PC's mail watcher at Azure"
setx BIDDESK_URL "https://$hostName" | Out-Null
setx BIDDESK_API_KEY $apiKey | Out-Null

Write-Host "`nDone. Bid desk: https://$hostName (company sign-in required)" -ForegroundColor Green
Write-Host "The first start takes a few minutes. The mail watcher uses Azure after you log out and back in (or restart it)."