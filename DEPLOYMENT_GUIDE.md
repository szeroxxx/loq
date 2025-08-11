# Wallet Scanner GCP Deployment Guide

## Prerequisites

1. **Google Cloud Platform Account**: Sign up at https://cloud.google.com/
2. **GCP Project**: Create a new project in GCP Console
3. **Google Cloud SDK**: Install from https://cloud.google.com/sdk/docs/install
4. **Docker** (optional, for local testing)

## Quick Start Deployment

### Method 1: Using Cloud Run (Recommended for 24/7 operation)

1. **Install Google Cloud CLI**
   ```powershell
   # Download and install from: https://cloud.google.com/sdk/docs/install-sdk
   ```

2. **Authenticate with Google Cloud**
   ```powershell
   gcloud auth login
   gcloud auth application-default login
   ```

3. **Set your project ID**
   ```powershell
   $PROJECT_ID = "your-project-id-here"
   gcloud config set project $PROJECT_ID
   ```

4. **Deploy using our PowerShell script**
   ```powershell
   .\deploy.ps1 -ProjectId "your-project-id-here"
   ```

### Method 2: Manual Step-by-Step Deployment

1. **Enable required APIs**
   ```powershell
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable run.googleapis.com
   ```

2. **Build Docker image**
   ```powershell
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/wallet-scanner
   ```

3. **Deploy to Cloud Run**
   ```powershell
   gcloud run deploy wallet-scanner `
     --image gcr.io/YOUR_PROJECT_ID/wallet-scanner `
     --platform managed `
     --region us-central1 `
     --allow-unauthenticated `
     --memory 1Gi `
     --cpu 1 `
     --timeout 3600 `
     --min-instances 1 `
     --max-instances 1
   ```

4. **Set environment variables (for security)**
   ```powershell
   gcloud run services update wallet-scanner `
     --region us-central1 `
     --set-env-vars TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN,TELEGRAM_CHAT_ID=YOUR_CHAT_ID
   ```

## Configuration

### Environment Variables
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `TELEGRAM_CHAT_ID`: Your Telegram chat ID
- `LOG_DIR`: Directory for logs (default: /app/data)
- `DATA_DIR`: Directory for data files (default: /app/data)

### Cost Optimization
- **Cloud Run**: Pay only when running, automatic scaling
- **Memory**: 1GB allocated (adjust based on needs)
- **CPU**: 1 vCPU allocated
- **Timeout**: 1 hour per request

## Monitoring and Management

### View Logs
```powershell
gcloud run logs tail wallet-scanner --region us-central1
```

### Update Environment Variables
```powershell
gcloud run services update wallet-scanner `
  --region us-central1 `
  --set-env-vars KEY=VALUE
```

### Scale Service
```powershell
gcloud run services update wallet-scanner `
  --region us-central1 `
  --min-instances 1 `
  --max-instances 1
```

### Delete Service
```powershell
gcloud run services delete wallet-scanner --region us-central1
```

## Security Best Practices

1. **Use Secret Manager** for sensitive data:
   ```powershell
   # Create secrets
   echo "YOUR_BOT_TOKEN" | gcloud secrets create telegram-bot-token --data-file=-
   echo "YOUR_CHAT_ID" | gcloud secrets create telegram-chat-id --data-file=-
   ```

2. **Update service to use secrets**:
   ```powershell
   gcloud run services update wallet-scanner `
     --region us-central1 `
     --set-env-vars TELEGRAM_BOT_TOKEN=/secrets/telegram-bot-token/latest,TELEGRAM_CHAT_ID=/secrets/telegram-chat-id/latest
   ```

## Troubleshooting

### Common Issues
1. **Permission Denied**: Ensure you have Owner or Editor role
2. **API Not Enabled**: Run the enable commands above
3. **Out of Memory**: Increase memory allocation
4. **Timeout**: Increase timeout or optimize code

### Debug Commands
```powershell
# Check service status
gcloud run services describe wallet-scanner --region us-central1

# View service logs
gcloud run logs tail wallet-scanner --region us-central1

# Test locally with Docker
docker build -t wallet-scanner .
docker run -e TELEGRAM_BOT_TOKEN=your_token wallet-scanner
```

## Cost Estimation

**Cloud Run Pricing** (us-central1):
- vCPU: $0.00002400 per vCPU-second
- Memory: $0.00000250 per GB-second
- Requests: $0.40 per million requests

**Estimated Monthly Cost** (running 24/7):
- ~$52-65 USD per month for continuous operation
- Much cheaper if the bot has idle periods

## Alternative: Compute Engine for Lower Costs

For 24/7 operation, consider using Compute Engine f1-micro (free tier):

```powershell
# Create VM instance
gcloud compute instances create wallet-scanner-vm `
  --zone us-central1-a `
  --machine-type f1-micro `
  --image-family ubuntu-2004-lts `
  --image-project ubuntu-os-cloud `
  --boot-disk-size 10GB
```

## Support

- **GCP Documentation**: https://cloud.google.com/run/docs
- **Pricing Calculator**: https://cloud.google.com/products/calculator
- **Support**: https://cloud.google.com/support
