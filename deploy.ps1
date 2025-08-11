# PowerShell Deployment Script for Wallet Scanner on GCP
# Replace YOUR_PROJECT_ID with your actual GCP project ID

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [string]$Region = "us-central1",
    [string]$ImageName = "wallet-scanner"
)

Write-Host "🚀 Starting GCP deployment for Wallet Scanner..." -ForegroundColor Green

# Step 1: Set the project
Write-Host "📋 Setting GCP project..." -ForegroundColor Yellow
gcloud config set project $ProjectId

# Step 2: Enable required APIs
Write-Host "🔧 Enabling required APIs..." -ForegroundColor Yellow
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable container.googleapis.com

# Step 3: Build and push Docker image
Write-Host "🏗️ Building Docker image..." -ForegroundColor Yellow
gcloud builds submit --tag "gcr.io/$ProjectId/$ImageName"

# Step 4: Deploy to Cloud Run
Write-Host "☁️ Deploying to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $ImageName `
    --image "gcr.io/$ProjectId/$ImageName" `
    --platform managed `
    --region $Region `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --timeout 3600 `
    --concurrency 1 `
    --min-instances 1 `
    --max-instances 1

Write-Host "✅ Deployment completed!" -ForegroundColor Green
Write-Host "📊 Check logs with: gcloud run logs tail $ImageName --region $Region" -ForegroundColor Cyan

# Optional: Set environment variables for Telegram
Write-Host "🔐 Setting up environment variables..." -ForegroundColor Yellow
Write-Host "Run these commands to set your Telegram credentials:" -ForegroundColor Cyan
Write-Host "gcloud run services update $ImageName --region $Region --set-env-vars TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN,TELEGRAM_CHAT_ID=YOUR_CHAT_ID" -ForegroundColor White
