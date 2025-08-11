# Wallet Scanner GCP Setup Script
# This script will guide you through the deployment process

param(
    [string]$ProjectId = "",
    [string]$TelegramBotToken = "",
    [string]$TelegramChatId = ""
)

Write-Host "🎯 Wallet Scanner GCP Deployment Setup" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green

# Check if gcloud is installed
try {
    $gcloudVersion = gcloud version --format="value(Google Cloud SDK)" 2>$null
    if ($gcloudVersion) {
        Write-Host "✅ Google Cloud SDK found: $gcloudVersion" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Google Cloud SDK not found!" -ForegroundColor Red
    Write-Host "Please install it from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    exit 1
}

# Get project ID if not provided
if (-not $ProjectId) {
    Write-Host "`n📋 Available GCP Projects:" -ForegroundColor Yellow
    gcloud projects list --format="table(projectId,name,projectNumber)"
    
    $ProjectId = Read-Host "`nEnter your GCP Project ID"
    if (-not $ProjectId) {
        Write-Host "❌ Project ID is required!" -ForegroundColor Red
        exit 1
    }
}

# Get Telegram credentials if not provided
if (-not $TelegramBotToken) {
    Write-Host "`n🤖 Telegram Bot Setup:" -ForegroundColor Yellow
    Write-Host "1. Message @BotFather on Telegram" -ForegroundColor Cyan
    Write-Host "2. Send: /newbot" -ForegroundColor Cyan
    Write-Host "3. Follow instructions to get your bot token" -ForegroundColor Cyan
    $TelegramBotToken = Read-Host "`nEnter your Telegram Bot Token"
}

if (-not $TelegramChatId) {
    Write-Host "`n💬 Get your Chat ID:" -ForegroundColor Yellow
    Write-Host "1. Add your bot to a group or start a chat" -ForegroundColor Cyan
    Write-Host "2. Send a message to the bot" -ForegroundColor Cyan
    Write-Host "3. Visit: https://api.telegram.org/bot$TelegramBotToken/getUpdates" -ForegroundColor Cyan
    Write-Host "4. Look for 'chat':{'id': YOUR_CHAT_ID}" -ForegroundColor Cyan
    $TelegramChatId = Read-Host "`nEnter your Telegram Chat ID"
}

Write-Host "`n🚀 Starting deployment with:" -ForegroundColor Green
Write-Host "Project ID: $ProjectId" -ForegroundColor Cyan
Write-Host "Bot Token: $($TelegramBotToken.Substring(0,10))..." -ForegroundColor Cyan
Write-Host "Chat ID: $TelegramChatId" -ForegroundColor Cyan

$confirm = Read-Host "`nProceed with deployment? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "❌ Deployment cancelled." -ForegroundColor Yellow
    exit 0
}

# Set project
Write-Host "`n📋 Setting GCP project..." -ForegroundColor Yellow
gcloud config set project $ProjectId

# Enable APIs
Write-Host "`n🔧 Enabling required APIs..." -ForegroundColor Yellow
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com

# Build image
Write-Host "`n🏗️ Building Docker image..." -ForegroundColor Yellow
gcloud builds submit --tag "gcr.io/$ProjectId/wallet-scanner"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed!" -ForegroundColor Red
    exit 1
}

# Deploy to Cloud Run
Write-Host "`n☁️ Deploying to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy wallet-scanner `
    --image "gcr.io/$ProjectId/wallet-scanner" `
    --platform managed `
    --region us-central1 `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --timeout 3600 `
    --concurrency 1 `
    --min-instances 1 `
    --max-instances 1 `
    --set-env-vars "TELEGRAM_BOT_TOKEN=$TelegramBotToken,TELEGRAM_CHAT_ID=$TelegramChatId"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Deployment successful!" -ForegroundColor Green
    Write-Host "`n📊 Useful commands:" -ForegroundColor Yellow
    Write-Host "View logs: gcloud run logs tail wallet-scanner --region us-central1" -ForegroundColor Cyan
    Write-Host "View service: gcloud run services describe wallet-scanner --region us-central1" -ForegroundColor Cyan
    Write-Host "Delete service: gcloud run services delete wallet-scanner --region us-central1" -ForegroundColor Cyan
    
    Write-Host "`n💰 Estimated monthly cost: ~$50-65 USD" -ForegroundColor Yellow
    Write-Host "🔗 GCP Console: https://console.cloud.google.com/run/detail/us-central1/wallet-scanner/metrics?project=$ProjectId" -ForegroundColor Cyan
} else {
    Write-Host "`n❌ Deployment failed!" -ForegroundColor Red
    Write-Host "Check the error messages above for troubleshooting." -ForegroundColor Yellow
}
