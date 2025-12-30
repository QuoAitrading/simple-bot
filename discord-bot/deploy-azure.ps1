# Deploy Discord Ticket Bot to Azure App Service
# Same method as your Flask API - simple and reliable

Write-Host "Deploying Discord Ticket Bot to Azure..." -ForegroundColor Cyan

# Check Azure CLI login
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "Not logged in to Azure. Running 'az login'..." -ForegroundColor Yellow
    az login
}

$ResourceGroup = "quotrading-rg"
$AppName = "quotrading-discord-bot"
$Location = "eastus"

# Create webapp if it doesn't exist
Write-Host "Creating/updating Azure Web App..." -ForegroundColor Green
az webapp up --name $AppName --resource-group $ResourceGroup --runtime "PYTHON:3.11" --sku B1

# Set the bot token as environment variable
$configPath = Join-Path $PSScriptRoot "config.json"
if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    $botToken = $config.bot_token
    
    Write-Host "Setting bot token as environment variable..." -ForegroundColor Green
    az webapp config appsettings set --name $AppName --resource-group $ResourceGroup --settings DISCORD_BOT_TOKEN=$botToken
}

# Set startup command
Write-Host "Configuring startup command..." -ForegroundColor Green
az webapp config set --name $AppName --resource-group $ResourceGroup --startup-file "start.sh"

# Enable always on to prevent the app from sleeping
Write-Host "Enabling Always On..." -ForegroundColor Green
az webapp config set --name $AppName --resource-group $ResourceGroup --always-on true

# Set web.config for proper Azure integration
Write-Host "Ensuring web.config is deployed..." -ForegroundColor Green

Write-Host ""
Write-Host "Done! Discord bot deployed to Azure." -ForegroundColor Green
Write-Host "Check logs: az webapp log tail --name $AppName --resource-group $ResourceGroup" -ForegroundColor Yellow
Write-Host "Check status: https://$AppName.azurewebsites.net/health" -ForegroundColor Yellow
