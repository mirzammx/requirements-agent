<#
.SYNOPSIS
  Puts the Bid desk on Azure App Service (Linux B1), behind company Microsoft sign-in.

.DESCRIPTION
  Creates (or updates, when run again) in resource group rugrel-biddesk:
    - a container registry, and builds the app image there from this folder
      (.dockerignore keeps samples/, data/ and .env out of it)
    - a storage account with an Azure Files share mounted at /app/data (tenders, summaries, documents)
    - an App Service plan (Linux B1) and the web app, always on, HTTPS only
    - company sign-in (Entra ID). Only the mail watcher's three /api/ paths skip sign-in;
      they need the secret key instead.
  Then points this PC's mail watcher at the Azure address (BIDDESK_URL, BIDDESK_API_KEY for your Windows user).

  Run "az login" first. Running it again rebuilds the image and restarts the app (use it to deploy updates).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\deploy-azure.ps1
  powershell -ExecutionPolicy Bypass -File .\deploy-azure.ps1 -CopyData     # also upload the local data\ folder once
#>
param(
    [string]$Location = "centralindia",
    [string]$ResourceGroup = "rugrel-biddesk",
    [switch]$CopyData
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
function Az {
    $out = & az @args
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

Step "Container registry $acr, and build the image there"
Az acr create -g $ResourceGroup -n $acr --sku Basic --admin-enabled false -o none
Az acr build -r $acr -t biddesk:latest -t "biddesk:$(git rev-parse --short HEAD)" . --no-logs -o none

Step "Storage for tender data ($storage / $share)"
Az storage account create -g $ResourceGroup -n $storage -l $Location --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false -o none
Az storage share-rm create -g $ResourceGroup --storage-account $storage -n $share --quota 100 -o none 2>$null
$storageKey = Az storage account keys list -g $ResourceGroup -n $storage --query "[0].value" -o tsv
if ($CopyData -and (Test-Path data)) {
    Step "Copying the local data\ folder to Azure (one time)"
    Az storage file upload-batch --account-name $storage --account-key $storageKey --destination $share --source data -o none
}

Step "App Service plan (Linux B1) and web app $app"
Az appservice plan create -g $ResourceGroup -n $plan --is-linux --sku B1 -o none
$exists = & az webapp show -g $ResourceGroup -n $app --query name -o tsv 2>$null
if (-not $exists) { Az webapp create -g $ResourceGroup -p $plan -n $app --container-image-name $image -o none }
Az webapp update -g $ResourceGroup -n $app --https-only true -o none
Az webapp config set -g $ResourceGroup -n $app --always-on true --ftps-state Disabled --min-tls-version 1.2 -o none

Step "Let the app pull its image (managed identity)"
$principal = Az webapp identity assign -g $ResourceGroup -n $app --query principalId -o tsv
$acrId = Az acr show -n $acr --query id -o tsv
& az role assignment create --assignee-object-id $principal --assignee-principal-type ServicePrincipal --role AcrPull --scope $acrId -o none 2>$null
if ($LASTEXITCODE -eq 0) {
    Az webapp config set -g $ResourceGroup -n $app --generic-configurations '{\"acrUseManagedIdentityCreds\": true}' -o none
    Az webapp config container set -g $ResourceGroup -n $app --container-image-name $image --container-registry-url "https://$acr.azurecr.io" -o none
} else {
    Write-Host "No permission to assign roles; using the registry's admin login instead." -ForegroundColor Yellow
    Az acr update -n $acr --admin-enabled true -o none
    $acrUser = Az acr credential show -n $acr --query username -o tsv
    $acrPass = Az acr credential show -n $acr --query "passwords[0].value" -o tsv
    Az webapp config container set -g $ResourceGroup -n $app --container-image-name $image --container-registry-url "https://$acr.azurecr.io" --container-registry-user $acrUser --container-registry-password $acrPass -o none
}

Step "Mount the data share at /app/data"
$mounted = & az webapp config storage-account list -g $ResourceGroup -n $app --query "[?name=='data'].name" -o tsv 2>$null
if (-not $mounted) {
    Az webapp config storage-account add -g $ResourceGroup -n $app --custom-id data --storage-type AzureFiles --share-name $share --account-name $storage --access-key $storageKey --mount-path /app/data -o none
}

Step "App settings"
$apiKey = & az webapp config appsettings list -g $ResourceGroup -n $app --query "[?name=='BIDDESK_API_KEY'].value" -o tsv 2>$null
if (-not $apiKey) { $apiKey = -join ((48..57) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ }) }
$settings = @("WEBSITES_PORT=8000", "WEBSITES_CONTAINER_START_TIME_LIMIT=600", "TZ=Asia/Kolkata",
              "BIDDESK_DATA_DIR=/app/data", "BIDDESK_ALLOWED_HOSTS=$hostName", "BIDDESK_API_KEY=$apiKey")
foreach ($k in "GEMINI_API_KEY", "ANTHROPIC_API_KEY") { if ($envFile[$k]) { $settings += "$k=$($envFile[$k])" } }
Az webapp config appsettings set -g $ResourceGroup -n $app --settings @settings -o none

Step "Company sign-in (Entra ID)"
$authOk = $true
try {
    $appId = Az ad app list --display-name "Bid desk ($app)" --query "[0].appId" -o tsv
    if (-not $appId) {
        $appId = Az ad app create --display-name "Bid desk ($app)" --sign-in-audience AzureADMyOrg `
            --web-redirect-uris "https://$hostName/.auth/login/aad/callback" --enable-id-token-issuance true --query appId -o tsv
        Az ad sp create --id $appId -o none
    }
    $secret = Az ad app credential reset --id $appId --display-name "app-service" --years 2 --query password -o tsv
    Az webapp config appsettings set -g $ResourceGroup -n $app --settings "MICROSOFT_PROVIDER_AUTHENTICATION_SECRET=$secret" -o none
    Az webapp auth microsoft update -g $ResourceGroup -n $app --client-id $appId `
        --client-secret-setting-name MICROSOFT_PROVIDER_AUTHENTICATION_SECRET `
        --issuer "https://login.microsoftonline.com/$tenant/v2.0" --yes -o none
    Az webapp auth update -g $ResourceGroup -n $app --enabled true --action RedirectToLoginPage `
        --redirect-provider azureactivedirectory --excluded-paths "[/api/intake,/api/replies,/api/attachment]" -o none
} catch {
    $authOk = $false
    Write-Host "Could not set up sign-in automatically: $($_.Exception.Message)" -ForegroundColor Yellow
}

Step "Restart"
Az webapp restart -g $ResourceGroup -n $app -o none

Step "Point this PC's mail watcher at Azure"
setx BIDDESK_URL "https://$hostName" | Out-Null
setx BIDDESK_API_KEY $apiKey | Out-Null

Write-Host "`nDone. Bid desk: https://$hostName" -ForegroundColor Green
Write-Host "The first start takes a few minutes. The mail watcher uses Azure after you log out and back in (or restart it)."
if (-not $authOk) {
    Write-Host @"
SIGN-IN IS NOT ON YET, so do not share the address. In the Azure portal open App Service '$app' >
Authentication > Add identity provider > Microsoft > 'Current tenant - single tenant' >
Restrict access: Require authentication > Add. Then under 'Excluded paths' (Edit authentication settings)
add /api/intake, /api/replies and /api/attachment. If you can't create app registrations, ask IT to do this step.
"@ -ForegroundColor Yellow
}
