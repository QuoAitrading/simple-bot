# Deploy Flask API to Azure
# Maintains Python 3.12 runtime

Write-Host "Deploying to Azure App Service..." -ForegroundColor Cyan

# Navigate to flask-api directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Create deployment package (zip current directory excluding unnecessary files)
$exclude = @('__pycache__', '.azure', 'migrations', '.git', '*.pyc', 'deploy.ps1')
$files = Get-ChildItem -Recurse -File | Where-Object {
    $path = $_.FullName
    -not ($exclude | Where-Object { $path -like "*$_*" })
}

Write-Host "Creating deployment package..." -ForegroundColor Yellow
$zipPath = ".\deploy_package.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath }

# Create zip with all filtered files
Compress-Archive -Path $files -DestinationPath $zipPath -Force

# Deploy to Azure using az webapp deployment
Write-Host "Deploying to quotrading-flask-api..." -ForegroundColor Yellow
az webapp deployment source config-zip `
    --resource-group quotrading-rg `
    --name quotrading-flask-api `
    --src $zipPath

# Clean up
Remove-Item $zipPath

Write-Host "`nDeployment complete!" -ForegroundColor Green
Write-Host "App URL: https://quotrading-flask-api.azurewebsites.net" -ForegroundColor Cyan
